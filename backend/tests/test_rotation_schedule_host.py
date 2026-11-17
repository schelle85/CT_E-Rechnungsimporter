"""Fixed host calendar/publisher and flow. systemd, clocks and Linux boundaries are explicit doubles."""
from contextlib import contextmanager
import configparser
import importlib.util
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import rotation_status
from app.rotation_schema008 import head,requests
import test_rotation_host_flow as flow_fixture
from test_rotation_host import host as controller_module
from rotation_test_support import NOW

directory=Path(__file__).parent.parent/"operator"
if not (directory/"rotation-schedule-host.py").exists():directory=Path(__file__).parents[2]/"deploy"
spec=importlib.util.spec_from_file_location("rotation_schedule_host_test",directory/"rotation-schedule-host.py")
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
PROFILE="/etc/invoice-importer/rotation-host.json"


def units(now=NOW):
    result={host.START:dict(Id=host.START,LoadState="loaded",ActiveState="active")}
    for name in host.TIMERS:
        result[host.TIMERS[name]]=dict(Id=host.TIMERS[name],LoadState="loaded",ActiveState="active",UnitFileState="enabled",
            TimersCalendar="{ OnCalendar="+host.CALENDARS[name]+" ; next_elapse=@0 ; }",Triggers=host.SERVICES[name],
            Persistent="yes",RandomizedDelayUSec="0",AccuracyUSec="1s",NextElapseUSecRealtime="@"+str(host.calendar(now)[1]))
        command="/usr/bin/python3 -I -B /etc/invoice-importer/run-rotation.py "+name+" --profile "+PROFILE
        result[host.SERVICES[name]]=dict(Id=host.SERVICES[name],LoadState="loaded",User="root",UMask="0077",KillMode="control-group",
            ExecStart="{ path=/usr/bin/python3 ; argv[]="+command+" ; ignore_errors=no ; }")
    return result


class TimerTests(unittest.TestCase):
    def test_fixed_templates_and_exact_active_calendar_command_profile_are_required(self):
        for name in host.TIMERS:
            timer=configparser.ConfigParser();timer.read(directory/(host.TIMERS[name]+".example"))
            service=configparser.ConfigParser();service.read(directory/(host.SERVICES[name]+".example"))
            self.assertEqual(timer["Timer"]["OnCalendar"],host.CALENDARS[name]);self.assertEqual(timer["Timer"]["Unit"],host.SERVICES[name])
            self.assertEqual(timer["Timer"]["Persistent"],"true");self.assertEqual(service["Service"]["KillMode"],"control-group")
            self.assertEqual(service["Service"]["ExecStart"],"/usr/bin/python3 -I -B /etc/invoice-importer/run-rotation.py "+name+" --profile "+PROFILE)
        c=SimpleNamespace(profile_path=PROFILE,until=time.monotonic()+10)
        with patch.object(host,"systemd",return_value=units()),patch.object(host.time,"time",return_value=NOW):
            self.assertEqual(host.timer_status(c),dict(daily=True,opportunity=True,next_check_at=host.calendar(NOW)[1]))
        for target,changed in ((host.TIMERS["daily"],dict(ActiveState="inactive")),(host.TIMERS["daily"],dict(UnitFileState="disabled")),
                (host.TIMERS["daily"],dict(TimersCalendar="{ OnCalendar=*-*-* 04:00:00 Europe/Berlin ; }")),
                (host.TIMERS["daily"],dict(Triggers="foreign.service")),(host.TIMERS["daily"],dict(Persistent="no")),
                (host.SERVICES["daily"],dict(ExecStart="{ argv[]=/usr/bin/other ; }")),(host.SERVICES["daily"],dict(User="10001")),
                (host.SERVICES["daily"],dict(KillMode="process"))):
            altered=units();altered[target].update(changed)
            with patch.object(host,"systemd",return_value=altered),patch.object(host.time,"time",return_value=NOW):
                self.assertFalse(host.timer_status(c)["daily"]);self.assertIsNone(host.timer_status(c)["next_check_at"])
        with patch.object(host,"systemd",return_value=units()):
            self.assertFalse(host.timer_status(SimpleNamespace(profile_path="/different/profile.json",until=c.until))["daily"])

    def test_systemd_parsing_deadline_output_limit_and_next_time_never_invent_status(self):
        text="\n\n".join("\n".join(k+"="+v for k,v in row.items()) for row in units().values())
        self.assertEqual(host.parse_units(text),units())
        for malformed in (text+"\n\nId="+host.START,"Id="+host.START+"\nId="+host.START):
            with self.assertRaises(ValueError):host.parse_units(malformed)
        def capture(args,**kwargs):
            self.assertEqual(args[0:2],["/usr/bin/systemctl","show"]);self.assertIn("--timestamp=unix",args)
            self.assertLessEqual(kwargs["timeout"],3);kwargs["stdout"].write(text.encode());return SimpleNamespace(returncode=0)
        with patch.object(host.subprocess,"run",side_effect=capture):self.assertEqual(host.systemd(time.monotonic()+10),units())
        with patch.object(host.subprocess,"run",side_effect=AssertionError("deadline must precede spawn")):
            with self.assertRaises(ValueError):host.systemd(time.monotonic()-1)
        def too_much(*args,**kwargs):kwargs["stdout"].write(b"x"*32769);return SimpleNamespace(returncode=0)
        with patch.object(host.subprocess,"run",side_effect=too_much):
            with self.assertRaises(ValueError):host.systemd(time.monotonic()+10)
        c=SimpleNamespace(profile_path=PROFILE,until=time.monotonic()+10);altered=units();altered[host.TIMERS["daily"]]["NextElapseUSecRealtime"]="@"+str(NOW+1)
        with patch.object(host,"systemd",return_value=altered),patch.object(host.time,"time",return_value=NOW):
            value=host.timer_status(c);self.assertTrue(value["daily"]);self.assertIsNone(value["next_check_at"])


class HostScheduleTests(unittest.TestCase):
    def setUp(self):
        self.f=flow_fixture.IntegratedHostTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.c=self.f.controller;self.c.profile_path=PROFILE
        self.f.stack.enter_context(patch.object(host,"systemd",return_value={}))

    def public(self):return json.loads((self.c.gate_directory/"rotation-status.json").read_text())

    def test_opportunity_processes_manual_request_when_automatic_disabled_and_reuses_it(self):
        self.assertFalse(self.f.store.status()["enabled"])
        result=host.run(self.c,"opportunity");self.assertTrue(result["ok"]);self.assertTrue(result["status_recorded"])
        public=self.public();self.assertEqual(public["operation"]["operation_id"],self.f.operation)
        self.assertEqual(public["last_attempt"]["operation_id"],self.f.operation);self.assertEqual(public["last_renewal"]["operation_id"],self.f.operation)
        self.assertEqual(self.f.remote.adds,1);self.assertIsNone(public["last_successful_daily_check_at"])
        with patch.object(rotation_status,"boot_id",return_value=self.f.current_boot):rotation_status.validate(public,self.f.access,NOW)
        self.assertTrue(host.run(self.f.fresh_controller(),"opportunity")["ok"]);self.assertEqual(self.f.remote.adds,1)

    def test_paused_or_foreign_drain_publishes_without_graph_or_clearing_pause(self):
        self.f.gate["mode"]="paused";self.assertTrue(host.run(self.c,"opportunity")["deferred"])
        self.f.gate["mode"]="allowed";drain=Path(self.c.host.DRAIN_FILE);drain.write_text("foreign-pause")
        self.assertTrue(host.run(self.c,"daily")["deferred"]);self.assertEqual(drain.read_text(),"foreign-pause")
        self.assertEqual(self.f.remote.adds,0);self.assertNotIn("stop",self.f.events)
        self.assertIsNone(self.public()["last_attempt"])

    def test_publisher_uses_public_readback_actual_boot_and_exact_two_hour_overdue_boundary(self):
        due=host.calendar(NOW)[0]
        for now,expected in ((due+7199,False),(due+7200,True)):
            with patch.object(host.time,"time",return_value=now):self.assertTrue(host.publish(self.c))
            value=self.public();self.assertEqual(value["check_overdue"],expected);self.assertEqual(value["check_due_at"],due)
            self.assertEqual(set(value),rotation_status.FIELDS)
            with patch.object(rotation_status,"boot_id",return_value=self.f.current_boot):rotation_status.validate(value,self.f.access,now)
            for private in ("pem_hash","consumer_id","PRIVATE KEY","container_id"):self.assertNotIn(private,json.dumps(value))
        previous=(self.c.gate_directory/"rotation-status.json").read_bytes()
        with patch.object(self.c.model,"boot_id",side_effect=[self.f.current_boot,"88888888-8888-8888-8888-888888888888"]):
            with self.assertRaisesRegex(ValueError,"boot_changed"):host.publish(self.c)
        self.assertEqual((self.c.gate_directory/"rotation-status.json").read_bytes(),previous)
        with patch.object(self.c,"worker",return_value=dict(ok=True,binding={},**{name:None for name in host.PUBLIC_FIELDS})):
            with self.assertRaisesRegex(ValueError,"status_unconfirmed"):host.publish(self.c)

    def test_due_check_uses_existing_lifecycle_order_but_repeated_opportunity_does_no_check(self):
        self.f.gate["mode"]="allowed";events=[];original=self.c.worker
        def worker(command,*args,**kwargs):
            events.append(command)
            if command=="scheduled-check":
                self.assertIn("lock:lifecycle",self.f.events);self.assertIn("lock:processing",self.f.events)
                self.assertIn("lock:/run/invoice-importer/notification.lock",self.f.events);self.assertIn("ready",self.f.events)
                return dict(ok=True)
            return original(command,*args,**kwargs)
        with patch.object(self.c,"worker",side_effect=worker),patch.object(self.c,"operate",return_value=dict(ok=True)):
            self.assertTrue(host.run(self.c,"daily")["ok"])
        self.assertEqual(events.count("scheduled-check"),1)
        from app.rotation_schedule import ScheduleJournal
        ScheduleJournal(self.f.root).save(last_check=dict(slot=host.calendar(NOW)[0],at=NOW,ok=True,code=None),last_successful_daily_check_at=NOW)
        events.clear()
        with patch.object(host,"systemd",return_value=units()),patch.object(self.c,"worker",side_effect=worker),patch.object(self.c,"operate",return_value=dict(ok=True)):
            self.assertTrue(host.run(self.c,"opportunity")["ok"])
        self.assertNotIn("scheduled-check",events);self.assertEqual(self.f.remote.adds,0)

    def test_automatic_request_under_one_hour_defers_without_register_or_activation(self):
        with self.f.engine.begin() as c:c.execute(requests.delete());c.execute(head.update().values(active_operation=None,revision=0,enabled=True))
        self.f.store.request(self.f.operation,"system",0,self.f.current.fingerprint,trigger="automatic")
        with patch.object(host.time,"time",return_value=self.f.current.expires_at-3599):result=host.run(self.c,"opportunity")
        self.assertFalse(result["ok"]);self.assertEqual(result["code"],"rotation_automatic_window_closed")
        self.assertTrue(result["status_recorded"]);self.assertEqual(self.f.remote.adds,0);self.assertNotIn("stop",self.f.events)

    def test_busy_writer_does_not_start_worker_or_publish_and_guard_requires_actual_writer(self):
        @contextmanager
        def busy():raise ValueError("graph_gate_writer_busy");yield
        with patch.object(self.c.writer,"session",side_effect=busy),patch.object(self.c,"worker",side_effect=AssertionError("must not spawn")):
            result=host.run(self.c,"daily");self.assertTrue(result["deferred"]);self.assertFalse(result["status_recorded"])
        with patch.object(self.c.writer,"_require",side_effect=ValueError("graph_gate_lock_required")):
            with self.assertRaisesRegex(ValueError,"lock_required"):self.c.operate("resume",locked=True)

    def test_committed_operation_needs_current_gate_boot_seal_and_material_in_public_projection(self):
        self.assertTrue(self.c.operate("run")["ok"]);self.assertTrue(host.publish(self.c))
        self.assertIsNotNone(self.public()["operation"])
        self.f.gate["mode"]="blocked";self.assertTrue(host.publish(self.c))
        self.assertIsNone(self.public()["operation"]);self.assertIsNotNone(self.public()["last_renewal"])
        from app.graph_access import GraphAccessError
        gate=SimpleNamespace(read=lambda:dict(self.f.gate),_bound=lambda _:(_ for _ in ()).throw(GraphAccessError("graph_access_binding_changed")))
        with patch("app.graph_access.AccessGate",return_value=gate):
            with self.assertRaises(GraphAccessError):host.publish(self.c)


class ActivationWindowTests(unittest.TestCase):
    def test_automatic_horizon_is_rechecked_after_candidate_probe_before_actual_file_activation(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"current.pem";path.write_bytes(b"synthetic old bytes")
            c=controller_module.Controller.__new__(controller_module.Controller);c.automatic_operation="operation";c.processing=dict(graph_credential=str(path))
            c.host=SimpleNamespace(protected=lambda p:Path(p));c.model=SimpleNamespace(boot_id=lambda:"boot")
            now=[NOW];state=dict(phase="prepared",boot_id="boot",paused=False,target="new",old=dict(expires_at=NOW+3601),new=dict(pem_hash="synthetic"))
            c.candidate_gate=lambda *a:None;c.material=lambda *a,**k:b"synthetic new bytes"
            def probe(*a):now[0]+=3;return {}
            c.probe=probe;c.worker=lambda command,*a,**k:dict(host=dict(state,phase="activation_started")) if command=="activation-started" else {}
            c.activate=lambda *a:self.fail("new material must not be activated below the automatic horizon")
            with patch.object(controller_module.time,"time",side_effect=lambda:now[0]):
                with self.assertRaisesRegex(ValueError,"automatic_window_closed"):c.switch("operation",state,"resume",{}, {})
