"""Host/worker cleanup with real SQL/files/crypto, explicit inherited host and Graph doubles."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from app import rotation_cleanup,rotation_maintenance as maintenance,rotation_worker as worker
from app.graph import GraphError
from app.notification_certificate import CertificateMaterial
from app.rotation_schema008 import requests
from rotation_test_support import NOW,BINDING
import test_rotation_cleanup as cleanup_fixture
import test_rotation_host_flow as flow_fixture


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.f=flow_fixture.IntegratedHostTests();self.f.setUp();self.addCleanup(self.f.doCleanups);f=self.f
        f.root.adopt_existing(f.operation,f.remote.records[0],evidence="d"*64)
        self.assertTrue(f.controller.operate("run")["ok"])
        self.graph=cleanup_fixture.CleanupRemote(CertificateMaterial.parse(f.old_bytes),f.root.material(f.operation))
        self.events=[];self.fail_probe=False;self.permit=SimpleNamespace(check=lambda *a,**k:self.events.append("check"))
        @contextmanager
        def admission(config,current,*,expected_instance):
            self.assertEqual(expected_instance,BINDING.instance_id);self.assertEqual(current,self.graph.signer)
            self.events.append("admitted")
            try:yield self.permit
            finally:self.events.append("admission-closed")
        def probe():
            self.events.append("fresh-inbox")
            if self.fail_probe:raise GraphError("synthetic_fresh_probe_failed")
        @contextmanager
        def certificate(config,current):yield SimpleNamespace(probe=probe)
        @contextmanager
        def graph(bound,current,*,deadline,access):
            self.assertIs(access,self.permit);self.assertEqual(current,self.graph.signer);self.assertIn("fresh-inbox",self.events)
            yield self.graph
        for name,value in (("graph_operation",admission),("certificate_client",certificate),("rotation_client",graph)):
            f.stack.enter_context(patch.object(maintenance,name,side_effect=value))
        f.stack.enter_context(patch.object(worker.time,"time",return_value=NOW+rotation_cleanup.OVERLAP_SECONDS))
        f.stack.enter_context(patch.object(flow_fixture,"NOW",NOW+rotation_cleanup.OVERLAP_SECONDS))

    def state(self):return rotation_cleanup.CleanupJournal(worker.AdoptionJournal(self.f.root,self.f.access)).state(self.f.operation)
    def resume(self):return self.f.fresh_controller().operate("resume")

    def test_due_cleanup_requires_fresh_successor_then_releases_original_request(self):
        f=self.f;request_hash=f.store.read(f.operation)["request_hash"];initial=self.state()
        with patch.object(worker.time,"time",return_value=NOW+1):
            self.assertEqual(self.resume()["cleanup"]["phase"],"planned")
        self.assertEqual(self.events,[]);self.assertEqual(self.graph.removes,0)
        result=self.resume();self.assertEqual(result["cleanup"]["phase"],"completed")
        self.assertEqual(f.store.read(f.operation)["state"],"completed");self.assertIsNone(f.store.status()["active_operation"])
        self.assertEqual(f.store.read(f.operation)["request_hash"],request_hash);self.assertEqual(self.graph.removes,1)
        self.assertEqual(self.state()["not_before"],initial["not_before"]);self.assertFalse((f.root.directory/(f.operation+".old.pem")).exists())
        before=list(self.events);self.assertEqual(self.resume()["code"],"rotation_no_active_request");self.assertEqual(self.events,before)

    def test_graph_pause_and_foreign_drain_defer_without_fresh_probe_or_removal(self):
        f=self.f;f.gate["mode"]="paused";self.assertEqual(self.resume()["cleanup"]["deferred"],"paused")
        f.gate["mode"]="allowed";path=Path(f.controller.host.DRAIN_FILE);path.write_text("foreign-operator-drain")
        self.assertEqual(self.resume()["cleanup"]["deferred"],"paused");self.assertEqual(path.read_text(),"foreign-operator-drain")
        self.assertEqual(self.events,[]);self.assertEqual(self.graph.removes,0);self.assertEqual(f.store.read(f.operation)["state"],"overlap")

    def test_failed_fresh_successor_probe_keeps_old_key_and_send_permission_unused(self):
        self.fail_probe=True
        with self.assertRaises(GraphError):self.resume()
        self.assertEqual(self.graph.removes,0);self.assertEqual(self.state()["phase"],"planned")
        self.assertTrue((self.f.root.directory/(self.f.operation+".old.pem")).exists())

    def test_slow_probe_close_does_not_refresh_the_original_success_time(self):
        now=[NOW+rotation_cleanup.OVERLAP_SECONDS]
        @contextmanager
        def delayed_close(config,current):
            yield SimpleNamespace(probe=lambda:self.events.append("fresh-inbox"))
            now[0]+=61  # Explicit clock/SDK-close double; no sleep or native deadline claim.
        with patch.object(maintenance,"certificate_client",side_effect=delayed_close),patch.object(worker.time,"time",side_effect=lambda:now[0]):
            with self.assertRaisesRegex(GraphError,"rotation_cleanup_proof_required"):self.resume()
        self.assertEqual(self.graph.removes,0);self.assertEqual(self.graph.reads,0);self.assertEqual(self.state()["phase"],"planned")

    def test_direct_worker_also_defers_under_paused_gate(self):
        self.f.gate["mode"]="paused"
        result=self.f.controller.worker("cleanup",self.f.operation)
        self.assertEqual(result["deferred"],"graph_paused");self.assertEqual(self.graph.removes,0);self.assertEqual(self.events,[])

    def test_unknown_remove_is_publicly_visible_then_read_reconciled_without_second_post(self):
        self.graph.removal_error="lost"
        self.assertEqual(self.resume()["cleanup"]["phase"],"removal_unknown")
        self.assertEqual(self.f.store.read(self.f.operation)["state"],"cleanup_unknown")
        self.assertEqual(self.resume()["cleanup"]["phase"],"completed");self.assertEqual(self.graph.removes,1)

    def test_loss_after_durable_local_completion_repairs_sql_without_remote_work(self):
        save=rotation_cleanup.CleanupJournal.save
        def crash(instance,value,**changes):
            result=save(instance,value,**changes)
            if changes.get("phase")=="completed":raise SystemExit("synthetic lost completed reply")
            return result
        with patch.object(rotation_cleanup.CleanupJournal,"save",new=crash),self.assertRaises(SystemExit):self.resume()
        self.assertEqual(self.state()["phase"],"completed");self.assertEqual(self.f.store.read(self.f.operation)["state"],"cleanup_started")
        previous=list(self.events);self.assertEqual(self.resume()["cleanup"]["phase"],"completed")
        self.assertEqual(self.events,previous);self.assertEqual(self.graph.removes,1);self.assertIsNone(self.f.store.status()["active_operation"])

    def test_completed_new_key_survives_boot_without_old_private_file_or_new_request(self):
        self.resume();f=self.f;original=f.root._read(f.operation+".host.json");cleanup=self.state()
        request_hash=f.store.read(f.operation)["request_hash"]
        f.gate["mode"]="paused";f.current_boot="88888888-8888-8888-8888-888888888888"
        result=f.start_through_automation()
        self.assertTrue(result["ok"]);self.assertTrue(result["graph_access"]["paused"])
        self.assertEqual(f.store.read(f.operation)["state"],"completed");self.assertIsNone(f.store.status()["active_operation"])
        self.assertEqual(f.store.read(f.operation)["request_hash"],request_hash);self.assertEqual(self.state(),cleanup)
        self.assertEqual(f.archive_for(original)["checkpoint"],original);self.assertEqual(self.graph.removes,1);self.assertEqual(f.remote.adds,1)
        self.assertFalse((f.root.directory/(f.operation+".old.pem")).exists())

    def test_closed_cleanup_rejects_changed_sql_completion_before_reclaim(self):
        self.resume();f=self.f;original=f.root._read(f.operation+".host.json")
        f.current_boot="88888888-8888-8888-8888-888888888888"
        with f.engine.begin() as connection:connection.execute(requests.update().values(error_code="rotation_cleanup_unknown"))
        with self.assertRaises(GraphError):self.resume()
        self.assertIsNone(f.store.status()["active_operation"]);self.assertEqual(f.root._read(f.operation+".host.json"),original)
        self.assertEqual(self.graph.removes,1)
