"""Fixed AP10 read-only effect probe for the existing pinned backend image."""
import hashlib
import json
import sys

# Existing durable stores: no age-based clearing and no write/recovery methods.
QUERIES={
    "notifications":"""SELECT 1 FROM notification_outbox WHERE scope_key=:notification
        AND (owner IS NOT NULL OR lease_until<>0 OR state='sending'
        OR (state='unknown' AND reservations<>1) OR (state='prepared' AND reservations<>0)
        OR (reservations=1 AND reserved_at IS NULL)
        OR (state='accepted' AND (reservations<>1 OR post_started_at IS NULL OR http_status IS NULL OR http_status<>202))) LIMIT 1""",
    "graph":"""SELECT 1 FROM graph_actions WHERE mailbox_key=:graph_mailbox
        AND (owner IS NOT NULL OR lease_until<>0 OR state IN ('sending','checking')
        OR (state='pending' AND reservations<>0)
        OR (state IN ('done','unknown','operator_required') AND reservations<>1)) LIMIT 1""",
    "storage":"""SELECT 1 FROM storage_operations WHERE scope_key=:storage
        AND (owner IS NOT NULL OR lease_until<>0 OR state='publishing'
        OR (state='pending' AND publication_attempts>0 AND publication_rejected=0)) LIMIT 1""",
    "file_receipts":"""SELECT 1 FROM processing_attachments a
        JOIN processing_messages m ON a.message_key=m.message_key
        LEFT JOIN storage_operations s ON a.effect_key=s.action_key
        WHERE m.mailbox_key=:processing_mailbox AND a.effect_key IS NOT NULL AND a.effect_state IN ('uncertain','blocked')
        AND (s.action_key IS NULL OR s.owner IS NOT NULL OR s.lease_until<>0 OR s.state='publishing'
        OR (s.state='pending' AND s.publication_attempts>0 AND s.publication_rejected=0)) LIMIT 1""",
    "processing_owner":"""SELECT 1 FROM processing_messages WHERE mailbox_key=:processing_mailbox
        AND (owner IS NOT NULL OR lease_until<>0) LIMIT 1"""}

TERMINAL={
    "notifications":"""SELECT 1 FROM notification_outbox WHERE scope_key=:notification
        AND state='unknown' AND reservations=1 AND owner IS NULL AND lease_until=0 AND reserved_at IS NOT NULL LIMIT 1""",
    "graph":"""SELECT 1 FROM graph_actions WHERE mailbox_key=:graph_mailbox
        AND state IN ('unknown','operator_required') AND reservations=1 AND owner IS NULL AND lease_until=0 LIMIT 1""",
    "storage":"""SELECT 1 FROM storage_operations WHERE scope_key=:storage AND state='operator_required'
        AND publication_attempts>0 AND publication_rejected=0 AND owner IS NULL AND lease_until=0 LIMIT 1"""}


def scan(read,parameters,queries=QUERIES):
    return {name:read(sql,parameters) is not None for name,sql in queries.items()}


def main():
    engine=None
    try:
        import sqlalchemy as sa
        from app.database import make_engine
        from app.graph import GraphConfig
        from app.graph_access_runtime import binding
        from app.notification_model import graph_scope
        from app.processing_cli import configuration
        from app.storage_plan import digest
        raw=sys.stdin.buffer.read(16385)
        if len(raw)>16384: raise ValueError()
        request=json.loads(raw)
        config=GraphConfig.load("/run/importer/graph.json")
        access=binding(config)
        if request!={"binding":access.fields()}: raise ValueError()
        processing=configuration("/run/importer/processing.json")
        scope=graph_scope(config.tenant_id,config.client_id,config.mailbox)
        parameters=dict(notification=scope,graph_mailbox=hashlib.sha256(config.mailbox.lower().encode()).hexdigest(),
                        processing_mailbox=digest([config.mailbox.lower()]),storage=digest([processing["scope"]]))
        engine=make_engine()
        with engine.connect() as connection:
            connection.exec_driver_sql("SET SESSION max_statement_time=5")
            connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            instance=connection.exec_driver_sql("SELECT instance_id FROM app_metadata WHERE singleton=1").scalar_one()
            if instance!=access.instance_id: raise ValueError()
            head=connection.exec_driver_sql("SELECT scope_key FROM notification_settings WHERE singleton=1").scalar_one()
            if head not in (None,scope): raise ValueError()
            blocked=scan(lambda sql,p:connection.execute(sa.text(sql),p).first(),parameters)
            terminal=scan(lambda sql,p:connection.execute(sa.text(sql),p).first(),parameters,TERMINAL)
            # Connection closes by rollback; no business writes or Graph clients.
        result=dict(ok=True,binding=access.fields(),blocked=blocked,terminal_uncertain=terminal)
    except BaseException:
        result=dict(ok=False,code="effects_unconfirmed")
    finally:
        if engine is not None: engine.dispose()
    print(json.dumps(result,separators=(",",":")))
    return 0 if result["ok"] else 1


if __name__=="__main__": raise SystemExit(main())
