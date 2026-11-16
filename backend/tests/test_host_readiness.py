"""B-R1: real peer checks with synthetic sockets and one virtual deadline."""
from contextlib import contextmanager,nullcontext
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import test_host_lifecycle as fixtures

runtime=fixtures.runtime
OLD=hashlib.sha256(b"old-leaf").hexdigest()
NEW=hashlib.sha256(b"new-leaf").hexdigest()


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.now=[0.0];self.sleeps=[];self.attempts=[]
        def sleep(seconds):self.sleeps.append(seconds);self.now[0]+=seconds
        clock=patch.object(runtime,"time",SimpleNamespace(monotonic=lambda:self.now[0],sleep=sleep))
        clock.start();self.addCleanup(clock.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.binding=dict(tls_root=str(self.root),peer_address="192.0.2.10",instance_id=fixtures.INSTANCE)

    @contextmanager
    def sockets(self,responses):
        pending=list(responses);last=pending[-1]
        def connect(address,timeout):
            nonlocal last
            self.attempts.append((self.now[0],timeout))
            if pending:last=pending.pop(0)
            if isinstance(last,Exception):raise last
            der,instance=last
            body=json.dumps(dict(status="ready",mode="journal",instance_id=instance)).encode()
            connection=SimpleNamespace(getpeercert=Mock(return_value=der),settimeout=Mock(),sendall=Mock(),
                recv=Mock(side_effect=[b"HTTP/1.0 200 OK\r\n\r\n"+body,b""]))
            return nullcontext(connection)
        context=SimpleNamespace(load_verify_locations=Mock(),wrap_socket=Mock(side_effect=lambda plain,**kwargs:nullcontext(plain)))
        with patch.object(runtime.socket,"create_connection",side_effect=connect),\
                patch.object(runtime.ssl,"SSLContext",return_value=context):
            yield
        self.assertTrue(all(call.kwargs["server_hostname"]=="invoice.example.invalid" for call in context.wrap_socket.call_args_list))

    def test_start_accepts_refused_then_ready_without_new_budget_or_source_mount(self):
        (self.root/"cert.pem").write_text("-----BEGIN CERTIFICATE-----\nbmV3LWxlYWY=\n-----END CERTIFICATE-----\n")
        fake=SimpleNamespace(host_lock=fixtures.acquired,draining=lambda:False)
        with self.sockets([ConnectionRefusedError("not listening"),(b"new-leaf",fixtures.INSTANCE)]),\
                patch.object(runtime,"gate",return_value=None),\
                patch.object(runtime,"inspect_container",return_value=dict(id="c"*64,state=dict(Running=True,Health=dict(Status="healthy")))),\
                patch.object(runtime,"current_release",return_value=("releases/current",self.root)),\
                patch.object(runtime,"Source") as source:
            value=runtime.start(self.binding,fixtures.ORIGIN,fake,3)
        self.assertTrue(value["ready"]);self.assertEqual(len(self.attempts),2)
        self.assertEqual(self.now[0],.5);source.assert_not_called()

    def adoption(self,responses,*,forward_failure=False,until=2,unconfirmed=False):
        current=["releases/old"];commands=[]
        def switch(root,old,target):self.assertEqual(current[0],old);current[0]=target
        def command(args,*a,**kw):
            commands.append(args)
            if forward_failure and current[0]=="releases/new" and args[-1]=="reload":raise ValueError("forward_reload_failed")
            return ""
        with self.sockets(responses),patch.object(runtime,"switch",side_effect=switch),\
                patch.object(runtime.os,"readlink",side_effect=lambda path:current[0]),patch.object(runtime,"sync_directory"):
            if unconfirmed:
                with self.assertRaisesRegex(RuntimeError,"tls_rollback_unconfirmed"):
                    runtime.adopt(self.binding,fixtures.ORIGIN,SimpleNamespace(command=command),until,
                        ("releases/old",OLD),"releases/new",NEW,fixtures.CONTAINER)
            elif forward_failure:
                with self.assertRaisesRegex(ValueError,"forward_reload_failed"):
                    runtime.adopt(self.binding,fixtures.ORIGIN,SimpleNamespace(command=command),until,
                        ("releases/old",OLD),"releases/new",NEW,fixtures.CONTAINER)
            else:
                value=runtime.adopt(self.binding,fixtures.ORIGIN,SimpleNamespace(command=command),until,
                    ("releases/old",OLD),"releases/new",NEW,fixtures.CONTAINER)
                self.assertTrue(value["changed"])
        return current[0],commands

    def test_forward_reload_waits_for_new_peer_without_repeating_reload(self):
        target,commands=self.adoption([(b"old-leaf",fixtures.INSTANCE),(b"new-leaf",fixtures.INSTANCE)])
        self.assertEqual(target,"releases/new");self.assertEqual(len(self.attempts),2)
        self.assertEqual(sum(args[-1]=="reload" for args in commands),1)
        self.assertEqual(self.now[0],.5);self.assertFalse(runtime.tls_pending(self.root).exists())

    def test_rollback_waits_for_original_peer_and_clears_only_after_confirmation(self):
        target,commands=self.adoption([(b"new-leaf",fixtures.INSTANCE),(b"old-leaf",fixtures.INSTANCE)],forward_failure=True)
        self.assertEqual(target,"releases/old");self.assertEqual(len(self.attempts),2)
        self.assertEqual(sum(args[-1]=="reload" for args in commands),2)
        self.assertFalse(runtime.tls_pending(self.root).exists());self.assertEqual(self.now[0],.5)

    def test_permanent_wrong_peer_exhausts_original_forward_and_rollback_windows(self):
        target,commands=self.adoption([(b"other-trusted-leaf",fixtures.INSTANCE)],until=1,unconfirmed=True)
        self.assertEqual(target,"releases/old");self.assertEqual(self.now[0],46)
        self.assertEqual(sum(args[-1]=="reload" for args in commands),2)
        self.assertTrue(runtime.tls_pending(self.root).exists())
        self.assertTrue(all(at<46 and timeout<=46-at for at,timeout in self.attempts))

    def test_permanent_wrong_instance_never_becomes_ready(self):
        with self.sockets([(b"new-leaf","44444444-4444-4444-4444-444444444444")]):
            with self.assertRaisesRegex(ValueError,"host_deadline"):
                runtime.wait_readiness(lambda:runtime.peer(self.binding,fixtures.ORIGIN,1,NEW),1)
        self.assertEqual(self.now[0],1);self.assertEqual(len(self.attempts),2)

    def test_read_time_counts_and_late_success_cannot_extend_deadline(self):
        calls=[]
        def check():
            calls.append(self.now[0]);self.now[0]+=2
            if len(calls)==1:raise ValueError("not ready")
            return True
        with self.assertRaisesRegex(ValueError,"host_deadline"):runtime.wait_readiness(check,3)
        self.assertEqual(calls,[0,2.5]);self.assertEqual(self.sleeps,[.5])
        self.assertEqual(self.now[0],4.5)
        check=Mock()
        with self.assertRaisesRegex(ValueError,"host_deadline"):runtime.wait_readiness(check,4.5)
        check.assert_not_called()
