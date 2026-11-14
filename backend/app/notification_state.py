"""AP07 durable plans: at most one POST permission, never reset a reservation."""
from contextlib import contextmanager
import json
import re
import time
from uuid import UUID, uuid4
import sqlalchemy as sa
from app.notification_schema007 import settings, outbox, monitor
from app.notification_model import (DEFAULTS, NotificationError, Slot, canonical, checked_actor,
    checked_key, checked_settings, identity, make_payload, test_request)
from app.notification_planning import INCIDENT_FIELDS, IncidentSlot, outage_slot
from app.schema import audit

RECEIPT_FIELDS = ("slot_key", "request_id", "actor", "scope_key", "kind", "period_start",
    "period_end", "due_at", "stale_at", "config_version", "plan_revision", "payload_hash",
    "state", "reservations", "reserved_at", "post_started_at", "completed_at", "not_before",
    "error_code", "http_status", "created_at", "updated_at")

class NotificationStore:
    LEASE_SECONDS = 120

    def __init__(self, engine, notification_cipher, instance_id, *, clock=time.time):
        self.engine, self.cipher, self.clock = engine, notification_cipher, clock
        self.instance = str(UUID(instance_id))

    @contextmanager
    def transaction(self):
        # Same tested write boundary as ProcessingStore, without touching its state.
        with self.engine.connect() as c:
            if self.engine.dialect.name == "sqlite":
                c.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                c.begin()
            try:
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    @staticmethod
    def _head(c):
        value = c.execute(sa.select(settings).where(settings.c.singleton == 1).with_for_update()).mappings().first()
        if value is None:
            raise NotificationError("notification_schema_unavailable", 503)
        return dict(value)

    @staticmethod
    def _row(c, key):
        value = c.execute(sa.select(outbox).where(outbox.c.slot_key == checked_key(key)).with_for_update()).mappings().first()
        if value is None:
            raise NotificationError("notification_not_found", 404)
        return dict(value)

    def _encrypt(self, value):
        try:
            return self.cipher.encrypt(canonical(value).encode("ascii")).decode("ascii")
        except Exception:
            raise NotificationError("notification_key_unavailable", 503) from None

    def _decrypt(self, value):
        try:
            result = json.loads(self.cipher.decrypt(value.encode("ascii")))
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except Exception:
            raise NotificationError("notification_payload_unavailable", 503) from None

    @staticmethod
    def receipt(row):
        return {name: row[name] for name in RECEIPT_FIELDS}

    def _configuration(self, row):
        if row["payload_cipher"] is None:
            return dict(DEFAULTS, recipients=[])
        return checked_settings(self._decrypt(row["payload_cipher"]))

    def _log(self, c, actor, action, key, *, revision=None, old_hash=None, new_hash=None):
        fields = [key]
        if revision is not None:
            fields += ["plan_revision:" + str(revision), "old_hash:" + str(old_hash), "new_hash:" + str(new_hash)]
        c.execute(audit.insert().values(occurred_at=int(self.clock()), actor=actor[:256],
            action=action, result="ok", changed_fields=canonical(fields), config_id=None))

    def configuration(self):
        with self.engine.connect() as c:
            row = c.execute(sa.select(settings).where(settings.c.singleton == 1)).mappings().one()
            return dict(version=row["version"], scope_key=row["scope_key"],
                configured=row["payload_cipher"] is not None, settings=self._configuration(row))

    def save_settings(self, expected_version, value, scope, actor):
        config = checked_settings(value)
        actor = checked_actor(actor)
        checked_key(scope)
        if type(expected_version) is not int or expected_version < 0:
            raise NotificationError("notification_version_invalid", 422)
        with self.transaction() as c:
            head = self._head(c)
            if head["version"] != expected_version:
                raise NotificationError("notification_settings_changed")
            if head["scope_key"] is not None and head["scope_key"] != scope:
                raise NotificationError("notification_scope_changed")
            changed = c.execute(settings.update().where(settings.c.singleton == 1,
                settings.c.version == expected_version).values(version=expected_version + 1,
                scope_key=scope, payload_cipher=self._encrypt(config), actor=actor,
                updated_at=int(self.clock())))
            if changed.rowcount != 1:
                raise NotificationError("notification_settings_changed")
            self._log(c, actor, "notification_settings", str(expected_version + 1))
        return self.configuration()

    @staticmethod
    def _scope(head, scope):
        checked_key(scope)
        if head["scope_key"] is not None and head["scope_key"] != scope:
            raise NotificationError("notification_scope_changed")

    def _insert(self, c, key, slot, scope, actor, version, *, request=None, request_fence=None):
        now = int(self.clock())
        c.execute(outbox.insert().values(slot_key=key, request_fence=request_fence,
            request_hash=identity(request) if request is not None else None,
            request_id=request["request_id"] if request is not None else None,
            actor=actor, scope_key=scope, kind=slot.kind, period_start=slot.start,
            period_end=slot.end, due_at=slot.due, stale_at=slot.stale, config_version=version,
            plan_revision=0, payload_cipher=None, payload_hash=None, state="prepared",
            monitor_keys=canonical([]),
            reservations=0, owner=None, lease_until=0, not_before=0,
            created_at=now, updated_at=now))

    def _incident_plan(self,c,scope,slot,config,as_of,now,*,data=None):
        if (not isinstance(slot,IncidentSlot) or type(as_of) is not int
                or not slot.last_seen <= as_of <= now
                or outage_slot(slot.token,slot.observation(),config,as_of) != slot):
            raise NotificationError("notification_incident_plan_invalid",422)
        if data is not None and (not isinstance(data,dict)
                or set(data) != {"source","first_seen","last_seen","count","codes"}
                or data["source"] not in {"api","graph","processing"}
                or any(type(data[name]) is not int for name in ("first_seen","last_seen","count"))
                or (data["first_seen"],data["last_seen"],data["count"],data["codes"])
                    != (slot.first_seen,slot.last_seen,1,[slot.code])):
            raise NotificationError("notification_facts_invalid",422)
        member = dict(key=identity([scope,"incident",slot.token]),token=slot.token,as_of=as_of,
            **{name:getattr(slot,name) for name in INCIDENT_FIELDS})
        source = c.execute(sa.select(monitor).where(monitor.c.monitor_key == member["key"],
            monitor.c.scope_key == scope,monitor.c.kind == "incident").with_for_update()).mappings().first()
        if source is None:
            raise NotificationError("notification_monitor_changed")
        payload = json.loads(source["payload"])
        if (any(payload[name] != member[name] for name in ("episode","first_seen","code","resolved_at"))
                or payload["active"] is not (slot.kind == "outage")
                or not slot.last_seen <= payload["last_seen"] <= now
                or not slot.last_failure <= payload["last_failure"] <= payload["last_seen"]
                or slot.kind == "outage" and now-payload["last_seen"] > 300):
            raise NotificationError("notification_monitor_changed")
        return member,source,payload

    def _write_plan(self, c, row, head, slot, data, as_of, origin, members=()):
        incident = slot.kind in {"outage","recovery"}
        if (len(members) > 100 or len(set(members)) != len(members)
                or incident and len(members) != 1):
            raise NotificationError("notification_members_invalid", 422)
        config = self._configuration(head)
        now = int(self.clock())
        membership = []
        if incident:
            member,_,_ = self._incident_plan(c,row["scope_key"],slot,config,as_of,now,data=data)
            if list(members) != [member["key"]]:
                raise NotificationError("notification_members_invalid",422)
            membership = [member]
        else:
            for member in members:
                checked_key(member)
                if not c.execute(sa.select(monitor.c.monitor_key).where(monitor.c.monitor_key == member,
                        monitor.c.scope_key == row["scope_key"],monitor.c.kind == "incident").with_for_update()).first():
                    raise NotificationError("notification_monitor_changed")
                membership.append(member)
        previous_members = json.loads(row["monitor_keys"])
        if incident and previous_members:
            if (len(previous_members) != 1 or not isinstance(previous_members[0],dict)
                    or any(previous_members[0].get(name) != membership[0][name] for name in
                        ("key","token","episode","first_seen","code","resolved_at"))):
                raise NotificationError("notification_monitor_changed")
        if not config["recipients"]:
            c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"],
                outbox.c.reservations == 0).values(error_code="notification_settings_missing",
                    monitor_keys=canonical(membership)))
            return
        payload = make_payload(slot, row["slot_key"], config, data, as_of, origin=origin)
        digest = identity(payload)
        revision = row["plan_revision"] + int(row["payload_cipher"] is not None or row["config_version"] != head["version"])
        changed = c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"],
            outbox.c.reservations == 0, outbox.c.plan_revision == row["plan_revision"]).values(
            config_version=head["version"], plan_revision=revision,
            payload_cipher=self._encrypt(payload), payload_hash=digest, state="prepared",
            monitor_keys=canonical(membership if incident else sorted(membership)),
            due_at=slot.due, stale_at=slot.stale, error_code=None,
            owner=None, lease_until=0, updated_at=now))
        if changed.rowcount != 1:
            raise NotificationError("notification_plan_changed")
        self._log(c, row["actor"], "notification_plan", row["slot_key"],
            revision=revision, old_hash=row["payload_hash"], new_hash=digest)

    def prepare(self, slot, scope, data, *, expected_version, as_of, origin=None, members=()):
        if type(expected_version) is not int or expected_version < 0:
            raise NotificationError("notification_version_invalid", 422)
        if slot.kind == "test":
            raise NotificationError("notification_test_requires_request", 422)
        now = int(self.clock())
        key = slot.key(self.instance, scope)
        with self.transaction() as c:
            head = self._head(c)
            self._scope(head, scope)
            row = c.execute(sa.select(outbox).where(outbox.c.slot_key == key).with_for_update()).mappings().first()
            if row and row["reservations"]:
                return self.receipt(row)
            if expected_version != head["version"]:
                raise NotificationError("notification_settings_changed")
            config = self._configuration(head)
            enabled = (slot.kind == "certificate" or config.get(
                "outages_enabled" if slot.kind in {"outage", "recovery"} else slot.kind + "_enabled", True))
            newer = slot.kind in {"daily", "weekly"} and c.execute(sa.select(outbox.c.slot_key).where(
                outbox.c.scope_key == scope, outbox.c.kind == slot.kind,
                outbox.c.period_end > slot.end, outbox.c.state != "obsolete").limit(1).with_for_update()).first()
            if not enabled or now >= slot.stale or newer:
                if row:
                    c.execute(outbox.update().where(outbox.c.slot_key == key, outbox.c.reservations == 0).values(
                        state="obsolete", owner=None, lease_until=0, updated_at=now))
                return self.receipt(self._row(c, key)) if row else None
            if slot.kind in {"outage","recovery"}:
                member,_,_ = self._incident_plan(c,scope,slot,config,as_of,now,data=data)
                if list(members) != [member["key"]]:
                    raise NotificationError("notification_members_invalid",422)
            if row is None:
                self._insert(c, key, slot, scope, "system", head["version"])
                row = self._row(c, key)
            else:
                row = dict(row)
                if row["owner"] and row["lease_until"] > now:
                    return self.receipt(row)
                if row["config_version"] == head["version"] and row["payload_cipher"] and row["state"] == "prepared":
                    return self.receipt(row)
            self._write_plan(c, row, head, slot, data, as_of, origin, members)
            return self.receipt(self._row(c, key))

    def request_test(self, request_id, expected_version, scope, actor, *, origin=None):
        request = test_request(request_id, expected_version)
        actor = checked_actor(actor)
        checked_key(scope)
        fence = identity([self.instance, actor, "test", request["request_id"]])
        key = identity([self.instance, scope, actor, "test", request["request_id"]])
        now = int(self.clock())
        with self.transaction() as c:
            head = self._head(c)
            # Existing exact receipt precedes active version/configuration checks.
            previous = c.execute(sa.select(outbox).where(outbox.c.request_fence == fence).with_for_update()).mappings().first()
            if previous:
                if previous["scope_key"] != scope or previous["actor"] != actor or previous["request_hash"] != identity(request):
                    raise NotificationError("notification_request_conflict")
                return self.receipt(previous)
            self._scope(head, scope)
            if expected_version != head["version"]:
                raise NotificationError("notification_settings_changed")
            if not self._configuration(head)["recipients"]:
                raise NotificationError("notification_settings_missing")
            recent = c.execute(sa.select(outbox.c.slot_key).where(outbox.c.scope_key == scope,
                outbox.c.kind == "test", outbox.c.created_at > now - 300,
                outbox.c.state != "obsolete").limit(1).with_for_update()).first()
            if recent:
                raise NotificationError("notification_test_cooldown", 429)
            slot = Slot("test", now, now + 900, now, now + 900, request["request_id"])
            self._insert(c, key, slot, scope, actor, head["version"], request=request, request_fence=fence)
            self._write_plan(c, self._row(c, key), head, slot, {}, now, origin)
            return self.receipt(self._row(c, key))

    def read(self, key):
        with self.engine.connect() as c:
            row = c.execute(sa.select(outbox).where(outbox.c.slot_key == checked_key(key))).mappings().first()
            if row is None:
                raise NotificationError("notification_not_found", 404)
            return self.receipt(row)

    def _eligible(self, c, row, head, now):
        self._scope(head, row["scope_key"])
        if now >= row["stale_at"]:
            c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"], outbox.c.reservations == 0)
                .values(state="obsolete", owner=None, lease_until=0, updated_at=now))
            return False
        if row["config_version"] != head["version"] or not row["payload_cipher"]:
            # Mandatory normal slots must be re-planned, never permanently lost.
            c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"], outbox.c.reservations == 0)
                .values(state="obsolete" if row["kind"] == "test" else "prepared",
                    error_code="notification_replan_required", owner=None, lease_until=0, updated_at=now))
            return False
        backoff = c.execute(sa.select(monitor.c.payload).where(
            monitor.c.monitor_key == identity([row["scope_key"], "transport"])).with_for_update()).scalar_one_or_none()
        blocked_until = json.loads(backoff)["not_before"] if backoff else 0
        reserved = c.execute(sa.select(outbox.c.reserved_at).where(outbox.c.scope_key == row["scope_key"],
            outbox.c.reserved_at > now - 3600).with_for_update()).scalars().all()
        if len(reserved) >= 4:
            blocked_until = max(blocked_until, min(reserved) + 3600)
        if now < max(row["due_at"], row["not_before"], blocked_until):
            return False
        return True

    def claim(self, key, scope):
        checked_key(scope)
        now = int(self.clock())
        with self.transaction() as c:
            head = self._head(c)
            row = self._row(c, key)
            if row["scope_key"] != scope:
                raise NotificationError("notification_scope_changed")
            if row["state"] != "prepared" or row["reservations"]:
                return None
            if row["owner"] and row["lease_until"] > now:
                return None
            if not self._eligible(c, row, head, now):
                return None
            owner = uuid4().hex
            c.execute(outbox.update().where(outbox.c.slot_key == key, outbox.c.reservations == 0,
                outbox.c.state == "prepared").values(owner=owner, lease_until=now + self.LEASE_SECONDS))
            return dict(slot_key=key, owner=owner, plan_revision=row["plan_revision"],
                payload_hash=row["payload_hash"], scope_key=row["scope_key"])

    def reserve(self, ticket, *, budget):
        now = int(self.clock())
        with self.transaction() as c:
            head = self._head(c)
            row = self._row(c, ticket["slot_key"])
            if (budget.remaining() <= 0 or row["state"] != "prepared" or row["reservations"] or row["owner"] != ticket["owner"]
                    or row["lease_until"] <= now or row["plan_revision"] != ticket["plan_revision"]
                    or row["payload_hash"] != ticket["payload_hash"] or row["scope_key"] != ticket["scope_key"]):
                return False
            if not self._eligible(c, row, head, now):
                return False
            members = json.loads(row["monitor_keys"])
            incident = row["kind"] in {"outage","recovery"}
            if incident and (len(members) != 1 or not isinstance(members[0],dict)):
                raise NotificationError("notification_monitor_changed")
            sources = []
            for member in members:
                if incident:
                    try:
                        slot = IncidentSlot(row["kind"],row["period_start"],row["period_end"],row["due_at"],row["stale_at"],
                            identity([member["token"],member["episode"]]),token=member["token"],
                            **{name:member[name] for name in INCIDENT_FIELDS})
                        if slot.key(self.instance,row["scope_key"]) != row["slot_key"]:
                            raise NotificationError("notification_monitor_changed")
                        expected,source,payload = self._incident_plan(c,row["scope_key"],slot,
                            self._configuration(head),member["as_of"],now)
                    except (KeyError,TypeError):
                        raise NotificationError("notification_monitor_changed") from None
                    if member != expected:
                        raise NotificationError("notification_monitor_changed")
                    member_key = member["key"]
                else:
                    member_key = member
                    source = c.execute(sa.select(monitor).where(monitor.c.monitor_key == member_key,
                        monitor.c.scope_key == row["scope_key"],monitor.c.kind == "incident").with_for_update()).mappings().first()
                    if source is None:
                        raise NotificationError("notification_monitor_changed")
                    payload = json.loads(source["payload"])
                if row["kind"] == "outage":
                    last = payload["last_reserved_at"]
                    until = last+self._configuration(head)["outage_repeat_hours"]*3600 if last is not None else 0
                    if now < until:
                        c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"],outbox.c.reservations == 0).values(
                            not_before=max(row["not_before"],until),error_code="notification_outage_repeat_deferred",
                            owner=None,lease_until=0,updated_at=now))
                        return False
                sources.append((member_key,source,payload))
            for member_key,source,payload in sources:
                payload["last_reserved_at"] = now
                c.execute(monitor.update().where(monitor.c.monitor_key == member_key).values(
                    payload=canonical(payload),revision=source["revision"]+1,updated_at=now))
            c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"],
                outbox.c.reservations == 0, outbox.c.owner == ticket["owner"]).values(
                reservations=1, reserved_at=now, state="sending", updated_at=now))
            self._log(c, row["actor"], "notification_reserved", row["slot_key"])
            return True  # Returned only after the transaction context commits.

    def begin_post(self, ticket, *, budget):
        now = int(self.clock())
        with self.transaction() as c:
            self._head(c)
            row = self._row(c, ticket["slot_key"])
            if (row["state"] != "sending" or row["reservations"] != 1 or row["owner"] != ticket["owner"]
                    or row["plan_revision"] != ticket["plan_revision"] or row["payload_hash"] != ticket["payload_hash"]
                    or row["post_started_at"] is not None or row["lease_until"] <= now
                    or row["scope_key"] != ticket["scope_key"]):
                return None
            if budget.remaining() <= 0 or now >= row["stale_at"]:
                c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"]).values(
                    state="rejected", completed_at=now, error_code="notification_deadline_before_post",
                    owner=None, lease_until=0, updated_at=now))
                return None
            payload = self._decrypt(row["payload_cipher"])
            if identity(payload) != row["payload_hash"]:
                raise NotificationError("notification_payload_changed", 503)
            c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"],
                outbox.c.post_started_at.is_(None)).values(post_started_at=now, updated_at=now))
            return payload  # Permission is consumed once, even by the same owner.

    def finish(self, ticket, state, *, http_status=None, error_code=None):
        if state not in {"accepted", "rejected", "unknown"} or state == "accepted" and http_status != 202:
            raise NotificationError("notification_result_invalid", 422)
        if error_code is not None and (not isinstance(error_code, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", error_code)):
            raise NotificationError("notification_error_invalid", 422)
        with self.transaction() as c:
            self._head(c)
            row = self._row(c, ticket["slot_key"])
            if row["state"] != "sending" or row["owner"] != ticket["owner"] or row["reservations"] != 1:
                return self.receipt(row)
            if state == "accepted" and row["post_started_at"] is None:
                raise NotificationError("notification_result_invalid", 422)
            if state == "rejected" and row["post_started_at"] is not None and http_status not in {400,401,403,404,405,413,415,422,429}:
                raise NotificationError("notification_result_invalid", 422)
            if state == "unknown" and http_status == 202:
                raise NotificationError("notification_result_invalid", 422)
            c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"],
                outbox.c.state == "sending", outbox.c.owner == ticket["owner"]).values(
                state=state, http_status=http_status, error_code=error_code, owner=None,
                lease_until=0, completed_at=int(self.clock()), updated_at=int(self.clock())))
            self._log(c, row["actor"], "notification_" + state, row["slot_key"])
            return self.receipt(self._row(c, row["slot_key"]))

    def recover(self, key, *, stopped_owner=None):
        now = int(self.clock())
        with self.transaction() as c:
            self._head(c)
            row = self._row(c, key)
            if row["state"] not in {"prepared", "sending"}:
                return self.receipt(row)
            if stopped_owner is not None and row["owner"] != stopped_owner:
                return self.receipt(row)
            if stopped_owner is None and row["lease_until"] > now:
                return self.receipt(row)
            state = "unknown" if row["reservations"] else row["state"]
            c.execute(outbox.update().where(outbox.c.slot_key == key, outbox.c.state == row["state"],
                outbox.c.owner == row["owner"]).values(state=state, owner=None, lease_until=0,
                error_code="notification_outcome_unknown" if row["reservations"] else row["error_code"], updated_at=now))
            return self.receipt(self._row(c, key))

    def defer(self, ticket, code, until):
        if type(until) is not int or not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", code):
            raise NotificationError("notification_time_invalid", 422)
        with self.transaction() as c:
            self._head(c)
            row = self._row(c, ticket["slot_key"])
            if row["state"] == "prepared" and not row["reservations"] and row["owner"] == ticket["owner"]:
                c.execute(outbox.update().where(outbox.c.slot_key == row["slot_key"], outbox.c.reservations == 0)
                    .values(owner=None, lease_until=0, not_before=until, error_code=code, updated_at=int(self.clock())))
            return self.receipt(self._row(c, row["slot_key"]))

    def scope_backoff(self, scope, until):
        checked_key(scope)
        if type(until) is not int or until < 0:
            raise NotificationError("notification_time_invalid", 422)
        key = identity([scope, "transport"])
        with self.transaction() as c:
            self._head(c)
            previous = c.execute(sa.select(monitor).where(monitor.c.monitor_key == key).with_for_update()).mappings().first()
            if previous:
                until = max(until, json.loads(previous["payload"])["not_before"])
                c.execute(monitor.update().where(monitor.c.monitor_key == key).values(
                    payload=canonical(dict(not_before=until)), revision=previous["revision"]+1, updated_at=int(self.clock())))
            else:
                c.execute(monitor.insert().values(monitor_key=key, scope_key=scope, kind="transport",
                    payload=canonical(dict(not_before=until)), revision=1, updated_at=int(self.clock())))

    def test_receipt(self, request_id, expected_version, scope, actor):
        request = test_request(request_id, expected_version)
        actor = checked_actor(actor); checked_key(scope)
        fence = identity([self.instance, actor, "test", request["request_id"]])
        with self.engine.connect() as c:
            row = c.execute(sa.select(outbox).where(outbox.c.request_fence == fence)).mappings().first()
            if row is None:
                return None
            if row["scope_key"] != scope or row["request_hash"] != identity(request):
                raise NotificationError("notification_request_conflict")
            return self.receipt(row)

    def history(self, scope, *, page=1, page_size=25):
        checked_key(scope)
        if type(page) is not int or not 1 <= page <= 100000 or type(page_size) is not int or not 1 <= page_size <= 50:
            raise NotificationError("notification_page_invalid", 422)
        from app.process_queries import ProcessQueries
        with ProcessQueries(self.engine).snapshot() as c:
            total = c.execute(sa.select(sa.func.count()).select_from(outbox).where(outbox.c.scope_key == scope)).scalar_one()
            rows = c.execute(sa.select(outbox).where(outbox.c.scope_key == scope)
                .order_by(outbox.c.created_at.desc(),outbox.c.slot_key).limit(page_size).offset((page-1)*page_size)).mappings()
            return dict(items=[self.receipt(row) for row in rows],total=total,page=page,page_size=page_size)

    def monitor_state(self, scope, kind, token):
        checked_key(scope); checked_key(token)
        key = identity([scope,kind,token])
        with self.engine.connect() as c:
            row = c.execute(sa.select(monitor).where(monitor.c.monitor_key == key)).mappings().first()
            return None if row is None else dict(monitor_key=key,revision=row["revision"],data=json.loads(row["payload"]),updated_at=row["updated_at"])

    def put_monitor(self, scope, kind, token, data, *, expected_revision):
        checked_key(scope); checked_key(token)
        if (kind not in {"certificate","incident","runtime"} or not isinstance(data,dict)
                or len(canonical(data)) > 16384 or type(expected_revision) is not int or expected_revision < 0):
            raise NotificationError("notification_monitor_invalid", 422)
        key = identity([scope,kind,token])
        with self.transaction() as c:
            head = self._head(c); self._scope(head,scope)
            row = c.execute(sa.select(monitor).where(monitor.c.monitor_key == key).with_for_update()).mappings().first()
            if expected_revision != (row["revision"] if row else 0):
                raise NotificationError("notification_monitor_changed")
            values=dict(payload=canonical(data),revision=expected_revision+1,updated_at=int(self.clock()))
            if row:
                c.execute(monitor.update().where(monitor.c.monitor_key == key,monitor.c.revision == expected_revision).values(**values))
            else:
                c.execute(monitor.insert().values(monitor_key=key,scope_key=scope,kind=kind,**values))
        return self.monitor_state(scope,kind,token)
