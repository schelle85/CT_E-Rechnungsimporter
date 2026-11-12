from datetime import datetime, timezone
import unittest
from unittest.mock import patch
import httpx
from app.graph import GraphClient, GraphError
from app.graph_mail import Mailbox, CUTOFF, CUTOFF_GRAPH, received
from test_graph import CONFIG, Credential


def message(mid="m1", timestamp="2026-12-01T00:00:00+01:00", parent="inbox", flag="notFlagged"):
    return {"id": mid, "receivedDateTime": timestamp, "parentFolderId": parent,
            "hasAttachments": False, "flag": {"flagStatus": flag}}


def attachment(aid="a1", kind="file", inline=False, size=7, name="../untrusted.pdf"):
    return {"id": aid, "name": name, "size": size, "isInline": inline,
            "contentType": "application/octet-stream", "@odata.type": "#microsoft.graph." + kind + "Attachment"}


class InboxDouble:
    """Synthetic remote state. Every read/write is recorded and can fail independently."""
    def __init__(self):
        self.calls = []
        self.messages = {"m1": message()}
        self.attachments = {"m1": [attachment()]}
        self.raw = b"\x00\x01PDF\xff\n"
        self.override = None

    def __call__(self, request):
        self.calls.append(request)
        if self.override:
            response = self.override(request)
            if response is not None:
                return response
        path = request.url.path.split("/users/invoice@example.invalid")[-1]
        if path == "/mailFolders/inbox":
            return httpx.Response(200, json={"id": "inbox"})
        if path == "/mailFolders/inbox/messages":
            return httpx.Response(200, json={"value": list(self.messages.values())})
        if path.startswith("/messages/"):
            parts = path.split("/")
            mid = parts[2]
            if mid not in self.messages:
                return httpx.Response(404)
            if len(parts) == 3:
                return httpx.Response(200, json=self.messages[mid])
            if len(parts) == 4 and parts[3] == "attachments":
                return httpx.Response(200, json={"value": self.attachments.get(mid, [])})
            if parts[-1] == "$value":
                return httpx.Response(200, content=self.raw)
        raise AssertionError("Unimplemented synthetic endpoint")


class GraphMailTests(unittest.TestCase):
    def mailbox(self, remote=None):
        remote = remote or InboxDouble()
        http = httpx.Client(transport=httpx.MockTransport(remote), trust_env=False)
        self.addCleanup(http.close)
        return Mailbox(GraphClient(CONFIG, Credential(), http, sleep=lambda _: None)), remote

    def test_cutoff_inclusive_and_offsets(self):
        self.assertEqual(CUTOFF.isoformat(), "2026-11-30T23:00:00+00:00")
        for stamp in (CUTOFF_GRAPH, "2026-12-01T00:00:00+01:00", "2026-11-30T18:00:00-05:00"):
            box, remote = self.mailbox()
            remote.messages["m1"] = message(timestamp=stamp)
            self.assertEqual(len(box.scan()), 1)
            query = next(r for r in remote.calls if r.url.path.endswith("/inbox/messages")).url.params
            self.assertEqual(query["$filter"], "receivedDateTime ge 2026-11-30T23:00:00Z")
            self.assertNotIn("body", query["$select"].lower())
        self.assertGreater(received("2026-11-30T23:00:00.000001Z"), CUTOFF)

    def test_old_missing_or_invalid_time_blocks_direct_content(self):
        for stamp in ("2026-11-30T22:59:59.999999Z", "2026-12-01T00:00:00", None, "broken"):
            box, remote = self.mailbox()
            remote.messages["m1"] = message(timestamp=stamp)
            with self.subTest(stamp=stamp), self.assertRaises(GraphError):
                with box.attachment_content("m1", "a1"):
                    self.fail("no old content")
            self.assertEqual(len(remote.calls), 1)
            self.assertFalse(any(r.method != "GET" for r in remote.calls))

    def test_paging_overlap_and_empty_intermediate_page(self):
        box, remote = self.mailbox()
        remote.messages["m2"] = message("m2", "2026-12-02T12:00:00Z")
        url = box.client.root + "/mailFolders/inbox/messages"
        def pages(request):
            if request.url.path.endswith("/inbox/messages"):
                skip = request.url.params.get("$skiptoken")
                if skip is None:
                    return httpx.Response(200, json={"value": [remote.messages["m1"]], "@odata.nextLink": url + "?$skiptoken=opaque%2B1"})
                if skip == "opaque+1":
                    return httpx.Response(200, json={"value": [], "@odata.nextLink": url + "?$skiptoken=opaque%2B2"})
                self.assertEqual(skip, "opaque+2")
                return httpx.Response(200, json={"value": list(remote.messages.values())})
        remote.override = pages
        values = box.scan()
        self.assertEqual([m.id for m, _ in values], ["m1", "m2"])
        self.assertTrue(all(r.headers["Prefer"] == 'IdType="ImmutableId"' for r in remote.calls))

    def test_bad_nextlink_loop_partial_failure_not_complete(self):
        for failure in ("foreign", "mailbox", "collection", "loop", "http"):
            box, remote = self.mailbox()
            url = box.client.root + "/mailFolders/inbox/messages"
            def fail(request):
                if request.url.path.endswith("/inbox/messages"):
                    if request.url.params.get("$skiptoken"):
                        return httpx.Response(403)
                    link = {"foreign": "https://evil.invalid/stolen", "mailbox": url.replace("invoice%40", "other%40"),
                            "collection": box.client.root + "/messages", "loop": url,
                            "http": url + "?$skiptoken=fail"}[failure]
                    return httpx.Response(200, json={"value": [message()], "@odata.nextLink": link})
            remote.override = fail
            with self.subTest(failure=failure), self.assertRaises(GraphError):
                box.scan()
            self.assertTrue(all(r.url.host == "graph.microsoft.com" for r in remote.calls))
            self.assertFalse(any("/attachments" in r.url.path for r in remote.calls))

    def test_inline_only_and_all_attachment_types_paged(self):
        box, remote = self.mailbox()
        values = [attachment("inline", inline=True), attachment("item", kind="item"),
                  attachment("ref", kind="reference"), attachment("future", kind="future")]
        url = box.client.root + "/messages/m1/attachments"
        def pages(request):
            if request.url.path.endswith("/m1/attachments"):
                self.assertNotIn("contentBytes", request.url.params.get("$select", ""))
                if request.url.params.get("$skiptoken"):
                    return httpx.Response(200, json={"value": values[1:]})
                return httpx.Response(200, json={"value": values[:1], "@odata.nextLink": url + "?$skiptoken=next"})
        remote.override = pages
        rows = box.scan()[0][1]
        self.assertEqual([a.kind for a in rows], ["file", "item", "reference", "unsupported"])
        self.assertTrue(rows[0].inline)
        self.assertEqual(rows[0].name, "../untrusted.pdf")

    def test_raw_bytes_file_and_item_no_filename_path(self):
        for kind in ("file", "item"):
            box, remote = self.mailbox()
            remote.attachments["m1"] = [attachment(kind=kind)]
            with box.attachment_content("m1", "a1") as output:
                self.assertEqual(output.read(), remote.raw)
                self.assertIsInstance(output.name, int)
            self.assertTrue(output.closed)

    def test_reference_unsupported_and_oversize_never_download(self):
        for value in (attachment(kind="reference"), attachment(kind="future"), attachment(size=Mailbox.MAX_DOWNLOAD + 1)):
            box, remote = self.mailbox()
            remote.attachments["m1"] = [value]
            with self.assertRaises(GraphError):
                with box.attachment_content("m1", "a1"):
                    self.fail("must refuse")
            self.assertFalse(any(r.url.path.endswith("/$value") for r in remote.calls))

    def test_chunk_download_limit_and_unexpected_encoding(self):
        for encoding in (None, "gzip"):
            box, remote = self.mailbox()
            box.MAX_DOWNLOAD = 16
            def oversized(request):
                if request.url.path.endswith("/$value"):
                    if encoding:
                        return httpx.Response(200, headers={"Content-Encoding": encoding}, content=b"bad-gzip")
                    return httpx.Response(200, content=b"x" * 17)
            remote.override = oversized
            with self.assertRaises(GraphError):
                with box.attachment_content("m1", "a1"):
                    self.fail("no partial download")

    def test_changed_message_attachment_and_collection_limits(self):
        box, remote = self.mailbox()
        remote.messages["m1"]["parentFolderId"] = "elsewhere"
        with self.assertRaises(GraphError):
            box.scan()
        box, remote = self.mailbox()
        box.MAX_MESSAGES = 0
        with self.assertRaises(GraphError):
            box.scan()
        box, remote = self.mailbox()
        remote.attachments["m1"] = [attachment(), attachment(size=8)]
        with self.assertRaises(GraphError):
            box.scan()

    def test_partial_empty_and_broken_stream_close_temporary_file(self):
        from tempfile import TemporaryFile
        class Broken(httpx.SyncByteStream):
            closed = False
            def __iter__(self):
                yield b"partial"
                raise httpx.ReadError("synthetic stream failure")
            def close(self):
                self.closed = True
        for status in (206, 204, "range200", "broken"):
            box, remote = self.mailbox()
            stream = Broken()
            opened = []
            def temporary(*args, **kwargs):
                output = TemporaryFile(*args, **kwargs)
                opened.append(output)
                return output
            def fail(request):
                if request.url.path.endswith("/$value"):
                    if status == "broken":
                        return httpx.Response(200, stream=stream)
                    if status == "range200":
                        return httpx.Response(200, headers={"Content-Range": "bytes 0-2/7"}, content=b"par")
                    return httpx.Response(status, headers={"Content-Range": "bytes 0-2/7"} if status == 206 else {}, content=b"par" if status == 206 else b"")
            remote.override = fail
            with patch("app.graph_mail.TemporaryFile", side_effect=temporary):
                with self.subTest(status=status), self.assertRaises(GraphError) as raised:
                    with box.attachment_content("m1", "a1"):
                        self.fail("never return partial content")
            self.assertTrue(opened and all(output.closed for output in opened))
            self.assertEqual(raised.exception.code, "graph_transport_error" if status == "broken" else "graph_incomplete_attachment")
            if status == "broken":
                self.assertTrue(stream.closed)
                remote.override = None
                with box.attachment_content("m1", "a1") as output:
                    self.assertEqual(output.read(), remote.raw)

    def test_full_200_empty_file_is_valid(self):
        box, remote = self.mailbox()
        remote.raw = b""
        remote.attachments["m1"] = [attachment(size=0)]
        with box.attachment_content("m1", "a1") as output:
            self.assertEqual(output.read(), b"")

    def test_finished_download_does_not_lend_timer_to_caller(self):
        import signal
        box, remote = self.mailbox()
        with box.attachment_content("m1", "a1") as output:
            self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
            self.assertEqual(box.client.probe(), {"mailbox_access": "ok"})
            self.assertEqual(output.read(), remote.raw)

    def test_download_trickle_stops_at_receive_budget_and_closes_stream(self):
        from test_graph_deadline import Trickle
        box, remote = self.mailbox()
        now = [0]
        box.client.clock = lambda: now[0]
        box.MAX_DOWNLOAD_SECONDS = 3
        stream = Trickle(lambda: now.__setitem__(0, now[0] + 1))
        remote.override = lambda r: httpx.Response(200, stream=stream) if r.url.path.endswith("/$value") else None
        with self.assertRaises(GraphError) as raised:
            with box.attachment_content("m1", "a1"):
                self.fail("no partial content")
        self.assertEqual(raised.exception.code, "graph_download_limit")
        self.assertEqual(stream.consumed, 3)
        self.assertTrue(stream.closed)

    def test_rescan_after_partial_page_failure_restarts_complete_scan(self):
        box, remote = self.mailbox()
        remote.messages["m2"] = message("m2", "2026-12-02T12:00:00Z")
        url = box.client.root + "/mailFolders/inbox/messages"
        def fail(request):
            if request.url.path.endswith("/inbox/messages"):
                if request.url.params.get("$skiptoken"):
                    return httpx.Response(403)
                return httpx.Response(200, json={"value": [message()], "@odata.nextLink": url + "?$skiptoken=failed"})
        remote.override = fail
        with self.assertRaises(GraphError):
            box.scan()
        remote.override = None
        self.assertEqual([m.id for m, _ in box.scan()], ["m1", "m2"])

    def test_attachment_failure_after_first_mail_then_fresh_scan(self):
        box, remote = self.mailbox()
        remote.messages["m2"] = message("m2", "2026-12-02T12:00:00Z")
        remote.attachments["m2"] = [attachment("a2")]
        def fail(request):
            if request.url.path.endswith("/m2/attachments"):
                return httpx.Response(403)
        remote.override = fail
        with self.assertRaises(GraphError):
            box.scan()
        self.assertTrue(any(r.url.path.endswith("/m1/attachments") for r in remote.calls))
        remote.override = None
        self.assertEqual([(m.id, [a.id for a in rows]) for m, rows in box.scan()], [("m1", ["a1"]), ("m2", ["a2"])])
        self.assertTrue(all(r.method == "GET" and r.url.host == "graph.microsoft.com" for r in remote.calls))

    def test_changed_final_guard_prevents_raw_access(self):
        for changed in ("old", "moved"):
            box, remote = self.mailbox()
            calls = []
            def change(request):
                if request.url.path.endswith("/messages/m1"):
                    calls.append(request)
                    if len(calls) == 2:
                        return httpx.Response(200, json=message(timestamp="2026-11-30T22:59:59Z") if changed == "old" else message(parent="elsewhere"))
            remote.override = change
            with self.subTest(changed=changed), self.assertRaises(GraphError):
                with box.attachment_content("m1", "a1"):
                    self.fail("no raw access")
            self.assertFalse(any(r.url.path.endswith("/$value") for r in remote.calls))

    def test_conflicting_message_and_all_collection_budgets(self):
        box, remote = self.mailbox()
        remote.override = lambda r: httpx.Response(200, json={"value": [message(), message(flag="flagged")]}) if r.url.path.endswith("/inbox/messages") else None
        with self.assertRaises(GraphError):
            box.scan()
        for attribute in ("MAX_PAGES", "MAX_ATTACHMENTS", "MAX_SCAN_ATTACHMENTS"):
            box, _ = self.mailbox()
            setattr(box, attribute, 0)
            with self.subTest(budget=attribute), self.assertRaises(GraphError):
                box.scan()
        box, _ = self.mailbox()
        ticks = iter([0, 121, 122, 123])
        # _pages must fail before another page when the shared scan clock has expired.
        box.client.clock = lambda: next(ticks, 124)
        with self.assertRaises(GraphError):
            tuple(box._pages(box.client.root + "/mailFolders/inbox/messages", {}, 10, started=0))


if __name__ == "__main__":
    unittest.main()
