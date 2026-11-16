"""C2B-R1: real Linux parent budget, spawn, inner POSIX timer and mock HTTP."""
from contextlib import contextmanager
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx

from app import graph_access_probe as probe
from app.graph import GraphError
from app.notification_model import OperationBudget
from graph_access_test_support import BOUND,admitted_transport
from notification_test_support import CONFIG,material

ACTUAL_CHILD=probe._probe_child


def fixture_child(value,deadline):
    """Test-only seams live in the actual spawned process, never in API images."""
    settings=value["native_timing"];events=Path(settings["events"])
    def note(name):
        with events.open("a") as output:output.write(json.dumps(dict(event=name,at=time.monotonic(),pid=os.getpid()))+"\n")
    def config(_):
        note("preflight");time.sleep(settings.get("preflight",0));return CONFIG
    class Credential:
        def __init__(self,*_,**__):pass
        def get_token(self,*_):
            note("token");time.sleep(settings.get("token",0));return SimpleNamespace(token="synthetic")
        def close(self):note("close");time.sleep(settings.get("close",0))
    actual_http=httpx.Client
    def respond(request):
        note(request.method)
        assert request.method=="GET"
        return httpx.Response(200,json={"id":"synthetic-inbox"})
    def client(**kwargs):return actual_http(transport=httpx.MockTransport(respond),**kwargs)
    # Actual certificate_client -> operation -> GraphClient -> request_deadline.
    # Only admission/config/SDK/network are synthetic here; C2a proves real gate separately.
    with patch.object(probe.GraphConfig,"load",side_effect=config),patch.object(
            probe.CertificateMaterial,"load",return_value=material()),patch.object(probe.runtime,"binding",return_value=BOUND),patch.object(
            probe.runtime,"host_probe",side_effect=admitted_transport),patch("azure.identity.CertificateCredential",Credential),patch(
            "httpx.Client",side_effect=client):
        return ACTUAL_CHILD(value,deadline)


@unittest.skipUnless(os.name=="posix","Real POSIX timer/spawn check; never replace with Windows timer doubles")
class NativeProbeDeadlineTests(unittest.TestCase):
    def invoke(self,*,seconds,**timing):
        with tempfile.TemporaryDirectory() as directory:
            events=Path(directory)/"events.jsonl"
            value=dict(operation_id=str(uuid4()),epoch=1,purpose="candidate-read",consumer_role="candidate",
                consumer_id="e"*64,secret="f"*64,native_timing=dict(events=str(events),**timing))
            def budget(**kwargs):return OperationBudget(clock=time.monotonic,seconds=seconds)
            started=time.monotonic();result=None;error=None
            with patch.object(probe,"OperationBudget",side_effect=budget),patch.object(probe,"_probe_child",fixture_child):
                try:result=probe.run(value)
                except GraphError as caught:error=caught
            elapsed=time.monotonic()-started
            records=[json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
        self.assertFalse(multiprocessing.active_children(),"Parent returned with live probe child")
        return result,error,elapsed,records

    def test_actual_graph_get_succeeds_without_nested_timer_conflict(self):
        result,error,elapsed,events=self.invoke(seconds=6,preflight=.05,token=.05)
        self.assertIsNone(error);self.assertTrue(result["ok"])
        self.assertEqual([item["event"] for item in events],["preflight","token","GET","close"])
        self.assertLess(elapsed,6.5)

    def test_preflight_does_not_renew_original_budget_before_token_timer(self):
        result,error,elapsed,events=self.invoke(seconds=6,preflight=1.5,token=3)
        self.assertIsNone(result);self.assertEqual(error.code,"graph_probe_unavailable")
        names=[item["event"] for item in events]
        self.assertIn("token",names);self.assertNotIn("GET",names)
        self.assertLess(elapsed,6.5)

    def test_blocked_credential_close_is_inside_parent_budget_and_reaped(self):
        result,error,elapsed,events=self.invoke(seconds=6,close=8)
        self.assertIsNone(result);self.assertEqual(error.code,"graph_probe_unavailable")
        self.assertIn("GET",[item["event"] for item in events]);self.assertIn("close",[item["event"] for item in events])
        self.assertLess(elapsed,6.5)
