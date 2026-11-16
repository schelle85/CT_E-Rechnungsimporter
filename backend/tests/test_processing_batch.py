"""A-P1: actual journal/service lifecycle inside a bounded synthetic host batch.

Inputs are preclassified with durable synthetic storage receipts; no native
download/OCR/CIFS/Docker behavior is claimed. Graph completion is a double.
"""
from contextlib import contextmanager
import hashlib
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock,patch
import sqlalchemy as sa
from app.graph import GraphError
from app.processing import ProcessingService
from app.storage_state import StorageStore,metadata,operations
import test_processing_state as fixtures
import test_automation_runtime as runtime
from test_processing_plan import mail,attachment


class BatchTests(unittest.TestCase):
    def setUp(self):
        fixtures.ProcessingStateTests.setUp(self)
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:connection.execute(operations.delete())
        self.storage=StorageStore(self.engine,destination_key="d"*64,clock=lambda:self.now[0])
        self.files=SimpleNamespace(destination_key="d"*64)
        self.graph=SimpleNamespace(check_manifest=Mock(),folders=Mock(return_value=fixtures.FOLDERS),
            finish=Mock(side_effect=lambda message,intent,*args:SimpleNamespace(parent_id=intent["destination_id"],flag="flagged")))
        self.service=ProcessingService(self.store,self.graph,self.storage,self.files,"synthetic")

    def prepare(self,count):
        keys=[self.key]+[self.store.register(self.mailbox,mail(id="synthetic-batch-"+str(i)),
            [attachment(name="synthetic-"+str(i)+".pdf")]) for i in range(1,count)]
        for index,key in enumerate(keys):
            claim=self.store.claim(key);owner,revision=claim["owner"],claim["revision"]
            aid=self.store.get_attachments(key)[0]["attachment_key"]
            digest=hashlib.sha256(("batch"+str(index).zfill(2)).encode()).hexdigest()
            self.store.content(key,aid,owner,revision,byte_size=7,sha256=digest)
            self.store.finding(key,aid,owner,revision,dict(status="recognized",category="PDF",reason="invoice_fields",
                method="pdf_text",original_sha256=digest,rule_version="ap03-4"))
            request=self.store.begin_storage(key,aid,owner,revision,"synthetic",self.files.destination_key)
            ticket=self.storage.claim(request)
            self.storage.begin_publication(request.key,ticket["owner"])
            self.storage.finish(request.key,ticket["owner"],"stored")
            # Simulate resumption after a durable storage receipt: first quantum
            # attaches that receipt, next quantum performs the real DB close.
            self.store.release(key,owner,revision)
        return keys

    def batch(self,count,*,duration=.1,backoff=False):
        keys=self.prepare(count);host=runtime.host;clock=[0.0];calls=[];deadlines=[]
        if backoff:self.graph.check_manifest.side_effect=GraphError("graph_retry_later",status=429,retry_not_before=4600)
        def coordinator(args,working,deadline):
            calls.append(args);deadlines.append(deadline)
            if args[0]=="select":return dict(ok=True,message_keys=keys)
            result=self.service.advance(args[args.index("--message-key")+1],working)
            clock[0]+=duration
            value=dict(ok=True,**result.result())
            if result.status=="busy" and (result.reason or "").startswith("graph_"):
                value["retry_not_before"]=self.store.get_message(result.message_key)["next_attempt"]
            return value
        with self.engine.connect() as connection:before=list(connection.execute(sa.select(operations)).mappings())
        fake=SimpleNamespace(coordinator=coordinator,classifier=Mock(side_effect=AssertionError("already_classified")))
        with tempfile.TemporaryDirectory() as directory:
            @contextmanager
            def working(**kwargs):yield directory
            with patch.object(host,"Runtime",return_value=fake),patch.object(host.tempfile,"TemporaryDirectory",working),\
                    patch.object(host.os,"chown",create=True),patch.object(host.os,"chmod"),\
                    patch.object(host,"time",SimpleNamespace(monotonic=lambda:clock[0],time=lambda:self.now[0])):
                result=host.operate_locked("inbox",runtime.IMAGE,{},host.AUTOMATIC_MAX_QUANTA,780)
        self.assertTrue(all(deadline<=740 for deadline in deadlines))
        fake.classifier.assert_not_called()
        with self.engine.connect() as connection:self.assertEqual(list(connection.execute(sa.select(operations)).mappings()),before)
        completed=sum(self.store.get_message(key)["completed_revision"]==self.store.get_message(key)["revision"] for key in keys)
        self.assertEqual(len(calls),result["quanta"]+1)
        return result,completed,clock[0]

    def test_fast_batch_runs_twenty_quanta_and_completes_mail_without_next_tick(self):
        result,completed,elapsed=self.batch(11)
        self.assertEqual(result["quanta"],20)
        self.assertEqual(result["states"],dict(progress=11,done=9))
        self.assertEqual(completed,9);self.assertEqual(result["remaining"],2)
        self.assertLess(elapsed,3)

    def test_empty_queue_ends_before_twenty_after_actual_mail_closes(self):
        result,completed,_=self.batch(2)
        self.assertEqual(result["quanta"],4);self.assertEqual(result["remaining"],0)
        self.assertEqual(completed,2)

    def test_remaining_time_stops_new_quantum_even_below_twenty(self):
        result,completed,elapsed=self.batch(2,duration=130)
        self.assertEqual((result["quanta"],completed,elapsed),(2,0,260))
        self.assertLess(780-elapsed,540)

    def test_known_backoff_stops_the_batch_before_another_message(self):
        result,completed,_=self.batch(2,backoff=True)
        self.assertEqual((result["quanta"],completed,result["retry_not_before"]),(3,0,4600))
        self.assertEqual(result["states"],dict(progress=2,busy=1))
        self.graph.finish.assert_not_called()
