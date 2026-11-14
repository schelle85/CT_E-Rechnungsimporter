import asyncio
from pathlib import Path
import os
import sys
import time
import unittest
from unittest.mock import patch
from app.notification_cli import arguments
from app.notification_model import NotificationError,OperationBudget
from app.notification_process import ENVIRONMENT,execute_notification,invoke,worker_environment
from notification_test_support import Fixture,INSTANCE,SCOPE

class ProcessTests(Fixture,unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        environment=patch.dict(os.environ,{"PYTHONPATH":os.pathsep.join(sys.path)})
        environment.start();self.addCleanup(environment.stop)

    async def test_real_child_main_thread_environment_and_bounded_output(self):
        before=time.monotonic()
        with patch.dict("os.environ",{name:"synthetic-forbidden" for name in
                ("CONFIG_KEY_FILE","LDAP_BIND_PASSWORD_FILE","LDAP_BOOTSTRAP_FILE","TLS_PRIVATE_KEY_FILE","HTTPS_PROXY","SYNTHETIC_FORBIDDEN")}):
            value,stopped=await invoke(dict(mode="where"),deadline=before+5,worker="notification_process_probe",cleanup_seconds=.2)
        self.assertTrue(stopped)
        self.assertTrue(value["main_thread"])
        self.assertEqual(value["forbidden_env"],[])
        self.assertLessEqual(value["deadline"],before+5)
        for mode in ("eof","oversize"):
            value,stopped=await invoke(dict(mode=mode),deadline=time.monotonic()+3,worker="notification_process_probe",cleanup_seconds=.2)
            self.assertTrue(stopped)
            self.assertIsNone(value)

    async def test_real_stuck_child_and_delayed_spawn_are_bounded_without_restart(self):
        start=time.monotonic()
        result,stopped=await invoke(dict(mode="sleep"),deadline=start+.8,worker="notification_process_probe",cleanup_seconds=.2)
        self.assertIsNone(result);self.assertTrue(stopped)
        self.assertLess(time.monotonic()-start,2)
        self.assertGreater(time.monotonic()-start,.5)
        original=asyncio.create_subprocess_exec
        spawned=[]
        ready=asyncio.Event()
        async def delayed(*args,**kwargs):
            await asyncio.sleep(.3)
            process=await original(*args,**kwargs);spawned.append(process);ready.set();return process
        with patch("app.notification_process.asyncio.create_subprocess_exec",side_effect=delayed):
            value,stopped=await invoke(dict(mode="sleep"),deadline=time.monotonic()+.2,
                worker="notification_process_probe",cleanup_seconds=.1)
        self.assertIsNone(value);self.assertFalse(stopped)
        await asyncio.wait_for(ready.wait(),2)
        self.assertEqual(len(spawned),1)
        await asyncio.wait_for(spawned[0].wait(),1)
        self.assertIsNotNone(spawned[0].returncode)

    async def test_cancellation_stops_the_existing_child(self):
        marker=Path(self.temp.name)/"started"
        task=asyncio.create_task(invoke(dict(mode="sleep",ready_file=str(marker)),deadline=time.monotonic()+5,
            worker="notification_process_probe",cleanup_seconds=.2))
        async def started():
            while not marker.exists():await asyncio.sleep(.01)
        await asyncio.wait_for(started(),2)
        task.cancel()
        result,stopped=await asyncio.wait_for(task,1)
        self.assertIsNone(result);self.assertTrue(stopped)

    async def test_eof_kill_and_durable_accepted_are_reconciled_without_resending(self):
        self.configure()
        key_file=Path(self.temp.name)/"synthetic.key";key_file.write_bytes(self.key)
        for mode,expected in (("unreserved-eof","prepared"),("reserve-eof","unknown"),
                ("post-eof","unknown"),("accept-eof","accepted"),("post-sleep","unknown")):
            with self.subTest(mode=mode):
                self.now[0]+=3601
                row=self.request_row()
                calls=[]
                async def runner(job,*,deadline):
                    calls.append(job["command"])
                    return await invoke(dict(job,mode=mode,database=str(self.database),key_file=str(key_file),
                        instance=INSTANCE,scope=SCOPE,now=self.now[0]),deadline=deadline,
                        worker="notification_process_probe",cleanup_seconds=.2)
                budget=OperationBudget(clock=time.monotonic,seconds=13)
                started=time.monotonic()
                result=await execute_notification(dict(command="send",slot_key=row["slot_key"]),budget=budget,runner=runner)
                self.assertLess(time.monotonic()-started,13)
                self.assertTrue(result["persisted"])
                self.assertEqual(result["receipts"][0]["state"],expected)
                self.assertEqual(calls,["send","readback"])
                if expected!="prepared":self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))

    async def test_database_lock_is_inside_the_child_budget(self):
        self.configure()
        row=self.request_row()
        key_file=Path(self.temp.name)/"synthetic.key";key_file.write_bytes(self.key)
        marker=Path(self.temp.name)/"started"
        with self.engine.connect() as lock:
            lock.exec_driver_sql("BEGIN IMMEDIATE")
            started=time.monotonic()
            value,stopped=await invoke(dict(command="send",mode="reserve-eof",keys=[row["slot_key"]],owner="a"*32,
                database=str(self.database),key_file=str(key_file),instance=INSTANCE,scope=SCOPE,now=self.now[0],ready_file=str(marker)),
                deadline=started+1.5,worker="notification_process_probe",cleanup_seconds=.2)
            self.assertIsNone(value);self.assertTrue(stopped)
            self.assertTrue(marker.is_file())
            self.assertLess(time.monotonic()-started,2.5)
            lock.rollback()
        self.assertEqual(self.store.read(row["slot_key"])["reservations"],0)

    async def test_readback_failure_never_claims_a_persisted_unknown_or_replays(self):
        calls=[]
        async def runner(job,*,deadline):
            calls.append(job["command"])
            return (dict(ok=True,receipts=[dict(state="accepted")]),True) if job["command"]=="send" else (None,True)
        result=await execute_notification(dict(command="send",slot_key="a"*64),
            budget=OperationBudget(clock=time.monotonic),runner=runner)
        self.assertFalse(result["persisted"])
        self.assertEqual(result["code"],"notification_status_unavailable")
        self.assertEqual(calls,["send","readback"])

    async def test_preflight_and_readback_use_same_absolute_total_budget(self):
        now=[0]
        budget=OperationBudget(clock=lambda:now[0])
        now[0]=25  # ASGI/CLI preflight already used part of the original80s.
        phases=[]
        async def runner(job,*,deadline):
            phases.append((job["command"],deadline-time.monotonic()))
            if job["command"]=="send":now[0]+=45;return None,True
            return dict(ok=True,receipts=[dict(state="unknown")]),True
        result=await execute_notification(dict(command="send",slot_key="a"*64),budget=budget,runner=runner)
        self.assertTrue(result["persisted"])
        self.assertLessEqual(phases[0][1],45.01)
        self.assertLessEqual(phases[1][1],5.01)
        self.assertEqual(budget.deadline,80)
        now[0]=71
        calls=[]
        async def forbidden(job,*,deadline):calls.append(job);return None,True
        result=await execute_notification(dict(command="send",slot_key="a"*64),budget=budget,runner=forbidden)
        self.assertEqual(calls,[])
        self.assertFalse(result["persisted"])

    async def test_request_lookup_after_eof_uses_original_uuid_version_without_create_replay(self):
        calls=[]
        async def runner(job,*,deadline):
            calls.append(job)
            if job["command"]=="request-test":return None,True
            return dict(ok=True,persisted=True,receipt=dict(state="prepared",slot_key="a"*64)),True
        request="11111111-1111-1111-1111-111111111111"
        result=await execute_notification(dict(command="request-test",request_id=request,expected_version=3),
            budget=OperationBudget(clock=time.monotonic),runner=runner)
        self.assertEqual([job["command"] for job in calls],["request-test","status"])
        self.assertEqual(calls[1]["expected_version"],3)
        self.assertEqual(calls[1]["request_id"],request)
        self.assertTrue(result["persisted"])

class BindingAndCliTests(unittest.TestCase):
    def test_operator_arguments_and_separate_container_allowlist(self):
        request="11111111-1111-1111-1111-111111111111"
        parsed=arguments(["request-test","--request-id",request,"--expected-version","0"])
        self.assertEqual(parsed,dict(command="request-test",request_id=request,expected_version=0))
        self.assertEqual(arguments(["dispatch"]),dict(command="dispatch",limit=1))
        self.assertEqual(arguments(["dispatch","--limit","5"])["limit"],5)
        candidates=(Path(__file__).resolve().parents[2]/"deploy/compose.notification.yaml",
            Path(__file__).resolve().parents[1]/"operator/compose.notification.yaml")
        compose=next(path for path in candidates if path.is_file()).read_text()
        import re
        targets=re.findall(r"target: (.+)",compose)
        self.assertEqual(len(targets),3)
        self.assertEqual(set(targets),
            {"/run/secrets/notification_key","/run/importer/graph.json","/run/secrets/graph_credential"})
        for forbidden in ("<<:","CONFIG_KEY_FILE","LDAP_","docker.sock","TLS_","privileged:"):
            self.assertNotIn(forbidden,compose)
        section=compose.split("    environment:\n",1)[1].split("    secrets:",1)[0]
        self.assertEqual(set(re.findall(r"^      ([A-Z_]+):",section,re.M)),
            {"DB_HOST","DB_NAME","DB_USER","DB_PASSWORD_FILE","NOTIFICATION_KEY_FILE","GRAPH_CONFIG_FILE","GRAPH_CREDENTIAL_FILE","PUBLIC_ORIGIN"})
        self.assertIn("secrets: [db_password]",compose)
        self.assertIn('read_only: true',compose)
        self.assertNotIn("CONFIG_KEY_FILE",ENVIRONMENT)
        initial=next(path.with_name("compose.notification-init.yaml") for path in candidates
            if path.with_name("compose.notification-init.yaml").is_file()).read_text()
        self.assertEqual(re.findall(r"target: (.+)",initial),["/run/importer/notification-init.json"])
        self.assertIn("read_only: true",initial)
        self.assertIn("create_host_path: false",initial)
