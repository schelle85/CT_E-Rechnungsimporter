"""Server-only bridge from protected binding/current admission to Graph clients."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json
import os

from app.graph import GraphConfig, GraphError, protected_bytes
from app.graph_access import AccessBinding, AccessGate, AccessPermit, GraphAccessError
from app.notification_certificate import CertificateMaterial
from app.rotation_model import RotationBinding, unique_json

BINDING_FILE="/run/importer/graph-access-binding.json"
FIELDS={"schema_version","source_commit","deployment_id","instance_id","application_id","scope_key"}
_current=ContextVar("invoice_graph_access",default=None)


@dataclass(frozen=True,repr=False)
class AccessFrame:
    binding: AccessBinding
    permit: object


def binding(config,*,expected_instance=None):
    try:
        value=json.loads(protected_bytes(os.environ.get("GRAPH_ACCESS_BINDING_FILE",BINDING_FILE)),object_pairs_hook=unique_json)
        if not isinstance(value,dict) or set(value)!=FIELDS or type(value["schema_version"]) is not int or value["schema_version"]!=1:
            raise ValueError()
        rotation=RotationBinding(value["instance_id"],config.tenant_id,config.client_id,value["application_id"],config.mailbox)
        result=AccessBinding(value["source_commit"],value["deployment_id"],value["instance_id"],value["scope_key"])
        if result.scope_key!=rotation.scope or expected_instance is not None and result.instance_id!=expected_instance:
            raise ValueError()
        return result
    except (ValueError,KeyError,TypeError,GraphAccessError,GraphError):
        raise GraphError("graph_access_binding_unavailable") from None


def current():return _current.get()


@contextmanager
def api_operation(engine):
    """Current DB identity and protected Graph material, before any API child."""
    from app.errors import AccessError
    from app.notification_model import NotificationError
    import sqlalchemy as sa
    try:
        config=GraphConfig.load(os.environ.get("GRAPH_CONFIG_FILE","/run/importer/graph.json"))
        material=CertificateMaterial.load(os.environ.get("GRAPH_CREDENTIAL_FILE","/run/secrets/graph_credential"))
        with engine.connect() as c:
            instance=c.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
        with operation(config,material,expected_instance=instance) as permit:yield permit
    except (GraphError,GraphAccessError,NotificationError):
        raise AccessError(503,"Graphzugriff ist für Wartung gesperrt oder noch nicht bestätigt.") from None


@contextmanager
def notification_operation(job):
    graph_work=job.get("command") in {"automatic","plan","dispatch","send","send-automatic"} or (
        job.get("command")=="observe" and job.get("probe") is True)
    if not graph_work:
        yield None
        return
    config=GraphConfig.load(os.environ.get("GRAPH_CONFIG_FILE","/run/importer/graph.json"))
    material=CertificateMaterial.load(os.environ.get("GRAPH_CREDENTIAL_FILE","/run/secrets/graph_credential"))
    with operation(config,material) as permit:yield permit


@contextmanager
def _use(bound,permit):
    if current() is not None:raise GraphError("graph_access_context_conflict")
    token=_current.set(AccessFrame(bound,permit))
    try:yield permit
    finally:_current.reset(token)


@contextmanager
def operation(config,material,*,expected_instance=None):
    """Admission starts before child creation; nested factories reuse its lifetime."""
    bound=binding(config,expected_instance=expected_instance)
    active=current()
    try:
        if active is not None:
            if active.binding!=bound:raise GraphError("graph_access_scope_changed")
            active.permit.check(material.pem,material.fingerprint)
            yield active.permit
        else:
            with AccessGate(bound).admit(material.pem,material.fingerprint) as permit:
                with _use(bound,permit):yield permit
    except GraphAccessError as error:
        raise GraphError(error.code) from None
    except OSError:
        raise GraphError("graph_access_unavailable") from None


@contextmanager
def receive(transfer,config,material,*,expected_instance=None):
    """Only an inherited FD and metadata made by the server's parent launcher."""
    if (not isinstance(transfer,dict) or set(transfer)!={"fd","snapshot"}
            or type(transfer["fd"]) is not int or transfer["fd"]<3):
        raise GraphError("graph_access_transfer_invalid")
    fd=transfer["fd"];permit=None
    try:
        bound=binding(config,expected_instance=expected_instance)
        permit=AccessGate(bound).adopt(fd,transfer["snapshot"],material.pem,material.fingerprint)
        with _use(bound,permit):yield permit
    except GraphAccessError as error:
        raise GraphError(error.code) from None
    except OSError:
        raise GraphError("graph_access_transfer_invalid") from None
    finally:
        if permit is not None:permit.close()
        else:
            try:os.close(fd)
            except OSError:pass


def transfer():
    active=current()
    if active is None:return None
    if not isinstance(active.permit,AccessPermit):raise GraphError("graph_access_probe_child_forbidden")
    return active.permit.export()


def _restore_child(duplicate,snapshot):
    return dict(fd=duplicate.detach(),snapshot=snapshot)


class ChildAccess:
    """Pickled only by multiprocessing's spawning context, never from HTTP data."""
    def __init__(self,value):self.value=value
    def __reduce__(self):
        from multiprocessing.reduction import DupFd
        if self.value is None:raise GraphError("graph_access_transfer_invalid")
        return _restore_child,(DupFd(self.value["fd"]),self.value["snapshot"])


def proof_access(config,material):
    active=current()
    if active is None:raise GraphError("graph_access_proof_closed")
    if active.binding!=binding(config):raise GraphError("graph_access_scope_changed")
    try:active.permit.check(material.pem,material.fingerprint,proof=True)
    except GraphAccessError as error:raise GraphError(error.code) from None


@contextmanager
def host_probe(config,material,secret,*,operation_id,epoch,purpose,consumer_role,consumer_id,expected_instance=None):
    """Called solely by the fixed host probe CLI; no route/worker flag opens it."""
    bound=binding(config,expected_instance=expected_instance)
    try:
        with AccessGate(bound).host_probe(secret,operation_id=operation_id,epoch=epoch,purpose=purpose,
                consumer_role=consumer_role,consumer_id=consumer_id,pem=material.pem,fingerprint=material.fingerprint) as permit:
            with _use(bound,permit):yield permit
    except GraphAccessError as error:raise GraphError(error.code) from None
