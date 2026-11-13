import hashlib
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import httpx
import sqlalchemy as sa
from app.graph import GraphClient
from app.graph_actions import GraphActions
from app.graph_state import ActionStore, metadata as graph_metadata
from app.processing import GraphProcessing, ProcessingService
from app.processing_plan import ProcessingError
from app.processing_state import ProcessingStore, metadata as processing_metadata
from app.storage_state import StorageStore, metadata as storage_metadata
from test_graph import CONFIG, Credential
from test_graph_actions import ActionRemote
from test_graph_mail import attachment, message
from test_storage import Crash, FilesDouble


class PathFiles(FilesDouble):
    def stage(self, name, value, item):
        return super().stage(name, Path(value).read_bytes(), item)


@unittest.skipUnless(sys.platform == "linux", "Real opaque-file handling requires Linux; no Windows syscall substitute")
class ProcessingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = sa.create_engine("sqlite:///" + str(self.root / "pipeline.sqlite"))
        self.addCleanup(self.engine.dispose)
        for metadata in (processing_metadata, storage_metadata, graph_metadata):
            metadata.create_all(self.engine)
        self.now = [1000]
        self.store = ProcessingStore(self.engine, clock=lambda: self.now[0])
        self.files = PathFiles()
        self.storage = StorageStore(self.engine, destination_key=self.files.destination_key, clock=lambda: self.now[0])
        self.remote = ActionRemote()
        self.remote.messages, self.remote.attachments = {}, {}
        self.contents, self.findings = {}, {}
        self.remote.override = self.respond
        self.http = httpx.Client(transport=httpx.MockTransport(self.remote), trust_env=False)
        self.addCleanup(self.http.close)
        client = GraphClient(CONFIG, Credential(), self.http, sleep=lambda _: None)
        self.graph = GraphProcessing(client, GraphActions(client, ActionStore(self.engine, clock=lambda: self.now[0])))
        self.service = ProcessingService(self.store, self.graph, self.storage, self.files, "synthetic-processing")
        self.sequence = 0

    def respond(self, request):
        path = request.url.path
        if path.endswith("/mailFolders/inbox/messages"):
            return httpx.Response(200, json={"value": [item for item in self.remote.messages.values() if item["parentFolderId"] == "inbox"]})
        if path.endswith("/$value"):
            parts = path.split("/")
            value = self.contents[(parts[-4], parts[-2])]
            return httpx.Response(503) if value is None else httpx.Response(200, content=value)

    def add_mail(self, mid, specs):
        self.remote.messages[mid] = message(mid=mid)
        self.remote.attachments[mid] = []
        for index, (data, status, category, reason, options) in enumerate(specs):
            aid = "a" + str(index)
            value = attachment(aid, size=999, name=mid + "-" + aid + ".pdf", inline=options.get("inline", False))
            value.update({key: item for key, item in options.items() if key != "inline"})
            self.remote.attachments[mid].append(value)
            self.contents[(mid, aid)] = data
            self.findings[(mid, aid)] = (status, category, reason)
        keys = self.service.scan()
        return next(key for key in keys if self.store.get_message(key)["graph_id"] == mid)

    def workspace(self):
        self.sequence += 1
        directory = self.root / ("exchange-" + str(self.sequence))
        directory.mkdir(mode=0o700)
        return directory

    def first_step(self, key):
        directory = self.workspace()
        return self.service.advance(key, directory), directory

    def submit(self, key, result, directory, *, override=None):
        row = next(value for value in self.store.get_attachments(key) if value["attachment_key"] == result.attachment_key)
        mid = self.store.get_message(key)["graph_id"]
        status, category, reason = self.findings[(mid, row["graph_id"])]
        finding = {"status": status, "category": category, "reason": reason, "method": "pdf_text",
                   "original_sha256": result.original_sha256, "rule_version": "ap03-4"}
        finding.update(override or {})
        return self.service.advance(key, directory, owner=result.owner, revision=result.revision,
                                    attachment_key=result.attachment_key, finding=finding)

    def finish(self, key, limit=20):
        for _ in range(limit):
            result, directory = self.first_step(key)
            if result.status == "classification_required":
                result = self.submit(key, result, directory)
            if result.status not in {"progress", "classification_required"}:
                return result
        self.fail("Bounded test did not finish")

    def test_unknown_sibling_does_not_block_storage_and_correction_reuses_receipts_after_move(self):
        key = self.add_mail("m1", [(b"unknown", "unknown", None, "ambiguous_pdf", {}),
                                  (b"invoice-xml", "recognized", "E-Rechnung", "invoice_xml_structure", {})])
        self.assertEqual(self.finish(key).status, "waiting_correction")
        self.assertEqual(len(self.files.published), 1)
        rows = self.store.get_attachments(key)
        unknown = next(row for row in rows if row["effective_status"] == "unknown")
        stored = next(row for row in rows if row["storage_state"] == "stored")
        original = unknown["original_finding"]
        # A consumed successful sibling must not be downloaded or invalidated during correction.
        self.remote.attachments["m1"] = [item for item in self.remote.attachments["m1"] if item["id"] != stored["graph_id"]]
        self.files.targets.clear()
        self.store.approved_correction(unknown["attachment_key"], "approved", "PDF", "synthetic-user", 1000)
        self.store.start_corrections(key)
        self.assertEqual(self.finish(key).status, "done")
        self.assertEqual(self.remote.messages["m1"]["parentFolderId"], "folder-Nachfragen")
        self.assertEqual(self.remote.messages["m1"]["flag"]["flagStatus"], "flagged")
        self.assertEqual(len(self.files.published), 2)
        after = next(row for row in self.store.get_attachments(key) if row["attachment_key"] == unknown["attachment_key"])
        self.assertEqual(after["original_finding"], original)

    def test_inline_image_default_needs_finding_and_no_hashlist_configuration(self):
        for index, (status, category, reason, expected_flag, publications) in enumerate((
                ("ignored", None, "unsupported_attachment", "notFlagged", 1),
                ("recognized", "PDF", "invoice_fields", "flagged", 2),
                ("unknown", None, "ambiguous_pdf", "flagged", 1))):
            mid = "signature" + str(index)
            key = self.add_mail(mid, [(b"invoice", "recognized", "PDF", "invoice_fields", {}),
                (b"image-or-document", status, category, reason, {"inline": True, "contentType": "image/png"})])
            before = len(self.files.published)
            result = self.finish(key)
            self.assertIn(result.status, {"done", "waiting_correction"})
            self.assertEqual(self.remote.messages[mid]["flag"]["flagStatus"], expected_flag)
            self.assertEqual(len(self.files.published) - before, publications)

    def test_download_error_at_each_position_is_local_and_siblings_are_stored(self):
        for bad in range(3):
            specs = [(None if index == bad else b"valid-data", "recognized", "PDF", "invoice_fields", {}) for index in range(3)]
            key = self.add_mail("failure" + str(bad), specs)
            before = len(self.files.published)
            self.assertEqual(self.finish(key).status, "failed")
            self.assertEqual(len(self.files.published) - before, 2)
            self.assertEqual(self.remote.messages["failure" + str(bad)]["parentFolderId"], "folder-Failed")
            failed = next(row for row in self.store.get_attachments(key) if row["effective_status"] == "failed")
            self.assertTrue(failed["error_code"])

    def test_stored_receipt_is_checked_before_missing_source_and_dms_file(self):
        key = self.add_mail("m1", [(b"invoice", "recognized", "PDF", "invoice_fields", {})])
        request, directory = self.first_step(key)
        with patch.object(self.store, "stored", side_effect=Crash()):
            with self.assertRaises(Crash):
                self.submit(key, request, directory)
        downloads = sum(call.url.path.endswith("/$value") for call in self.remote.calls)
        self.remote.attachments["m1"] = []
        self.files.targets.clear()
        self.now[0] += 601
        self.assertEqual(self.finish(key).status, "done")
        self.assertEqual(sum(call.url.path.endswith("/$value") for call in self.remote.calls), downloads)
        self.assertEqual(len(self.files.published), 1)

    def test_crash_after_move_and_flag_resumes_in_target_without_republication(self):
        key = self.add_mail("m1", [(b"first", "recognized", "PDF", "invoice_fields", {}),
                                  (b"second", "recognized", "Mahnung", "reminder_title", {})])
        with patch.object(self.store, "finish_close", side_effect=Crash()):
            with self.assertRaises(Crash):
                self.finish(key)
        writes = len(self.remote.writes)
        self.now[0] += 601
        self.remote.attachments["m1"] = []
        self.files.targets.clear()
        self.assertEqual(self.finish(key).status, "done")
        self.assertEqual(len(self.remote.writes), writes)
        self.assertEqual(len(self.files.published), 2)
        self.assertEqual(self.remote.messages["m1"]["flag"]["flagStatus"], "flagged")

    def test_uncertain_consumed_publication_never_becomes_a_failed_move_or_replay(self):
        key = self.add_mail("m1", [(b"invoice", "recognized", "PDF", "invoice_fields", {})])
        request, directory = self.first_step(key)
        self.files.failure = "consumed_crash"
        with self.assertRaises(Crash):
            self.submit(key, request, directory)
        self.files.failure = None
        self.now[0] += 601
        self.assertEqual(self.finish(key).status, "operator_required")
        self.assertEqual(len(self.files.published), 1)
        self.assertEqual(self.remote.writes, [])
        self.assertEqual(self.remote.messages["m1"]["parentFolderId"], "inbox")

    def test_delayed_classifier_response_after_takeover_is_rejected(self):
        key = self.add_mail("m1", [(b"invoice", "recognized", "PDF", "invoice_fields", {})])
        old, old_directory = self.first_step(key)
        self.now[0] += 601
        current, directory = self.first_step(key)
        with self.assertRaises(ProcessingError):
            self.submit(key, old, old_directory)
        self.submit(key, current, directory)
        self.assertEqual(self.finish(key).status, "done")
        self.assertEqual(len(self.files.published), 1)

    def test_bad_classifier_hash_is_a_failed_attachment_without_storage(self):
        key = self.add_mail("m1", [(b"invoice", "recognized", "PDF", "invoice_fields", {})])
        request, directory = self.first_step(key)
        self.submit(key, request, directory, override={"original_sha256": "f" * 64})
        self.assertEqual(self.finish(key).status, "failed")
        self.assertEqual(self.files.published, [])

    def test_duplicate_does_not_prevent_new_sibling_storage(self):
        key = self.add_mail("m1", [(b"same-size-1", "recognized", "PDF", "invoice_fields", {"name": "duplicate.pdf"}),
                                  (b"same-size-2", "recognized", "PDF", "invoice_fields", {"name": "duplicate.pdf"}),
                                  (b"new-invoice", "recognized", "E-Rechnung", "invoice_xml_structure", {"name": "fresh.xml"})])
        self.assertEqual(self.finish(key).status, "done")
        self.assertEqual(self.remote.messages["m1"]["parentFolderId"], "folder-unzugeordnet")
        self.assertEqual(len(self.files.published), 2)
        self.assertEqual(sorted(row["storage_state"] for row in self.store.get_attachments(key)), ["duplicate", "stored", "stored"])

    def test_late_reserved_storage_call_after_takeover_cannot_republish(self):
        key = self.add_mail("m1", [(b"invoice", "recognized", "PDF", "invoice_fields", {})])
        request, directory = self.first_step(key)
        paused, resume = threading.Event(), threading.Event()
        failures = []
        from app.storage import store_attachment as actual_storage
        old_thread = None
        def delayed(*args, **kwargs):
            if threading.current_thread() is old_thread:
                paused.set()
                if not resume.wait(15):
                    raise AssertionError("test_release_timeout")
            return actual_storage(*args, **kwargs)
        def old_worker():
            try:
                self.submit(key, request, directory)
            except BaseException as error:
                failures.append(error)
        old_thread = threading.Thread(target=old_worker)
        with patch("app.processing.store_attachment", side_effect=delayed):
            old_thread.start()
            try:
                self.assertTrue(paused.wait(10))
                self.now[0] += 601
                self.assertEqual(self.finish(key).status, "done")
            finally:
                resume.set()
                old_thread.join(15)
        self.assertFalse(old_thread.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], ProcessingError)
        self.assertEqual(failures[0].code, "processing_owner_conflict")
        self.assertEqual(len(self.files.published), 1)
