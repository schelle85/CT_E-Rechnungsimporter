"""C2 real ASGI/AD/CSRF/SQLite boundary, without external Graph or spawned children."""
import unittest
from contextlib import contextmanager
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import sqlalchemy as sa
from app.graph import GraphError
from app.graph_access_runtime import api_operation as protected_api_operation
from app.notification_schema007 import outbox,monitor
from app.preview import PreviewManager
from test_notification_web import NotificationWebFixture
from notification_test_support import CONFIG


class ClosedApiTests(NotificationWebFixture,unittest.IsolatedAsyncioTestCase):
    def counts(self):
        with self.engine.connect() as c:
            return tuple(c.execute(sa.select(sa.func.count()).select_from(table)).scalar_one() for table in (outbox,monitor))

    def gate(self):
        return patch("app.graph_access_runtime.api_operation",protected_api_operation)

    async def test_closed_test_send_does_not_prepare_slot_proof_or_start_child(self):
        await self.login("admin")
        before=self.counts()
        with self.gate(),patch("app.graph_access_runtime.GraphConfig.load",return_value=CONFIG),patch(
                "app.graph_access_runtime.protected_bytes",side_effect=GraphError("graph_operator_file_unavailable")),patch(
                "app.notification_routes.prepare_test") as prepare,patch("app.notification_routes.execute_notification") as execute:
            response=await self.client.post("/api/notifications/test",json=dict(request_id=str(uuid4()),expected_version=0),headers=self.headers())
        self.assertEqual(response.status_code,503,response.text)
        prepare.assert_not_called();execute.assert_not_called();self.assertEqual(self.counts(),before)

    async def test_ad_and_csrf_still_precede_graph_admission(self):
        body=dict(request_id=str(uuid4()),expected_version=0)
        with patch("app.graph_access_runtime.api_operation") as admission:
            self.assertEqual((await self.client.post("/api/notifications/test",json=body)).status_code,401)
            await self.login("reader")
            self.assertEqual((await self.client.post("/api/notifications/test",json=body,headers=self.headers())).status_code,403)
            await self.login("admin")
            self.assertEqual((await self.client.post("/api/notifications/test",json=body,headers={})).status_code,403)
        admission.assert_not_called()

    async def test_closed_original_returns_503_without_process_or_tempfile_and_releases_slots(self):
        await self.login("reader")
        manager=PreviewManager(self.engine,root=self.temp.name)
        self.app.state.preview=manager
        with self.gate(),patch("app.graph_access_runtime.GraphConfig.load",return_value=CONFIG),patch(
                "app.graph_access_runtime.protected_bytes",side_effect=GraphError("graph_operator_file_unavailable")),patch(
                "app.preview.multiprocessing.get_context") as spawn,patch.object(manager,"directory") as directory:
            response=await self.client.get("/api/attachments/"+"a"*64+"/original")
        self.assertEqual(response.status_code,503,response.text)
        spawn.assert_not_called();directory.assert_not_called()
        self.assertTrue(manager.slots.acquire(blocking=False));self.assertTrue(manager.slots.acquire(blocking=False))
        manager.slots.release();manager.slots.release()

    async def test_certificate_status_remains_a_read_without_admission(self):
        await self.login("reader")
        before=self.counts()
        with patch("app.graph_access_runtime.api_operation") as admission:
            response=await self.client.get("/api/notifications/certificate")
        self.assertEqual(response.status_code,200,response.text)
        admission.assert_not_called();self.assertEqual(self.counts(),before)


class PreviewLifetimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_reap_precedes_release_and_local_response_does_not_hold_admission(self):
        events=[];active=[False];data=b"%PDF-synthetic";digest=hashlib.sha256(data).hexdigest()
        @contextmanager
        def admit(_):
            active[0]=True;events.append("admit")
            try:yield
            finally:active[0]=False;events.append("release")
        selected=dict(byte_size=len(data),raw_sha256=digest)
        snapshot=dict(filename="synthetic.pdf",selected=selected,fingerprint="fixed")
        receiver=SimpleNamespace(poll=lambda:True,recv_bytes=lambda _:json.dumps(
            dict(ok=True,size=len(data),sha256=digest,pdf=True)).encode(),close=lambda:None)
        sender=SimpleNamespace(close=lambda:None)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)
            manager=PreviewManager(None)
            def create(**kwargs):
                self.assertTrue(active[0])
                def start():
                    self.assertTrue(active[0]);(path/"original").write_bytes(data)
                return SimpleNamespace(start=start)
            def reap(process):
                if process is not None:
                    self.assertTrue(active[0]);events.append("reap")
            manager.snapshot=lambda *a,**k:snapshot
            manager.directory=lambda:path
            manager.verify=lambda *a:(path/"original").stat()
            manager.reap=reap
            context=SimpleNamespace(Pipe=lambda **_: (receiver,sender),Process=create)
            async def receive():await asyncio.Future()
            async def send(message):
                if message["type"]=="http.response.start":
                    self.assertFalse(active[0]);events.append("response")
            scope=dict(type="http",method="GET",headers=[],extensions={},path="/",http_version="1.1")
            with patch("app.graph_access_runtime.api_operation",side_effect=admit),patch(
                    "app.graph_access_runtime.ChildAccess",return_value=None),patch(
                    "app.preview.multiprocessing.get_context",return_value=context):
                await manager.response("a"*64)(scope,receive,send)
        self.assertEqual(events,["admit","reap","release","response"])
