"""Worker-only minimal runtime. No Runtime.cipher, LDAP loader or migrations."""
import json
import os
import time
import sqlalchemy as sa
from cryptography.fernet import Fernet
from app.database import make_engine
from app.graph import GraphConfig, GraphError, protected_bytes
from app.notification_certificate import CERTIFICATE_TOKEN, CertificateMaterial
from app.notification_model import NotificationError, OperationBudget, checked_key, checked_settings, graph_scope, identity
from app.notification_schema007 import outbox
from app.notification_service import NotificationService
from app.notification_state import AUTOMATIC_KINDS,NotificationStore

INITIAL_FILE = "/run/importer/notification-init.json"

def load_notification_cipher():
    try:
        raw = protected_bytes(os.environ.get("NOTIFICATION_KEY_FILE","/run/secrets/notification_key"))
        return Fernet(raw.rstrip(b"\r\n"))
    except (ValueError,GraphError):
        raise NotificationError("notification_key_unavailable",503) from None

def run_job(job):
    deadline = job["deadline"]
    now = time.monotonic()
    if type(deadline) not in (int,float) or not now < deadline <= now+80:
        raise NotificationError("notification_deadline",504)
    budget = OperationBudget(clock=time.monotonic,seconds=min(60,deadline-now))
    budget.deadline = min(deadline,budget.deadline)
    command = job["command"]
    config = GraphConfig.load(os.environ.get("GRAPH_CONFIG_FILE","/run/importer/graph.json"))
    scope = graph_scope(config.tenant_id,config.client_id,config.mailbox)
    read_only = command in {"status","readback","pending"}
    cipher = None if read_only else load_notification_cipher()
    engine = make_engine()
    try:
        with engine.connect() as c:
            instance = c.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
        store = NotificationStore(engine,cipher,instance)
        if command == "status":
            if "request_id" in job:
                receipt = store.test_receipt(job["request_id"],job["expected_version"],scope,"operator")
            else:
                receipt = store.read(checked_key(job["slot_key"]))
                if receipt["scope_key"] != scope:raise NotificationError("notification_scope_changed")
            return dict(ok=True,persisted=True,receipt=receipt)
        if command == "readback":
            receipts = []
            for key in job["keys"]:
                row = store.read(key)
                if row["scope_key"] != scope:raise NotificationError("notification_scope_changed")
                receipts.append(store.recover(key,stopped_owner=job["owner"]))
            return dict(ok=True,persisted=True,receipts=receipts)
        if command == "pending":
            return dict(ok=True,keys=store.pending(scope,limit=job["limit"]))
        if command == "configuration":
            value = store.configuration()
            return dict(ok=True,persisted=True,version=value["version"],configured=value["configured"],
                scope_key=value["scope_key"],recipient_count=len(value["settings"]["recipients"]),
                settings_hash=identity(value["settings"]))
        if command == "configure-init":
            if job.get("config",INITIAL_FILE) != INITIAL_FILE:
                raise NotificationError("notification_initial_file_invalid",422)
            initial = json.loads(protected_bytes(INITIAL_FILE))
            if (not isinstance(initial,dict) or set(initial) != {"expected_version","settings"}
                    or type(initial["expected_version"]) is not int or initial["expected_version"] != 0):
                raise NotificationError("notification_initial_file_invalid",422)
            value = store.save_settings(0,checked_settings(initial["settings"]),scope,"operator")
            return dict(ok=True,persisted=True,version=value["version"],actor="operator",
                recipient_count=len(value["settings"]["recipients"]),settings_hash=identity(value["settings"]))
        if command == "request-test":
            return dict(ok=True,persisted=True,receipt=store.request_test(job["request_id"],job["expected_version"],
                scope,"operator",origin=os.environ.get("PUBLIC_ORIGIN")))
        if command == "preview":
            key = checked_key(job["slot_key"])
            with engine.connect() as c:
                row = c.execute(sa.select(outbox).where(outbox.c.slot_key == key,outbox.c.scope_key == scope)).mappings().first()
            if row is None:raise NotificationError("notification_not_found",404)
            if row["payload_cipher"] is None:raise NotificationError("notification_settings_missing")
            payload = store._decrypt(row["payload_cipher"])
            if identity(payload) != row["payload_hash"]:raise NotificationError("notification_payload_changed",503)
            return dict(ok=True,persisted=True,receipt=store.receipt(row),payload=payload)
        if command not in {"observe","plan","send","send-automatic"}:
            raise NotificationError("notification_command_invalid",422)
        if command == "send-automatic":
            keys=job.get("keys")
            if not isinstance(keys,list) or not 1<=len(keys)<=5 or len(set(keys))!=len(keys):
                raise NotificationError("notification_limit_invalid",422)
            for key in keys:
                row=store.read(checked_key(key))
                if row["scope_key"]!=scope or row["kind"] not in AUTOMATIC_KINDS:
                    raise NotificationError("notification_automatic_kind_invalid",422)
        # Capture the fence before reading PEM bytes; a later observer/proof cannot be overwritten.
        observed = store.monitor_state(scope,"certificate",CERTIFICATE_TOKEN)
        observation_revision = observed["revision"] if observed else 0
        try:
            material = CertificateMaterial.load(os.environ.get("GRAPH_CREDENTIAL_FILE","/run/secrets/graph_credential"))
        except NotificationError:
            material = None
        service = NotificationService(store,config,material,observation_revision=observation_revision,
            origin=os.environ.get("PUBLIC_ORIGIN"))
        if command == "observe":
            return dict(ok=True,persisted=True,certificate=service.observe(probe=job.get("probe") is True,budget=budget))
        if command == "plan":
            from app.notification_observers import observe_and_plan
            observed_plans=observe_and_plan(service,budget=budget)
            # The minimal external worker has no host-status directory binding.
            return dict(ok=True,persisted=True,receipts=observed_plans+service.plan(),
                automatic_schedule_active=None,automatic_schedule_state="unknown")
        keys = job["keys"]
        if not isinstance(keys,list) or not 1 <= len(keys) <= 5 or len(set(keys)) != len(keys):
            raise NotificationError("notification_limit_invalid",422)
        return dict(ok=True,receipts=[service.send(checked_key(key),budget=budget,owner=job["owner"]) for key in keys])
    finally:
        engine.dispose()
