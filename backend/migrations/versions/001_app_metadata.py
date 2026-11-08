"""Persistent deployment identity; no invoice data."""
import uuid
from alembic import op
import sqlalchemy as sa
revision = "001_app_metadata"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    table = op.create_table("app_metadata",
        sa.Column("singleton", sa.SmallInteger, primary_key=True),
        sa.Column("instance_id", sa.String(36), nullable=False),
        sa.CheckConstraint("singleton = 1", name="one_metadata_row"),
    )
    op.bulk_insert(table, [{"singleton": 1, "instance_id": str(uuid.uuid4())}])

def downgrade():
    op.drop_table("app_metadata")
