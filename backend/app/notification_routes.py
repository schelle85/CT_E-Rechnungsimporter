"""AD-protected notification/report projections; no send on a read request."""
import os
import sqlalchemy as sa
from fastapi import APIRouter,Request
from typing import Literal
from app.errors import AccessError
from app.graph import GraphConfig,GraphError
from app.notification_certificate import CertificateMaterial
from app.notification_model import CERTIFICATE_TOKEN,NotificationError,certificate_level,graph_scope
from app.notification_queries import report_cohort,report_range
from app.notification_state import NotificationStore
from app.storage_plan import digest

router=APIRouter()

def graph_config():
    try:return GraphConfig.load(os.environ.get("GRAPH_CONFIG_FILE","/run/importer/graph.json"))
    except GraphError:raise AccessError(503,"Graph-Konfiguration nicht verfügbar.") from None

def notification_store(request,*,cipher=None):
    runtime=request.app.state.runtime
    with runtime.engine.connect() as c:
        instance=c.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
    return NotificationStore(runtime.engine,cipher,instance,clock=runtime.store.clock)

@router.get("/api/admin/reports")
def reports(request:Request,period:Literal["daily","weekly","range"]="daily",anchor:str|None=None,
        from_date:str|None=None,to_date:str|None=None):
    config=graph_config();runtime=request.app.state.runtime
    now=int(runtime.store.clock())
    slot=report_range(period,anchor,from_date,to_date,now=now)
    return dict(report_cohort(runtime.engine,slot,digest([config.mailbox.lower()]),as_of=now),
        period=period,timezone="Europe/Berlin",synthetic=False)

@router.get("/api/notifications/certificate")
def certificate_status(request:Request):
    config=graph_config();scope=graph_scope(config.tenant_id,config.client_id,config.mailbox)
    store=notification_store(request);now=int(store.clock())
    try:
        value=CertificateMaterial.load(os.environ.get("GRAPH_CREDENTIAL_FILE","/run/secrets/graph_credential"))
        local=value.metadata(now)
    except NotificationError:
        local=dict(code="notification_certificate_unavailable")
    observed=store.monitor_state(scope,"certificate",CERTIFICATE_TOKEN)
    data=observed["data"] if observed else {}
    warning=data.get("warning")
    warning=dict(warning,**certificate_level(warning["expires_at"],now)) if warning else None
    proof=data.get("proof")
    return dict(checked_at=now,local=local,warning=warning,
        proof={key:proof[key] for key in ("fingerprint","at")} if proof else None,
        monitor_checked_at=data.get("checked_at"))
