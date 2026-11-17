"""Root worker: real SQLite/core journal/crypto, explicit host/Entra/gate doubles."""
from contextlib import ExitStack,contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
import sqlalchemy as sa

from app import rotation_worker as worker
from app.graph import GraphError
from app.graph_access import AccessBinding
from app.notification_model import graph_scope,identity
from app.notification_schema007 import metadata as notification_metadata
from app.rotation_schema008 import requests
from app.rotation_state import RotationStore
from app.schema import metadata as security_metadata
from rotation_test_support import BINDING,CONFIG,NOW,Remote,local_journal,material
from test_rotation_state import upgrade


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        directory=Path(self.temp.name);self.root=self.stack.enter_context(local_journal(directory))
        self.engine=sa.create_engine("sqlite:///"+str(directory/"worker.sqlite"),poolclass=sa.pool.NullPool)
        self.addCleanup(self.engine.dispose);security_metadata.create_all(self.engine);notification_metadata.create_all(self.engine)
        with self.engine.begin() as c:
            c.exec_driver_sql("CREATE TABLE app_metadata (singleton INTEGER PRIMARY KEY,instance_id VARCHAR(36))")
            c.execute(sa.text("INSERT INTO app_metadata VALUES(1,:instance)"),dict(instance=BINDING.instance_id))
        upgrade(self.engine)
        self.access=AccessBinding("a"*40,str(uuid4()),BINDING.instance_id,BINDING.scope)
        self.current=material(days=365);self.remote=Remote(self.current);self.operation=str(uuid4())
        self.store=RotationStore(self.engine,BINDING,clock=lambda:NOW)
        self.store.request(self.operation,"operator",0,self.current.fingerprint)
        @contextmanager
        def session():yield self.root
        @contextmanager
        def graph(*args,**kwargs):yield self.remote
        for target,value in (("make_engine",lambda:self.engine),("RootJournal",lambda *a:self.root),
                ("access_binding",lambda config:self.access),("rotation_client",graph)):
            self.stack.enter_context(patch.object(worker,target,side_effect=value))
        self.stack.enter_context(patch.object(self.root,"session",side_effect=session))
        self.stack.enter_context(patch.object(worker.GraphConfig,"load",return_value=CONFIG))
        self.stack.enter_context(patch.object(worker.CertificateMaterial,"load",side_effect=lambda _:self.current))
        self.stack.enter_context(patch("app.graph.protected_bytes",return_value=json.dumps(dict(application_id=BINDING.application_id)).encode()))
        self.stack.enter_context(patch("app.rotation_adoption.protected_bytes",side_effect=lambda p:Path(p).read_bytes()))
        self.stack.enter_context(patch("app.rotation_adoption.sync_directory"))
        self.stack.enter_context(patch("app.rotation_adoption.boot_id",return_value="77777777-7777-7777-7777-777777777777"))
        self.stack.enter_context(patch.object(worker.time,"time",return_value=NOW))
        self.images={role:"sha256:"+"b"*64 for role in ("api","processing","notifications")}

    def call(self,command,**values):
        return worker.execute(dict(command=command,operation_id=self.operation,**values),time.monotonic()+70)

    def receipt(self,role,*,purpose="consumer-read",epoch=3,proof_revision=None):
        candidate=self.root.material(self.operation);cid=hashlib.sha256((role+purpose).encode()).hexdigest()
        probe=dict(ok=True,code="graph_probe_verified",**self.access.fields(),operation_id=self.operation,epoch=epoch,
            purpose=purpose,consumer_role=role,consumer_id=hashlib.sha256(cid.encode()).hexdigest(),fingerprint=candidate.fingerprint,
            pem_hash=hashlib.sha256(candidate.pem).hexdigest(),at=NOW,proof_revision=proof_revision,
            proof_at=NOW if proof_revision is not None else None)
        probe["receipt_hash"]=identity(probe)
        return dict(container_id=cid,image=self.images.get(role,self.images["notifications"]),probe=probe)

    def test_register_replay_and_full_private_commit_precede_public_release(self):
        first=self.call("register");again=self.call("register")
        self.assertEqual(first["core"],again["core"]);self.assertEqual(self.remote.adds,1)
        self.call("prepare",images=self.images,paused=False,drain_identity=None)
        self.call("candidate-verified",receipt=self.receipt("candidate",purpose="candidate-read"))
        self.call("activation-started");self.current=self.root.material(self.operation);self.call("activated")
        self.call("consumers",receipts={role:self.receipt(role) for role in self.images})
        proof=self.receipt("notifications",purpose="finalize-proof",epoch=5,proof_revision=1)
        self.call("proof-started",consumer=proof,epoch=5,base_revision=0)
        self.call("proof-verified",receipt=proof)
        result=self.call("commit",paused=False,drain_identity=None)
        self.assertEqual(result["host"]["phase"],"committed")
        self.assertEqual(self.store.read(self.operation)["state"],"adopted")
        self.assertEqual(self.store.status()["active_operation"],self.operation)
        # Public completion cannot race ahead of actual gate release.
        with patch("app.graph_access.AccessGate") as gate:
            gate.return_value.read.return_value=dict(mode="blocked",operation_id=self.operation,release_hash=None)
            with self.assertRaises(GraphError):self.call("publish")
        self.assertEqual(self.store.read(self.operation)["state"],"adopted")
        with patch("app.graph_access.AccessGate") as gate:
            gate.return_value.read.return_value=dict(mode="allowed",operation_id=self.operation,release_hash=result["host"]["seal"])
            published=self.call("publish")
        self.assertEqual(published["request"]["state"],"overlap");self.assertEqual(self.remote.adds,1)

    def test_worker_rejects_unknown_fields_and_other_operation_binding(self):
        with self.assertRaises(GraphError):worker.request(json.dumps(dict(command="register",operation_id=self.operation,path="/other")).encode())
        other=str(uuid4())
        with self.assertRaises(GraphError):worker.execute(dict(command="register",operation_id=other),time.monotonic()+70)
        self.assertEqual(self.remote.adds,0)

    def test_host_projection_keeps_original_request_and_blocks_new_auto_generation(self):
        self.call("register");row=self.store.read(self.operation)
        original=row["request_hash"]
        for phase in ("adoption_prepared","adopting","adopted","failed"):
            row=self.store.project_host(self.operation,row["revision"],phase,code="rotation_rolled_back" if phase=="failed" else None)
        self.assertEqual(row["request_hash"],original);self.assertIsNone(self.store.status()["active_operation"])
        self.assertEqual(self.store.status()["blocked_fingerprint"],self.current.fingerprint)
