import time
from unittest.mock import patch
import unittest
import httpx
from app.graph import GraphClient, GraphError
from app.graph_deadline import bounded_operation, request_deadline
from test_graph import CONFIG, Credential


def blocked_authentication():
    # Synthetic operation blocks before producing a token/HTTP response.
    time.sleep(30)
    return {"ok": True}


class Trickle(httpx.SyncByteStream):
    def __init__(self, tick):
        self.tick, self.consumed, self.closed = tick, 0, False
    def __iter__(self):
        for _ in range(1000):
            self.consumed += 1
            self.tick()
            yield b" "
    def close(self):
        self.closed = True


class GraphDeadlineTests(unittest.TestCase):
    def test_many_small_transport_pieces_stop_before_full_consumption(self):
        now = [0]
        stream = Trickle(lambda: now.__setitem__(0, now[0] + 1))
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=stream))) as http:
            client = GraphClient(CONFIG, Credential(), http, clock=lambda: now[0])
            with self.assertRaises(GraphError) as raised:
                client.probe()
        self.assertEqual(raised.exception.code, "graph_response_limit")
        self.assertEqual(stream.consumed, 45)
        self.assertTrue(stream.closed)

    def test_blocking_read_interrupted_and_write_uncertainty_preserved(self):
        stream = Trickle(lambda: time.sleep(30))
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=stream))) as http:
            client = GraphClient(CONFIG, Credential(), http)
            def short_deadline(*_, **kwargs):
                return request_deadline(0.03, **kwargs)
            with patch("app.graph_deadline.request_deadline", side_effect=short_deadline):
                started = time.monotonic()
                with self.assertRaises(GraphError) as raised:
                    client._json("POST", client.root + "/mailFolders/inbox/childFolders", payload={})
        self.assertEqual(raised.exception.code, "graph_request_deadline")
        self.assertTrue(raised.exception.uncertain)
        self.assertLess(time.monotonic() - started, 2)
        self.assertTrue(stream.closed)

    def test_authentication_inside_request_deadline(self):
        credential = Credential()
        credential.get_token = lambda _: blocked_authentication()
        with httpx.Client(transport=httpx.MockTransport(lambda _: self.fail("no HTTP"))) as http:
            client = GraphClient(CONFIG, credential, http)
            with patch("app.graph_deadline.request_deadline", side_effect=lambda *_, **kw: request_deadline(0.03, **kw)):
                with self.assertRaises(GraphError) as raised:
                    client.probe()
        self.assertEqual(raised.exception.code, "graph_request_deadline")

    def test_parent_kills_stuck_operation_without_replay(self):
        started = time.monotonic()
        result = bounded_operation(blocked_authentication, seconds=0.1, uncertain=True)
        self.assertEqual(result, {"ok": False, "code": "graph_operation_deadline", "uncertain": True})
        self.assertLess(time.monotonic() - started, 2.5)
