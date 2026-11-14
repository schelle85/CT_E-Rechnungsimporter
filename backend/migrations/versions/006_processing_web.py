"""Current finding generations, explicit retry receipts and versioned web controls."""
from alembic import op
import sqlalchemy as sa
from app.processing_state import attachments, corrections, findings, retries, controls
from app.storage_plan import digest
import json

revision = "006_processing_web"
down_revision = "005_processing"
branch_labels = None
depends_on = None


def upgrade():
    connection=op.get_bind()
    # 005 historically imports live metadata: handle both an existing005 and fresh installs.
    for table,names in ((attachments,('effective_finding','finding_revision')),
                        (corrections,('expected_revision','request_payload'))):
        existing={column['name'] for column in sa.inspect(connection).get_columns(table.name)}
        for name in names:
            if name not in existing:
                column=table.c[name]
                op.add_column(table.name,sa.Column(name,column.type,nullable=column.nullable,
                    server_default='0' if name in {'finding_revision','expected_revision'} else None))
    for table in (findings,retries,controls):table.create(connection,checkfirst=True)
    connection.execute(attachments.update().where(attachments.c.effective_finding.is_(None)).values(
        effective_finding=attachments.c.original_finding))
    for row in connection.execute(sa.select(attachments.c.attachment_key,attachments.c.original_finding).where(
            attachments.c.original_finding.is_not(None))).mappings():
        key=digest([row['attachment_key'],0,json.loads(row['original_finding'])])
        if not connection.execute(sa.select(findings.c.finding_key).where(findings.c.finding_key==key)).first():
            connection.execute(findings.insert().values(finding_key=key,attachment_key=row['attachment_key'],
                revision=0,finding=row['original_finding'],recorded_at=0))
    if not connection.execute(sa.select(controls.c.singleton)).first():
        connection.execute(controls.insert().values(singleton=1,version=1,preview_enabled=1,retry_enabled=1,
            actor='schema006',updated_at=0))


def downgrade():
    raise RuntimeError('Finding, approval and retry history is persistent; destructive downgrade disabled')
