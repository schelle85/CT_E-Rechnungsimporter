from graph_access_test_support import transport_access
from graph_access_test_support import admitted_transport
from contextlib import nullcontext
import json
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
import sqlalchemy as sa
from cryptography.fernet import Fernet,InvalidToken
from app.graph import GraphClient,GraphError,retry_not_before
from app.notification_certificate import CERTIFICATE_TOKEN,CertificateMaterial,certificate_client,record_certificate
from app.notification_model import NotificationError
from app.notification_runtime import INITIAL_FILE,load_notification_cipher,run_job
from app.notification_schema007 import outbox,settings
from notification_test_support import Fixture,CONFIG,SCOPE,NOW,material

class DeliveryTests(Fixture,unittest.TestCase):
    def test_graph_auth_and_transport_are_capped_by_remaining_absolute_deadline(self):
        from types import SimpleNamespace
        now=[100.0];calls=[];limits=[]
        def limit(seconds,**kwargs):limits.append(seconds);return nullcontext()
        with httpx.Client(transport=httpx.MockTransport(lambda request:(calls.append(request) or httpx.Response(200,json={"id":"inbox"})))) as http:
            client=GraphClient(CONFIG,SimpleNamespace(get_token=lambda _:SimpleNamespace(token="synthetic")),http,
                clock=lambda:now[0],deadline=100.25,**transport_access())
            with patch("app.graph_deadline.request_deadline",side_effect=limit):client.probe()
            self.assertEqual(limits,[.25])
            now[0]=100.3
            with self.assertRaises(GraphError) as error:client._write("POST",client.root+"/sendMail",{},expected=202)
            self.assertEqual(error.exception.code,"graph_request_deadline")
        self.assertEqual(len(calls),1)

    def test_late_post_gate_commit_never_starts_transport_after_budget(self):
        self.configure()
        row=self.request_row()
        begin=self.store.begin_post
        def late_commit(ticket,*,budget):
            payload=begin(ticket,budget=budget)
            self.now[0]+=81
            return payload
        with patch.object(self.store,"begin_post",side_effect=late_commit):
            result=self.service(material()).send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
        self.assertEqual((result["state"],result["reservations"],result["error_code"]),
            ("unknown",1,"notification_deadline_before_transport"))
        self.assertEqual(sum(request.method=="POST" for request in self.http_calls),0)
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))

    def test_existing_adapter_read_defaults_remain_three_attempts_and_writes_one(self):
        from types import SimpleNamespace
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(503 if len(calls)<3 else 200,json={"id":"inbox"})
        credential=SimpleNamespace(get_token=lambda _:SimpleNamespace(token="synthetic"))
        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            client=GraphClient(CONFIG,credential,http,sleep=lambda _:None,**transport_access())
            with client._response("GET",client.root+"/mailFolders/inbox") as response:self.assertEqual(response.status_code,200)
        self.assertEqual(len(calls),3)
        calls.clear()
        with httpx.Client(transport=httpx.MockTransport(lambda request:(calls.append(request) or httpx.Response(429)))) as http:
            client=GraphClient(CONFIG,credential,http,sleep=lambda _:None,**transport_access())
            with self.assertRaises(GraphError):
                with client._response("POST",client.root+"/sendMail",payload={}):pass
        self.assertEqual(len(calls),1)
    def test_202_only_one_post_and_no_database_transaction_across_network(self):
        self.configure()
        row=self.request_row()
        active=[0]
        sa.event.listen(self.engine,"begin",lambda c:active.__setitem__(0,active[0]+1))
        sa.event.listen(self.engine,"commit",lambda c:active.__setitem__(0,active[0]-1))
        sa.event.listen(self.engine,"rollback",lambda c:active.__setitem__(0,active[0]-1))
        def respond(request):
            self.assertEqual(active[0],0)
            if request.method=="GET":return httpx.Response(200,json={"id":"inbox"})
            self.assertEqual(request.url.path,"/v1.0/users/invoice@example.invalid/sendMail")
            payload=json.loads(request.content)
            self.assertTrue(payload["saveToSentItems"])
            self.assertEqual(len(payload["message"]["toRecipients"]),2)
            return httpx.Response(202)
        service=self.service(material(),handler=respond)
        first=service.send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
        self.assertEqual((first["state"],first["http_status"]),("accepted",202))
        service.send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
        self.assertEqual(sum(r.method=="POST" for r in self.http_calls),1)
        self.assertEqual(active[0],0)

    def test_definite_4xx_and_uncertain_responses_never_replay(self):
        self.configure()
        for status,expected in ((400,"rejected"),(403,"rejected"),(429,"rejected"),(500,"unknown"),(503,"unknown"),(200,"unknown"),(302,"unknown")):
            with self.subTest(status=status):
                self.now[0]+=3601
                row=self.request_row()
                def respond(request):
                    return httpx.Response(200,json={"id":"inbox"}) if request.method=="GET" else httpx.Response(status,headers={"Retry-After":"900"})
                service=self.service(material(),handler=respond)
                result=service.send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
                self.assertEqual((result["state"],result["reservations"]),(expected,1))
                before=len(self.http_calls)
                service.send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
                self.assertEqual(len(self.http_calls),before)

    def test_transport_timeout_has_one_post_and_unknown_durable_reservation(self):
        self.configure()
        row=self.request_row()
        def respond(request):
            if request.method=="GET":return httpx.Response(200,json={"id":"inbox"})
            raise httpx.ReadTimeout("synthetic-private-upstream",request=request)
        result=self.service(material(),handler=respond).send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
        self.assertEqual((result["state"],result["reservations"]),("unknown",1))
        self.assertEqual(sum(r.method=="POST" for r in self.http_calls),1)
        self.assertNotIn("synthetic-private-upstream",json.dumps(result))

    def test_uncertain_reservation_commit_stops_before_post(self):
        self.configure()
        row=self.request_row();owner=uuid4().hex
        reserve=self.store.reserve
        def lost_commit_response(ticket,*,budget):
            self.assertTrue(reserve(ticket,budget=budget))
            raise RuntimeError("synthetic-lost-db-ack")
        with patch.object(self.store,"reserve",side_effect=lost_commit_response):
            with self.assertRaises(RuntimeError):self.service(material()).send(row["slot_key"],budget=self.budget(),owner=owner)
        self.assertEqual(sum(r.method=="POST" for r in self.http_calls),0)
        self.assertEqual(self.store.recover(row["slot_key"],stopped_owner=owner)["state"],"unknown")

    def test_preflight_429_backoff_defers_other_probe_and_retains_unreserved_slot(self):
        self.configure()
        row=self.request_row()
        service=self.service(material(),handler=lambda r:httpx.Response(429,headers={"Retry-After":"9999999999999999999999999"}))
        result=service.send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
        self.assertEqual((result["state"],result["reservations"]),("prepared",0))
        self.assertEqual(self.store.transport_not_before(SCOPE),9223372036854775807)
        before=len(self.http_calls)
        checked=self.service(material()).observe(probe=True)
        self.assertEqual(checked["probe_code"],"notification_transport_deferred")
        self.assertEqual(len(self.http_calls),before)
        self.assertEqual(len(self.http_calls),1)
        for value in (None,"bad","-1"):
            self.assertEqual(retry_not_before(value,now=1000),1900)
        self.assertEqual(retry_not_before("3600",now=1000),4600)
        self.assertEqual(retry_not_before("Thu, 01 Jan 1970 01:00:00 GMT",now=1000),3600)

class CertificateTests(Fixture,unittest.TestCase):
    def test_matching_certificate_metadata_and_invalid_or_ambiguous_pem(self):
        certificate=material(days=2)
        self.assertEqual(certificate.metadata(NOW)["severity"],"orange")
        self.assertTrue(certificate.metadata(NOW)["valid"])
        public=certificate.pem.split(b"-----BEGIN PRIVATE KEY-----")[0]
        for bad in (b"invalid",public,public+certificate.pem):
            with self.assertRaises(NotificationError):CertificateMaterial.parse(bad)
        self.assertNotIn("PRIVATE",repr(certificate))

    def test_file_swap_or_invalid_successor_does_not_end_series(self):
        self.configure()
        old=material(days=2)
        initial=self.service(old).observe()
        healthy=material(days=30)
        swapped=self.service(healthy).observe()
        self.assertEqual(swapped["warning"]["fingerprint"],old.fingerprint)
        self.assertIsNone(swapped["proof"])
        failed=self.service(healthy,handler=lambda r:httpx.Response(403)).observe(probe=True)
        self.assertEqual(failed["warning"]["fingerprint"],old.fingerprint)
        future=self.service(material(days=30,before=1)).observe(probe=True)
        self.assertFalse(future["current"]["valid"])
        self.assertEqual(future["warning"]["fingerprint"],old.fingerprint)
        missing=self.service(None).observe(probe=True)
        self.assertEqual(missing["warning"],initial["warning"])
        self.assertIn("code",missing["current"])

    def test_fresh_valid_successor_closes_old_unreserved_series_and_warns_own_certificate(self):
        self.configure()
        old=material(days=2)
        planned=self.service(old).plan()
        old_row=next(row for row in planned if row["kind"]=="certificate")
        successor=material(days=5)
        value=self.service(successor).observe(probe=True)
        self.assertEqual(value["proof"]["fingerprint"],successor.fingerprint)
        self.assertEqual(value["proof"]["scope_key"],SCOPE)
        self.assertEqual(value["last_closed"]["fingerprint"],old.fingerprint)
        self.assertEqual(value["warning"]["fingerprint"],successor.fingerprint)
        self.assertEqual(self.store.read(old_row["slot_key"])["state"],"obsolete")
        new_row=next(row for row in self.service(successor).plan() if row["kind"]=="certificate")
        self.assertNotEqual(old_row["slot_key"],new_row["slot_key"])

    def test_expired_certificate_still_attempts_one_warning_when_graph_works(self):
        self.configure()
        expired=material(days=-1)
        service=self.service(expired)
        row=next(row for row in service.plan() if row["kind"]=="certificate")
        result=service.send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
        self.assertEqual(result["state"],"accepted")
        current=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)["data"]
        self.assertTrue(current["current"]["expired"])
        self.assertIsNone(current["proof"])
        self.assertEqual(current["warning"]["fingerprint"],expired.fingerprint)

    def test_expired_certificate_auth_failure_is_neutral_and_next_day_remains_plannable(self):
        from contextlib import contextmanager
        self.configure()
        expired=material(days=-1)
        service=self.service(expired)
        row=next(row for row in service.plan() if row["kind"]=="certificate")
        regular=self.factory()
        @contextmanager
        def failed_auth(config,certificate):
            with regular(config,certificate) as client:
                client.credential.get_token=lambda _:(_ for _ in ()).throw(ValueError("synthetic-private-auth-detail"))
                yield client
        service.client_factory=failed_auth
        result=service.send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
        self.assertEqual((result["state"],result["reservations"],result["error_code"]),
            ("prepared",0,"graph_authentication_failed"))
        self.assertEqual(self.http_calls,[])
        self.assertNotIn("synthetic-private-auth-detail",json.dumps(result))
        current=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)["data"]
        self.assertEqual(current["current"]["severity"],"red")
        self.assertIsNone(current["proof"])
        self.now[0]+=86400
        following=next(row for row in self.service(expired).plan() if row["kind"]=="certificate")
        self.assertNotEqual(following["slot_key"],row["slot_key"])

    def test_stale_local_observation_and_proof_cannot_overwrite_newer_certificate(self):
        self.configure()
        old=material(days=2)
        stale=self.service(old)
        stale.local_observation()
        healthy=material(days=30)
        newer=self.service(healthy)
        newer.observe(probe=True)
        before=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)
        with admitted_transport(),self.assertRaises(NotificationError):stale._proof()
        with self.assertRaises(NotificationError):stale.local_observation()
        self.assertEqual(self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN),before)
        self.assertIsNone(before["data"]["warning"])

    def test_real_fresh_credential_constructor_uses_exact_read_bytes_without_persistent_cache(self):
        certificate=material()
        with patch("app.notification_certificate.protected_bytes",return_value=certificate.pem) as reader:
            loaded=CertificateMaterial.load("/synthetic/credential")
        reader.assert_called_once_with("/synthetic/credential")
        clients=[]
        with admitted_transport(),patch("azure.identity.CertificateCredential") as provider:
            for _ in range(2):
                with certificate_client(CONFIG,loaded) as client:clients.append(client)
            self.assertEqual(provider.call_count,2)
            for call in provider.call_args_list:
                self.assertIs(call.kwargs["certificate_data"],loaded.pem)
                self.assertEqual(call.kwargs["retry_total"],0)
                self.assertNotIn("cache_persistence_options",call.kwargs)
                self.assertNotIn("additionally_allowed_tenants",call.kwargs)
            self.assertEqual(provider.return_value.close.call_count,2)
        self.assertTrue(all(client.read_attempts==1 for client in clients))

class OperatorRuntimeTests(Fixture,unittest.TestCase):
    def job(self,command,**values):
        with patch("app.notification_runtime.make_engine",return_value=self.engine),patch(
                "app.notification_runtime.GraphConfig.load",return_value=CONFIG),patch(
                "app.notification_runtime.load_notification_cipher",return_value=self.cipher):
            return run_job(dict(command=command,deadline=time.monotonic()+20,**values))

    def test_private_init_operator_request_replay_and_readback_without_ad(self):
        initial=dict(expected_version=0,settings=self.config)
        with patch("app.notification_runtime.protected_bytes",return_value=json.dumps(initial).encode()) as read:
            configured=self.job("configure-init",config=INITIAL_FILE)
            self.assertEqual((configured["actor"],configured["version"]),("operator",1))
            read.assert_called_once_with(INITIAL_FILE)
            with self.assertRaises(NotificationError):self.job("configure-init",config=INITIAL_FILE)
        request=str(uuid4())
        first=self.job("request-test",request_id=request,expected_version=1)["receipt"]
        self.configure(recipients=["changed@example.invalid"])
        replay=self.job("request-test",request_id=request,expected_version=1)["receipt"]
        self.assertEqual(replay["slot_key"],first["slot_key"])
        self.assertEqual(replay["actor"],"operator")
        self.assertEqual(self.job("status",request_id=request,expected_version=1)["receipt"],replay)
        preview=self.job("preview",slot_key=first["slot_key"])
        self.assertEqual(len(preview["payload"]["message"]["toRecipients"]),2)
        self.assertEqual(self.store.history(SCOPE)["total"],1)
        with self.engine.connect() as c:self.assertEqual(c.execute(sa.text("SELECT count(*) FROM auth_sessions")).scalar_one(),0)

    def test_status_does_not_require_the_notification_key_or_ldap_files(self):
        self.configure()
        row=self.request_row()
        with patch("app.notification_runtime.make_engine",return_value=self.engine),patch(
                "app.notification_runtime.GraphConfig.load",return_value=CONFIG),patch(
                "app.notification_runtime.load_notification_cipher",side_effect=AssertionError("no secret loading")):
            result=run_job(dict(command="status",slot_key=row["slot_key"],deadline=time.monotonic()+10))
        self.assertEqual(result["receipt"]["slot_key"],row["slot_key"])

    def test_notification_key_is_independent_and_missing_key_does_not_load_ldap(self):
        ldap=Fernet(Fernet.generate_key())
        encrypted=ldap.encrypt(b"synthetic-ldap-password")
        with patch.dict("os.environ",{"NOTIFICATION_KEY_FILE":"/synthetic/notification-key","CONFIG_KEY_FILE":"/forbidden/config"}),patch(
                "app.notification_runtime.protected_bytes",return_value=self.key) as read:
            cipher=load_notification_cipher()
            with self.assertRaises(InvalidToken):cipher.decrypt(encrypted)
            self.assertEqual(cipher.decrypt(cipher.encrypt(b"notification")),b"notification")
            read.assert_called_once_with("/synthetic/notification-key")
        with patch("app.notification_runtime.protected_bytes",side_effect=GraphError("graph_operator_file_unavailable")):
            with self.assertRaises(NotificationError) as raised:load_notification_cipher()
            self.assertEqual(raised.exception.code,"notification_key_unavailable")

    def test_runtime_captures_revision_before_pem_read_and_rejects_stale_publication(self):
        self.configure()
        healthy=material(days=30);old=material(days=2)
        def change_during_read(path):
            record_certificate(self.store,SCOPE,healthy.metadata(self.now[0]),expected_revision=0)
            return old
        with patch("app.notification_runtime.CertificateMaterial.load",side_effect=change_during_read):
            with self.assertRaises(NotificationError):self.job("observe")
        saved=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)["data"]
        self.assertEqual(saved["current"]["fingerprint"],healthy.fingerprint)
        self.assertIsNone(saved["warning"])
