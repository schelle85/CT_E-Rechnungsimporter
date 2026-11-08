"""Add configuration, session, audit and throttle tables; preserve revision001."""
from alembic import op
from app.schema import metadata
revision = "002_security_configuration"
down_revision = "001_app_metadata"
branch_labels = None
depends_on = None

def upgrade():
    metadata.create_all(bind=op.get_bind(), checkfirst=True)

def downgrade():
    metadata.drop_all(bind=op.get_bind(), checkfirst=True)
