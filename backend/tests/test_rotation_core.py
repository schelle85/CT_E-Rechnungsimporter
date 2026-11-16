"""Durable registration recovery with real private candidate files and crypto."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.graph import GraphError
from app.rotation_core import register, verify_candidate
from app.rotation_journal import RootJournal
from rotation_test_support import BINDING, OLD_ID, NEW_ID, NOW, Remote, local_journal, material, public_key
from app.rotation_model import key_record


class RotationCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.operation=str(uuid4());self.old=material(days=365);self.remote=Remote(self.old)

    def prepare(self,journal):return journal.prepare(self.operation,self.old.fingerprint,self.remote.read(),NOW)

    def test_preparation_restart_reuses_exact_candidate_and_inventory_starts_empty(self):
        with local_journal(self.directory) as journal:
            first=self.prepare(journal);raw=journal.material(self.operation).pem
            self.assertEqual(journal.inventory()["keys"],{})
        with local_journal(self.directory) as journal,patch("app.rotation_journal.candidate",side_effect=AssertionError("regenerated")):
            self.assertEqual(self.prepare(journal),first)
            self.assertEqual(journal.material(self.operation).pem,raw)

    def test_crash_after_pem_before_metadata_reuses_exact_pem(self):
        with local_journal(self.directory) as journal:
            with patch.object(journal,"_write",side_effect=OSError("synthetic fsync interruption")):
                with self.assertRaises(OSError):self.prepare(journal)
        original=(self.directory/(self.operation+".pem")).read_bytes()
        with local_journal(self.directory) as journal,patch("app.rotation_journal.candidate",side_effect=AssertionError("regenerated")):
            self.prepare(journal)
            self.assertEqual(journal.material(self.operation).pem,original)

    def test_accepted_add_lost_reply_resumes_without_second_post(self):
        self.remote.error=GraphError("synthetic_reply_lost",uncertain=True)
        with local_journal(self.directory) as journal:
            self.prepare(journal);result=register(journal,self.operation,self.remote)
            self.assertEqual(result["phase"],"registered")
            self.assertEqual(set(journal.inventory()["keys"]),{NEW_ID})
        with local_journal(self.directory) as journal:
            self.assertEqual(register(journal,self.operation,self.remote)["phase"],"registered")
        self.assertEqual(self.remote.adds,1)

    def test_delayed_visibility_keeps_unknown_then_read_only_reconciles(self):
        self.remote.error=GraphError("synthetic_reply_lost",uncertain=True);self.remote.visible=False
        with local_journal(self.directory) as journal:
            self.prepare(journal)
            self.assertEqual(register(journal,self.operation,self.remote)["phase"],"registration_unknown")
        self.remote.visible=True
        with local_journal(self.directory) as journal:
            self.assertEqual(register(journal,self.operation,self.remote)["phase"],"registered")
        self.assertEqual(self.remote.adds,1)

    def test_process_death_after_send_permission_never_grants_another_send(self):
        self.remote.crash=True
        with local_journal(self.directory) as journal:
            self.prepare(journal)
            with self.assertRaises(SystemExit):register(journal,self.operation,self.remote)
        self.remote.crash=False
        with local_journal(self.directory) as journal:
            self.assertEqual(journal.state(self.operation)["phase"],"registration_started")
            self.assertEqual(register(journal,self.operation,self.remote)["phase"],"registration_unknown")
        self.assertEqual(self.remote.adds,1)

    def test_definite_rejection_does_not_touch_old_material_or_retry(self):
        self.remote.error=GraphError("rotation_registration_rejected",403)
        original=self.old.pem
        with local_journal(self.directory) as journal:
            self.prepare(journal)
            self.assertEqual(register(journal,self.operation,self.remote)["phase"],"registration_rejected")
            self.assertEqual(register(journal,self.operation,self.remote)["phase"],"registration_rejected")
            self.assertEqual(journal.inventory()["keys"],{})
        self.assertEqual((self.remote.adds,self.old.pem),(1,original))

    def test_changed_baseline_same_id_and_candidate_tamper_block_before_post(self):
        with local_journal(self.directory) as journal:
            self.prepare(journal)
            self.remote.records[0]["expires_at"]+=1
            with self.assertRaises(GraphError):register(journal,self.operation,self.remote)
            self.remote.records[0]["expires_at"]-=1
            (self.directory/(self.operation+".pem")).write_bytes(material(days=10).pem)
            with self.assertRaises(GraphError):register(journal,self.operation,self.remote)
        self.assertEqual(self.remote.adds,0)

    def test_multiple_matching_keys_do_not_choose_or_retry(self):
        self.remote.error=GraphError("synthetic_reply_lost",uncertain=True);self.remote.visible=False
        with local_journal(self.directory) as journal:
            self.prepare(journal);register(journal,self.operation,self.remote)
            certificate=journal.material(self.operation)
            self.remote.records.extend([key_record(public_key(certificate,str(uuid4()))) for _ in range(2)])
            self.assertEqual(register(journal,self.operation,self.remote)["phase"],"registration_unknown")
        self.assertEqual(self.remote.adds,1)

    def test_candidate_probe_uses_exact_bytes_without_ap07_monitor_call(self):
        calls=[]
        @contextmanager
        def factory(config,certificate):
            calls.append(certificate.pem)
            yield SimpleNamespace(probe=lambda:{"mailbox_access":"ok"},deadline=None)
        with local_journal(self.directory) as journal:
            self.prepare(journal);register(journal,self.operation,self.remote)
            expected=journal.material(self.operation).pem
            with patch("app.notification_certificate.record_certificate",side_effect=AssertionError("productive proof")):
                self.assertEqual(verify_candidate(journal,self.operation,deadline=10**12,client_factory=factory)["phase"],"candidate_verified")
                verify_candidate(journal,self.operation,deadline=10**12,client_factory=factory)
        self.assertEqual(calls,[expected,expected])

    def test_unmanaged_key_removal_denied_explicit_attestation_only(self):
        with local_journal(self.directory) as journal:
            with self.assertRaises(GraphError):journal.reconcile_removal(OLD_ID,self.remote.read())
            journal.adopt_existing(self.operation,self.remote.records[0],evidence="a"*64)
            self.assertEqual(journal.reconcile_removal(OLD_ID,self.remote.read()),"present")
            self.assertEqual(journal.reconcile_removal(OLD_ID,[]),"absent")
            self.assertEqual(set(journal.inventory()["keys"]),{OLD_ID})

    def test_host_policy_is_mandatory_without_test_double(self):
        with self.assertRaises(GraphError):RootJournal(self.directory,BINDING)
