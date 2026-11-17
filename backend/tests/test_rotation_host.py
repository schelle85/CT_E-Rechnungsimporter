"""C3b host ordering and negative guards; Docker/locks/cgroups are explicit doubles."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from uuid import uuid4

deployed=Path(__file__).parent.parent/"operator/run-rotation.py"
location=deployed if deployed.exists() else Path(__file__).parents[2]/"deploy/run-rotation.py"
spec=importlib.util.spec_from_file_location("rotation_host_test",location)
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


class HostOrderTests(unittest.TestCase):
    def fixture(self):
        result=host.Controller.__new__(host.Controller);result.until=time.monotonic()+30
        result.events=[];result.control=None;result.operation=str(uuid4());result.access=SimpleNamespace(fields=lambda:{})
        result.journal=Path(self.temp.name);result.gate_directory=result.journal
        result.images={};result.auto=dict(public_origin="https://test.invalid");result.binding={};result.processing={}
        record=dict(mode="allowed",epoch=1,boot_id="boot",release_hash=None)
        @contextmanager
        def session():yield
        @contextmanager
        def lock(path,**kwargs):
            self.assertEqual(record["mode"],"blocked");result.events.append("lock:"+path);yield True
        @contextmanager
        def exclusive(*args,**kwargs):
            self.assertIn("stopped",result.events);self.assertIn("quiet",result.events)
            result.events.append("exclusive");yield
        def block(*args,**kwargs):result.events.append("blocked");record.update(mode="blocked",epoch=2)
        result.writer=SimpleNamespace(session=session,binding=result.access,gate=SimpleNamespace(read=lambda:dict(record)),block=block,exclusive=exclusive)
        result.host=SimpleNamespace(host_lock=lock,PROCESSING_LOCK="processing",protected=lambda path:Path(path))
        result.write=lambda path,value:path.write_text(json.dumps(value))  # Explicit POSIX write-policy double.
        result.runtime=SimpleNamespace(LIFECYCLE_LOCK="lifecycle",inspect_container=lambda *a:dict(id=a[1]),wait_readiness=lambda fn,until:fn())
        result.model=SimpleNamespace(boot_id=lambda:"boot")
        result.recover_job=lambda **kw:result.events.append("recover-jobs")
        state=dict(phase="prepared",paused=False)
        def worker(command,operation=None,**values):
            result.events.append("worker:"+command)
            if command=="status":return dict(binding={},head=dict(active_operation=result.operation),host=state,core=dict(phase="registered"))
            if command=="register":return dict(core=dict(phase="registered"))
            raise AssertionError(command)
        result.worker=worker;result.drain=lambda op:result.events.append("drain")
        result.api=lambda:dict(Id="api")
        result.bound_api=lambda operation:result.api()
        def stop(api):result.events.append("stopped");return dict(stopped=True)
        result.stop=stop;result.no_other_graph_consumers=lambda api:result.events.append("quiet")
        return result

    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)

    def test_block_precedes_host_locks_quiet_precedes_exclusive_then_switch(self):
        controller=self.fixture()
        def switch(*args):
            self.assertEqual(controller.events[-1],"exclusive");controller.events.append("switch");return dict(ok=True)
        controller.switch=switch;controller.return_old=lambda *a:self.fail("unexpected rollback")
        self.assertTrue(controller.operate("run")["ok"])
        events=controller.events
        self.assertLess(events.index("blocked"),events.index("lock:lifecycle"))
        self.assertLess(events.index("lock:lifecycle"),events.index("lock:processing"))
        self.assertLess(events.index("lock:processing"),events.index("lock:/run/invoice-importer/notification.lock"))
        self.assertLess(events.index("quiet"),events.index("exclusive"))

    def test_switch_failure_uses_original_operation_for_bounded_return(self):
        controller=self.fixture()
        def switch(*args):raise ValueError("synthetic API recreate failure")
        controller.switch=switch
        def rollback(operation,before):
            self.assertEqual(operation,controller.operation);controller.events.append("rollback");return dict(ok=True,target="old")
        controller.return_old=rollback
        self.assertEqual(controller.operate("run")["target"],"old")
        self.assertIn("exclusive",controller.events)

    def test_unconfirmed_quiet_never_enters_exclusive_or_switch(self):
        controller=self.fixture()
        def fail(_):raise ValueError("synthetic child still alive")
        controller.no_other_graph_consumers=fail;controller.switch=lambda *a:self.fail("switch after failed quiet")
        with self.assertRaises(ValueError):controller.operate("run")
        self.assertNotIn("exclusive",controller.events)


class CgroupAndDrainTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        self.controller=host.Controller.__new__(host.Controller)

    def test_empty_process_list_with_populated_descendants_is_not_quiet(self):
        (self.path/"cgroup.procs").write_text("");(self.path/"cgroup.events").write_text("populated 1\nfrozen 0\n")
        with self.assertRaises(ValueError):self.controller.quiet(self.path)
        (self.path/"cgroup.events").write_text("populated 0\nfrozen 0\n")
        self.controller.quiet(self.path)

    def test_api_main_only_is_not_quiet_with_extra_child_or_frozen_group(self):
        (self.path/"cgroup.procs").write_text("12\n13\n");(self.path/"cgroup.events").write_text("populated 1\nfrozen 0\n")
        with self.assertRaises(ValueError):self.controller.quiet(self.path,main=12)
        (self.path/"cgroup.procs").write_text("12\n");self.controller.quiet(self.path,main=12)
        (self.path/"cgroup.events").write_text("populated 1\nfrozen 1\n")
        with self.assertRaises(ValueError):self.controller.quiet(self.path,main=12)

    def test_foreign_drain_is_preserved_and_only_own_identity_is_removed(self):
        path=self.path/"draining";path.write_text("foreign")
        @contextmanager
        def lock(*a,**k):yield True
        self.controller.until=time.monotonic()+5
        self.controller.host=SimpleNamespace(DRAIN_FILE=str(path),host_lock=lock)
        self.controller.runtime=SimpleNamespace(GATE_LOCK="gate",sync_directory=lambda _:None)
        self.controller.control=dict(owned_drain=dict(inode=1))
        self.controller.marker=lambda:dict(inode=2)
        self.controller.clear_drain();self.assertTrue(path.exists())
        self.controller.marker=lambda:dict(inode=1)
        self.controller.clear_drain();self.assertFalse(path.exists())


class ExecRecoveryTests(unittest.TestCase):
    def test_exec_recovery_blocks_early_but_waits_for_lifecycle_and_archives_no_early_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            c=host.Controller.__new__(host.Controller);c.journal=Path(directory);c.until=time.monotonic()+10
            c.access=SimpleNamespace(fields=lambda:{});operation=str(uuid4());name="invoice-rotation-"+uuid4().hex
            path=c.job_path(name);path.write_text(json.dumps(dict(kind="exec",name=name,operation_id=operation,
                container_id="c"*64,image="sha256:"+"b"*64)))
            lifecycle=threading.Lock();lifecycle.acquire();attempted=threading.Event();blocked=threading.Event()
            held=[];events=[];errors=[];record=dict(epoch=1,mode="allowed")
            c.write=lambda path,value:path.write_text(json.dumps(value))  # Real controller record, POSIX write-policy double.
            @contextmanager
            def lock(filename,**kwargs):
                self.assertNotIn(filename,held)
                if filename=="lifecycle":
                    attempted.set()
                    if not lifecycle.acquire(timeout=3):raise ValueError("fixture lifecycle timeout")
                held.append(filename);events.append("lock:"+filename)
                try:yield True
                finally:
                    held.remove(filename)
                    if filename=="lifecycle":lifecycle.release()
            @contextmanager
            def exclusive(*args,**kwargs):
                self.assertEqual(held,["lifecycle","processing","/run/invoice-importer/notification.lock"])
                self.assertIn("stopped-and-quiet",events);events.append("exclusive");yield
            def block(*args,**kwargs):record["epoch"]+=1;blocked.set();events.append("blocked")
            c.writer=SimpleNamespace(gate=SimpleNamespace(read=lambda:dict(record)),block=block,exclusive=exclusive)
            c.host=SimpleNamespace(protected=lambda value:Path(value),host_lock=lock,PROCESSING_LOCK="processing")
            c.runtime=SimpleNamespace(LIFECYCLE_LOCK="lifecycle",sync_directory=lambda _:None)
            c.drain=lambda op:events.append("drain");c.command=lambda *a,**k:"c"*64
            c.inspect=lambda *a:dict(Id="c"*64)
            def stop(item):
                self.assertEqual(held,["lifecycle","processing","/run/invoice-importer/notification.lock"])
                self.assertTrue(path.exists());events.append("stopped-and-quiet")
            c.stop=stop
            def run():
                try:c.recover_job()
                except BaseException as error:errors.append(error)
            thread=threading.Thread(target=run);thread.start()
            try:
                self.assertTrue(blocked.wait(2));self.assertTrue(attempted.wait(2))
                self.assertNotIn("stopped-and-quiet",events);self.assertTrue(path.exists())
            finally:lifecycle.release();thread.join(4)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[]);self.assertFalse(path.exists())
            self.assertLess(events.index("blocked"),events.index("lock:lifecycle"))
            self.assertLess(events.index("stopped-and-quiet"),events.index("exclusive"))

    def test_already_locked_recovery_never_reenters_host_or_graph_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            c=host.Controller.__new__(host.Controller);c.journal=Path(directory);c.access=SimpleNamespace(fields=lambda:{})
            operation=str(uuid4());name="invoice-rotation-"+uuid4().hex;path=c.job_path(name)
            path.write_text(json.dumps(dict(kind="exec",name=name,operation_id=operation,container_id="c"*64,image="sha256:"+"b"*64)))
            checked=[]
            c.writer=SimpleNamespace(gate=SimpleNamespace(read=lambda:dict(epoch=1,mode="blocked")),block=lambda *a,**k:None,
                _require=lambda **kw:checked.append(kw),exclusive=lambda *a,**k:self.fail("reentered graph lock"))
            c.write=lambda path,value:path.write_text(json.dumps(value))
            c.host=SimpleNamespace(protected=lambda value:Path(value),host_lock=lambda *a,**k:self.fail("reentered host lock"))
            c.runtime=SimpleNamespace(sync_directory=lambda _:None);c.recover_exec=lambda value:checked.append("quiet")
            c.recover_job(locked=True)
            self.assertEqual(checked,[dict(exclusive=True),"quiet"]);self.assertFalse(path.exists())
