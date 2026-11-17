"""Real ASGI/AD/session/CSRF and SQL, synthetic directory and protected file boundary only."""
import asyncio
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from app.graph import GraphError
from app.graph_access import AccessBinding
from app.rotation_model import RotationBinding
from app.rotation_schema008 import requests
from app.rotation_state import RotationStore
from app import rotation_status
from app.schema import audit
from app.notification_schema007 import monitor
from app.notification_model import CERTIFICATE_TOKEN,graph_scope,identity,canonical
from notification_test_support import CONFIG,NOW,material
import test_preview as security_fixture


class RotationApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await security_fixture.SecurityTests.asyncSetUp(self)
        self.now=[NOW];self.runtime.store.clock=lambda:self.now[0];self.current=material(days=365)
        with self.engine.connect() as connection:instance=connection.execute(sa.text("SELECT instance_id FROM app_metadata WHERE singleton=1")).scalar_one()
        self.bound=RotationBinding(instance,CONFIG.tenant_id,CONFIG.client_id,"44444444-4444-4444-4444-444444444444",CONFIG.mailbox)
        self.access=AccessBinding("a"*40,str(uuid4()),instance,self.bound.scope)
        self.profile=dict(schema_version=1,**self.access.fields(),application_id=self.bound.application_id)
        self.store=RotationStore(self.engine,self.bound,clock=lambda:self.now[0])
        replacements={"app.rotation_routes.GraphConfig.load":dict(return_value=CONFIG),
            "app.graph_access_runtime.protected_bytes":dict(side_effect=lambda path:json.dumps(self.profile).encode()),
            "app.rotation_routes.protected_bytes":dict(side_effect=lambda path:json.dumps(self.profile).encode()),
            "app.rotation_routes.CertificateMaterial.load":dict(side_effect=lambda path:self.current),
            "app.rotation_status.protected_bytes":dict(side_effect=GraphError("synthetic_no_root_publication")),
            "azure.identity.CertificateCredential":dict(side_effect=AssertionError("API must not create a Graph credential")),
            "app.rotation_worker.execute":dict(side_effect=AssertionError("API must not invoke Root worker"))}
        for target,options in replacements.items():
            patcher=patch(target,**options);patcher.start();self.addCleanup(patcher.stop)

    asyncTearDown=security_fixture.SecurityTests.asyncTearDown
    challenge=security_fixture.SecurityTests.challenge
    headers=security_fixture.SecurityTests.headers
    login=security_fixture.SecurityTests.login

    def payload(self,**changes):
        return dict(dict(operation_id=str(uuid4()),scope_key=self.bound.scope,expected_revision=self.store.status()["revision"],old_fingerprint=self.current.fingerprint),**changes)

    def count(self):
        with self.engine.connect() as connection:return connection.execute(sa.select(sa.func.count()).select_from(requests)).scalar_one()

    async def test_both_roles_read_metadata_history_but_missing_host_proof_is_unconfirmed(self):
        for path in ("/api/rotation/status","/api/rotation/history"):
            self.assertEqual((await self.client.get(path)).status_code,401)
        before=self.store.status()
        for role in ("reader","admin"):
            await self.login(role)
            response=await self.client.get("/api/rotation/status");self.assertEqual(response.status_code,200,response.text)
            value=response.json();self.assertEqual(value["can_edit"],role=="admin");self.assertEqual(value["local"]["fingerprint"],self.current.fingerprint)
            self.assertFalse(value["host"]["available"]);self.assertIsNone(value["last_successful_check_at"])
            self.assertEqual(response.headers["cache-control"],"no-store")
            self.assertEqual((await self.client.get("/api/rotation/history")).json()["items"],[])
            for secret in ("PRIVATE KEY","pem_hash","/run/","keyCredentials","bind_cipher"):self.assertNotIn(secret,response.text)
        self.assertEqual(self.store.status(),before);self.assertEqual(self.count(),0)

    async def test_reader_and_removed_ad_membership_cannot_write_or_bypass_current_check(self):
        await self.login("reader")
        self.assertEqual((await self.client.post("/api/rotation/request",json=self.payload(),headers=self.headers())).status_code,403)
        config=dict(scope_key=self.bound.scope,expected_revision=0,enabled=True)
        self.assertEqual((await self.client.put("/api/rotation/config",json=config,headers=self.headers())).status_code,403)
        await self.login("admin");self.directory.rows["1"*32]["attributes"]["memberOf"]=[]
        self.assertEqual((await self.client.get("/api/rotation/status")).status_code,401)
        self.assertEqual((await self.client.post("/api/rotation/request",json=self.payload(),headers=self.headers())).status_code,401)
        self.assertEqual(self.count(),0);self.assertFalse(self.store.status()["enabled"])

    async def test_replay_after_new_certificate_head_revision_and_session_keeps_original_request(self):
        await self.login();payload=self.payload()
        first=await self.client.post("/api/rotation/request",json=payload,headers=self.headers());self.assertEqual(first.status_code,200,first.text)
        original=first.json()["receipt"];self.current=material(days=366)
        self.store.configure(self.store.status()["revision"],True,"operator")
        await self.login()
        repeated=await self.client.post("/api/rotation/request",json=payload,headers=self.headers())
        self.assertEqual(repeated.status_code,200,repeated.text);self.assertEqual(repeated.json()["receipt"],original)
        status=await self.client.get("/api/rotation/request",params=payload)
        self.assertEqual(status.status_code,200,status.text);self.assertEqual(status.json()["receipt"],original)
        self.assertEqual(self.count(),1)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(sa.select(sa.func.count()).select_from(audit).where(audit.c.action=="graph_rotation_requested")).scalar_one(),1)

    async def test_receipt_binding_and_csrf_origin_apply_before_any_replay(self):
        await self.login();payload=self.payload()
        self.assertEqual((await self.client.post("/api/rotation/request",json=payload,headers=self.headers())).status_code,200)
        for headers in ({},{"Origin":"https://test.invalid"},{"Origin":"https://foreign.invalid","X-CSRF-Token":self.csrf}):
            self.assertEqual((await self.client.post("/api/rotation/request",json=payload,headers=headers)).status_code,403)
        changed=dict(payload,expected_revision=payload["expected_revision"]+1)
        self.assertEqual((await self.client.get("/api/rotation/request",params=changed)).status_code,409)
        self.assertEqual((await self.client.post("/api/rotation/request",json=changed,headers=self.headers())).status_code,409)
        await self.login("reader")
        self.assertEqual((await self.client.get("/api/rotation/request",params=payload)).status_code,409)
        self.assertEqual(self.count(),1)

    async def test_missing_original_receipt_is_not_persisted_and_later_same_post_is_confirmed_once(self):
        await self.login();payload=self.payload();before=self.store.status()
        def audited():
            with self.engine.connect() as connection:
                return connection.execute(sa.select(sa.func.count()).select_from(audit).where(audit.c.action=="graph_rotation_requested")).scalar_one()
        before_audit=audited()
        absent=await self.client.get("/api/rotation/request",params=payload)
        self.assertEqual(absent.status_code,200,absent.text)
        self.assertEqual(absent.json(),dict(ok=True,persisted=False,receipt=None))
        self.assertEqual(self.count(),0);self.assertEqual(audited(),before_audit);self.assertEqual(self.store.status(),before)
        accepted=await self.client.post("/api/rotation/request",json=payload,headers=self.headers())
        self.assertEqual(accepted.status_code,200,accepted.text);self.assertTrue(accepted.json()["persisted"])
        confirmed=await self.client.get("/api/rotation/request",params=payload)
        self.assertEqual(confirmed.status_code,200,confirmed.text);self.assertEqual(confirmed.json(),accepted.json())
        self.assertEqual(confirmed.json()["receipt"]["operation_id"],payload["operation_id"])
        self.assertEqual(self.count(),1);self.assertEqual(audited(),before_audit+1)

    async def test_concurrent_different_requests_only_create_one_persistent_operation(self):
        await self.login();payload=self.payload();other=dict(payload,operation_id=str(uuid4()))
        responses=await asyncio.gather(*(self.client.post("/api/rotation/request",json=value,headers=self.headers()) for value in (payload,other)))
        self.assertEqual(sorted(value.status_code for value in responses),[200,409]);self.assertEqual(self.count(),1)

    async def test_new_request_checks_actual_current_material_scope_and_validity(self):
        await self.login()
        for change in (dict(old_fingerprint="f"*64),dict(scope_key="f"*64)):
            response=await self.client.post("/api/rotation/request",json=self.payload(**change),headers=self.headers())
            self.assertEqual(response.status_code,409,response.text)
        self.now[0]=self.current.expires_at;await self.login()
        self.assertEqual((await self.client.post("/api/rotation/request",json=self.payload(),headers=self.headers())).status_code,409)
        self.assertEqual(self.count(),0)

    async def test_fixed_settings_strict_body_and_revision_never_accept_paths_or_timers(self):
        await self.login();config=dict(scope_key=self.bound.scope,expected_revision=0,enabled=True)
        for change in (dict(enabled="true"),dict(expected_revision=True),dict(path="/other"),dict(daily_time="04:00")):
            self.assertEqual((await self.client.put("/api/rotation/config",json=dict(config,**change),headers=self.headers())).status_code,422)
        self.assertEqual((await self.client.post("/api/rotation/request",json=dict(self.payload(),command="run"),headers=self.headers())).status_code,422)
        saved=await self.client.put("/api/rotation/config",json=config,headers=self.headers());self.assertEqual(saved.status_code,200,saved.text)
        self.assertTrue(saved.json()["enabled"]);self.assertEqual((await self.client.put("/api/rotation/config",json=config,headers=self.headers())).status_code,409)
        self.assertEqual((await self.client.get("/api/rotation/history",params=dict(page=0))).status_code,422)

    async def test_profile_app_or_instance_change_cannot_rebind_existing_requests(self):
        await self.login();payload=self.payload()
        for field in ("instance_id","application_id"):
            original=self.profile[field];self.profile[field]=str(uuid4())
            self.assertEqual((await self.client.post("/api/rotation/request",json=payload,headers=self.headers())).status_code,503)
            self.profile[field]=original
        self.assertEqual(self.count(),0)

    async def test_last_successful_check_requires_current_fingerprint_scope_and_real_past_time(self):
        await self.login();scope=graph_scope(CONFIG.tenant_id,CONFIG.client_id,CONFIG.mailbox)
        key=identity([scope,"certificate",CERTIFICATE_TOKEN])
        for changes,expected in (({},NOW),(dict(fingerprint="f"*64),None),(dict(scope_key="f"*64),None),(dict(at=NOW+1),None)):
            proof=dict(dict(fingerprint=self.current.fingerprint,scope_key=scope,at=NOW),**changes)
            with self.engine.begin() as connection:
                connection.execute(monitor.delete())
                connection.execute(monitor.insert().values(monitor_key=key,scope_key=scope,kind="certificate",revision=1,
                    payload=canonical(dict(proof=proof)),updated_at=NOW))
            response=await self.client.get("/api/rotation/status");self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["last_successful_check_at"],expected);self.assertFalse(response.json()["host"]["available"])
        self.assertEqual(self.count(),0)


class PublicStatusTests(unittest.TestCase):
    def test_only_fresh_complete_bound_public_projection_is_accepted(self):
        access=AccessBinding("a"*40,str(uuid4()),str(uuid4()),"b"*64);boot=str(uuid4())
        value=dict(schema_version=1,**access.fields(),boot_id=boot,observed_at=NOW,last_check=dict(at=NOW,ok=True,code=None),
            last_attempt=None,last_renewal=None,operation=None,timers=dict(daily=True,opportunity=True,next_check_at=NOW+3600))
        with patch.object(rotation_status,"boot_id",return_value=boot),patch.object(rotation_status,"protected_bytes",return_value=json.dumps(value).encode()):
            self.assertTrue(rotation_status.read(access,NOW)["available"])
            self.assertFalse(rotation_status.read(access,NOW+181)["available"])
        for changes in (dict(source_commit="f"*40),dict(instance_id=str(uuid4())),dict(boot_id=str(uuid4())),
                dict(observed_at=NOW+1),dict(schema_version=True),dict(pem="forbidden"),dict(timers=dict(value["timers"],next_check_at=NOW-1))):
            with self.subTest(changes=changes),patch.object(rotation_status,"boot_id",return_value=boot),patch.object(rotation_status,"protected_bytes",return_value=json.dumps(dict(value,**changes)).encode()):
                self.assertFalse(rotation_status.read(access,NOW)["available"])
