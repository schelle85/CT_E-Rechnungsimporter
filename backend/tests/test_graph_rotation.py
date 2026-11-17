"""Bound application/PoP and fixed candidate against synthetic transport only."""
import base64
from dataclasses import replace
import json
import unittest
from types import SimpleNamespace
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import httpx

from app.graph import GraphError
from app.rotation_model import candidate, proof, certificate_der, key_record, POP_AUDIENCE
from rotation_test_support import BINDING, OLD_ID, NEW_ID, NOW, material, public_key, transport


class GraphRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old, cls.new = material(days=365), candidate(NOW)

    def test_candidate_actual_lifetime_keypair_and_secret_repr(self):
        self.assertEqual(self.new.expires_at-self.new.not_before,180*86400)
        self.assertEqual(self.new.not_before,NOW-300)
        key=serialization.load_pem_private_key(self.new.pem,password=None)
        self.assertEqual(key.key_size,3072)
        self.assertNotIn("PRIVATE KEY",repr(self.new))

    def test_pop_signature_object_id_audience_and_exact_ten_minutes(self):
        token=proof(BINDING,self.old,NOW)
        parts=token.split(".")
        decode=lambda value:base64.urlsafe_b64decode(value+"="*((-len(value))%4))
        header,claims=(json.loads(decode(part)) for part in parts[:2])
        self.assertEqual((header["alg"],claims["iss"],claims["aud"]),("RS256",BINDING.application_id,POP_AUDIENCE))
        self.assertNotEqual(claims["iss"],BINDING.client_id)
        self.assertEqual((claims["nbf"],claims["exp"]),(NOW,NOW+600))
        cert=x509.load_der_x509_certificate(certificate_der(self.old))
        cert.public_key().verify(decode(parts[2]),".".join(parts[:2]).encode(),padding.PKCS1v15(),hashes.SHA256())

    def test_expired_signer_and_noncanonical_binding_rejected(self):
        with self.assertRaises(GraphError):proof(BINDING,replace(self.old,expires_at=NOW),NOW)
        with self.assertRaises(GraphError):replace(BINDING,application_id="{"+BINDING.application_id+"}")

    def test_add_only_public_der_fixed_metadata_one_post(self):
        calls=[]
        def handler(request):
            calls.append(request);return httpx.Response(200,json={"keyId":NEW_ID})
        with transport(handler,self.old) as graph:self.assertEqual(graph.add(self.new),NEW_ID)
        self.assertEqual(len(calls),1)
        self.assertEqual(str(calls[0].url),"https://graph.microsoft.com/v1.0/applications/"+BINDING.application_id+"/addKey")
        body=json.loads(calls[0].content)
        self.assertEqual(base64.b64decode(body["keyCredential"]["key"]),certificate_der(self.new))
        self.assertIsNone(body["passwordCredential"])
        self.assertNotIn("PRIVATE KEY",calls[0].content.decode())
        self.assertNotIn("keyId",body["keyCredential"])

    def test_selected_get_checks_both_ids_and_all_key_bytes(self):
        def response(app_id):
            return lambda _:httpx.Response(200,json=dict(id=app_id,appId=BINDING.client_id,
                keyCredentials=[public_key(self.old,OLD_ID)]))
        with transport(response(BINDING.application_id),self.old) as graph:
            self.assertEqual(graph.read()[0]["fingerprint"],self.old.fingerprint)
        with transport(response(NEW_ID),self.old) as graph:
            with self.assertRaises(GraphError):graph.read()
        changed=public_key(self.old,OLD_ID);changed["endDateTime"]="2020-01-01T00:00:00Z"
        with self.assertRaises(GraphError):key_record(changed)

    def test_server_error_forbidden_and_redirect_are_never_replayed(self):
        for status,uncertain in ((503,True),(403,False),(307,True)):
            calls=[]
            def handler(request):
                calls.append(request);return httpx.Response(status,headers={"Location":"https://untrusted.invalid"})
            with transport(handler,self.old) as graph:
                with self.assertRaises(GraphError) as caught:graph.add(self.new)
            self.assertEqual(caught.exception.uncertain,uncertain)
            self.assertEqual(len(calls),1)

    def test_remove_uses_successor_pop_and_exact_managed_id(self):
        calls=[]
        def handler(request):calls.append(request);return httpx.Response(204)
        with transport(handler,self.new) as graph:graph.remove(OLD_ID)
        self.assertEqual(json.loads(calls[0].content)["keyId"],OLD_ID)
        self.assertEqual(len(calls),1)

    def test_cleanup_admission_checked_before_credential_and_before_remove_transport(self):
        events=[]
        def check(pem,fingerprint,*,method):
            self.assertEqual(pem,self.new.pem);self.assertEqual(fingerprint,self.new.fingerprint)
            self.assertEqual(method,"POST");events.append("admission")
        def handler(request):events.append("http");return httpx.Response(204)
        with transport(handler,self.new) as graph:
            graph.access=SimpleNamespace(check=check)
            graph.credential=SimpleNamespace(get_token=lambda scope:(events.append("token") or SimpleNamespace(token="synthetic")))
            graph.remove(OLD_ID)
        self.assertEqual(events,["admission","token","admission","http"])

    def test_changed_cleanup_admission_after_credential_prevents_remove_transport(self):
        events=[]
        def check(*args,**kwargs):
            events.append("admission")
            if len(events)==2:raise GraphError("synthetic_admission_changed")
        with transport(lambda request:self.fail("remove after changed admission"),self.new) as graph:
            graph.access=SimpleNamespace(check=check)
            with self.assertRaises(GraphError):graph.remove(OLD_ID)
        self.assertEqual(events,["admission","admission"])

    def test_invalid_or_large_response_stays_uncertain(self):
        for response in (httpx.Response(200,content=b"invalid"),httpx.Response(200,content=b"x"*131073),
                httpx.Response(200,content=b'{"keyId":"a","keyId":"b"}')):
            with transport(lambda _:response,self.old) as graph:
                with self.assertRaises(GraphError) as caught:graph.add(self.new)
            self.assertTrue(caught.exception.uncertain)

    def test_nonfixed_candidate_never_reaches_post(self):
        calls=[]
        with transport(lambda request:calls.append(request),self.old) as graph:
            with self.assertRaises(GraphError):graph.add(self.old)
        self.assertEqual(calls,[])
