"""C collector/receipt contract. Linux commands, metadata and mounts are explicit doubles."""
from contextlib import contextmanager,ExitStack
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch,mock_open
from app import operations_status as model
import test_automation_runtime as fixtures
from operations_test_support import SOURCE,DEPLOYMENT,INSTANCE,BOOT,NOW

ops=fixtures.host_module("ap08_operations_host","operations-host.py")
runtime=fixtures.host_module("ap08_operations_runtime","host-runtime.py")


@contextmanager
def acquired(*args,**kwargs):yield True


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/"cert.pem").write_text("-----BEGIN CERTIFICATE-----\nbGVhZg==\n-----END CERTIFICATE-----\n")
        self.cfg=dict(source_commit=SOURCE,deployment_id=DEPLOYMENT,result_directory=str(self.root),output_directory=str(self.root/"public"))
        self.automation=dict(runtime_profile="runtime",public_origin="https://invoice.example.invalid",processing_profile="processing",tls_profile="tls",processing_state=str(self.root/"queue.json"))
        self.binding=dict(instance_id=INSTANCE,tls_root=str(self.root),peer_address="192.0.2.10",containers={key:dict(name="synthetic-"+key,image=fixtures.IMAGE) for key in ("db","api","nginx")})
        self.units={ops.START:dict(LoadState="loaded",ActiveState="active",SubState="exited",Result="success",ExecMainStartTimestamp="@"+str(NOW-30))}
        for name in ops.SERVICES:
            self.units[ops.SERVICES[name]]=dict(LoadState="loaded",ActiveState="inactive",SubState="dead",Result="success",ExecMainStatus="0",ExecMainStartTimestamp="@"+str(NOW-30))
            self.units[ops.TIMERS[name]]=dict(LoadState="loaded",ActiveState="active",TimersCalendar="{ OnCalendar="+ops.CALENDARS[name]+" ; next_elapse=@"+str(NOW+60)+" }",Triggers=ops.SERVICES[name],NextElapseUSecRealtime="@"+str(NOW+60))
        for mode in ("start",*ops.SERVICES):self.receipt(mode,"ok")
        self.values=[]
        for kind in ("db","api","nginx"):
            self.values.append(dict(id="c"*64,image=fixtures.IMAGE,state=dict(Running=True,Health=dict(Status="healthy")),
                mounts=[dict(Destination="/etc/importer-tls",Source=str(self.root),RW=False)] if kind=="nginx" else [],user="10002:10002" if kind=="nginx" else "10001:10001",readonly=True,
                command=["mariadbd"] if kind=="db" else ["-g","daemon off;"] if kind=="nginx" else ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--no-server-header","--no-access-log"],entrypoint=["nginx"] if kind=="nginx" else None))
        self.host=SimpleNamespace(host_lock=acquired,load_peer=lambda filename:model,command=Mock(side_effect=lambda *a,**kw:"\n".join(json.dumps(value) for value in self.values)),
            protected=self.protected,draining=lambda:False,profile=lambda _:dict(),CifsBinding=self.source,queue_step=fixtures.host.queue_step,PROCESSING_LOCK="processing.lock")

    def protected(self,path):
        path=Path(path);path.stat();return path

    @contextmanager
    def source(self,*args):yield SimpleNamespace(check=lambda:None)

    def receipt(self,mode,outcome,**changes):
        value=dict(schema_version=1,source_commit=SOURCE,deployment_id=DEPLOYMENT,instance_id=INSTANCE,boot_id=BOOT,started_at=NOW-30,at=NOW-10,result=outcome);value.update(changes)
        (self.root/(mode+".json")).write_text(json.dumps(value))

    def collect(self,*,locked=False,systemd_error=False):
        captured=[]
        with patch.object(ops,"profile",return_value=(self.cfg,self.automation,self.binding)),patch.object(runtime,"profile",return_value=self.binding),\
                patch.object(ops,"systemd",side_effect=ValueError() if systemd_error else lambda _:deepcopy(self.units)),patch.object(ops,"held",return_value=locked),\
                patch.object(runtime,"current_release",return_value=("releases/current",self.root)),patch.object(runtime,"tls_profile",return_value={}),\
                patch.object(runtime,"Source",self.source),patch.object(runtime,"peer") as peer,patch.object(model,"boot_id",return_value=BOOT),\
                patch.object(ops.time,"time",return_value=NOW),patch.object(ops.time,"monotonic",return_value=0),\
                patch.object(ops,"atomic",side_effect=lambda path,value,host,**kw:captured.append((path,value,kw))):
            result=ops.collect("status-profile",self.host,runtime,15)
        self.assertTrue(result["published"]);self.assertEqual(len(captured),1);self.assertEqual(captured[0][2],dict(public=True))
        value=captured[0][1];model.validate_raw(value)
        public=model.project(value,now=NOW,source_commit=SOURCE,deployment_id=DEPLOYMENT,instance_id=INSTANCE,current_boot=BOOT)
        return value,public,peer

    def test_real_container_validation_and_receipts_produce_only_whitelisted_metadata(self):
        value,public,peer=self.collect()
        self.assertEqual(public["state"],"active");self.assertEqual(peer.call_count,1)
        self.assertTrue(all(row["last_result"]=="ok" for row in value["jobs"].values()))
        self.assertEqual(value["jobs"]["inbox"]["next_run_at"],NOW+60)
        args=self.host.command.call_args.args[0];self.assertEqual(args[0],"inspect");self.assertEqual(len(self.host.command.call_args_list),1)
        for secret in ("image","credential","password",str(self.root),"192.0.2.10","invoice.example.invalid"):self.assertNotIn(secret,json.dumps(value))

    def test_failed_host_reads_wrong_image_and_wrong_calendar_never_green(self):
        _,public,_=self.collect(systemd_error=True)
        self.assertEqual(public["state"],"unknown");self.assertIsNone(public["automatic_schedule_active"])
        self.values[1]["image"]="sha256:"+"b"*64
        value,public,peer=self.collect()
        self.assertIsNone(value["startup"]["database_ready"]);self.assertEqual(public["state"],"degraded");peer.assert_not_called()
        self.units[ops.TIMERS["inbox"]]["TimersCalendar"]="{ OnCalendar=*-*-* *:*:00 UTC ; next_elapse=@0 }"
        _,public,_=self.collect();self.assertIsNone(public["jobs"]["inbox"]["active"])

    def test_paused_uninstalled_and_backoff_with_running_mode_are_separate(self):
        self.units[ops.TIMERS["notifications"]]["ActiveState"]="inactive"
        self.units[ops.TIMERS["tls"]]["LoadState"]="not-found"
        (self.root/"queue.json").write_text(json.dumps(dict(due=dict(inbox=True,corrections=False),last="corrections",active="corrections",not_before=NOW+300)))
        value,public,_=self.collect(locked=True)
        self.assertEqual(public["automatic_schedule_state"],"paused");self.assertFalse(public["jobs"]["tls"]["configured"])
        self.assertTrue(value["processing_running"]);self.assertTrue(value["jobs"]["corrections"]["running"]);self.assertFalse(value["jobs"]["inbox"]["running"])
        self.assertTrue(value["jobs"]["inbox"]["blocked"]);self.assertEqual(public["jobs"]["inbox"]["state"],"degraded")

    def test_old_invalid_and_future_receipts_are_not_current_success(self):
        for changes in (dict(source_commit="b"*40),dict(deployment_id=INSTANCE),dict(instance_id=BOOT),dict(boot_id=DEPLOYMENT),
                dict(at=NOW-40,started_at=NOW-50),dict(at=NOW+31),dict(schema_version=True),dict(result="private-secret")):
            self.receipt("inbox","ok",**changes)
            value,public,_=self.collect()
            self.assertEqual(value["jobs"]["inbox"]["last_result"],"unknown");self.assertEqual(public["jobs"]["inbox"]["state"],"degraded")
        self.receipt("inbox","failed");self.assertEqual(self.collect()[1]["jobs"]["inbox"]["state"],"degraded")
        self.receipt("inbox","deferred");self.assertEqual(self.collect()[0]["jobs"]["inbox"]["last_result"],"deferred")

    def pending(self,name="inbox",**changes):
        other="corrections" if name=="inbox" else "inbox"
        value=dict(due={name:True,other:False},last=other,active=None,not_before=0);value.update(changes)
        (self.root/"queue.json").write_text(json.dumps(value))
        self.receipt(name,"ok",started_at=NOW-330,at=NOW-323)

    def test_coalesced_trigger_is_deferred_until_its_actual_pickup_in_either_direction(self):
        for name in ("inbox","corrections"):
            with self.subTest(name=name):
                for mode in ("inbox","corrections"):self.units[ops.SERVICES[mode]]["ExecMainStartTimestamp"]="@"+str(NOW-30)
                self.receipt("inbox","ok");self.receipt("corrections","ok");self.pending(name)
                value,public,_=self.collect();job=value["jobs"][name]
                self.assertEqual(job["last_result"],"deferred");self.assertEqual(job["last_run_at"],NOW-10)
                self.assertFalse(job["running"]);self.assertEqual(public["jobs"][name]["state"],"active")
                self.assertTrue(json.loads((self.root/"queue.json").read_text())["due"][name])
                # The normal later trigger consumes the queued mode, with its own genuine receipt.
                self.units[ops.SERVICES[name]]["ExecMainStartTimestamp"]="@"+str(NOW-5)
                self.receipt(name,"ok",started_at=NOW-5,at=NOW-1)
                (self.root/"queue.json").write_text(json.dumps(dict(due=dict(inbox=False,corrections=False),last=name,active=None,not_before=0)))
                value,public,_=self.collect()
                self.assertEqual(value["jobs"][name]["last_result"],"ok");self.assertEqual(value["jobs"][name]["last_run_at"],NOW-1)
                self.assertEqual(public["jobs"][name]["state"],"active")

    def test_pending_queue_without_current_bound_success_cannot_explain_a_trigger(self):
        self.pending()
        for changes in (dict(source_commit="b"*40),dict(deployment_id=INSTANCE),dict(instance_id=BOOT),dict(boot_id=DEPLOYMENT),
                dict(started_at=NOW-50,at=NOW-40),dict(at=NOW+31),dict(result="failed"),dict(result="unknown"),dict(result="deferred")):
            with self.subTest(changes=changes):
                self.receipt("corrections","ok",**changes)
                value,public,_=self.collect()
                self.assertEqual(value["jobs"]["inbox"]["last_result"],"unknown")
                self.assertEqual(public["jobs"]["inbox"]["state"],"degraded")
        (self.root/"corrections.json").unlink()
        self.assertEqual(self.collect()[0]["jobs"]["inbox"]["last_result"],"unknown")

    def test_trigger_coalesced_during_actual_run_uses_its_completion_not_its_start(self):
        self.pending()
        self.receipt("corrections","ok",started_at=NOW-31,at=NOW-10)
        value,public,_=self.collect()
        self.assertEqual(value["jobs"]["inbox"]["last_result"],"deferred")
        self.assertEqual(value["jobs"]["corrections"]["last_result"],"ok")
        self.assertEqual(public["state"],"active")

    def test_real_service_or_receipt_failures_are_never_masked_by_queue_or_ok_receipt(self):
        self.pending();self.units[ops.SERVICES["inbox"]]["Result"]="exit-code"
        self.receipt("inbox","ok")
        value,public,_=self.collect()
        self.assertEqual(value["jobs"]["inbox"]["last_result"],"failed");self.assertEqual(public["jobs"]["inbox"]["state"],"degraded")
        self.units[ops.SERVICES["inbox"]]["Result"]="success"
        for started in (NOW-330,NOW-30):
            self.receipt("inbox","failed",started_at=started)
            self.assertNotEqual(self.collect()[1]["jobs"]["inbox"]["state"],"active")

    def test_running_unlocked_or_incomplete_queue_snapshots_do_not_invent_completion(self):
        self.pending(active="corrections")
        value,public,_=self.collect(locked=True)
        self.assertTrue(value["jobs"]["corrections"]["running"]);self.assertFalse(value["jobs"]["inbox"]["running"])
        self.assertEqual(public["jobs"]["inbox"]["state"],"degraded")
        self.pending()
        for locked in (True,None):
            self.assertEqual(self.collect(locked=locked)[0]["jobs"]["inbox"]["last_result"],"unknown")
        for changes in (dict(ActiveState="activating"),dict(ExecMainStatus="1"),dict(Result="exit-code"),dict(ExecMainStartTimestamp="")):
            original=deepcopy(self.units[ops.SERVICES["corrections"]])
            self.units[ops.SERVICES["corrections"]].update(changes)
            self.assertEqual(self.collect()[0]["jobs"]["inbox"]["last_result"],"unknown")
            self.units[ops.SERVICES["corrections"]]=original
        self.pending(due=dict(inbox=False,corrections=False))
        self.assertEqual(self.collect()[0]["jobs"]["inbox"]["last_result"],"unknown")

    def test_backoff_and_drain_remain_restrictions_even_with_proven_queue_deferral(self):
        self.pending(not_before=NOW+300)
        value,public,_=self.collect()
        self.assertEqual(value["jobs"]["inbox"]["last_result"],"deferred")
        self.assertTrue(value["jobs"]["inbox"]["blocked"]);self.assertEqual(public["jobs"]["inbox"]["state"],"degraded")
        self.pending();self.host.draining=lambda:True
        self.assertEqual(self.collect()[1]["jobs"]["inbox"]["state"],"degraded")

    def test_exact_vm_systemd_format_and_spent_budget(self):
        text="Id=invoice-tls.timer\nLoadState=loaded\nTimersCalendar={ OnCalendar=*-*-* *:00:00 Europe/Berlin ; next_elapse=@1794852000 }\nNextElapseUSecRealtime=@1794864557\n\nId=invoice-tls.service\nExecMainStartTimestamp=@1794169442\n"
        rows=ops.parse_units(text);self.assertEqual(ops.timestamp(rows[ops.TIMERS["tls"]]["NextElapseUSecRealtime"]),1794864557)
        self.assertEqual(ops.timestamp(rows[ops.SERVICES["tls"]]["ExecMainStartTimestamp"]),1794169442)
        with self.assertRaises(ValueError):ops.parse_units(text+"\nId=invoice-tls.timer\n")
        with patch.object(ops.time,"monotonic",return_value=15),patch.object(ops.subprocess,"run") as command:
            with self.assertRaises(ValueError):ops.systemd(15)
        command.assert_not_called()

    def test_lock_observation_reads_only_matching_existing_flock(self):
        fake=SimpleNamespace(protected=lambda _:SimpleNamespace(stat=lambda:SimpleNamespace(st_dev=0,st_ino=42)))
        with patch("builtins.open",mock_open(read_data="1: FLOCK ADVISORY WRITE 1234 08:01:42 0 EOF\n")),\
                patch.object(ops.os,"major",return_value=8,create=True),patch.object(ops.os,"minor",return_value=1,create=True):
            self.assertTrue(ops.held("processing.lock",fake))
        with patch("builtins.open",mock_open(read_data="1: FLOCK ADVISORY WRITE 1234 08:01:43 0 EOF\n")),\
                patch.object(ops.os,"major",return_value=8,create=True),patch.object(ops.os,"minor",return_value=1,create=True):
            self.assertFalse(ops.held("processing.lock",fake))


class ImportReceiptTests(unittest.TestCase):
    def test_real_automatic_dynamic_import_and_receipt_use_explicit_host(self):
        automatic=fixtures.host_module("ap08_receipt_entry","run-automation.py")
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory)
            for name in ("run-automation.py","run-processing.py","operations-host.py"):shutil.copyfile(Path(automatic.__file__).with_name(name),root/name)
            shutil.copyfile(Path(model.__file__),root/"operations-status.py")
            automatic.__file__=str(root/"run-automation.py")
            original_stat=Path.stat
            def metadata(path,*args,**kwargs):
                info=original_stat(path,*args,**kwargs)
                return SimpleNamespace(st_uid=0,st_mode=stat.S_IFDIR|0o700 if stat.S_ISDIR(info.st_mode) else stat.S_IFREG|0o600,st_size=info.st_size)
            stack.enter_context(patch.object(Path,"lstat",metadata))
            stack.enter_context(patch.object(automatic,"os",SimpleNamespace(name="posix",geteuid=lambda:0,umask=lambda _:None)))
            stack.enter_context(patch.object(automatic,"sys",SimpleNamespace(flags=SimpleNamespace(isolated=1),dont_write_bytecode=True)))
            receipts=[];loaded=[];real_loader=automatic.load_processing
            def loader(filename="run-processing.py"):
                host=real_loader(filename);loaded.append(host);peer=host.load_peer
                def load_peer(name):
                    module=peer(name)
                    if name=="operations-host.py":
                        module.profile=lambda path,received:(dict(source_commit=SOURCE,deployment_id=DEPLOYMENT,result_directory=directory),{},dict(instance_id=INSTANCE)) if received is host else (_ for _ in ()).throw(ValueError())
                        module.atomic=lambda path,value,received,**kw:receipts.append((path,value,received))
                    elif name=="operations-status.py":module.boot_id=lambda:BOOT
                    return module
                host.load_peer=load_peer
                return host
            stack.enter_context(patch.object(automatic,"load_processing",side_effect=loader))
            stack.enter_context(patch.object(automatic,"profile",return_value={}))
            stack.enter_context(patch.object(automatic,"operate",return_value=dict(ok=True,mode="corrections",private_payload="must-not-leak")))
            stack.enter_context(patch.object(sys,"argv",["run-automation.py","inbox","--profile","synthetic"]))
            output=stack.enter_context(patch("sys.stdout",new_callable=io.StringIO))
            self.assertEqual(automatic.main(),0)
            result=json.loads(output.getvalue())
            self.assertTrue(result["status_recorded"]);self.assertEqual(len(receipts),1)
            self.assertEqual(receipts[0][0].name,"corrections.json");self.assertIs(receipts[0][2],loaded[0])
            self.assertEqual(receipts[0][1]["result"],"ok");self.assertNotIn("must-not-leak",json.dumps(receipts[0][1]))
            self.assertNotIn("invoice_processing_host",sys.modules)


class PublicationTests(unittest.TestCase):
    def publish(self,fail=False):
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);target=root/"status.json";target.write_text('{"old":true}')
            original_open=ops.os.open;original_replace=ops.os.replace;events=[]
            stack.enter_context(patch.object(ops.os,"O_DIRECTORY",0x10000,create=True))
            stack.enter_context(patch.object(ops.os,"open",side_effect=lambda path,flags,*a,**kw:original_open(ops.os.devnull,ops.os.O_RDONLY) if Path(path)==root else original_open(path,flags,*a,**kw)))
            stack.enter_context(patch.object(ops.os,"fchown",side_effect=lambda fd,uid,gid:events.append(("owner",uid,gid)),create=True))
            stack.enter_context(patch.object(ops.os,"fchmod",side_effect=lambda fd,mode:events.append(("mode",mode)),create=True))
            stack.enter_context(patch.object(ops.os,"fsync",side_effect=lambda fd:events.append(("sync",))))
            def replace(source,destination):
                self.assertEqual(json.loads(target.read_text()),dict(old=True));events.append(("replace",))
                if fail:raise OSError("synthetic_replace_failure")
                original_replace(source,destination)
            stack.enter_context(patch.object(ops.os,"replace",side_effect=replace))
            host=SimpleNamespace(controlled_directory=lambda path:Path(path))
            if fail:
                with self.assertRaises(OSError):ops.atomic(target,dict(new=True),host,public=True)
                self.assertEqual(json.loads(target.read_text()),dict(old=True))
            else:
                ops.atomic(target,dict(new=True),host,public=True)
                self.assertEqual(json.loads(target.read_text()),dict(new=True))
                self.assertEqual(events,[("owner",0,10001),("mode",0o440),("sync",),("replace",),("sync",)])
            self.assertEqual([item.name for item in root.iterdir()],["status.json"])

    def test_replacement_occurs_after_complete_body_metadata_and_sync(self):self.publish()
    def test_failed_replace_keeps_previous_file_and_removes_own_staging(self):self.publish(fail=True)
