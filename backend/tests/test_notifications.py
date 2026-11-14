"""Targeted AP07 slots, snapshots and durable no-replay contract; no network."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from uuid import uuid4
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.notification_model import (DEFAULTS, NotificationError, OperationBudget, Slot,
    calendar_slot, certificate_level, checked_settings, graph_scope, identity, wall_instant)
from app.notification_schema007 import metadata, settings, outbox
from app.notification_state import NotificationStore
from app.notification_queries import report_cohort
from app.schema import metadata as security_metadata
from app.processing_state import ProcessingStore, metadata as processing_metadata, messages, attachments
from app.storage_state import StorageStore, metadata as storage_metadata
from app.storage import StorageResult
from app.graph_mail import Message, Attachment

SCOPE="a"*64
ACTOR="ad:"+"1"*32

def stamp(value):
    return int(datetime.fromisoformat(value).timestamp())

class CipherDouble:
    """Explicit test double, not a cryptographic claim; real key tests belong to B."""
    def encrypt(self, raw):
        return b"notification-only:"+base64.urlsafe_b64encode(raw)
    def decrypt(self, raw):
        if not raw.startswith(b"notification-only:"):
            raise ValueError("wrong synthetic key")
        return base64.urlsafe_b64decode(raw.split(b":",1)[1])

class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine=sa.create_engine("sqlite:///"+str(Path(self.temp.name)/"notifications.sqlite"),
            connect_args={"check_same_thread":False,"timeout":10})
        self.addCleanup(self.engine.dispose)
        security_metadata.create_all(self.engine)
        processing_metadata.create_all(self.engine)
        storage_metadata.create_all(self.engine)
        metadata.create_all(self.engine)
        with self.engine.begin() as c:
            c.execute(settings.insert().values(singleton=1,version=0,actor="schema007",updated_at=0))
        self.now=[stamp("2026-12-01T12:00:00+00:00")]
        self.store=NotificationStore(self.engine,CipherDouble(),"11111111-1111-1111-1111-111111111111",clock=lambda:self.now[0])
        self.config=dict(DEFAULTS,recipients=["first@example.invalid"])

    def configure(self, **changes):
        self.config=dict(self.config,**changes)
        version=self.store.configuration()["version"]
        return self.store.save_settings(version,self.config,SCOPE,ACTOR)

    def budget(self):
        return OperationBudget(clock=lambda:self.now[0])

    def warning(self):
        slot=calendar_slot("certificate",self.now[0],self.config,certificate="f"*64)
        data=dict(fingerprint="f"*64,expires_at=self.now[0]+86400,remaining_seconds=86400)
        row=self.store.prepare(slot,SCOPE,data,expected_version=self.store.configuration()["version"],as_of=self.now[0])
        return slot,data,row

    def reserve(self, row):
        ticket=self.store.claim(row["slot_key"],SCOPE)
        self.assertIsNotNone(ticket)
        self.assertTrue(self.store.reserve(ticket,budget=self.budget()))
        return ticket

    def test_e1_unconfigured_and_changed_recipient_replan_same_unreserved_day(self):
        slot,data,missing=self.warning()
        self.assertEqual(missing["error_code"],"notification_settings_missing")
        self.assertIsNone(self.store.claim(missing["slot_key"],SCOPE))
        self.configure()
        _,_,first=self.warning()
        self.assertEqual(first["slot_key"],missing["slot_key"])
        self.configure(recipients=["second@example.invalid"])
        self.assertIsNone(self.store.claim(first["slot_key"],SCOPE))  # Deferred, not obsolete.
        self.assertEqual(self.store.read(first["slot_key"])["state"],"prepared")
        _,_,second=self.warning()
        self.assertEqual(first["slot_key"],second["slot_key"])
        self.assertGreater(second["plan_revision"],first["plan_revision"])
        ticket=self.reserve(second)
        self.configure(recipients=["third@example.invalid"])
        payload=self.store.begin_post(ticket,budget=self.budget())
        self.assertEqual(payload["message"]["toRecipients"],[{"emailAddress":{"address":"second@example.invalid"}}])
        self.assertIsNone(self.store.begin_post(ticket,budget=self.budget()))
        self.assertIsNone(self.store.claim(second["slot_key"],SCOPE))
        self.assertEqual(self.warning()[2]["reservations"],1)

    def test_e1_backoff_and_quota_defer_without_losing_today(self):
        self.configure()
        _,_,row=self.warning()
        self.store.scope_backoff(SCOPE,self.now[0]+900)
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))
        self.now[0]+=901
        self.reserve(row)
        for index in range(3):
            fingerprint=f"{index:064x}"
            slot=calendar_slot("certificate",self.now[0],self.config,certificate=fingerprint)
            data=dict(fingerprint=fingerprint,expires_at=self.now[0],remaining_seconds=0)
            prepared=self.store.prepare(slot,SCOPE,data,expected_version=1,as_of=self.now[0])
            self.reserve(prepared)
        another=calendar_slot("certificate",self.now[0],self.config,certificate="e"*64)
        pending=self.store.prepare(another,SCOPE,dict(fingerprint="e"*64,expires_at=self.now[0],remaining_seconds=0),
            expected_version=1,as_of=self.now[0])
        self.assertIsNone(self.store.claim(pending["slot_key"],SCOPE))
        self.assertEqual(self.store.read(pending["slot_key"])["reservations"],0)
        self.now[0]+=3601
        self.reserve(pending)

    def test_e2_exact_actor_scope_and_original_request_replay_before_active_version(self):
        self.configure()
        request=str(uuid4())
        old=self.store.request_test(request,1,SCOPE,ACTOR)
        ticket=self.reserve(old)
        self.store.begin_post(ticket,budget=self.budget())
        self.store.finish(ticket,"accepted",http_status=202)
        self.configure(recipients=["changed@example.invalid"])
        again=self.store.request_test(request.upper(),1,SCOPE,ACTOR)
        self.assertEqual((again["slot_key"],again["state"],again["config_version"]),(old["slot_key"],"accepted",1))
        for version,scope in ((2,SCOPE),(1,"b"*64)):
            with self.assertRaises(NotificationError) as error:self.store.request_test(request,version,scope,ACTOR)
            self.assertEqual(error.exception.status,409)
        with self.assertRaises(NotificationError) as error:self.store.request_test(request,2,SCOPE,"ad:"+"2"*32)
        self.assertEqual(error.exception.status,429)  # New actor cannot execute old request; shared cooldown.

    def test_e2_stale_unreserved_test_is_not_silently_retargeted(self):
        self.configure()
        request=str(uuid4())
        row=self.store.request_test(request,1,SCOPE,ACTOR)
        self.configure(recipients=["changed@example.invalid"])
        replay=self.store.request_test(request,1,SCOPE,ACTOR)
        self.assertEqual(replay["slot_key"],row["slot_key"])
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))
        self.assertEqual(self.store.read(row["slot_key"])["state"],"obsolete")

    def test_e3_unreserved_and_reserved_abort_and_late_results(self):
        self.configure()
        _,_,row=self.warning()
        ticket=self.store.claim(row["slot_key"],SCOPE)
        self.store.recover(row["slot_key"],stopped_owner=ticket["owner"])
        replacement=self.store.claim(row["slot_key"],SCOPE)
        self.assertNotEqual(replacement["owner"],ticket["owner"])
        self.assertFalse(self.store.reserve(ticket,budget=self.budget()))
        self.assertTrue(self.store.reserve(replacement,budget=self.budget()))
        restarted=NotificationStore(self.engine,CipherDouble(),self.store.instance,clock=lambda:self.now[0])
        recovered=restarted.recover(row["slot_key"],stopped_owner=replacement["owner"])
        self.assertEqual((recovered["state"],recovered["reservations"]),("unknown",1))
        self.assertIsNone(restarted.claim(row["slot_key"],SCOPE))
        self.assertIsNone(restarted.begin_post(replacement,budget=self.budget()))
        self.assertEqual(restarted.finish(replacement,"accepted",http_status=202)["state"],"unknown")

    def test_e3_accepted_commit_survives_parent_eof_and_expired_lease(self):
        self.configure()
        _,_,row=self.warning()
        ticket=self.reserve(row)
        self.assertIsNotNone(self.store.begin_post(ticket,budget=self.budget()))
        receipt=self.store.finish(ticket,"accepted",http_status=202)
        self.now[0]+=1000
        self.assertEqual(self.store.recover(row["slot_key"],stopped_owner=ticket["owner"])["state"],"accepted")
        self.assertEqual(self.store.finish(ticket,"unknown")["state"],"accepted")
        self.assertEqual(receipt["http_status"],202)
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))

    def test_e3_deadline_before_reservation_and_post_never_returns_permission(self):
        self.configure()
        _,_,row=self.warning()
        ticket=self.store.claim(row["slot_key"],SCOPE)
        budget=self.budget()
        self.now[0]+=81
        self.assertFalse(self.store.reserve(ticket,budget=budget))
        self.store.recover(row["slot_key"],stopped_owner=ticket["owner"])
        ticket=self.reserve(row)
        expired=self.budget()
        self.now[0]+=81
        self.assertIsNone(self.store.begin_post(ticket,budget=expired))
        self.assertEqual(self.store.read(row["slot_key"])["state"],"rejected")
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))

    def test_only202_is_accepted_and_5xx_never_becomes_definite_rejection(self):
        self.configure()
        _,_,row=self.warning()
        ticket=self.reserve(row)
        with self.assertRaises(NotificationError):self.store.finish(ticket,"accepted",http_status=202)
        self.store.begin_post(ticket,budget=self.budget())
        for state,status in (("accepted",200),("rejected",500),("rejected",None),("unknown",202)):
            with self.assertRaises(NotificationError):self.store.finish(ticket,state,http_status=status)
        result=self.store.finish(ticket,"unknown",http_status=503,error_code="graph_http_error")
        self.assertEqual((result["state"],result["reservations"]),("unknown",1))

    def test_parallel_claims_only_one_reservation_and_one_post_permission(self):
        self.configure()
        _,_,row=self.warning()
        barrier=threading.Barrier(2)
        def run():
            barrier.wait()
            ticket=self.store.claim(row["slot_key"],SCOPE)
            if ticket and self.store.reserve(ticket,budget=self.budget()):
                return self.store.begin_post(ticket,budget=self.budget())
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(lambda _:run(),range(2)))
        self.assertEqual(sum(value is not None for value in results),1)
        self.assertEqual(self.store.read(row["slot_key"])["reservations"],1)

    def test_private_targets_not_stored_in_plaintext_or_audit(self):
        self.configure()
        self.warning()
        with self.engine.connect() as c:
            serialized=json.dumps({table.name:[dict(row) for row in c.execute(sa.select(table)).mappings()]
                for table in (settings,outbox)},default=str)
            audit_rows=c.execute(sa.text("SELECT changed_fields FROM audit_log")).scalars().all()
        self.assertNotIn("first@example.invalid",serialized)
        self.assertNotIn("first@example.invalid"," ".join(audit_rows))

    def test_settings_validation_scope_fence_and_mandatory_certificate(self):
        self.configure()
        for value in (dict(self.config,recipients=[]),dict(self.config,certificate_enabled=False),
                dict(self.config,recipients=["user@example.invalid\r\nBcc:bad@example.invalid"]),
                dict(self.config,recipients=["bad.@example.invalid"]),dict(self.config,weekly_day=True)):
            with self.assertRaises(NotificationError):checked_settings(value)
        with self.assertRaises(NotificationError):self.store.save_settings(1,self.config,"b"*64,ACTOR)
        with self.assertRaises(NotificationError):self.store.save_settings(0,self.config,SCOPE,ACTOR)
        self.configure(errors_enabled=False,daily_enabled=False,weekly_enabled=False,outages_enabled=False)
        self.assertIsNotNone(self.warning()[2])

    def test_calendar_dst_fold_gap_half_open_days_and_latest_only(self):
        config=dict(self.config,daily_time="08:15")
        spring=calendar_slot("daily",stamp("2027-03-29T08:00:00+00:00"),config)
        fall=calendar_slot("daily",stamp("2027-11-01T08:00:00+00:00"),config)
        self.assertEqual(spring.end-spring.start,23*3600)
        self.assertEqual(fall.end-fall.start,25*3600)
        self.assertEqual(wall_instant(date(2027,3,28),"02:30"),stamp("2027-03-28T01:00:00+00:00"))
        self.assertEqual(wall_instant(date(2027,10,31),"02:30"),stamp("2027-10-31T00:30:00+00:00"))
        latest=calendar_slot("weekly",stamp("2027-01-04T10:00:00+00:00"),config)
        self.assertEqual(datetime.fromtimestamp(latest.start,timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("Europe/Berlin")).date(),date(2026,12,28))

    def test_exact_certificate_thresholds_and_common_budget(self):
        for remaining,level in ((864001,"healthy"),(864000,"orange"),(863999,"orange"),
                (86401,"orange"),(86400,"red"),(86399,"red"),(0,"red"),(-1,"red")):
            self.assertEqual(certificate_level(1000+remaining,1000)["severity"],level)
        budget=self.budget()
        self.assertEqual(budget.child_seconds(),60)
        self.now[0]+=30
        self.assertEqual(budget.child_seconds(),40)
        self.now[0]+=41
        self.assertEqual(budget.child_seconds(),0)
        self.assertEqual(graph_scope("A"*8+"-AAAA-AAAA-AAAA-"+"A"*12,"B"*8+"-BBBB-BBBB-BBBB-"+"B"*12,"INVOICE@example.invalid"),
            graph_scope("a"*8+"-aaaa-aaaa-aaaa-"+"a"*12,"b"*8+"-bbbb-bbbb-bbbb-"+"b"*12,"invoice@example.invalid"))

    def test_report_cohort_is_half_open_and_receipts_do_not_multiply(self):
        import types
        import test_process_queries as source_fixture
        from app.storage_plan import digest
        processing=ProcessingStore(self.engine,clock=lambda:self.now[0])
        storage=StorageStore(self.engine,destination_key="d"*64,clock=lambda:self.now[0])
        helper=types.SimpleNamespace(store=processing,storage=storage)
        slot=calendar_slot("daily",stamp("2026-12-02T09:00:00+00:00"),self.config)
        self.now[0]=slot.start
        first=source_fixture.ProcessQueryTests.mail(helper,mid="report-first",specs=[
            ("a1","invoice.pdf","recognized","PDF","invoice_fields"),
            ("a2","unknown.pdf","unknown",None,"ambiguous_pdf")])
        self.now[0]=slot.start+1
        source_fixture.ProcessQueryTests.mail(helper,mid="report-duplicate",specs=[
            ("a1","invoice.pdf","recognized","PDF","invoice_fields")])
        self.now[0]=slot.end
        source_fixture.ProcessQueryTests.mail(helper,mid="exact-end")
        self.now[0]=slot.start-1
        source_fixture.ProcessQueryTests.mail(helper,mid="before-start")
        processing.register("other@example.invalid",Message("other-source",datetime(2026,12,1,tzinfo=timezone.utc),"inbox","notFlagged"),
            [Attachment("a1","not-in-scope.pdf",2,"application/pdf",False,"file")])
        self.now[0]=slot.end+3600
        with self.engine.connect() as c:
            before={table.name:[dict(r) for r in c.execute(sa.select(table)).mappings()]
                for table in (*processing_metadata.tables.values(),*storage_metadata.tables.values())}
        report=report_cohort(self.engine,slot,digest(["invoice@example.invalid"]),as_of=self.now[0])
        self.assertEqual((report["start"],report["end"],report["as_of"]),(slot.start,slot.end,self.now[0]))
        self.assertEqual({k:report["counts"][k] for k in ("messages","attachments","unknown_open","stored_receipts","duplicates","PDF")},
            dict(messages=2,attachments=3,unknown_open=1,stored_receipts=2,duplicates=1,PDF=2))
        with self.engine.connect() as c:
            after={table.name:[dict(r) for r in c.execute(sa.select(table)).mappings()]
                for table in (*processing_metadata.tables.values(),*storage_metadata.tables.values())}
        self.assertEqual(before,after)
        # A current update does not change the created_at cohort.
        row=next(r for r in processing.get_attachments(first) if r["graph_id"]=="a2")
        processing.approved_correction(row["attachment_key"],"report-approved","PDF","synthetic-admin",self.now[0])
        updated=report_cohort(self.engine,slot,digest(["invoice@example.invalid"]),as_of=self.now[0])
        self.assertEqual(updated["counts"]["unknown_open"],0)
        self.assertEqual(updated["counts"]["messages"],2)

    def test_all_report_counts_share_one_snapshot_during_concurrent_update(self):
        from app.storage_plan import digest
        with self.engine.connect() as c:c.exec_driver_sql("PRAGMA journal_mode=WAL")
        processing=ProcessingStore(self.engine,clock=lambda:self.now[0])
        key=processing.register("invoice@example.invalid",Message("snapshot",datetime(2026,12,1,tzinfo=timezone.utc),"inbox","notFlagged"),
            [Attachment("a1","synthetic.pdf",2,"application/pdf",False,"file")])
        with self.engine.begin() as c:c.execute(attachments.update().where(attachments.c.message_key==key).values(effective_status="unknown"))
        slot=Slot("daily",self.now[0]-1,self.now[0]+1,self.now[0],self.now[0]+86400)
        changed=[]
        def update_after_mail_count(conn,cursor,statement,parameters,context,executemany):
            if changed or not statement.startswith("SELECT count(") or "FROM processing_messages" not in statement:
                return
            changed.append(True)
            with self.engine.begin() as writer:
                writer.execute(attachments.update().where(attachments.c.message_key==key).values(effective_status="ignored"))
        sa.event.listen(self.engine,"after_cursor_execute",update_after_mail_count)
        try:
            report=report_cohort(self.engine,slot,digest(["invoice@example.invalid"]),as_of=self.now[0])
        finally:sa.event.remove(self.engine,"after_cursor_execute",update_after_mail_count)
        self.assertTrue(changed)
        self.assertEqual((report["counts"]["messages"],report["counts"]["unknown_open"]),(1,1))
        self.assertEqual(report_cohort(self.engine,slot,digest(["invoice@example.invalid"]),as_of=self.now[0])["counts"]["unknown_open"],0)

    def test_old_plan_owner_cannot_reserve_after_replan(self):
        self.configure()
        _,_,first=self.warning()
        old=self.store.claim(first["slot_key"],SCOPE)
        self.store.defer(old,"graph_authentication_failed",self.now[0]+900)
        self.configure(recipients=["new@example.invalid"])
        _,_,new=self.warning()
        self.assertFalse(self.store.reserve(old,budget=self.budget()))
        self.assertGreater(new["plan_revision"],first["plan_revision"])
        self.now[0]+=901
        ticket=self.reserve(new)
        self.assertEqual(self.store.begin_post(ticket,budget=self.budget())["message"]["toRecipients"],
            [{"emailAddress":{"address":"new@example.invalid"}}])


    def test_incident_bundle_marks_attempt_in_same_reservation_and_recovers_once(self):
        from app.notification_planning import observe_incident,error_bundle,outage_slot
        self.configure()
        token=identity(["synthetic-observer"])
        first=observe_incident(None,now=self.now[0],failed=True,code="processing_source_unavailable")
        self.store.put_monitor(SCOPE,"incident",token,first,expected_revision=0)
        self.assertIsNone(error_bundle([self.store.monitor_state(SCOPE,"incident",token)],self.config,self.now[0]+899))
        self.now[0]+=900
        again=observe_incident(first,now=self.now[0],failed=True,code="processing_source_unavailable")
        self.store.put_monitor(SCOPE,"incident",token,again,expected_revision=1)
        state=self.store.monitor_state(SCOPE,"incident",token)
        bundle=error_bundle([state],self.config,self.now[0])
        slot,data,members=bundle
        row=self.store.prepare(slot,SCOPE,data,expected_version=1,as_of=self.now[0],members=members)
        ticket=self.reserve(row)
        saved=self.store.monitor_state(SCOPE,"incident",token)
        self.assertEqual(saved["data"]["last_reserved_at"],self.now[0])
        self.assertIsNone(error_bundle([saved],self.config,self.now[0]+3600))
        with self.assertRaises(NotificationError):self.store.put_monitor(SCOPE,"incident",token,again,expected_revision=2)
        outage=outage_slot(token,again,self.config,self.now[0])
        self.assertEqual(outage.kind,"outage")
        self.assertIsNone(outage_slot(token,again,self.config,self.now[0]+301))
        recovered=observe_incident(saved["data"],now=self.now[0]+60,failed=False)
        recovery=outage_slot(token,recovered,self.config,self.now[0]+60)
        self.assertEqual(recovery.kind,"recovery")
        self.assertEqual(recovery.key(self.store.instance,SCOPE),
            outage_slot(token,observe_incident(recovered,now=self.now[0]+120,failed=False),self.config,self.now[0]+120).key(self.store.instance,SCOPE))
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))

    def outage_observation(self, *, failed=True, code="graph_authentication_failed"):
        from app.notification_planning import observe_incident
        token=identity(["a1-synthetic-graph-observer"])
        before=self.store.monitor_state(SCOPE,"incident",token)
        value=observe_incident(before["data"] if before else None,now=self.now[0],
            failed=failed,code=code if failed else None)
        return token,self.store.put_monitor(SCOPE,"incident",token,value,
            expected_revision=before["revision"] if before else 0)

    def outage_plan(self, slot, observed):
        value=observed["data"]
        facts=dict(source="graph",first_seen=value["first_seen"],last_seen=value["last_seen"],
            count=1,codes=[value["code"]])
        return self.store.prepare(slot,SCOPE,facts,expected_version=self.store.configuration()["version"],
            as_of=self.now[0],members=[observed["monitor_key"]])

    def test_a1_delayed_outage_unknown_and_exact_repeat_boundary(self):
        from app.notification_planning import outage_slot
        self.configure()
        start=self.now[0]
        token,_=self.outage_observation()
        repeat=self.config["outage_repeat_hours"]*3600
        self.now[0]=start+repeat+self.config["outage_after_minutes"]*60-1
        token,observed=self.outage_observation()
        first_slot=outage_slot(token,observed["data"],self.config,self.now[0])
        first=self.outage_plan(first_slot,observed)
        first_at=self.now[0]
        ticket=self.reserve(first)
        self.assertIsNotNone(self.store.begin_post(ticket,budget=self.budget()))
        self.store.recover(first["slot_key"],stopped_owner=ticket["owner"])
        self.assertEqual(self.store.read(first["slot_key"])["state"],"unknown")
        self.now[0]+=1
        # Delayed worker still holds the genuine pre-reservation snapshot, at current time.
        stale_slot=outage_slot(token,observed["data"],self.config,self.now[0])
        stale=self.outage_plan(stale_slot,observed)
        token,observed=self.outage_observation()
        self.assertIsNone(outage_slot(token,observed["data"],self.config,self.now[0]))
        stale_ticket=self.store.claim(stale["slot_key"],SCOPE)
        self.assertIsNotNone(stale_ticket)
        self.assertFalse(self.store.reserve(stale_ticket,budget=self.budget()))
        deferred=self.store.read(stale["slot_key"])
        self.assertEqual((deferred["state"],deferred["reservations"],deferred["not_before"]),
            ("prepared",0,first_at+repeat))
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",token)["data"]["last_reserved_at"],first_at)
        self.configure(recipients=["changed@example.invalid"])
        fresh_slot=outage_slot(token,stale_slot.observation(),self.config,self.now[0])
        self.outage_plan(fresh_slot,dict(observed,data=stale_slot.observation()))
        self.assertIsNone(self.store.claim(stale["slot_key"],SCOPE))
        self.now[0]=first_at+repeat-1
        token,observed=self.outage_observation()
        self.assertIsNone(outage_slot(token,observed["data"],self.config,self.now[0]))
        self.assertIsNone(self.store.claim(stale["slot_key"],SCOPE))
        self.now[0]+=1
        token,observed=self.outage_observation()
        slot=outage_slot(token,observed["data"],self.config,self.now[0])
        self.assertIsNotNone(slot)
        next_row=self.outage_plan(slot,observed)
        self.assertEqual(next_row["slot_key"],stale["slot_key"])
        next_ticket=self.reserve(next_row)
        self.assertIsNotNone(self.store.begin_post(next_ticket,budget=self.budget()))
        self.assertIsNone(self.store.begin_post(next_ticket,budget=self.budget()))
        self.assertEqual(self.now[0]-first_at,86400)
        self.assertFalse(self.store.reserve(ticket,budget=self.budget()))

    def test_a1_concurrent_stale_outage_plans_only_one_reservation(self):
        from app.notification_planning import outage_slot
        self.configure()
        token,_=self.outage_observation()
        self.now[0]+=900
        token,observed=self.outage_observation()
        slot=outage_slot(token,observed["data"],self.config,self.now[0])
        barrier=threading.Barrier(2)
        def run(_):
            barrier.wait()
            row=self.outage_plan(slot,observed)
            ticket=self.store.claim(row["slot_key"],SCOPE)
            return row,ticket,bool(ticket and self.store.reserve(ticket,budget=self.budget()))
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes=list(executor.map(run,range(2)))
        self.assertEqual(sum(accepted for _,_,accepted in outcomes),1)
        self.assertEqual(len({row["slot_key"] for row,_,_ in outcomes}),1)
        row,ticket,_=next(value for value in outcomes if value[2])
        self.store.recover(row["slot_key"],stopped_owner=ticket["owner"])
        self.assertEqual(self.store.read(row["slot_key"])["state"],"unknown")
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",token)["data"]["last_reserved_at"],self.now[0])

    def test_a1_outage_membership_keeps_episode_and_recovery_is_separate(self):
        from app.notification_planning import outage_slot
        self.configure()
        token,_=self.outage_observation()
        self.now[0]+=900
        token,observed=self.outage_observation()
        slot=outage_slot(token,observed["data"],self.config,self.now[0])
        with self.assertRaises(NotificationError):
            self.store.prepare(slot,SCOPE,{},expected_version=1,as_of=self.now[0])
        row=self.outage_plan(slot,observed)
        ticket=self.reserve(row)
        reserved=self.store.monitor_state(SCOPE,"incident",token)
        self.now[0]+=1
        token,recovered=self.outage_observation(failed=False)
        recovery=outage_slot(token,recovered["data"],self.config,self.now[0])
        recovery_row=self.outage_plan(recovery,recovered)
        self.reserve(recovery_row)
        self.assertEqual(self.store.read(row["slot_key"])["reservations"],1)

    def test_a1_k2_first_prepare_of_old_episode_is_rejected_without_marking_new_episode(self):
        from dataclasses import replace
        from app.notification_planning import outage_slot
        self.configure()
        start=self.now[0]
        token,_=self.outage_observation()
        self.now[0]=start+86400+900-1
        token,old=self.outage_observation()
        slot=outage_slot(token,old["data"],self.config,self.now[0])
        first=self.outage_plan(slot,old)
        ticket=self.reserve(first)
        self.store.begin_post(ticket,budget=self.budget())
        self.store.finish(ticket,"accepted",http_status=202)  # Synthetic store acknowledgment only.
        self.now[0]+=1
        self.outage_observation(failed=False)
        token,current=self.outage_observation(code="graph_forbidden")
        self.assertEqual(current["data"]["episode"],old["data"]["episode"]+1)
        self.assertIsNone(outage_slot(token,current["data"],self.config,self.now[0]))
        delayed=outage_slot(token,old["data"],self.config,self.now[0])
        self.assertIsNotNone(delayed)
        with self.assertRaises(NotificationError):self.outage_plan(delayed,old)
        with self.assertRaises(NotificationError) as missing:self.store.read(delayed.key(self.store.instance,SCOPE))
        self.assertEqual(missing.exception.status,404)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",token),current)
        self.now[0]+=899
        token,current=self.outage_observation(code="graph_forbidden")
        self.assertIsNone(outage_slot(token,current["data"],self.config,self.now[0]))
        # Relabeling the old slot with the new snapshot still cannot bypass qualification/period binding.
        relabeled=replace(delayed,tag=identity([token,current["data"]["episode"]]),
            **{name:current["data"][name] for name in ("episode","first_seen","last_seen","last_failure","code","resolved_at")})
        with self.assertRaises(NotificationError):self.outage_plan(relabeled,current)
        self.assertIsNone(self.store.monitor_state(SCOPE,"incident",token)["data"]["last_reserved_at"])
        self.now[0]+=1
        token,current=self.outage_observation(code="graph_forbidden")
        fresh=outage_slot(token,current["data"],self.config,self.now[0])
        self.assertIsNotNone(fresh)
        allowed=self.reserve(self.outage_plan(fresh,current))
        payload=self.store.begin_post(allowed,budget=self.budget())
        self.assertIn("graph_forbidden",payload["message"]["body"]["content"])
        self.assertNotIn("graph_authentication_failed",payload["message"]["body"]["content"])

    def test_a1_k2_slot_facts_and_membership_cannot_be_mixed(self):
        from dataclasses import replace
        from app.notification_planning import outage_slot
        self.configure()
        token,_=self.outage_observation()
        self.now[0]+=900
        token,observed=self.outage_observation()
        slot=outage_slot(token,observed["data"],self.config,self.now[0])
        for changed in (dict(codes=["graph_forbidden"]),dict(first_seen=self.now[0]),
                dict(last_seen=self.now[0]-1),dict(count=2)):
            facts=dict(source="graph",first_seen=slot.first_seen,last_seen=slot.last_seen,count=1,codes=[slot.code])
            facts.update(changed)
            with self.assertRaises(NotificationError):self.store.prepare(slot,SCOPE,facts,expected_version=1,
                as_of=self.now[0],members=[observed["monitor_key"]])
        unbound=Slot(slot.kind,slot.start,slot.end,slot.due,slot.stale,slot.tag)
        for invalid in (unbound,replace(slot,start=slot.start+1),replace(slot,stale=slot.stale+1),
                replace(slot,token="b"*64,tag=identity(["b"*64,slot.episode]))):
            with self.assertRaises(NotificationError):self.outage_plan(invalid,observed)
        facts=dict(source="graph",first_seen=slot.first_seen,last_seen=slot.last_seen,count=1,codes=[slot.code])
        with self.assertRaises(NotificationError):self.store.prepare(slot,SCOPE,facts,expected_version=1,
            as_of=self.now[0],members=["b"*64])
        self.assertEqual(self.store.history(SCOPE)["total"],0)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",token),observed)

    def test_a1_k2_existing_plan_and_unconfigured_plan_cannot_change_episode(self):
        from app.notification_planning import outage_slot
        token,_=self.outage_observation()
        self.now[0]+=900
        token,old=self.outage_observation()
        slot=outage_slot(token,old["data"],self.config,self.now[0])
        missing=self.outage_plan(slot,old)
        self.assertEqual(missing["error_code"],"notification_settings_missing")
        self.configure()
        row=self.outage_plan(slot,old)
        ticket=self.store.claim(row["slot_key"],SCOPE)
        self.now[0]+=1
        self.outage_observation(failed=False)
        token,current=self.outage_observation(code="graph_forbidden")
        with self.assertRaises(NotificationError):self.store.reserve(ticket,budget=self.budget())
        self.store.recover(row["slot_key"],stopped_owner=ticket["owner"])
        before=self.store.read(row["slot_key"])
        # Identical-version replay and a configuration-triggered replan both reject the stale episode.
        with self.assertRaises(NotificationError):self.outage_plan(slot,old)
        self.configure(recipients=["changed@example.invalid"])
        with self.assertRaises(NotificationError):self.outage_plan(slot,old)
        with self.assertRaises(NotificationError):self.outage_plan(slot,current)
        self.assertEqual(self.store.read(row["slot_key"]),before)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",token),current)

    def error_observation(self,label,*,failed=True,code="processing_source_unavailable"):
        from app.notification_planning import observe_incident
        token=identity(["a2-synthetic-cause",label])
        before=self.store.monitor_state(SCOPE,"incident",token)
        value=observe_incident(before["data"] if before else None,now=self.now[0],failed=failed,
            code=code if failed else None)
        return self.store.put_monitor(SCOPE,"incident",token,value,expected_revision=before["revision"] if before else 0)

    def bundle_plan(self,bundle):
        slot,facts,members=bundle
        return self.store.prepare(slot,SCOPE,facts,expected_version=self.store.configuration()["version"],
            as_of=self.now[0],members=members)

    def test_a2_delayed_bundle_unknown_and_exact_24_hour_boundary(self):
        from app.notification_planning import error_bundle
        self.configure()
        self.now[0]=stamp("2026-12-01T11:45:00+00:00")
        self.error_observation("a")
        self.now[0]=stamp("2026-12-01T12:59:59+00:00")
        old=self.error_observation("a")
        first=self.bundle_plan(error_bundle([old],self.config,self.now[0]))
        first_at=self.now[0]
        ticket=self.reserve(first)
        self.store.begin_post(ticket,budget=self.budget())
        self.store.finish(ticket,"unknown",http_status=503,error_code="graph_http_error")
        self.now[0]+=1
        current=self.error_observation("a")
        self.assertIsNone(error_bundle([current],self.config,self.now[0]))
        late=self.bundle_plan(error_bundle([old],self.config,self.now[0]))
        late_ticket=self.store.claim(late["slot_key"],SCOPE)
        self.assertFalse(self.store.reserve(late_ticket,budget=self.budget()))
        self.assertIsNone(self.store.begin_post(late_ticket,budget=self.budget()))
        self.assertEqual(self.store.read(late["slot_key"])["not_before"],first_at+86400)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","a"])),current)
        self.now[0]=first_at+86400-1
        current=self.error_observation("a")
        self.assertIsNone(error_bundle([current],self.config,self.now[0]))
        before=self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","a"]))
        stale=self.bundle_plan(error_bundle([old],self.config,self.now[0]))
        stale_ticket=self.store.claim(stale["slot_key"],SCOPE)
        self.assertFalse(self.store.reserve(stale_ticket,budget=self.budget()))
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","a"])),before)
        self.now[0]+=1
        current=self.error_observation("a")
        ready=self.bundle_plan(error_bundle([current],self.config,self.now[0]))
        allowed=self.reserve(ready)
        self.assertIsNotNone(self.store.begin_post(allowed,budget=self.budget()))
        self.assertIsNone(self.store.begin_post(allowed,budget=self.budget()))
        self.assertEqual(self.now[0]-first_at,86400)
        self.assertEqual(self.store.read(first["slot_key"])["state"],"unknown")

    def test_a2_global_hour_waits_from_actual_reservation_for_another_cause(self):
        from app.notification_planning import error_bundle
        self.configure()
        self.now[0]=stamp("2026-12-01T11:45:00+00:00")
        self.error_observation("a");self.error_observation("b",code="processing_destination_unavailable")
        self.now[0]=stamp("2026-12-01T12:59:59+00:00")
        first=self.bundle_plan(error_bundle([self.error_observation("a")],self.config,self.now[0]))
        first_at=self.now[0]
        ticket=self.reserve(first)
        self.store.recover(first["slot_key"],stopped_owner=ticket["owner"])
        self.now[0]+=1
        observed=self.error_observation("b",code="processing_destination_unavailable")
        second=self.bundle_plan(error_bundle([observed],self.config,self.now[0]))
        other=self.store.claim(second["slot_key"],SCOPE)
        self.assertFalse(self.store.reserve(other,budget=self.budget()))
        self.assertEqual(self.store.read(second["slot_key"])["not_before"],first_at+3600)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","b"])),observed)
        self.now[0]=first_at+3599
        self.assertIsNone(self.store.claim(second["slot_key"],SCOPE))
        self.now[0]+=1
        ready=self.bundle_plan(error_bundle([self.error_observation("b",code="processing_destination_unavailable")],self.config,self.now[0]))
        allowed=self.reserve(ready)
        self.assertIsNotNone(self.store.begin_post(allowed,budget=self.budget()))
        self.assertEqual(self.now[0]-first_at,3600)

    def test_a2_old_selection_first_prepare_replay_and_reserve_do_not_relabel_members(self):
        from app.notification_planning import error_bundle
        self.configure()
        self.error_observation("a");self.error_observation("b")
        self.now[0]+=900
        old_a=self.error_observation("a");old_b=self.error_observation("b")
        old=error_bundle([old_a,old_b],self.config,self.now[0])
        self.now[0]+=1
        self.error_observation("a",failed=False)
        current_a=self.error_observation("a",code="processing_new_failure")
        before_b=self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","b"]))
        with self.assertRaises(NotificationError):self.bundle_plan(old)
        self.assertEqual(self.store.history(SCOPE)["total"],0)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","a"])),current_a)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","b"])),before_b)
        fresh=error_bundle([current_a,before_b],self.config,self.now[0])
        self.assertEqual(fresh[1]["count"],1)
        row=self.bundle_plan(fresh)
        ticket=self.store.claim(row["slot_key"],SCOPE)
        self.now[0]+=1
        resolved=self.error_observation("b",failed=False)
        with self.assertRaises(NotificationError):self.store.reserve(ticket,budget=self.budget())
        self.store.recover(row["slot_key"],stopped_owner=ticket["owner"])
        before=self.store.read(row["slot_key"])
        with self.assertRaises(NotificationError):self.bundle_plan(fresh)
        self.configure(recipients=["changed@example.invalid"])
        with self.assertRaises(NotificationError):self.bundle_plan(fresh)
        self.assertEqual(self.store.read(row["slot_key"]),before)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","b"])),resolved)
        self.assertIsNone(resolved["data"]["last_reserved_at"])

    def test_a2_fresh_consistent_replan_drops_cooling_member_without_marking_it_again(self):
        from app.notification_planning import error_bundle
        self.configure()
        self.now[0]=stamp("2026-12-01T11:45:00+00:00")
        self.error_observation("a");self.error_observation("b",code="processing_other_failure")
        self.now[0]=stamp("2026-12-01T12:59:59+00:00")
        old_a=self.error_observation("a");old_b=self.error_observation("b",code="processing_other_failure")
        first=self.bundle_plan(error_bundle([old_a],self.config,self.now[0]))
        first_at=self.now[0]
        self.reserve(first)
        self.now[0]+=1
        late=self.bundle_plan(error_bundle([old_a,old_b],self.config,self.now[0]))
        stale_ticket=self.store.claim(late["slot_key"],SCOPE)
        self.assertFalse(self.store.reserve(stale_ticket,budget=self.budget()))
        self.assertEqual(self.store.read(late["slot_key"])["not_before"],first_at+86400)
        self.assertIsNone(self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","b"]))["data"]["last_reserved_at"])
        self.now[0]=first_at+3600
        current_a=self.error_observation("a");current_b=self.error_observation("b",code="processing_other_failure")
        fresh=error_bundle([current_a,current_b],self.config,self.now[0])
        self.assertEqual(fresh[1]["count"],1)
        replanned=self.bundle_plan(fresh)
        self.assertEqual(replanned["slot_key"],late["slot_key"])
        self.assertGreater(replanned["plan_revision"],late["plan_revision"])
        self.assertFalse(self.store.reserve(stale_ticket,budget=self.budget()))
        allowed=self.reserve(replanned)
        body=self.store.begin_post(allowed,budget=self.budget())["message"]["body"]["content"]
        self.assertIn("processing_other_failure",body)
        self.assertNotIn("processing_source_unavailable",body)
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause","a"]))["data"]["last_reserved_at"],first_at)

    def test_a2_mixed_facts_members_and_parallel_selection_keep_payload_coherent(self):
        from app.notification_planning import error_bundle
        self.configure()
        self.error_observation("a");self.error_observation("b",code="processing_other_failure")
        self.now[0]+=900
        a=self.error_observation("a");b=self.error_observation("b",code="processing_other_failure")
        bundles=[error_bundle([value],self.config,self.now[0]) for value in (a,b)]
        slot,facts,members=bundles[0]
        for bad in (dict(facts,count=2),dict(facts,codes=["processing_other_failure"]),dict(facts,source="api")):
            with self.assertRaises(NotificationError):self.store.prepare(slot,SCOPE,bad,expected_version=1,
                as_of=self.now[0],members=members)
        with self.assertRaises(NotificationError):self.store.prepare(slot,SCOPE,facts,expected_version=1,
            as_of=self.now[0],members=[b["monitor_key"]])
        unbound=Slot(slot.kind,slot.start,slot.end,slot.due,slot.stale)
        with self.assertRaises(NotificationError):self.store.prepare(unbound,SCOPE,facts,expected_version=1,
            as_of=self.now[0],members=members)
        self.assertEqual(self.store.history(SCOPE)["total"],0)
        barrier=threading.Barrier(2)
        def run(bundle):
            barrier.wait()
            row=self.bundle_plan(bundle)
            ticket=self.store.claim(row["slot_key"],SCOPE)
            return row,ticket,bool(ticket and self.store.reserve(ticket,budget=self.budget()))
        with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(run,bundles))
        self.assertEqual(sum(value[2] for value in results),1)
        row,ticket,_=next(value for value in results if value[2])
        body=self.store.begin_post(ticket,budget=self.budget())["message"]["body"]["content"]
        marked=[]
        for label,code in (("a","processing_source_unavailable"),("b","processing_other_failure")):
            state=self.store.monitor_state(SCOPE,"incident",identity(["a2-synthetic-cause",label]))
            if state["data"]["last_reserved_at"] is not None:marked.append(code)
        self.assertEqual(len(marked),1)
        self.assertIn(marked[0],body)
        self.assertIsNone(self.store.begin_post(ticket,budget=self.budget()))

    def test_history_and_readback_are_scope_bound_without_creating_a_new_request(self):
        self.configure()
        request=str(uuid4())
        self.assertIsNone(self.store.test_receipt(request,1,SCOPE,ACTOR))
        row=self.store.request_test(request,1,SCOPE,ACTOR)
        self.configure(recipients=["new@example.invalid"])
        self.assertEqual(self.store.test_receipt(request,1,SCOPE,ACTOR)["slot_key"],row["slot_key"])
        self.assertIsNone(self.store.test_receipt(request,1,SCOPE,"ad:"+"2"*32))
        self.assertEqual(self.store.history(SCOPE)["total"],1)
        self.assertEqual(self.store.history("b"*64)["total"],0)
        with self.assertRaises(NotificationError):self.store.claim(row["slot_key"],"b"*64)
        with self.assertRaises(NotificationError):self.store.test_receipt(request,2,SCOPE,ACTOR)


class NotificationMigrationTests(unittest.TestCase):
    def test_006_to007_and_repeated_head_preserve_every_old_table_and_identity(self):
        from alembic import command
        from alembic.config import Config
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            engine=sa.create_engine("sqlite:///"+str(Path(folder)/"upgrade.sqlite"),poolclass=sa.pool.NullPool)
            self.addCleanup(engine.dispose)
            config=Config(str(Path(__file__).resolve().parents[1]/"alembic.ini"))
            config.set_main_option("script_location",str(Path(__file__).resolve().parents[1]/"migrations"))
            with patch("app.database.make_engine",return_value=engine):
                command.upgrade(config,"006_processing_web")
                with engine.begin() as c:
                    c.execute(sa.text("INSERT INTO configuration_versions (id,settings,bind_cipher,created_at,actor) VALUES (1,'{}','synthetic-existing-ldap-cipher',1,'fixture')"))
                    c.execute(sa.text("INSERT INTO configuration_head (singleton,active_id) VALUES (1,1)"))
                def snapshot():
                    with engine.connect() as c:
                        result={}
                        for name in sa.inspect(c).get_table_names():
                            if name=="alembic_version":continue
                            table=sa.Table(name,sa.MetaData(),autoload_with=c)
                            result[name]=dict(columns=[col.name for col in table.columns],
                                rows=[dict(row) for row in c.execute(sa.select(table).order_by(*table.primary_key.columns)).mappings()])
                        return result
                before=snapshot()
                command.upgrade(config,"head")
                command.upgrade(config,"head")
                after=snapshot()
                for name in before:self.assertEqual(before[name],after[name])
                self.assertEqual(set(after)-set(before),{"notification_settings","notification_outbox","notification_monitor"})
                self.assertEqual(after["notification_settings"]["rows"][0]["version"],0)
                self.assertIsNone(after["notification_settings"]["rows"][0]["payload_cipher"])
                path=Path(__file__).resolve().parents[1]/"migrations/versions/007_notifications.py"
                spec=importlib.util.spec_from_file_location("notification_migration_fixture",path)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                with engine.begin() as c,Operations.context(MigrationContext.configure(c)):
                    module.upgrade()
                    with self.assertRaises(RuntimeError):module.downgrade()
                self.assertEqual(snapshot(),after)
