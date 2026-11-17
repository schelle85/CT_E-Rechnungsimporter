"""Fixed Root maintenance of a confirmed successor under normal Graph admission."""
import time

from app.graph import GraphError
from app.graph_access_runtime import operation as graph_operation
from app.notification_certificate import certificate_client
from app.notification_model import graph_scope
from app.rotation_cleanup import CleanupJournal
from app.rotation_graph import rotation_client


def project_cleanup(store,operation,value):
    row=store.read(operation)
    if row["state"]=="adopted":row=store.project_host(operation,row["revision"],"overlap")
    if value["phase"]=="planned":return row
    if row["state"]=="overlap":row=store.project_host(operation,row["revision"],"cleanup_started")
    state="completed" if value["phase"]=="completed" else "cleanup_unknown" if value["phase"]=="removal_unknown" else "cleanup_started"
    return store.project_host(operation,row["revision"],state,code=value["error_code"])


def maintain(store,host,access,operation,current,deadline):
    from app.graph_access import AccessGate
    cleanup=CleanupJournal(host);value=cleanup.plan(operation);state=host.state(operation)
    gate=AccessGate(access);release=gate.read();gate._bound(release)
    if (release["operation_id"]!=operation or release["release_hash"]!=state["seal"]
            or any(release[name]!=expected for name,expected in access.fields().items())):
        raise GraphError("rotation_release_invalid")
    gate._material(release,current.pem,current.fingerprint)
    if release["mode"]!="allowed":return dict(ok=True,cleanup=value,request=store.read(operation),deferred="graph_paused")
    now=int(time.time())
    if value["phase"]=="completed" or value["phase"]=="planned" and now<value["not_before"]:
        return dict(ok=True,cleanup=value,request=project_cleanup(store,operation,value))
    bound=host.root.binding
    # One absolute working budget keeps the fresh GET within the removal proof's
    # 60-second limit. The existing bounded parent owns close/reap deadlines.
    until=min(deadline,time.monotonic()+40)
    with graph_operation(bound.config,current,expected_instance=bound.instance_id) as permit:
        with certificate_client(bound.config,current) as client:
            client.deadline=until;client.probe()
            proof=dict(fingerprint=current.fingerprint,scope_key=graph_scope(bound.tenant_id,bound.client_id,bound.mailbox),at=int(time.time()))
        permit.check(current.pem,current.fingerprint)
        with rotation_client(bound,current,deadline=until,access=permit) as graph:
            value=cleanup.remove(operation,graph,current,proof,int(time.time()))
        project_cleanup(store,operation,value)
        permit.check(current.pem,current.fingerprint)
        cleanup.current(operation,graph,current,proof,int(time.time()))
        if value["phase"] in {"remote_absent","local_pending","unmanaged_retained"}:
            value=cleanup.finish_local(operation,current)
        return dict(ok=True,cleanup=value,request=project_cleanup(store,operation,value))
