"""AP12 local Graph admission and host-only read permits. Standard library only.

No route, runtime installation, scheduler or privileged command lives here.
"""
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import time
from uuid import UUID

DIRECTORY = "/run/importer/operations/graph-access"
FIELDS = {"schema_version", "source_commit", "deployment_id", "instance_id", "scope_key",
    "boot_id", "epoch", "admission_epoch", "operation_id", "mode", "pem_hash", "fingerprint", "release_hash", "grants"}
BINDING_FIELDS = ("source_commit", "deployment_id", "instance_id", "scope_key")
ADMISSION_FIELDS = (*BINDING_FIELDS, "boot_id", "admission_epoch", "pem_hash", "fingerprint")
GRANT_FIELDS = {"secret_hash", "purpose", "consumer_role", "consumer_id", "issued_at", "expires_at"}
PURPOSES = {"candidate-read", "consumer-read", "finalize-proof"}
ROLES = {"candidate", "api", "processing", "notifications"}


class GraphAccessError(Exception):
    def __init__(self, code="graph_access_closed"):
        self.code = code
        super().__init__(code)


def _hex(value, length=64):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{"+str(length)+"}", value) is not None


def _uuid(value):
    try:
        parsed=UUID(value)
        return parsed.int != 0 and str(parsed)==value
    except (ValueError, TypeError, AttributeError):
        return False


def _unique(pairs):
    value={}
    for name,item in pairs:
        if name in value:raise ValueError()
        value[name]=item
    return value


def boot_id():
    try:
        value=Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        if not _uuid(value):raise ValueError()
        return value
    except (OSError,ValueError):
        raise GraphAccessError("graph_access_boot_unavailable") from None


@dataclass(frozen=True)
class AccessBinding:
    source_commit: str
    deployment_id: str
    instance_id: str
    scope_key: str

    def __post_init__(self):
        if (not _hex(self.source_commit,40) or not _uuid(self.deployment_id)
                or not _uuid(self.instance_id) or not _hex(self.scope_key)):
            raise GraphAccessError("graph_access_binding_invalid")

    def fields(self):
        return {name:getattr(self,name) for name in BINDING_FIELDS}


def validate(value):
    try:
        if not isinstance(value,dict) or set(value)!=FIELDS:raise ValueError()
        AccessBinding(**{name:value[name] for name in BINDING_FIELDS})
        if (type(value["schema_version"]) is not int or value["schema_version"]!=1
                or not _uuid(value["boot_id"]) or not _uuid(value["operation_id"])
                or type(value["epoch"]) is not int or not 1<=value["epoch"]<2**63
                or type(value["admission_epoch"]) is not int or not 0<=value["admission_epoch"]<=value["epoch"]
                or value["mode"] not in {"allowed","blocked","paused"}
                or any(not _hex(value[name]) for name in ("pem_hash","fingerprint"))
                or value["release_hash"] is not None and not _hex(value["release_hash"])
                or not isinstance(value["grants"],list) or len(value["grants"])>4):raise ValueError()
        if value["mode"]=="allowed" and (value["admission_epoch"]!=value["epoch"] or value["release_hash"] is None):
            raise ValueError()
        if value["mode"]!="blocked" and value["grants"]:raise ValueError()
        hashes=[]
        for grant in value["grants"]:
            if (not isinstance(grant,dict) or set(grant)!=GRANT_FIELDS or not _hex(grant["secret_hash"])
                    or grant["purpose"] not in PURPOSES or grant["consumer_role"] not in ROLES
                    or not _hex(grant["consumer_id"])
                    or any(type(grant[name]) is not int for name in ("issued_at","expires_at"))
                    or not 0<grant["expires_at"]-grant["issued_at"]<=60
                    or grant["purpose"]=="candidate-read" and grant["consumer_role"]!="candidate"
                    or grant["purpose"]=="finalize-proof" and grant["consumer_role"]!="notifications"):
                raise ValueError()
            hashes.append(grant["secret_hash"])
        if len(set(hashes))!=len(hashes):raise ValueError()
        return value
    except (ValueError,KeyError,TypeError,GraphAccessError):
        raise GraphAccessError("graph_access_record_invalid") from None


def directory_policy(path):
    if os.name!="posix" or not path.is_absolute():raise GraphAccessError("graph_access_platform")
    for part in (*reversed(path.parents),path):
        info=part.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:
            raise GraphAccessError("graph_access_directory_invalid")
    info=path.stat()
    if info.st_gid!=10001 or stat.S_IMODE(info.st_mode)!=0o750:
        raise GraphAccessError("graph_access_directory_invalid")


def file_policy(info, *, lock=False):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_gid!=10001
            or stat.S_IMODE(info.st_mode)!=0o440 or info.st_nlink!=1
            or (info.st_size!=0 if lock else not 1<=info.st_size<=16384)):
        raise GraphAccessError("graph_access_file_invalid")


def flock(fd, *, exclusive=False):
    import fcntl
    try:fcntl.flock(fd,(fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)|fcntl.LOCK_NB)
    except BlockingIOError:raise GraphAccessError("graph_access_busy") from None


class AccessGate:
    def __init__(self,binding,*,directory=DIRECTORY):
        self.binding,self.directory=binding,Path(directory)

    def read(self):
        try:
            directory_policy(self.directory)
            fd=os.open(self.directory/"graph-access.json",os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,"rb") as source:
                file_policy(os.fstat(source.fileno()))
                raw=source.read(16385)
            if len(raw)>16384:raise ValueError()
            return validate(json.loads(raw,object_pairs_hook=_unique))
        except GraphAccessError:raise
        except (OSError,ValueError,AttributeError):
            raise GraphAccessError("graph_access_unavailable") from None

    def _lock(self):
        fd=None
        try:
            directory_policy(self.directory)
            fd=os.open(self.directory/"graph-access.lock",os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            file_policy(os.fstat(fd),lock=True)
            return fd
        except (OSError,AttributeError,GraphAccessError):
            if fd is not None:os.close(fd)
            raise GraphAccessError("graph_access_lock_unavailable") from None

    def _bound(self,value):
        if any(value[name]!=expected for name,expected in self.binding.fields().items()) or value["boot_id"]!=boot_id():
            raise GraphAccessError("graph_access_binding_changed")

    def _identity(self,fd):
        reference=self._lock()
        try:
            actual,expected=os.fstat(fd),os.fstat(reference)
            file_policy(actual,lock=True)
            if (actual.st_dev,actual.st_ino)!=(expected.st_dev,expected.st_ino):
                raise GraphAccessError("graph_access_lock_changed")
        finally:os.close(reference)

    @staticmethod
    def _material(value,pem,fingerprint):
        if (not isinstance(pem,bytes) or not 1<=len(pem)<=65536 or not _hex(fingerprint)
                or hashlib.sha256(pem).hexdigest()!=value["pem_hash"] or fingerprint!=value["fingerprint"]):
            raise GraphAccessError("graph_access_credential_changed")

    def admit(self,pem,fingerprint):
        fd=self._lock()
        try:
            flock(fd)
            value=self.read();self._bound(value);self._material(value,pem,fingerprint)
            if value["mode"]!="allowed":raise GraphAccessError()
            snapshot={name:value[name] for name in ADMISSION_FIELDS}
            return AccessPermit(self,fd,snapshot)
        except BaseException:
            os.close(fd)  # Close only: explicit LOCK_UN would also unlock a child's duplicate.
            raise

    def adopt(self,fd,snapshot,pem,fingerprint):
        """Only server-created child IPC, never an HTTP/CLI user parameter."""
        if type(fd) is not int or fd<3 or not isinstance(snapshot,dict) or set(snapshot)!=set(ADMISSION_FIELDS):
            raise GraphAccessError("graph_access_transfer_invalid")
        reference=self._lock()
        try:
            file_policy(os.fstat(fd),lock=True)
            actual,expected=os.fstat(fd),os.fstat(reference)
            if (actual.st_dev,actual.st_ino)!=(expected.st_dev,expected.st_ino):
                raise GraphAccessError("graph_access_transfer_invalid")
            flock(fd)
            permit=AccessPermit(self,fd,dict(snapshot))
            permit.check(pem,fingerprint)
            return permit
        finally:os.close(reference)

    def host_probe(self,secret,*,operation_id,epoch,purpose,consumer_role,consumer_id,pem,fingerprint):
        if not isinstance(secret,bytes) or len(secret)!=32:
            raise GraphAccessError("graph_access_probe_invalid")
        permit=HostProbePermit(self,secret,operation_id,epoch,purpose,consumer_role,consumer_id)
        permit.check(pem,fingerprint)
        return permit


class AccessPermit:
    def __init__(self,gate,fd,snapshot):
        self.gate,self.fd,self.snapshot=gate,fd,snapshot

    def __repr__(self):return "<Graph access admission>"

    def check(self,pem,fingerprint,*,method="GET",proof=False):
        if self.fd is None:raise GraphAccessError("graph_access_admission_closed")
        self.gate._identity(self.fd)
        value=self.gate.read();self.gate._bound(value);self.gate._material(value,pem,fingerprint)
        if (value["admission_epoch"]==0 or any(value[name]!=self.snapshot[name] for name in ADMISSION_FIELDS)):
            raise GraphAccessError("graph_access_generation_changed")
        if method not in {"GET","POST","PATCH"}:raise GraphAccessError("graph_access_method_invalid")

    def export(self):
        if self.fd is None:raise GraphAccessError("graph_access_admission_closed")
        return dict(fd=self.fd,snapshot=dict(self.snapshot))

    def close(self):
        if self.fd is not None:
            fd,self.fd=self.fd,None
            os.close(fd)  # Last duplicate closes the kernel lock, including after parent death.

    def __enter__(self):return self
    def __exit__(self,*_):self.close()


class HostProbePermit:
    def __init__(self,gate,secret,operation,epoch,purpose,role,consumer):
        self.gate,self._secret=gate,secret
        self.operation,self.epoch,self.purpose,self.role,self.consumer=operation,epoch,purpose,role,consumer

    def __repr__(self):return "<Host Graph read permit>"

    def check(self,pem,fingerprint,*,method="GET",proof=False):
        value=self.gate.read();self.gate._bound(value);self.gate._material(value,pem,fingerprint)
        now=int(time.time())
        if (self._secret is None or value["mode"]!="blocked" or value["operation_id"]!=self.operation
                or type(self.epoch) is not int or value["epoch"]!=self.epoch
                or method!="GET" or proof and self.purpose!="finalize-proof"):
            raise GraphAccessError("graph_access_probe_invalid")
        token_hash=hashlib.sha256(self._secret).hexdigest()
        grants=[item for item in value["grants"] if hmac.compare_digest(item["secret_hash"],token_hash)
            and (item["purpose"],item["consumer_role"],item["consumer_id"])==(self.purpose,self.role,self.consumer)
            and item["issued_at"]<=now<item["expires_at"]]
        if len(grants)!=1:raise GraphAccessError("graph_access_probe_invalid")

    def close(self):self._secret=None
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
