"""Fixed Root-only host worker; no HTTP exposure or arbitrary paths/commands."""
from contextlib import ExitStack
import hashlib
import json
import logging
import os
import sys
import time

import sqlalchemy as sa
from app.database import make_engine
from app.graph import GraphConfig,GraphError
from app.graph_access_runtime import binding as access_binding
from app.graph_deadline import bounded_operation
from app.notification_certificate import CertificateMaterial
from app.notification_model import CERTIFICATE_TOKEN,OperationBudget,graph_scope,identity
from app.notification_schema007 import monitor
from app.rotation_adoption import AdoptionJournal,metadata
from app.rotation_core import register
from app.rotation_cleanup import CleanupJournal
from app.rotation_graph import rotation_client
from app.rotation_journal import RootJournal
from app.rotation_model import RotationBinding,sha,unique_json,uuid
from app.rotation_state import RotationStore
from app.rotation_maintenance import maintain,project_cleanup
from app.rotation_schedule import ScheduleJournal,overview

DIRECTORY="/var/lib/invoice-importer/rotation"
FIELDS={"status":set(),"register":set(),"candidate-verified":{"receipt"},
    "prepare":{"images","paused","drain_identity"},"activation-started":set(),"activated":set(),
    "consumers":{"receipts"},"proof-started":{"consumer","epoch","base_revision"},"proof-unknown":set(),
    "proof-verified":{"receipt"},"commit":{"paused","drain_identity"},"rollback":set(),"rollback-unknown":set(),
    "recover":{"pem_hash","quiet_evidence","paused","drain_identity"},"monitor":set(),"read":set()}
FIELDS["publish"]=set()
FIELDS["resume-closed"]={"seal"}
FIELDS["cleanup"]=set()
FIELDS["scheduled-check"]=set()
FIELDS["overview"]=set()


def request(raw):
    try:
        if len(raw)>16384:raise ValueError()
        value=json.loads(raw,object_pairs_hook=unique_json)
        command=value["command"]
        if (command not in FIELDS or set(value)!={"command","operation_id"}|FIELDS[command]):raise ValueError()
        if command in {"scheduled-check","overview"} and value["operation_id"] is not None:raise ValueError()
        if command not in {"status","monitor","scheduled-check","overview"} or value["operation_id"] is not None:uuid(value["operation_id"])
        return value
    except (ValueError,KeyError,TypeError,GraphError):raise GraphError("rotation_host_request_invalid") from None


def monitor_state(engine,config):
    scope=graph_scope(config.tenant_id,config.client_id,config.mailbox)
    key=identity([scope,"certificate",CERTIFICATE_TOKEN])
    # Current locking read, including uncertain prior commit, never an RR snapshot.
    with engine.begin() as connection:
        row=connection.execute(sa.select(monitor).where(monitor.c.monitor_key==key,
            monitor.c.scope_key==scope,monitor.c.kind=="certificate").with_for_update()).mappings().one_or_none()
    return dict(revision=row["revision"],proof=json.loads(row["payload"]).get("proof")) if row else dict(revision=0,proof=None)


def project(store,operation,core):
    """Rebuild only already proven B checkpoints, preserving its one-POST contract."""
    row=store.read(operation);target=core["phase"]
    if row["state"]=="requested":row=store.project_core(operation,row["revision"],"prepared")
    if row["state"]=="prepared" and target!="prepared":row=store.project_core(operation,row["revision"],"registration_started")
    if row["state"]=="registration_started" and target in {"registration_unknown","registration_rejected","registered","candidate_verified"}:
        state="registered" if target=="candidate_verified" else target
        code={"registration_unknown":"rotation_registration_unknown","registration_rejected":"rotation_registration_rejected"}.get(state)
        row=store.project_core(operation,row["revision"],state,code=code)
    if row["state"]=="registration_unknown" and target in {"registered","candidate_verified"}:
        row=store.project_core(operation,row["revision"],"registered")
    if row["state"]=="registered" and target=="candidate_verified":row=store.project_core(operation,row["revision"],target)
    return row


def candidate_receipt(value,access,operation,material,now):
    if not isinstance(value,dict) or set(value)!={"container_id","image","probe"}:raise GraphError("rotation_candidate_probe_failed")
    sha(value["container_id"]);probe=value["probe"]
    if (not isinstance(probe,dict) or probe.get("ok") is not True or probe.get("code")!="graph_probe_verified"
            or any(probe.get(name)!=expected for name,expected in access.fields().items())
            or probe.get("operation_id")!=operation or probe.get("purpose")!="candidate-read"
            or probe.get("consumer_role")!="candidate" or probe.get("consumer_id")!=hashlib.sha256(value["container_id"].encode()).hexdigest()
            or probe.get("fingerprint")!=material.fingerprint or probe.get("pem_hash")!=hashlib.sha256(material.pem).hexdigest()
            or type(probe.get("at")) is not int or not 0<=now-probe["at"]<=60
            or probe.get("proof_revision") is not None or probe.get("proof_at") is not None
            or probe.get("receipt_hash")!=identity({name:item for name,item in probe.items() if name!="receipt_hash"})):
        raise GraphError("rotation_candidate_probe_failed")


def project_host(store,operation,state):
    row=store.read(operation)
    if state["phase"]=="prepared" and row["state"]=="registered":return row
    if row["state"] in {"registered","candidate_verified"}:row=store.project_host(operation,row["revision"],"adoption_prepared")
    target="adopted" if state["phase"]=="committed" else "rollback_unknown" if state["phase"]=="rollback_unknown" else "adopting"
    if state["phase"]=="prepared":return row
    code="rotation_rolled_back" if target=="adopted" and state["target"]=="old" else (
        "rotation_rollback_unknown" if target=="rollback_unknown" else "rotation_proof_unknown" if state["phase"]=="proof_unknown" else
        "rotation_rollback_pending" if state["target"]=="old" else None)
    if row["state"]=="adoption_prepared":row=store.project_host(operation,row["revision"],"adopting",code=code)
    if row["state"]!=target:row=store.project_host(operation,row["revision"],target,code=code)
    return row


def execute(value,deadline):
    config=GraphConfig.load("/run/importer/graph.json");access=access_binding(config)
    # Access profile's protected app identity, also validated by access_binding.
    from app.graph import protected_bytes
    profile=json.loads(protected_bytes("/run/importer/graph-access-binding.json"),object_pairs_hook=unique_json)
    bound=RotationBinding(access.instance_id,config.tenant_id,config.client_id,profile["application_id"],config.mailbox)
    engine=make_engine()
    try:
        store=RotationStore(engine,bound);head=store.status();operation=value["operation_id"]
        if operation is not None:
            store.read(operation)
            if head["active_operation"]!=operation and value["command"] not in {"read","monitor","publish","resume-closed"}:raise GraphError("rotation_operation_changed")
        journal=RootJournal(DIRECTORY,bound)
        with journal.session():
            host=AdoptionJournal(journal,access);now=int(time.time());command=value["command"]
            current=CertificateMaterial.load("/run/secrets/graph_credential")
            if command=="status":
                active=head["active_operation"]
                return dict(ok=True,binding=access.fields(),head=head,current=metadata(current),request=store.read(active) if active else None,
                    notification_scope=graph_scope(config.tenant_id,config.client_id,config.mailbox),
                    core=journal.state(active) if active else None,host=host.state(active) if active else None,
                    cleanup=CleanupJournal(host).state(active) if active else None)
            if command=="monitor":return dict(ok=True,observed=monitor_state(engine,config))
            if command=="scheduled-check":return ScheduleJournal(journal).check(store,access,current,deadline,lambda:monitor_state(engine,config))
            if command=="overview":return overview(store,host,access,current)
            if command=="read":return dict(ok=True,core=journal.state(operation),host=host.state(operation))
            if command=="resume-closed":
                from app.graph_access import AccessGate
                state=host.state(operation);release=AccessGate(access).read()
                if (head["active_operation"] is not None or state is None or state["phase"]!="committed"
                        or metadata(current)!=state[state["target"]] or state["seal"]!=value["seal"]
                        or any(release.get(name)!=expected for name,expected in access.fields().items())
                        or release["operation_id"]!=operation or release["release_hash"]!=state["seal"]
                        or release["boot_id"]!=state["boot_id"] or release["mode"] not in {"allowed","paused","blocked"}
                        or any(release[name]!=state[state["target"]][name] for name in ("pem_hash","fingerprint"))):
                    raise GraphError("rotation_release_invalid")
                completed=state["target"]=="new"
                if completed:
                    cleanup=CleanupJournal(host).state(operation)
                    if cleanup is None or cleanup["phase"]!="completed" or cleanup["new"]!=metadata(current):raise GraphError("rotation_release_invalid")
                host.reconcile_proof(state,monitor_state(engine,config),now)
                row=store.read(operation)
                row=store.resume_closed(operation,row["revision"],current.fingerprint,completed=completed)
                return dict(ok=True,request=row)
            if command=="publish":
                from app.graph_access import AccessGate
                state=host.state(operation);gate=AccessGate(access);release=gate.read();gate._bound(release)
                if state is None or state["phase"]!="committed" or release["operation_id"]!=operation or release["mode"] not in {"allowed","paused"} or release["release_hash"]!=state["seal"]:
                    raise GraphError("rotation_release_invalid")
                gate._material(release,current.pem,current.fingerprint)
                row=store.read(operation);cleanup=None
                if state["target"]=="old":row=store.project_host(operation,row["revision"],"failed",code="rotation_rolled_back")
                else:
                    cleanup=CleanupJournal(host).plan(operation);ScheduleJournal(journal).renewed(operation,cleanup)
                    row=project_cleanup(store,operation,cleanup)
                return dict(ok=True,request=row,cleanup=cleanup)
            if command=="cleanup":return maintain(store,host,access,operation,current,deadline)
            if command=="register":
                ScheduleJournal(journal).attempt(operation,now)
                core=journal.state(operation)
                if core is None:
                    row=store.read(operation)
                    if row["old_fingerprint"]!=current.fingerprint:raise GraphError("rotation_credential_changed")
                    with rotation_client(bound,current,deadline=deadline) as graph:
                        journal.prepare(operation,current.fingerprint,graph.read(),now)
                core=journal.state(operation);project(store,operation,core)
                if core["phase"] not in {"registered","candidate_verified","registration_rejected"}:
                    with rotation_client(bound,current,deadline=deadline) as graph:core=register(journal,operation,graph)
                row=project(store,operation,core)
                return dict(ok=True,core=core,request=row,candidate=metadata(journal.material(operation)))
            if command=="candidate-verified":
                core=journal.state(operation)
                if core is None or core["phase"] not in {"registered","candidate_verified"}:raise GraphError("rotation_transition_invalid")
                candidate_receipt(value["receipt"],access,operation,journal.material(operation),now)
                if core["phase"]=="registered":core=journal.transition(operation,"candidate_verified")
                project(store,operation,core)
                existing=host.state(operation)
                if existing is not None:project_host(store,operation,existing)
                return dict(ok=True,core=core)
            if command=="prepare":state=host.prepare(operation,current,value["images"],paused=value["paused"],drain_identity=value["drain_identity"],now=now)
            elif command=="activation-started":state=host.activation_started(operation)
            elif command=="activated":state=host.activated(operation)
            elif command=="consumers":state=host.consumers_verified(operation,value["receipts"],now)
            elif command=="proof-started":state=host.proof_started(operation,value["consumer"],epoch=value["epoch"],base_revision=value["base_revision"],now=now)
            elif command=="proof-unknown":state=host.proof_unknown(operation)
            elif command=="proof-verified":state=host.proof_verified(operation,value["receipt"],now)
            elif command=="rollback":state=host.rollback(operation,now)
            elif command=="rollback-unknown":state=host.rollback_unknown(operation)
            elif command=="recover":state=host.recover(operation,pem_hash=value["pem_hash"],quiet_evidence=value["quiet_evidence"],
                observed=monitor_state(engine,config),now=now,paused=value["paused"],drain_identity=value["drain_identity"])
            elif command=="commit":state=host.commit(operation,now=now,paused=value["paused"],drain_identity=value["drain_identity"])
            else:raise GraphError("rotation_host_request_invalid")
            project_host(store,operation,state)
            return dict(ok=True,host=state)
    finally:engine.dispose()


def main():
    logging.disable(logging.CRITICAL)
    try:
        if len(sys.argv)!=1 or os.name!="posix" or os.geteuid()!=0:raise GraphError("rotation_host_required")
        value=request(sys.stdin.buffer.read(16385));budget=OperationBudget(clock=time.monotonic)
        result=bounded_operation(execute,(value,budget.deadline-2),seconds=max(.001,budget.remaining()-2))
        if not isinstance(result,dict) or result.get("ok") is not True:raise GraphError("rotation_host_unavailable")
    except (GraphError,OSError,ValueError,TypeError,sa.exc.SQLAlchemyError):result=dict(ok=False,code="rotation_host_unavailable")
    print(json.dumps(result,separators=(",",":")))
    return 0 if result["ok"] else 1


if __name__=="__main__":raise SystemExit(main())
