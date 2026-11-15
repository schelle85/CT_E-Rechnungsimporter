"""Actual AD/session boundary with synthetic directory and real journal rows."""
from datetime import datetime,timezone
import json
import unittest
from unittest.mock import patch
import sqlalchemy as sa
from app.notification_certificate import record_certificate
from app.notification_model import CERTIFICATE_TOKEN
from app.notification_schema007 import metadata,outbox,settings
from app.notification_state import NotificationStore
from app.notification_queries import report_range
import test_process_api as process_fixture
from notification_test_support import CONFIG,SCOPE,material


class NotificationReadTests(unittest.IsolatedAsyncioTestCase):
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
