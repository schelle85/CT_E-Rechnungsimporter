"""Additive file receipts. A publication reservation is never acquired twice."""
from datetime import datetime, timezone
import time
from uuid import uuid4
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from app.storage_plan import StorageError, digest, path_key, week_key

metadata = sa.MetaData()
operations = sa.Table("storage_operations", metadata,
    sa.Column("action_key", sa.String(64), primary_key=True),
    sa.Column("scope_key", sa.String(64), nullable=False),
    sa.Column("destination_key", sa.String(64), nullable=False),
    sa.Column("input_key", sa.String(64), nullable=False),
    sa.Column("original_name", sa.Text, nullable=False),
    sa.Column("byte_size", sa.BigInteger, nullable=False),
    sa.Column("sha256", sa.String(64), nullable=False),
    sa.Column("received_at", sa.String(40), nullable=False),
    sa.Column("category", sa.String(16), nullable=False),
    sa.Column("dedupe_week", sa.String(10), nullable=False),
    sa.Column("dedupe_key", sa.String(64), unique=True),
    sa.Column("duplicate_of", sa.String(64)),
    sa.Column("target", sa.Text),
    sa.Column("path_key", sa.String(64), unique=True),
    sa.Column("state", sa.String(24), nullable=False),
    sa.Column("collision", sa.SmallInteger, nullable=False),
    sa.Column("publication_attempts", sa.SmallInteger, nullable=False),
    sa.Column("publication_rejected", sa.SmallInteger, nullable=False),
    sa.Column("stage_name", sa.String(100)),
    sa.Column("owner", sa.String(32)),
    sa.Column("lease_until", sa.BigInteger, nullable=False),
    sa.Column("error_code", sa.String(64)),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("byte_size >= 0 AND byte_size <= 26214400", name="storage_bounded_size"),
    sa.CheckConstraint("collision IN (0,1) AND publication_rejected IN (0,1) AND publication_attempts BETWEEN 0 AND 2", name="storage_bounded_attempts"),
    sa.CheckConstraint("state IN ('pending','publishing','stored','waiting','duplicate','operator_required')", name="storage_known_state"))


class StorageStore:
    LEASE_SECONDS = 300

    def __init__(self, engine, *, destination_key, clock=time.time):
        if not isinstance(destination_key, str) or len(destination_key) != 64 or any(char not in "0123456789abcdef" for char in destination_key):
            raise StorageError("storage_destination_invalid")
        self.engine, self.clock, self.destination_key = engine, clock, destination_key

    def get(self, key):
        with self.engine.connect() as connection:
            row = connection.execute(sa.select(operations).where(operations.c.action_key == key)).mappings().first()
            return dict(row) if row else None

    def _ensure(self, request, now):
        if self.get(request.key):
            return
        processing_at = datetime.fromtimestamp(now, timezone.utc)
        values = dict(action_key=request.key, scope_key=digest([request.scope]), destination_key=self.destination_key,
                      input_key=digest(request.immutable),
                      original_name=request.original_name, byte_size=request.byte_size, sha256=request.sha256,
                      received_at=request.received_at.isoformat(), category=request.category,
                      dedupe_week=week_key(processing_at), dedupe_key=request.duplicate_key(processing_at),
                      state="pending", collision=0, publication_attempts=0, publication_rejected=0,
                      lease_until=0, created_at=now, updated_at=now)
        for collision in (False, True):
            target = request.target(request.key[:32], collision=collision)
            try:
                with self.engine.begin() as connection:
                    connection.execute(operations.insert().values(**dict(values, target=target,
                        path_key=path_key(request.scope, target), collision=int(collision))))
                return
            except IntegrityError:
                if self.get(request.key):
                    return
                with self.engine.connect() as connection:
                    first = connection.execute(sa.select(operations.c.action_key, operations.c.destination_key).where(
                        operations.c.dedupe_key == values["dedupe_key"])).mappings().first()
                if first:
                    if first["destination_key"] != self.destination_key:
                        raise StorageError("storage_destination_conflict")
                    waiting = dict(values, state="waiting", dedupe_key=None, duplicate_of=first["action_key"])
                    try:
                        with self.engine.begin() as connection:
                            connection.execute(operations.insert().values(**waiting))
                    except IntegrityError:
                        if not self.get(request.key):
                            raise StorageError("storage_reservation_conflict") from None
                    return
        raise StorageError("storage_path_conflict")

    def claim(self, request):
        now = int(self.clock())
        self._ensure(request, now)
        with self.engine.begin() as connection:
            row = dict(connection.execute(sa.select(operations).where(
                operations.c.action_key == request.key).with_for_update()).mappings().one())
            if row["input_key"] != digest(request.immutable) or row["destination_key"] != self.destination_key:
                raise StorageError("storage_source_conflict")
            if row["state"] == "waiting":
                first = connection.execute(sa.select(operations).where(
                    operations.c.action_key == row["duplicate_of"])).mappings().one()
                if first["state"] == "stored":
                    connection.execute(operations.update().where(operations.c.action_key == request.key).values(
                        state="duplicate", target=first["target"], updated_at=now))
                    return dict(row, state="duplicate", target=first["target"], mode="done")
                return dict(row, mode="operator_required" if first["state"] == "operator_required" else "busy")
            if row["state"] in ("stored", "duplicate"):
                return dict(row, mode="done")
            if row["owner"] and row["lease_until"] > now:
                return dict(row, mode="busy")
            owner = uuid4().hex
            stage = request.key + "-" + owner  # Unique per owner; stale writers never share a stage file.
            changes = dict(owner=owner, lease_until=now + self.LEASE_SECONDS, updated_at=now)
            if row["state"] == "pending":
                changes["stage_name"] = stage
            result = connection.execute(operations.update().where(
                operations.c.action_key == request.key, operations.c.state == row["state"],
                operations.c.owner == row["owner"], operations.c.lease_until == row["lease_until"]).values(**changes))
            if result.rowcount != 1:
                return dict(row, mode="busy")
            return dict(row, **changes, mode="stage" if row["state"] == "pending" else "reconcile")

    def _owned(self, connection, key, owner, states):
        row = dict(connection.execute(sa.select(operations).where(
            operations.c.action_key == key).with_for_update()).mappings().one())
        if row["owner"] != owner or row["state"] not in states:
            raise StorageError("storage_owner_conflict")
        return row

    def begin_publication(self, key, owner):
        now = int(self.clock())
        with self.engine.begin() as connection:
            row = self._owned(connection, key, owner, {"pending"})
            if row["lease_until"] <= now or row["publication_attempts"] >= 2:
                raise StorageError("storage_owner_expired")
            result = connection.execute(operations.update().where(
                operations.c.action_key == key, operations.c.owner == owner, operations.c.state == "pending").values(
                    state="publishing", publication_attempts=row["publication_attempts"] + 1,
                    publication_rejected=0, updated_at=now))
            if result.rowcount != 1:
                raise StorageError("storage_owner_conflict")

    def collision(self, request, owner):
        """Only call after definitive EEXIST: the preceding rename did not apply."""
        with self.engine.begin() as connection:
            row = self._owned(connection, request.key, owner, {"publishing"})
            if row["collision"] or row["publication_attempts"] != 1:
                raise StorageError("storage_path_conflict")
            target = request.target(request.key[:32], collision=True)
            try:
                result = connection.execute(operations.update().where(
                    operations.c.action_key == request.key, operations.c.owner == owner, operations.c.state == "publishing").values(
                        state="pending", target=target, path_key=path_key(request.scope, target), collision=1, publication_rejected=1,
                        updated_at=int(self.clock())))
            except IntegrityError:
                raise StorageError("storage_path_conflict") from None
            if result.rowcount != 1:
                raise StorageError("storage_owner_conflict")
            return target

    def finish(self, key, owner, state, *, error=None, rejected=False):
        if state not in ("stored", "operator_required"):
            raise StorageError("storage_state_invalid")
        with self.engine.begin() as connection:
            row = self._owned(connection, key, owner, {"publishing", "operator_required"} if state == "stored" else {"pending", "publishing", "operator_required"})
            if state == "stored" and (not row["publication_attempts"] or row["publication_rejected"] or rejected):
                raise StorageError("storage_not_published")
            changes = dict(state=state, owner=None, lease_until=0, error_code=error, updated_at=int(self.clock()))
            if rejected:
                changes["publication_rejected"] = 1
            result = connection.execute(operations.update().where(
                operations.c.action_key == key, operations.c.owner == owner).values(**changes))
            if result.rowcount != 1:
                raise StorageError("storage_owner_conflict")
