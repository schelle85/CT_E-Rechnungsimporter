"""A-R1/V3: 429 boundary from actual CLI/store to persistent host schedule.

SQLite by default; host file writes are real, Linux ownership/flock/fsync-dir
primitives are explicit doubles. No external reads or writes.
"""
from contextlib import contextmanager,nullcontext
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import httpx
import sqlalchemy as sa
from app.graph import GraphClient,GraphError
from app.graph_state import ActionStore,actions,metadata as graph_metadata
from app.processing import known_429_not_before
from app.storage import StorageResult
from app.storage_state import StorageStore,metadata as storage_metadata,operations
from app import processing_cli as cli
from test_graph import CONFIG,Credential
from test_graph_actions import ActionRemote
from test_graph_mail import message,attachment
import test_processing_state as fixtures
import test_automation_runtime as runtime


class BackoffTests(unittest.TestCase):
    def setUp(self):
        fixtures.ProcessingStateTests.setUp(self)
        graph_metadata.create_all(self.engine)
        with self.engine.begin() as connection:connection.execute(actions.delete())

    def execute(self,args,graph,*,real_client=None):
        files=SimpleNamespace(destination_key="synthetic")
        with patch.object(cli,"configuration",return_value=dict(scope="synthetic",storage_root="/unused",
                expected_source="//files.example.invalid/importer",staging_name="_staging",staging_excluded=True)),\
                patch.object(cli,"make_engine",return_value=self.engine),\
                patch.object(cli,"CifsFiles",side_effect=lambda *a,**kw:nullcontext(files)),\
                patch.object(cli,"operator_client",side_effect=lambda *a,**kw:nullcontext(real_client)),\
                (patch.object(cli,"GraphActions") if graph is not None else nullcontext()),\
                (patch.object(cli,"GraphProcessing",return_value=graph) if graph is not None else nullcontext()),\
                patch.object(cli,"ActionStore",side_effect=lambda engine:ActionStore(engine,clock=lambda:self.now[0])),\
                patch.object(cli,"ProcessingStore",return_value=self.store),\
                patch.object(cli,"StorageStore",return_value=files),\
                patch.object(cli.time,"time",side_effect=lambda:self.now[0]):
            return cli.execute(cli.arguments(args))

    def persistent_host_boundary(self,result,expected):
        host=runtime.host
        @contextmanager
        def lock(*args,**kwargs):yield True
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory);state=parent/"schedule.json"
            class HostOS:
                name="posix";O_DIRECTORY=0
                def __getattr__(self,name):return getattr(os,name)
                def geteuid(self):return 0
                def open(self,path,*args,**kwargs):
                    return -91 if Path(path)==parent else os.open(path,*args,**kwargs)
                def fsync(self,fd):
                    if fd!=-91:os.fsync(fd)
                def close(self,fd):
                    if fd!=-91:os.close(fd)
            with patch.object(host,"os",HostOS()),patch.object(host,"host_lock",lock),\
                    patch.object(host,"protected",side_effect=Path),patch.object(host,"controlled_directory"),\
                    patch.object(host,"time",SimpleNamespace(monotonic=lambda:0,time=lambda:self.now[0])),\
                    patch.object(host,"command",return_value=""),\
                    patch.object(host,"operate_locked",return_value=result) as operation:
                host.operate("inbox",runtime.IMAGE,{},scheduled_state=str(state))
                self.assertEqual(json.loads(state.read_text())["not_before"],expected)
                self.assertEqual(operation.call_count,1)
                self.now[0]=expected-1
                for mode in ("inbox","corrections"):
                    value=host.operate(mode,runtime.IMAGE,{},scheduled_state=str(state))
                    self.assertTrue(value["deferred"]);self.assertEqual(value["quanta"],0)
                    self.assertEqual(value["retry_not_before"],expected)
                self.assertEqual(operation.call_count,1)
                persisted=json.loads(state.read_text())
                self.assertEqual(persisted["due"],dict(inbox=True,corrections=True))
                self.assertEqual(persisted["not_before"],expected)
                self.now[0]=expected
                host.operate("corrections",runtime.IMAGE,{},scheduled_state=str(state))
                self.assertEqual(operation.call_count,2)
                self.assertEqual(operation.call_args.args[0],"corrections")

    def test_select_short_and_missing_or_unusable_boundary_reach_shared_schedule(self):
        for boundary,expected in ((1005,1300),(None,1900),(0,1900),(999,1900),(True,1900)):
            with self.subTest(boundary=boundary):
                self.now[0]=1000
                graph=SimpleNamespace(scan=Mock(side_effect=GraphError("graph_read_failed",status=429,retry_not_before=boundary)))
                result=self.execute(["select","--mode","inbox"],graph)
                self.assertTrue(result["ok"]);self.assertEqual(result["message_keys"],[])
                self.assertEqual(result["retry_not_before"],expected)
                self.persistent_host_boundary(result,expected)

    def resumed_close(self,boundary,expected):
        claim=self.store.claim(self.key);owner,revision=claim["owner"],claim["revision"]
        attachment=fixtures.ProcessingStateTests.finding(self,owner,revision)
        fixtures.ProcessingStateTests.storage(self,attachment,owner,revision)
        intent=self.store.prepare_close(self.key,owner,revision,fixtures.FOLDERS)
        self.store.release(self.key,owner,revision)
        journal=ActionStore(self.engine,clock=lambda:self.now[0])
        token,actor,permission=journal.claim(self.mailbox,"move","immutable-message",intent["destination"],intent_key=intent["intent_key"])
        self.assertTrue(permission)
        journal.finish(token,actor,"unknown",error="synthetic_lost_response")
        before=self.store.get_message(self.key)
        effects=[dict(row) for row in self.store.get_attachments(self.key)]
        with self.engine.connect() as connection:graph_before=list(connection.execute(sa.select(actions)).mappings())
        graph=SimpleNamespace(check_manifest=Mock(side_effect=GraphError("graph_read_failed",status=429,retry_not_before=boundary)),
            folders=Mock(),finish=Mock())
        result=self.execute(["advance","--message-key",self.key],graph)
        self.assertEqual((result["status"],result["retry_not_before"]),("busy",expected))
        after=self.store.get_message(self.key)
        self.assertEqual(after["next_attempt"],expected)
        for name in ("close_key","close_payload","completed_revision","revision","current_parent"):
            self.assertEqual(after[name],before[name])
        self.assertEqual(after["state"],"closing");self.assertIsNone(after["owner"])
        self.assertEqual([dict(row) for row in self.store.get_attachments(self.key)],effects)
        with self.engine.connect() as connection:self.assertEqual(list(connection.execute(sa.select(actions)).mappings()),graph_before)
        graph.check_manifest.assert_called_once();graph.folders.assert_not_called();graph.finish.assert_not_called()
        self.assertEqual(self.store.due("inbox"),[])
        self.persistent_host_boundary(result,expected)

    def test_existing_close_long_server_boundary_and_all_effect_tokens_survive(self):
        self.resumed_close(4600,4600)

    def test_existing_close_without_server_boundary_uses_nine_hundred_seconds(self):
        self.resumed_close(None,1900)

    def test_absolute_maximum_survives_clock_progress_without_overflow(self):
        maximum=9223372036854775807
        boundary=known_429_not_before(GraphError("graph_read_failed",status=429,retry_not_before=maximum),1000)
        claim=self.store.claim(self.key);self.now[0]+=1
        self.store.release(self.key,claim["owner"],claim["revision"],not_before=boundary)
        self.assertEqual(self.store.get_message(self.key)["next_attempt"],maximum)

    def test_uncertain_select_does_not_gain_a_retry_permission_or_boundary(self):
        error=GraphError("graph_request_failed",status=429,uncertain=True,retry_not_before=4600)
        self.assertIsNone(known_429_not_before(error,1000))
        result=self.execute(["select"],SimpleNamespace(scan=Mock(side_effect=error)))
        self.assertFalse(result["ok"]);self.assertTrue(result["uncertain"])
        self.assertNotIn("retry_not_before",result)

    def real_action_boundary(self,header,forwarded,expected):
        storage_metadata.create_all(self.engine)
        with self.engine.begin() as connection:connection.execute(operations.delete())
        claim=self.store.claim(self.key);owner,revision=claim["owner"],claim["revision"]
        aid=fixtures.ProcessingStateTests.finding(self,owner,revision)
        request=self.store.begin_storage(self.key,aid,owner,revision,"synthetic","d"*64)
        storage=StorageStore(self.engine,destination_key="d"*64,clock=lambda:self.now[0])
        reserved=storage.claim(request)
        storage.begin_publication(request.key,reserved["owner"])
        storage.finish(request.key,reserved["owner"],"stored")
        self.store.stored(self.key,aid,owner,revision,StorageResult(request.key,"stored",storage.get(request.key)["target"]))
        intent=self.store.prepare_close(self.key,owner,revision,fixtures.FOLDERS)
        self.store.release(self.key,owner,revision)
        journal=ActionStore(self.engine,clock=lambda:self.now[0])
        token,actor,_=journal.claim(self.mailbox,"move","immutable-message",intent["destination"],intent_key=intent["intent_key"])
        journal.finish(token,actor,"unknown",error="synthetic_lost_response")
        before=self.store.get_message(self.key)
        effects=[dict(row) for row in self.store.get_attachments(self.key)]
        with self.engine.connect() as connection:
            storage_before=list(connection.execute(sa.select(operations)).mappings())
            graph_before=list(connection.execute(sa.select(actions)).mappings())
        remote=ActionRemote()
        remote.messages={"immutable-message":message(mid="immutable-message")}
        item=attachment(size=999,name="invoice.pdf");item["contentType"]="application/pdf"
        remote.attachments={"immutable-message":[item]}
        remote.folders={name:dict(id=key,displayName=name,parentFolderId="inbox",isHidden=False) for name,key in fixtures.FOLDERS.items()}
        def respond(request):
            if request.url.path.endswith("/mailFolders/inbox/childFolders"):
                # Earlier manifest GETs succeed. Reject only after the actual
                # GraphActions._run has claimed its own first folder action.
                with self.engine.connect() as connection:
                    active=connection.execute(sa.select(actions.c.action_key).where(
                        actions.c.kind=="folder",actions.c.owner.is_not(None))).first()
                if active:return httpx.Response(429,headers={} if header is None else {"Retry-After":header})
        remote.override=respond
        with httpx.Client(transport=httpx.MockTransport(remote),trust_env=False) as http:
            client=GraphClient(CONFIG,Credential(),http,read_attempts=1)
            # Observe the received error without replacing GraphActions or
            # GraphProcessing; their real reads, claims and forwarding run.
            with patch("app.processing.known_429_not_before",wraps=known_429_not_before) as boundary:
                result=self.execute(["advance","--message-key",self.key],None,real_client=client)
            self.assertEqual(boundary.call_count,1)
            error=boundary.call_args.args[0]
            self.assertEqual((error.status,error.uncertain,error.retry_not_before),(429,False,forwarded))
        self.assertEqual((result["status"],result["retry_not_before"]),("busy",expected))
        after=self.store.get_message(self.key)
        self.assertEqual(after["next_attempt"],expected)
        for name in ("close_key","close_payload","completed_revision","revision","current_parent"):
            self.assertEqual(after[name],before[name])
        self.assertEqual([dict(row) for row in self.store.get_attachments(self.key)],effects)
        with self.engine.connect() as connection:
            self.assertEqual(list(connection.execute(sa.select(operations)).mappings()),storage_before)
            graph_after={row["action_key"]:dict(row) for row in connection.execute(sa.select(actions)).mappings()}
        for row in graph_before:self.assertEqual(graph_after[row["action_key"]],dict(row))
        added=[row for key,row in graph_after.items() if key not in {row["action_key"] for row in graph_before}]
        self.assertEqual(len(added),1)
        self.assertEqual((added[0]["kind"],added[0]["state"],added[0]["reservations"],added[0]["owner"]),("folder","unknown",1,None))
        self.assertEqual(remote.writes,[]);self.assertTrue(all(request.method=="GET" for request in remote.calls))
        self.persistent_host_boundary(result,expected)

    def test_real_graph_action_preserves_long_boundary_through_close_and_host(self):
        self.real_action_boundary("3600",4600,4600)

    def test_real_graph_action_short_boundary_keeps_three_hundred_minimum(self):
        self.real_action_boundary("5",1005,1300)

    def test_real_graph_action_missing_header_keeps_nine_hundred_fallback(self):
        self.real_action_boundary(None,1900,1900)
