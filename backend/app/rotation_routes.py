"""Existing AD/Origin/CSRF boundary; fixed SQL requests and read-only certificate metadata."""
from contextlib import contextmanager
import json
import os

from fastapi import APIRouter,Request
from pydantic import BaseModel,ConfigDict,Field
import sqlalchemy as sa

from app.errors import AccessError
from app.graph import GraphConfig,GraphError,protected_bytes
from app.graph_access_runtime import binding as access_binding,BINDING_FILE
from app.notification_certificate import CertificateMaterial
from app.notification_model import CERTIFICATE_TOKEN,NotificationError,checked_actor,graph_scope
from app.notification_state import NotificationStore
from app.rotation_model import RotationBinding,unique_json
from app.rotation_state import RotationStore
from app.rotation_status import read as read_host_status

router=APIRouter()
RECEIPT_FIELDS={"operation_id","scope_key","actor","trigger_kind","request_hash","expected_revision","old_fingerprint",
    "state","revision","error_code","created_at","updated_at"}
MESSAGES={"rotation_request_conflict":"Die Anforderung passt nicht zur ursprünglichen Bindung. Bitte die Betreuung hinzuziehen.",
    "rotation_revision_changed":"Der Stand hat sich geändert. Bitte aktualisieren und die ursprüngliche Anforderung abgleichen.",
    "rotation_already_active":"Ein Zertifikatswechsel ist bereits offen. Bitte dessen Abschluss abwarten.",
    "rotation_scope_changed":"Die Anwendungsbindung hat sich geändert. Bitte die Betreuung zum Abgleich hinzuziehen.",
    "rotation_credential_changed":"Das aktive Zertifikat hat sich geändert. Bitte den aktuellen Stand laden.",
    "rotation_signer_expired":"Das Anmeldezertifikat ist nicht gültig. Die Betreuung muss den Zugang wiederherstellen."}


@contextmanager
def boundary():
    try:yield
    except (GraphError,NotificationError) as error:
        if error.code in {"rotation_identity_invalid","rotation_page_invalid","rotation_request_invalid"}:
            raise AccessError(422,"Ungültige Zertifikatsanforderung.") from None
        raise AccessError(409 if error.code in MESSAGES else 503,MESSAGES.get(error.code,"Zertifikatsverwaltung ist noch nicht bestätigt. Bitte die Betreuung hinzuziehen.")) from None
    except (OSError,ValueError,TypeError,KeyError):
        raise AccessError(503,"Zertifikatsverwaltung ist noch nicht bestätigt. Bitte die Betreuung hinzuziehen.") from None


def context(request):
    runtime=request.app.state.runtime
    with runtime.engine.connect() as connection:instance=connection.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
    config=GraphConfig.load(os.environ.get("GRAPH_CONFIG_FILE","/run/importer/graph.json"))
    access=access_binding(config,expected_instance=instance)
    profile=json.loads(protected_bytes(os.environ.get("GRAPH_ACCESS_BINDING_FILE",BINDING_FILE)),object_pairs_hook=unique_json)
    bound=RotationBinding(instance,config.tenant_id,config.client_id,profile["application_id"],config.mailbox)
    if access.scope_key!=bound.scope or any(profile[name]!=expected for name,expected in access.fields().items()):raise GraphError("rotation_scope_changed")
    return RotationStore(runtime.engine,bound,clock=runtime.store.clock),access


def actor(request):return checked_actor("ad:"+request.state.principal.guid)
def receipt(row):return {name:row[name] for name in RECEIPT_FIELDS} if row is not None else None
def material():return CertificateMaterial.load(os.environ.get("GRAPH_CREDENTIAL_FILE","/run/secrets/graph_credential"))


class RenewalInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    operation_id:str=Field(min_length=36,max_length=36)
    scope_key:str=Field(pattern="^[0-9a-f]{64}$")
    expected_revision:int=Field(ge=0,strict=True)
    old_fingerprint:str=Field(pattern="^[0-9a-f]{64}$")


class ConfigurationInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    scope_key:str=Field(pattern="^[0-9a-f]{64}$")
    expected_revision:int=Field(ge=0,strict=True)
    enabled:bool=Field(strict=True)


def scope(store,expected):
    if store.binding.scope!=expected:raise GraphError("rotation_scope_changed")


@router.get("/api/rotation/status")
def status(request:Request):
    with boundary():
        store,access=context(request);head=store.status();now=int(store.clock());config=store.binding.config
        try:local=material().metadata(now)
        except NotificationError:local=dict(code="notification_certificate_unavailable")
        monitor=NotificationStore(store.engine,None,store.binding.instance_id).monitor_state(graph_scope(config.tenant_id,config.client_id,config.mailbox),"certificate",CERTIFICATE_TOKEN)
        proof=monitor["data"].get("proof") if monitor else None
        checked=proof["at"] if (isinstance(proof,dict) and local.get("fingerprint") is not None and proof.get("fingerprint")==local.get("fingerprint")
            and proof.get("scope_key")==graph_scope(config.tenant_id,config.client_id,config.mailbox)
            and type(proof.get("at")) is int and 0<proof["at"]<=now) else None
        active=store.read(head["active_operation"]) if head["active_operation"] else None
        host=read_host_status(access,now)
        if host["available"] and head["active_operation"] and host["operation"] and host["operation"]["operation_id"]!=head["active_operation"]:
            host=dict(host,operation=None)
        return dict(scope_key=store.binding.scope,revision=head["revision"],enabled=head["enabled"],can_edit=request.state.principal.role=="admin",
            local=local,last_successful_check_at=checked,active=receipt(active),host=host,checked_at=now,
            schedule=dict(timezone="Europe/Berlin",daily_time="03:35",renew_before_days=30,overlap_days=7))


@router.get("/api/rotation/history")
def history(request:Request,page:int=1):
    with boundary():
        store,_=context(request);value=store.history(page);return dict(value,items=[receipt(row) for row in value["items"]])


@router.get("/api/rotation/request")
def request_status(request:Request,operation_id:str,scope_key:str,expected_revision:int,old_fingerprint:str):
    with boundary():
        store,_=context(request);scope(store,scope_key)
        return dict(ok=True,persisted=True,receipt=receipt(store.request_receipt(operation_id,actor(request),expected_revision,old_fingerprint)))


@router.post("/api/rotation/request")
def renew(candidate:RenewalInput,request:Request):
    with boundary():
        store,_=context(request);scope(store,candidate.scope_key)
        def validate_new():
            current=material()
            if current.fingerprint!=candidate.old_fingerprint:raise GraphError("rotation_credential_changed")
            if not current.not_before<=store.clock()<current.expires_at:raise GraphError("rotation_signer_expired")
        row=store.request(candidate.operation_id,actor(request),candidate.expected_revision,candidate.old_fingerprint,validate_new=validate_new)
        return dict(ok=True,persisted=True,receipt=receipt(row))


@router.put("/api/rotation/config")
def configure(candidate:ConfigurationInput,request:Request):
    with boundary():
        store,_=context(request);scope(store,candidate.scope_key)
        head=store.configure(candidate.expected_revision,candidate.enabled,actor(request))
        return dict(scope_key=store.binding.scope,revision=head["revision"],enabled=head["enabled"],can_edit=True)
