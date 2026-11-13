from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import unittest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.processing_plan import ProcessingError
from app.processing_state import ProcessingStore, attachments, corrections, metadata
from app.storage import StorageResult
from test_processing_plan import attachment, mail
from test_storage_migration import migration

FOLDERS = {name: "folder-" + name for name in ("Success", "Failed", "Nachfragen", "unzugeordnet", "Mahnung", "Zahlungsavis")}


class ProcessingStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        if os.environ.get("INTEGRATION_DB") == "1":
            from app.database import make_engine
            self.engine = make_engine()
        else:
            self.engine = sa.create_engine("sqlite:///" + str(Path(self.temp.name) / "processing.sqlite"))
        self.addCleanup(self.engine.dispose)
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            for table in reversed(metadata.sorted_tables):
                connection.execute(table.delete())
        self.now = [1000]
        self.store = ProcessingStore(self.engine, clock=lambda: self.now[0])
        self.mailbox = "invoice@example.invalid"
        self.key = self.store.register(self.mailbox, mail(), [attachment()])

    def claim(self):
        result = self.store.claim(self.key)
        return result["owner"], result["revision"]

    def finding(self, owner, revision, *, status="recognized", category="PDF", reason="invoice_fields"):
        key = self.store.get_attachments(self.key)[0]["attachment_key"]
        self.store.content(self.key, key, owner, revision, byte_size=7, sha256="a" * 64)
        self.store.finding(self.key, key, owner, revision, {"status": status, "category": category,
            "reason": reason, "method": "pdf_text", "original_sha256": "a" * 64, "rule_version": "ap03-4"})
        return key

    def storage(self, key, owner, revision, state="stored"):
        request = self.store.begin_storage(self.key, key, owner, revision, "synthetic", "d" * 64)
        self.store.stored(self.key, key, owner, revision, StorageResult(request.key, state, "PDF/synthetic.pdf"))
        return request

    def close(self, owner, revision):
        value = self.store.prepare_close(self.key, owner, revision, FOLDERS)
        self.store.finish_close(self.key, owner, revision, parent_id=value["destination_id"], flagged=True, intent_key=value["intent_key"])
        return value

    def test_manifest_registered_once_and_cannot_be_silently_changed(self):
        self.assertEqual(self.store.register(self.mailbox, mail(), [attachment()]), self.key)
        with self.assertRaises(ProcessingError):
            self.store.register(self.mailbox, mail(), [attachment(name="different.pdf")])
        self.assertEqual(self.store.get_attachments(self.key)[0]["state"], "pending")

    def test_parallel_claim_and_expired_owner_cannot_reserve_an_external_effect(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            claims = list(pool.map(lambda _: self.store.claim(self.key), range(6)))
        self.assertEqual(sum(value["mode"] == "owned" for value in claims), 1)
        old = next(value for value in claims if value["mode"] == "owned")
        key = self.finding(old["owner"], 0)
        self.now[0] += 601
        owner, revision = self.claim()
        with self.assertRaises(ProcessingError):
            self.store.begin_storage(self.key, key, old["owner"], 0, "synthetic", "d" * 64)
        self.assertIsNone(self.store.get_attachments(self.key)[0]["effect_key"])
        self.storage(key, owner, revision)

    def test_existing_effect_identity_survives_takeover_and_week_change(self):
        owner, revision = self.claim()
        key = self.finding(owner, revision)
        first = self.store.begin_storage(self.key, key, owner, revision, "synthetic", "d" * 64)
        self.now[0] += 7 * 86400
        current, revision = self.claim()
        self.assertEqual(self.store.begin_storage(self.key, key, current, revision, "synthetic", "d" * 64), first)
        with self.assertRaises(ProcessingError):
            self.store.begin_storage(self.key, key, current, revision, "changed-scope", "d" * 64)
        with self.assertRaises(ProcessingError):
            self.store.stored(self.key, key, owner, revision, StorageResult(first.key, "stored"))

    def test_late_classifier_reply_cannot_overwrite_after_takeover(self):
        owner, revision = self.claim()
        key = self.store.get_attachments(self.key)[0]["attachment_key"]
        self.store.content(self.key, key, owner, revision, byte_size=7, sha256="a" * 64)
        self.now[0] += 601
        current, _ = self.claim()
        with self.assertRaises(ProcessingError):
            self.store.finding(self.key, key, owner, revision, {"status": "ignored"})
        self.store.content(self.key, key, current, revision, byte_size=7, sha256="a" * 64)
        with self.assertRaises(ProcessingError):
            self.store.content(self.key, key, current, revision, byte_size=7, sha256="b" * 64)

    def test_uncertain_storage_and_busy_prevent_any_close_intent(self):
        owner, revision = self.claim()
        key = self.finding(owner, revision)
        for state in ("busy", "operator_required"):
            self.storage(key, owner, revision, state)
            with self.assertRaises(ProcessingError):
                self.store.prepare_close(self.key, owner, revision, FOLDERS)
            self.assertIsNone(self.store.get_message(self.key)["close_key"])

    def test_close_requires_observed_target_and_flag_then_survives_new_connection(self):
        owner, revision = self.claim()
        key = self.finding(owner, revision)
        self.storage(key, owner, revision)
        value = self.store.prepare_close(self.key, owner, revision, FOLDERS)
        with self.assertRaises(ProcessingError):
            self.store.finish_close(self.key, owner, revision, parent_id="elsewhere", flagged=True, intent_key=value["intent_key"])
        self.close(owner, revision)
        reloaded = ProcessingStore(self.engine, clock=lambda: self.now[0])
        self.assertEqual(reloaded.claim(self.key)["mode"], "idle")
        self.assertEqual(reloaded.get_attachments(self.key)[0]["storage_state"], "stored")
        two = self.store.register(self.mailbox, mail(id="two"), [attachment("r1", kind="reference"), attachment("r2", kind="reference")])
        claim = self.store.claim(two)
        for row in self.store.get_attachments(two):
            self.store.ignore(two, row["attachment_key"], claim["owner"], 0, "unsupported_attachment_kind")
        intent = self.store.prepare_close(two, claim["owner"], 0, FOLDERS)
        self.assertTrue(intent["flag_required"])
        with self.assertRaises(ProcessingError):
            self.store.finish_close(two, claim["owner"], 0, parent_id=intent["destination_id"], flagged=False, intent_key=intent["intent_key"])

    def test_signature_needs_confirmed_raw_hash_not_inline_metadata(self):
        owner, revision = self.claim()
        key = self.store.get_attachments(self.key)[0]["attachment_key"]
        with self.assertRaises(ProcessingError):
            self.store.content(self.key, key, owner, revision, byte_size=7, sha256="a" * 64, signature=True)

    def test_correction_generation_reuses_source_and_keeps_original_finding(self):
        owner, revision = self.claim()
        key = self.finding(owner, revision, status="unknown", category=None, reason="ambiguous_pdf")
        original = self.store.get_attachments(self.key)[0]["original_finding"]
        approval = self.store.approved_correction(key, "approval-1", "PDF", "synthetic-user", self.now[0])
        with self.assertRaises(ProcessingError):
            self.store.start_corrections(self.key)  # Predecessor not closed; even approved is insufficient.
        previous = self.close(owner, revision)
        self.assertEqual(previous["destination"], "unzugeordnet")
        self.assertEqual(self.store.start_corrections(self.key), 1)
        current, revision = self.claim()
        self.store.content(self.key, key, current, revision, byte_size=7, sha256="a" * 64)
        self.assertEqual(self.store.get_attachments(self.key)[0]["effective_status"], "recognized")
        self.assertEqual(self.store.get_attachments(self.key)[0]["original_finding"], original)
        self.storage(key, current, revision)
        next_intent = self.close(current, revision)
        self.assertNotEqual(next_intent["intent_key"], previous["intent_key"])
        self.assertEqual(self.store.approved_correction(key, "approval-1", "PDF", "synthetic-user", 1000), approval)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(sa.select(corrections.c.state)).scalar_one(), "processed")
        with self.assertRaises(ProcessingError):
            self.store.approved_correction(key, "other", "Mahnung", "synthetic-user", 1000)

    def test_structural_unknown_is_rejected_without_creating_new_revision(self):
        owner, revision = self.claim()
        key = self.finding(owner, revision, status="unknown", category=None, reason="hybrid_profile_mismatch")
        with self.assertRaises(ProcessingError):
            self.store.approved_correction(key, "approval", "ignored", "synthetic-user", 1000)
        self.assertEqual(self.store.get_message(self.key)["revision"], 0)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(sa.select(sa.func.count()).select_from(corrections)).scalar_one(), 0)

    def test_due_selection_and_retry_delay_use_injected_time(self):
        self.assertEqual(self.store.due("inbox"), [self.key])
        owner, revision = self.claim()
        self.assertEqual(self.store.due("inbox"), [])
        self.store.release(self.key, owner, revision, delay=300)
        self.assertEqual(self.store.due("inbox"), [])
        self.now[0] += 300
        self.assertEqual(self.store.due("inbox"), [self.key])

    def test_additive_migration_chain_preserves_old_identity_and_journals(self):
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                for name in ("001_app_metadata.py", "002_security_configuration.py", "003_graph_actions.py", "004_storage_operations.py"):
                    migration(name).upgrade()
                before = connection.execute(sa.text("SELECT instance_id FROM app_metadata")).scalar_one()
                existing = set(sa.inspect(connection).get_table_names())
                version = migration("005_processing.py")
                version.upgrade()
                version.upgrade()
                self.assertEqual(connection.execute(sa.text("SELECT instance_id FROM app_metadata")).scalar_one(), before)
                self.assertEqual(set(sa.inspect(connection).get_table_names()), existing | {"processing_messages", "processing_attachments", "processing_corrections"})
                with self.assertRaises(RuntimeError):
                    version.downgrade()
