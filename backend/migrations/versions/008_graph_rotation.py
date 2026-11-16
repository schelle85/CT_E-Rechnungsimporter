"""Add durable AP12 request/head metadata; keep existing application history."""
from alembic import op
import sqlalchemy as sa
from app.rotation_schema008 import metadata, head

revision = "008_graph_rotation"
down_revision = "007_notifications"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    metadata.create_all(connection, checkfirst=True)
    if not connection.execute(sa.select(head.c.singleton)).first():
        connection.execute(head.insert().values(singleton=1, revision=0, enabled=False, updated_at=0))


def downgrade():
    raise RuntimeError("Rotation identities/effect records must survive application rollback")
