"""Host probe CLI contract; synthetic SDK/HTTP, no privileged or external effects."""
import io
from contextlib import nullcontext
import json
import stat
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from uuid import uuid4

from app import graph_access_probe as probe
from app.graph import GraphError
from graph_access_test_support import BOUND,admitted_transport
from notification_test_support import Fixture,CONFIG,SCOPE,material
from test_graph_access import host_module


class RequestTests(unittest.TestCase):
    def packet(self):
        return dict(schema_version=1,operation_id=str(uuid4()),epoch=3,purpose="candidate-read",
            consumer_role="candidate",consumer_id="e"*64,secret="f"*64)

    def test_only_bounded_fixed_packet_has_no_paths_or_worker_flags(self):
        packet=self.packet()
        self.assertEqual(probe.request(json.dumps(packet).encode())["secret"],"f"*64)
        for change in ({"path":"/other"},{"epoch":True},{"secret":"x"*64},
                {"consumer_role":"api"},{"purpose":"finalize-proof"},{"schema_version":False}):
            with self.subTest(change=change),self.assertRaises(GraphError):
                probe.request(json.dumps(dict(packet,**change)).encode())
        for raw in (b"x"*4097,b'{"schema_version":1,"schema_version":1}'):
            with self.assertRaises(GraphError):probe.request(raw)

    def test_cli_failure_does_not_echo_secret_or_upstream_details(self):
        output=io.StringIO()
        with patch.object(probe.os,"name","posix"),patch.object(probe.os,"geteuid",return_value=10001,create=True),patch.object(
                probe.os,"getegid",return_value=10001,create=True),patch.object(probe.sys,"argv",["probe"]),patch.object(
                probe.sys,"stdin",SimpleNamespace(buffer=io.BytesIO(json.dumps(self.packet()).encode()))),patch.object(
                probe,"run",side_effect=GraphError("private-upstream-value")),patch.object(probe.sys,"stdout",output):
            self.assertEqual(probe.main(),1)
        self.assertEqual(json.loads(output.getvalue()),dict(ok=False,code="graph_probe_unavailable"))


class ProbeTests(Fixture,unittest.TestCase):
    def run_probe(self,purpose):
        value=probe.request(json.dumps(dict(schema_version=1,operation_id=str(uuid4()),epoch=1,purpose=purpose,
            consumer_role="notifications" if purpose=="finalize-proof" else "candidate",
            consumer_id="e"*64,secret="f"*64)).encode())
        with patch.object(probe.GraphConfig,"load",return_value=CONFIG),patch.object(
                probe.CertificateMaterial,"load",return_value=material()),patch.object(probe.runtime,"binding",return_value=BOUND),patch.object(
                probe.runtime,"host_probe",side_effect=admitted_transport),patch.object(probe,"certificate_client",self.factory()),patch.object(
                probe,"bounded_operation",side_effect=lambda operation,args,**kwargs:operation(*args)):
            return probe.run(value)

    def test_read_probe_uses_fresh_get_without_db_or_productive_proof(self):
        with patch.object(probe,"make_engine",side_effect=AssertionError("read probe must not touch DB")):
            result=self.run_probe("candidate-read")
        self.assertTrue(result["ok"]);self.assertIsNone(result["proof_revision"])
        self.assertEqual([r.method for r in self.http_calls],["GET"])
        self.assertNotIn("secret",json.dumps(result));self.assertNotIn("f"*64,json.dumps(result))

    def test_finalization_alone_records_current_bound_proof_after_get(self):
        self.configure()
        with patch.object(probe,"make_engine",return_value=self.engine):result=self.run_probe("finalize-proof")
        self.assertGreater(result["proof_revision"],0);self.assertIsInstance(result["proof_at"],int)
        self.assertEqual([r.method for r in self.http_calls],["GET"])
        observed=self.store.monitor_state(SCOPE,"certificate",probe.CERTIFICATE_TOKEN)
        self.assertEqual(observed["data"]["proof"]["fingerprint"],result["fingerprint"])


class ConsumerMountTests(unittest.TestCase):
    def test_separate_profile_returns_only_two_fixed_ro_metadata_targets(self):
        value=dict(binding_file="/synthetic/binding.json",directory="/synthetic/gate")
        profile=SimpleNamespace(read_text=lambda **_:json.dumps(value))
        protected=Mock(side_effect=[profile,Path(value["binding_file"])])
        directory=SimpleNamespace(stat=lambda:SimpleNamespace(st_gid=10001,st_mode=stat.S_IFDIR|0o750))
        result=host_module.consumer_mounts(protected,lambda _:directory)
        self.assertEqual([target for _,target in result],["/run/importer/graph-access-binding.json","/run/importer/operations/graph-access"])
        self.assertEqual(protected.call_args_list[0].args,(host_module.CONSUMER_PROFILE,))

    def test_extra_duplicate_or_unsafe_path_profile_rejected(self):
        for value in (dict(binding_file="/binding",directory="/gate",api_id="no"),
                dict(binding_file="/binding,bad",directory="/gate")):
            with self.subTest(value=value),self.assertRaises(ValueError):
                host_module.consumer_mounts(lambda _:SimpleNamespace(read_text=lambda **__:json.dumps(value)),Mock())
        with self.assertRaises(ValueError):
            host_module.consumer_mounts(lambda _:SimpleNamespace(read_text=lambda **__: '{"directory":"/a","directory":"/b"}'),Mock())
