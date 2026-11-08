"""Frozen additive schema for revision002; later changes need a new migration."""
import sqlalchemy as sa
metadata = sa.MetaData()
versions = sa.Table("configuration_versions", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("settings", sa.Text, nullable=False),
    sa.Column("bind_cipher", sa.Text),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("actor", sa.String(256), nullable=False))
head = sa.Table("configuration_head", metadata,
    sa.Column("singleton", sa.SmallInteger, primary_key=True, autoincrement=False),
    sa.Column("active_id", sa.Integer, sa.ForeignKey("configuration_versions.id"), nullable=False),
    sa.Column("previous_id", sa.Integer, sa.ForeignKey("configuration_versions.id")),
    sa.CheckConstraint("singleton = 1", name="one_configuration_head"))
sessions = sa.Table("auth_sessions", metadata,
    sa.Column("id_hash", sa.String(64), primary_key=True),
    sa.Column("csrf", sa.String(64), nullable=False),
    sa.Column("guid", sa.String(32)),
    sa.Column("username", sa.String(256)),
    sa.Column("dn", sa.String(2048)),
    sa.Column("config_id", sa.Integer),
    sa.Column("created_at", sa.BigInteger, nullable=False),
    sa.Column("last_seen", sa.BigInteger, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True))
attempts = sa.Table("login_attempts", metadata,
    sa.Column("bucket", sa.String(128), primary_key=True),
    sa.Column("count", sa.Integer, nullable=False),
    sa.Column("expires_at", sa.BigInteger, nullable=False, index=True))
audit = sa.Table("audit_log", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("occurred_at", sa.BigInteger, nullable=False),
    sa.Column("actor", sa.String(256), nullable=False),
    sa.Column("action", sa.String(64), nullable=False),
    sa.Column("result", sa.String(32), nullable=False),
    sa.Column("changed_fields", sa.Text, nullable=False),
    sa.Column("config_id", sa.Integer))
