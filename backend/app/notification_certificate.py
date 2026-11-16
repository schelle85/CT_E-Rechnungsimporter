"""Local Graph credential identity and fresh, exact-PEM proof. Never HTTPS files."""
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import uuid4
from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
from app.graph import GraphClient, GraphError, protected_bytes
from app.notification_model import CERTIFICATE_TOKEN,NotificationError,certificate_level,identity,canonical
from app.notification_schema007 import monitor, outbox
import sqlalchemy as sa

@dataclass(frozen=True,repr=False)
class CertificateMaterial:
    pem: bytes
    fingerprint: str
    not_before: int
    expires_at: int

    @classmethod
    def parse(cls, pem):
        try:
            key = serialization.load_pem_private_key(pem,password=None)
            certificates = x509.load_pem_x509_certificates(pem)
            public = lambda value:value.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
            matching = [cert for cert in certificates if public(cert.public_key()) == public(key.public_key())]
            # Azure Identity uses the first PEM certificate for the assertion thumbprint.
            if not isinstance(key,rsa.RSAPrivateKey) or len(matching) != 1 or matching[0] != certificates[0]:
                raise ValueError()
            cert = matching[0]
            return cls(pem,cert.fingerprint(hashes.SHA256()).hex(),
                int(cert.not_valid_before_utc.timestamp()),int(cert.not_valid_after_utc.timestamp()))
        except (ValueError,TypeError,AttributeError,UnsupportedAlgorithm):
            raise NotificationError("notification_certificate_invalid",503) from None

    @classmethod
    def load(cls,path):
        try:
            return cls.parse(protected_bytes(path))
        except GraphError:
            raise NotificationError("notification_certificate_unavailable",503) from None

    def metadata(self, now):
        return dict(fingerprint=self.fingerprint,not_before=self.not_before,expires_at=self.expires_at,
            valid=self.not_before <= now < self.expires_at,**certificate_level(self.expires_at,now))

@contextmanager
def certificate_client(config, material):
    from azure.identity import CertificateCredential
    from app.graph_access_runtime import operation
    credential = None
    try:
        with operation(config,material) as permit:
            credential = CertificateCredential(config.tenant_id,config.client_id,certificate_data=material.pem,
                retry_total=0,connection_timeout=5,read_timeout=10)
            with httpx.Client(timeout=httpx.Timeout(10,connect=5),trust_env=False,follow_redirects=False,
                    limits=httpx.Limits(max_connections=1)) as http:
                yield GraphClient(config,credential,http,read_attempts=1,access=permit,
                    access_material=(material.pem,material.fingerprint))
    except GraphError:
        raise
    except Exception:
        raise GraphError("graph_runtime_unavailable") from None
    finally:
        if credential is not None:
            try:
                credential.close()
            except Exception:
                raise GraphError("graph_runtime_unavailable") from None

def record_certificate(store, scope, current, *, expected_revision, fresh_proof=None):
    """One atomic observation/retirement, called only with server-created proof."""
    now = int(store.clock())
    key = identity([scope,"certificate",CERTIFICATE_TOKEN])
    with store.transaction() as c:
        store._scope(store._head(c),scope)
        row = c.execute(sa.select(monitor).where(monitor.c.monitor_key == key).with_for_update()).mappings().first()
        revision = row["revision"] if row else 0
        if type(expected_revision) is not int or expected_revision != revision:
            raise NotificationError("notification_certificate_changed")
        import json
        before = json.loads(row["payload"]) if row else dict(warning=None,proof=None,last_closed=None)
        if "fingerprint" in current:
            current = dict(current,valid=current["not_before"] <= now < current["expires_at"],
                **certificate_level(current["expires_at"],now))
        value = dict(before,current=current,checked_at=now)
        warning = value["warning"]
        if warning and "series_id" not in warning:
            warning = dict(warning,series_id=uuid4().hex)
            value["warning"] = warning
        if fresh_proof is not None:
            if (current.get("valid") is not True or set(fresh_proof) != {"fingerprint","scope_key","at"}
                    or fresh_proof["fingerprint"] != current["fingerprint"] or fresh_proof["scope_key"] != scope
                    or type(fresh_proof["at"]) is not int or not 0 <= now-fresh_proof["at"] <= 60):
                raise NotificationError("notification_certificate_proof_invalid",503)
            value["proof"] = fresh_proof
            if warning and warning["fingerprint"] != current["fingerprint"]:
                value["last_closed"] = dict(series_id=warning["series_id"],fingerprint=warning["fingerprint"],at=now,
                    successor=current["fingerprint"])
                value["warning"] = None
                c.execute(outbox.update().where(outbox.c.scope_key == scope,outbox.c.kind == "certificate",
                    outbox.c.reservations == 0,outbox.c.state == "prepared").values(
                        state="obsolete",owner=None,lease_until=0,updated_at=now))
                c.execute(outbox.update().where(outbox.c.scope_key == scope,outbox.c.kind == "certificate",
                    outbox.c.reservations == 1,outbox.c.state == "sending",outbox.c.post_started_at.is_(None)).values(
                        state="rejected",error_code="notification_certificate_series_closed",completed_at=now,
                        owner=None,lease_until=0,updated_at=now))
        if value["warning"] is None and current.get("severity") in {"orange","red"}:
            value["warning"] = dict(series_id=uuid4().hex,fingerprint=current["fingerprint"],not_before=current["not_before"],
                expires_at=current["expires_at"],started_at=now)
        values = dict(payload=canonical(value),revision=revision+1,updated_at=now)
        if row:
            c.execute(monitor.update().where(monitor.c.monitor_key == key).values(**values))
        else:
            c.execute(monitor.insert().values(monitor_key=key,scope_key=scope,kind="certificate",**values))
        return dict(value,revision=revision+1)
