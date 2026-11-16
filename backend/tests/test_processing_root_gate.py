"""A-C1: mandatory root metadata and entry ordering; no Docker/DB/CIFS effects."""
from contextlib import nullcontext,redirect_stderr
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from app import processing_cli as cli
from app.storage_plan import StorageError
import test_automation_runtime as runtime

DEVICE=101
INODE=9007199254740993  # Synthetic >2**53 identity, preserved as an integer.
PAIR=["--expected-root-device",str(DEVICE),"--expected-root-inode",str(INODE)]


class ConsumerRootGateTests(unittest.TestCase):
    def test_parser_requires_complete_valid_pair_for_select_and_advance(self):
        for command in (["select"],["advance","--message-key","a"*64]):
            good=cli.arguments([*command,*PAIR])
            self.assertEqual(cli.expected_root(good),(DEVICE,INODE))
            for values in ([],PAIR[:2],PAIR[2:],["--expected-root-device","-1",*PAIR[2:]],
                    [*PAIR[:2],"--expected-root-inode","18446744073709551616"],
                    ["--expected-root-device","not-an-int",*PAIR[2:]]):
                with self.subTest(command=command,values=values),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                    cli.arguments([*command,*values])

    def test_execute_rejects_missing_or_invalid_pair_even_if_parser_was_bypassed(self):
        for device,inode in ((None,None),(DEVICE,None),(None,INODE),(-1,INODE),(DEVICE,2**64),(True,INODE),(str(DEVICE),INODE)):
            args=cli.arguments(["select",*PAIR]);args.expected_root_device=device;args.expected_root_inode=inode
            with self.subTest(device=device,inode=inode),patch.object(cli,"configuration") as config,\
                    patch.object(cli,"make_engine") as engine,patch.object(cli,"CifsFiles") as files,\
                    patch.object(cli,"operator_client") as graph:
                result=cli.execute(args)
            self.assertEqual(result["code"],"processing_root_identity_invalid")
            self.assertFalse(result["ok"])
            config.assert_not_called();engine.assert_not_called();files.assert_not_called();graph.assert_not_called()

    def entry(self,*,device=DEVICE,inode=INODE,constructor_error=None,guard_error=None):
        events=[]
        def guard():
            events.append("guard")
            if guard_error:raise guard_error
        files=SimpleNamespace(identity=(999,device),inode=inode,destination_key="synthetic",guard=Mock(side_effect=guard),stage=Mock())
        def graph(*args,**kwargs):events.append("graph");return nullcontext(None)
        engine=SimpleNamespace(dispose=Mock())
        service=SimpleNamespace(scan=Mock(return_value=[]),store=SimpleNamespace(due=Mock(return_value=[])))
        with patch.object(cli,"configuration",return_value=dict(storage_root="/importer",expected_source="//files.example.invalid/importer",
                staging_name="_staging",staging_excluded=True,scope="synthetic")),\
                patch.object(cli,"make_engine",return_value=engine),\
                patch.object(cli,"CifsFiles",side_effect=constructor_error or (lambda *args,**kwargs:nullcontext(files))),\
                patch.object(cli,"operator_client",side_effect=graph) as graph_entry,\
                patch.object(cli,"ProcessingService",return_value=service) as service_entry,\
                patch.object(cli,"ProcessingStore"),patch.object(cli,"StorageStore") as storage_entry,\
                patch.object(cli,"GraphProcessing"),patch.object(cli,"GraphActions"),patch.object(cli,"ActionStore"):
            result=cli.execute(cli.arguments(["select",*PAIR]))
        engine.dispose.assert_called_once();files.stage.assert_not_called()
        return result,events,graph_entry,service_entry,storage_entry

    def test_matching_metadata_and_guard_precede_graph_and_service(self):
        result,events,graph,service,storage=self.entry()
        self.assertTrue(result["ok"]);self.assertEqual(events,["guard","graph"])
        graph.assert_called_once();service.assert_called_once();storage.assert_called_once()

    def test_wrong_device_or_inode_stops_before_graph_service_or_stage(self):
        for change in (dict(device=DEVICE+1),dict(inode=INODE+1)):
            with self.subTest(change=change):
                result,events,graph,service,storage=self.entry(**change)
                self.assertEqual(result["code"],"processing_root_identity_changed")
                self.assertEqual(events,["guard"])
                graph.assert_not_called();service.assert_not_called();storage.assert_not_called()

    def test_constructor_and_immediate_guard_failures_keep_processing_closed(self):
        for change in (dict(constructor_error=StorageError("storage_cifs_required")),
                dict(guard_error=StorageError("storage_mount_changed"))):
            with self.subTest(change=change):
                result,events,graph,service,storage=self.entry(**change)
                self.assertFalse(result["ok"])
                self.assertNotIn("graph",events)
                graph.assert_not_called();service.assert_not_called();storage.assert_not_called()


class HostRootBridgeTests(unittest.TestCase):
    def coordinator(self,*,exchange=False):
        host=runtime.host
        runner=host.Runtime.__new__(host.Runtime);runner.image=runtime.IMAGE
        runner.config=dict(networks=["isolated"],storage_gid=10001,db_host="db",db_name="synthetic",db_user="synthetic",
            graph_config="/graph",graph_credential="/credential",processing_config="/processing",db_password="/password")
        events=[];commands=[]
        def check():
            events.append("check")
            if exchange and len(events)>1:raise ValueError("processing_mount_changed")
        binding=SimpleNamespace(path="/fstab/importer",identity=(111,DEVICE,INODE),check=check)
        def command(args,*a,**kw):
            commands.append(args);events.append(args[0])
            return (0,dict(ok=True,message_keys=[])) if args[0]=="start" else ""
        with patch.object(host,"command",side_effect=command),patch.object(runner,"cleanup") as cleanup:
            if exchange:
                with self.assertRaisesRegex(ValueError,"processing_mount_changed"):
                    runner._coordinator(["select"],"/exchange",host.time.monotonic()+180,binding)
            else:runner._coordinator(["select"],"/exchange",host.time.monotonic()+180,binding)
        cleanup.assert_called_once()
        return events,commands

    def test_normal_path_and_held_reference_metadata_are_forwarded_without_proc_source(self):
        events,commands=self.coordinator()
        self.assertEqual(events,["check","create","check","start"])
        create=commands[0]
        self.assertIn("type=bind,source=/fstab/importer,target=/importer",create)
        self.assertEqual(create[-4:],PAIR)
        self.assertFalse(any("/proc/" in value for value in create))

    def test_exchange_after_create_prevents_worker_start_and_still_cleans_up(self):
        events,commands=self.coordinator(exchange=True)
        self.assertEqual(events,["check","create","check"])
        self.assertTrue(all(args[0]!="start" for args in commands))
