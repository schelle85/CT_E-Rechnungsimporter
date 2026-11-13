"""One bounded processing quantum, shared by inbox and already approved corrections."""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from app.graph import GraphError
from app.graph_actions import GraphActions
from app.graph_mail import Mailbox
from app.processing_graph import JournalMailbox
from app.processing_plan import ProcessingError
from app.storage import StorageResult, store_attachment
from app.storage_plan import StorageError


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    message_key: str
    attachment_key: str | None = None
    owner: str | None = None
    revision: int | None = None
    original_sha256: str | None = None
    byte_size: int | None = None
    reason: str | None = None

    def result(self):
        return asdict(self)


class GraphProcessing:
    def __init__(self, client, actions):
        self.client, self.actions = client, actions
        self.mailbox = client.config.mailbox

    def scan(self):
        return Mailbox(self.client).scan()

    def reader(self, message, attachments):
        return JournalMailbox(self.client, message, attachments)

    def folders(self, guard):
        return self.actions.ensure_folders(guard=guard)

    def finish(self, message, intent, guard):
        self.actions.move(message["graph_id"], intent["destination"], intent_key=intent["intent_key"],
                          source_parent=intent["source_parent"], destination_id=intent["destination_id"], guard=guard)
        if intent["flag_required"]:
            self.actions.flag(message["graph_id"], intent_key=intent["intent_key"], guard=guard)
        current = Mailbox(self.client).message(message["graph_id"])
        if (current.received_at.isoformat() != message["received_at"] or current.parent_id != intent["destination_id"]
                or intent["flag_required"] and current.flag != "flagged"):
            raise ProcessingError("processing_mail_not_observed")
        return current


class ProcessingService:
    def __init__(self, store, graph, storage, files, scope):
        self.store, self.graph, self.storage, self.files, self.scope = store, graph, storage, files, scope
        if files.destination_key != storage.destination_key:
            raise ProcessingError("processing_destination_conflict")

    def scan(self):
        sources = self.graph.scan()  # Complete all paging before registering or causing any writes.
        return [self.store.register(self.graph.mailbox, message, attachments)
                for message, attachments in sources]

    def _input(self, directory, message, rows, row, owner, revision):
        directory = Path(directory)
        info = directory.lstat()
        if (not directory.is_absolute() or not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077):
            raise ProcessingError("processing_exchange_invalid")
        path = directory / "document"
        if path.exists() or path.is_symlink():
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                details = os.fstat(stream.fileno())
                if not stat.S_ISREG(details.st_mode) or details.st_size > 26214400:
                    raise ProcessingError("processing_exchange_invalid")
                checksum, size = hashlib.sha256(), 0
                while chunk := stream.read(65536):
                    size += len(chunk)
                    if size > 26214400:
                        raise ProcessingError("processing_exchange_invalid")
                    checksum.update(chunk)
            if row["raw_sha256"] != checksum.hexdigest() or row["byte_size"] != size:
                raise ProcessingError("processing_exchange_invalid")
            return path
        self.store.active(message["message_key"], owner, revision)
        reader = self.graph.reader(message, rows)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as output, reader.attachment_content(message["graph_id"], row["graph_id"]) as stream:
                checksum, size = hashlib.sha256(), 0
                while chunk := stream.read(65536):
                    size += len(chunk)
                    if size > 26214400:
                        raise ProcessingError("processing_content_limit")
                    checksum.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            self.store.content(message["message_key"], row["attachment_key"], owner, revision,
                               byte_size=size, sha256=checksum.hexdigest())
            return path
        except BaseException:
            # Only this exclusively created opaque exchange file, never a customer original.
            path.unlink(missing_ok=True)
            raise

    def advance(self, key, directory, *, owner=None, revision=None, attachment_key=None, finding=None):
        if owner is None:
            message = self.store.claim(key)
            if message["mode"] != "owned":
                return ProcessingResult(message["mode"], key)
            owner, revision = message["owner"], message["revision"]
        else:
            message = self.store.active(key, owner, revision)
        selected, aid = None, None
        try:
            if finding is not None:
                try:
                    self.store.finding(key, attachment_key, owner, revision, finding)
                except ProcessingError as error:
                    if error.code != "processing_finding_invalid":
                        raise
                    self.store.failed(key, attachment_key, owner, revision, error.code)
                selected = attachment_key
            rows = self.store.get_attachments(key)
            if message["close_key"] is not None:
                return self._finish(message, owner, revision)
            if selected is None:
                pending = [row for row in rows if row["effective_status"] is None or row["effective_status"] == "recognized"
                           and row["storage_state"] not in {"stored", "duplicate", "failed", "operator_required", "busy"}]
                retry = [row for row in rows if row["effective_status"] == "recognized" and row["storage_state"] in {"operator_required", "busy"}
                         and row["effect_state"] != "blocked"]
                if not pending and not retry:
                    return self._finish(message, owner, revision)
                row = (pending or retry)[0]
            else:
                row = next(value for value in rows if value["attachment_key"] == selected)
            aid = row["attachment_key"]
            source = json.loads(row["source"])
            if row["effective_status"] is None and source[5] != "file":
                self.store.ignore(key, aid, owner, revision, "unsupported_attachment_kind")
                self.store.release(key, owner, revision)
                return ProcessingResult("progress", key, aid)
            if row["effective_status"] == "recognized":
                request = self.store.storage_request(message, row, self.scope)
                receipt = self.storage.get(request.key)
                path = None
                if not receipt or receipt["state"] == "pending" and (not receipt["owner"] or receipt["lease_until"] <= int(self.storage.clock())):
                    path = self._input(directory, message, rows, row, owner, revision)
                request = self.store.begin_storage(key, aid, owner, revision, self.scope, self.files.destination_key)
                self.store.active(key, owner, revision, attachment_key=aid, effect_key=request.key)
                if receipt and receipt["state"] in {"stored", "duplicate"}:
                    result = store_attachment(self.storage, self.files, request, None)  # Validate the immutable receipt, no source/file read.
                elif receipt and receipt["state"] in {"publishing", "operator_required"}:
                    self.store.active(key, owner, revision, attachment_key=aid, effect_key=request.key)
                    result = store_attachment(self.storage, self.files, request, None)
                elif receipt and receipt["owner"] and receipt["lease_until"] > int(self.storage.clock()):
                    result = StorageResult(request.key, "busy")
                else:
                    result = store_attachment(self.storage, self.files, request, path)
                self.store.stored(key, aid, owner, revision, result)
                if result.status in {"operator_required", "busy"}:
                    remaining = [value for value in self.store.get_attachments(key) if value["attachment_key"] != aid
                                 and (value["effective_status"] is None or value["effective_status"] == "recognized"
                                      and value["storage_state"] not in {"stored", "duplicate", "failed"} and value["effect_state"] != "blocked")]
                    current = next(value for value in self.store.get_attachments(key) if value["attachment_key"] == aid)
                    blocked = result.status == "operator_required" and current["effect_state"] == "blocked" and not remaining
                    delay = 300 if result.status == "busy" and not remaining else 0
                    self.store.release(key, owner, revision, blocked=blocked, delay=delay, error=result.reason)
                    return ProcessingResult("operator_required" if blocked else "busy" if delay else "progress", key, aid, reason=result.reason)
            elif row["effective_status"] is None:
                path = self._input(directory, message, rows, row, owner, revision)
                current = next(value for value in self.store.get_attachments(key) if value["attachment_key"] == aid)
                return ProcessingResult("classification_required", key, aid, owner, revision,
                                        current["raw_sha256"], current["byte_size"])
            self.store.release(key, owner, revision)
            return ProcessingResult("progress", key, aid)
        except (GraphError, StorageError, ProcessingError, OSError) as error:
            reason = getattr(error, "code", "processing_io_failed")
            if reason in {"processing_owner_conflict", "processing_finding_stale"}:
                raise
            identity_failure = reason in {"graph_before_cutoff", "graph_journal_identity_invalid", "graph_journal_parent_invalid",
                "graph_journal_source_changed", "graph_journal_manifest_changed", "graph_identity_changed", "graph_inbox_changed"}
            rows = self.store.get_attachments(key)
            row = next((value for value in rows if value["attachment_key"] == (selected or aid)), None)
            if row is not None and not row["effect_key"] and not message["close_key"] and not identity_failure:
                self.store.failed(key, row["attachment_key"], owner, revision, reason)
                self.store.release(key, owner, revision, error=reason)
                return ProcessingResult("progress", key, row["attachment_key"], reason=reason)
            if row is not None and row["effect_key"] and not identity_failure:
                self.store.stored(key, row["attachment_key"], owner, revision,
                                  StorageResult(row["effect_key"], "operator_required", reason=reason))
                self.store.release(key, owner, revision, error=reason)
                return ProcessingResult("progress", key, row["attachment_key"], reason=reason)
            transient = isinstance(error, GraphError) and not identity_failure and reason not in {
                "graph_action_operator_required", "graph_invalid_source_folder", "graph_existing_completed_flag", "graph_destination_changed"}
            self.store.release(key, owner, revision, error=reason, blocked=not transient, delay=300 if transient else 0)
            if transient:
                return ProcessingResult("busy", key, reason=reason)
            return ProcessingResult("operator_required", key, reason=reason)

    def _finish(self, message, owner, revision):
        key = message["message_key"]
        guard = lambda: self.store.active(key, owner, revision)
        folders = self.graph.folders(guard)
        intent = self.store.prepare_close(key, owner, revision, folders)
        effect_guard = lambda: self.store.active(key, owner, revision, close_key=intent["intent_key"])
        current = self.graph.finish(message, intent, effect_guard)
        self.store.finish_close(key, owner, revision, parent_id=current.parent_id, flagged=current.flag == "flagged", intent_key=intent["intent_key"])
        return ProcessingResult(intent["outcome"], key)
