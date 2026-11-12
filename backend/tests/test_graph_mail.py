from datetime import datetime, timezone
import unittest
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


if __name__ == "__main__":
    unittest.main()
