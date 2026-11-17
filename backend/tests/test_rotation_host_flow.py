"""C3b integrated host/worker flow: real files/SQLite/crypto; explicit Docker/OS/probe doubles."""
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from app import rotation_worker as worker
from app.graph import GraphError
from app.notification_certificate import CertificateMaterial
from app.notification_model import CERTIFICATE_TOKEN,canonical,graph_scope,identity
from app.notification_schema007 import monitor
from app.rotation_schema008 import head,requests
from rotation_test_support import CONFIG,NOW
from test_rotation_host import host
import test_rotation_worker as worker_fixture
import test_automation_runtime as automation_fixture


class IntegratedHostTests(unittest.TestCase):
    def setUp(self):
        worker_fixture.WorkerTests.setUp(self)
        self.events=[];self.counter=0;self.failure=None;self.crash=False;self.crash_proof=False;self.new_pause=False
        self.api_present=True;self.compose_loss=None;self.infrastructure_ids=dict(db="d"*64,nginx="e"*64);self.nginx_running=True
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
            inspect_container=lambda binding,kind,*a:dict(id=self.infrastructure_ids[kind],state=dict(Running=self.nginx_running if kind=="nginx" else True)))
        self.current_boot=self.gate["boot_id"]
        self.stack.enter_context(patch("app.rotation_adoption.boot_id",side_effect=lambda:self.current_boot))
        c.model=SimpleNamespace(boot_id=lambda:self.current_boot,validate=lambda value:value)
        def block(operation,**kwargs):self.gate.update(mode="blocked",operation_id=operation,epoch=self.gate["epoch"]+1);self.events.append("blocked")
        @contextmanager
        def exclusive(*a,**k):
            self.assertTrue(not self.api_present or not self.api_data["State"]["Running"]);self.events.append("exclusive");yield
        def candidate(operation,*,pem_hash,fingerprint,**kwargs):
            self.gate.update(pem_hash=pem_hash,fingerprint=fingerprint,epoch=self.gate["epoch"]+1,admission_epoch=0,boot_id=self.current_boot)
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
        def inspect(name,image,uid):
            if not self.api_present or name not in {"api",self.api_data["Id"]} or image!=self.api_data["Image"]:raise ValueError("synthetic missing/changed container")
            return self.api_data
        c.inspect=inspect;c.image=lambda value:None  # Explicit image-inspect boundary double.
        def stop(item):self.events.append("stop");self.api_data["State"]["Running"]=False;return dict(container_id=item["Id"],stopped=True)
        c.stop=stop;c.recover_job=lambda **kw:self.events.append("recover-jobs");c.no_other_graph_consumers=lambda *a:self.events.append("quiet")
        c.cgroup=lambda item:root/"synthetic-cgroup";c.quiet=lambda *a,**k:self.events.append("quiet")
        def command(args,*a,**kwargs):
            if args[0]=="container":return "api" if self.api_present else ""
            if args[0]=="start":
                if args[1]==self.infrastructure_ids["nginx"]:
                    self.assertTrue(self.api_present);self.nginx_running=True;self.events.append("nginx-start");return ""
                self.assertEqual(args[1],self.api_data["Id"]);self.api_data["State"]["Running"]=True;return ""
            if args[0]=="exec" and args[1]==self.infrastructure_ids["nginx"]:
                self.assertTrue(self.api_present);self.events.append("nginx:"+" ".join(args[2:]));return ""
            if args[0]=="compose" and "config" in args:
                override=json.loads(Path(args[args.index("config")-1]).read_text())["services"]["api"]
                return 0,dict(services=dict(api=dict(override,user="10001:10001",read_only=True,cap_drop=["ALL"])))
            if args[0]=="compose" and "up" in args:
                override=json.loads(Path(args[args.index("up")-1]).read_text())["services"]["api"]
                self.api_present=False
                if self.compose_loss=="removed":
                    self.compose_loss=None;raise SystemExit("synthetic host loss after removing old API")
                self.counter+=1;self.api_data["Id"]=hashlib.sha256(str(self.counter).encode()).hexdigest()
                self.api_present=True;self.api_data["Config"]["Labels"]=override["labels"]
                self.api_data["Image"]=self.images["api"]
                self.api_data["State"]["Running"]=True;self.api_data["material"]=CertificateMaterial.parse(self.active.read_bytes())
                self.events.append("recreate-api")
                if self.compose_loss=="response":
                    self.compose_loss=None;raise SystemExit("synthetic lost Compose response after new API creation")
                return ""
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

    def fresh_controller(self):
        # A new Python object, reloading durable state; OS/Docker boundaries stay explicit doubles.
        result=copy.copy(self.controller);result.control=None
        profile=Path(result.auto["runtime_profile"])
        if profile.exists():result.binding=json.loads(profile.read_text())
        result.recreate_api=host.Controller.recreate_api.__get__(result)
        self.controller=result
        return result

    def archive_for(self,state):
        return self.root._read(self.operation+".host-checkpoint-"+str(state["revision"])+".json")

    def start_through_automation(self):
        c=self.fresh_controller();runtime=automation_fixture.host_module("rotation_start_runtime","host-runtime.py")
        automatic=automation_fixture.automatic;c.host.draining=lambda:Path(c.host.DRAIN_FILE).exists()
        def inspect(binding,kind,*args):
            self.events.append("start-inspect:"+kind)
            if kind=="api":
                item=c.inspect("api",binding["containers"]["api"]["image"],"10001:10001")
                return dict(id=item["Id"],state=item["State"])
            return dict(id=self.infrastructure_ids[kind],state=dict(Running=True,Health=dict(Status="healthy")))
        peers={"host-runtime.py":runtime,"run-rotation.py":SimpleNamespace(Controller=lambda **kw:c)}
        with patch.object(automatic,"load_processing",side_effect=lambda name:peers[name]),\
                patch.object(automatic,"os",SimpleNamespace(name="posix",geteuid=lambda:0)),patch.object(runtime,"inspect_container",side_effect=inspect),\
                patch.object(runtime,"profile",side_effect=lambda path,host:json.loads(Path(path).read_text())),\
                patch.object(runtime,"ready",side_effect=lambda *args:self.events.append("start-ready")),patch.object(runtime,"sync_directory"):
            return automatic.operate("start",c.auto,c.host)

    def exchange_interruption(self,window,*,bootstrap=False):
        c=self.controller
        if bootstrap:
            with self.engine.begin() as connection:
                connection.execute(requests.delete());connection.execute(head.update().values(active_operation=None))
        c.images["api"]="sha256:"+"d"*64;Path(c.auto["runtime_profile"]).write_text(json.dumps(c.binding))
        if window=="profile":
            def lose_host(*args):
                if self.counter:raise SystemExit("synthetic new API before profile save")
            c.runtime.ready=lose_host
        else:self.compose_loss=window
        with self.assertRaises(SystemExit):c.operate("bootstrap" if bootstrap else "run")
        c.runtime.ready=lambda *args:None
        operation=json.loads((c.journal/".bootstrap.json").read_text())["operation_id"] if bootstrap else self.operation
        intent=c.exchange(operation);original_nonce=intent["nonce"]
        self.assertEqual(intent["old"]["image"],"sha256:"+"b"*64)
        self.assertEqual(json.loads(Path(c.auto["runtime_profile"]).read_text())["containers"]["api"]["image"],"sha256:"+"b"*64)
        self.events.clear();result=self.start_through_automation()
        self.assertTrue(result["ok"]);self.assertEqual(result["graph_access"]["operation_id"],operation)
        self.assertEqual(self.controller.exchange(operation)["nonce"],original_nonce)
        self.assertEqual(self.counter,1);self.assertEqual(self.remote.adds,0 if bootstrap else 1)
        self.assertEqual(self.controller.exchange(operation)["preserved"],{kind:dict(id=value) for kind,value in self.infrastructure_ids.items()})
        self.assertLess(self.events.index("release-last"),self.events.index("start-inspect:api"))

    def test_exchange_removed_api_resumes_through_actual_start(self):self.exchange_interruption("removed")

    def test_exchange_created_api_before_profile_resumes_through_actual_start(self):self.exchange_interruption("profile")

    def test_exchange_lost_compose_response_resumes_through_actual_start(self):self.exchange_interruption("response")

    def test_bootstrap_exchange_created_api_resumes_through_actual_start(self):self.exchange_interruption("profile",bootstrap=True)

    def test_exchange_rejects_foreign_api_and_changed_bind_after_response_loss(self):
        self.compose_loss="response"
        with self.assertRaises(SystemExit):self.controller.operate("run")
        c=self.fresh_controller();saved=copy.deepcopy(self.api_data)
        for changed in ("label","bind","image"):
            self.api_data=copy.deepcopy(saved)
            if changed=="label":self.api_data["Config"]["Labels"]["invoice.rotation.exchange"]="f"*32
            elif changed=="bind":self.api_data["Mounts"][0]["RW"]=True
            else:self.api_data["Image"]="sha256:"+"f"*64
            with self.subTest(changed=changed),self.assertRaises(ValueError):c.operate("resume")
            self.assertEqual(self.gate["mode"],"blocked");self.assertEqual(self.remote.adds,1)

    def test_closed_old_return_survives_boot_and_general_start_without_new_request(self):
        # Separate bootstrap identity is deliberately present.
        (self.controller.journal/".bootstrap.json").write_text(json.dumps(dict(operation_id="99999999-9999-9999-9999-999999999999")))
        self.failure="api";self.controller.operate("run")
        original=self.root._read(self.operation+".host.json");request_hash=self.store.read(self.operation)["request_hash"]
        self.assertIsNone(self.store.status()["active_operation"])
        # A later ordinary certificate observation increments revision but retains the proof.
        with self.engine.begin() as connection:connection.execute(monitor.update().values(revision=monitor.c.revision+1))
        self.gate["mode"]="paused"
        self.current_boot="88888888-8888-8888-8888-888888888888"
        result=self.start_through_automation()
        self.assertTrue(result["ok"]);self.assertEqual(result["graph_access"]["target"],"old");self.assertTrue(result["graph_access"]["paused"])
        self.assertEqual(self.archive_for(original)["checkpoint"],original)
        self.assertIsNone(self.store.status()["active_operation"]);self.assertEqual(self.remote.adds,1)
        self.assertEqual(self.store.read(self.operation)["request_hash"],request_hash)
        self.assertEqual(self.gate["boot_id"],self.current_boot);self.assertEqual(self.active.read_bytes(),self.old_bytes)

    def test_closed_return_rejects_unbound_gate_or_changed_sql_completion(self):
        self.failure="api";self.controller.operate("run")
        c=self.fresh_controller();original=self.root._read(self.operation+".host.json");saved_gate=dict(self.gate)
        self.current_boot="88888888-8888-8888-8888-888888888888"
        for field,value in (("release_hash","f"*64),("scope_key","f"*64),("operation_id","99999999-9999-9999-9999-999999999999")):
            self.gate.update(saved_gate);self.gate[field]=value
            with self.subTest(field=field),self.assertRaises(GraphError):c.operate("resume")
            self.assertIsNone(self.store.status()["active_operation"]);self.assertEqual(self.root._read(self.operation+".host.json"),original)
        self.gate.update(saved_gate)
        with self.engine.begin() as connection:connection.execute(requests.update().values(error_code="rotation_rollback_unknown"))
        with self.assertRaises(GraphError):c.operate("resume")
        self.assertIsNone(self.store.status()["active_operation"]);self.assertEqual(self.remote.adds,1)

    def test_removed_api_start_defers_nginx_until_api_exists(self):
        self.nginx_running=False;self.exchange_interruption("removed")
        self.assertLess(self.events.index("recreate-api"),self.events.index("nginx-start"))

    def test_explicit_rollback_reconciles_written_unknown_proof_before_reset(self):
        self.crash_proof=True
        with self.assertRaises(SystemExit):self.controller.operate("run")
        original=self.root._read(self.operation+".host.json")
        result=self.fresh_controller().operate("rollback")
        archived=self.archive_for(original)
        self.assertEqual(archived["checkpoint"],original)
        self.assertEqual(archived["observed_proof"]["revision"],original["proof_intent"]["base_revision"]+1)
        self.assertTrue(result["ok"]);self.assertEqual(result["target"],"old")
        self.assertEqual(self.active.read_bytes(),self.old_bytes);self.assertEqual(self.remote.adds,1)

    def test_explicit_rollback_archives_complete_committed_seal_before_old_proof(self):
        self.controller.operate("run");original=self.root._read(self.operation+".host.json")
        result=self.fresh_controller().operate("rollback")
        self.assertEqual(self.archive_for(original)["checkpoint"],original)
        self.assertIsNotNone(original["seal"]);self.assertTrue(result["ok"])
        self.assertEqual(result["target"],"old");self.assertEqual(self.remote.adds,1)

    def test_explicit_rollback_with_unmatched_proof_keeps_original_intent(self):
        self.crash_proof=True
        with self.assertRaises(SystemExit):self.controller.operate("run")
        original=self.root._read(self.operation+".host.json");active=self.active.read_bytes()
        with self.engine.begin() as connection:connection.execute(monitor.update().values(revision=9))
        with self.assertRaises(GraphError):self.fresh_controller().operate("rollback")
        self.assertEqual(self.root._read(self.operation+".host.json"),original)
        self.assertEqual(self.active.read_bytes(),active);self.assertIsNone(self.archive_for(original))
        self.assertEqual(self.gate["mode"],"blocked");self.assertEqual(self.remote.adds,1)

    def test_prepared_journal_resumes_after_boot_with_same_candidate_and_pause(self):
        c=self.controller;c.worker("register",self.operation)
        original=c.worker("prepare",self.operation,images=self.images,paused=True,drain_identity=None)["host"]
        candidate=self.root.material(self.operation).pem
        self.current_boot="88888888-8888-8888-8888-888888888888"
        result=self.fresh_controller().operate("resume")
        self.assertTrue(result["ok"]);self.assertTrue(result["paused"])
        self.assertEqual(self.archive_for(original)["checkpoint"],original)
        self.assertEqual(self.active.read_bytes(),candidate);self.assertEqual(self.remote.adds,1)
        self.assertEqual(self.gate["boot_id"],self.current_boot)
        self.assertEqual(self.root._read(self.operation+".host.json")["boot_id"],self.current_boot)

    def test_prepared_same_boot_preserves_new_graph_pause_before_worker_transitions(self):
        c=self.controller;c.worker("register",self.operation)
        original=c.worker("prepare",self.operation,images=self.images,paused=False,drain_identity=None)["host"]
        candidate=self.root.material(self.operation).pem
        self.gate.update(mode="paused",admission_epoch=0)
        result=self.fresh_controller().operate("resume")
        saved=self.root._read(self.operation+".host.json")
        self.assertTrue(result["ok"]);self.assertTrue(result["paused"]);self.assertEqual(self.gate["mode"],"paused")
        self.assertTrue(saved["paused"]);self.assertEqual(saved["boot_id"],original["boot_id"])
        self.assertEqual(self.archive_for(original)["checkpoint"],original);self.assertEqual(self.remote.adds,1)
        self.assertEqual(result["operation_id"],self.operation);self.assertEqual(self.active.read_bytes(),candidate)
        self.assertEqual(worker.AdoptionJournal(self.root,self.access).state(self.operation),saved)

    def test_prepared_same_boot_without_new_pause_still_opens_after_confirmation(self):
        c=self.controller;c.worker("register",self.operation)
        c.worker("prepare",self.operation,images=self.images,paused=False,drain_identity=None)
        result=self.fresh_controller().operate("resume")
        self.assertTrue(result["ok"]);self.assertFalse(result["paused"]);self.assertEqual(self.gate["mode"],"allowed")
        self.assertFalse(worker.AdoptionJournal(self.root,self.access).state(self.operation)["paused"])
        self.assertEqual(self.remote.adds,1);self.assertEqual(result["operation_id"],self.operation)

    def test_prepared_pause_survives_block_then_lifecycle_busy_and_new_controller(self):
        c=self.controller;c.worker("register",self.operation)
        original=c.worker("prepare",self.operation,images=self.images,paused=False,drain_identity=None)["host"]
        candidate=self.root.material(self.operation).pem;self.gate.update(mode="paused")
        original_block=c.writer.block;original_lock=c.host.host_lock
        path=c.journal/(self.operation+".controller.json")
        def block(*args,**kwargs):
            saved=json.loads(path.read_text())
            self.assertTrue(saved["graph_paused"]);self.assertEqual(saved["operation_id"],self.operation)
            for name,value in self.access.fields().items():self.assertEqual(saved[name],value)
            return original_block(*args,**kwargs)
        @contextmanager
        def busy(path,**kwargs):
            if path==c.runtime.LIFECYCLE_LOCK:
                self.assertEqual(self.gate["mode"],"blocked");yield False
            else:
                with original_lock(path,**kwargs) as acquired:yield acquired
        with patch.object(c.writer,"block",side_effect=block),patch.object(c.host,"host_lock",side_effect=busy):
            with self.assertRaisesRegex(ValueError,"rotation_host_busy"):c.operate("resume")
        self.assertEqual(self.root._read(self.operation+".host.json"),original)
        result=self.fresh_controller().operate("resume")
        saved=worker.AdoptionJournal(self.root,self.access).state(self.operation)
        self.assertTrue(result["ok"]);self.assertTrue(result["paused"]);self.assertTrue(saved["paused"])
        self.assertEqual(self.gate["mode"],"paused");self.assertEqual(self.gate["release_hash"],saved["seal"])
        self.assertEqual(self.active.read_bytes(),candidate);self.assertEqual(self.remote.adds,1)
        self.assertEqual(result["operation_id"],self.operation);self.assertEqual(saved["boot_id"],original["boot_id"])

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

    def test_bootstrap_resume_accepts_verified_new_named_api_after_old_id_was_removed(self):
        with self.engine.begin() as connection:
            connection.execute(requests.delete());connection.execute(head.update().values(active_operation=None))
        c=self.controller;old_id=self.api_data["Id"]
        c.images["api"]="sha256:"+"d"*64
        Path(c.auto["runtime_profile"]).write_text(json.dumps(c.binding))
        def lose_host(*args):raise SystemExit("synthetic loss after compose up before runtime profile save")
        c.runtime.ready=lose_host
        with self.assertRaises(SystemExit):c.operate("bootstrap")
        self.assertNotEqual(self.api_data["Id"],old_id)
        # A fresh controller reads the still-old durable runtime profile.
        c.binding=json.loads(Path(c.auto["runtime_profile"]).read_text());c.control=None
        c.runtime.ready=lambda *args:None
        result=c.operate("resume")
        self.assertTrue(result["ok"]);self.assertEqual(self.remote.adds,0)
