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
from pydantic import BaseModel,ConfigDict,Field
from starlette.concurrency import run_in_threadpool
from app.notification_model import checked_actor,identity
from app.notification_process import execute_notification
from app.notification_runtime import load_notification_cipher
from app.notification_schema007 import outbox
from app.operations_status import read_status

router=APIRouter()

def graph_config():
    try:return GraphConfig.load(os.environ.get("GRAPH_CONFIG_FILE","/run/importer/graph.json"))
    except GraphError:raise AccessError(503,"Graph-Konfiguration nicht verfügbar.") from None

def notification_store(request,*,cipher=None):
    runtime=request.app.state.runtime
    with runtime.engine.connect() as c:
        instance=c.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
    return NotificationStore(runtime.engine,cipher,instance,clock=runtime.store.clock)

def configured_store(request):
    config=graph_config()
    return notification_store(request,cipher=load_notification_cipher()),graph_scope(config.tenant_id,config.client_id,config.mailbox)

def actor(request):return checked_actor("ad:"+request.state.principal.guid)

class NotificationSettingsInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    expected_version:int=Field(ge=0,strict=True)
    settings:dict

class NotificationTestInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    request_id:str=Field(min_length=36,max_length=36)
    expected_version:int=Field(ge=0,strict=True)

@router.get("/api/notifications/config")
def configuration(request:Request):
    store,scope=configured_store(request)
    value=store.configuration()
    if value["scope_key"] not in {None,scope}:raise NotificationError("notification_scope_changed")
    status=read_status(store.instance,now=int(store.clock()))
    return dict(value,scope_key=scope,can_edit=request.state.principal.role=="admin",
        automatic_schedule_active=status["automatic_schedule_active"],automatic_schedule_state=status["automatic_schedule_state"])

@router.put("/api/notifications/config")
def save_configuration(candidate:NotificationSettingsInput,request:Request):
    store,scope=configured_store(request)
    value=store.save_settings(candidate.expected_version,candidate.settings,scope,actor(request))
    status=read_status(store.instance,now=int(store.clock()))
    return dict(value,can_edit=True,automatic_schedule_active=status["automatic_schedule_active"],
        automatic_schedule_state=status["automatic_schedule_state"])

@router.get("/api/notifications/history")
def history(request:Request,page:int=1):
    config=graph_config()
    return notification_store(request).history(graph_scope(config.tenant_id,config.client_id,config.mailbox),page=page)

@router.get("/api/notifications/test/status")
def test_status(request:Request,request_id:str,expected_version:int):
    config=graph_config();scope=graph_scope(config.tenant_id,config.client_id,config.mailbox)
    return dict(ok=True,persisted=True,receipt=notification_store(request).test_receipt(request_id,expected_version,scope,actor(request)))

def prepare_test(request,candidate,*,preview=False):
    budget=request.state.notification_budget
    if budget.remaining() <= 10:raise NotificationError("notification_deadline",504)
    store,scope=configured_store(request)
    if budget.remaining() <= 10:raise NotificationError("notification_deadline",504)
    receipt=store.request_test(candidate.request_id,candidate.expected_version,scope,actor(request),origin=request.app.state.runtime.origin)
    result=dict(ok=True,persisted=True,receipt=receipt)
    if preview:
        with store.engine.connect() as c:
            row=c.execute(sa.select(outbox).where(outbox.c.slot_key==receipt["slot_key"])).mappings().one()
        payload=store._decrypt(row["payload_cipher"])
        if identity(payload) != row["payload_hash"]:raise NotificationError("notification_payload_changed",503)
        result["payload"]=payload
    return result

@router.post("/api/notifications/test/preview")
async def test_preview(candidate:NotificationTestInput,request:Request):
    return await run_in_threadpool(prepare_test,request,candidate,preview=True)

@router.post("/api/notifications/test")
async def test_send(candidate:NotificationTestInput,request:Request):
    from app.graph_access_runtime import api_operation
    with api_operation(request.app.state.runtime.engine):
        return await _test_send(candidate,request)


async def _test_send(candidate,request):
    prepared=await run_in_threadpool(prepare_test,request,candidate)
    receipt=prepared["receipt"]
    if receipt["state"] != "prepared" or receipt["reservations"]:
        return prepared
    # Only this persisted AD-bound test slot; never plan/dispatch or a new budget.
    result=await execute_notification(dict(command="send",slot_key=receipt["slot_key"]),budget=request.state.notification_budget)
    receipts=result.get("receipts")
    if result.get("persisted") is True and isinstance(receipts,list) and len(receipts)==1 and receipts[0]["slot_key"]==receipt["slot_key"]:
        return dict(ok=result.get("ok") is True,persisted=True,receipt=receipts[0])
    return dict(ok=False,persisted=False,code="notification_status_unavailable",request_id=candidate.request_id)

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
