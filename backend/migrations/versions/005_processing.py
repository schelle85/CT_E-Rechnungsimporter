"""Add source, attachment and approved-correction integration state."""
from alembic import op
from app.processing_state import metadata

revision = "005_processing"
down_revision = "004_storage_operations"
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Processing history is persistent; destructive downgrade disabled")
