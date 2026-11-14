"""Notification settings, immutable reservations and monitor metadata only."""
from alembic import op
import sqlalchemy as sa
from app.notification_schema007 import metadata, settings

revision = "007_notifications"
down_revision = "006_processing_web"
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    metadata.create_all(connection, checkfirst=True)
    if not connection.execute(sa.select(settings.c.singleton)).first():
        connection.execute(settings.insert().values(singleton=1, version=0,
            scope_key=None, payload_cipher=None, actor="schema007", updated_at=0))

def downgrade():
    raise RuntimeError("Notification reservations/history must survive application rollback")
