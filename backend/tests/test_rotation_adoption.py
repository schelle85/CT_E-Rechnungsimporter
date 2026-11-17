"""Private adoption checkpoints; actual files/crypto, explicit local POSIX doubles."""
from contextlib import ExitStack
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.graph import GraphError
from app.graph_access import AccessBinding
from app.notification_model import graph_scope,identity
from app import rotation_adoption as module
from app.rotation_core import register
from notification_test_support import NOW,material
from rotation_test_support import BINDING,Remote,local_journal

BOOT="77777777-7777-7777-7777-777777777777"


class AdoptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.root=self.stack.enter_context(local_journal(self.temp.name))
        self.stack.enter_context(patch.object(module,"protected_bytes",side_effect=lambda p:Path(p).read_bytes()))
        self.stack.enter_context(patch.object(module,"sync_directory"))
        self.stack.enter_context(patch.object(module,"boot_id",return_value=BOOT))
        self.operation=str(uuid4());self.old=material(days=365)
        remote=Remote(self.old)
        self.root.prepare(self.operation,self.old.fingerprint,remote.read(),NOW)
        register(self.root,self.operation,remote)
        self.binding=AccessBinding("a"*40,str(uuid4()),BINDING.instance_id,BINDING.scope)
        self.journal=module.AdoptionJournal(self.root,self.binding)
        self.images={role:"sha256:"+"b"*64 for role in module.ROLES}
        self.value=self.journal.prepare(self.operation,self.old,self.images,paused=True,drain_identity="e"*64,now=NOW)

    def activate(self):
        self.root.transition(self.operation,"candidate_verified")
        self.journal.activation_started(self.operation);self.journal.activated(self.operation)

    def receipt(self,role,*,purpose="consumer-read",epoch=3,proof_revision=None):
        value=self.journal.state(self.operation);cid=hashlib.sha256((role+purpose).encode()).hexdigest()
        probe=dict(ok=True,code="graph_probe_verified",**self.binding.fields(),operation_id=self.operation,
            epoch=epoch,purpose=purpose,consumer_role=role,consumer_id=hashlib.sha256(cid.encode()).hexdigest(),
            pem_hash=value[value["target"]]["pem_hash"],fingerprint=value[value["target"]]["fingerprint"],
            at=NOW,proof_revision=proof_revision,proof_at=NOW if proof_revision is not None else None)
        probe["receipt_hash"]=identity(probe)
        return dict(container_id=cid,image=self.images[role],probe=probe)

    def verified(self):
        consumers={role:self.receipt(role) for role in module.ROLES}
        return self.journal.consumers_verified(self.operation,consumers,NOW)

    def proof(self):
        receipt=self.receipt("notifications",purpose="finalize-proof",epoch=5,proof_revision=8)
        self.journal.proof_started(self.operation,receipt,epoch=5,base_revision=7,now=NOW)
        return receipt

    def test_prepare_reuses_immutable_backup_and_candidate_and_does_not_touch_core(self):
        before=self.root.material(self.operation).pem
        again=self.journal.prepare(self.operation,self.old,self.images,paused=True,drain_identity="e"*64,now=NOW)
        self.assertEqual(self.value,again);self.assertEqual(self.journal.old_material(self.operation).pem,self.old.pem)
        self.assertEqual(self.root.material(self.operation).pem,before)
        self.assertEqual(self.root.state(self.operation)["phase"],"registered")
        with self.assertRaises(GraphError):self.journal.activation_started(self.operation)

    def test_three_actual_container_bound_receipts_precede_proof_and_commit(self):
        self.activate();self.verified();receipt=self.proof()
        self.journal.proof_verified(self.operation,receipt,NOW)
        result=self.journal.commit(self.operation,now=NOW,paused=True,drain_identity="e"*64)
        self.assertEqual(result["phase"],"committed");self.assertTrue(result["paused"])
        self.assertEqual(result["seal"],identity({name:item for name,item in result.items() if name!="seal"}))
        self.assertEqual(self.journal.state(self.operation),result)

    def test_wrong_missing_or_unbound_consumer_cannot_advance(self):
        self.activate()
        for change in ("missing","image","container","fingerprint"):
            receipts={role:self.receipt(role) for role in module.ROLES}
            if change=="missing":del receipts["api"]
            elif change=="image":receipts["api"]["image"]="sha256:"+"c"*64
            elif change=="container":receipts["api"]["container_id"]="d"*64
            else:
                probe=receipts["api"]["probe"];probe["fingerprint"]="f"*64
                probe["receipt_hash"]=identity({name:item for name,item in probe.items() if name!="receipt_hash"})
            with self.subTest(change=change),self.assertRaises(GraphError):self.journal.consumers_verified(self.operation,receipts,NOW)
        self.assertEqual(self.journal.state(self.operation)["phase"],"activated")

    def test_unknown_proof_keeps_original_intent_and_cannot_restart_write_stage(self):
        self.activate();self.verified();receipt=self.proof()
        intent=self.journal.state(self.operation)["proof_intent"]
        self.journal.proof_unknown(self.operation)
        with self.assertRaises(GraphError):self.journal.proof_started(self.operation,receipt,epoch=7,base_revision=8,now=NOW)
        self.assertEqual(self.journal.state(self.operation)["proof_intent"],intent)
        self.journal.proof_verified(self.operation,receipt,NOW)

    def test_new_pause_changed_drain_or_old_proof_prevents_commit(self):
        self.activate();self.verified();receipt=self.proof();self.journal.proof_verified(self.operation,receipt,NOW)
        for now,paused,drain in ((NOW,False,"e"*64),(NOW,True,"d"*64),(NOW+61,True,"e"*64)):
            with self.assertRaises(GraphError):self.journal.commit(self.operation,now=now,paused=paused,drain_identity=drain)
        self.assertEqual(self.journal.state(self.operation)["phase"],"proof_verified")

    def test_boot_change_prevents_effects_but_keeps_record_readable(self):
        with patch.object(module,"boot_id",return_value=str(uuid4())):
            self.assertEqual(self.journal.state(self.operation)["boot_id"],BOOT)
            with self.assertRaises(GraphError):self.journal.activation_started(self.operation)

    def test_rollback_requires_valid_original_and_all_old_consumers_and_proof(self):
        self.activate()
        with self.assertRaises(GraphError):self.journal.rollback(self.operation,self.old.expires_at)
        self.journal.rollback(self.operation,NOW);self.journal.activated(self.operation)
        self.verified();receipt=self.proof();self.journal.proof_verified(self.operation,receipt,NOW)
        result=self.journal.commit(self.operation,now=NOW,paused=True,drain_identity="e"*64)
        self.assertEqual(result["target"],"old");self.assertTrue(result["paused"])
        path=self.root.directory/(self.operation+".host.json");saved=path.read_bytes()
        with self.assertRaises(GraphError):self.journal.rollback_unknown(self.operation)
        self.assertEqual(path.read_bytes(),saved)
        self.assertEqual(self.journal.state(self.operation),result)

    def test_unsealed_rollback_unknown_checkpoint_stays_readable(self):
        self.activate();self.journal.rollback(self.operation,NOW)
        result=self.journal.rollback_unknown(self.operation)
        self.assertEqual(result["phase"],"rollback_unknown");self.assertEqual(result["target"],"old")
        self.assertIsNone(result["seal"]);self.assertEqual(self.journal.state(self.operation),result)

    def test_unknown_effect_is_read_reconciled_before_new_boot_revalidation(self):
        self.activate();self.verified();receipt=self.proof();self.journal.proof_unknown(self.operation)
        original=self.journal.state(self.operation);new_boot=str(uuid4())
        config=BINDING.config
        observed=dict(revision=8,proof=dict(fingerprint=receipt["probe"]["fingerprint"],
            scope_key=graph_scope(config.tenant_id,config.client_id,config.mailbox),at=NOW))
        with patch.object(module,"boot_id",return_value=new_boot):
            result=self.journal.recover(self.operation,pem_hash=original["new"]["pem_hash"],quiet_evidence="d"*64,
                observed=observed,now=NOW+1,paused=False,drain_identity=None)
        self.assertEqual(result["boot_id"],new_boot);self.assertEqual(result["phase"],"activated");self.assertTrue(result["paused"])
        self.assertIsNone(result["proof_intent"]);self.assertEqual(result["consumers"],{})
        archived=self.root._read(self.operation+".host-checkpoint-"+str(original["revision"])+".json")
        self.assertEqual(archived["checkpoint"],original);self.assertEqual(archived["observed_proof"],observed)

    def test_unreconciled_proof_never_resets_intent_or_writes_a_recovery_checkpoint(self):
        self.activate();self.verified();self.proof();self.journal.proof_unknown(self.operation)
        original=self.journal.state(self.operation)
        with self.assertRaises(GraphError):self.journal.recover(self.operation,pem_hash=original["new"]["pem_hash"],quiet_evidence="d"*64,
            observed=dict(revision=9,proof=None),now=NOW+1,paused=False,drain_identity=None)
        self.assertEqual(self.journal.state(self.operation),original)
        self.assertEqual(list(self.root.directory.glob("*.host-checkpoint-*.json")),[])
