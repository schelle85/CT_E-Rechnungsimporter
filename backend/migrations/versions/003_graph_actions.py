"""Add durable Graph intents; do not change AP01 tables or instance identity."""
from alembic import op
from app.graph_state import metadata

revision = "003_graph_actions"
down_revision = "002_security_configuration"
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError("Graph intents require operator reconciliation; destructive downgrade is disabled.")
