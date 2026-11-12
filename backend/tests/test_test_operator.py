import importlib.util
from pathlib import Path
import stat
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("test_operator", Path(__file__).parent.parent / "operator" / "run-test-source.py")
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)
IMAGE = "sha256:" + "a" * 64
ENV = {"GRAPH_CONFIG_HOST_FILE": "/protected/graph.json", "GRAPH_CREDENTIAL_HOST_FILE": "/protected/key.pem",
       "TEST_SOURCE_BINDING_HOST_FILE": "/protected/test.json", "TEST_SOURCE_COMPOSE_HOST_FILE": "/protected/compose.test-source.yaml",
       "CLASSIFIER_COMPOSE_HOST_FILE": "/protected/compose.classifier.yaml", "CLASSIFIER_PIN_ENV_HOST_FILE": "/protected/classifier.env"}


class OperatorTests(unittest.TestCase):
    def test_checked_files_require_root_regular_protected_absolute(self):
        class Info:
            st_mode = stat.S_IFREG | 0o640
            st_uid = 0
        with patch.object(Path, "lstat", return_value=Info()):
            self.assertEqual(operator.checked_file("/protected/file"), "/protected/file")
            with self.assertRaises(ValueError):
                operator.checked_file("relative")
            for mode, uid in ((stat.S_IFLNK | 0o777, 0), (stat.S_IFREG | 0o644, 0), (stat.S_IFREG | 0o600, 10001)):
                item = Info()
                item.st_mode, item.st_uid = mode, uid
                with patch.object(Path, "lstat", return_value=item), self.assertRaises(ValueError):
                    operator.checked_file("/protected/file")

    def test_sequential_handoff_exact_file_and_cleanup(self):
        calls, roots = [], []
        def invoke(arguments, environment, timeout):
            calls.append(arguments)
            root = Path(environment["TEST_SOURCE_OUTPUT_HOST_DIR"])
            roots.append(root)
            if len(calls) == 1:
                self.assertIn("compose.test-source.yaml", str(arguments))
                self.assertEqual(arguments[-5:], ["fetch", "--case", "1", "--attachment", "1"])
                document = root / "document"
                document.write_bytes(b"opaque")
                document.chmod(0o400)
                return 0, {"ok": True, "source": "test"}
            self.assertIn("compose.classifier.yaml", str(arguments))
            self.assertEqual(environment["CLASSIFIER_INPUT_HOST_FILE"], str(root / "document"))
            return 0, {"status": "ignored", "category": None, "reason": "unsupported_attachment"}
        with patch.dict(operator.os.environ, ENV), patch.object(operator.os, "geteuid", return_value=0), \
                patch.object(operator.os, "chown"), patch.object(operator, "checked_file", side_effect=lambda value: value), \
                patch.object(Path, "read_text", return_value="CLASSIFIER_IMAGE=" + IMAGE), \
                patch.object(operator, "invoke", side_effect=invoke), patch.object(operator.subprocess, "run") as cleanup:
            cleanup.return_value.returncode = 0
            result = operator.operate("fetch", 1, 1, IMAGE, IMAGE)
            self.assertTrue(result["ok"])
            self.assertEqual(len(calls), 2)
            self.assertEqual(cleanup.call_count, 2)
        self.assertTrue(all(not path.exists() for path in roots))

    def test_timeout_still_removes_containers_network_and_private_directory(self):
        roots = []
        def timeout(arguments, environment, seconds):
            roots.append(Path(environment["TEST_SOURCE_OUTPUT_HOST_DIR"]))
            raise subprocess.TimeoutExpired(arguments, seconds)
        with patch.dict(operator.os.environ, ENV), patch.object(operator.os, "geteuid", return_value=0), \
                patch.object(operator.os, "chown"), patch.object(operator, "checked_file", side_effect=lambda value: value), \
                patch.object(Path, "read_text", return_value="CLASSIFIER_IMAGE=" + IMAGE), \
                patch.object(operator, "invoke", side_effect=timeout), patch.object(operator.subprocess, "run") as cleanup:
            cleanup.return_value.returncode = 0
            with self.assertRaises(subprocess.TimeoutExpired):
                operator.operate("fetch", 1, 1, IMAGE, IMAGE)
            self.assertEqual(cleanup.call_count, 2)
        self.assertTrue(all(not path.exists() for path in roots))

    def test_unknown_and_reminder_are_not_rejected_during_handoff(self):
        for finding in ({"status": "unknown", "category": None, "reason": "ambiguous_pdf"},
                        {"status": "recognized", "category": "Mahnung", "reason": "reminder_title_amount_or_reference_date"}):
            def invoke(arguments, environment, timeout):
                if "test-source" in arguments:
                    document = Path(environment["TEST_SOURCE_OUTPUT_HOST_DIR"]) / "document"
                    document.write_bytes(b"opaque")
                    document.chmod(0o400)
                    return 0, {"ok": True}
                return 0, finding
            with self.subTest(finding=finding), patch.dict(operator.os.environ, ENV), \
                    patch.object(operator.os, "geteuid", return_value=0), patch.object(operator.os, "chown"), \
                    patch.object(operator, "checked_file", side_effect=lambda value: value), \
                    patch.object(Path, "read_text", return_value="CLASSIFIER_IMAGE=" + IMAGE), \
                    patch.object(operator, "invoke", side_effect=invoke), patch.object(operator.subprocess, "run") as cleanup:
                cleanup.return_value.returncode = 0
                result = operator.operate("fetch", 1, 1, IMAGE, IMAGE)
                self.assertTrue(result["ok"])
                self.assertEqual((result["status"], result["category"]), (finding["status"], finding["category"]))

    def test_mutable_images_rejected_before_execution(self):
        with patch.object(operator.os, "geteuid", return_value=0), patch.object(operator, "invoke") as invoke:
            with self.assertRaises(ValueError):
                operator.operate("scan", None, None, "latest", IMAGE)
            invoke.assert_not_called()

    def test_failed_docker_cleanup_cannot_report_success(self):
        with patch.dict(operator.os.environ, ENV), patch.object(operator.os, "geteuid", return_value=0), \
                patch.object(operator.os, "chown"), patch.object(operator, "checked_file", side_effect=lambda value: value), \
                patch.object(Path, "read_text", return_value="CLASSIFIER_IMAGE=" + IMAGE), \
                patch.object(operator, "invoke", return_value=(0, {"ok": True})), \
                patch.object(operator.subprocess, "run") as cleanup:
            cleanup.return_value.returncode = 1
            with self.assertRaises(ValueError):
                operator.operate("scan", None, None, IMAGE, IMAGE)


if __name__ == "__main__":
    unittest.main()
