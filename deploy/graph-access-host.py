"""AP12 fixed Graph gate writer. Reuses AP08 host policy/lock helpers; no CLI."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import time

WRITER_LOCK="/run/invoice-importer/graph-rotation.lock"


def root_policy():
    if os.name!="posix" or os.geteuid()!=0:raise ValueError("graph_gate_root_required")


class GraphGateWriter:
    def __init__(self,directory,binding,host,model):
        self.directory,self.binding,self.host,self.model=Path(directory),binding,host,model
        self.gate=model.AccessGate(binding,directory=directory)
        self._writer=False;self._exclusive=None

    @contextmanager
    def session(self):
        root_policy()
        if self._writer:raise ValueError("graph_gate_writer_busy")
        self.host.controlled_directory(self.directory)
        self.model.directory_policy(self.directory)
        with self.host.host_lock(WRITER_LOCK) as acquired:
            if not acquired:raise ValueError("graph_gate_writer_busy")
            self._writer=True
            try:yield self
            finally:self._writer=False

    def _require(self,*,exclusive=False):
        if not self._writer or exclusive and self._exclusive is None:
            raise ValueError("graph_gate_lock_required")
        self.model.directory_policy(self.directory)
        if exclusive:self.gate._identity(self._exclusive)

    def _current(self):
        value=self.gate.read()
        if any(value[name]!=expected for name,expected in self.binding.fields().items()):
            raise ValueError("graph_gate_binding_changed")
        return value

    def _sync(self):
        fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)

    def _save(self,value,expected_epoch):
        self._require()
        self.model.validate(value)
        current=None
        if (self.directory/"graph-access.json").exists() or (self.directory/"graph-access.json").is_symlink():
            current=self._current()
        if (current is None and expected_epoch!=0 or current is not None and current["epoch"]!=expected_epoch
                or value["epoch"]!=expected_epoch+1):raise ValueError("graph_gate_changed")
        if any(value[name]!=expected for name,expected in self.binding.fields().items()):
            raise ValueError("graph_gate_binding_changed")
        raw=json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")
        if len(raw)>16384:raise ValueError("graph_gate_limit")
        fd,temporary=tempfile.mkstemp(prefix=".graph-access-",dir=self.directory)
        try:
            with os.fdopen(fd,"wb") as output:
                os.fchown(output.fileno(),0,10001);os.fchmod(output.fileno(),0o440)
                output.write(raw);output.flush();os.fsync(output.fileno())
            os.replace(temporary,self.directory/"graph-access.json");self._sync()
        finally:
            if os.path.exists(temporary):os.unlink(temporary)
        return value

    def initialize(self,operation,pem_hash,fingerprint):
        self._require()
        if (self.directory/"graph-access.json").exists() or (self.directory/"graph-access.json").is_symlink():
            raise ValueError("graph_gate_already_initialized")
        path=self.directory/"graph-access.lock"
        try:
            fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        except FileExistsError:
            fd=self.gate._lock()
            os.close(fd)
        else:
            try:
                os.fchown(fd,0,10001);os.fchmod(fd,0o440);os.fsync(fd)
            finally:os.close(fd)
        self._sync()
        value=dict(schema_version=1,**self.binding.fields(),boot_id=self.model.boot_id(),epoch=1,
            admission_epoch=0,operation_id=operation,mode="blocked",pem_hash=pem_hash,
            fingerprint=fingerprint,release_hash=None,grants=[])
        return self._save(value,0)

    def block(self,operation,*,expected_epoch,pause=False):
        self._require()
        current=self._current()
        if any(current[name]!=value for name,value in self.binding.fields().items()):
            raise ValueError("graph_gate_binding_changed")
        if current["mode"]=="blocked" and current["operation_id"]!=operation:
            raise ValueError("graph_gate_operation_unreconciled")
        value=dict(current,epoch=expected_epoch+1,operation_id=operation,mode="paused" if pause else "blocked",grants=[])
        return self._save(value,expected_epoch)

    @contextmanager
    def exclusive(self,operation,*,expected_epoch,until):
        self._require()
        if self._exclusive is not None:raise ValueError("graph_gate_lock_required")
        current=self._current()
        if current["mode"]!="blocked" or current["operation_id"]!=operation or current["epoch"]!=expected_epoch:
            raise ValueError("graph_gate_changed")
        fd=self.gate._lock()
        try:
            while True:
                try:
                    self.model.flock(fd,exclusive=True);break
                except self.model.GraphAccessError as error:
                    if error.code!="graph_access_busy" or time.monotonic()>=until:raise
                    time.sleep(min(.1,max(0,until-time.monotonic())))
            if self.gate.read()!=current:raise ValueError("graph_gate_changed")
            self._exclusive=fd
            try:yield self
            finally:self._exclusive=None
        finally:os.close(fd)

    def candidate(self,operation,*,expected_epoch,pem_hash,fingerprint):
        self._require(exclusive=True)
        current=self._current()
        if current["operation_id"]!=operation or current["mode"]!="blocked":raise ValueError("graph_gate_changed")
        value=dict(current,epoch=expected_epoch+1,admission_epoch=0,pem_hash=pem_hash,
            fingerprint=fingerprint,boot_id=self.model.boot_id(),release_hash=None,grants=[])
        return self._save(value,expected_epoch)

    def issue_probe(self,operation,*,expected_epoch,purpose,consumer_role,consumer_id):
        self._require(exclusive=True)
        current=self._current()
        if current["operation_id"]!=operation or current["mode"]!="blocked":raise ValueError("graph_gate_changed")
        secret=secrets.token_bytes(32);now=int(time.time())
        grant=dict(secret_hash=hashlib.sha256(secret).hexdigest(),purpose=purpose,
            consumer_role=consumer_role,consumer_id=consumer_id,issued_at=now,expires_at=now+60)
        # One explicit consumer invocation at a time; stale grants are revoked.
        value=dict(current,epoch=expected_epoch+1,grants=[grant])
        self._save(value,expected_epoch)
        return secret,value

    def revoke_probe(self,operation,*,expected_epoch):
        self._require(exclusive=True)
        current=self._current()
        if current["operation_id"]!=operation or current["mode"]!="blocked":raise ValueError("graph_gate_changed")
        return self._save(dict(current,epoch=expected_epoch+1,grants=[]),expected_epoch)

    def release(self,operation,*,expected_epoch,release_hash,pause=False):
        """Caller must first verify consumer/proof/journal receipts. Open is last."""
        self._require(exclusive=True)
        current=self._current()
        if current["operation_id"]!=operation or current["mode"]!="blocked" or not self.model._hex(release_hash):
            raise ValueError("graph_gate_changed")
        value=dict(current,epoch=expected_epoch+1,admission_epoch=0 if pause else expected_epoch+1,
            mode="paused" if pause else "allowed",boot_id=self.model.boot_id(),release_hash=release_hash,grants=[])
        return self._save(value,expected_epoch)
