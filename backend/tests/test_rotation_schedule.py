"""Real journal/SQL/certificate/calendar checks; explicit Graph, gate and POSIX doubles."""
from contextlib import contextmanager
from datetime import datetime
import json
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
from app import rotation_schedule as schedule,rotation_worker as worker
from app.graph import GraphError
from app.notification_model import BERLIN,graph_scope
from app.notification_schema007 import settings
from app.rotation_schema008 import head,requests
from rotation_test_support import NOW,CONFIG,BINDING,material
import test_rotation_worker as fixture
import test_rotation_host_flow as flow_fixture


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorkerTests();self.f.setUp();self.addCleanup(self.f.doCleanups);f=self.f
        with f.engine.begin() as c:
            c.execute(requests.delete());c.execute(head.update().values(active_operation=None,revision=0,enabled=True,blocked_fingerprint=None))
            c.execute(settings.insert().values(singleton=1,version=0,scope_key=graph_scope(CONFIG.tenant_id,CONFIG.client_id,CONFIG.mailbox),actor="system",updated_at=NOW))
        self.current=material(days=29);self.journal=schedule.ScheduleJournal(f.root);self.events=[];self.now=[NOW]
        f.stack.enter_context(patch.object(schedule.time,"time",side_effect=lambda:self.now[0]))
        self.gate=SimpleNamespace(read=lambda:dict(mode="allowed"),_bound=lambda _:None,_material=lambda *a:None)
        f.stack.enter_context(patch("app.graph_access.AccessGate",return_value=self.gate))
        @contextmanager
        def admission(config,current,*,expected_instance):
            self.assertEqual(expected_instance,BINDING.instance_id);self.events.append("admit")
            yield SimpleNamespace(check=lambda *a:self.events.append("permit"))
        def probe():self.events.append("fresh-get");return {"mailbox_access":"ok"}
        self.probe=probe
        @contextmanager
        def client(config,current):yield SimpleNamespace(probe=lambda:self.probe())
        f.stack.enter_context(patch.object(schedule,"graph_operation",side_effect=admission))
        f.stack.enter_context(patch.object(schedule,"certificate_client",side_effect=client))

    def check(self):
        return self.journal.check(self.f.store,self.f.access,self.current,time.monotonic()+65,lambda:worker.monitor_state(self.f.engine,CONFIG))

    def count(self):
        with self.f.engine.connect() as c:return c.execute(sa.select(sa.func.count()).select_from(requests)).scalar_one()

    def test_daily_probe_records_real_monitor_and_original_automatic_request_only_once(self):
        result=self.check();operation=result["operation_id"];row=self.f.store.read(operation)
        self.assertEqual(row["actor"],"system");self.assertEqual(row["trigger_kind"],"automatic");self.assertEqual(self.count(),1)
        saved=json.loads((self.f.root.directory/(".automatic-"+self.current.fingerprint+".json")).read_text())
        self.assertEqual(saved["operation_id"],operation);self.assertEqual(saved["expected_revision"],row["expected_revision"])
        self.assertEqual(worker.monitor_state(self.f.engine,CONFIG)["proof"]["fingerprint"],self.current.fingerprint)
        self.assertEqual(self.journal.state()["last_successful_daily_check_at"],NOW)
        events=list(self.events);again=self.check();self.assertFalse(again["due"]);self.assertEqual(again["operation_id"],operation)
        self.assertEqual(self.events,events);self.assertEqual(self.count(),1);self.assertEqual(self.f.remote.adds,0)

    def test_lost_sql_response_reconciles_original_even_after_disable_without_new_uuid(self):
        original=self.f.store.request
        def lost(*args,**kwargs):original(*args,**kwargs);raise GraphError("synthetic_sql_reply_lost")
        with patch.object(self.f.store,"request",side_effect=lost):self.assertTrue(self.check()["check_failed"])
        pending=json.loads((self.f.root.directory/(".automatic-"+self.current.fingerprint+".json")).read_text())
        self.f.store.configure(self.f.store.status()["revision"],False,"operator")
        with patch.object(schedule,"uuid4",side_effect=AssertionError("must retain original")):
            self.assertEqual(self.check()["operation_id"],pending["operation_id"])
        self.assertEqual(self.count(),1);self.assertEqual(self.events.count("fresh-get"),1)

    def test_crash_after_durable_intent_before_sql_reuses_original_and_blocks_revision_replacement(self):
        with patch.object(self.f.store,"request",side_effect=SystemExit("synthetic pre-SQL interruption")):
            with self.assertRaises(SystemExit):self.check()
        self.assertEqual(self.count(),0);pending=json.loads((self.f.root.directory/(".automatic-"+self.current.fingerprint+".json")).read_text())
        self.assertTrue(self.journal.pending(self.f.store,self.current))
        with patch.object(schedule,"uuid4",side_effect=AssertionError("no replacement")):
            replay=self.check();self.assertEqual(replay["operation_id"],pending["operation_id"])
        self.assertEqual(self.count(),1);self.assertEqual(self.events.count("fresh-get"),1)
        self.assertFalse(self.journal.pending(self.f.store,self.current))
        # A separate synthetic generation with a changed head cannot silently obtain another UUID.
        with self.f.engine.begin() as c:c.execute(requests.delete());c.execute(head.update().values(active_operation=None,revision=20))
        with patch.object(schedule,"uuid4",side_effect=AssertionError("no replacement")):
            self.assertIsNone(self.check()["operation_id"])
        self.assertEqual(self.count(),0);self.assertEqual(json.loads((self.f.root.directory/(".automatic-"+self.current.fingerprint+".json")).read_text()),pending)

    def test_manual_request_wins_between_automatic_intent_fsync_and_sql_without_duplicate(self):
        original=self.f.root._write;manual=str(uuid4())
        def raced(name,value):
            original(name,value)
            if name.startswith(".automatic-"):
                self.f.store.request(manual,"operator",self.f.store.status()["revision"],self.current.fingerprint)
        with patch.object(self.f.root,"_write",side_effect=raced):self.assertTrue(self.check()["check_failed"])
        self.assertEqual(self.f.store.status()["active_operation"],manual);self.assertEqual(self.count(),1)
        with patch.object(schedule,"uuid4",side_effect=AssertionError("must not replace the original")):
            self.check()
        self.assertEqual(self.count(),1);self.assertEqual(self.events.count("fresh-get"),1)

    def test_changed_automatic_actor_and_extra_worker_parameters_fail_closed(self):
        operation=str(uuid4());manual=self.f.store.request(operation,"operator",0,self.current.fingerprint)
        self.f.root._write(".automatic-"+self.current.fingerprint+".json",dict(version=1,operation_id=operation,
            scope_key=BINDING.scope,expected_revision=manual["expected_revision"],old_fingerprint=self.current.fingerprint))
        with self.assertRaisesRegex(GraphError,"rotation_request_conflict"):
            self.journal.automatic(self.f.store,self.current,NOW)
        for command in ("scheduled-check","overview"):
            self.assertEqual(worker.request(json.dumps(dict(command=command,operation_id=None)).encode())["command"],command)
            for value in (dict(command=command,operation_id=operation),dict(command=command,operation_id=None,enabled=True)):
                with self.assertRaises(GraphError):worker.request(json.dumps(value).encode())

    def test_manual_winner_unknown_rejection_disable_and_blocked_generation_never_spawn_another_request(self):
        manual=self.f.store.request(str(uuid4()),"operator",0,self.current.fingerprint)
        self.assertIsNone(self.check()["operation_id"]);self.assertEqual(self.count(),1)
        row=manual
        for state in ("prepared","registration_started","registration_unknown"):
            row=self.f.store.project_core(row["operation_id"],row["revision"],state)
        self.now[0]+=86400;self.assertIsNone(self.check()["operation_id"]);self.assertEqual(self.count(),1)
        for changes in (dict(state="registration_rejected"),):
            with self.f.engine.begin() as c:c.execute(requests.update().values(**changes))
        self.now[0]+=86400;self.assertIsNone(self.check()["operation_id"]);self.assertEqual(self.count(),1)
        with self.f.engine.begin() as c:c.execute(requests.delete());c.execute(head.update().values(active_operation=None,blocked_fingerprint=self.current.fingerprint))
        self.now[0]+=86400;self.assertIsNone(self.check()["operation_id"]);self.assertEqual(self.count(),0)
        with self.f.engine.begin() as c:c.execute(head.update().values(blocked_fingerprint=None,enabled=False))
        self.now[0]+=86400;self.assertIsNone(self.check()["operation_id"]);self.assertEqual(self.count(),0)

    def test_generation_boundaries_expiry_and_graph_pause_do_not_create_automatic_requests(self):
        for days,shift in ((31,0),(1,86400-3599),(1,86400)):
            self.current=material(days=days);self.now[0]=NOW+shift
            # Each case is a separate synthetic calendar observation, not a native clock change.
            self.f.root._write(".schedule.json",dict(version=1,scope_key=BINDING.scope,last_check=None,last_successful_daily_check_at=None,last_attempt=None,last_renewal=None))
            self.check();self.assertEqual(self.count(),0)
        events=list(self.events);self.gate.read=lambda:dict(mode="paused")
        self.assertEqual(self.check()["deferred"],"graph_paused");self.assertEqual(self.events,events)

    def test_failed_interrupted_and_slow_close_checks_are_not_repeated_in_the_same_day(self):
        def failed():self.events.append("failed-get");raise GraphError("synthetic_probe_failed")
        self.probe=failed;self.assertTrue(self.check()["check_failed"]);self.assertFalse(self.check()["due"])
        self.assertIsNone(self.journal.state()["last_successful_daily_check_at"]);self.assertEqual(self.events.count("failed-get"),1);self.assertEqual(self.count(),0)
        self.now[0]+=86400
        @contextmanager
        def slow(config,current):
            yield SimpleNamespace(probe=lambda:{"mailbox_access":"ok"});self.now[0]+=61
        with patch.object(schedule,"certificate_client",side_effect=slow):self.assertTrue(self.check()["check_failed"])
        self.assertIsNone(self.journal.state()["last_successful_daily_check_at"]);self.assertEqual(self.count(),0)
        self.now[0]+=86400
        self.probe=lambda:(_ for _ in ()).throw(SystemExit("synthetic worker interruption"))
        with self.assertRaises(SystemExit):self.check()
        self.assertEqual(self.journal.state()["last_check"]["code"],"rotation_check_interrupted");self.assertFalse(self.check()["due"])


class CalendarTests(unittest.TestCase):
    def test_berlin_dst_and_missed_days_coalesce_to_one_latest_0335_slot(self):
        stamp=lambda text:int(datetime.fromisoformat(text).replace(tzinfo=BERLIN).timestamp())
        for date in ("2026-03-29","2026-10-25","2026-11-17"):
            due=stamp(date+"T03:35:00");self.assertEqual(schedule.due_slot(due),due)
            self.assertLess(schedule.due_slot(due-1),due);self.assertEqual(schedule.due_slot(stamp(date+"T23:59:59")),due)
        spring=stamp("2026-03-29T03:35:00")-stamp("2026-03-28T03:35:00")
        autumn=stamp("2026-10-25T03:35:00")-stamp("2026-10-24T03:35:00")
        self.assertEqual((spring,autumn),(23*3600,25*3600))

    def test_renewal_and_attempt_keep_original_times_across_resume_and_cleanup(self):
        f=flow_fixture.IntegratedHostTests();f.setUp();self.addCleanup(f.doCleanups)
        self.assertTrue(f.controller.operate("run")["ok"])
        journal=schedule.ScheduleJournal(f.root);initial=journal.state();self.assertEqual(initial["last_attempt"]["operation_id"],f.operation)
        self.assertEqual(initial["last_renewal"]["fingerprint"],f.root.material(f.operation).fingerprint)
        with patch.object(worker.time,"time",return_value=NOW+1):self.assertTrue(f.fresh_controller().operate("resume")["ok"])
        self.assertEqual(journal.state(),initial)
        public=schedule.overview(f.store,worker.AdoptionJournal(f.root,f.access),f.access,f.root.material(f.operation))
        self.assertEqual(public["last_renewal"],initial["last_renewal"]);self.assertEqual(public["last_attempt"]["at"],initial["last_attempt"]["at"])
        self.assertEqual(public["operation"]["cleanup_phase"],"planned")
        self.assertNotIn("pem_hash",json.dumps(public));self.assertNotIn("consumer_id",json.dumps(public))
