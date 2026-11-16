"""AP12 request concurrency and additive migration, synthetic SQLite only."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import importlib.util
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.graph import GraphError
from app.rotation_state import RotationStore
from app.rotation_schema008 import metadata, head, requests
from app.schema import metadata as security_metadata
from app.schema import audit
from rotation_test_support import BINDING, NOW


def upgrade(engine):
    path=Path(__file__).parents[1]/"migrations/versions/008_graph_rotation.py"
    spec=importlib.util.spec_from_file_location("rotation_migration008",path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with engine.begin() as connection,Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
    return migration


class RotationStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.engine=sa.create_engine("sqlite:///"+str(Path(self.temp.name)/"rotation.sqlite"),
            poolclass=sa.pool.NullPool,connect_args={"check_same_thread":False,"timeout":10})
        self.addCleanup(self.engine.dispose)
        security_metadata.create_all(self.engine)
        with self.engine.begin() as c:
            c.exec_driver_sql("CREATE TABLE app_metadata (singleton INTEGER PRIMARY KEY, instance_id VARCHAR(36))")
            c.execute(sa.text("INSERT INTO app_metadata VALUES (1,:instance)"),dict(instance=BINDING.instance_id))
        upgrade(self.engine)
        self.now=[NOW];self.store=RotationStore(self.engine,BINDING,clock=lambda:self.now[0])

    def request(self,*,operation=None,trigger="manual",revision=None,actor=None):
        return self.store.request(operation or str(uuid4()),actor or ("system" if trigger=="automatic" else "ad:"+"a"*32),
            self.store.status()["revision"] if revision is None else revision,"b"*64,trigger=trigger)

    def project(self,row,state):
        return self.store.project_core(row["operation_id"],row["revision"],state)

    def test_same_request_survives_new_head_revision_and_new_store(self):
        operation=str(uuid4());row=self.request(operation=operation)
        self.store.configure(self.store.status()["revision"],True,"operator")
        other=RotationStore(self.engine,BINDING)
        again=other.request(operation,"ad:"+"a"*32,0,"b"*64)
        self.assertEqual(again,row)
        for change in ({"actor":"ad:"+"c"*32},{"old_fingerprint":"c"*64}):
            payload=dict(operation=operation,actor="ad:"+"a"*32,expected_revision=0,old_fingerprint="b"*64,**{})
            payload.update(change)
            with self.assertRaises(GraphError):other.request(**payload)

    def test_two_concurrent_triggers_get_only_one_active_operation(self):
        barrier=Barrier(2)
        def attempt(_):
            barrier.wait()
            try:return self.request(revision=0)["operation_id"]
            except GraphError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertEqual(sum(value is not None for value in results),1)
        with self.engine.connect() as c:self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(requests)).scalar_one(),1)

    def test_identical_concurrent_requests_return_same_receipt_and_one_audit(self):
        barrier=Barrier(2);operation=str(uuid4())
        def attempt(_):
            barrier.wait()
            return self.store.request(operation,"ad:"+"a"*32,0,"b"*64)
        with ThreadPoolExecutor(max_workers=2) as pool:receipts=list(pool.map(attempt,range(2)))
        self.assertEqual(receipts[0],receipts[1])
        with self.engine.connect() as c:
            self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(requests)).scalar_one(),1)
            self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(audit).where(
                audit.c.action=="graph_rotation_requested")).scalar_one(),1)

    def test_unknown_not_released_by_time_new_id_or_configuration(self):
        self.store.configure(0,True,"operator")
        row=self.request(trigger="automatic")
        for phase in ("prepared","registration_started","registration_unknown"):row=self.project(row,phase)
        self.now[0]+=86400
        self.store.configure(self.store.status()["revision"],False,"operator")
        self.store.configure(self.store.status()["revision"],True,"operator")
        for trigger in ("automatic","manual"):
            with self.assertRaises(GraphError):self.request(trigger=trigger)
        self.assertEqual(self.store.read(row["operation_id"])["state"],"registration_unknown")

    def test_rejection_blocks_next_daily_replacement_but_explicit_manual_is_separate(self):
        self.store.configure(0,True,"operator")
        row=self.request(trigger="automatic")
        for phase in ("prepared","registration_started","registration_rejected"):row=self.project(row,phase)
        self.now[0]+=86400
        with self.assertRaises(GraphError):self.request(trigger="automatic")
        new=self.request(trigger="manual")
        self.assertNotEqual(new["operation_id"],row["operation_id"])
        self.assertEqual(self.store.read(row["operation_id"])["state"],"registration_rejected")

    def test_scope_instance_and_backward_transition_fail_closed(self):
        row=self.request()
        for binding in (replace(BINDING,application_id=str(uuid4())),replace(BINDING,instance_id=str(uuid4()))):
            with self.assertRaises(GraphError):RotationStore(self.engine,binding).read(row["operation_id"])
        row=self.project(row,"prepared")
        with self.assertRaises(GraphError):self.project(row,"candidate_verified")
        with self.assertRaises(GraphError):self.store.project_core(row["operation_id"],True,"registration_started")

    def test_migration_repeat_preserves_requests_and_application_rollback_keeps_schema(self):
        row=self.request();before=self.store.status()
        migration=upgrade(self.engine)
        self.assertEqual(self.store.status(),before)
        self.assertEqual(self.store.read(row["operation_id"]),row)
        with self.assertRaises(RuntimeError):migration.downgrade()
        with self.engine.connect() as c:self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(requests)).scalar_one(),1)
