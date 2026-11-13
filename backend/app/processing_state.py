"""Additive source/attachment/revision journal. External effects retain their own journals."""
from datetime import datetime
import json
import time
from uuid import uuid4
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from app.processing_plan import (AttachmentOutcome, ProcessingError, attachment_key, checked_finding,
                                 correction_allowed, mail_decision, source_manifest)
from app.storage_plan import StorageRequest, digest

metadata = sa.MetaData()
messages = sa.Table("processing_messages", metadata,
    sa.Column("message_key", sa.String(64), primary_key=True),
    sa.Column("mailbox_key", sa.String(64), nullable=False),
    sa.Column("graph_id", sa.Text, nullable=False),
    sa.Column("received_at", sa.String(40), nullable=False),
    sa.Column("source_parent", sa.Text, nullable=False),
    sa.Column("current_parent", sa.Text, nullable=False),
    sa.Column("manifest_key", sa.String(64), nullable=False),
    sa.Column("signature_hashes", sa.Text, nullable=False),
    sa.Column("state", sa.String(24), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("completed_revision", sa.Integer, nullable=False),
    sa.Column("owner", sa.String(32)),
    sa.Column("lease_until", sa.BigInteger, nullable=False),
    sa.Column("close_key", sa.String(64)),
    sa.Column("close_payload", sa.Text),
    sa.Column("next_attempt", sa.BigInteger, nullable=False),
    sa.Column("error_code", sa.String(64)),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("revision >= 0 AND completed_revision >= -1 AND completed_revision <= revision", name="processing_revision_order"),
    sa.CheckConstraint("state IN ('registered','processing','closing','waiting_correction','done','failed','operator_required')", name="processing_message_state"))

attachments = sa.Table("processing_attachments", metadata,
    sa.Column("attachment_key", sa.String(64), primary_key=True),
    sa.Column("message_key", sa.String(64), sa.ForeignKey("processing_messages.message_key"), nullable=False),
    sa.Column("graph_id", sa.Text, nullable=False),
    sa.Column("source", sa.Text, nullable=False),
    sa.Column("state", sa.String(24), nullable=False),
    sa.Column("raw_sha256", sa.String(64)),
    sa.Column("byte_size", sa.BigInteger),
    sa.Column("signature", sa.SmallInteger, nullable=False),
    sa.Column("original_finding", sa.Text),
    sa.Column("effective_status", sa.String(16)),
    sa.Column("category", sa.String(16)),
    sa.Column("class_owner", sa.String(32)),
    sa.Column("class_revision", sa.Integer),
    sa.Column("effect_key", sa.String(64)),
    sa.Column("effect_payload", sa.Text),
    sa.Column("effect_state", sa.String(16)),
    sa.Column("storage_state", sa.String(24)),
    sa.Column("storage_target", sa.Text),
    sa.CheckConstraint("signature IN (0,1) AND (byte_size IS NULL OR byte_size BETWEEN 0 AND 26214400)", name="processing_attachment_bounds"),
    sa.CheckConstraint("state IN ('pending','classifying','classified')", name="processing_attachment_state"))

corrections = sa.Table("processing_corrections", metadata,
    sa.Column("correction_key", sa.String(64), primary_key=True),
    sa.Column("attachment_key", sa.String(64), sa.ForeignKey("processing_attachments.attachment_key"), unique=True, nullable=False),
    sa.Column("message_key", sa.String(64), sa.ForeignKey("processing_messages.message_key"), nullable=False),
    sa.Column("expected_finding", sa.String(64), nullable=False),
    sa.Column("decision", sa.String(16), nullable=False),
    sa.Column("approved_by", sa.Text, nullable=False),
    sa.Column("approved_at", sa.BigInteger, nullable=False),
    sa.Column("state", sa.String(24), nullable=False),
    sa.Column("applied_revision", sa.Integer),
    sa.CheckConstraint("decision IN ('PDF','Zahlungsavis','Mahnung','ignored')", name="processing_correction_decision"),
    sa.CheckConstraint("state IN ('approved','processing','processed','failed')", name="processing_correction_state"))


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


class ProcessingStore:
    LEASE_SECONDS = 600  # One bounded handoff quantum (<=540s), never an entire multi-attachment mail.

    def __init__(self, engine, clock=time.time):
        self.engine, self.clock = engine, clock

    def get_message(self, key):
        with self.engine.connect() as connection:
            row = connection.execute(sa.select(messages).where(messages.c.message_key == key)).mappings().first()
            return dict(row) if row else None

    def get_attachments(self, key):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(sa.select(attachments).where(
                attachments.c.message_key == key).order_by(attachments.c.attachment_key)).mappings()]

    def register(self, mailbox, message, values, *, signature_hashes=()):
        snapshot = source_manifest(mailbox, message, values)
        for value in signature_hashes:
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ProcessingError("processing_signature_policy_invalid")
        key, now = snapshot["message_key"], int(self.clock())
        try:
            with self.engine.begin() as connection:
                connection.execute(messages.insert().values(message_key=key, mailbox_key=digest([mailbox.lower()]),
                    graph_id=message.id, received_at=snapshot["received_at"], source_parent=message.parent_id,
                    current_parent=message.parent_id, manifest_key=snapshot["manifest_key"],
                    signature_hashes=encoded(sorted(set(signature_hashes))), state="registered", revision=0,
                    completed_revision=-1, lease_until=0, next_attempt=now, created_at=now, updated_at=now))
                for value in snapshot["attachments"]:
                    connection.execute(attachments.insert().values(attachment_key=attachment_key(mailbox, message.id, value[0]),
                        message_key=key, graph_id=value[0], source=encoded(value), state="pending", signature=0))
        except IntegrityError:
            row = self.get_message(key)
            if (not row or row["manifest_key"] != snapshot["manifest_key"] or row["received_at"] != snapshot["received_at"]
                    or row["graph_id"] != message.id or row["current_parent"] != message.parent_id):
                raise ProcessingError("processing_source_conflict") from None
        return key

    def _message(self, connection, key):
        return dict(connection.execute(sa.select(messages).where(messages.c.message_key == key).with_for_update()).mappings().one())

    def _owned(self, connection, key, owner, revision):
        row = self._message(connection, key)
        if row["owner"] != owner or row["revision"] != revision or row["lease_until"] <= int(self.clock()):
            raise ProcessingError("processing_owner_conflict")
        return row

    def _write(self, connection, table, column, key, values, message_key, owner, revision):
        guards = (messages.c.message_key == message_key, messages.c.owner == owner,
                  messages.c.revision == revision, messages.c.lease_until > int(self.clock()))
        guard = sa.and_(*guards) if table is messages else sa.exists(sa.select(messages.c.message_key).where(*guards))
        result = connection.execute(table.update().where(column == key, guard).values(**values))
        if result.rowcount != 1:
            raise ProcessingError("processing_owner_conflict")

    def claim(self, key):
        now, owner = int(self.clock()), uuid4().hex
        with self.engine.begin() as connection:
            row = self._message(connection, key)
            if row["completed_revision"] == row["revision"] or row["state"] == "operator_required":
                return dict(row, mode="idle")
            if row["owner"] and row["lease_until"] > now:
                return dict(row, mode="busy")
            changes = dict(owner=owner, lease_until=now + self.LEASE_SECONDS, state="closing" if row["close_key"] else "processing", updated_at=now)
            result = connection.execute(messages.update().where(messages.c.message_key == key,
                messages.c.owner == row["owner"], messages.c.lease_until == row["lease_until"],
                messages.c.revision == row["revision"]).values(**changes))
            return dict(row, **changes, mode="owned") if result.rowcount == 1 else dict(row, mode="busy")

    def release(self, key, owner, revision, *, error=None, blocked=False, delay=0):
        with self.engine.begin() as connection:
            row = self._owned(connection, key, owner, revision)
            self._write(connection, messages, messages.c.message_key, key,
                dict(owner=None, lease_until=0, error_code=error, next_attempt=int(self.clock()) + delay,
                     state="operator_required" if blocked else ("closing" if row["close_key"] else "processing"),
                     updated_at=int(self.clock())), key, owner, revision)

    def _attachment(self, connection, message_key, key):
        row = connection.execute(sa.select(attachments).where(attachments.c.attachment_key == key,
            attachments.c.message_key == message_key).with_for_update()).mappings().one()
        return dict(row)

    def content(self, message_key, key, owner, revision, *, byte_size, sha256, signature=False):
        if (type(byte_size) is not int or not 0 <= byte_size <= 26214400 or not isinstance(sha256, str)
                or len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256)):
            raise ProcessingError("processing_content_invalid")
        with self.engine.begin() as connection:
            message = self._owned(connection, message_key, owner, revision)
            row = self._attachment(connection, message_key, key)
            if row["raw_sha256"] is not None and (row["raw_sha256"] != sha256 or row["byte_size"] != byte_size):
                raise ProcessingError("processing_content_changed")
            source = json.loads(row["source"])
            if signature and not (source[4] and (source[3] or "").lower().startswith("image/") and sha256 in json.loads(message["signature_hashes"])):
                raise ProcessingError("processing_signature_unconfirmed")
            if row["original_finding"] is not None:
                return  # A fresh content verification cannot reset a finding/manual decision.
            self._write(connection, attachments, attachments.c.attachment_key, key,
                dict(raw_sha256=sha256, byte_size=byte_size, signature=int(signature), state="classifying",
                     class_owner=owner, class_revision=revision), message_key, owner, revision)

    def finding(self, message_key, key, owner, revision, value):
        with self.engine.begin() as connection:
            self._owned(connection, message_key, owner, revision)
            row = self._attachment(connection, message_key, key)
            if row["class_owner"] != owner or row["class_revision"] != revision:
                raise ProcessingError("processing_finding_stale")
            value = checked_finding(value, row["raw_sha256"])
            if row["original_finding"] is not None and row["original_finding"] != encoded(value):
                raise ProcessingError("processing_finding_conflict")
            self._write(connection, attachments, attachments.c.attachment_key, key,
                dict(state="classified", original_finding=encoded(value), effective_status=value["status"], category=value["category"],
                     class_owner=None, class_revision=None), message_key, owner, revision)

    def ignore(self, message_key, key, owner, revision, reason):
        with self.engine.begin() as connection:
            self._owned(connection, message_key, owner, revision)
            row = self._attachment(connection, message_key, key)
            if row["original_finding"] is not None:
                raise ProcessingError("processing_finding_conflict")
            self._write(connection, attachments, attachments.c.attachment_key, key,
                dict(state="classified", original_finding=encoded({"status": "ignored", "category": None, "reason": reason,
                     "method": "source_policy"}), effective_status="ignored"), message_key, owner, revision)

    def begin_storage(self, message_key, key, owner, revision, scope, destination_key):
        with self.engine.begin() as connection:
            message = self._owned(connection, message_key, owner, revision)
            row = self._attachment(connection, message_key, key)
            if row["effective_status"] != "recognized" or row["raw_sha256"] is None:
                raise ProcessingError("processing_not_recognized")
            source = json.loads(row["source"])
            request = StorageRequest(scope, key, source[1], row["byte_size"], row["raw_sha256"],
                                     datetime.fromisoformat(message["received_at"]), row["category"])
            payload = encoded({"request": request.immutable, "source_key": key, "destination_key": destination_key})
            if row["effect_key"] and (row["effect_key"] != request.key or row["effect_payload"] != payload):
                raise ProcessingError("processing_storage_conflict")
            self._write(connection, attachments, attachments.c.attachment_key, key,
                dict(effect_key=request.key, effect_payload=payload, effect_state=row["effect_state"] or "reserved"),
                message_key, owner, revision)
            return request

    def stored(self, message_key, key, owner, revision, result):
        with self.engine.begin() as connection:
            self._owned(connection, message_key, owner, revision)
            row = self._attachment(connection, message_key, key)
            if result.action_key != row["effect_key"] or result.status not in {"stored", "duplicate", "failed", "busy", "operator_required"}:
                raise ProcessingError("processing_storage_conflict")
            if row["effect_state"] == "done" and row["storage_state"] != result.status:
                raise ProcessingError("processing_storage_conflict")
            state = "reserved" if result.status == "busy" else "uncertain" if result.status == "operator_required" else "done"
            self._write(connection, attachments, attachments.c.attachment_key, key,
                dict(effect_state=state, storage_state=result.status, storage_target=result.target), message_key, owner, revision)

    def prepare_close(self, key, owner, revision, folders):
        with self.engine.begin() as connection:
            message = self._owned(connection, key, owner, revision)
            rows = [dict(row) for row in connection.execute(sa.select(attachments).where(attachments.c.message_key == key)).mappings()]
            outcome = mail_decision(AttachmentOutcome(row["effective_status"] or "pending", row["category"], row["storage_state"]) for row in rows)
            if outcome.destination is None:
                raise ProcessingError("processing_effect_uncertain")
            destination_id = folders.get(outcome.destination)
            if not isinstance(destination_id, str) or not destination_id:
                raise ProcessingError("processing_destination_missing")
            payload = {"destination": outcome.destination, "destination_id": destination_id,
                       "outcome": outcome.state, "source_parent": message["current_parent"],
                       "flag_required": sum(not row["signature"] for row in rows) > 1, "revision": revision}
            if message["close_payload"]:
                if json.loads(message["close_payload"]) != payload:
                    raise ProcessingError("processing_close_conflict")
                return dict(payload, intent_key=message["close_key"])
            effect = digest([key, revision, payload])
            self._write(connection, messages, messages.c.message_key, key,
                dict(close_key=effect, close_payload=encoded(payload), state="closing", updated_at=int(self.clock())), key, owner, revision)
            return dict(payload, intent_key=effect)

    def finish_close(self, key, owner, revision, *, parent_id, flagged, intent_key):
        with self.engine.begin() as connection:
            message = self._owned(connection, key, owner, revision)
            if message["close_key"] != intent_key or not message["close_payload"]:
                raise ProcessingError("processing_close_conflict")
            payload = json.loads(message["close_payload"])
            if parent_id != payload["destination_id"]:
                raise ProcessingError("processing_move_not_observed")
            if payload["flag_required"] and not flagged:
                raise ProcessingError("processing_flag_not_observed")
            self._write(connection, messages, messages.c.message_key, key,
                dict(state=payload["outcome"], current_parent=parent_id, completed_revision=revision,
                     owner=None, lease_until=0, updated_at=int(self.clock())), key, owner, revision)
            pending = connection.execute(sa.select(corrections).where(corrections.c.message_key == key,
                corrections.c.applied_revision == revision, corrections.c.state == "processing")).mappings().all()
            for correction in pending:
                row = self._attachment(connection, key, correction["attachment_key"])
                state = "processed" if row["effective_status"] == "ignored" or row["storage_state"] in {"stored", "duplicate"} else "failed"
                connection.execute(corrections.update().where(corrections.c.correction_key == correction["correction_key"]).values(state=state))

    def approved_correction(self, attachment_key, approval_id, decision, actor, approved_at):
        """Internal consumption boundary for already approved decisions; no HTTP/GUI approval route."""
        if (decision not in {"PDF", "Zahlungsavis", "Mahnung", "ignored"} or not isinstance(approval_id, str) or not approval_id
                or len(approval_id) > 128 or not isinstance(actor, str) or not actor or len(actor) > 512 or type(approved_at) is not int):
            raise ProcessingError("processing_correction_invalid")
        with self.engine.begin() as connection:
            raw = connection.execute(sa.select(attachments).where(attachments.c.attachment_key == attachment_key)).mappings().one()
            self._message(connection, raw["message_key"])
            row = self._attachment(connection, raw["message_key"], attachment_key)
            finding = json.loads(row["original_finding"]) if row["original_finding"] else {}
            key = digest([attachment_key, approval_id])
            values = dict(correction_key=key, attachment_key=attachment_key, message_key=row["message_key"],
                expected_finding=digest(finding), decision=decision, approved_by=actor, approved_at=approved_at, state="approved")
            previous = connection.execute(sa.select(corrections).where(corrections.c.attachment_key == attachment_key)).mappings().first()
            if previous:
                if any(previous[name] != value for name, value in values.items() if name != "state"):
                    raise ProcessingError("processing_correction_conflict")
                return key
            if row["effective_status"] != "unknown" or not correction_allowed(finding):
                raise ProcessingError("processing_correction_forbidden")
            connection.execute(corrections.insert().values(**values))
            return key

    def start_corrections(self, key):
        now = int(self.clock())
        with self.engine.begin() as connection:
            message = self._message(connection, key)
            if (message["completed_revision"] != message["revision"] or message["owner"]
                    or message["state"] not in {"waiting_correction", "done", "failed"}):
                raise ProcessingError("processing_predecessor_unresolved")
            approved = connection.execute(sa.select(corrections).where(corrections.c.message_key == key,
                corrections.c.state == "approved", corrections.c.approved_at <= now).with_for_update()).mappings().all()
            if not approved:
                return None
            revision = message["revision"] + 1
            result = connection.execute(messages.update().where(messages.c.message_key == key, messages.c.owner.is_(None),
                messages.c.revision == message["revision"], messages.c.completed_revision == message["revision"]).values(
                    revision=revision, close_key=None, close_payload=None, state="registered", next_attempt=now, updated_at=now))
            if result.rowcount != 1:
                raise ProcessingError("processing_owner_conflict")
            for item in approved:
                row = self._attachment(connection, key, item["attachment_key"])
                original = json.loads(row["original_finding"])
                if (row["effective_status"] != "unknown" or digest(original) != item["expected_finding"]
                        or not correction_allowed(original) or row["effect_key"]):
                    raise ProcessingError("processing_correction_conflict")
                connection.execute(attachments.update().where(attachments.c.attachment_key == row["attachment_key"]).values(
                    effective_status="ignored" if item["decision"] == "ignored" else "recognized",
                    category=None if item["decision"] == "ignored" else item["decision"]))
                connection.execute(corrections.update().where(corrections.c.correction_key == item["correction_key"]).values(
                    state="processing", applied_revision=revision))
            return revision

    def due(self, mode, *, limit=50):
        if mode not in {"inbox", "corrections"} or type(limit) is not int or not 1 <= limit <= 100:
            raise ProcessingError("processing_selection_invalid")
        now = int(self.clock())
        with self.engine.connect() as connection:
            query = sa.select(messages.c.message_key).where(sa.or_(messages.c.owner.is_(None), messages.c.lease_until <= now))
            if mode == "inbox":
                query = query.where(messages.c.completed_revision < messages.c.revision,
                    messages.c.state != "operator_required", messages.c.next_attempt <= now)
            else:
                query = query.where(messages.c.completed_revision == messages.c.revision, sa.exists(sa.select(corrections.c.correction_key).where(
                    corrections.c.message_key == messages.c.message_key, corrections.c.state == "approved", corrections.c.approved_at <= now)))
            return list(connection.execute(query.order_by(messages.c.created_at, messages.c.message_key).limit(limit)).scalars())
