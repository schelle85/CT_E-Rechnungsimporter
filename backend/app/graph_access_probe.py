"""Fixed host-invoked probe. No HTTP route, normal worker flag or path argument."""
from contextlib import ExitStack
import hashlib
import json
import logging
import os
import re
import sys
import time

import sqlalchemy as sa
from app.database import make_engine
from app.graph import GraphConfig,GraphError
from app.graph_deadline import bounded_operation
from app.graph_access import PURPOSES,ROLES,_uuid
from app import graph_access_runtime as runtime
from app.notification_certificate import CertificateMaterial,certificate_client
from app.notification_model import CERTIFICATE_TOKEN,NotificationError,OperationBudget,canonical,graph_scope
from app.notification_service import NotificationService
from app.notification_state import NotificationStore
from app.rotation_model import unique_json

FIELDS={"schema_version","operation_id","epoch","purpose","consumer_role","consumer_id","secret"}


def request(raw):
    try:
        if not isinstance(raw,bytes) or len(raw)>4096:raise ValueError()
        value=json.loads(raw,object_pairs_hook=unique_json)
        if (not isinstance(value,dict) or set(value)!=FIELDS or type(value["schema_version"]) is not int
                or value["schema_version"]!=1 or not _uuid(value["operation_id"])
                or type(value["epoch"]) is not int or not 1<=value["epoch"]<2**63
                or value["purpose"] not in PURPOSES or value["consumer_role"] not in ROLES
                or any(not isinstance(value[name],str) or not re.fullmatch("[0-9a-f]{64}",value[name])
                    for name in ("consumer_id","secret"))):raise ValueError()
        if (value["purpose"]=="candidate-read" and value["consumer_role"]!="candidate"
                or value["purpose"]=="finalize-proof" and value["consumer_role"]!="notifications"):raise ValueError()
        return {name:item for name,item in value.items() if name!="schema_version"}
    except (ValueError,TypeError,KeyError):raise GraphError("graph_probe_request_invalid") from None


def run(value):
    budget=OperationBudget(clock=time.monotonic,seconds=40)
    # Existing bounded child owns the full workflow, reserving its two reap seconds.
    # No outer ITIMER_REAL: GraphClient retains its own remaining transport timer.
    deadline=budget.deadline-2
    seconds=deadline-time.monotonic()
    if seconds<=0:raise GraphError("graph_probe_unavailable")
    result=bounded_operation(_probe_child,(value,deadline),seconds=seconds)
    if not isinstance(result,dict) or result.get("ok") is not True:raise GraphError("graph_probe_unavailable")
    return result


def _probe_child(value,deadline):
    budget=OperationBudget(clock=time.monotonic,seconds=40)
    budget.deadline=deadline  # Original parent's absolute time, never renewed by spawn/preflight.
    return _run(value,budget)


def _run(value,budget):
    config=GraphConfig.load("/run/importer/graph.json")
    scope=graph_scope(config.tenant_id,config.client_id,config.mailbox)
    with ExitStack() as cleanup:
        store=instance=None;revision=0
        if value["purpose"]=="finalize-proof":
            engine=make_engine();cleanup.callback(engine.dispose)
            with engine.connect() as c:
                instance=c.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
            store=NotificationStore(engine,None,instance)
            observed=store.monitor_state(scope,"certificate",CERTIFICATE_TOKEN)
            revision=observed["revision"] if observed else 0
        # Capture the production monitor revision before reading candidate bytes.
        material=CertificateMaterial.load("/run/secrets/graph_credential")
        if material.metadata(int(time.time()))["valid"] is not True:raise GraphError("graph_probe_certificate_invalid")
        secret=bytes.fromhex(value["secret"])
        binding=runtime.binding(config,expected_instance=instance)
        with runtime.host_probe(config,material,secret,expected_instance=instance,
                **{name:value[name] for name in ("operation_id","epoch","purpose","consumer_role","consumer_id")}) as permit:
            with certificate_client(config,material) as client:
                client.deadline=budget.deadline
                client.probe()
                proof=None
                if store is not None:
                    proof=NotificationService(store,config,material,observation_revision=revision)._proof()
            permit.check(material.pem,material.fingerprint,proof=store is not None)
            result=dict(ok=True,code="graph_probe_verified",**binding.fields(),
                operation_id=value["operation_id"],epoch=value["epoch"],purpose=value["purpose"],
                consumer_role=value["consumer_role"],consumer_id=value["consumer_id"],
                pem_hash=hashlib.sha256(material.pem).hexdigest(),fingerprint=material.fingerprint,
                at=int(time.time()),proof_revision=proof["revision"] if proof else None,
                proof_at=proof["proof"]["at"] if proof else None)
            result["receipt_hash"]=hashlib.sha256(canonical(result).encode()).hexdigest()
            return result


def main():
    logging.disable(logging.CRITICAL)
    try:
        if len(sys.argv)!=1 or os.name!="posix" or os.geteuid()!=10001 or os.getegid()!=10001:
            raise GraphError("graph_probe_request_invalid")
        value=run(request(sys.stdin.buffer.read(4097)))
    except (GraphError,NotificationError,sa.exc.SQLAlchemyError,OSError,ValueError,TypeError):
        value=dict(ok=False,code="graph_probe_unavailable")
    print(json.dumps(value,separators=(",",":")))
    return 0 if value["ok"] else 1


if __name__=="__main__":raise SystemExit(main())
