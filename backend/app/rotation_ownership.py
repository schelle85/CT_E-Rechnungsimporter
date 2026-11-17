"""Explicit Root attestation of the currently proven certificate; selected GET only."""
import time

from app.graph import GraphError
from app.graph_access_runtime import operation as graph_operation
from app.notification_model import identity
from app.rotation_adoption import metadata
from app.rotation_cleanup import CleanupJournal
from app.rotation_graph import rotation_client
from app.rotation_model import sha,uuid


def current_release(store,host,access,current,gate):
    release=gate.read();gate._bound(release);gate._material(release,current.pem,current.fingerprint)
    if release["mode"]!="allowed":raise GraphError("rotation_attestation_paused")
    if not current.not_before<=int(time.time())<current.expires_at:raise GraphError("rotation_signer_expired")
    operation=uuid(release["operation_id"]);state=host.state(operation)
    if state is not None:
        if (state["phase"]!="committed" or state["seal"]!=release["release_hash"] or state["boot_id"]!=release["boot_id"]
                or state[state["target"]]!=metadata(current)):raise GraphError("rotation_attestation_unconfirmed")
        row=store.read(operation)
        if row["state"]!=("completed" if state["target"]=="new" else "failed"):raise GraphError("rotation_attestation_unconfirmed")
        if state["target"]=="new":
            cleanup=CleanupJournal(host).state(operation)
            if cleanup is None or cleanup["phase"]!="completed":raise GraphError("rotation_attestation_unconfirmed")
    else:
        record=host.root._read(".bootstrap.json")
        fields={"operation_id",*access.fields(),"current","paused","proof_intent","revision","seal","old_api","receipts","proof","observed","drain_identity"}
        if (not isinstance(record,dict) or set(record)!=fields or record["operation_id"]!=operation or record["current"]!=metadata(current)
                or any(record[name]!=value for name,value in access.fields().items()) or record["paused"] is not False
                or record["seal"]!=release["release_hash"] or record["seal"]!=identity({key:value for key,value in record.items() if key!="seal"})
                or set(record["receipts"])!={"api","processing","notifications"}):raise GraphError("rotation_attestation_unconfirmed")
        proof=record["proof"]["probe"]
        if (proof["fingerprint"]!=current.fingerprint or proof["pem_hash"]!=metadata(current)["pem_hash"]
                or proof["operation_id"]!=operation or proof["purpose"]!="finalize-proof" or proof["proof_revision"] is None
                or proof["receipt_hash"]!=identity({key:value for key,value in proof.items() if key!="receipt_hash"})):
            raise GraphError("rotation_attestation_unconfirmed")
    return release


def attest(store,host,access,current,*,key_id,fingerprint,evidence,deadline):
    key_id=uuid(key_id);sha(fingerprint);sha(evidence)
    if current.fingerprint!=fingerprint:raise GraphError("rotation_credential_changed")
    before=store.status()
    if before["active_operation"] is not None:raise GraphError("rotation_already_active")
    from app.graph_access import AccessGate
    gate=AccessGate(access);release=current_release(store,host,access,current,gate)
    bound=host.root.binding
    with graph_operation(bound.config,current,expected_instance=bound.instance_id) as permit:
        with rotation_client(bound,current,deadline=min(deadline,time.monotonic()+40),access=permit) as graph:
            if graph.binding!=bound or graph.signer.pem!=current.pem:raise GraphError("rotation_attestation_unconfirmed")
            records=graph.read()
        matches=[row for row in records if row["key_id"]==key_id or row["fingerprint"]==fingerprint]
        if (len(matches)!=1 or matches[0]["key_id"]!=key_id or matches[0]["fingerprint"]!=fingerprint
                or matches[0]["type"]!="AsymmetricX509Cert" or matches[0]["usage"]!="Verify"
                or matches[0]["not_before"]!=current.not_before or matches[0]["expires_at"]!=current.expires_at):
            raise GraphError("rotation_attestation_key_mismatch")
        permit.check(current.pem,current.fingerprint)
        if current_release(store,host,access,current,gate)!=release:raise GraphError("rotation_attestation_changed")
        # Keep the SQL head locked through the local attestation. API requests cannot
        # appear between the final no-active-request check and durable inventory save.
        with store.transaction() as connection:
            if store._head(connection)!=before:raise GraphError("rotation_attestation_changed")
            inventory=host.root.inventory();owned=inventory["keys"].get(key_id)
            if any(key!=key_id and item["fingerprint"]==fingerprint for key,item in inventory["keys"].items()):
                raise GraphError("rotation_inventory_conflict")
            if owned is not None:
                if owned["fingerprint"]!=fingerprint:raise GraphError("rotation_inventory_conflict")
            else:
                host.root.adopt_existing(release["operation_id"],matches[0],evidence=evidence)
            item=host.root.inventory()["keys"][key_id]
        return dict(ok=True,already_managed=owned is not None,key_id=key_id,**item)
