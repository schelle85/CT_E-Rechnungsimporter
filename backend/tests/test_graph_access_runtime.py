"""C2 targeted integration. POSIX policies/flock are explicit C1 fixture doubles."""
from contextlib import contextmanager,nullcontext
import asyncio
import json
import os
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import httpx
from app import graph_access_runtime as runtime
from app.graph import GraphClient,GraphError
from app.graph_access import GraphAccessError
from app.notification_certificate import certificate_client
from app.notification_model import NotificationError,OperationBudget
from app.notification_process import execute_notification,invoke
from app.rotation_model import RotationBinding
from notification_test_support import CONFIG,INSTANCE
from test_graph_access import GateFixture,BINDING,PEM,FP


class BindingTests(unittest.TestCase):
    def profile(self):
        app="44444444-4444-4444-4444-444444444444"
        scope=RotationBinding(INSTANCE,CONFIG.tenant_id,CONFIG.client_id,app,CONFIG.mailbox).scope
        return dict(schema_version=1,source_commit="a"*40,deployment_id=str(uuid4()),
            instance_id=INSTANCE,application_id=app,scope_key=scope)

    def test_protected_profile_binds_actual_mailbox_app_and_db_instance(self):
        profile=self.profile()
        with patch.object(runtime,"protected_bytes",return_value=json.dumps(profile).encode()):
            bound=runtime.binding(CONFIG,expected_instance=INSTANCE)
            self.assertEqual(bound.scope_key,profile["scope_key"])
            with self.assertRaises(GraphError):runtime.binding(CONFIG,expected_instance=str(uuid4()))
        for change in ({"extra":1},{"schema_version":True},{"scope_key":"f"*64},{"application_id":str(uuid4())}):
            with self.subTest(change=change),patch.object(runtime,"protected_bytes",return_value=json.dumps(dict(profile,**change)).encode()):
                with self.assertRaises(GraphError):runtime.binding(CONFIG)

    def test_missing_or_duplicate_profile_never_opens_a_gate(self):
        for failure in (GraphError("graph_operator_file_unavailable"),b'{"schema_version":1,"schema_version":1}'):
            options=dict(side_effect=failure) if isinstance(failure,Exception) else dict(return_value=failure)
            with patch.object(runtime,"protected_bytes",**options),patch.object(runtime,"AccessGate") as gate:
                with self.assertRaises(GraphError):runtime.binding(CONFIG)
                gate.assert_not_called()

    def test_raw_client_denies_before_token_or_http(self):
        credential=Mock();calls=[]
        with httpx.Client(transport=httpx.MockTransport(lambda r:calls.append(r))) as http:
            client=GraphClient(CONFIG,credential,http)
            with patch("app.graph_deadline.request_deadline",side_effect=lambda *a,**k:nullcontext()):
                with self.assertRaises(GraphError) as raised:client.probe()
        self.assertEqual(raised.exception.code,"graph_access_closed")
        credential.get_token.assert_not_called();self.assertEqual(calls,[])


class BridgeTests(GateFixture):
    def setUp(self):
        super().setUp()
        self.material=SimpleNamespace(pem=PEM,fingerprint=FP)
        self.patches.enter_context(patch.object(runtime,"binding",return_value=BINDING))
        self.patches.enter_context(patch.object(runtime,"AccessGate",side_effect=lambda _:self.gate))

    def test_closed_real_factory_never_constructs_sdk_or_http(self):
        with patch("azure.identity.CertificateCredential") as sdk,patch("app.notification_certificate.httpx.Client") as http:
            with self.assertRaises(GraphError):
                with certificate_client(CONFIG,self.material):pass
        sdk.assert_not_called();http.assert_not_called();self.assertIsNone(runtime.current())

    def test_nested_factories_reuse_one_admission_and_proof_requires_context(self):
        self.allow()
        with self.assertRaises(GraphError):runtime.proof_access(CONFIG,self.material)
        with runtime.operation(CONFIG,self.material) as parent:
            with runtime.operation(CONFIG,self.material) as nested:self.assertIs(parent,nested)
            runtime.proof_access(CONFIG,self.material)
            with patch("azure.identity.CertificateCredential") as sdk:
                with certificate_client(CONFIG,self.material) as client:
                    self.assertIs(client.access,parent)
                    self.assertEqual(client.access_material,(PEM,FP))
                sdk.return_value.close.assert_called_once()
        self.assertIsNone(runtime.current());self.assertIsNone(parent.fd)

    def test_received_duplicate_lives_until_child_context_exit(self):
        self.allow()
        parent=self.gate.admit(PEM,FP)
        value=parent.export();fd=os.dup(value["fd"]);value["fd"]=fd
        try:
            with runtime.receive(value,CONFIG,self.material) as child:
                parent.close();child.check(PEM,FP)
                self.assertIs(runtime.current().permit,child)
            with self.assertRaises(OSError):os.fstat(fd)
        finally:parent.close()
        self.assertIsNone(runtime.current())

    def test_failed_binding_closes_received_fd_without_unlock(self):
        fd=os.open(self.path/"graph-access.lock",os.O_RDONLY)
        with patch.object(runtime,"binding",side_effect=GraphError("graph_access_binding_unavailable")):
            with self.assertRaises(GraphError):
                with runtime.receive(dict(fd=fd,snapshot={}),CONFIG,self.material):pass
        with self.assertRaises(OSError):os.fstat(fd)

    def test_candidate_probe_get_cannot_publish_ap07_proof_or_spawn_worker(self):
        with self.writer.session():
            with self.writer.exclusive(self.operation,expected_epoch=1,until=10**12):
                secret,state=self.writer.issue_probe(self.operation,expected_epoch=1,purpose="candidate-read",
                    consumer_role="candidate",consumer_id="e"*64)
        with runtime.host_probe(CONFIG,self.material,secret,operation_id=self.operation,epoch=state["epoch"],
                purpose="candidate-read",consumer_role="candidate",consumer_id="e"*64) as permit:
            permit.check(PEM,FP)
            with self.assertRaises(GraphError):runtime.proof_access(CONFIG,self.material)
            with self.assertRaises(GraphError):runtime.transfer()

    def test_only_finalization_grant_allows_bound_proof(self):
        with self.writer.session():
            with self.writer.exclusive(self.operation,expected_epoch=1,until=10**12):
                secret,state=self.writer.issue_probe(self.operation,expected_epoch=1,purpose="finalize-proof",
                    consumer_role="notifications",consumer_id="e"*64)
        with runtime.host_probe(CONFIG,self.material,secret,operation_id=self.operation,epoch=state["epoch"],
                purpose="finalize-proof",consumer_role="notifications",consumer_id="e"*64) as permit:
            runtime.proof_access(CONFIG,self.material)
            with self.assertRaises(GraphAccessError):permit.check(PEM,FP,method="POST")

    def test_spawn_pickle_duplicates_only_inside_spawning_reducer(self):
        self.allow()
        with self.gate.admit(PEM,FP) as permit,patch("multiprocessing.reduction.DupFd",create=True) as duplicate:
            value=runtime.ChildAccess(permit.export())
            duplicate.assert_not_called()
            restore,args=value.__reduce__()
            duplicate.assert_called_once_with(permit.fd)
            args[0].detach.return_value=72
            self.assertEqual(restore(*args),dict(fd=72,snapshot=permit.snapshot))


class ProcessBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_parent_admission_spans_send_and_durable_readback(self):
        events=[]
        @contextmanager
        def admit(_):
            events.append("admit")
            try:yield
            finally:events.append("release")
        async def runner(job,*,deadline):
            self.assertNotIn("release",events);events.append(job["command"])
            return dict(ok=True,receipts=[dict(state="accepted")]),True
        with patch.object(runtime,"notification_operation",side_effect=admit):
            result=await execute_notification(dict(command="send",slot_key="a"*64),
                budget=OperationBudget(clock=time.monotonic),runner=runner)
        self.assertTrue(result["ok"]);self.assertEqual(events,["admit","send","readback","release"])

    async def test_cancellation_closes_parent_after_runner_cleanup(self):
        events=[]
        @contextmanager
        def admit(_):
            try:yield
            finally:events.append("release")
        async def runner(job,*,deadline):
            try:raise asyncio.CancelledError()
            finally:events.append("runner-cleanup")
        with patch.object(runtime,"notification_operation",side_effect=admit):
            with self.assertRaises(asyncio.CancelledError):
                await execute_notification(dict(command="send",slot_key="a"*64),
                    budget=OperationBudget(clock=time.monotonic),runner=runner)
        self.assertEqual(events,["runner-cleanup","release"])

    async def test_closed_parent_never_calls_runner_or_reserves(self):
        runner=Mock()
        with patch.object(runtime.GraphConfig,"load",side_effect=GraphError("graph_operator_file_unavailable")):
            with self.assertRaises(GraphError):
                await execute_notification(dict(command="send",slot_key="a"*64),
                    budget=OperationBudget(clock=time.monotonic),runner=runner)
        runner.assert_not_called()

    async def test_job_cannot_supply_parent_transfer(self):
        with self.assertRaises(NotificationError):
            await invoke(dict(command="status",_graph_access=dict(fd=99)),deadline=time.monotonic()+5)

    async def test_subprocess_receives_only_server_fd_and_closes_before_parent_release(self):
        events=[];captured={}
        class Input:
            def write(self,body):captured["body"]=json.loads(body)
            async def drain(self):pass
            def close(self):pass
        class Output:
            done=False
            async def read(self,_):
                if self.done:return b""
                self.done=True;return b'{"ok":true}'
        class Process:
            returncode=0
            stdin=Input();stdout=Output()
            async def wait(self):events.append("child-stopped")
        async def spawn(*args,**kwargs):captured.update(kwargs);return Process()
        transfer=dict(fd=42,snapshot={"synthetic":"snapshot"})
        with patch.object(runtime,"transfer",return_value=transfer),patch(
                "app.notification_process.asyncio.create_subprocess_exec",side_effect=spawn):
            result,stopped=await invoke(dict(command="status"),deadline=time.monotonic()+5)
        self.assertTrue(stopped);self.assertTrue(result["ok"])
        self.assertEqual(captured["pass_fds"],(42,))
        self.assertEqual(captured["body"]["_graph_access"],transfer)
        self.assertTrue(events)
