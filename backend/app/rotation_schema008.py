"""Additive AP12 request metadata only. No key bytes and no AP07 table changes."""
import sqlalchemy as sa

# Frozen schema values: future business changes must not rewrite migration 008.
PHASES = {"requested", "prepared", "registration_started", "registration_unknown",
    "registration_rejected", "registered", "candidate_verified", "adoption_prepared", "adopting",
    "rollback_unknown", "adopted", "overlap", "cleanup_started", "cleanup_unknown", "completed", "failed"}

metadata = sa.MetaData()
head = sa.Table("graph_rotation_head", metadata,
    sa.Column("singleton", sa.SmallInteger, primary_key=True, autoincrement=False),
    sa.Column("instance_id", sa.String(36)),
    sa.Column("scope_key", sa.String(64)),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("enabled", sa.Boolean, nullable=False),
    sa.Column("active_operation", sa.String(36)),
    sa.Column("blocked_fingerprint", sa.String(64)),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("singleton = 1 AND revision >= 0", name="rotation_one_head"))
requests = sa.Table("graph_rotation_requests", metadata,
    sa.Column("operation_id", sa.String(36), primary_key=True),
    sa.Column("instance_id", sa.String(36), nullable=False),
    sa.Column("scope_key", sa.String(64), nullable=False),
    sa.Column("actor", sa.String(64), nullable=False),
    sa.Column("trigger_kind", sa.String(16), nullable=False),
    sa.Column("request_hash", sa.String(64), nullable=False),
    sa.Column("expected_revision", sa.Integer, nullable=False),
    sa.Column("old_fingerprint", sa.String(64), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("error_code", sa.String(64)),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("updated_at", sa.BigInteger, nullable=False),
    sa.CheckConstraint("revision >= 0 AND expected_revision >= 0", name="rotation_revision"),
    sa.CheckConstraint("trigger_kind IN ('manual','automatic')", name="rotation_trigger"),
    sa.CheckConstraint("state IN (" + ",".join("'"+name+"'" for name in sorted(PHASES)) + ")", name="rotation_phase"))
