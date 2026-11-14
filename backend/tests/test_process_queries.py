from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sqlalchemy as sa
from app.errors import AccessError
from app.graph_mail import Attachment, Message
from app.process_queries import ProcessQueries, archive_boundary
from app.processing_state import ProcessingStore, metadata, messages, attachments, corrections
from app.storage import StorageResult
from app.storage_state import StorageStore, metadata as storage_metadata

FOLDERS = {name: "folder-"+name for name in ("Failed", "unzugeordnet", "Mahnung", "Nachfragen", "Zahlungsavis", "Success")}


class ProcessQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = sa.create_engine("sqlite:///"+str(Path(self.temp.name)/"read.sqlite"))
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        metadata.create_all(self.engine)
        storage_metadata.create_all(self.engine)
        self.now = [int(datetime(2030,3,1,tzinfo=timezone.utc).timestamp())]
        self.store = ProcessingStore(self.engine,clock=lambda:self.now[0])
        self.storage = StorageStore(self.engine,destination_key="d"*64,clock=lambda:self.now[0])
        self.queries = ProcessQueries(self.engine,clock=lambda:self.now[0])

    def mail(self, mid="m1", specs=None, close=True):
        specs = specs or [("a1", "invoice.pdf", "unknown", None, "ambiguous_pdf")]
        message = Message(mid,datetime(2026,12,1,tzinfo=timezone.utc),"inbox","notFlagged")
        raw = [Attachment(aid,name,len(aid.encode()),"application/pdf",False,"file") for aid,name,*_ in specs]
        key = self.store.register("invoice@example.invalid",message,raw)
        owned = self.store.claim(key)
        for aid,name,status,category,reason in specs:
            row = next(row for row in self.store.get_attachments(key) if row["graph_id"]==aid)
            checksum=hashlib.sha256(aid.encode()).hexdigest()
            self.store.content(key,row["attachment_key"],owned["owner"],0,byte_size=len(aid.encode()),sha256=checksum)
            self.store.finding(key,row["attachment_key"],owned["owner"],0,
                {"status":status,"category":category,"reason":reason,"method":"pdf_text","format":"PDF",
                 "original_sha256":checksum,"rule_version":"ap03-4"})
            if status=="recognized":
                request=self.store.begin_storage(key,row["attachment_key"],owned["owner"],0,"query-tests","d"*64)
                receipt=self.storage.claim(request)
                if receipt["mode"]=="stage":
                    self.storage.begin_publication(request.key,receipt["owner"])
                    self.storage.finish(request.key,receipt["owner"],"stored")
                    result=StorageResult(request.key,"stored",receipt["target"])
                else:
                    result=StorageResult(request.key,receipt["state"],receipt["target"])
                self.store.stored(key,row["attachment_key"],owned["owner"],0,result)
        if close:
            intent=self.store.prepare_close(key,owned["owner"],0,FOLDERS)
            self.store.finish_close(key,owned["owner"],0,parent_id=intent["destination_id"],flagged=True,intent_key=intent["intent_key"])
        else:
            self.store.release(key,owned["owner"],0)
        return key

    def state(self):
        with self.engine.connect() as c:
            return {table.name:[dict(row) for row in c.execute(sa.select(table)).mappings()]
                    for table in (*metadata.tables.values(),*storage_metadata.tables.values())}

    def test_empty_is_a_real_empty_result(self):
        self.assertEqual(self.queries.list(),{"items":[],"total":0,"page":1,"page_size":25,"synthetic":False})
        self.assertEqual(self.queries.stats(),{"messages":0,"attachments":0,"unknown_open":0,"duplicates":0,"stored":0,"errors":0,"approved":0})
        self.assertEqual(self.queries.unknown()["items"],[])

    def test_attachment_counts_do_not_multiply_and_approval_is_not_open_unknown(self):
        key=self.mail(specs=[("a1","one.pdf","unknown",None,"ambiguous_pdf"),
            ("a2","two.pdf","unknown",None,"ambiguous_hybrid"),("a3","invoice.pdf","recognized","PDF","invoice_fields")])
        detail=self.queries.detail(key)
        self.assertEqual(detail["attachment_count"],3)
        self.assertEqual(detail["unknown_open"],2)
        normal=next(row for row in detail["attachments"] if row["name"]=="one.pdf")
        structural=next(row for row in detail["attachments"] if row["name"]=="two.pdf")
        self.assertTrue(normal["can_correct"])
        self.assertFalse(structural["can_correct"])
        self.store.approved_correction(normal["id"],"request","PDF","synthetic-admin",self.now[0])
        stats=self.queries.stats()
        self.assertEqual((stats["messages"],stats["attachments"],stats["unknown_open"],stats["approved"]),(1,3,1,1))
        self.assertEqual(self.queries.unknown()["total"],1)
        approved=next(row for row in self.queries.detail(key)["attachments"] if row["id"]==normal["id"])
        self.assertEqual(approved["status"],"approved")
        self.assertFalse(approved["can_correct"])

    def test_processed_requires_confirmed_mail_and_required_file_receipt(self):
        key=self.mail(specs=[("a1","invoice.pdf","recognized","PDF","invoice_fields")],close=False)
        detail=self.queries.detail(key)
        self.assertEqual(detail["attachments"][0]["status"],"waiting")
        self.assertFalse(detail["mail_action_confirmed"])
        owned=self.store.claim(key)
        intent=self.store.prepare_close(key,owned["owner"],0,FOLDERS)
        self.store.finish_close(key,owned["owner"],0,parent_id=intent["destination_id"],flagged=True,intent_key=intent["intent_key"])
        detail=self.queries.detail(key)
        self.assertEqual(detail["attachments"][0]["status"],"processed")
        self.assertEqual(detail["attachments"][0]["storage_receipt"]["publication_attempts"],1)
        self.assertTrue(detail["mail_action_confirmed"])

    def test_filters_are_bounded_literal_and_stable(self):
        one=self.mail("m1",[("a1","Rechnung_100%.pdf","recognized","PDF","invoice_fields"),
                            ("a2","Rechnung_100%.pdf","recognized","PDF","invoice_fields")])
        two=self.mail("m2",[("a1","Anderes.pdf","unknown",None,"ambiguous_pdf")])
        self.assertEqual(self.queries.list(search="_100%")["total"],1)
        self.assertEqual(self.queries.list(search="%' OR 1=1 --")["total"],0)
        self.assertEqual(self.queries.list(category="PDF",duplicate=True)["total"],1)
        self.assertEqual(self.queries.list(state="unknown")["total"],1)
        self.assertEqual(self.queries.list(received_from="2026-12-01",received_to="2026-12-01")["total"],2)
        self.assertEqual(self.queries.list(received_to="2026-11-30")["total"],0)
        pages=[self.queries.list(page=p,page_size=1)["items"][0]["id"] for p in (1,2)]
        self.assertEqual(pages,sorted([one,two]))
        for params in ({"page_size":51},{"page":0},{"view":"deleted"},{"received_from":"yesterday"},
                       {"received_from":"2027-01-01","received_to":"2026-01-01"}):
            with self.assertRaises(AccessError):
                self.queries.list(**params)

    def test_archive_boundary_includes_exact_second_and_retains_data(self):
        first=self.mail("m1")
        second=self.mail("m2")
        cutoff=archive_boundary(self.now[0])
        with self.engine.begin() as c:
            c.execute(messages.update().where(messages.c.message_key==first).values(created_at=cutoff))
            c.execute(messages.update().where(messages.c.message_key==second).values(created_at=cutoff-1))
        before=self.state()
        self.assertEqual(self.queries.list()["items"][0]["id"],first)
        self.assertEqual(self.queries.list(view="archive")["items"][0]["id"],second)
        self.assertFalse(self.queries.detail(second)["attachments"][0]["can_correct"])
        self.assertEqual(self.state(),before)
        leap=int(datetime(2028,2,29,12,tzinfo=timezone.utc).timestamp())
        expected=int(datetime(2026,2,28,12,tzinfo=timezone.utc).timestamp())
        self.assertEqual(archive_boundary(leap),expected)

    def test_detail_and_filters_never_modify_durable_journals_or_expose_raw_graph_ids(self):
        key=self.mail("PRIVATE-GRAPH-ID")
        before=self.state()
        detail=self.queries.detail(key)
        self.queries.list(search="invoice")
        self.queries.stats()
        self.queries.unknown()
        self.assertEqual(self.state(),before)
        self.assertNotIn("PRIVATE-GRAPH-ID",json.dumps(detail))
        for bad in ("../secret","A"*64,"missing"):
            with self.assertRaises(AccessError):self.queries.detail(bad)

    def test_snapshot_cannot_mix_pre_and_post_revision_state(self):
        key=self.mail()
        with self.queries.snapshot() as reader:
            original=reader.execute(sa.select(messages.c.revision).where(messages.c.message_key==key)).scalar_one()
            with self.engine.begin() as writer:
                writer.execute(messages.update().where(messages.c.message_key==key).values(revision=1))
            observed=reader.execute(sa.select(messages.c.revision).where(messages.c.message_key==key)).scalar_one()
        self.assertEqual((original,observed),(0,0))
        self.assertEqual(self.queries.detail(key)["revision"],1)
