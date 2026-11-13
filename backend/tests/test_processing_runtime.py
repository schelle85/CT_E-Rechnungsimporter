import contextlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import patch
from app.processing_cli import arguments, configuration, select as select_processing
from app.processing_plan import ProcessingError

deployed = Path(__file__).parent.parent / "operator" / "run-processing.py"
location = deployed if deployed.exists() else Path(__file__).resolve().parents[2] / "deploy" / "run-processing.py"
spec = importlib.util.spec_from_file_location("processing_operator", location)
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)
IMAGE = "sha256:" + "a" * 64


class ProcessingRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux", "Actual pipe/process group limits require Linux")
    def test_command_stream_is_bounded_and_timeout_kills_descendants_after_stdout_eof(self):
        script = "import os;os.write(1,b'x'*(2*1024*1024))"
        tracemalloc.start()
        try:
            with patch.object(operator, "DOCKER", [sys.executable, "-c", script]):
                with self.assertRaisesRegex(ValueError, "processing_output_limit"):
                    operator.command([], 5)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 512*1024)
        quiet = "import os;os.write(2,b'e'*(2*1024*1024));print('{}')"
        with patch.object(operator, "DOCKER", [sys.executable, "-c", quiet]):
            self.assertEqual(operator.command([], 5, json_output=True), (0, {}))
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "late-effect"
            hanging = ("import os,time;from pathlib import Path;os.close(1);child=os.fork();"
                       "time.sleep(0.4 if child==0 else 10);Path(" + repr(str(marker)) + ").write_text('late')")
            with patch.object(operator, "DOCKER", [sys.executable, "-c", hanging]):
                with self.assertRaises(subprocess.TimeoutExpired):
                    operator.command([], 0.1)
            time.sleep(0.5)
            self.assertFalse(marker.exists())

    def test_cli_refuses_partial_resume_and_config_cannot_override_root_or_cutoff(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for args in (["advance"], ["advance", "--message-key", "a"*64, "--owner", "b"*32],
                         ["select", "--cutoff", "2020-01-01"], ["select", "--limit", "101"]):
                with self.assertRaises(SystemExit):
                    arguments(args)
        good = {"scope": "synthetic", "storage_root": "/importer", "expected_source": "//server/share",
                "staging_name": "_staging", "staging_excluded": True}
        for changed in ({"storage_root": "/"}, {"staging_excluded": False}, {"cutoff": "2020-01-01"}):
            with patch("app.processing_cli.protected_bytes", return_value=json.dumps({**good, **changed}).encode()):
                with self.assertRaises(ProcessingError):
                    configuration("/protected/synthetic.json")

    def test_classifier_command_has_only_one_ro_input_and_cleanup_failure_propagates(self):
        captured = []
        def command(args, timeout, **kwargs):
            captured.append(args)
            if args[:2] == ["image", "inspect"]:
                return IMAGE
            if args[0] == "run":
                return 0, {"status": "ignored"}
            return ""
        with patch.object(operator, "command", side_effect=command):
            runtime = operator.Runtime({}, IMAGE)
            runtime.classifier(PurePosixPath("/private/document"), time.monotonic()+150)
        actual = captured[1]
        self.assertEqual(actual[actual.index("--network")+1], "none")
        self.assertEqual(actual.count("--mount"), 1)
        self.assertEqual(actual[actual.index("--mount")+1], "type=bind,source=/private/document,target=/input/document,readonly")
        self.assertNotIn("--env", actual)
        self.assertNotIn("--group-add", actual)
        with patch.object(operator, "command", side_effect=ValueError()):
            with self.assertRaises(operator.CleanupFailure):
                runtime.cleanup("invoice-processing-synthetic")

    @unittest.skipUnless(sys.platform == "linux", "Actual opaque-file handoff requires Linux user10001")
    def test_handoff_and_classifier_failure_follow_same_journal_path_and_correction_selection(self):
        # Compose the actual service and host handoff; findings injected here, real OCR separately.
        from test_processing import ProcessingServiceTests
        fixture = ProcessingServiceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        specs = [(b"unknown", "unknown", None, "ambiguous_pdf", {}),
                 (b"invoice", "recognized", "PDF", "invoice_fields", {})]
        key = fixture.add_mail("handoff", specs)
        def coordinate(args):
            parsed = arguments(args)
            finding = json.loads((working / "finding.json").read_text()) if parsed.finding else None
            result = fixture.service.advance(parsed.message_key, working, owner=parsed.owner,
                revision=parsed.revision, attachment_key=parsed.attachment_key, finding=finding)
            return {"ok": True, **result.result()}
        def classify(document):
            result = fixture.store.get_message(key)
            row = next(row for row in fixture.store.get_attachments(key) if row["state"] == "classifying")
            status, category, reason = fixture.findings[(result["graph_id"], row["graph_id"])]
            return {"status":status,"category":category,"reason":reason,"method":"pdf_text",
                    "original_sha256":row["raw_sha256"],"rule_version":"ap03-4"}
        for _ in range(2):
            working = fixture.workspace()
            self.assertEqual(operator.handoff(coordinate, classify, key, working)["status"], "progress")
        self.assertEqual(fixture.finish(key).status, "waiting_correction")
        unknown = next(row for row in fixture.store.get_attachments(key) if row["effective_status"] == "unknown")
        fixture.store.approved_correction(unknown["attachment_key"], "approved", "PDF", "synthetic", 1000)
        selected = select_processing(fixture.service, "corrections", 50)
        self.assertEqual(selected["message_keys"], [key])
        self.assertNotIn(key, fixture.store.due("inbox"))
        self.assertIn(key, fixture.store.due("corrections"))
        self.assertEqual(fixture.finish(key).status, "done")
        self.assertNotIn(key, fixture.store.due("corrections"))
        # A runtime classifier failure is persisted against the correct source, then safely routed.
        key = fixture.add_mail("timeout", [(b"opaque", "recognized", "PDF", "invoice_fields", {})])
        working = fixture.workspace()
        def unavailable(_):
            raise subprocess.TimeoutExpired("synthetic-classifier", 150)
        self.assertEqual(operator.handoff(coordinate, unavailable, key, working)["status"], "progress")
        self.assertEqual(fixture.finish(key).status, "failed")
        failed = fixture.store.get_attachments(key)[0]
        self.assertEqual(json.loads(failed["original_finding"])["reason"], "processing_classifier_unavailable")

