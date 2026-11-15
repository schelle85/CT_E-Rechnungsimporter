from contextlib import nullcontext
import json
import os
from functools import partial
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import httpx
import sqlalchemy as sa
from app.notification_model import identity
from app.notification_observers import observe_and_plan,probe_api,journal_errors,record_incident
from app.notification_schema007 import monitor,outbox,settings,metadata as notification_metadata
from app.notification_state import NotificationStore
from app.processing_state import ProcessingStore,messages,attachments,metadata as processing_metadata
from app.storage_state import StorageStore,metadata as storage_metadata
from app.notification_service import NotificationService
from app.notification_runtime import run_job
import test_process_queries as query_fixture
from notification_test_support import Fixture,SCOPE,CONFIG,material


class ObserverTests(Fixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        if os.environ.get("INTEGRATION_DB")=="1":
            # Existing opt-in isolated DB mode, never a production fixture switch.
            from app.database import make_engine
            self.engine=make_engine();self.addCleanup(self.engine.dispose)
            with self.engine.begin() as c:
                for group in (notification_metadata,processing_metadata,storage_metadata):
                    for table in reversed(group.sorted_tables):c.execute(table.delete())
                c.execute(settings.insert().values(singleton=1,version=0,actor="schema007",updated_at=0))
                instance=c.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
            self.store=NotificationStore(self.engine,self.cipher,instance,clock=lambda:self.now[0])
        self.configure(daily_enabled=False,weekly_enabled=False,outage_after_minutes=5)
        self.certificate=material()
        self.journal=SimpleNamespace(store=ProcessingStore(self.engine,clock=lambda:self.now[0]),
            storage=StorageStore(self.engine,destination_key="d"*64,clock=lambda:self.now[0]),now=self.now)

    def mail(self,**values):return query_fixture.ProcessQueryTests.mail(self.journal,**values)

    def cycle(self,*,api=True,graph=200):
        service=self.service(self.certificate,handler=lambda _:httpx.Response(graph,json={"id":"inbox"}))
        return observe_and_plan(service,budget=self.budget(),api_probe=lambda *_:(api,None if api else "notification_api_unavailable"))

    def test_empty_or_unknown_journal_and_inactive_jobs_do_not_create_failure(self):
        self.assertEqual(self.cycle(),[])
        self.mail()
        self.now[0]+=900
        self.assertEqual(self.cycle(),[])
        errors,_=journal_errors(self.store,SCOPE,"invoice@example.invalid")
        self.assertEqual(errors,{})
        self.assertEqual(self.store.history(SCOPE)["total"],0)

    def test_actual_error_is_stable_bundled_neutral_and_counted_once_after_reservation(self):
        self.mail(specs=[("a1","private-invoice.pdf","failed",None,"processing_classifier_unavailable")])
        self.assertEqual(self.cycle(),[])
        with self.engine.connect() as c:
            before=[dict(row) for row in c.execute(sa.select(monitor).where(monitor.c.payload.like('%"source":"processing"%'))).mappings()]
        self.assertEqual(len(before),1)
        first=json.loads(before[0]["payload"])["first_seen"]
        self.now[0]+=900
        plans=self.cycle();self.assertEqual(len(plans),1)
        row=plans[0];self.assertEqual(row["kind"],"errors")
        with self.engine.connect() as c:
            raw=c.execute(sa.select(outbox).where(outbox.c.slot_key==row["slot_key"])).mappings().one()
        payload=self.store._decrypt(raw["payload_cipher"])
        self.assertNotIn("private-invoice",json.dumps(payload))
        self.assertIn("processing_classifier_unavailable",json.dumps(payload))
        self.assertIn("Beobachtete Ereignisse: 1",json.dumps(payload))
        ticket=self.store.claim(row["slot_key"],SCOPE)
        self.assertTrue(self.store.reserve(ticket,budget=self.budget()))
        self.assertIsNotNone(self.store.begin_post(ticket,budget=self.budget()))
        self.store.finish(ticket,"unknown")
        self.now[0]+=1;self.assertEqual(self.cycle(),[])
        with self.engine.connect() as c:
            data=json.loads(c.execute(sa.select(monitor.c.payload).where(monitor.c.monitor_key==before[0]["monitor_key"])).scalar_one())
        self.assertEqual(data["first_seen"],first)
        self.assertEqual(data["last_reserved_at"],self.now[0]-1)

    def test_actual_resolution_retires_unreserved_bundle_without_changing_journal(self):
        key=self.mail(specs=[("a1","failed.pdf","failed",None,"processing_classifier_unavailable")])
        self.cycle();self.now[0]+=900;row=self.cycle()[0]
        with self.engine.begin() as c:
            c.execute(attachments.update().where(attachments.c.message_key==key).values(effective_status="ignored",error_code=None))
            c.execute(messages.update().where(messages.c.message_key==key).values(state="done",error_code=None))
        with self.engine.connect() as c:
            before=[dict(value) for value in c.execute(sa.select(messages)).mappings()]
        self.now[0]+=1;self.assertEqual(self.cycle(),[])
        self.assertEqual(self.store.read(row["slot_key"])["state"],"obsolete")
        with self.engine.connect() as c:self.assertEqual([dict(value) for value in c.execute(sa.select(messages)).mappings()],before)
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))

    def test_api_and_graph_outages_require_fresh_observed_duration_and_recover_separately(self):
        for source in ("api","graph"):
            with self.subTest(source=source):
                self.now[0]+=86401
                bad=dict(api=source!="api",graph=403 if source=="graph" else 200)
                self.assertEqual(self.cycle(**bad),[])
                self.now[0]+=299;self.assertEqual(self.cycle(**bad),[])
                self.now[0]+=1;plans=self.cycle(**bad)
                row=next(value for value in plans if value["kind"]=="outage")
                self.now[0]+=1;recovery=self.cycle()
                self.assertEqual(self.store.read(row["slot_key"])["state"],"obsolete")
                recovered=next(value for value in recovery if value["kind"]=="recovery")
                self.assertNotEqual(recovered["slot_key"],row["slot_key"])
                ticket=self.store.claim(recovered["slot_key"],SCOPE)
                self.assertTrue(self.store.reserve(ticket,budget=self.budget()))
                self.assertIsNotNone(self.store.begin_post(ticket,budget=self.budget()))
                self.store.finish(ticket,"accepted",http_status=202)

    def test_graph_retry_after_does_not_turn_cached_failure_into_fresh_availability(self):
        self.cycle(graph=403)
        token=identity(["availability","graph"])
        before=self.store.monitor_state(SCOPE,"incident",token)
        self.store.scope_backoff(SCOPE,self.now[0]+900)
        self.now[0]+=301
        plans=self.cycle()
        self.assertFalse(any(value["kind"] in {"outage","recovery"} for value in plans))
        self.assertEqual(self.store.monitor_state(SCOPE,"incident",token),before)

    def test_retirement_does_not_reset_reserved_history(self):
        self.cycle(api=False);self.now[0]+=300;row=self.cycle(api=False)[0]
        ticket=self.store.claim(row["slot_key"],SCOPE)
        self.assertTrue(self.store.reserve(ticket,budget=self.budget()))
        self.assertIsNotNone(self.store.begin_post(ticket,budget=self.budget()))
        before=self.store.finish(ticket,"unknown")
        self.now[0]+=1;self.cycle()
        self.assertEqual(self.store.read(row["slot_key"]),before)

    def test_api_probe_is_bounded_same_instance_and_not_a_graph_or_mail_action(self):
        calls=[]
        def factory(response):return lambda **kwargs:httpx.Client(transport=httpx.MockTransport(lambda request:(calls.append(request) or response)),**kwargs)
        with patch("app.notification_observers.request_deadline",side_effect=lambda *_:nullcontext()):
            ready=probe_api(self.store.instance,self.budget(),client_factory=factory(httpx.Response(200,json={"status":"ready","instance_id":self.store.instance})))
            self.assertEqual(ready,(True,None))
            wrong=probe_api(self.store.instance,self.budget(),client_factory=factory(httpx.Response(200,json={"status":"ready","instance_id":"other"})))
            self.assertEqual(wrong,(False,"notification_api_identity"))
            huge=probe_api(self.store.instance,self.budget(),client_factory=factory(httpx.Response(200,content=b"x"*4097)))
            self.assertEqual(huge,(False,"notification_api_unavailable"))
        self.assertTrue(all(request.method=="GET" and str(request.url)=="http://api:8000/api/health/ready" for request in calls))

    def test_bounded_scan_rechecks_unselected_original_cause_before_resolving(self):
        self.mail(mid="old",specs=[("a1","old.pdf","failed",None,"processing_classifier_unavailable")])
        self.cycle()
        original,_=journal_errors(self.store,SCOPE,"invoice@example.invalid")
        for index in range(100):
            self.now[0]+=1
            self.mail(mid="new"+str(index),specs=[("a1","new.pdf","failed",None,"processing_classifier_unavailable")])
        current,resolved=journal_errors(self.store,SCOPE,"invoice@example.invalid")
        self.assertTrue(set(original)<=set(current))
        self.assertFalse(set(original)&{token for token,_ in resolved})

    def test_runtime_plan_reaches_real_observers_without_dispatching_or_scheduling(self):
        def service(store,config,certificate,**values):
            return NotificationService(store,config,certificate,client_factory=self.factory(),**values)
        observe=partial(observe_and_plan,api_probe=lambda *_:(False,"notification_api_unavailable"))
        with patch("app.notification_runtime.make_engine",return_value=self.engine),patch(
                "app.notification_runtime.GraphConfig.load",return_value=CONFIG),patch(
                "app.notification_runtime.load_notification_cipher",return_value=self.cipher),patch(
                "app.notification_runtime.NotificationStore",return_value=self.store),patch(
                "app.notification_runtime.CertificateMaterial.load",return_value=self.certificate),patch(
                "app.notification_runtime.NotificationService",side_effect=service),patch(
                "app.notification_observers.observe_and_plan",side_effect=observe):
            first=run_job(dict(command="plan",deadline=time.monotonic()+20))
            self.assertEqual(first["receipts"],[])
            self.now[0]+=300
            second=run_job(dict(command="plan",deadline=time.monotonic()+20))
        self.assertFalse(second["automatic_schedule_active"])
        self.assertEqual([row["kind"] for row in second["receipts"]],["outage"])
        self.assertEqual(second["receipts"][0]["reservations"],0)
        self.assertTrue(all(request.method=="GET" for request in self.http_calls))
