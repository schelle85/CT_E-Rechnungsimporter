"""Explicit GET-only test-folder source. No production cutoff override or actions."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryFile
from urllib.parse import quote

from app.graph import GraphClient, GraphError, protected_bytes
from app.graph_deadline import request_deadline
from app.graph_mail import Attachment, identifier, received

FOLDER_SELECT = "id,displayName,parentFolderId"
MESSAGE_SELECT = "id,receivedDateTime,parentFolderId"
ATTACHMENT_SELECT = "id,name,contentType,size,isInline"


class ReadOnlyGraphClient(GraphClient):
    @contextmanager
    def _response(self, method, url, *, params=None, payload=None):
        if method != "GET" or payload is not None:
            raise GraphError("graph_test_read_only")
        with super()._response(method, url, params=params) as response:
            yield response

    def _write(self, *args, **kwargs):
        raise GraphError("graph_test_read_only")


@dataclass(frozen=True, repr=False)
class TestBinding:
    mailbox: str
    folder_id: str
    parent_id: str

    def __post_init__(self):
        identifier(self.folder_id)
        identifier(self.parent_id)
        if self.folder_id == self.parent_id or not isinstance(self.mailbox, str):
            raise GraphError("graph_test_binding_invalid")

    @classmethod
    def load(cls, path, mailbox):
        try:
            value = json.loads(protected_bytes(path))
            if not isinstance(value, dict) or set(value) != {"mailbox", "folder_id", "parent_id"}:
                raise ValueError()
            binding = cls(**value)
            if binding.mailbox != mailbox:
                raise ValueError()
            return binding
        except (ValueError, TypeError):
            raise GraphError("graph_test_binding_invalid") from None


@dataclass(frozen=True)
class TestMessage:
    id: str
    parent_id: str
    received_at: datetime


class TestSource:
    MAX_MESSAGES = 50
    MAX_ATTACHMENTS = 100
    MAX_PAGES = 20
    MAX_SCAN_SECONDS = 120
    MAX_DOWNLOAD = 25 * 1024 * 1024
    MAX_DOWNLOAD_SECONDS = 120

    def __init__(self, client, binding):
        if not isinstance(client, ReadOnlyGraphClient) or binding.mailbox != client.config.mailbox:
            raise GraphError("graph_test_binding_invalid")
        self.client, self.binding = client, binding

    def _pages(self, url, params, limit, *, before=None):
        collection, seen, count = url, set(), 0
        started = self.client.clock()
        while url:
            if url in seen or len(seen) >= self.MAX_PAGES or self.client.clock() - started >= self.MAX_SCAN_SECONDS:
                raise GraphError("graph_paging_limit")
            self.client._checked_url(url, collection)
            if before is not None:
                before()
            seen.add(url)
            data = self.client._json("GET", url, params=params)
            params = None
            values = data.get("value")
            if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
                raise GraphError("graph_invalid_response")
            count += len(values)
            if count > limit:
                raise GraphError("graph_collection_limit")
            yield from values
            url = data.get("@odata.nextLink")
            if url is not None and (not isinstance(url, str) or not url):
                raise GraphError("graph_invalid_response")
        if self.client.clock() - started >= self.MAX_SCAN_SECONDS:
            raise GraphError("graph_paging_limit")

    def validate(self):
        binding, root = self.binding, self.client.root
        folder = self.client._json("GET", root + "/mailFolders/" + quote(binding.folder_id, safe=""),
                                   params={"$select": FOLDER_SELECT})
        if (folder.get("id") != binding.folder_id or folder.get("parentFolderId") != binding.parent_id
                or folder.get("displayName") != "Test"):
            raise GraphError("graph_test_folder_changed")
        parent = self.client._json("GET", root + "/mailFolders/" + quote(binding.parent_id, safe=""),
                                   params={"$select": "id"})
        if parent.get("id") != binding.parent_id:
            raise GraphError("graph_test_folder_changed")
        candidates = {}
        url = root + "/mailFolders/" + quote(binding.parent_id, safe="") + "/childFolders"
        for item in self._pages(url, {"$select": FOLDER_SELECT, "$top": "100", "includeHiddenFolders": "true"}, 500):
            name = item.get("displayName")
            if not isinstance(name, str):
                raise GraphError("graph_invalid_response")
            if name.casefold() == "test":
                iid = identifier(item.get("id"))
                if item.get("parentFolderId") != binding.parent_id:
                    raise GraphError("graph_test_folder_changed")
                if iid in candidates and candidates[iid] != item:
                    raise GraphError("graph_test_folder_changed")
                candidates[iid] = item
        if set(candidates) != {binding.folder_id} or candidates[binding.folder_id].get("displayName") != "Test":
            raise GraphError("graph_test_folder_ambiguous")

    def _message(self, data, expected=None):
        item = TestMessage(identifier(data.get("id")), identifier(data.get("parentFolderId")), received(data.get("receivedDateTime")))
        if item.parent_id != self.binding.folder_id:
            raise GraphError("graph_test_message_outside_folder")
        if expected is not None and item.id != expected:
            raise GraphError("graph_identity_changed")
        return item

    def messages(self):
        self.validate()
        url = self.client.root + "/mailFolders/" + quote(self.binding.folder_id, safe="") + "/messages"
        result = {}
        for data in self._pages(url, {"$select": MESSAGE_SELECT, "$top": "50", "$orderby": "receivedDateTime asc"}, self.MAX_MESSAGES, before=self.validate):
            item = self._message(data)
            if item.id in result and result[item.id] != item:
                raise GraphError("graph_message_changed")
            result[item.id] = item
        return tuple(result.values())

    def message(self, message_id):
        self.validate()
        mid = identifier(message_id)
        return self._message(self.client._json("GET", self.client.root + "/messages/" + quote(mid, safe=""),
                                               params={"$select": MESSAGE_SELECT}), mid)

    def attachments(self, message_id):
        message = self.message(message_id)
        url = self.client.root + "/messages/" + quote(message.id, safe="") + "/attachments"
        result = {}
        for item in self._pages(url, {"$select": ATTACHMENT_SELECT, "$top": "100"}, self.MAX_ATTACHMENTS,
                                before=lambda: self.message(message.id)):
            iid, size, inline = identifier(item.get("id")), item.get("size"), item.get("isInline")
            name, content_type = item.get("name"), item.get("contentType")
            if (type(size) is not int or size < 0 or type(inline) is not bool or not isinstance(name, str) or len(name) > 1024
                    or content_type is not None and (not isinstance(content_type, str) or len(content_type) > 512)):
                raise GraphError("graph_invalid_attachment")
            kind = {"#microsoft.graph.fileAttachment": "file", "#microsoft.graph.itemAttachment": "item",
                    "#microsoft.graph.referenceAttachment": "reference"}.get(item.get("@odata.type"), "unsupported")
            value = Attachment(iid, name, size, content_type, inline, kind)
            if iid in result and result[iid] != value:
                raise GraphError("graph_attachment_changed")
            result[iid] = value
        return tuple(result.values())

    @contextmanager
    def content(self, message_id, attachment_id):
        aid = identifier(attachment_id)
        values = [item for item in self.attachments(message_id) if item.id == aid]
        if len(values) != 1:
            raise GraphError("graph_attachment_not_found")
        value = values[0]
        if value.kind != "file":
            raise GraphError("graph_test_attachment_unsupported")
        if value.size > self.MAX_DOWNLOAD:
            raise GraphError("graph_download_limit")
        current = self.message(message_id)  # Recheck folder/parent immediately before raw access.
        url = self.client.root + "/messages/" + quote(current.id, safe="") + "/attachments/" + quote(aid, safe="") + "/$value"
        count, started = 0, self.client.clock()
        with TemporaryFile(mode="w+b") as output:
            with request_deadline(self.MAX_DOWNLOAD_SECONDS):
                with self.client._response("GET", url) as response:
                    if response.status_code != 200 or "Content-Range" in response.headers:
                        raise GraphError("graph_incomplete_attachment")
                    length = response.headers.get("Content-Length")
                    if length is not None:
                        try:
                            length = int(length)
                            if length < 0 or length > self.MAX_DOWNLOAD:
                                raise GraphError("graph_download_limit")
                        except ValueError:
                            raise GraphError("graph_invalid_response") from None
                    for chunk in response.iter_bytes():
                        count += len(chunk)
                        if count > self.MAX_DOWNLOAD or self.client.clock() - started >= self.MAX_DOWNLOAD_SECONDS:
                            raise GraphError("graph_download_limit")
                        output.write(chunk)
                    if length is not None and count != length:
                        raise GraphError("graph_incomplete_attachment")
            output.seek(0)
            yield output


def download(source, message_id, attachment_id, directory):
    """Copy opaque bytes to one generated private filename; no parser import."""
    path = Path(directory) / "document"
    digest, count, created = hashlib.sha256(), 0, False
    try:
        with source.content(message_id, attachment_id) as content:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
            created = True
            with os.fdopen(fd, "wb") as output:
                while chunk := content.read(65536):
                    count += len(chunk)
                    if count > source.MAX_DOWNLOAD:
                        raise GraphError("graph_download_limit")
                    digest.update(chunk)
                    output.write(chunk)
        return {"bytes": count, "sha256": digest.hexdigest()}
    except BaseException:
        # The directory is exclusively owned by this one operation.
        if created and path.is_file() and not path.is_symlink():
            path.unlink()
        raise
