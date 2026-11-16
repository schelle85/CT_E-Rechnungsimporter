"""AP12 C1 gate contract. Explicit POSIX/flock/ownership doubles on Windows."""
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import stat
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import graph_access as model

BOOT="11111111-1111-1111-1111-111111111111"
BINDING=model.AccessBinding("a"*40,"22222222-2222-2222-2222-222222222222",
    "33333333-3333-3333-3333-333333333333","b"*64)
PEM=b"synthetic-material-for-admission-contract"
FP="c"*64
NOW=1794864000

spec=importlib.util.spec_from_file_location("graph_access_host_fixture",
    Path(__file__).parents[2]/"deploy/graph-access-host.py")
host_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(host_module)


class GateFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="ap12-gate-")
        self.path=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.addCleanup(lambda:[item.chmod(0o600) for item in self.path.iterdir() if item.is_file()])
        self.patches=ExitStack();self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(model,"directory_policy"))
        self.patches.enter_context(patch.object(model,"file_policy"))
        self.patches.enter_context(patch.object(model,"flock"))
        self.patches.enter_context(patch.object(model,"boot_id",return_value=BOOT))
        self.patches.enter_context(patch.object(host_module,"root_policy"))
        for name in ("O_NOFOLLOW","O_NONBLOCK"):self.patches.enter_context(patch.object(os,name,0,create=True))
        for name in ("fchown","fchmod"):self.patches.enter_context(patch.object(os,name,create=True))
        self.patches.enter_context(patch.object(host_module.time,"time",return_value=NOW))
        self.patches.enter_context(patch.object(host_module.GraphGateWriter,"_sync"))
        @contextmanager
        def host_lock(_):yield True
        host=SimpleNamespace(controlled_directory=lambda _:None,host_lock=host_lock)
        self.writer=host_module.GraphGateWriter(self.path,BINDING,host,model)
        self.gate=model.AccessGate(BINDING,directory=self.path)
        self.operation=str(uuid4())
        with self.writer.session():self.writer.initialize(self.operation,hashlib.sha256(PEM).hexdigest(),FP)

    def allow(self):
        with self.writer.session():
            current=self.gate.read()
            with self.writer.exclusive(self.operation,expected_epoch=current["epoch"],until=10**12):
                return self.writer.release(self.operation,expected_epoch=current["epoch"],release_hash="d"*64)


class GraphAdmissionTests(GateFixture):
    def test_closed_bootstrap_cannot_admit_until_explicit_release(self):
        with self.assertRaises(model.GraphAccessError):self.gate.admit(PEM,FP)
        self.allow()
        with self.gate.admit(PEM,FP) as permit:permit.check(PEM,FP,method="POST",proof=True)

    def test_wrong_boot_binding_or_actual_bytes_denied(self):
        self.allow()
        with patch.object(model,"boot_id",return_value=str(uuid4())):
            with self.assertRaises(model.GraphAccessError):self.gate.admit(PEM,FP)
        other=model.AccessGate(replace(BINDING,source_commit="e"*40),directory=self.path)
        with self.assertRaises(model.GraphAccessError):other.admit(PEM,FP)
        with self.assertRaises(model.GraphAccessError):self.gate.admit(b"other",FP)

    def test_admitted_child_duplicate_survives_parent_close_while_new_requests_stop(self):
        self.allow();parent=self.gate.admit(PEM,FP);transfer=parent.export();duplicate=os.dup(transfer["fd"])
        child=self.gate.adopt(duplicate,transfer["snapshot"],PEM,FP)
        with self.writer.session():
            current=self.gate.read()
            self.writer.block(str(uuid4()),expected_epoch=current["epoch"])
        with self.assertRaises(model.GraphAccessError):self.gate.admit(PEM,FP)
        parent.close()
        try:child.check(PEM,FP)
        finally:child.close()
        self.assertIsNone(parent.fd)
        with self.assertRaises(model.GraphAccessError):parent.export()

    def test_unrelated_fd_cannot_claim_inherited_admission(self):
        self.allow()
        with self.gate.admit(PEM,FP) as permit:
            path=self.path/"different.lock";path.write_bytes(b"")
            fd=os.open(path,os.O_RDONLY)
            try:
                with self.assertRaises(model.GraphAccessError):self.gate.adopt(fd,permit.snapshot,PEM,FP)
            finally:os.close(fd)

    def test_new_credential_generation_invalidates_old_snapshot(self):
        self.allow();permit=self.gate.admit(PEM,FP)
        try:
            with self.writer.session():
                closed=self.writer.block(str(uuid4()),expected_epoch=self.gate.read()["epoch"])
                with self.writer.exclusive(closed["operation_id"],expected_epoch=closed["epoch"],until=10**12):
                    self.writer.candidate(closed["operation_id"],expected_epoch=closed["epoch"],pem_hash="f"*64,fingerprint="e"*64)
            with self.assertRaises(model.GraphAccessError):permit.check(PEM,FP)
        finally:permit.close()

    def test_open_pause_is_preserved_by_explicit_paused_release(self):
        with self.writer.session():
            with self.writer.exclusive(self.operation,expected_epoch=1,until=10**12):
                state=self.writer.release(self.operation,expected_epoch=1,release_hash="d"*64,pause=True)
        self.assertEqual(state["mode"],"paused")
        with self.assertRaises(model.GraphAccessError):self.gate.admit(PEM,FP)

    def test_root_exclusive_requirement_and_epoch_cas(self):
        with self.writer.session():
            with self.assertRaises(ValueError):self.writer.release(self.operation,expected_epoch=1,release_hash="d"*64)
            with self.writer.exclusive(self.operation,expected_epoch=1,until=10**12):
                with self.assertRaises(ValueError):self.writer.release(self.operation,expected_epoch=99,release_hash="d"*64)
        self.assertEqual(self.gate.read()["epoch"],1)

    def test_missing_or_ambiguous_control_has_no_fallback(self):
        (self.path/"graph-access.json").write_bytes(b'{"schema_version":1,"schema_version":1}')
        with self.assertRaises(model.GraphAccessError):self.gate.admit(PEM,FP)
        (self.path/"graph-access.json").unlink()
        with self.assertRaises(model.GraphAccessError):self.gate.admit(PEM,FP)

    def test_initialization_flush_failure_closes_its_descriptor(self):
        path=self.path/"failed-init";path.mkdir()
        writer=host_module.GraphGateWriter(path,BINDING,self.writer.host,model)
        original_open=os.open;opened=[]
        def tracking_open(*args,**kwargs):
            fd=original_open(*args,**kwargs)
            if Path(args[0]).name=="graph-access.lock":opened.append(fd)
            return fd
        with writer.session(),patch.object(os,"open",side_effect=tracking_open),\
                patch.object(os,"fsync",side_effect=OSError("synthetic flush failure")):
            with self.assertRaises(OSError):writer.initialize(str(uuid4()),hashlib.sha256(PEM).hexdigest(),FP)
        self.assertEqual(len(opened),1)
        with self.assertRaises(OSError):os.fstat(opened[0])


class HostProbeTests(GateFixture):
    def issue(self,purpose="consumer-read",role="api"):
        self.context=ExitStack();self.addCleanup(self.context.close)
        self.context.enter_context(self.writer.session())
        current=self.gate.read()
        self.context.enter_context(self.writer.exclusive(self.operation,expected_epoch=current["epoch"],until=10**12))
        return self.writer.issue_probe(self.operation,expected_epoch=current["epoch"],purpose=purpose,
            consumer_role=role,consumer_id="e"*64)

    def probe(self,secret,value,*,purpose="consumer-read",role="api",consumer="e"*64):
        return self.gate.host_probe(secret,operation_id=self.operation,epoch=value["epoch"],purpose=purpose,
            consumer_role=role,consumer_id=consumer,pem=PEM,fingerprint=FP)

    def test_host_probe_is_exact_get_only_without_normal_admission_or_proof(self):
        secret,value=self.issue();permit=self.probe(secret,value)
        self.assertNotIn(secret.hex(),(self.path/"graph-access.json").read_text())
        self.assertNotIn(secret.hex(),repr(permit))
        permit.check(PEM,FP)
        for kwargs in ({"method":"POST"},{"proof":True}):
            with self.assertRaises(model.GraphAccessError):permit.check(PEM,FP,**kwargs)
        with self.assertRaises(model.GraphAccessError):self.gate.admit(PEM,FP)

    def test_wrong_secret_role_consumer_epoch_and_expiry_denied(self):
        secret,value=self.issue()
        for call in (lambda:self.probe(b"x"*32,value),lambda:self.probe(secret,value,role="processing"),
                lambda:self.probe(secret,value,consumer="f"*64),lambda:self.probe(secret,dict(value,epoch=value["epoch"]+1))):
            with self.assertRaises(model.GraphAccessError):call()
        with patch.object(model.time,"time",return_value=NOW+60):
            with self.assertRaises(model.GraphAccessError):self.probe(secret,value)

    def test_only_separate_finalize_grant_may_record_proof_and_revocation_sticks(self):
        secret,value=self.issue(purpose="finalize-proof",role="notifications")
        permit=self.probe(secret,value,purpose="finalize-proof",role="notifications")
        permit.check(PEM,FP,proof=True)
        self.writer.revoke_probe(self.operation,expected_epoch=value["epoch"])
        with self.assertRaises(model.GraphAccessError):permit.check(PEM,FP,proof=True)


class RecordValidationTests(unittest.TestCase):
    def test_file_mode_owner_link_and_lock_size_are_strict(self):
        normal=dict(st_mode=stat.S_IFREG|0o440,st_uid=0,st_gid=10001,st_nlink=1,st_size=0)
        model.file_policy(SimpleNamespace(**normal),lock=True)
        for change in ({"st_uid":10001},{"st_gid":0},{"st_nlink":2},{"st_mode":stat.S_IFREG|0o444},{"st_size":1}):
            with self.assertRaises(model.GraphAccessError):model.file_policy(SimpleNamespace(**dict(normal,**change)),lock=True)

    def test_binding_and_grant_types_fail_closed(self):
        with self.assertRaises(model.GraphAccessError):model.AccessBinding("a"*39,BINDING.deployment_id,BINDING.instance_id,BINDING.scope_key)
        with self.assertRaises(model.GraphAccessError):model.validate({})
