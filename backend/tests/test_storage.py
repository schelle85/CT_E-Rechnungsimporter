import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sqlalchemy as sa
from app.storage import store_attachment
from app.storage_files import StorageCollision
from app.storage_plan import StorageError
from app.storage_state import StorageStore, metadata
from test_storage_plan import moment, request


class Crash(BaseException):
    pass


class FilesDouble:
    """Synthetic orchestration only; does not establish any Linux/CIFS property."""
    def __init__(self):
        self.destination_key = "d" * 64
        self.stages, self.targets, self.published = {}, {}, []
        self.failure = None

    def stage(self, name, value, item):
        self.stages[name] = value
        if len(value) != item.byte_size or hashlib.sha256(value).hexdigest() != item.sha256:
            raise StorageError("storage_integrity_failed")
        if self.failure == "stage_crash":
            raise Crash()

    def publish(self, name, target):
        if target in self.targets:
            raise StorageCollision("storage_target_exists")
        if self.failure == "before_rename":
            raise OSError("synthetic uncertain failure")
        self.targets[target] = self.stages.pop(name)
        self.published.append(target)
        if self.failure in ("after_rename", "consumed_crash"):
            if self.failure == "consumed_crash":
                del self.targets[target]
            raise Crash()
        if self.failure == "consumed":
            del self.targets[target]

    def stage_exists(self, name):
        return name in self.stages

    def matches(self, target, item):
        value = self.targets.get(target)
        return value is not None and len(value) == item.byte_size and hashlib.sha256(value).hexdigest() == item.sha256


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = sa.create_engine("sqlite:///" + str(Path(self.temp.name) / "workflow.sqlite"))
        self.addCleanup(self.engine.dispose)
        metadata.create_all(self.engine)
        self.now = [int(moment("2026-11-13T10:00:00Z").timestamp())]
        self.store = StorageStore(self.engine, destination_key="d" * 64, clock=lambda: self.now[0])
        self.files = FilesDouble()
        self.data = b"synthetic content\x00\xff"
        self.item = request(byte_size=len(self.data), sha256=hashlib.sha256(self.data).hexdigest())

    def run_item(self, item=None, data=None):
        return store_attachment(self.store, self.files, item or self.item, self.data if data is None else data)

    def expire(self):
        self.now[0] += self.store.LEASE_SECONDS + 1

    def test_stored_receipt_and_duplicate_do_not_depend_on_dms_retention(self):
        self.files.failure = "consumed"
        self.assertEqual(self.run_item().status, "stored")
        self.assertEqual(self.files.targets, {})
        self.assertEqual(self.run_item(data=b"must not be read again").status, "stored")
        duplicate = request(source_key="other", byte_size=len(self.data), sha256="b" * 64, category="Mahnung")
        self.assertEqual(self.run_item(duplicate, b"not read").status, "duplicate")
        self.assertEqual(len(self.files.published), 1)

    def test_existing_unindexed_file_gets_suffix_without_overwrite(self):
        target = self.item.target(self.item.key[:32])
        self.files.targets[target] = b"pre-existing external file"
        result = self.run_item()
        self.assertEqual(result.status, "stored")
        self.assertNotEqual(target, result.target)
        self.assertEqual(self.files.targets[target], b"pre-existing external file")
        self.assertEqual(self.files.targets[result.target], self.data)
        self.assertEqual(self.store.get(self.item.key)["publication_attempts"], 2)

    def test_crash_after_rename_is_reconciled_without_another_publication(self):
        self.files.failure = "after_rename"
        with self.assertRaises(Crash):
            self.run_item()
        self.assertEqual(self.run_item().status, "busy")
        self.expire()
        self.assertEqual(self.run_item().status, "stored")
        self.assertEqual(len(self.files.published), 1)

    def test_crash_with_immediate_dms_removal_remains_operator_required(self):
        self.files.failure = "consumed_crash"
        with self.assertRaises(Crash):
            self.run_item()
        self.expire()
        self.assertEqual(self.run_item().status, "operator_required")
        self.assertEqual(self.run_item().status, "operator_required")
        self.assertEqual(len(self.files.published), 1)

    def test_uncertain_rename_with_intact_stage_is_not_retried(self):
        self.files.failure = "before_rename"
        self.assertEqual(self.run_item().status, "operator_required")
        self.files.failure = None
        self.assertEqual(self.run_item().status, "operator_required")
        self.assertEqual(self.files.published, [])

    def test_matching_foreign_target_with_stage_present_is_not_our_receipt(self):
        row = self.store.claim(self.item)
        self.files.stage(row["stage_name"], self.data, self.item)
        self.store.begin_publication(self.item.key, row["owner"])
        self.files.targets[row["target"]] = self.data
        self.expire()
        self.assertEqual(self.run_item().status, "operator_required")
        self.assertEqual(self.files.published, [])

    def test_crash_during_staging_can_resume_under_new_owner(self):
        self.files.failure = "stage_crash"
        with self.assertRaises(Crash):
            self.run_item()
        old_name = self.store.get(self.item.key)["stage_name"]
        self.expire()
        self.files.failure = None
        self.assertEqual(self.run_item().status, "stored")
        self.assertIn(old_name, self.files.stages)  # No unsafe cleanup of a stale writer's stage.
        self.assertEqual(len(self.files.published), 1)

    def test_known_rejection_never_becomes_success_after_stage_removal(self):
        self.files.targets[self.item.target(self.item.key[:32])] = self.data
        self.files.targets[self.item.target(self.item.key[:32], collision=True)] = self.data
        self.assertEqual(self.run_item().status, "operator_required")
        self.assertEqual(self.store.get(self.item.key)["publication_rejected"], 1)
        self.files.stages.clear()  # Even later manual cleanup cannot convert known EEXIST to stored.
        self.assertEqual(self.run_item().status, "operator_required")
        self.assertEqual(self.files.published, [])

    def test_failure_to_acknowledge_db_receipt_does_not_republish(self):
        finish = self.store.finish
        def lost_ack(key, owner, state, **kwargs):
            finish(key, owner, state, **kwargs)
            raise Crash()
        with patch.object(self.store, "finish", side_effect=lost_ack):
            with self.assertRaises(Crash):
                self.run_item()
        self.assertEqual(self.run_item().status, "stored")
        self.assertEqual(len(self.files.published), 1)

    def test_invalid_content_fails_before_any_publication(self):
        result = self.run_item(data=b"wrong bytes")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason, "storage_integrity_failed")
        self.assertEqual(self.files.published, [])
        self.files.destination_key = "e" * 64
        self.assertEqual(self.run_item().reason, "storage_destination_conflict")
