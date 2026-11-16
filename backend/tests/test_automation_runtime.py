"""AP08 bounded host policy; Docker/CIFS are doubles here, native proof is separate."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock


def host_module(name,filename):
    deployed=Path(__file__).parent.parent/"operator"/filename
    location=deployed if deployed.exists() else Path(__file__).resolve().parents[2]/"deploy"/filename
    spec=importlib.util.spec_from_file_location(name,location)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


host=host_module("ap08_processing","run-processing.py")
automatic=host_module("ap08_automatic","run-automation.py")
IMAGE="sha256:"+"a"*64


class AutomationRuntimeTests(unittest.TestCase):
    def queue(self):return dict(due=dict(inbox=False,corrections=False),last=None,active=None,not_before=0)

    def test_coalescing_alternation_crash_recovery_and_scope_cooldown(self):
        value=self.queue()
        for _ in range(50):value,_=host.queue_step(value,request="inbox")
        value,_=host.queue_step(value,request="corrections")
        value,mode=host.queue_step(value,start=True,now=100)
        self.assertEqual(mode,"inbox")
        # Restart recovers the active opportunity once, without an unbounded backlog.
        value,mode=host.queue_step(value,start=True,now=101)
        self.assertEqual(mode,"corrections")
        value,_=host.queue_step(value,complete=mode,not_before=500)
        value,mode=host.queue_step(value,start=True,now=499)
        self.assertIsNone(mode);self.assertTrue(value["due"]["inbox"])
        value,mode=host.queue_step(value,start=True,now=500)
        self.assertEqual(mode,"inbox")
        value,_=host.queue_step(value,complete=mode,ok=False,not_before=400)
        self.assertTrue(value["due"][mode]);self.assertEqual(value["not_before"],500)
        with self.assertRaises(ValueError):host.queue_step(dict(value,unexpected=True),start=True)

    def test_no_new_work_without_complete_quantum_reserve_or_during_backoff(self):
        for elapsed,retry,expected in ((0,0,1),(241,0,0),(0,2000,0)):
            with self.subTest(elapsed=elapsed,retry=retry):
                now=[0.0];calls=[]
                def coordinate(args,*_):
                    calls.append(args);now[0]+=elapsed
                    return dict(message_keys=["a"*64,"b"*64],retry_not_before=retry)
                runtime=SimpleNamespace(coordinator=coordinate,classifier=Mock())
                with tempfile.TemporaryDirectory() as directory:
                    @contextmanager
                    def working(**kwargs):yield directory
                    with patch.object(host,"Runtime",return_value=runtime),patch.object(host.tempfile,"TemporaryDirectory",working),\
                            patch.object(host.os,"chown",create=True),patch.object(host.os,"chmod"),\
                            patch.object(host.time,"monotonic",side_effect=lambda:now[0]),\
                            patch.object(host.time,"time",return_value=1000),\
                            patch.object(host,"handoff",return_value=dict(status="progress")) as handoff:
                        result=host.operate_locked("inbox",IMAGE,{},1,780)
                    self.assertEqual(result["quanta"],expected);self.assertEqual(handoff.call_count,expected)
                    self.assertEqual(calls[0],["select","--mode","inbox","--limit","50"])

    def test_both_automatic_entrypoints_use_the_same_fixed_batch_cap(self):
        self.assertEqual(host.AUTOMATIC_MAX_QUANTA,20)
        @contextmanager
        def lock(path):yield True
        with patch.object(host.os,"name","posix"),patch.object(host.os,"geteuid",return_value=0,create=True),\
                patch.object(host,"host_lock",lock),patch.object(host,"command",return_value=""),\
                patch.object(host,"draining",return_value=False),\
                patch.object(host,"scheduled_queue",side_effect=[({},None),({},"inbox"),({},None)]),\
                patch.object(host,"operate_locked",return_value=dict(ok=True)) as run:
            host.operate("inbox",IMAGE,{},1,scheduled_state="/state/schedule.json")
        self.assertEqual(run.call_args.args[3],host.AUTOMATIC_MAX_QUANTA)
        binding=SimpleNamespace(profile=lambda *args:{},ready=Mock())
        with patch.object(automatic.os,"name","posix"),patch.object(automatic.os,"geteuid",return_value=0,create=True),\
                patch.object(automatic,"load_processing",return_value=binding),\
                patch.object(host,"profile",return_value={}),patch.object(host,"operate",return_value=dict(ok=True)) as run:
            automatic.operate("inbox",dict(processing_profile="/private/profile",processing_image=IMAGE,processing_state="/state/schedule.json",
                runtime_profile="/private/runtime",public_origin="https://invoice.example.invalid"),host)
        self.assertEqual(run.call_args.args[3],host.AUTOMATIC_MAX_QUANTA)

    def test_manual_and_scheduled_entry_use_same_lock_and_do_not_work_when_busy(self):
        @contextmanager
        def busy(path):
            self.assertEqual(path,host.PROCESSING_LOCK);yield False
        for scheduled in (None,"/state/queue.json"):
            with patch.object(host.os,"name","posix"),patch.object(host.os,"geteuid",return_value=0,create=True),\
                    patch.object(host,"host_lock",busy),patch.object(host,"scheduled_queue") as queue,\
                    patch.object(host,"command") as command,patch.object(host,"operate_locked") as run:
                result=host.operate("inbox",IMAGE,{},scheduled_state=scheduled)
            self.assertTrue(result["deferred"]);command.assert_not_called();run.assert_not_called()
            self.assertEqual(queue.call_count,int(scheduled is not None))

    def test_cifs_reference_is_held_and_rejects_changed_mount_before_create(self):
        config=dict(processing_config="/private/config",storage_root="/mount/importer")
        source=SimpleNamespace(read_text=lambda **_:json.dumps(dict(expected_source="//files.example.invalid/importer")))
        with patch.object(host,"protected",return_value=source),patch.object(host,"open_directory",side_effect=[10,11]),\
                patch.object(host,"mount_identity",side_effect=[(1,2,3),(9,2,3)]),patch.object(host.os,"close") as close:
            with host.CifsBinding(config) as binding:
                self.assertEqual(binding.path,config["storage_root"])
                with self.assertRaisesRegex(ValueError,"processing_mount_changed"):binding.check()
                self.assertEqual(close.call_args_list[0].args,(11,))
            self.assertEqual(close.call_args_list[-1].args,(10,))
        runtime=host.Runtime.__new__(host.Runtime);runtime.image=IMAGE
        runtime.config=dict(networks=["isolated"],storage_gid=10001,db_host="db",db_name="synthetic",db_user="synthetic",
            graph_config="/config",graph_credential="/credential",processing_config="/processing",db_password="/password")
        binding=SimpleNamespace(path="/mount/importer",identity=(1,2,3),check=Mock(side_effect=ValueError("processing_mount_changed")))
        with patch.object(host,"command") as command,patch.object(runtime,"cleanup"):
            with self.assertRaisesRegex(ValueError,"processing_mount_changed"):
                runtime._coordinator(["select"],"/exchange",host.time.monotonic()+180,binding)
        command.assert_not_called()

    def test_notification_host_has_only_required_ro_secrets_and_exact_cleanup(self):
        calls=[];clean=[]
        @contextmanager
        def lock(path):yield True
        def command(args,timeout,**kwargs):
            calls.append((args,timeout))
            if args[0]=="image":return IMAGE
            if args[0]=="start":return 0,dict(ok=True,persisted=True)
            return ""
        fake=SimpleNamespace(host_lock=lock,command=command,CleanupFailure=host.CleanupFailure,draining=lambda:False,
            Runtime=SimpleNamespace(cleanup=lambda name,deadline,**kwargs:clean.append((name,deadline,kwargs))))
        config=dict(networks=["dbnet","egress"],db_host="db",db_name="synthetic",db_user="synthetic",
            graph_config="/graph",graph_credential="/credential",db_password="/dbpassword",storage_root="/must-not-bind")
        result=automatic.notify(dict(notification_image=IMAGE,notification_key="/notifykey",public_origin="https://invoice.example.invalid"),fake,config)
        self.assertTrue(result["ok"])
        create=next(args for args,_ in calls if args[0]=="create")
        mounts=[create[i+1] for i,item in enumerate(create) if item=="--mount"]
        self.assertEqual(len(mounts),4);self.assertTrue(all(item.endswith(",readonly") for item in mounts))
        self.assertFalse(any("/importer," in item or "LDAP" in item or "CONFIG_KEY" in item for item in create))
        self.assertEqual(create[-6:],[IMAGE,"python","-B","-m","app.notification_cli","automatic"])
        name=create[create.index("--name")+1]
        self.assertEqual(clean[0][0],name)
        self.assertEqual(clean[0][2],dict(list_seconds=3,remove_seconds=5))
        self.assertTrue(all(0<seconds<=85 for _,seconds in calls))
