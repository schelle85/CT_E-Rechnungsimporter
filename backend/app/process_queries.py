"""Bounded read projections of durable processing state; never claim or mutate work."""
from contextlib import contextmanager
from datetime import date, datetime, time as day_time, timedelta, timezone
import json
import re
import time
from zoneinfo import ZoneInfo
import sqlalchemy as sa
from app.errors import AccessError
from app.processing_plan import correction_allowed
from app.processing_state import attachments, corrections, messages
from app.storage_plan import CATEGORIES, digest
from app.storage_state import operations

BERLIN = ZoneInfo("Europe/Berlin")
STATES = {"registered", "processing", "closing", "waiting_correction", "done", "failed", "operator_required", "unknown"}


def archive_boundary(now):
    local = datetime.fromtimestamp(now, timezone.utc).astimezone(BERLIN)
    try:
        cutoff = local.replace(year=local.year-2)
    except ValueError:
        cutoff = local.replace(year=local.year-2, day=28)
    return int(cutoff.timestamp())


def key_value(key):
    if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
        raise AccessError(404, "Vorgang nicht vorhanden.")
    return key


def finding(row):
    raw = row.get("effective_finding") or row.get("original_finding")
    return json.loads(raw) if raw else None


def day_boundary(value, *, following=False):
    try:
        day = date.fromisoformat(value)
        if following:
            day += timedelta(days=1)
        return datetime.combine(day, day_time.min, BERLIN).astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        raise AccessError(422, "Ungültiger Datumsfilter.") from None


class ProcessQueries:
    def __init__(self, engine, clock=time.time):
        self.engine, self.clock = engine, clock

    @contextmanager
    def snapshot(self):
        with self.engine.connect() as connection:
            if self.engine.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN")
            else:
                connection = connection.execution_options(isolation_level="REPEATABLE READ")
                connection.begin()
            try:
                yield connection
            finally:
                connection.rollback()

    @staticmethod
    def unassigned():
        return sa.and_(attachments.c.effective_status == "unknown",
            ~sa.exists(sa.select(corrections.c.correction_key).where(
                corrections.c.attachment_key == attachments.c.attachment_key)))

    def conditions(self, *, view="active", search="", state=None, category=None, duplicate=None,
                   received_from=None, received_to=None, now=None):
        if view not in {"active", "archive"} or not isinstance(search, str) or len(search) > 200:
            raise AccessError(422, "Ungültiger Filter.")
        if state is not None and state not in STATES or category is not None and category not in CATEGORIES:
            raise AccessError(422, "Ungültiger Filter.")
        if duplicate is not None and type(duplicate) is not bool:
            raise AccessError(422, "Ungültiger Filter.")
        boundary = archive_boundary(self.clock() if now is None else now)
        parts = [messages.c.created_at >= boundary if view == "active" else messages.c.created_at < boundary]
        def has(*criteria):
            return sa.exists(sa.select(attachments.c.attachment_key).where(
                attachments.c.message_key == messages.c.message_key, *criteria).correlate(messages))
        if state:
            parts.append(has(self.unassigned()) if state == "unknown" else messages.c.state == state)
        if category:
            parts.append(has(attachments.c.category == category))
        if duplicate is not None:
            predicate = has(attachments.c.storage_state == "duplicate")
            parts.append(predicate if duplicate else ~predicate)
        if search.strip():
            value = search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
            name = sa.func.json_extract(attachments.c.source, "$[1]")
            if self.engine.dialect.name in {"mysql", "mariadb"}:
                name = sa.func.json_unquote(name)
            pattern = "%" + value + "%"
            parts.append(sa.or_(messages.c.message_key.like(pattern, escape="!"),
                messages.c.error_code.like(pattern, escape="!"),
                has(sa.or_(name.like(pattern, escape="!"), attachments.c.storage_target.like(pattern, escape="!"),
                           attachments.c.category.like(pattern, escape="!")))))
        if received_from:
            parts.append(messages.c.received_at >= day_boundary(received_from))
        if received_to:
            parts.append(messages.c.received_at < day_boundary(received_to, following=True))
        if received_from and received_to and received_from > received_to:
            raise AccessError(422, "Datumsbereich ist umgekehrt.")
        return parts

    @staticmethod
    def page_values(page, page_size):
        if type(page) is not int or not 1 <= page <= 100000 or type(page_size) is not int or not 1 <= page_size <= 50:
            raise AccessError(422, "Ungültige Seitenauswahl.")

    def attachment(self, row, message, approval=None, receipt=None, *, now=None):
        now = self.clock() if now is None else now
        source = json.loads(row["source"])
        current = finding(row)
        original = json.loads(row["original_finding"]) if row["original_finding"] else None
        complete = message["completed_revision"] == message["revision"]
        active = bool(message["owner"] and message["lease_until"] > int(now))
        if row["effective_status"] == "failed" or row["storage_state"] == "failed":
            status = "failed"
        elif row["storage_state"] == "operator_required":
            status = "operator_required"
        elif message["state"] == "operator_required":
            status = "operator_required"
        elif approval and approval["state"] == "approved":
            status = "approved"
        elif row["effective_status"] == "unknown":
            status = "unknown"
        elif complete and (row["effective_status"] == "ignored" or row["storage_state"] in {"stored", "duplicate"}):
            status = "processed"
        elif active or approval and approval["state"] == "processing":
            status = "processing"
        else:
            status = "waiting"
        allowed = (row["effective_status"] == "unknown" and current and correction_allowed(current) and not approval
            and row["raw_sha256"] is not None and complete and not active
            and message["created_at"] >= archive_boundary(now))
        return {
            "id": row["attachment_key"], "message_id": message["message_key"], "name": source[1],
            "kind": source[5], "inline": source[4], "byte_size": row["byte_size"], "sha256": row["raw_sha256"],
            "status": status, "recognition_status": row["effective_status"], "category": row["category"],
            "original_finding": original, "current_finding": current,
            "finding_key": digest(current) if current else None,
            "can_correct": bool(allowed),
            "can_read_original": bool(source[5] == "file" and row["raw_sha256"] is not None and row["byte_size"] is not None),
            "signature_exception": bool(row["signature"]), "storage_state": row["storage_state"],
            "storage_target": row["storage_target"], "error_code": row["error_code"],
            "approval": None if approval is None else {
                "id": approval["correction_key"], "decision": approval["decision"], "actor": approval["approved_by"],
                "approved_at": approval["approved_at"], "state": approval["state"], "applied_revision": approval["applied_revision"]},
            "storage_receipt": None if receipt is None else {
                "id": receipt["action_key"], "state": receipt["state"], "target": receipt["target"],
                "duplicate_of": receipt["duplicate_of"], "dedupe_week": receipt["dedupe_week"],
                "publication_attempts": receipt["publication_attempts"], "collision": bool(receipt["collision"]),
                "error_code": receipt["error_code"], "updated_at": receipt["updated_at"]},
        }

    def related(self, connection, keys):
        rows = [dict(row) for row in connection.execute(sa.select(attachments).where(
            attachments.c.message_key.in_(keys)).order_by(attachments.c.attachment_key)).mappings()]
        approvals = {row["attachment_key"]: dict(row) for row in connection.execute(sa.select(corrections).where(
            corrections.c.message_key.in_(keys))).mappings()}
        return rows, approvals

    def summary(self, row, children, approvals, *, now=None):
        now = self.clock() if now is None else now
        closing = json.loads(row["close_payload"]) if row["close_payload"] else {}
        open_unknown = sum(child["effective_status"] == "unknown" and child["attachment_key"] not in approvals for child in children)
        return {
            "id": row["message_key"], "received_at": row["received_at"], "created_at": row["created_at"],
            "updated_at": row["updated_at"], "state": row["state"], "revision": row["revision"],
            "completed_revision": row["completed_revision"], "archived": row["created_at"] < archive_boundary(now),
            "owner_active": bool(row["owner"] and row["lease_until"] > int(now)),
            "attachment_count": len(children), "unknown_open": open_unknown,
            "duplicate_count": sum(child["storage_state"] == "duplicate" for child in children),
            "stored_count": sum(child["storage_state"] == "stored" for child in children),
            "failed_count": sum(child["effective_status"] == "failed" or child["storage_state"] == "failed" for child in children),
            "categories": sorted({child["category"] for child in children if child["category"]}),
            "names": [json.loads(child["source"])[1] for child in children[:3]],
            "destination": closing.get("destination"), "flag_required": closing.get("flag_required"),
            "mail_action_confirmed": row["completed_revision"] == row["revision"],
            "error_code": row["error_code"], "next_attempt": row["next_attempt"],
        }

    def list(self, *, page=1, page_size=25, **filters):
        self.page_values(page, page_size)
        now = self.clock()
        conditions = self.conditions(now=now, **filters)
        with self.snapshot() as connection:
            total = connection.execute(sa.select(sa.func.count()).select_from(messages).where(*conditions)).scalar_one()
            rows = [dict(row) for row in connection.execute(sa.select(messages).where(*conditions)
                .order_by(messages.c.created_at.desc(), messages.c.message_key).limit(page_size).offset((page-1)*page_size)).mappings()]
            children, approvals = self.related(connection, [row["message_key"] for row in rows]) if rows else ([], {})
            grouped = {row["message_key"]: [] for row in rows}
            for child in children:
                grouped[child["message_key"]].append(child)
            return {"items": [self.summary(row, grouped[row["message_key"]], approvals, now=now) for row in rows],
                    "total": total, "page": page, "page_size": page_size, "synthetic": False}

    def detail(self, key):
        key_value(key)
        now = self.clock()
        with self.snapshot() as connection:
            raw = connection.execute(sa.select(messages).where(messages.c.message_key == key)).mappings().first()
            if raw is None:
                raise AccessError(404, "Vorgang nicht vorhanden.")
            message = dict(raw)
            children, approvals = self.related(connection, [key])
            effect_keys = [row["effect_key"] for row in children if row["effect_key"]]
            receipts = {row["action_key"]: dict(row) for row in connection.execute(sa.select(operations).where(
                operations.c.action_key.in_(effect_keys))).mappings()} if effect_keys else {}
            return {**self.summary(message, children, approvals, now=now), "attachments": [
                self.attachment(row, message, approvals.get(row["attachment_key"]), receipts.get(row["effect_key"]), now=now) for row in children]}

    def unknown(self, *, page=1, page_size=25, view="active", search=""):
        self.page_values(page, page_size)
        now = self.clock()
        conditions = self.conditions(view=view, search=search, now=now)
        with self.snapshot() as connection:
            query = sa.select(attachments.c.attachment_key).join(messages, attachments.c.message_key == messages.c.message_key).where(
                *conditions, self.unassigned())
            total = connection.execute(sa.select(sa.func.count()).select_from(query.subquery())).scalar_one()
            ids = list(connection.execute(query.order_by(messages.c.created_at, attachments.c.attachment_key)
                .limit(page_size).offset((page-1)*page_size)).scalars())
            if not ids:
                return {"items": [], "total": total, "page": page, "page_size": page_size}
            rows = [dict(row) for row in connection.execute(sa.select(attachments).where(attachments.c.attachment_key.in_(ids))).mappings()]
            parents = {row["message_key"]: dict(row) for row in connection.execute(sa.select(messages).where(
                messages.c.message_key.in_({row["message_key"] for row in rows}))).mappings()}
            by_id = {row["attachment_key"]: row for row in rows}
            return {"items": [self.attachment(by_id[key], parents[by_id[key]["message_key"]], now=now) for key in ids],
                    "total": total, "page": page, "page_size": page_size}

    def stats(self, **filters):
        now = self.clock()
        conditions = self.conditions(now=now, **filters)
        with self.snapshot() as connection:
            selected = sa.select(messages.c.message_key).where(*conditions)
            scope = attachments.c.message_key.in_(selected)
            counts = connection.execute(sa.select(sa.func.count().label("attachments"),
                sa.func.coalesce(sa.func.sum(sa.case((self.unassigned(), 1), else_=0)), 0).label("unknown_open"),
                sa.func.coalesce(sa.func.sum(sa.case((attachments.c.storage_state == "duplicate", 1), else_=0)), 0).label("duplicates"),
                sa.func.coalesce(sa.func.sum(sa.case((attachments.c.storage_state == "stored", 1), else_=0)), 0).label("stored"))
                .select_from(attachments).where(scope)).mappings().one()
            total = connection.execute(sa.select(sa.func.count()).select_from(selected.subquery())).scalar_one()
            errors = connection.execute(sa.select(sa.func.count()).select_from(messages).where(
                *conditions, messages.c.state.in_(("failed", "operator_required")))).scalar_one()
            approved = connection.execute(sa.select(sa.func.count()).select_from(corrections).where(
                corrections.c.message_key.in_(selected), corrections.c.state == "approved")).scalar_one()
            return {"messages": total, **dict(counts), "errors": errors, "approved": approved}
