"""Additive attachment storage receipts; no Graph or existing configuration changes."""
from alembic import op
from app.storage_state import metadata

revision = "004_storage_operations"
down_revision = "003_graph_actions"
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Storage history is persistent; destructive downgrade disabled")
