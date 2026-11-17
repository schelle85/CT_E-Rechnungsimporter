"""Retirement of own inactive PEM files; real files/crypto, explicit existing POSIX doubles."""
import copy
import hashlib
import json
from unittest.mock import patch
import unittest
from uuid import uuid4

from app.graph import GraphError
from app.notification_model import identity
from app.rotation_material import check_material
from rotation_test_support import NOW,OLD_ID
import test_rotation_cleanup as cleanup_fixture


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.fixture=cleanup_fixture.CleanupTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.root=f.root;self.cleanup=f.cleanup;self.operation=f.operation;self.new=f.new
        self.path=self.root.directory/(self.operation+".old.pem")

    def ready(self):
        self.cleanup.plan(self.operation);self.assertEqual(self.fixture.remove()["phase"],"remote_absent")

    def finish(self):return self.cleanup.finish_local(self.operation,self.new)

    def test_confirmed_removal_retires_only_old_copy_and_preserves_sealed_history(self):
        self.ready();host=self.fixture.fixture.journal.state(self.operation)
        preserved={name:(self.root.directory/name).read_bytes() for name in (
            self.operation+".host.json",self.operation+".json","inventory.json",self.operation+".pem")}
        foreign=self.root.directory/"operator-copy.pem";foreign.write_bytes(self.fixture.fixture.old.pem)
        self.assertEqual(self.finish()["phase"],"completed");self.assertFalse(self.path.exists())
        self.assertEqual(foreign.read_bytes(),self.fixture.fixture.old.pem)
        for name,raw in preserved.items():self.assertEqual((self.root.directory/name).read_bytes(),raw)
        self.assertEqual(self.fixture.fixture.journal.state(self.operation),host)
        receipt=self.root._read(self.path.name+".retired.json")
        self.assertNotIn("PRIVATE KEY",json.dumps(receipt));self.assertEqual(receipt["material"],host["old"])
        self.assertEqual(self.finish()["phase"],"completed");self.assertEqual(self.fixture.graph.removes,1)

    def test_unknown_remote_effect_never_deletes_local_material(self):
        self.cleanup.plan(self.operation);self.fixture.graph.removal_error="lost";self.fixture.remove()
        with self.assertRaises(GraphError):self.finish()
        self.assertTrue(self.path.exists());self.assertFalse((self.root.directory/(self.path.name+".retired.json")).exists())

    def test_loss_after_retirement_receipt_before_unlink_resumes_without_remote_post(self):
        self.ready();write=self.root._write
        def crash(name,value):
            write(name,value)
            if name.endswith(".retired.json"):raise SystemExit("synthetic loss after durable public receipt")
        with patch.object(self.root,"_write",side_effect=crash),self.assertRaises(SystemExit):self.finish()
        self.assertTrue(self.path.exists());self.assertEqual(self.cleanup.state(self.operation)["phase"],"local_pending")
        receipt=(self.root.directory/(self.path.name+".retired.json")).read_bytes()
        self.assertEqual(self.finish()["phase"],"completed");self.assertFalse(self.path.exists())
        self.assertEqual((self.root.directory/(self.path.name+".retired.json")).read_bytes(),receipt)
        self.assertEqual(self.fixture.graph.removes,1)

    def test_loss_after_unlink_before_completion_keeps_host_receipt_valid_and_resumes(self):
        self.ready()
        def sync(_):
            if not self.path.exists():raise SystemExit("synthetic loss after unlink")
        with patch("app.rotation_journal.sync_directory",side_effect=sync),self.assertRaises(SystemExit):self.finish()
        self.assertFalse(self.path.exists());self.assertEqual(self.cleanup.state(self.operation)["phase"],"local_pending")
        self.assertEqual(self.fixture.fixture.journal.state(self.operation)["phase"],"committed")
        self.assertEqual(self.finish()["phase"],"completed");self.assertEqual(self.fixture.graph.removes,1)

    def test_changed_retirement_attestation_or_missing_file_without_it_is_rejected(self):
        self.ready();raw=self.path.read_bytes();self.path.unlink()
        with self.assertRaises(GraphError):self.fixture.fixture.journal.state(self.operation)
        self.path.write_bytes(raw);self.finish();original=self.root._read(self.path.name+".retired.json")
        for changes in (dict(scope_key="a"*64),dict(certificate_der="YWJj"),dict(key_id=str(uuid4()))):
            changed=dict(original,**changes);changed["seal"]=identity({key:item for key,item in changed.items() if key!="seal"})
            self.root._write(self.path.name+".retired.json",changed)
            with self.subTest(changes=changes),self.assertRaises(GraphError):self.fixture.fixture.journal.state(self.operation)
        self.root._write(self.path.name+".retired.json",original)
        self.assertEqual(self.fixture.fixture.journal.state(self.operation)["phase"],"committed")

    def test_prior_owned_candidate_and_probe_copies_are_removed_but_successor_stays(self):
        previous=str(uuid4());old=self.fixture.fixture.old
        with patch("app.rotation_journal.candidate",return_value=old):self.root.prepare(previous,"a"*64,[],NOW)
        self.root.transition(previous,"registration_started")
        self.root.transition(previous,"registered",registered_key_id=OLD_ID)
        self.root.transition(previous,"candidate_verified")
        inventory=self.root.inventory();del inventory["keys"][OLD_ID];self.root._write("inventory.json",inventory)
        self.root.record_created(previous)
        prior=self.root.directory/(previous+".pem");probe=self.root.directory/(previous+".probe.pem");probe.write_bytes(old.pem)
        current=self.root.directory/(self.operation+".probe.pem");current.write_bytes(self.new.pem)
        expected=dict(fingerprint=old.fingerprint,pem_hash=hashlib.sha256(old.pem).hexdigest(),expires_at=old.expires_at)
        self.ready();self.assertEqual(len(self.finish()["files"]),3)
        for path in (prior,probe,self.path):
            self.assertFalse(path.exists());self.assertEqual(check_material(self.root,path.name,expected),expected)
        self.assertEqual(current.read_bytes(),self.new.pem);self.assertEqual(self.root.material(self.operation),self.new)
        self.assertEqual(self.fixture.fixture.journal.state(self.operation)["phase"],"committed")

    def test_changed_current_material_or_host_never_grants_local_deletion(self):
        self.ready()
        with self.assertRaises(GraphError):self.cleanup.finish_local(self.operation,self.fixture.fixture.old)
        state=copy.deepcopy(self.fixture.fixture.journal.state(self.operation));state.update(phase="activated",seal=None)
        self.root._write(self.operation+".host.json",state)
        with self.assertRaises(GraphError):self.finish()
        self.assertTrue(self.path.exists())

    def test_unmanaged_old_material_is_retained_when_closing_cleanup(self):
        inventory=self.root.inventory();del inventory["keys"][OLD_ID];self.root._write("inventory.json",inventory)
        self.cleanup.plan(self.operation);self.assertEqual(self.fixture.remove()["phase"],"unmanaged_retained")
        result=self.finish();self.assertEqual(result["phase"],"completed");self.assertEqual(result["error_code"],"rotation_old_key_unmanaged")
        self.assertTrue(self.path.exists());self.assertEqual(result["files"],[]);self.assertEqual(self.fixture.graph.removes,0)
