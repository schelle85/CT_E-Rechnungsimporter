"""One durable bound request, independent of process leases or HTTP responses."""
from contextlib import contextmanager
import time
import sqlalchemy as sa

from app.graph import GraphError
from app.notification_model import checked_actor, identity
from app.rotation_model import sha, uuid
from app.rotation_schema008 import head, requests
from app.schema import audit

CORE_PHASES = {"prepared", "registration_started", "registration_unknown", "registration_rejected",
    "registered", "candidate_verified"}
TRANSITIONS = {"requested": {"prepared"}, "prepared": {"registration_started"},
    "registration_started": {"registration_unknown", "registration_rejected", "registered"},
    "registration_unknown": {"registration_unknown", "registered"},
    "registered": {"candidate_verified"}}


class RotationStore:
    def __init__(self, engine, binding, *, clock=time.time):
        self.engine, self.binding, self.clock = engine, binding, clock

    @contextmanager
    def transaction(self):
        with self.engine.connect() as c:
            c.exec_driver_sql("BEGIN IMMEDIATE") if self.engine.dialect.name == "sqlite" else c.begin()
            try:
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    def _head(self, c):
        # Serialize before the first consistent read: a pre-lock REPEATABLE READ
        # snapshot must not hide the winner's immutable request receipt.
        row = c.execute(sa.select(head).where(head.c.singleton == 1).with_for_update()).mappings().first()
        if row is None:
            raise GraphError("rotation_schema_unavailable")
        instance = c.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
        if instance != self.binding.instance_id:
            raise GraphError("rotation_scope_changed")
        if row["scope_key"] not in {None, self.binding.scope} or row["instance_id"] not in {None, self.binding.instance_id}:
            raise GraphError("rotation_scope_changed")
        return dict(row)

    def _row(self, c, operation):
        row = c.execute(sa.select(requests).where(requests.c.operation_id == uuid(operation)).with_for_update()).mappings().first()
        if row is None:
            raise GraphError("rotation_not_found")
        if row["scope_key"] != self.binding.scope or row["instance_id"] != self.binding.instance_id:
            raise GraphError("rotation_scope_changed")
        return dict(row)

    def status(self):
        with self.transaction() as c:
            return self._head(c)

    def read(self, operation):
        with self.transaction() as c:
            self._head(c)
            return self._row(c, operation)

    def request(self, operation, actor, expected_revision, old_fingerprint, *, trigger="manual"):
        uuid(operation); sha(old_fingerprint)
        actor = checked_actor(actor)
        if (trigger not in {"manual", "automatic"} or type(expected_revision) is not int or expected_revision < 0
                or (trigger == "automatic" and actor != "system")):
            raise GraphError("rotation_request_invalid")
        request_hash = identity([operation, self.binding.scope, actor, trigger, expected_revision, old_fingerprint])
        now = int(self.clock())
        with self.transaction() as c:
            current = self._head(c)
            existing = c.execute(sa.select(requests).where(requests.c.operation_id == operation).with_for_update()).mappings().first()
            if existing is not None:
                if existing["request_hash"] != request_hash or existing["scope_key"] != self.binding.scope:
                    raise GraphError("rotation_request_conflict")
                return dict(existing)  # Before comparing a now-newer head revision.
            if expected_revision != current["revision"]:
                raise GraphError("rotation_revision_changed")
            if trigger == "automatic" and (not current["enabled"] or current["blocked_fingerprint"] == old_fingerprint):
                raise GraphError("rotation_automatic_blocked")
            if current["active_operation"] is not None:
                previous = self._row(c, current["active_operation"])
                if previous["state"] != "registration_rejected" or trigger != "manual":
                    raise GraphError("rotation_already_active")
            c.execute(requests.insert().values(operation_id=operation, instance_id=self.binding.instance_id,
                scope_key=self.binding.scope, actor=actor, trigger_kind=trigger, request_hash=request_hash,
                expected_revision=expected_revision, old_fingerprint=old_fingerprint, state="requested", revision=0,
                created_at=now, updated_at=now))
            c.execute(head.update().where(head.c.singleton == 1).values(instance_id=self.binding.instance_id,
                scope_key=self.binding.scope, active_operation=operation, revision=current["revision"]+1, updated_at=now))
            c.execute(audit.insert().values(occurred_at=now, actor=actor, action="graph_rotation_requested",
                result="ok", changed_fields='["operation:'+operation+'"]', config_id=None))
            return self._row(c, operation)

    def configure(self, expected_revision, enabled, actor):
        actor = checked_actor(actor)
        if type(enabled) is not bool or type(expected_revision) is not int or expected_revision < 0:
            raise GraphError("rotation_request_invalid")
        with self.transaction() as c:
            current = self._head(c)
            if current["revision"] != expected_revision:
                raise GraphError("rotation_revision_changed")
            c.execute(head.update().where(head.c.singleton == 1).values(instance_id=self.binding.instance_id,
                scope_key=self.binding.scope, enabled=enabled, revision=expected_revision+1, updated_at=int(self.clock())))
            c.execute(audit.insert().values(occurred_at=int(self.clock()), actor=actor,
                action="graph_rotation_configured", result="ok", changed_fields='["enabled"]', config_id=None))
        return self.status()

    def project_core(self, operation, expected_revision, state, *, code=None):
        """Host projection only, no lease expiry/reset or application adoption in B."""
        if (type(expected_revision) is not int or expected_revision < 0 or state not in CORE_PHASES
                or code not in {None, "rotation_registration_rejected", "rotation_registration_unknown"}):
            raise GraphError("rotation_transition_invalid")
        with self.transaction() as c:
            current = self._head(c); row = self._row(c, operation)
            if current["active_operation"] != operation or row["revision"] != expected_revision:
                raise GraphError("rotation_revision_changed")
            if state not in TRANSITIONS.get(row["state"], set()):
                raise GraphError("rotation_transition_invalid")
            c.execute(requests.update().where(requests.c.operation_id == operation).values(state=state,
                error_code=code, revision=expected_revision+1, updated_at=int(self.clock())))
            if state in {"registration_rejected", "registration_unknown"}:
                c.execute(head.update().where(head.c.singleton == 1).values(blocked_fingerprint=row["old_fingerprint"]))
            return self._row(c, operation)

    def resume_closed(self,operation,expected_revision,fingerprint,*,completed=False):
        """Root has verified the matching closed gate/journal; retain original request."""
        with self.transaction() as c:
            current=self._head(c);row=self._row(c,operation)
            outcome=(row["state"]=="completed" and row["error_code"] in {None,"rotation_old_key_unmanaged"}
                and row["old_fingerprint"]!=fingerprint) if completed else (
                row["state"]=="failed" and row["error_code"]=="rotation_rolled_back"
                and row["old_fingerprint"]==fingerprint and current["blocked_fingerprint"]==fingerprint)
            if current["active_operation"] is not None or row["revision"]!=expected_revision or not outcome:
                raise GraphError("rotation_operation_changed")
            now=int(self.clock())
            c.execute(requests.update().where(requests.c.operation_id==operation).values(state="adopting",
                error_code=None if completed else "rotation_rollback_pending",revision=row["revision"]+1,updated_at=now))
            c.execute(head.update().where(head.c.singleton==1).values(active_operation=operation,
                revision=current["revision"]+1,updated_at=now))
            return self._row(c,operation)

    def project_host(self,operation,expected_revision,state,*,code=None):
        """Root worker only; final publication follows the persisted gate release."""
        transitions={"registered":{"adoption_prepared"},"candidate_verified":{"adoption_prepared"},
            "adoption_prepared":{"adopting"},"adopting":{"rollback_unknown","adopted"},
            "rollback_unknown":{"adopting","adopted"},"adopted":{"adopting","overlap","failed"},
            "overlap":{"adopting","cleanup_started"},"cleanup_started":{"adopting","cleanup_unknown","completed"},
            "cleanup_unknown":{"adopting","cleanup_started","completed"}}
        codes={None,"rotation_rollback_pending","rotation_rollback_unknown","rotation_proof_unknown","rotation_rolled_back",
            "rotation_cleanup_unknown","rotation_old_key_unmanaged"}
        if state not in {target for values in transitions.values() for target in values} or code not in codes:
            raise GraphError("rotation_transition_invalid")
        with self.transaction() as c:
            current=self._head(c);row=self._row(c,operation)
            if row["state"]==state and row["error_code"]==code:return row
            if current["active_operation"]!=operation or row["revision"]!=expected_revision or (state!=row["state"] and state not in transitions.get(row["state"],set())):
                raise GraphError("rotation_transition_invalid")
            now=int(self.clock())
            c.execute(requests.update().where(requests.c.operation_id==operation).values(state=state,error_code=code,
                revision=row["revision"]+1,updated_at=now))
            changes=dict(revision=current["revision"]+1,updated_at=now)
            if state in {"failed","completed"}:changes["active_operation"]=None
            if state=="failed":changes["blocked_fingerprint"]=row["old_fingerprint"]
            c.execute(head.update().where(head.c.singleton==1).values(**changes))
            return self._row(c,operation)
