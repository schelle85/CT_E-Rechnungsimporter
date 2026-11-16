"""AP12 fixed application identity and local candidate/PoP; no runtime entrypoint."""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from app.graph import GraphConfig, GraphError
from app.notification_certificate import CertificateMaterial
from app.notification_model import canonical, identity

POP_AUDIENCE = "00000002-0000-0000-c000-000000000000"
PHASES = frozenset({"requested", "prepared", "registration_started", "registration_unknown",
    "registration_rejected", "registered", "candidate_verified", "adoption_prepared", "adopting",
    "rollback_unknown", "adopted", "overlap", "cleanup_started", "cleanup_unknown", "completed", "failed"})


def uuid(value):
    try:
        parsed = UUID(value)
        if not parsed.int or str(parsed) != value:
            raise ValueError()
        return value
    except (ValueError, TypeError, AttributeError):
        raise GraphError("rotation_identity_invalid") from None


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise GraphError("rotation_identity_invalid")
    return value


@dataclass(frozen=True, repr=False)
class RotationBinding:
    instance_id: str
    tenant_id: str
    client_id: str
    application_id: str
    mailbox: str

    def __post_init__(self):
        for value in (self.instance_id, self.tenant_id, self.client_id, self.application_id):
            uuid(value)
        GraphConfig(self.tenant_id, self.client_id, self.mailbox)

    @property
    def config(self):
        return GraphConfig(self.tenant_id, self.client_id, self.mailbox)

    @property
    def scope(self):
        return identity([self.instance_id, self.tenant_id, self.client_id, self.application_id, self.mailbox.lower()])


def certificate_der(material):
    return x509.load_pem_x509_certificates(material.pem)[0].public_bytes(serialization.Encoding.DER)


def records_hash(records):
    if not isinstance(records, list) or len(records) > 64:
        raise GraphError("rotation_key_metadata_invalid")
    keys = [uuid(item["key_id"]) for item in records]
    if len(set(keys)) != len(keys):
        raise GraphError("rotation_key_metadata_invalid")
    return identity(sorted(records, key=lambda item: item["key_id"]))


def checked_candidate(material, now):
    key = serialization.load_pem_private_key(material.pem, password=None)
    if (type(now) is not int or not material.not_before <= now < material.expires_at
            or material.expires_at - material.not_before != 180 * 86400
            or not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 3072):
        raise GraphError("rotation_candidate_invalid")
    return material


def unique_json(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("duplicate JSON key")
        value[name] = item
    return value


def candidate(now):
    """Actual X.509 lifetime is 180 days including the five-minute backdate."""
    if type(now) is not int or now < 0:
        raise GraphError("rotation_time_invalid")
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "invoice-importer-graph")])
    before = now - 300
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.fromtimestamp(before, timezone.utc))
        .not_valid_after(datetime.fromtimestamp(before + 180 * 86400, timezone.utc)).sign(key, hashes.SHA256()))
    return CertificateMaterial.parse(cert.public_bytes(serialization.Encoding.PEM) + key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))


def proof(binding, material, now):
    if type(now) is not int or not material.not_before <= now < material.expires_at:
        raise GraphError("rotation_signer_expired")
    key = serialization.load_pem_private_key(material.pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise GraphError("rotation_signer_invalid")
    cert = x509.load_pem_x509_certificates(material.pem)[0]
    b64 = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=")
    header = dict(alg="RS256", typ="JWT", x5t=b64(cert.fingerprint(hashes.SHA1())).decode("ascii"))
    claims = dict(aud=POP_AUDIENCE, iss=binding.application_id, nbf=now, exp=now + 600)
    body = b".".join(b64(canonical(value).encode("ascii")) for value in (header, claims))
    return (body + b"." + b64(key.sign(body, padding.PKCS1v15(), hashes.SHA256()))).decode("ascii")


def key_record(value):
    """Public selected-GET metadata; foreign types are preserved but never adopted."""
    try:
        if not isinstance(value, dict):
            raise ValueError()
        key_id = uuid(value["keyId"])
        result = dict(key_id=key_id, type=value["type"], usage=value["usage"], fingerprint=None,
            not_before=None, expires_at=None)
        if result["type"] == "AsymmetricX509Cert" and result["usage"] == "Verify":
            raw = base64.b64decode(value["key"], validate=True)
            if not 1 <= len(raw) <= 65536:
                raise ValueError()
            cert = x509.load_der_x509_certificate(raw)
            result.update(fingerprint=hashlib.sha256(raw).hexdigest(),
                not_before=int(cert.not_valid_before_utc.timestamp()), expires_at=int(cert.not_valid_after_utc.timestamp()))
            for source, target in (("startDateTime", "not_before"), ("endDateTime", "expires_at")):
                parsed = datetime.fromisoformat(value[source].replace("Z", "+00:00"))
                if parsed.tzinfo is None or parsed.timestamp() != result[target]:
                    raise ValueError()
        elif not all(isinstance(result[name], str) and len(result[name]) <= 64 for name in ("type", "usage")):
            raise ValueError()
        return result
    except (ValueError, TypeError, KeyError, AttributeError):
        raise GraphError("rotation_key_metadata_invalid") from None
