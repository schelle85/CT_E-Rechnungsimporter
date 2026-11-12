from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from app.graph import GraphConfig, GraphClient, GraphError
from app.graph_mail import Mailbox, CUTOFF_GRAPH
from app.test_source import ReadOnlyGraphClient, TestBinding, TestSource, download
from app.test_source_cli import execute

CONFIG = GraphConfig("11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "invoice@example.invalid")
BINDING = TestBinding(CONFIG.mailbox, "fixed-test", "fixed-parent")
OLD = {"id": "m1", "parentFolderId": "fixed-test", "receivedDateTime": "2026-01-01T00:00:00Z",
       "flag": {"flagStatus": "notFlagged"}}
ATTACHMENT = {"id": "a1", "name": "../../private.dat", "size": 7, "isInline": True,
              "contentType": "image/png", "@odata.type": "#microsoft.graph.fileAttachment"}


class Remote:
    def __init__(self):
        self.calls, self.override = [], None
        self.folder = {"id": "fixed-test", "parentFolderId": "fixed-parent", "displayName": "Test"}
        self.children = [dict(self.folder)]
        self.messages, self.attachments = [dict(OLD)], [dict(ATTACHMENT)]
        self.raw = b"opaque\x00"

    def __call__(self, request):
        self.calls.append(request)
        if request.method != "GET":
            raise AssertionError("No Graph writes allowed")
        if self.override:
            result = self.override(request)
            if result is not None:
                return result
        path = request.url.path.split("/users/" + CONFIG.mailbox)[-1]
        if path == "/mailFolders/fixed-test":
            return httpx.Response(200, json=self.folder)
        if path == "/mailFolders/fixed-parent":
            return httpx.Response(200, json={"id": "fixed-parent"})
        if path == "/mailFolders/fixed-parent/childFolders":
            return httpx.Response(200, json={"value": self.children})
        if path == "/mailFolders/fixed-test/messages":
            return httpx.Response(200, json={"value": self.messages})
        if path == "/messages/m1":
            return httpx.Response(200, json=self.messages[0])
        if path == "/messages/m1/attachments":
            return httpx.Response(200, json={"value": self.attachments})
        if path == "/messages/m1/attachments/a1/$value":
            return httpx.Response(200, content=self.raw)
        if path == "/mailFolders/inbox":
            return httpx.Response(200, json={"id": "inbox"})
        return httpx.Response(404)


class TestSourceTests(unittest.TestCase):
    def source(self, remote=None):
        remote = remote or Remote()
        transport = httpx.Client(transport=httpx.MockTransport(remote), trust_env=False)
        self.addCleanup(transport.close)
        credential = Mock()
        credential.get_token.return_value = SimpleNamespace(token="synthetic")
        client = ReadOnlyGraphClient(CONFIG, credential, transport, sleep=lambda _: None)
        source = TestSource(client, BINDING)
        self.addCleanup(lambda: self.assertTrue(all(r.method == "GET" for r in remote.calls)))
        return source, remote, credential

    def test_older_mail_only_in_fixed_test_source_productive_guard_unchanged(self):
        source, remote, _ = self.source()
        self.assertEqual(source.messages()[0].id, "m1")
        with source.content("m1", "a1") as stream:
            self.assertEqual(stream.read(), remote.raw)
        productive = Mailbox(source.client)
        with self.assertRaises(GraphError) as error:
            productive.message("m1")
        self.assertEqual(error.exception.code, "graph_before_cutoff")
        self.assertEqual(CUTOFF_GRAPH, "2026-11-30T23:00:00Z")
        for request in remote.calls:
            self.assertNotIn("ignore_cutoff", str(request.url))

    def test_writes_rejected_before_token_or_transport(self):
        source, remote, credential = self.source()
        for method in ("POST", "PATCH", "PUT", "DELETE", "get"):
            with self.subTest(method=method), self.assertRaises(GraphError):
                source.client._json(method, source.client.root + "/messages/m1")
        with self.assertRaises(GraphError):
            source.client._write("POST", source.client.root + "/sendMail", {}, expected=202)
        with self.assertRaises(GraphError):
            source.client._json("GET", source.client.root + "/messages/m1", payload={})
        self.assertEqual(remote.calls, [])
        credential.get_token.assert_not_called()

    def test_binding_file_exact_keys_and_mailbox(self):
        for value in ({"mailbox": CONFIG.mailbox, "folder_id": "fixed-test", "parent_id": "fixed-parent"},
                      {"mailbox": "other@example.invalid", "folder_id": "fixed-test", "parent_id": "fixed-parent"},
                      {"mailbox": CONFIG.mailbox, "folder_id": "fixed-test", "parent_id": "fixed-parent", "ignore_cutoff": True}):
            with patch("app.test_source.protected_bytes", return_value=json.dumps(value).encode()):
                if value.get("mailbox") == CONFIG.mailbox and len(value) == 3:
                    self.assertEqual(TestBinding.load("protected", CONFIG.mailbox), BINDING)
                else:
                    with self.assertRaises(GraphError):
                        TestBinding.load("protected", CONFIG.mailbox)
        source, _, _ = self.source()
        with self.assertRaises(GraphError):
            TestSource(GraphClient(CONFIG, None, None), BINDING)

    def test_missing_renamed_moved_and_ambiguous_folder_fail(self):
        for variant in ("missing", "renamed", "moved", "duplicate", "hidden_duplicate"):
            source, remote, _ = self.source()
            if variant == "missing":
                remote.children = []
            elif variant == "renamed":
                remote.folder["displayName"] = "Invoices"
            elif variant == "moved":
                remote.folder["parentFolderId"] = "other-parent"
            else:
                remote.children.append({"id": "other-test", "displayName": "TEST", "parentFolderId": "fixed-parent"})
            with self.subTest(variant=variant), self.assertRaises(GraphError):
                source.messages()
            self.assertFalse(any(r.url.path.endswith("/messages") for r in remote.calls))

    def test_all_pages_processed_and_foreign_page_targets_rejected(self):
        source, remote, _ = self.source()
        root = source.client.root + "/mailFolders/fixed-test/messages"
        def paging(request):
            if request.url.path.endswith("/fixed-test/messages"):
                if "page" not in request.url.params:
                    return httpx.Response(200, json={"value": [dict(OLD)], "@odata.nextLink": root + "?page=2"})
                return httpx.Response(200, json={"value": [{**OLD, "id": "m2"}]})
        remote.override = paging
        self.assertEqual([m.id for m in source.messages()], ["m1", "m2"])
        for target in ("https://evil.invalid/token", root.replace("invoice%40example.invalid", "foreign%40example.invalid"),
                       source.client.root + "/mailFolders/inbox/messages", source.client.root + "/messages/m1/attachments"):
            source, remote, _ = self.source()
            def bad(request, target=target):
                if request.url.path.endswith("/fixed-test/messages"):
                    return httpx.Response(200, json={"value": [], "@odata.nextLink": target})
            remote.override = bad
            with self.subTest(target=target), self.assertRaises(GraphError) as error:
                source.messages()
            self.assertEqual(error.exception.code, "graph_untrusted_url")

    def test_foreign_messages_inbox_and_nested_folder_rejected(self):
        for parent in ("inbox", "another-folder", "test-child"):
            source, remote, _ = self.source()
            remote.messages[0]["parentFolderId"] = parent
            with self.subTest(parent=parent), self.assertRaises(GraphError):
                with source.content("m1", "a1"):
                    self.fail("No foreign content")
            self.assertFalse(any("attachments" in r.url.path for r in remote.calls))
        source, _, _ = self.source()
        with self.assertRaises(GraphError):
            source.attachments("unknown-message")

    def test_folder_and_attachment_pages_are_fully_read(self):
        source, remote, _ = self.source()
        def pages(request):
            if request.url.path.endswith("/childFolders"):
                if "page" not in request.url.params:
                    return httpx.Response(200, json={"value": [], "@odata.nextLink": source.client.root + "/mailFolders/fixed-parent/childFolders?page=2"})
                return httpx.Response(200, json={"value": remote.children})
            if request.url.path.endswith("/attachments"):
                if "page" not in request.url.params:
                    return httpx.Response(200, json={"value": remote.attachments, "@odata.nextLink": source.client.root + "/messages/m1/attachments?page=2"})
                return httpx.Response(200, json={"value": [{**ATTACHMENT, "id": "a2"}]})
        remote.override = pages
        self.assertEqual([value.id for value in source.attachments("m1")], ["a1", "a2"])

    def test_paging_loop_and_actual_blocking_download_deadline(self):
        source, remote, _ = self.source()
        def loop(request):
            if request.url.path.endswith("/fixed-test/messages"):
                return httpx.Response(200, json={"value": [], "@odata.nextLink": str(request.url)})
        remote.override = loop
        with self.assertRaises(GraphError):
            source.messages()
        source, remote, _ = self.source()
        source.MAX_DOWNLOAD_SECONDS = 0.01
        class Slow(httpx.SyncByteStream):
            def __iter__(self):
                import time
                time.sleep(0.2)
                yield b"slow"
        def slow(request):
            if request.url.path.endswith("/$value"):
                return httpx.Response(200, stream=Slow())
        remote.override = slow
        with self.assertRaises(GraphError) as error:
            with source.content("m1", "a1"):
                self.fail("No partial result")
        self.assertEqual(error.exception.code, "graph_request_deadline")

    def test_parent_rechecked_before_every_attachment_page_and_raw(self):
        source, remote, _ = self.source()
        url = source.client.root + "/messages/m1/attachments"
        def moved_between_pages(request):
            if request.url.path.endswith("/attachments") and "page" not in request.url.params:
                remote.messages[0]["parentFolderId"] = "inbox"
                return httpx.Response(200, json={"value": [], "@odata.nextLink": url + "?page=2"})
        remote.override = moved_between_pages
        with self.assertRaises(GraphError):
            source.attachments("m1")
        self.assertFalse(any("page=2" in str(r.url) for r in remote.calls))
        source, remote, _ = self.source()
        def moved_before_raw(request):
            if request.url.path.endswith("/attachments"):
                remote.messages[0]["parentFolderId"] = "inbox"
        remote.override = moved_before_raw
        with self.assertRaises(GraphError):
            with source.content("m1", "a1"):
                self.fail("No raw fetch after movement")
        self.assertFalse(any(r.url.path.endswith("/$value") for r in remote.calls))

    def test_inline_fake_suffix_is_opaque_byte_copy_with_generated_name(self):
        source, remote, _ = self.source()
        with tempfile.TemporaryDirectory() as directory:
            result = download(source, "m1", "a1", directory)
            path = Path(directory) / "document"
            self.assertEqual(path.read_bytes(), remote.raw)
            self.assertEqual(result["sha256"], sha256(remote.raw).hexdigest())
            self.assertEqual(path.stat().st_mode & 0o777, 0o400)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["document"])

    def test_output_never_overwrites_or_removes_existing_file(self):
        source, _, _ = self.source()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document"
            path.write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                download(source, "m1", "a1", directory)
            self.assertEqual(path.read_bytes(), b"keep")

    def test_limits_and_unsupported_attachments_fail_without_raw(self):
        for field, value in (("size", 25 * 1024 * 1024 + 1), ("@odata.type", "#microsoft.graph.referenceAttachment"),
                             ("@odata.type", "#microsoft.graph.itemAttachment")):
            source, remote, _ = self.source()
            remote.attachments[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(GraphError):
                with source.content("m1", "a1"):
                    self.fail("No raw fetch")
            self.assertFalse(any(r.url.path.endswith("/$value") for r in remote.calls))
        source, _, _ = self.source()
        source.MAX_MESSAGES = 0
        with self.assertRaises(GraphError):
            source.messages()

    def test_raw_limits_ranges_redirects_and_partial_response_fail(self):
        for status, headers in ((206, {}), (200, {"Content-Range": "bytes 0-1/7"}),
                                (302, {"Location": "https://evil.invalid/a"}), (200, {"Content-Length": "100"})):
            source, remote, _ = self.source()
            def bad(request, status=status, headers=headers):
                if request.url.path.endswith("/$value"):
                    return httpx.Response(status, headers=headers, content=b"tiny")
            remote.override = bad
            with self.subTest(status=status, headers=headers), self.assertRaises(GraphError):
                with source.content("m1", "a1"):
                    self.fail("No incomplete result")
        source, _, _ = self.source()
        source.MAX_DOWNLOAD = 3
        with self.assertRaises(GraphError):
            with source.content("m1", "a1"):
                self.fail("No oversized result")

    def test_cli_execution_keeps_output_neutral_and_has_no_actions(self):
        source, remote, _ = self.source()
        @contextmanager
        def client(*_):
            yield source.client
        with tempfile.TemporaryDirectory() as directory, patch("app.test_source_cli.operator_client", client), \
                patch("app.test_source_cli.TestBinding.load", return_value=BINDING):
            result = execute("fetch", "m1", "a1", directory)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["source"], "test")
            for private in ("m1", "a1", "private.dat", "synthetic", "opaque"):
                self.assertNotIn(private, json.dumps(result))
            self.assertEqual((Path(directory) / "document").read_bytes(), remote.raw)

    def test_neutral_case_inventory_and_bounded_ordinal_selection(self):
        source, remote, _ = self.source()
        @contextmanager
        def client(*_):
            yield source.client
        with tempfile.TemporaryDirectory() as directory, patch("app.test_source_cli.operator_client", client), \
                patch("app.test_source_cli.TestBinding.load", return_value=BINDING):
            result = execute("scan", None, None, directory)
            self.assertEqual(result["cases"][0]["attachments"][0]["attachment"], 1)
            self.assertNotIn("m1", str(result))
            self.assertNotIn("private.dat", str(result))
            result = execute("fetch", None, None, directory, 1, 1)
            self.assertTrue(result["ok"], result)
            self.assertEqual((Path(directory) / "document").read_bytes(), remote.raw)
            bad = execute("fetch", None, None, directory, 2, 1)
            self.assertEqual(bad["code"], "graph_test_selection_invalid")


if __name__ == "__main__":
    unittest.main()
