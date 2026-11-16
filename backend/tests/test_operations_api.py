"""C actual AD/session routing and read-only projections on synthetic SQLite."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from app import operations_status as model
from app.notification_model import DEFAULTS
from app.notification_state import NotificationStore
from app.notification_schema007 import metadata as notification_metadata
from app.processing_state import metadata as processing_metadata
from app.storage_state import metadata as storage_metadata
import test_notification_web as fixture
from notification_test_support import SCOPE
from operations_test_support import SOURCE,DEPLOYMENT,BOOT,raw


class OperationsApiTests(fixture.NotificationWebFixture,unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixture.NotificationWebFixture.asyncSetUp(self)
        cipher=Fernet(Fernet.generate_key())
        self.notifications=NotificationStore(self.engine,cipher,self.notifications.instance,clock=lambda:self.now[0])
        self.settings=dict(DEFAULTS,recipients=["synthetic@example.invalid"])
        self.notifications.save_settings(0,self.settings,SCOPE,"operator")
        key=patch("app.notification_routes.load_notification_cipher",return_value=cipher);key.start();self.addCleanup(key.stop)
        self.current=raw(self.now[0],self.notifications.instance);self.reads=[]
        def read(instance,*,now):
            self.reads.append((instance,now))
            return model.project(deepcopy(self.current),now=now,source_commit=SOURCE,deployment_id=DEPLOYMENT,instance_id=instance,current_boot=BOOT)
        for target in ("app.main.read_status","app.notification_routes.read_status"):
            item=patch(target,side_effect=read);item.start();self.addCleanup(item.stop)
        forbidden=patch("app.notification_routes.execute_notification",side_effect=AssertionError("read must never launch a job"));self.execute=forbidden.start();self.addCleanup(forbidden.stop)

    def snapshot(self):
        with self.engine.connect() as connection:
            return {table.name:[tuple(row) for row in connection.execute(table.select())] for metadata in (processing_metadata,storage_metadata,notification_metadata) for table in metadata.sorted_tables}

    async def test_both_roles_get_actual_bound_status_without_business_writes(self):
        self.mail();before=self.snapshot()
        for role in ("reader","admin"):
            await self.login(role)
            response=await self.client.get("/api/operations/status")
            self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.headers["cache-control"],"no-store")
            self.assertEqual(response.json()["state"],"active");self.assertEqual(response.json()["instance_id"],self.notifications.instance)
            config=await self.client.get("/api/notifications/config")
            self.assertEqual(config.status_code,200,config.text);self.assertIs(config.json()["automatic_schedule_active"],True)
            self.assertEqual(config.json()["automatic_schedule_state"],"active")
            self.assertEqual(config.json()["can_edit"],role=="admin")
        self.assertEqual(self.snapshot(),before);self.execute.assert_not_called()
        self.assertTrue(all(instance==self.notifications.instance and now==self.now[0] for instance,now in self.reads))

    async def test_auth_role_revocation_and_no_control_route(self):
        path="/api/operations/status"
        self.assertEqual((await self.client.get(path)).status_code,401)
        await self.login("reader")
        self.assertEqual((await self.client.post(path,json={},headers=self.headers())).status_code,403)
        self.directory.rows["2"*32]["attributes"]["memberOf"]=[]
        self.assertEqual((await self.client.get(path)).status_code,401)
        await self.login("admin")
        self.assertEqual((await self.client.post(path,json={},headers=self.headers())).status_code,405)
        self.assertEqual((await self.client.post("/api/operations/start",json={},headers=self.headers())).status_code,404)
        self.execute.assert_not_called()

    async def test_stale_paused_and_degraded_config_get_and_put_preserve_nullable_flag(self):
        await self.login("admin")
        for active,state in ((False,"paused"),(None,"unknown"),(True,"degraded")):
            self.current=raw(self.now[0],self.notifications.instance)
            self.current["jobs"]["notifications"].update(configured=active,active=active)
            if active is True:self.current["startup"]["database_ready"]=False
            response=await self.client.get("/api/notifications/config")
            self.assertEqual(response.status_code,200,response.text)
            self.assertIs(response.json()["automatic_schedule_active"],active);self.assertEqual(response.json()["automatic_schedule_state"],state)
        self.current=raw(self.now[0]-181,self.notifications.instance)
        status=await self.client.get("/api/operations/status")
        self.assertEqual(status.json()["reason"],"stale");self.assertIsNone(status.json()["automatic_schedule_active"])
        response=await self.client.put("/api/notifications/config",json=dict(expected_version=1,settings=self.settings),headers=self.headers())
        self.assertEqual(response.status_code,200,response.text);self.assertIsNone(response.json()["automatic_schedule_active"])
        self.assertEqual(response.json()["automatic_schedule_state"],"unknown");self.execute.assert_not_called()
