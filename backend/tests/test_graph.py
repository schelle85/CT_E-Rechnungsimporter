import json
import os
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
import httpx
from app.graph import GraphClient, GraphConfig, GraphError, JSON_LIMIT, protected_bytes, operator_client


CONFIG = GraphConfig("11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "invoice@example.invalid")


class Credential:
    def get_token(self, scope):
        assert scope == "https://graph.microsoft.com/.default"
        return SimpleNamespace(token="synthetic-token")


class GraphTransportTests(unittest.TestCase):
    def client(self, handler):
        http = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
        self.addCleanup(http.close)
        return GraphClient(CONFIG, Credential(), http, sleep=lambda _: None)

    def test_bound_probe_and_immutable_header(self):
        def handler(request):
            self.assertEqual(request.url.path, "/v1.0/users/invoice@example.invalid/mailFolders/inbox")
            self.assertEqual(request.url.params["$select"], "id")
            self.assertEqual(request.headers["Prefer"], 'IdType="ImmutableId"')
            return httpx.Response(200, json={"id": "inbox-synthetic"})
        self.assertEqual(self.client(handler).probe(), {"mailbox_access": "ok"})

    def test_untrusted_urls_never_get_token_or_request(self):
        client = self.client(lambda _: self.fail("request forbidden"))
        for url in ("https://evil.invalid/a", "http://graph.microsoft.com/v1.0/users/invoice@example.invalid/a",
                    "https://graph.microsoft.com.evil.invalid/a", "https://graph.microsoft.com/v1.0/users/other@example.invalid/a",
                    client.root + "/../other", client.root + "/a#fragment", "https://user@graph.microsoft.com/a"):
            with self.subTest(url=url), self.assertRaises(GraphError) as raised:
                client._json("GET", url)
            self.assertEqual(raised.exception.code, "graph_untrusted_url")

    def test_redirect_and_access_failures_closed(self):
        for status in (302, 401, 403):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, headers={"Location": "https://evil.invalid/token"}, text="PRIVATE UPSTREAM")
            with self.subTest(status=status), self.assertRaises(GraphError) as raised:
                self.client(handler).probe()
            self.assertNotIn("PRIVATE", str(raised.exception))
            self.assertEqual(len(calls), 1)

    def test_read_retry_budget_and_large_retry_after(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(503, json={"private": "never exported"})
        with self.assertRaises(GraphError):
            self.client(handler).probe()
        self.assertEqual(len(calls), 3)
        client = self.client(lambda _: httpx.Response(429, headers={"Retry-After": "3600"}))
        with self.assertRaises(GraphError) as raised:
            client.probe()
        self.assertEqual(raised.exception.code, "graph_retry_later")

    def test_write_timeout_not_replayed(self):
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout("secret-body", request=request)
        client = self.client(handler)
        with self.assertRaises(GraphError) as raised:
            client._json("POST", client.root + "/mailFolders/inbox/childFolders", payload={})
        self.assertTrue(raised.exception.uncertain)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("secret-body", str(raised.exception))

    def test_response_size_and_invalid_json(self):
        for body in (b"x" * (JSON_LIMIT + 1), b"[]", b"bad-json"):
            with self.subTest(size=len(body)), self.assertRaises(GraphError):
                self.client(lambda _: httpx.Response(200, content=body)).probe()

    def test_auth_error_neutral(self):
        client = self.client(lambda _: self.fail("no request"))
        def fail(*_):
            raise ValueError("PRIVATE PEM AND TOKEN")
        client.credential.get_token = fail
        with self.assertRaises(GraphError) as raised:
            client.probe()
        self.assertEqual(str(raised.exception), "graph_authentication_failed")

    def test_configuration_and_collection_scope(self):
        with self.assertRaises(GraphError):
            GraphConfig(CONFIG.tenant_id, CONFIG.client_id, "invoice@example.invalid/other")
        client = self.client(lambda _: self.fail("no request"))
        expected = client.root + "/mailFolders/inbox/messages"
        self.assertEqual(client._checked_url(expected + "?$skip=42", expected), expected + "?$skip=42")
        with self.assertRaises(GraphError):
            client._checked_url(client.root + "/messages", expected)

    def test_operator_file_permissions_and_symlink(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "synthetic")
            with open(path, "wb") as output:
                output.write(b"synthetic-operator-value")
            os.chmod(path, 0o440)
            real_stat = os.fstat
            def root_stat(fd):
                value = real_stat(fd)
                return SimpleNamespace(st_mode=value.st_mode, st_uid=0, st_size=value.st_size)
            with patch("app.graph.os.fstat", side_effect=root_stat):
                self.assertEqual(protected_bytes(path), b"synthetic-operator-value")
                for mode in (0o444, 0o460, 0o666):
                    os.chmod(path, mode)
                    with self.assertRaises(GraphError):
                        protected_bytes(path)
                os.chmod(path, 0o440)
                link = os.path.join(folder, "link")
                os.symlink(path, link)
                with self.assertRaises(GraphError):
                    protected_bytes(link)

    def test_operator_identity_options_and_close(self):
        value = json.dumps({"tenant_id": CONFIG.tenant_id, "client_id": CONFIG.client_id, "mailbox": CONFIG.mailbox}).encode()
        with patch("app.graph.protected_bytes", side_effect=[value, b"synthetic-pem"]), patch("azure.identity.CertificateCredential") as provider:
            with operator_client("config", "pem") as client:
                self.assertEqual(client.config.mailbox, CONFIG.mailbox)
            options = provider.call_args.kwargs
            self.assertEqual(options["retry_total"], 0)
            self.assertEqual(options["certificate_data"], b"synthetic-pem")
            self.assertNotIn("cache_persistence_options", options)
            self.assertNotIn("additionally_allowed_tenants", options)
            provider.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
