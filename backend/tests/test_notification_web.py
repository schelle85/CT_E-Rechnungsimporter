"""Actual AD/session boundary with synthetic directory and real journal rows."""
from datetime import datetime,timezone
import json
import unittest
import asyncio
import time
from uuid import uuid4
from unittest.mock import patch
import sqlalchemy as sa
from app.notification_certificate import record_certificate
from app.notification_model import CERTIFICATE_TOKEN,DEFAULTS,OperationBudget
from cryptography.fernet import Fernet
from app.notification_schema007 import metadata,outbox,settings
from app.notification_state import NotificationStore
from app.notification_queries import report_range
import test_process_api as process_fixture
from notification_test_support import CONFIG,SCOPE,material


class NotificationWebFixture:
    async def asyncSetUp(self):
        await process_fixture.ProcessApiTests.asyncSetUp(self)
        self.now[0]=int(datetime(2026,12,1,12,tzinfo=timezone.utc).timestamp())
        with self.engine.begin() as c:
            for table in reversed(metadata.sorted_tables):c.execute(table.delete())
            c.execute(settings.insert().values(singleton=1,version=0,actor="schema007",updated_at=0))
            instance=c.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
        self.notifications=NotificationStore(self.engine,None,instance,clock=lambda:self.now[0])
        self.config_patch=patch("app.notification_routes.graph_config",return_value=CONFIG)
        self.config_patch.start();self.addCleanup(self.config_patch.stop)
        self.certificate=material(days=30)
        self.pem_patch=patch("app.notification_routes.CertificateMaterial.load",side_effect=lambda _:self.certificate)
        self.pem_patch.start();self.addCleanup(self.pem_patch.stop)

    asyncTearDown=process_fixture.ProcessApiTests.asyncTearDown
    challenge=process_fixture.ProcessApiTests.challenge
    headers=process_fixture.ProcessApiTests.headers
    login=process_fixture.ProcessApiTests.login
    mail=process_fixture.ProcessApiTests.mail


class NotificationReadTests(NotificationWebFixture,unittest.IsolatedAsyncioTestCase):
    async def test_reports_use_real_rows_and_snapshot_without_creating_mail(self):
        await self.login("reader")
        query="/api/admin/reports?period=daily&anchor=2026-12-01"
        empty=await self.client.get(query)
        self.assertEqual(empty.status_code,200,empty.text)
        self.assertEqual(empty.json()["counts"]["messages"],0)
        self.mail(specs=[("a1","unknown.pdf","unknown",None,"ambiguous_pdf"),
            ("a2","invoice.pdf","recognized","PDF","pdf_invoice")])
        value=(await self.client.get(query)).json()
        self.assertEqual((value["counts"]["messages"],value["counts"]["attachments"],value["counts"]["unknown_open"],value["counts"]["stored_receipts"]),(1,2,1,1))
        self.assertEqual(value["counts"]["PDF"],1)
        self.assertFalse(value["synthetic"])
        self.assertEqual((await self.client.get("/api/admin/reports?period=daily&anchor=2026-11-30")).json()["counts"]["messages"],0)
        weekly=(await self.client.get("/api/admin/reports?period=weekly&anchor=2026-12-02")).json()
        self.assertEqual(weekly["counts"],value["counts"])
        self.assertEqual(weekly["start"],int(datetime(2026,11,29,23,tzinfo=timezone.utc).timestamp()))
        with self.engine.connect() as c:self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(outbox)).scalar_one(),0)

    async def test_current_ad_both_roles_and_invalid_ranges(self):
        paths=("/api/admin/reports","/api/notifications/certificate")
        for path in paths:self.assertEqual((await self.client.get(path)).status_code,401)
        for role in ("reader","admin"):
            await self.login(role)
            for path in paths:
                response=await self.client.get(path)
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.headers["cache-control"],"no-store")
            for query in ("period=range&from_date=2026-12-02&to_date=2026-12-01","period=range","anchor=invalid","period=range&from_date=2020-01-01&to_date=2026-01-01"):
                self.assertEqual((await self.client.get("/api/admin/reports?"+query)).status_code,422)
        self.directory.rows["1"*32]["attributes"]["memberOf"]=[]
        for path in paths:self.assertEqual((await self.client.get(path)).status_code,401)

    async def test_certificate_thresholds_local_file_and_open_series_are_separate(self):
        old=material(days=2)
        record_certificate(self.notifications,SCOPE,old.metadata(self.now[0]),expected_revision=0)
        before=self.notifications.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)
        for remaining,severity in ((10*86400+1,"healthy"),(10*86400,"orange"),(86400,"red"),(0,"red"),(-1,"red")):
            self.now[0]=self.certificate.expires_at-remaining
            await self.login("reader")
            response=await self.client.get("/api/notifications/certificate")
            self.assertEqual(response.status_code,200,response.text)
            data=response.json()
            self.assertEqual(data["local"]["severity"],severity)
            self.assertEqual(data["local"]["remaining_seconds"],remaining)
            self.assertEqual(data["warning"]["fingerprint"],old.fingerprint)
            self.assertIsNone(data["proof"])
            for secret in ("pem","PRIVATE KEY","cipher","bind_password","synthetic-token"):
                self.assertNotIn(secret,json.dumps(data))
        self.assertEqual(self.notifications.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN),before)

    async def test_db_or_graph_configuration_errors_are_not_empty_report_data(self):
        from app.errors import AccessError
        await self.login("admin")
        with patch("app.notification_routes.graph_config",side_effect=AccessError(503,"Nicht verfügbar.")):
            response=await self.client.get("/api/admin/reports")
        self.assertEqual(response.status_code,503)
        self.assertNotIn("counts",response.json())


class ReportRangeTests(unittest.TestCase):
    def test_berlin_days_dst_week_and_inclusive_custom_end(self):
        now=int(datetime(2026,12,1,tzinfo=timezone.utc).timestamp())
        self.assertEqual(report_range("daily","2026-03-29",now=now).end-report_range("daily","2026-03-29",now=now).start,23*3600)
        self.assertEqual(report_range("daily","2026-10-25",now=now).end-report_range("daily","2026-10-25",now=now).start,25*3600)
        selected=report_range("range",from_date="2026-03-28",to_date="2026-03-29",now=now)
        self.assertEqual(selected.end-selected.start,47*3600)
        weekly=report_range("weekly","2026-12-02",now=now)
        self.assertEqual(weekly.end-weekly.start,7*86400)


class NotificationActionTests(NotificationWebFixture,unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await NotificationWebFixture.asyncSetUp(self)
        self.notification_cipher=Fernet(Fernet.generate_key())
        self.notifications=NotificationStore(self.engine,self.notification_cipher,self.notifications.instance,clock=lambda:self.now[0])
        self.saved=dict(DEFAULTS,recipients=["first@example.invalid","second@example.invalid"])
        self.notifications.save_settings(0,self.saved,SCOPE,"operator")
        self.key_patch=patch("app.notification_routes.load_notification_cipher",return_value=self.notification_cipher)
        self.key_patch.start();self.addCleanup(self.key_patch.stop)
        self.sent=[];self.deadlines=[]
        async def execute(job,*,budget):
            self.assertEqual(set(job),{"command","slot_key"})
            self.assertEqual(job["command"],"send")
            self.deadlines.append(budget.deadline)
            ticket=self.notifications.claim(job["slot_key"],SCOPE)
            if ticket and self.notifications.reserve(ticket,budget=budget):
                payload=self.notifications.begin_post(ticket,budget=budget)
                if payload:
                    self.sent.append(payload)
                    self.notifications.finish(ticket,"accepted",http_status=202)
            return dict(ok=True,persisted=True,receipts=[self.notifications.read(job["slot_key"])])
        self.execute=patch("app.notification_routes.execute_notification",side_effect=execute)
        self.worker=self.execute.start();self.addCleanup(self.execute.stop)
        self.body=dict(request_id=str(uuid4()),expected_version=1)

    async def post(self,path="/api/notifications/test",body=None,headers=None):
        return await self.client.post(path,json=body or self.body,headers=self.headers() if headers is None else headers)

    async def test_preview_has_fixed_payload_and_parallel_replay_sends_one_named_test(self):
        await self.login("admin")
        preview=await self.post("/api/notifications/test/preview")
        self.assertEqual(preview.status_code,200,preview.text)
        data=preview.json()
        self.assertEqual(data["receipt"]["actor"],"ad:"+"1"*32)
        self.assertEqual(data["receipt"]["state"],"prepared")
        self.assertEqual(len(data["payload"]["message"]["toRecipients"]),2)
        self.assertEqual(self.sent,[])
        first,second=await asyncio.gather(self.post(),self.post())
        for response in (first,second):
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["receipt"]["state"],"accepted")
            self.assertEqual(response.json()["receipt"]["slot_key"],data["receipt"]["slot_key"])
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.notifications.history(SCOPE)["total"],1)

    async def test_original_request_survives_new_session_and_settings_version(self):
        await self.login("admin")
        first=(await self.post()).json()["receipt"]
        self.notifications.save_settings(1,dict(self.saved,recipients=["changed@example.invalid"]),SCOPE,"operator")
        await self.login("admin")
        replay=await self.post()
        self.assertEqual(replay.status_code,200,replay.text)
        self.assertEqual(replay.json()["receipt"],first)
        self.assertEqual(len(self.sent),1)
        conflict=await self.post(body=dict(self.body,expected_version=2))
        self.assertEqual(conflict.status_code,409)
        status=await self.client.get("/api/notifications/test/status",params=self.body)
        self.assertEqual(status.json()["receipt"],first)

    async def test_current_ad_csrf_origin_role_and_allowlisted_body_before_lookup(self):
        self.assertEqual((await self.post()).status_code,401)
        await self.login("reader")
        self.assertEqual((await self.post()).status_code,403)
        self.assertEqual((await self.client.get("/api/notifications/config")).status_code,200)
        self.assertEqual((await self.client.get("/api/notifications/history")).status_code,200)
        await self.login("admin")
        for headers in ({},{"Origin":"https://other.invalid","X-CSRF-Token":self.csrf},{"Origin":"https://test.invalid"}):
            self.assertEqual((await self.post(headers=headers)).status_code,403)
        for extra in ({"actor":"operator"},{"scope_key":"b"*64},{"to":["other@example.invalid"]},{"body":"anything"},{"slot_key":"c"*64}):
            self.assertEqual((await self.post(body=dict(self.body,**extra))).status_code,422)
        self.directory.rows["1"*32]["attributes"]["memberOf"]=[]
        self.assertEqual((await self.post()).status_code,401)
        self.assertEqual(self.notifications.history(SCOPE)["total"],0)
        self.worker.assert_not_called()

    async def test_versioned_settings_keep_certificate_mandatory_and_reader_read_only(self):
        await self.login("reader")
        body=dict(expected_version=1,settings=self.saved)
        self.assertEqual((await self.client.put("/api/notifications/config",json=body,headers=self.headers())).status_code,403)
        await self.login("admin")
        self.assertEqual((await self.client.put("/api/notifications/config",json=dict(body,settings=dict(self.saved,certificate_enabled=False)),headers=self.headers())).status_code,422)
        changed=await self.client.put("/api/notifications/config",json=dict(body,settings=dict(self.saved,daily_enabled=False)),headers=self.headers())
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(changed.json()["version"],2)
        self.assertFalse(changed.json()["settings"]["daily_enabled"])
        self.assertEqual((await self.client.put("/api/notifications/config",json=body,headers=self.headers())).status_code,409)

    async def test_budget_is_created_before_ad_and_same_deadline_reaches_child(self):
        await self.login("admin")
        require=self.runtime.require;observed=[]
        def slow(request,*args):
            observed.append(request.state.notification_budget.deadline)
            time.sleep(.04)
            return require(request,*args)
        with patch.object(self.runtime,"require",side_effect=slow):response=await self.post()
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.deadlines,observed)
        self.assertLess(self.deadlines[0]-time.monotonic(),79.98)

    async def test_hard_budget_includes_slow_preflight_and_never_starts_child(self):
        await self.login("admin")
        require=self.runtime.require
        def slow(*args):time.sleep(.2);return require(*args)
        start=time.monotonic()
        with patch("app.notification_web_boundary.OperationBudget",side_effect=lambda **kwargs:OperationBudget(clock=time.monotonic,seconds=.05)),patch.object(self.runtime,"require",side_effect=slow):
            response=await self.post()
        elapsed=time.monotonic()-start
        self.assertEqual(response.status_code,504,response.text)
        self.assertFalse(response.json()["persisted"])
        self.assertLess(elapsed,.18)
        self.worker.assert_not_called()
        await asyncio.sleep(.25)  # Let the read-only AD test double return before cleanup.

    async def test_lost_child_result_keeps_original_status_and_has_no_new_request(self):
        await self.login("admin")
        with patch("app.notification_routes.execute_notification",return_value=dict(ok=False,persisted=False)):
            response=await self.post()
        self.assertFalse(response.json()["persisted"])
        status=(await self.client.get("/api/notifications/test/status",params=self.body)).json()
        self.assertEqual(status["receipt"]["state"],"prepared")
        self.assertEqual(status["receipt"]["request_id"],self.body["request_id"])
        self.assertEqual(self.notifications.history(SCOPE)["total"],1)
