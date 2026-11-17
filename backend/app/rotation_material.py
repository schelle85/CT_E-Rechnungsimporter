"""Public retirement attestations keep old host receipts readable without old private keys."""
import base64
import hashlib
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from app.graph import GraphError
from app.notification_certificate import CertificateMaterial
from app.notification_model import identity
from app.rotation_model import uuid


def material_metadata(material):
    return dict(fingerprint=material.fingerprint,pem_hash=hashlib.sha256(material.pem).hexdigest(),expires_at=material.expires_at)


def filename(value):
    match=re.fullmatch(r"([0-9a-f-]{36})(?:\.(?:old|probe))?\.pem",value)
    if match is None:raise GraphError("rotation_material_name_invalid")
    uuid(match[1]);return value


def retirement_receipt(root,name,material,cleanup):
    filename(name)
    certificate=x509.load_pem_x509_certificates(material.pem)[0]
    result=dict(version=1,file=name,scope_key=root.binding.scope,cleanup_operation=cleanup["operation_id"],
        key_id=cleanup["owned"]["key_id"],material=material_metadata(material),
        certificate_der=base64.b64encode(certificate.public_bytes(serialization.Encoding.DER)).decode("ascii"))
    result["seal"]=identity(result)
    return result


def retired_metadata(root,name,expected):
    filename(name);value=root._read(name+".retired.json")
    try:
        if (not isinstance(value,dict) or set(value)!={"version","file","scope_key","cleanup_operation","key_id","material","certificate_der","seal"}
                or type(value["version"]) is not int or value["version"]!=1 or value["file"]!=name
                or value["scope_key"]!=root.binding.scope or value["material"]!=expected
                or value["seal"]!=identity({key:item for key,item in value.items() if key!="seal"})):raise ValueError()
        uuid(value["key_id"]);uuid(value["cleanup_operation"])
        certificate=x509.load_der_x509_certificate(base64.b64decode(value["certificate_der"],validate=True))
        if (certificate.fingerprint(hashes.SHA256()).hex()!=expected["fingerprint"]
                or int(certificate.not_valid_after_utc.timestamp())!=expected["expires_at"]):raise ValueError()
        cleanup=root._read(value["cleanup_operation"]+".cleanup.json")
        owned=root.inventory()["keys"].get(value["key_id"])
        if (not isinstance(cleanup,dict) or cleanup.get("scope_key")!=root.binding.scope
                or cleanup.get("operation_id")!=value["cleanup_operation"] or cleanup.get("phase") not in {"local_pending","completed"}
                or cleanup.get("old")!=expected or not isinstance(cleanup.get("owned"),dict)
                or cleanup["owned"].get("key_id")!=value["key_id"] or owned!={key:item for key,item in cleanup["owned"].items() if key!="key_id"}
                or dict(name=name,receipt_hash=identity(value)) not in cleanup.get("files",[])):raise ValueError()
        return expected
    except (KeyError,ValueError,TypeError,GraphError):raise GraphError("rotation_retired_material_invalid") from None


def check_material(root,name,expected):
    from app.rotation_journal import protected_bytes
    path=root.directory/filename(name)
    if path.exists() or path.is_symlink():
        if material_metadata(CertificateMaterial.parse(protected_bytes(path)))!=expected:
            raise GraphError("rotation_material_changed")
        return expected
    return retired_metadata(root,name,expected)
