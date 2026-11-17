"""C3b integrated host/worker flow: real files/SQLite/crypto; explicit Docker/OS/probe doubles."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from app import rotation_worker as worker
from app.notification_certificate import CertificateMaterial
from app.notification_model import CERTIFICATE_TOKEN,canonical,graph_scope,identity
from app.notification_schema007 import monitor
from app.rotation_schema008 import head,requests
from rotation_test_support import CONFIG,NOW
from test_rotation_host import host
import test_rotation_worker as worker_fixture


class IntegratedHostTests(unittest.TestCase):
    def setUp(self):
        worker_fixture.WorkerTests.setUp(self)
        self.events=[];self.counter=0;self.failure=None;self.crash=False;self.crash_proof=False;self.new_pause=False
        root=Path(self.temp.name);self.active=root/"active.pem";self.active.write_bytes(self.current.pem)
        self.old_bytes=self.current.pem
        c=host.Controller.__new__(host.Controller);self.controller=c;c.until=time.monotonic()+600
        c.journal=root;c.gate_directory=root;c.access=self.access;c.images=self.images;c.control=None
        c.auto=dict(public_origin="https://test.invalid",runtime_profile=str(root/"runtime.json"),notification_key=str(root/"notification.key"))
        c.binding=dict(instance_id=self.access.instance_id,containers={kind:dict(name=kind,image=self.images["api"]) for kind in ("api","db","nginx")})
        c.processing=dict(graph_credential=str(self.active),graph_config=str(root/"graph.json"),db_password=str(root/"db.key"),
            processing_config=str(root/"processing.json"),storage_gid=10001,networks=["synthetic"],db_host="db",db_name="synthetic",db_user="synthetic")
        c.binding_file=root/"binding.json";c.gate_directory=root/"gate";c.gate_directory.mkdir()
        (c.gate_directory/"graph-access.json").write_text("{}")
        c.profile=dict(compose_env=str(root/"compose.env"),compose_files=[str(root/"compose.json")]);c.compose_directory=root
        for path in (c.binding_file,Path(c.auto["notification_key"]),Path(c.profile["compose_env"]),Path(c.profile["compose_files"][0])):path.write_text("synthetic")
        self.gate=dict(**self.access.fields(),mode="allowed",epoch=1,admission_epoch=1,boot_id="77777777-7777-7777-7777-777777777777",
            operation_id=self.operation,release_hash=None,**worker.metadata(self.current))
        @contextmanager
        def session(*a,**k):yield True
        @contextmanager
        def lock(path,**kwargs):self.events.append("lock:"+path);yield True
        @contextmanager
        def cifs(config):yield SimpleNamespace(check=lambda:self.events.append("cifs-check"))
        c.host=SimpleNamespace(protected=lambda path:Path(path),controlled_directory=lambda path:Path(path),host_lock=lock,
            PROCESSING_LOCK="processing",DRAIN_FILE=str(root/"draining"),CifsBinding=cifs)
        c.runtime=SimpleNamespace(LIFECYCLE_LOCK="lifecycle",GATE_LOCK="gate",sync_directory=lambda path:None,
            wait_readiness=lambda fn,until:fn(),ready=lambda *a:self.events.append("ready"),
            inspect_container=lambda binding,kind,*a:dict(id=kind))
        c.model=SimpleNamespace(boot_id=lambda:self.gate["boot_id"],validate=lambda value:value)
        def block(operation,**kwargs):self.gate.update(mode="blocked",operation_id=operation,epoch=self.gate["epoch"]+1);self.events.append("blocked")
        @contextmanager
        def exclusive(*a,**k):
            self.assertFalse(self.api_data["State"]["Running"]);self.events.append("exclusive");yield
        def candidate(operation,*,pem_hash,fingerprint,**kwargs):
            self.gate.update(pem_hash=pem_hash,fingerprint=fingerprint,epoch=self.gate["epoch"]+1,admission_epoch=0)
        def release(operation,*,release_hash,pause,**kwargs):
            state=self.root._read(operation+".host.json")
            if state is not None:
                self.assertEqual(state["phase"],"committed");self.assertEqual(state["seal"],release_hash)
                self.assertEqual(self.store.read(operation)["state"],"adopted")
            else:self.assertEqual(json.loads((root/".bootstrap.json").read_text())["seal"],release_hash)
            self.events.append("release-last");self.gate.update(mode="paused" if pause else "allowed",release_hash=release_hash)
        c.writer=SimpleNamespace(session=session,binding=self.access,gate=SimpleNamespace(read=lambda:dict(self.gate)),block=block,
            exclusive=exclusive,candidate=candidate,release=release,_require=lambda **kwargs:None)
        self.api_data=dict(Id="c"*64,Name="/api",Image=self.images["api"],Config=dict(Cmd=host.API_COMMAND,Entrypoint=None),
            HostConfig=dict(Init=False),State=dict(Running=True,Pid=10,Health=dict(Status="healthy")),
            Mounts=[dict(Destination=target,Source=source,RW=False,Type="bind") for target,source in {
                "/run/importer/graph.json":c.processing["graph_config"],"/run/secrets/graph_credential":str(self.active),
                "/run/importer/graph-access-binding.json":str(c.binding_file),"/run/importer/operations/graph-access":str(c.gate_directory),
                "/run/secrets/notification_key":c.auto["notification_key"]}.items()],material=self.current)
        c.inspect=lambda *a:self.api_data
        def stop(item):self.events.append("stop");self.api_data["State"]["Running"]=False;return dict(container_id=item["Id"],stopped=True)
        c.stop=stop;c.recover_job=lambda:self.events.append("recover-jobs");c.no_other_graph_consumers=lambda *a:self.events.append("quiet")
        c.cgroup=lambda item:root/"synthetic-cgroup";c.quiet=lambda *a,**k:self.events.append("quiet")
        def command(args,*a,**kwargs):
            if args[0]=="container":return "api"
            if args[0]=="compose" and "config" in args:
                return 0,dict(services=dict(api=dict(image=self.images["api"],user="10001:10001",read_only=True,cap_drop=["ALL"])))
            if args[0]=="compose" and "up" in args:
                self.counter+=1;self.api_data["Id"]=hashlib.sha256(str(self.counter).encode()).hexdigest()
                self.api_data["State"]["Running"]=True;self.api_data["material"]=CertificateMaterial.parse(self.active.read_bytes())
                self.events.append("recreate-api");return ""
            raise AssertionError(args)
        c.command=command
        def execute(command,operation=None,**values):
            self.current=CertificateMaterial.parse(self.active.read_bytes())
            return worker.execute(dict(command=command,operation_id=operation,**values),time.monotonic()+70)
        c.worker=execute
        def probe(operation,role,purpose,pem,*,api=None,before=None):
            material=api["material"] if api is not None else CertificateMaterial.parse(Path(pem).read_bytes())
            self.assertEqual(material.fingerprint,self.gate["fingerprint"])
            if self.failure==role and material.pem!=self.old_bytes:
                self.failure=None;raise ValueError("synthetic new consumer auth failed")
            if self.new_pause and role=="api" and purpose=="consumer-read":
                Path(c.host.DRAIN_FILE).write_text("new-operator-pause");self.new_pause=False
            self.gate["epoch"]+=2;epoch=self.gate["epoch"]
            cid=api["Id"] if api is not None else hashlib.sha256((role+purpose+str(epoch)).encode()).hexdigest()
            outer=dict(container_id=cid,image=self.images["api" if role=="api" else "notifications" if role=="candidate" else role],probe=None)
            if before is not None:before(outer,epoch)
            proof_revision=proof_at=None
            if purpose=="finalize-proof":
                scope=graph_scope(CONFIG.tenant_id,CONFIG.client_id,CONFIG.mailbox);key=identity([scope,"certificate",CERTIFICATE_TOKEN])
                with self.engine.begin() as connection:
                    row=connection.execute(sa.select(monitor).where(monitor.c.monitor_key==key)).mappings().first()
                    proof_revision=(row["revision"] if row else 0)+1;proof_at=NOW
                    values=dict(revision=proof_revision,updated_at=NOW,payload=canonical(dict(proof=dict(fingerprint=material.fingerprint,scope_key=scope,at=NOW))))
                    if row:connection.execute(monitor.update().where(monitor.c.monitor_key==key).values(**values))
                    else:connection.execute(monitor.insert().values(monitor_key=key,scope_key=scope,kind="certificate",**values))
                if self.crash_proof:self.crash_proof=False;raise SystemExit("synthetic host loss after DB proof")
            receipt=dict(ok=True,code="graph_probe_verified",**self.access.fields(),operation_id=operation,epoch=epoch,purpose=purpose,
                consumer_role=role,consumer_id=hashlib.sha256(cid.encode()).hexdigest(),fingerprint=material.fingerprint,
                pem_hash=hashlib.sha256(material.pem).hexdigest(),at=NOW,proof_revision=proof_revision,proof_at=proof_at)
            receipt["receipt_hash"]=identity(receipt);outer["probe"]=receipt;self.events.append("probe:"+role+":"+purpose)
            return outer
        c.probe=probe
        self.stack.enter_context(patch.object(host.os,"fchown",create=True))
        gate=SimpleNamespace(read=lambda:dict(self.gate),_bound=lambda value:None,_material=lambda *a:None)
        self.stack.enter_context(patch("app.graph_access.AccessGate",return_value=gate))
        original_recreate=c.recreate_api
        def recreate(operation):
            if self.crash:self.crash=False;raise SystemExit("synthetic host loss after file activation")
            return original_recreate(operation)
        c.recreate_api=recreate

    def test_complete_switch_recreates_file_bind_then_commits_before_open(self):
        result=self.controller.operate("run")
        self.assertTrue(result["ok"]);self.assertEqual(result["target"],"new")
        self.assertNotEqual(self.active.read_bytes(),self.old_bytes);self.assertEqual(self.remote.adds,1)
        self.assertEqual(self.store.read(self.operation)["state"],"overlap")
        self.assertLess(self.events.index("recreate-api"),self.events.index("probe:api:consumer-read"))
        self.assertEqual(self.events.count("release-last"),1)
        self.assertLess(max(index for index,event in enumerate(self.events) if event.startswith("probe:")),self.events.index("release-last"))
        self.assertFalse(Path(self.controller.host.DRAIN_FILE).exists())

    def test_failed_new_consumer_restores_old_bytes_and_proves_old_consumers(self):
        self.failure="api";result=self.controller.operate("run")
        self.assertTrue(result["ok"]);self.assertEqual(result["target"],"old")
        self.assertEqual(self.active.read_bytes(),self.old_bytes);self.assertEqual(self.remote.adds,1)
        self.assertEqual(self.store.read(self.operation)["state"],"failed");self.assertIsNone(self.store.status()["active_operation"])
        self.assertEqual(self.gate["fingerprint"],CertificateMaterial.parse(self.old_bytes).fingerprint)

    def test_host_loss_after_replace_resumes_same_candidate_without_second_add(self):
        self.crash=True
        with self.assertRaises(SystemExit):self.controller.operate("run")
        candidate=self.active.read_bytes();self.assertNotEqual(candidate,self.old_bytes);self.assertEqual(self.gate["mode"],"blocked")
        result=self.controller.operate("resume")
        self.assertTrue(result["ok"]);self.assertEqual(result["target"],"new")
        self.assertEqual(self.active.read_bytes(),candidate);self.assertEqual(self.remote.adds,1)

    def test_lost_proof_response_is_read_reconciled_before_resume_without_second_add(self):
        self.crash_proof=True
        with self.assertRaises(SystemExit):self.controller.operate("run")
        state=self.root._read(self.operation+".host.json")
        self.assertEqual(state["phase"],"proof_unknown")
        original_intent=state["proof_intent"]
        result=self.controller.operate("resume")
        self.assertTrue(result["ok"]);self.assertEqual(self.remote.adds,1)
        archived=[json.loads(path.read_bytes()) for path in self.root.directory.glob("*.host-checkpoint-*.json")]
        self.assertTrue(any(value["checkpoint"]["proof_intent"]==original_intent for value in archived))

    def test_bootstrap_recreates_guarded_consumers_without_add_and_preserves_graph_pause(self):
        with self.engine.begin() as connection:
            connection.execute(requests.delete());connection.execute(head.update().values(active_operation=None))
        self.gate.update(mode="paused",admission_epoch=0)
        result=self.controller.operate("bootstrap")
        self.assertTrue(result["ok"]);self.assertTrue(result["paused"])
        self.assertEqual(self.gate["mode"],"paused");self.assertEqual(self.remote.adds,0)
        self.assertEqual(self.active.read_bytes(),self.old_bytes)

    def test_new_operator_automation_pause_is_retained_during_successful_adoption(self):
        self.new_pause=True;result=self.controller.operate("run")
        self.assertTrue(result["ok"]);self.assertEqual(result["target"],"new");self.assertEqual(self.remote.adds,1)
        self.assertEqual(Path(self.controller.host.DRAIN_FILE).read_text(),"new-operator-pause")
