"""AP08 B policy/failure cases; OS/Docker/OpenSSL boundaries are explicit doubles."""
from contextlib import contextmanager,nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import test_automation_runtime as fixtures

runtime=fixtures.host_module("ap08_host_runtime","host-runtime.py")
host=fixtures.host
ORIGIN="https://invoice.example.invalid"
INSTANCE="33333333-3333-3333-3333-333333333333"
OLD="a"*64;NEW="b"*64;CONTAINER="c"*64


@contextmanager
def acquired(*args,**kwargs):yield True


def protected(path):
    path=Path(path);path.stat();return path


class LifecycleTests(unittest.TestCase):
    def test_spent_original_budget_cannot_start_processing_or_image_inspection(self):
        with patch.object(host.os,"name","posix"),patch.object(host.os,"geteuid",return_value=0,create=True),\
                patch.object(host,"command") as command,patch.object(host,"scheduled_queue") as queue:
            with self.assertRaisesRegex(ValueError,"processing_deadline"):
                host.operate("inbox",fixtures.IMAGE,{},scheduled_state="/state",deadline=host.time.monotonic()-1)
            with self.assertRaisesRegex(ValueError,"processing_deadline"):
                host.Runtime({},fixtures.IMAGE,deadline=host.time.monotonic()-1)
        command.assert_not_called();queue.assert_not_called()

    def test_start_role_cannot_select_a_migration_or_wrong_image(self):
        binding=dict(containers=dict(api=dict(name="synthetic-api",image=fixtures.IMAGE)))
        value=dict(id=CONTAINER,image=fixtures.IMAGE,state={},mounts=[],user="10001:10001",readonly=True,
            command=["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--no-server-header","--no-access-log"],entrypoint=None)
        fake=SimpleNamespace(command=Mock(return_value=(0,value)))
        self.assertEqual(runtime.inspect_container(binding,"api",fake,runtime.time.monotonic()+10)["id"],CONTAINER)
        for changed in (dict(command=["alembic","upgrade","head"]),dict(image="sha256:"+"f"*64),dict(entrypoint=["alembic"])):
            with self.subTest(changed=changed):
                fake.command.return_value=(0,dict(value,**changed))
                with self.assertRaises(ValueError):runtime.inspect_container(binding,"api",fake,runtime.time.monotonic()+10)

    def test_start_only_existing_ids_and_keeps_a_newer_drain_request(self):
        with tempfile.TemporaryDirectory() as directory:
            gate=Path(directory)/"draining";gate.write_bytes(b"old-request")
            fake=SimpleNamespace(DRAIN_FILE=str(gate),protected=protected,host_lock=acquired,
                command=Mock(return_value=""),draining=lambda:gate.exists())
            def inspect(binding,kind,*args):
                return dict(id={"db":"1","api":"2","nginx":"3"}[kind]*64,
                    state=dict(Running=False if kind=="db" and fake.command.call_count==0 else True,Health=dict(Status="healthy")))
            def ready(*args,**kwargs):gate.write_bytes(b"new-drain-request")
            with patch.object(runtime,"inspect_container",side_effect=inspect),patch.object(runtime,"ready",side_effect=ready),\
                    patch.object(runtime,"sync_directory"),patch.object(runtime,"Source") as source:
                result=runtime.start({},ORIGIN,fake,runtime.time.monotonic()+10)
            self.assertEqual(fake.command.call_args.args[0],["start","1"*64])
            self.assertEqual(fake.command.call_count,1)
            self.assertEqual(gate.read_bytes(),b"new-drain-request")
            self.assertTrue(result["ready"]);self.assertTrue(result["draining"])
            source.assert_not_called()

    def test_unready_database_stops_start_before_api_or_web(self):
        now=[0.0];seen=[]
        def inspect(binding,kind,*args):
            seen.append(kind);return dict(id="1"*64,state=dict(Running=True,Health=dict(Status="starting")))
        def sleep(value):now[0]+=value
        fake=SimpleNamespace(host_lock=acquired,command=Mock(),DRAIN_FILE="/not-present",protected=protected)
        with patch.object(runtime,"inspect_container",side_effect=inspect),patch.object(runtime,"gate",return_value=None),\
                patch.object(runtime,"time",SimpleNamespace(monotonic=lambda:now[0],sleep=sleep)):
            with self.assertRaisesRegex(ValueError,"host_deadline"):runtime.start({},ORIGIN,fake,3)
        self.assertEqual(set(seen),{"db"});fake.command.assert_not_called()

    def test_notifications_require_db_and_keep_running_when_api_is_unavailable(self):
        fake=SimpleNamespace()
        with patch.object(runtime,"inspect_container",return_value=dict(state=dict(Running=True,Health=dict(Status="healthy")))) as inspect,\
                patch.object(runtime,"peer") as peer,patch.object(runtime,"Source") as source:
            runtime.ready({},ORIGIN,fake,runtime.time.monotonic()+10,notifications=True)
        self.assertEqual([call.args[1] for call in inspect.call_args_list],["db"])
        peer.assert_not_called();source.assert_not_called()

    def test_drain_leaves_closed_gate_even_when_an_active_mode_cannot_drain(self):
        with tempfile.TemporaryDirectory() as directory:
            flag=Path(directory)/"draining"
            @contextmanager
            def lock(path,**kwargs):yield path!=host.PROCESSING_LOCK
            fake=SimpleNamespace(DRAIN_FILE=str(flag),PROCESSING_LOCK=host.PROCESSING_LOCK,
                host_lock=lock,controlled_directory=lambda path:None,command=Mock())
            with patch.object(runtime,"sync_directory"):
                with self.assertRaisesRegex(ValueError,"host_drain_busy"):
                    runtime.drain(fake,runtime.time.monotonic()+10)
            self.assertEqual(len(flag.read_bytes()),32);fake.command.assert_not_called()

    def test_closed_gate_blocks_manual_processing_notification_and_tls(self):
        with patch.object(host.os,"name","posix"),patch.object(host.os,"geteuid",return_value=0,create=True),\
                patch.object(host,"host_lock",acquired),patch.object(host,"draining",return_value=True),\
                patch.object(host,"command") as command:
            result=host.operate("inbox",fixtures.IMAGE,{})
        self.assertEqual(result["code"],"processing_draining");command.assert_not_called()
        fake=SimpleNamespace(host_lock=acquired,draining=lambda:True,command=Mock())
        self.assertEqual(fixtures.automatic.notify({},fake,{})["code"],"notification_draining")
        self.assertEqual(runtime.tls({},ORIGIN,"/missing",fake,runtime.time.monotonic()+20)["code"],"tls_draining")
        fake.command.assert_not_called()

    def test_drain_entry_does_not_load_missing_runtime_or_secret_profiles(self):
        fake_runtime=SimpleNamespace(drain=Mock(return_value=dict(ok=True)),profile=Mock())
        with patch.object(fixtures.automatic.os,"name","posix"),\
                patch.object(fixtures.automatic.os,"geteuid",return_value=0,create=True),\
                patch.object(fixtures.automatic,"load_processing",return_value=fake_runtime):
            self.assertTrue(fixtures.automatic.operate("drain",{},host)["ok"])
        fake_runtime.profile.assert_not_called();fake_runtime.drain.assert_called_once()


class AdoptionTests(unittest.TestCase):
    def run_adoption(self,failure=None):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        root=Path(directory.name);state=["releases/old"];commands=[];peers=[]
        def switch(path,previous,target):
            self.assertEqual(state[0],previous);state[0]=target
            if failure=="link-fsync" and target=="releases/new":raise OSError("synthetic sync failure")
        def command(args,*a,**kw):
            commands.append(args)
            if failure=="test" and state[0]=="releases/new" and args[-1]=="-t":raise ValueError("synthetic test failure")
            if failure=="reload" and state[0]=="releases/new" and args[-1]=="reload":raise subprocess.TimeoutExpired("synthetic",1)
            if failure=="rollback" and state[0]=="releases/old" and args[-1]=="reload":raise ValueError("synthetic rollback failure")
            return ""
        def peer(*args):
            peers.append(args[-1])
            if failure in {"peer","rollback"} and args[-1]==NEW:raise ValueError("tls_peer_changed")
            return args[-1]
        fake=SimpleNamespace(command=command)
        clock=[0.0]
        def sleep(seconds):clock[0]+=seconds
        with patch.object(runtime,"switch",side_effect=switch),patch.object(runtime.os,"readlink",side_effect=lambda path:state[0]),\
                patch.object(runtime,"sync_directory"),patch.object(runtime,"peer",side_effect=peer),\
                patch.object(runtime,"time",SimpleNamespace(monotonic=lambda:clock[0],sleep=sleep)):
            if failure:
                with self.assertRaises((ValueError,OSError,subprocess.TimeoutExpired,RuntimeError)) as caught:
                    runtime.adopt(dict(tls_root=str(root)),ORIGIN,fake,runtime.time.monotonic()+30,
                        ("releases/old",OLD),"releases/new",NEW,CONTAINER)
                if failure=="rollback":self.assertEqual(str(caught.exception),"tls_rollback_unconfirmed")
            else:
                result=runtime.adopt(dict(tls_root=str(root)),ORIGIN,fake,runtime.time.monotonic()+30,
                    ("releases/old",OLD),"releases/new",NEW,CONTAINER)
                self.assertTrue(result["changed"])
        return root,state[0],commands,peers

    def test_success_tests_reloads_exact_id_and_confirms_peer_before_clearing_fence(self):
        root,target,commands,peers=self.run_adoption()
        self.assertEqual(target,"releases/new")
        self.assertEqual(commands,[["exec",CONTAINER,"nginx","-t"],["exec",CONTAINER,"nginx","-s","reload"]])
        self.assertEqual(peers,[NEW]);self.assertFalse(runtime.tls_pending(root).exists())

    def test_config_failure_restores_old_link_without_reload(self):
        root,target,commands,peers=self.run_adoption("test")
        self.assertEqual(target,"releases/old");self.assertTrue(all(args[-1]=="-t" for args in commands))
        self.assertEqual(peers,[OLD]);self.assertFalse(runtime.tls_pending(root).exists())

    def test_reload_timeout_and_wrong_peer_restore_test_reload_and_read_old_peer(self):
        for failure in ("reload","peer"):
            with self.subTest(failure=failure):
                root,target,commands,peers=self.run_adoption(failure)
                self.assertEqual(target,"releases/old")
                self.assertEqual(commands[-2:],[["exec",CONTAINER,"nginx","-t"],["exec",CONTAINER,"nginx","-s","reload"]])
                self.assertEqual(peers[-1],OLD);self.assertFalse(runtime.tls_pending(root).exists())

    def test_failure_after_atomic_replace_is_also_rolled_back(self):
        root,target,commands,peers=self.run_adoption("link-fsync")
        self.assertEqual(target,"releases/old");self.assertEqual(peers,[OLD])
        self.assertFalse(runtime.tls_pending(root).exists())

    def test_unconfirmed_rollback_retains_the_exact_pending_operation(self):
        root,target,_,_=self.run_adoption("rollback")
        self.assertEqual(target,"releases/old")
        value=json.loads(runtime.tls_pending(root).read_text())
        self.assertEqual((value["previous"],value["target"],value["container"]),("releases/old","releases/new",CONTAINER))


class CandidatePolicyTests(unittest.TestCase):
    def check_candidate(self,*,wrong_key=False,wrong_chain=False,expires=False,verify_failure=False):
        now=runtime.time.time();calls=[]
        def openssl(args,until):
            args=list(map(str,args));calls.append(args)
            if args[0]=="pkcs12":
                path=Path(args[args.index("-out")+1])
                path.write_bytes((b"-----BEGIN PRIVATE KEY-----\nYWJj\n-----END PRIVATE KEY-----\n") if "-nocerts" in args else
                    b"-----BEGIN CERTIFICATE-----\nTGVhZg==\n-----END CERTIFICATE-----\n-----BEGIN CERTIFICATE-----\nQ2hhaW4=\n-----END CERTIFICATE-----\n")
            if args[0]=="pkey":
                if "-out" in args:Path(args[args.index("-out")+1]).write_bytes(b"synthetic-private-material")
                if "-pubout" in args:return b"wrong-key" if wrong_key else b"leaf-key"
            if args[0]=="x509" and "-pubkey" in args:
                return b"leaf-key" if b"TGVhZg==" in Path(args[args.index("-in")+1]).read_bytes() else b"chain-key"
            if args[0]=="verify":
                self.assertEqual(args[args.index("-purpose")+1],"sslserver")
                self.assertEqual(args[args.index("-verify_hostname")+1],"invoice.example.invalid")
                if verify_failure:raise subprocess.CalledProcessError(1,"synthetic verify")
            return b""
        def certificate(path,until):
            leaf=b"TGVhZg==" in Path(path).read_bytes()
            return dict(fingerprint=NEW if leaf else OLD,not_before=int(now)-10,expires=int(now)+(10 if expires and leaf else 86400),
                subject="CN=leaf" if leaf else "CN=wrong" if wrong_chain else "CN=issuer",issuer="CN=issuer")
        with tempfile.TemporaryDirectory() as directory,patch.object(runtime,"openssl",side_effect=openssl),\
                patch.object(runtime,"certificate",side_effect=certificate):
            path=Path(directory)/"candidate"
            if wrong_key or wrong_chain or expires or verify_failure:
                with self.assertRaises((ValueError,subprocess.CalledProcessError)):
                    runtime.candidate(b"synthetic-pfx",path,b"",True,"invoice.example.invalid",runtime.time.monotonic()+20)
            else:
                value=runtime.candidate(b"synthetic-pfx",path,b"",True,"invoice.example.invalid",runtime.time.monotonic()+20)
                self.assertEqual(value["fingerprint"],NEW)
                self.assertTrue((path/"fullchain.pem").read_bytes().startswith((path/"cert.pem").read_bytes()))
        for args in calls:
            if "-legacy" in args:self.assertEqual(args[0],"pkcs12")
        return calls

    def test_pair_chain_order_validity_and_verification_rejections(self):
        self.check_candidate()
        for case in ("wrong_key","wrong_chain","expires","verify_failure"):
            with self.subTest(case=case):self.check_candidate(**{case:True})

    def test_mount_exchange_is_rejected(self):
        fake=SimpleNamespace(open_directory=Mock(return_value=12),
            mount_identity=Mock(side_effect=[(2,2,2)]))
        source=runtime.Source(dict(source_root="/mount",expected_source="//certs.example.invalid/ssl"),fake)
        source.fd=11;source.identity=(1,1,1)
        with patch.object(runtime.os,"close") as close:
            with self.assertRaises(runtime.SourceChanged):source.check()
        close.assert_called_once_with(12)


class SourceCoordinatorTests(unittest.TestCase):
    def exercise(self,case):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/"releases/old").mkdir(parents=True)
            password=root/"password";password.write_bytes(b"\n")
            if case=="pending":runtime.tls_pending(root).write_text("{}")
            fake=SimpleNamespace(host_lock=acquired,draining=lambda:False,protected=protected,
                controlled_directory=lambda path:None)
            reads=[(b"synthetic-pfx","source-hash",(1,2,3))]*2
            if case=="changed-snapshot":reads[1]=(b"different","changed-hash",(1,2,4))
            source=SimpleNamespace(names=lambda:["candidate.pfx"],read=Mock(side_effect=reads),check=Mock())
            def candidate(snapshot,path,*args):
                path.mkdir()
                for name in ("cert.pem","chain.pem","fullchain.pem","privkey.pem"):(path/name).write_bytes(b"normalized-synthetic-material")
                return dict(directory=path,fingerprint=OLD if case=="noop" else NEW,not_before=200,expires=3000)
            with patch.object(runtime,"inspect_container",return_value=dict(id=CONTAINER,state=dict(Running=True))),\
                    patch.object(runtime,"current_release",return_value=("releases/old",root/"releases/old")),\
                    patch.object(runtime,"certificate",return_value=dict(fingerprint=OLD,not_before=100,expires=2000)),\
                    patch.object(runtime,"tls_profile",return_value=dict(password_file=str(password),legacy_rc2=True)),\
                    patch.object(runtime,"Source",side_effect=lambda *args:nullcontext(source)) as opened,\
                    patch.object(runtime,"candidate",side_effect=candidate),patch.object(runtime,"sync_directory"),\
                    patch.object(runtime.os,"chown",create=True) as chown,patch.object(runtime.os,"chmod") as chmod,\
                    patch.object(runtime,"peer",return_value=OLD) as peer,\
                    patch.object(runtime,"adopt",return_value=dict(ok=True,changed=True)) as adopt:
                if case in {"pending","changed-snapshot"}:
                    with self.assertRaises(RuntimeError):
                        runtime.tls(dict(tls_root=str(root)),ORIGIN,"/private/profile",fake,runtime.time.monotonic()+180)
                    adopt.assert_not_called();chown.assert_not_called()
                    if case=="pending":opened.assert_not_called()
                else:
                    result=runtime.tls(dict(tls_root=str(root)),ORIGIN,"/private/profile",fake,runtime.time.monotonic()+180)
                    self.assertTrue(result["ok"])
                    if case=="noop":
                        self.assertFalse(result["changed"]);adopt.assert_not_called();chown.assert_not_called()
                        self.assertEqual(peer.call_args.args[-1],OLD)
                        self.assertEqual(source.read.call_count,1)
                    else:
                        self.assertEqual(result["source_sha256"],"source-hash")
                        self.assertEqual(source.read.call_count,2)
                        self.assertEqual(chown.call_count,5)
                        self.assertTrue(all(call.args[1:]==(0,10002) for call in chown.call_args_list))
                        self.assertEqual([call.args[1] for call in chmod.call_args_list],[0o440]*4+[0o750])
                        self.assertTrue(adopt.call_args.args[5].startswith("releases/auto-"))
                        self.assertEqual(adopt.call_args.args[-2:],(NEW,CONTAINER))
                self.assertTrue((root/"releases/old").is_dir())

    def test_unchanged_candidate_is_noop_with_peer_readback(self):self.exercise("noop")
    def test_changed_source_snapshot_stops_before_release_or_reload(self):self.exercise("changed-snapshot")
    def test_pending_unconfirmed_operation_blocks_a_new_adoption(self):self.exercise("pending")
    def test_new_release_uses_only_the_four_files_and_existing_nginx_rights(self):self.exercise("new")


class PeerTests(unittest.TestCase):
    def peer(self,*,expected=None,instance=INSTANCE,status=200,verification_failure=False):
        der=b"synthetic-peer-certificate"
        payload=json.dumps(dict(status="ready",mode="journal",instance_id=instance)).encode()
        reply=b"HTTP/1.0 "+str(status).encode()+b" response\r\n\r\n"+payload
        connection=SimpleNamespace(getpeercert=Mock(return_value=der),settimeout=Mock(),sendall=Mock(),recv=Mock(side_effect=[reply,b""]))
        context=SimpleNamespace(load_verify_locations=Mock(),wrap_socket=Mock(
            side_effect=runtime.ssl.SSLCertVerificationError("synthetic verification failure") if verification_failure else None,
            return_value=nullcontext(connection)))
        with patch.object(runtime.ssl,"SSLContext",return_value=context),\
                patch.object(runtime.socket,"create_connection",return_value=nullcontext(object())) as connect:
            result=runtime.peer(dict(peer_address="192.0.2.10",instance_id=INSTANCE),ORIGIN,runtime.time.monotonic()+10,expected)
        self.assertEqual(context.wrap_socket.call_args.kwargs["server_hostname"],"invoice.example.invalid")
        self.assertEqual(connect.call_args.args[0],("192.0.2.10",443))
        self.assertEqual(result,hashlib.sha256(der).hexdigest())
        return result

    def test_exact_peer_and_ready_instance_are_both_checked(self):
        fingerprint=self.peer()
        self.peer(expected=fingerprint)
        for kwargs in (dict(expected=OLD),dict(instance="44444444-4444-4444-4444-444444444444"),dict(status=503)):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.peer(**kwargs)

    def test_certificate_verification_failure_cannot_return_a_peer_success(self):
        with self.assertRaises(runtime.ssl.SSLCertVerificationError):self.peer(verification_failure=True)
