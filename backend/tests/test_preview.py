"""Security boundaries; directory transport doubles exist only in this test module."""
import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import create_engine

from app.main import create_app
from app.security import Runtime, COOKIE
from app.settings import LdapSettings, read_secret
from app.directory import LdapDirectory
from app.errors import DirectoryDenied, DirectoryUnavailable
from app.schema import metadata, versions, head, sessions, attempts, audit
from app.database import make_engine

CFG=dict(servers=["dc1.example.invalid","dc2.example.invalid"],port=636,
    search_base="DC=example,DC=invalid",bind_user="ldap@example.invalid",
    admin_group="CN=Admins,DC=example,DC=invalid",reader_group="CN=Readers,DC=example,DC=invalid",
    connect_timeout=2,receive_timeout=3)

def entry(guid,name,groups,uac=512,computed=0,expires=0):
    return {"type":"searchResEntry","dn":"CN="+name+",DC=example,DC=invalid",
        "attributes":{"sAMAccountName":name,"memberOf":groups},
        "raw_attributes":{"objectGUID":[bytes.fromhex(guid)],
            "userAccountControl":[str(uac).encode()],
            "msDS-User-Account-Control-Computed":[str(computed).encode()],
            "accountExpires":[str(expires).encode()]}}

class DirectoryDouble:
    def __init__(self):
        self.rows={
            "1"*32:entry("1"*32,"admin",[CFG["admin_group"],CFG["reader_group"]]),
            "2"*32:entry("2"*32,"reader",[CFG["reader_group"]]),
            "3"*32:entry("3"*32,"outside",["CN=NestedParent,DC=example,DC=invalid"]),
            "4"*32:entry("4"*32,"disabled",[CFG["admin_group"]],uac=514),
            "5"*32:entry("5"*32,"locked",[CFG["admin_group"]],computed=16),
            "6"*32:entry("6"*32,"expired",[CFG["admin_group"]],expires=1)}
        self.available=True
        self.validations=0
        self.revalidations=0

    def check(self,cfg,password):
        if not self.available or cfg.servers[0].startswith("bad") or password not in ("bootstrap bind pass ","replacement bind pass "):
            raise DirectoryUnavailable()

    def authenticate(self,cfg,bind_password,username,password):
        self.check(cfg,bind_password)
        if password!="synthetic-user-password":
            raise DirectoryDenied()
        for row in self.rows.values():
            if username.casefold()==row["attributes"]["sAMAccountName"].casefold():
                return LdapDirectory._principal(row,cfg)
        raise DirectoryDenied()

    def revalidate(self,cfg,password,guid):
        self.check(cfg,password)
        self.revalidations+=1
        if guid not in self.rows:
            raise DirectoryDenied()
        return LdapDirectory._principal(self.rows[guid],cfg)

    def validate(self,cfg,password):
        self.check(cfg,password)
        self.validations+=1

class SecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.bind_file=Path(self.temp.name)/"bind"
        self.bind_file.write_text("bootstrap bind pass \n")
        self.engine=make_engine() if os.environ.get("INTEGRATION_DB")=="1" else create_engine(
            "sqlite:///"+str(Path(self.temp.name)/"test.sqlite"),connect_args={"check_same_thread":False})
        with patch("app.database.make_engine",return_value=self.engine):
            command.upgrade(Config("alembic.ini"),"head")
        with self.engine.begin() as c:
            for table in reversed(metadata.sorted_tables):
                c.execute(table.delete())
        self.key=Fernet.generate_key()
        self.directory=DirectoryDouble()
        self.runtime=Runtime(self.engine,Fernet(self.key),self.directory,"https://test.invalid",str(self.bind_file))
        self.original=self.runtime.store.activate(LdapSettings(**CFG),None,"test-bootstrap",None)
        self.app=create_app(lambda:self.runtime)
        self.lifespan=self.app.router.lifespan_context(self.app)
        await self.lifespan.__aenter__()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url="https://test.invalid")
        self.csrf=""

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.lifespan.__aexit__(None,None,None)
        self.temp.cleanup()

    async def challenge(self):
        response=await self.client.get("/api/auth/session")
        self.assertEqual(response.status_code,200,response.text)
        self.csrf=response.json()["csrf_token"]
        return response

    def headers(self):
        return {"Origin":"https://test.invalid","X-CSRF-Token":self.csrf}

    async def login(self,username="admin",password="synthetic-user-password"):
        await self.challenge()
        response=await self.client.post("/api/auth/login",json={"username":username,"password":password},headers=self.headers())
        if response.status_code==200:
            self.csrf=response.json()["csrf_token"]
        return response

    def candidate(self,**changes):
        cfg=dict(CFG);cfg.update(changes)
        return {"expected_version":self.runtime.store.active()["id"],"settings":cfg}

    async def test_anonymous_and_forged_session_cannot_reach_any_protected_path(self):
        for path in ("/api/processes","/api/admin/config","/api/admin/audit","/api/unknown"):
            self.assertEqual((await self.client.get(path)).status_code,401)
        self.client.cookies.set(COOKIE,"forged-role-admin",domain="test.invalid",path="/")
        self.assertEqual((await self.client.get("/api/processes",headers={"Authorization":"Bearer admin","X-Role":"admin"})).status_code,401)
        self.assertEqual((await self.client.get("/api/health/live")).status_code,200)

    async def test_allowed_roles_cookie_rotation_and_reader_write_denied_with_valid_csrf(self):
        challenge=await self.challenge()
        old=self.client.cookies.get(COOKIE)
        response=await self.login("reader")
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["user"]["role"],"reader")
        self.assertNotEqual(old,self.client.cookies.get(COOKIE))
        cookie=response.headers["set-cookie"].lower()
        for flag in ("secure","httponly","samesite=strict","path=/"):
            self.assertIn(flag,cookie)
        self.assertNotIn("domain=",cookie)
        self.assertEqual((await self.client.get("/api/processes")).status_code,200)
        for method,path in (("PUT","/api/admin/config"),("POST","/api/import"),("DELETE","/api/admin/config")):
            response=await self.client.request(method,path,headers=self.headers(),json=self.candidate())
            self.assertEqual(response.status_code,403,response.text)
        config_response=await self.client.get("/api/admin/config")
        self.assertEqual(config_response.status_code,200)
        self.assertFalse(config_response.json()["can_edit"])
        self.assertNotIn("bind_password",config_response.text)
        self.assertNotIn("bind_cipher",config_response.text)
        self.assertNotIn("bootstrap bind pass",config_response.text)
        audit_response=await self.client.get("/api/admin/audit")
        self.assertEqual(audit_response.status_code,200)
        self.assertNotIn("bootstrap bind pass",audit_response.text)

    async def test_bad_password_outside_direct_groups_disabled_locked_expired_denied(self):
        for name,password in (("admin","wrong"),("outside","synthetic-user-password"),("disabled","synthetic-user-password"),("locked","synthetic-user-password"),("expired","synthetic-user-password")):
            response=await self.login(name,password)
            self.assertEqual(response.status_code,401,(name,response.text))

    async def test_login_csrf_and_origin_required_and_validation_never_echoes_secret(self):
        await self.challenge()
        payload={"username":"admin","password":"sensitive-not-echoed"}
        for headers in ({},{"Origin":"https://other.invalid","X-CSRF-Token":self.csrf},{"Origin":"https://test.invalid","X-CSRF-Token":"forged"}):
            self.assertEqual((await self.client.post("/api/auth/login",json=payload,headers=headers)).status_code,403)
        payload["extra"]="forbidden"
        response=await self.client.post("/api/auth/login",json=payload,headers=self.headers())
        self.assertEqual(response.status_code,422)
        self.assertNotIn("sensitive",response.text)

    async def test_logout_csrf_revokes_server_session_even_when_directory_unavailable(self):
        self.assertEqual((await self.login()).status_code,200)
        old=self.client.cookies.get(COOKIE)
        self.assertEqual((await self.client.post("/api/auth/logout")).status_code,403)
        self.directory.available=False
        self.assertEqual((await self.client.get("/api/processes")).status_code,503)
        count=self.directory.revalidations
        self.assertEqual((await self.client.post("/api/auth/logout",headers=self.headers())).status_code,200)
        self.assertEqual(count,self.directory.revalidations)
        self.directory.available=True
        response=await self.client.get("/api/processes",headers={"Cookie":COOKIE+"="+old})
        self.assertEqual(response.status_code,401)

    async def test_group_downgrade_removal_and_account_disable_revalidated(self):
        await self.login()
        self.directory.rows["1"*32]["attributes"]["memberOf"]=[CFG["reader_group"]]
        response=await self.client.get("/api/auth/session")
        self.assertEqual(response.json()["user"]["role"],"reader")
        self.assertEqual((await self.client.put("/api/admin/config",json=self.candidate(),headers=self.headers())).status_code,403)
        self.directory.rows["1"*32]["attributes"]["memberOf"]=[]
        self.assertEqual((await self.client.get("/api/processes")).status_code,401)
        self.directory.rows["1"*32]["attributes"]["memberOf"]=[CFG["admin_group"]]
        await self.login()
        self.directory.rows["1"*32]["raw_attributes"]["userAccountControl"]=[b"514"]
        self.assertEqual((await self.client.get("/api/processes")).status_code,401)

    async def test_concurrent_logout_during_directory_check_cannot_authorize_request(self):
        await self.login()
        token=self.client.cookies.get(COOKIE)
        original=self.directory.revalidate
        def revoke_during_lookup(*args):
            principal=original(*args)
            self.runtime.store.revoke(token)
            return principal
        with patch.object(self.directory,"revalidate",side_effect=revoke_during_lookup):
            self.assertEqual((await self.client.get("/api/processes")).status_code,401)

    async def test_cross_site_challenge_nonascii_csrf_and_session_reload(self):
        self.assertEqual((await self.client.get("/api/auth/session",headers={"Sec-Fetch-Site":"cross-site"})).status_code,403)
        await self.login()
        token=self.client.cookies.get(COOKIE)
        csrf=self.csrf
        self.runtime=Runtime(self.engine,Fernet(self.key),self.directory,"https://test.invalid",str(self.bind_file))
        self.app.state.runtime=self.runtime
        response=await self.client.get("/api/auth/session")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["csrf_token"],csrf)
        self.assertEqual(response.json()["user"]["role"],"admin")
        self.assertEqual(self.client.cookies.get(COOKIE),token)
        response=await self.client.post("/api/auth/logout",headers=[(b"Origin",b"https://test.invalid"),(b"X-CSRF-Token",b"\xff")])
        self.assertEqual(response.status_code,403)

    async def test_bad_password_retry_keeps_preauth_challenge_usable(self):
        await self.challenge()
        token=self.client.cookies.get(COOKIE)
        headers=self.headers()
        bad=await self.client.post("/api/auth/login",json={"username":"admin","password":"wrong"},headers=headers)
        self.assertEqual(bad.status_code,401)
        self.assertEqual(self.client.cookies.get(COOKIE),token)
        good=await self.client.post("/api/auth/login",json={"username":"admin","password":"synthetic-user-password"},headers=headers)
        self.assertEqual(good.status_code,200,good.text)
        self.assertNotEqual(self.client.cookies.get(COOKIE),token)

    async def test_operator_session_revocation_does_not_require_directory(self):
        await self.login()
        before=self.runtime.store.active()["id"]
        self.directory.available=False
        from app import bootstrap
        with patch("app.bootstrap.build_runtime",return_value=self.runtime),patch("sys.argv",["bootstrap","revoke-sessions"]),contextlib.redirect_stdout(io.StringIO()):
            bootstrap.main()
        self.assertEqual(self.runtime.store.active()["id"],before)
        self.assertEqual((await self.client.get("/api/processes")).status_code,401)

    async def test_expired_or_deleted_preauth_requires_fresh_challenge_without_bind(self):
        for cause in ("expired","configuration-deleted"):
            with self.subTest(cause=cause):
                self.runtime.store.clock=time.time
                await self.challenge()
                old_csrf=self.csrf
                if cause=="expired":
                    now=int(time.time())
                    self.runtime.store.clock=lambda:now+601
                else:
                    current=self.runtime.store.active()
                    self.runtime.store.activate(LdapSettings(**CFG),current["bind_cipher"],"test-config-switch",current["id"])
                with patch.object(self.directory,"authenticate",wraps=self.directory.authenticate) as authenticate:
                    response=await self.client.post("/api/auth/login",json={"username":"admin","password":"synthetic-user-password"},headers=self.headers())
                    self.assertEqual(response.status_code,403)
                    authenticate.assert_not_called()
                    await self.challenge()
                    self.assertNotEqual(self.csrf,old_csrf)
                    response=await self.client.post("/api/auth/login",json={"username":"admin","password":"synthetic-user-password"},headers=self.headers())
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(authenticate.call_count,1)
                self.runtime.store.clock=time.time
                await self.client.post("/api/auth/logout",headers={"Origin":"https://test.invalid","X-CSRF-Token":response.json()["csrf_token"]})

    async def test_idle_and_absolute_expiry(self):
        await self.login()
        now=int(time.time())
        self.runtime.store.clock=lambda:now+1801
        self.assertEqual((await self.client.get("/api/processes")).status_code,401)
        self.runtime.store.clock=time.time
        await self.login()
        for step in range(1,17):
            self.runtime.store.clock=lambda step=step:now+step*1700
            self.assertEqual((await self.client.get("/api/processes")).status_code,200)
        self.runtime.store.clock=lambda:now+28801
        self.assertEqual((await self.client.get("/api/processes")).status_code,401)

    async def test_persistent_login_rate_limit(self):
        for attempt in range(5):
            self.assertEqual((await self.login("admin","wrong")).status_code,401)
        # New Runtime/Store represents a process restart, same DB.
        self.runtime=Runtime(self.engine,Fernet(self.key),self.directory,"https://test.invalid",str(self.bind_file))
        self.app.state.runtime=self.runtime
        self.assertEqual((await self.login("admin","wrong")).status_code,429)

    async def test_bad_config_and_self_lockout_preserve_active_version_and_session(self):
        await self.login()
        before=self.runtime.store.active()["id"]
        response=await self.client.put("/api/admin/config",json=self.candidate(servers=["bad.example.invalid"]),headers=self.headers())
        self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.runtime.store.active()["id"],before)
        response=await self.client.put("/api/admin/config",json=self.candidate(admin_group="CN=Other,DC=example,DC=invalid"),headers=self.headers())
        self.assertEqual(response.status_code,422)
        self.assertEqual((await self.client.get("/api/admin/config")).status_code,200)
        self.assertEqual(self.runtime.store.active()["id"],before)

    async def test_config_encryption_audit_invalidation_restore_and_persistence(self):
        await self.login()
        old_token=self.client.cookies.get(COOKIE)
        response=await self.client.get("/api/admin/config")
        self.assertNotIn("bind_password",response.text)
        candidate=self.candidate()
        candidate["bind_password"]="replacement bind pass "
        response=await self.client.put("/api/admin/config",json=candidate,headers=self.headers())
        self.assertEqual(response.status_code,200,response.text)
        new_id=response.json()["version"]
        self.assertNotEqual(new_id,self.original)
        active=self.runtime.store.active()
        self.assertNotIn("replacement bind pass",json.dumps(active))
        self.assertEqual(Fernet(self.key).decrypt(active["bind_cipher"].encode()).decode(),"replacement bind pass ")
        self.assertEqual((await self.client.get("/api/processes",headers={"Cookie":COOKIE+"="+old_token})).status_code,401)
        # Runtime/key reload, persisted configuration and new login still work.
        self.runtime=Runtime(self.engine,Fernet(self.key),self.directory,"https://test.invalid",str(self.bind_file))
        self.app.state.runtime=self.runtime
        self.assertEqual((await self.login()).status_code,200)
        response=await self.client.get("/api/admin/audit")
        self.assertEqual(response.status_code,200)
        self.assertNotIn("replacement bind pass",response.text)
        self.assertTrue(any(x["action"]=="config_activate" for x in response.json()["items"]))
        from app import bootstrap
        output=io.StringIO()
        with patch("app.bootstrap.build_runtime",return_value=self.runtime),patch("sys.argv",["bootstrap","restore","--version",str(self.original)]),contextlib.redirect_stdout(output):
            bootstrap.main()
        self.assertEqual(self.runtime.store.active()["id"],self.original)
        self.assertNotIn("pass",output.getvalue())
        self.assertEqual((await self.client.get("/api/processes")).status_code,401)

    async def test_config_csrf_stale_version_and_tls_bypass_forbidden(self):
        await self.login()
        candidate=self.candidate()
        self.assertEqual((await self.client.put("/api/admin/config",json=candidate)).status_code,403)
        candidate["expected_version"]+=100
        self.assertEqual((await self.client.put("/api/admin/config",json=candidate,headers=self.headers())).status_code,409)
        candidate=self.candidate()
        candidate["settings"]["verify_tls"]=False
        self.assertEqual((await self.client.put("/api/admin/config",json=candidate,headers=self.headers())).status_code,422)

class AdapterTests(unittest.TestCase):
    def test_user_bind_transport_abort_is_never_retried_on_second_dc(self):
        from unittest.mock import Mock
        from ldap3.core.exceptions import LDAPSocketReceiveError
        cfg=LdapSettings(**CFG)
        directory=LdapDirectory("/etc/ssl/certs/ca-certificates.crt")
        server=directory._server(cfg,cfg.servers[0])
        for failure in (OSError("synthetic transport abort"),LDAPSocketReceiveError("synthetic receive timeout")):
            with self.subTest(failure=type(failure).__name__):
                service=Mock()
                service.server=server;service.bind.return_value=True
                service.result={"result":0}
                service.response=[entry("1"*32,"admin",[CFG["admin_group"]])]
                user=Mock();user.bind.side_effect=failure
                # A reachable second service/user pair is deliberately available.
                second_service=Mock();second_service.bind.return_value=True
                second_user=Mock();second_user.bind.return_value=True
                with patch.object(directory,"_connection",side_effect=[service,user,second_service,second_user]) as connect:
                    with self.assertRaises(DirectoryUnavailable):
                        directory.authenticate(cfg,"synthetic-bind","admin","synthetic-user-password")
                    self.assertEqual(connect.call_count,2)
                    self.assertEqual(user.bind.call_count,1)
                    second_service.bind.assert_not_called()
                    second_user.bind.assert_not_called()

    def test_file_terminator_preserves_legitimate_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"s"
            for raw,want in [(b" a \n"," a "),(b" a \r\n"," a "),(b" a "," a "),(b"x\n\n","x\n")]:
                p.write_bytes(raw)
                self.assertEqual(read_secret(p),want)

    def test_tls_referrals_filter_escaping_failover_and_no_bad_password_retry(self):
        import ssl
        from unittest.mock import Mock
        cfg=LdapSettings(**CFG)
        directory=LdapDirectory("/etc/ssl/certs/ca-certificates.crt")
        server=directory._server(cfg,cfg.servers[0])
        self.assertTrue(server.ssl)
        self.assertEqual(server.tls.validate,ssl.CERT_REQUIRED)
        self.assertEqual(server.tls.version,ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(server.tls.valid_names,[cfg.servers[0]])
        self.assertEqual(server.tls.sni,cfg.servers[0])
        with patch("app.directory.Connection") as constructor:
            directory._connection(server,"test","synthetic",cfg)
            self.assertFalse(constructor.call_args.kwargs["auto_referrals"])
            self.assertTrue(constructor.call_args.kwargs["read_only"])
            self.assertEqual(constructor.call_args.kwargs["receive_timeout"],3)
        calls=[]
        row=entry("1"*32,"admin",[CFG["admin_group"]])
        service=Mock()
        service.server=server;service.bind.return_value=True
        service.result={"result":0};service.response=[row]
        service.search.side_effect=lambda *args,**kwargs:calls.append((args,kwargs))
        user=Mock();user.bind.return_value=True
        with patch.object(directory,"_connection",side_effect=[OSError("offline"),service,user]):
            principal=directory.authenticate(cfg,"synthetic-bind","admin*)(objectClass=*)","synthetic-user")
        self.assertEqual(principal.role,"admin")
        self.assertIn(r"\2a\29\28",calls[0][0][1])
        service.result={"result":0}
        user.bind.return_value=False;user.result={"result":49}
        with patch.object(directory,"_connection",side_effect=[service,user]) as connect:
            with self.assertRaises(DirectoryDenied):
                directory.authenticate(cfg,"synthetic-bind","admin","wrong")
            self.assertEqual(connect.call_count,2)

if __name__=="__main__":
    unittest.main()
