"""Durable one-write reservations; uncertain outcomes are reconciled, never replayed."""
import hashlib
import json
import time
from uuid import uuid4
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from app.graph import GraphError

metadata = sa.MetaData()
actions = sa.Table("graph_actions", metadata,
    sa.Column("action_key", sa.String(64), primary_key=True),
    sa.Column("mailbox_key", sa.String(64), nullable=False),
    sa.Column("kind", sa.String(16), nullable=False),
    sa.Column("resource", sa.Text, nullable=False),
    sa.Column("target", sa.Text, nullable=False),
    sa.Column("state", sa.String(24), nullable=False),
    sa.Column("reservations", sa.SmallInteger, nullable=False),
    sa.Column("owner", sa.String(32)),
    sa.Column("lease_until", sa.BigInteger, nullable=False),
    sa.Column("result_id", sa.Text),
    sa.Column("error_code", sa.String(64)),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("reservations >= 0 AND reservations <= 1", name="graph_one_write_reservation"),
    sa.CheckConstraint("state IN ('pending','sending','checking','unknown','done','operator_required')", name="graph_known_state"))


class ActionStore:
    LEASE_SECONDS = 300  # Longer than the complete CLI operation including termination.

    def __init__(self, engine, clock=time.time):
        self.engine, self.clock = engine, clock

    def claim(self, mailbox, kind, resource, target):
        mailbox_key = hashlib.sha256(mailbox.lower().encode()).hexdigest()
        key = hashlib.sha256(json.dumps([mailbox_key, kind, resource], separators=(",", ":")).encode()).hexdigest()
        now, owner = int(self.clock()), uuid4().hex
        try:
            with self.engine.begin() as connection:
                connection.execute(actions.insert().values(action_key=key, mailbox_key=mailbox_key, kind=kind,
                    resource=resource, target=target, state="pending", reservations=0,
                    lease_until=0, created_at=now, updated_at=now))
        except IntegrityError:
            pass  # Exact identity already exists; inspect and lock it below.
        with self.engine.begin() as connection:
            row = connection.execute(sa.select(actions).where(actions.c.action_key == key).with_for_update()).mappings().one()
            if row["target"] != target or row["resource"] != resource or row["kind"] != kind:
                raise GraphError("graph_action_conflict")
            if row["owner"] and row["lease_until"] > now:
                raise GraphError("graph_action_busy")
            may_send = row["state"] == "pending" and row["reservations"] == 0
            connection.execute(actions.update().where(actions.c.action_key == key).values(
                state="sending" if may_send else "checking", reservations=1,
                owner=owner, lease_until=now + self.LEASE_SECONDS, updated_at=now))
        return key, owner, may_send

    def finish(self, key, owner, state, *, result=None, error=None):
        with self.engine.begin() as connection:
            row = connection.execute(sa.select(actions).where(actions.c.action_key == key).with_for_update()).mappings().one()
            if row["owner"] != owner:
                raise GraphError("graph_action_conflict")
            connection.execute(actions.update().where(actions.c.action_key == key).values(
                state=state, result_id=result, error_code=error, owner=None, lease_until=0, updated_at=int(self.clock())))
