"""Read-only AP02 inbox and attachment operations, with an immutable cutoff."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from tempfile import TemporaryFile
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.graph import GraphError

CUTOFF = datetime(2026, 12, 1, tzinfo=ZoneInfo("Europe/Berlin")).astimezone(timezone.utc)
CUTOFF_GRAPH = "2026-11-30T23:00:00Z"
MESSAGE_SELECT = "id,receivedDateTime,parentFolderId,hasAttachments,flag"
ATTACHMENT_SELECT = "id,name,contentType,size,isInline"


def identifier(value):
    if not isinstance(value, str) or not value or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise GraphError("graph_invalid_identifier")
    return value


def received(value):
    try:
        if not isinstance(value, str):
            raise ValueError()
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise GraphError("graph_invalid_received_time") from None


@dataclass(frozen=True)
class Message:
    id: str
    received_at: datetime
    parent_id: str
    flag: str


@dataclass(frozen=True)
class Attachment:
    id: str
    name: str
    size: int
    content_type: str | None
    inline: bool
    kind: str


class Mailbox:
    MAX_PAGES = 1000
    MAX_MESSAGES = 10000
    MAX_ATTACHMENTS = 1000
    MAX_SCAN_ATTACHMENTS = 20000
    MAX_SCAN_SECONDS = 120
    MAX_DOWNLOAD = 25 * 1024 * 1024
    MAX_DOWNLOAD_SECONDS = 120

    def __init__(self, client):
        self.client = client

    def _pages(self, url, params, limit, started=None):
        started = self.client.clock() if started is None else started
        collection, seen, count, page = url, set(), 0, 0
        while url:
            if url in seen or page >= self.MAX_PAGES or self.client.clock() - started > self.MAX_SCAN_SECONDS:
                raise GraphError("graph_paging_limit")
            self.client._checked_url(url, collection)
            seen.add(url)
            page += 1
            data = self.client._json("GET", url, params=params)
            params = None
            values = data.get("value")
            if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
                raise GraphError("graph_invalid_response")
            count += len(values)
            if count > limit:
                raise GraphError("graph_collection_limit")
            yield from values
            url = data.get("@odata.nextLink")
            if url is not None and (not isinstance(url, str) or not url):
                raise GraphError("graph_invalid_response")
        if self.client.clock() - started > self.MAX_SCAN_SECONDS:
            raise GraphError("graph_paging_limit")

    def inbox_id(self):
        return identifier(self.client._json("GET", self.client.root + "/mailFolders/inbox",
                                           params={"$select": "id"}).get("id"))

    def _parse_message(self, data):
        timestamp = received(data.get("receivedDateTime"))
        if timestamp < CUTOFF:
            raise GraphError("graph_before_cutoff")
        flag_value = data.get("flag")
        flag = flag_value.get("flagStatus") if isinstance(flag_value, dict) else None
        if flag not in ("notFlagged", "flagged", "complete"):
            raise GraphError("graph_invalid_response")
        return Message(identifier(data.get("id")), timestamp, identifier(data.get("parentFolderId")), flag)

    def message(self, message_id):
        message_id = identifier(message_id)
        result = self._parse_message(self.client._json("GET", self.client.root + "/messages/" + quote(message_id, safe=""),
                                                       params={"$select": MESSAGE_SELECT}))
        if result.id != message_id:
            raise GraphError("graph_identity_changed")
        return result

    def messages(self, started=None):
        inbox = self.inbox_id()
        url = self.client.root + "/mailFolders/inbox/messages"
        result = {}
        for data in self._pages(url, {"$select": MESSAGE_SELECT, "$top": "100",
                                      "$filter": "receivedDateTime ge " + CUTOFF_GRAPH,
                                      "$orderby": "receivedDateTime asc"}, self.MAX_MESSAGES, started):
            item = self._parse_message(data)
            if item.parent_id != inbox:
                raise GraphError("graph_inbox_changed")
            old = result.get(item.id)
            if old is not None and old != item:
                raise GraphError("graph_message_changed")
            result[item.id] = item
        return tuple(result.values())

    def attachments(self, message_id, started=None):
        item = self.message(message_id)  # Guard again before *any* direct attachment access.
        if item.parent_id != self.inbox_id():
            raise GraphError("graph_inbox_changed")
        url = self.client.root + "/messages/" + quote(item.id, safe="") + "/attachments"
        result = {}
        for value in self._pages(url, {"$select": ATTACHMENT_SELECT, "$top": "100"}, self.MAX_ATTACHMENTS, started):
            size, inline = value.get("size"), value.get("isInline")
            name, content_type = value.get("name"), value.get("contentType")
            if (type(size) is not int or size < 0 or type(inline) is not bool
                    or not isinstance(name, str) or len(name) > 1024
                    or content_type is not None and (not isinstance(content_type, str) or len(content_type) > 512)):
                raise GraphError("graph_invalid_attachment")
            kind = {"#microsoft.graph.fileAttachment": "file", "#microsoft.graph.itemAttachment": "item",
                    "#microsoft.graph.referenceAttachment": "reference"}.get(value.get("@odata.type"), "unsupported")
            attachment = Attachment(identifier(value.get("id")), name, size, content_type, inline, kind)
            if attachment.id in result and result[attachment.id] != attachment:
                raise GraphError("graph_attachment_changed")
            result[attachment.id] = attachment
        return tuple(result.values())

    def scan(self):
        started = self.client.clock()
        # Materialize message pages completely before following attachments. Never mutate while paging.
        messages = self.messages(started)
        result, count = [], 0
        for message in messages:
            attachments = self.attachments(message.id, started)
            count += len(attachments)
            if count > self.MAX_SCAN_ATTACHMENTS:
                raise GraphError("graph_collection_limit")
            result.append((message, attachments))
        return tuple(result)

    @contextmanager
    def attachment_content(self, message_id, attachment_id):
        """Caller consumes a temporary binary stream. No untrusted name/path or export."""
        attachment_id = identifier(attachment_id)
        values = [v for v in self.attachments(message_id) if v.id == attachment_id]
        if len(values) != 1:
            raise GraphError("graph_attachment_not_found")
        value = values[0]
        if value.kind not in ("file", "item"):
            raise GraphError("graph_attachment_content_unsupported")
        if value.size > self.MAX_DOWNLOAD:
            raise GraphError("graph_download_limit")
        # Recheck immediately before byte retrieval; no caller-supplied timestamp is trusted.
        current = self.message(message_id)
        if current.parent_id != self.inbox_id():
            raise GraphError("graph_inbox_changed")
        url = self.client.root + "/messages/" + quote(current.id, safe="") + "/attachments/" + quote(value.id, safe="") + "/$value"
        started, count = self.client.clock(), 0
        with TemporaryFile(mode="w+b") as output:
            with self.client._response("GET", url) as response:
                header = response.headers.get("Content-Length")
                try:
                    if header is not None and (int(header) < 0 or int(header) > self.MAX_DOWNLOAD):
                        raise GraphError("graph_download_limit")
                except ValueError:
                    raise GraphError("graph_invalid_response") from None
                for chunk in response.iter_bytes(chunk_size=65536):
                    count += len(chunk)
                    if count > self.MAX_DOWNLOAD or self.client.clock() - started > self.MAX_DOWNLOAD_SECONDS:
                        raise GraphError("graph_download_limit")
                    output.write(chunk)
            # Graph attachment.size can include overhead; do not silently equate it to raw byte length.
            output.seek(0)
            yield output
