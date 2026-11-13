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

    def claim(self, mailbox, kind, resource, target, *, intent_key=None):
        mailbox_key = hashlib.sha256(mailbox.lower().encode()).hexdigest()
        identity = [mailbox_key, kind, resource]
        if intent_key is not None:
            if not isinstance(intent_key, str) or len(intent_key) != 64 or any(c not in "0123456789abcdef" for c in intent_key):
                raise GraphError("graph_intent_invalid")
            identity.append(intent_key)
        key = hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()
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
            if intent_key is not None and row["state"] == "done":
                return key, None, False  # Historical revision receipt: never reset or reapply it.
            if row["owner"] and row["lease_until"] > now:
                raise GraphError("graph_action_busy")
            may_send = row["state"] == "pending" and row["reservations"] == 0
            result = connection.execute(actions.update().where(actions.c.action_key == key,
                actions.c.owner == row["owner"], actions.c.lease_until == row["lease_until"], actions.c.state == row["state"]).values(
                state="sending" if may_send else "checking", reservations=1,
                owner=owner, lease_until=now + self.LEASE_SECONDS, updated_at=now))
            if result.rowcount != 1:
                raise GraphError("graph_action_busy")
        return key, owner, may_send

    def finish(self, key, owner, state, *, result=None, error=None):
        with self.engine.begin() as connection:
            row = connection.execute(sa.select(actions).where(actions.c.action_key == key).with_for_update()).mappings().one()
            if row["owner"] != owner:
                raise GraphError("graph_action_conflict")
            connection.execute(actions.update().where(actions.c.action_key == key).values(
                state=state, result_id=result, error_code=error, owner=None, lease_until=0, updated_at=int(self.clock())))
