"""Selected unchanged API/Notification/Processing/Preview readers on additive 008."""
import time
import unittest
import sqlalchemy as sa
from app.notification_certificate import CERTIFICATE_TOKEN
from app.notification_runtime import run_job
from app.preview import PreviewManager
from app.process_queries import ProcessQueries
from app.rotation_schema008 import requests
from test_notification_web import NotificationWebFixture
from test_rotation_state import upgrade
from unittest.mock import patch
from notification_test_support import Fixture, CONFIG, SCOPE
from uuid import uuid4


class RotationCompatibilityTests(NotificationWebFixture,unittest.IsolatedAsyncioTestCase):
    async def test_existing_consumers_keep_actual_rows_and_empty_rotation_on008(self):
        key=self.mail()
        before=self.store.get_message(key)
        with self.engine.connect() as c:
            counts={table:c.execute(sa.text("SELECT COUNT(*) FROM "+table)).scalar_one()
                for table in ("processing_messages","processing_attachments","notification_outbox","notification_monitor")}
        upgrade(self.engine)
        self.assertEqual(self.store.get_message(key),before)
        await self.login("reader")
        for route in ("/api/processes","/api/notifications/history","/api/notifications/certificate","/api/admin/reports"):
            response=await self.client.get(route)
            self.assertEqual(response.status_code,200,(route,response.text))
        with self.engine.connect() as c:
            attachment=c.execute(sa.text("SELECT attachment_key FROM processing_attachments WHERE message_key=:key"),dict(key=key)).scalar_one()
            c.execute(sa.text("UPDATE processing_attachments SET raw_sha256=:hash, byte_size=1 WHERE attachment_key=:key"),dict(hash="a"*64,key=attachment));c.commit()
        snapshot=PreviewManager(self.engine).snapshot(attachment)
        self.assertEqual(snapshot["message"]["message_key"],key)
        self.assertEqual(self.store.get_message(key),before)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(requests)).scalar_one(),0)
            for table,count in counts.items():self.assertEqual(c.execute(sa.text("SELECT COUNT(*) FROM "+table)).scalar_one(),count)


class RotationLegacyMigrationTests(Fixture,unittest.TestCase):
    def test007_settings_outbox_monitor_and_minimal_notification_runtime_survive008(self):
        self.configure()
        row=self.store.request_test(str(uuid4()),1,SCOPE,"operator")
        tables=sa.inspect(self.engine).get_table_names()
        def snapshot():
            with self.engine.connect() as c:
                return {name:[dict(item) for item in c.execute(sa.text('SELECT * FROM "'+name+'"')).mappings()]
                    for name in tables}
        before=snapshot()
        self.assertNotIn("graph_rotation_head",tables)
        upgrade(self.engine)
        self.assertEqual(snapshot(),before)
        with patch("app.notification_runtime.make_engine",return_value=self.engine),\
                patch("app.notification_runtime.GraphConfig.load",return_value=CONFIG),\
                patch("app.notification_runtime.load_notification_cipher",return_value=self.cipher):
            result=run_job(dict(command="configuration",deadline=time.monotonic()+70))
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"],1)
        self.assertEqual(self.store.read(row["slot_key"])["state"],"prepared")
