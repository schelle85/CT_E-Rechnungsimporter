"""Explicit ownership: real SQL/files/crypto; inherited OS, Docker and Graph doubles."""
from contextlib import contextmanager,redirect_stderr
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from app import rotation_ownership as ownership,rotation_worker as worker
from app.graph import GraphError
from app.rotation_schema008 import head,requests
from rotation_test_support import BINDING,OLD_ID,NEW_ID
from test_rotation_host import host
import test_rotation_host_flow as flow_fixture
import test_rotation_maintenance as maintenance_fixture


def bind_graph(test,f,remote):
    events=[];permit=SimpleNamespace(check=lambda *args:events.append("material-check"))
    @contextmanager
    def admission(config,current,*,expected_instance):
        test.assertEqual(expected_instance,BINDING.instance_id);test.assertEqual(current.pem,remote.signer.pem)
        events.append("shared-admission")
        try:yield permit
        finally:events.append("admission-closed")
    @contextmanager
    def graph(bound,current,*,deadline,access):
        test.assertEqual(bound,BINDING);test.assertIs(access,permit);test.assertEqual(current.pem,remote.signer.pem)
        yield remote
    f.stack.enter_context(patch.object(ownership,"graph_operation",side_effect=admission))
    f.stack.enter_context(patch.object(ownership,"rotation_client",side_effect=graph))
    return events


class BootstrapOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.f=flow_fixture.IntegratedHostTests();self.f.setUp();self.addCleanup(self.f.doCleanups);f=self.f
        with f.engine.begin() as connection:
            connection.execute(requests.delete());connection.execute(head.update().values(active_operation=None,revision=0))
        self.assertTrue(f.controller.operate("bootstrap")["ok"])
        self.c=f.fresh_controller();self.fingerprint=f.current.fingerprint;f.events.clear()
        self.events=bind_graph(self,f,f.remote)

    def attest(self,**changes):
        return self.c.attest_current(**dict(dict(key_id=OLD_ID,fingerprint=self.fingerprint,evidence="d"*64),**changes))

    def test_selected_get_and_explicit_evidence_adopt_once_without_rotation_or_sql_request(self):
        f=self.f;before=f.store.status();gate=dict(f.gate);material=f.active.read_bytes()
        first=self.attest();self.assertFalse(first["already_managed"]);self.assertEqual(first["origin"],"adopted")
        self.assertEqual(first["operation_id"],gate["operation_id"]);self.assertEqual(first["evidence"],"d"*64)
        inventory=f.root.inventory();again=self.attest(evidence="e"*64)
        self.assertTrue(again["already_managed"]);self.assertEqual(again["evidence"],"d"*64);self.assertEqual(f.root.inventory(),inventory)
        self.assertEqual(f.remote.reads,2);self.assertEqual(f.remote.adds,0);self.assertEqual(f.gate,gate)
        self.assertEqual(f.active.read_bytes(),material);self.assertEqual(f.store.status(),before)
        with f.engine.begin() as connection:self.assertEqual(connection.execute(sa.select(sa.func.count()).select_from(requests)).scalar_one(),0)
        for absent in ("stop","blocked","exclusive","recreate-api"):self.assertNotIn(absent,f.events)
        for present in ("lock:lifecycle","lock:processing","lock:/run/invoice-importer/notification.lock","ready"):self.assertIn(present,f.events)
        self.assertEqual(self.events,["shared-admission","material-check","admission-closed"]*2)

    def test_expected_fingerprint_and_fixed_arguments_fail_before_remote_read(self):
        for change in (dict(fingerprint="f"*64),dict(key_id="not-a-key"),dict(key_id="00000000-0000-0000-0000-000000000000"),
                dict(evidence=""),dict(evidence="F"*64),dict(fingerprint="a"*63)):
            with self.subTest(change=change),self.assertRaises(ValueError):self.attest(**change)
        self.assertEqual(self.f.remote.reads,0);self.assertEqual(self.f.root.inventory()["keys"],{})

    def test_selected_key_must_match_material_dates_type_and_be_unique(self):
        original=copy.deepcopy(self.f.remote.records);record=original[0]
        variants=[[],[record,dict(record,key_id=NEW_ID)],[dict(record,key_id=NEW_ID)],
            [dict(record,fingerprint="f"*64)],[dict(record,expires_at=record["expires_at"]+1)],
            [dict(record,not_before=record["not_before"]-1)],[dict(record,type="Other")],[dict(record,usage="Sign")]]
        for records in variants:
            self.f.remote.records=records
            with self.subTest(records=records),self.assertRaisesRegex(GraphError,"key_mismatch"):self.attest()
            self.assertEqual(self.f.root.inventory()["keys"],{})
        self.assertEqual(self.f.remote.adds,0)

    def test_paused_wrong_boot_and_foreign_drain_never_adopt_or_clear_control(self):
        f=self.f;initial=dict(f.gate);drain=Path(self.c.host.DRAIN_FILE)
        for kind in ("paused","boot","drain"):
            f.gate.update(initial)
            if kind=="paused":f.gate["mode"]="paused"
            elif kind=="boot":f.gate["boot_id"]="88888888-8888-8888-8888-888888888888"
            else:drain.write_text("foreign-operator-pause")
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,"attestation_paused"):self.attest()
        self.assertEqual(drain.read_text(),"foreign-operator-pause");self.assertEqual(f.remote.reads,0)
        f.gate["mode"]="paused"
        with self.assertRaisesRegex(GraphError,"attestation_paused"):
            self.c.worker("attest-current",key_id=OLD_ID,fingerprint=self.fingerprint,evidence="d"*64)
        self.assertEqual(f.root.inventory()["keys"],{})

    def test_missing_or_changed_bootstrap_release_cannot_establish_ownership(self):
        f=self.f;path=f.root.directory/".bootstrap.json";raw=path.read_bytes();record=json.loads(raw)
        path.unlink()
        with self.assertRaisesRegex(GraphError,"attestation_unconfirmed"):self.attest()
        changed=dict(record,seal="f"*64);path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(GraphError,"attestation_unconfirmed"):self.attest()
        path.write_bytes(raw);f.gate["release_hash"]="e"*64
        with self.assertRaisesRegex(GraphError,"attestation_unconfirmed"):self.attest()
        self.assertEqual(f.remote.reads,0);self.assertEqual(f.root.inventory()["keys"],{})

    def test_request_arriving_during_get_prevents_inventory_write(self):
        f=self.f;original=f.remote.read;operation=str(uuid4())
        def concurrent_request():
            result=original();f.store.request(operation,"operator",f.store.status()["revision"],self.fingerprint);return result
        with patch.object(f.remote,"read",side_effect=concurrent_request):
            with self.assertRaisesRegex(GraphError,"attestation_changed"):self.attest()
        self.assertEqual(f.store.status()["active_operation"],operation);self.assertEqual(f.root.inventory()["keys"],{})
        self.assertEqual(f.remote.adds,0)
        with self.assertRaisesRegex(ValueError,"attestation_unavailable"):self.attest()
        self.assertEqual(f.remote.reads,1)

    def test_gate_change_during_get_is_rechecked_before_inventory(self):
        f=self.f;original=f.remote.read
        def changed_gate():
            result=original();f.gate["epoch"]+=1;return result
        with patch.object(f.remote,"read",side_effect=changed_gate):
            with self.assertRaisesRegex(GraphError,"attestation_changed"):self.attest()
        self.assertEqual(f.root.inventory()["keys"],{})

    def test_conflicting_managed_key_or_duplicate_fingerprint_is_not_overwritten(self):
        f=self.f;record=f.remote.records[0]
        for key,changed in ((OLD_ID,dict(record,fingerprint="f"*64)),(NEW_ID,dict(record,key_id=NEW_ID))):
            f.root._write("inventory.json",dict(version=1,scope_key=BINDING.scope,keys={}))
            f.root.adopt_existing(str(uuid4()),changed,evidence="a"*64);before=f.root.inventory()
            with self.subTest(key=key),self.assertRaisesRegex(GraphError,"inventory_conflict"):self.attest()
            self.assertEqual(f.root.inventory(),before)

    def test_lost_inventory_response_reconciles_original_evidence_without_remote_mutation(self):
        f=self.f;original=f.root.adopt_existing
        def lost_response(*args,**kwargs):
            original(*args,**kwargs);raise SystemExit("synthetic lost local attestation response")
        with patch.object(f.root,"adopt_existing",side_effect=lost_response),self.assertRaises(SystemExit):self.attest()
        before=f.root.inventory();result=f.fresh_controller().attest_current(OLD_ID,self.fingerprint,"e"*64)
        self.assertTrue(result["already_managed"]);self.assertEqual(result["evidence"],"d"*64)
        self.assertEqual(f.root.inventory(),before);self.assertEqual(f.remote.adds,0)


class CompletedOwnershipTests(unittest.TestCase):
    def test_completed_created_key_keeps_original_provenance_after_old_cleanup(self):
        m=maintenance_fixture.MaintenanceTests();m.setUp();self.addCleanup(m.doCleanups);f=m.f
        self.assertEqual(m.resume()["cleanup"]["phase"],"completed")
        bind_graph(self,f,m.graph);before=f.root.inventory();created=before["keys"][NEW_ID]
        self.assertEqual(created["origin"],"created");self.assertFalse((f.root.directory/(f.operation+".old.pem")).exists())
        result=f.fresh_controller().attest_current(NEW_ID,f.current.fingerprint,"e"*64)
        self.assertTrue(result["already_managed"]);self.assertEqual(f.root.inventory(),before)
        self.assertEqual(result["evidence"],created["evidence"]);self.assertEqual(m.graph.removes,1);self.assertEqual(f.remote.adds,1)


class AttestationBoundaryTests(unittest.TestCase):
    def test_worker_accepts_only_fixed_no_operation_request(self):
        value=dict(command="attest-current",operation_id=None,key_id=OLD_ID,fingerprint="a"*64,evidence="d"*64)
        self.assertEqual(worker.request(json.dumps(value).encode()),value)
        for changes in (dict(operation_id=str(uuid4())),dict(key_id="bad"),dict(fingerprint=""),dict(evidence=None),dict(path="/foreign")):
            with self.subTest(changes=changes),self.assertRaises(GraphError):worker.request(json.dumps(dict(value,**changes)).encode())

    def test_cli_requires_all_attestation_arguments_and_rejects_them_on_other_modes(self):
        cases=[["attest-current"],["attest-current","--key-id",OLD_ID],
            ["attest-current","--key-id",OLD_ID,"--fingerprint","a"*64],["resume","--evidence","d"*64]]
        for args in cases:
            with self.subTest(args=args),patch.object(host.sys,"argv",["run-rotation.py",*args]),patch.object(host,"Controller") as controller,redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:host.main()
                self.assertEqual(error.exception.code,2);controller.assert_not_called()
