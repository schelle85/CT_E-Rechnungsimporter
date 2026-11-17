"""Own-key removal effects: real root files/crypto; explicit synthetic Graph transport."""
from unittest.mock import patch
import unittest

from app.graph import GraphError
from app.notification_model import graph_scope
from app.rotation_cleanup import CleanupJournal,OVERLAP_SECONDS
from rotation_test_support import BINDING,NOW,OLD_ID,Remote,material
import test_rotation_adoption as adoption_fixture


class CleanupRemote(Remote):
    def __init__(self,old,new):
        super().__init__(old);self.candidate=new;self.signer=new;self.removes=0;self.removal_error=None

    def remove(self,key):
        self.removes+=1
        if self.removal_error=="reject":raise GraphError("synthetic_rejection",403)
        self.records=[item for item in self.records if item["key_id"]!=key]
        if self.removal_error=="lost":raise GraphError("synthetic_response_lost",uncertain=True)
        if self.removal_error=="crash":raise SystemExit("synthetic loss after remote effect")


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.fixture=adoption_fixture.AdoptionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.activate();f.verified();receipt=f.proof();f.journal.proof_verified(f.operation,receipt,NOW)
        f.journal.commit(f.operation,now=NOW,paused=True,drain_identity="e"*64)
        self.operation=f.operation;self.root=f.root;self.new=self.root.material(self.operation)
        self.graph=CleanupRemote(f.old,self.new);self.cleanup=CleanupJournal(f.journal)
        self.root.adopt_existing(self.operation,self.graph.records[0],evidence="d"*64)
        self.now=NOW+OVERLAP_SECONDS

    def proof(self,**changes):
        config=BINDING.config
        return dict(dict(fingerprint=self.new.fingerprint,scope_key=graph_scope(config.tenant_id,config.client_id,config.mailbox),at=self.now),**changes)

    def remove(self,**changes):
        options=dict(operation=self.operation,graph=self.graph,material=self.new,proof=self.proof(),now=self.now);options.update(changes)
        return self.cleanup.remove(**options)

    def test_owned_old_key_removed_once_and_only_after_seven_day_overlap(self):
        plan=self.cleanup.plan(self.operation);self.assertEqual(plan["not_before"],self.now)
        self.assertEqual(self.remove(now=self.now-1,proof=self.proof(at=self.now-1))["phase"],"planned");self.assertEqual(self.graph.removes,0)
        result=self.remove();self.assertEqual(result["phase"],"remote_absent");self.assertEqual(self.graph.removes,1)
        self.assertEqual(self.remove(),result);self.assertEqual(self.graph.removes,1)
        self.assertEqual([item["fingerprint"] for item in self.graph.read()],[self.new.fingerprint])
        self.assertTrue((self.root.directory/(self.operation+".old.pem")).exists())  # Remote result alone never unlinks files.

    def test_unmanaged_old_key_is_retained_without_remote_write(self):
        inventory=self.root.inventory();del inventory["keys"][OLD_ID];self.root._write("inventory.json",inventory)
        self.cleanup.plan(self.operation);before=self.graph.read();result=self.remove()
        self.assertEqual(result["phase"],"unmanaged_retained");self.assertEqual(self.graph.read(),before);self.assertEqual(self.graph.removes,0)

    def test_lost_response_is_unknown_then_read_only_absence_reconciliation(self):
        self.cleanup.plan(self.operation);self.graph.removal_error="lost"
        result=self.remove();self.assertEqual(result["phase"],"removal_unknown");reads=self.graph.reads
        result=self.remove();self.assertEqual(result["phase"],"remote_absent")
        self.assertGreater(self.graph.reads,reads);self.assertEqual(self.graph.removes,1)

    def test_process_loss_after_remote_effect_never_repeats_post(self):
        self.cleanup.plan(self.operation);self.graph.removal_error="crash"
        with self.assertRaises(SystemExit):self.remove()
        self.assertEqual(self.cleanup.state(self.operation)["phase"],"removal_started")
        self.assertEqual(self.remove()["phase"],"remote_absent");self.assertEqual(self.graph.removes,1)

    def test_loss_after_send_permission_before_transport_never_grants_another_post(self):
        self.cleanup.plan(self.operation);original=self.cleanup.save
        def crash(value,**changes):
            saved=original(value,**changes)
            if changes.get("phase")=="removal_started":raise SystemExit("synthetic fsync-only crash")
            return saved
        with patch.object(self.cleanup,"save",side_effect=crash),self.assertRaises(SystemExit):self.remove()
        self.assertEqual(self.remove()["phase"],"removal_unknown");self.assertEqual(self.graph.removes,0)

    def test_rejection_and_still_present_key_remain_unknown_without_retry(self):
        self.cleanup.plan(self.operation);self.graph.removal_error="reject"
        self.assertEqual(self.remove()["phase"],"removal_unknown")
        self.assertEqual(self.remove()["phase"],"removal_unknown");self.assertEqual(self.graph.removes,1)

    def test_changed_owner_remote_target_or_stale_proof_cannot_remove(self):
        self.cleanup.plan(self.operation)
        for proof in (self.proof(at=self.now-61),self.proof(fingerprint="f"*64),self.proof(scope_key="f"*64)):
            with self.subTest(proof=proof),self.assertRaises(GraphError):self.remove(proof=proof)
        self.graph.records[0]["fingerprint"]="f"*64
        with self.assertRaises(GraphError):self.remove()
        self.graph.records[0]["fingerprint"]=self.fixture.old.fingerprint
        inventory=self.root.inventory();inventory["keys"][OLD_ID]["evidence"]="f"*64;self.root._write("inventory.json",inventory)
        with self.assertRaises(GraphError):self.remove()
        self.assertEqual(self.graph.removes,0);self.assertEqual(self.cleanup.state(self.operation)["phase"],"planned")

    def test_ambiguous_ownership_is_not_arbitrarily_selected(self):
        inventory=self.root.inventory();inventory["keys"]["99999999-9999-9999-9999-999999999999"]=dict(inventory["keys"][OLD_ID])
        self.root._write("inventory.json",inventory)
        with self.assertRaises(GraphError):self.cleanup.plan(self.operation)
        self.assertEqual(self.graph.removes,0)

    def test_shorter_actual_old_validity_caps_overlap_without_expanding_it(self):
        with patch.object(adoption_fixture,"material",side_effect=lambda **kw:material(days=3)):
            f=adoption_fixture.AdoptionTests();f.setUp();self.addCleanup(f.doCleanups)
        f.activate();f.verified();receipt=f.proof();f.journal.proof_verified(f.operation,receipt,NOW)
        f.journal.commit(f.operation,now=NOW,paused=True,drain_identity="e"*64)
        plan=CleanupJournal(f.journal).plan(f.operation)
        self.assertEqual(plan["not_before"],f.old.expires_at);self.assertLess(plan["not_before"],NOW+OVERLAP_SECONDS)
