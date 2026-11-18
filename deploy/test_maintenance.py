"""AP10 targeted orchestration tests. Native actions replaced by explicit fakes."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('maintenance',Path(__file__).with_name('run-maintenance.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def stamp(iso): return datetime.fromisoformat(iso).timestamp()
SUNDAY=stamp('2026-11-22T03:00:00+01:00')

class Host:
    def __init__(self,*,reboot=False):
        self.value=None;self.drain=None;self.calls=[];self.cancelled=False;self.profile_hash='hash'
        self.reboot=reboot;self.boot_id='before';self.fail=None;self.mutator=None;self.guarded=False
    def read(self): return deepcopy(self.value)
    def save(self,value): self.value=deepcopy(value)
    def archive(self,value): self.calls.append('archive')
    def preflight(self): self.calls.append('preflight')
    def marker(self): return self.drain
    def boot(self): return self.boot_id
    def pause(self,value):
        if self.drain not in (None,value['token']): raise m.Refused('operator_pause_preserved')
        self.drain=value['token'];self.calls.append('pause')
    def unpause(self,value):
        if self.drain!=value['token']: raise m.Refused('pause_owner_changed')
        self.drain=None;self.calls.append('unpause')
    def confirm_pause(self,value):
        if self.drain!=value['token']: raise m.Refused('pause_owner_changed')
    @contextmanager
    def guards(self):
        assert not self.guarded;self.guarded=True;self.calls.append('guard')
        try: yield
        finally:self.guarded=False;self.calls.append('unlock')
    def facts(self):
        assert self.guarded
        if self.fail=='facts': raise m.Refused('graph_not_confirmed')
        return dict(containers={k:dict(id=k,image=k) for k in ('db','api','nginx')},graph=dict(fingerprint='new'),boot_id=self.boot_id)
    def packages(self,*_): return dict(audit_empty=True,inventory_sha256='unchanged')
    def stop(self): assert self.guarded;self.calls.append('stop')
    def start(self): assert self.guarded;self.calls.append('start')
    def parent_start(self): assert not self.guarded;self.calls.append('parent_start')
    def reboot_required(self): return self.reboot
    def refresh_status(self): return dict(fresh=True)
    def command(self,args,timeout=15,*,apt=False):
        assert self.guarded
        self.calls.append(tuple(args))
        if self.mutator:self.mutator(self,args)
        if apt:return dict(exit=100 if self.fail in args else 0,output_sha256='digest',output_bytes=0)
        return ''


class MaintenanceTests(unittest.TestCase):
    def run_at(self,h,mode='scheduled',clock=None): return m.execute(h,mode,clock=clock or (lambda:SUNDAY))
    def test_exact_berlin_windows_and_dst(self):
        for day,offset in [('2026-03-29','+02:00'),('2026-10-25','+01:00'),('2026-11-22','+01:00')]:
            self.assertTrue(m.window(stamp(day+'T03:00:00'+offset)))
            self.assertFalse(m.window(stamp(day+'T03:15:00'+offset)))
            self.assertTrue(m.window(stamp(day+'T04:29:59'+offset),reboot=True))
            self.assertFalse(m.window(stamp(day+'T04:30:00'+offset),reboot=True))
        self.assertFalse(m.window(stamp('2026-11-18T10:00:00+01:00')))
    def test_offslot_never_pauses_or_calls_apt(self):
        h=Host();self.assertTrue(self.run_at(h,clock=lambda:SUNDAY+86400)['skipped']);self.assertEqual(h.calls,[])
    def test_healthy_run_no_reboot_without_native_marker(self):
        h=Host();self.assertEqual(self.run_at(h)['phase'],'completed');self.assertIsNone(h.drain)
        apt=[c for c in h.calls if isinstance(c,tuple)];self.assertEqual(len(apt),2)
        self.assertIn('--no-remove',apt[-1]);self.assertNotIn('dist-upgrade',apt[-1]);self.assertNotIn('autoremove',apt[-1])
        self.assertLess(h.calls.index('stop'),h.calls.index(apt[0]))
    def test_operator_pause_and_unconfirmed_graph_never_update(self):
        h=Host();h.drain='operator'
        with self.assertRaises(m.Refused):self.run_at(h)
        self.assertEqual(h.drain,'operator')
        h=Host();h.fail='facts'
        with self.assertRaises(m.Refused):self.run_at(h)
        self.assertFalse(any(isinstance(c,tuple) for c in h.calls))
    def test_apt_failure_keeps_pause_and_never_reboots(self):
        for command in ('update','upgrade'):
            h=Host(reboot=True);h.fail=command
            with self.assertRaises(m.Refused):self.run_at(h)
            self.assertEqual(h.value['phase'],'failed');self.assertIsNotNone(h.drain)
            self.assertFalse(h.value['apt_in_progress'])
            self.assertFalse(any(isinstance(c,tuple) and 'reboot' in c for c in h.calls))
    def test_need_reboot_stops_again_then_requires_different_boot(self):
        h=Host(reboot=True);self.assertTrue(self.run_at(h)['verification_pending'])
        self.assertEqual(h.calls.count('stop'),2);self.assertEqual(h.value['phase'],'awaiting_reboot')
        before=len([c for c in h.calls if isinstance(c,tuple)])
        with self.assertRaisesRegex(m.Refused,'reboot_not_observed'):self.run_at(h,'recover')
        h.boot_id='after';self.assertEqual(self.run_at(h,'recover')['phase'],'completed')
        self.assertEqual(len([c for c in h.calls if isinstance(c,tuple)]),before)
    def test_long_apt_cannot_authorize_late_reboot(self):
        h=Host(reboot=True);now=[SUNDAY]
        h.mutator=lambda _,args:now.__setitem__(0,SUNDAY+5400) if 'upgrade' in args else None
        with self.assertRaisesRegex(m.Refused,'reboot_window_closed'):self.run_at(h,clock=lambda:now[0])
        self.assertFalse(any(isinstance(c,tuple) and 'reboot' in c for c in h.calls))
    def test_boot_guard_and_unknown_transaction_do_not_replay(self):
        h=Host();self.run_at(h);h.value.update(phase='apt_upgrade',apt_in_progress=True);h.drain=None
        self.assertTrue(self.run_at(h,'boot-guard')['guarded']);count=len(h.calls)
        with self.assertRaisesRegex(m.Refused,'apt_outcome_unconfirmed'):self.run_at(h,'recover')
        self.assertFalse(any(isinstance(c,tuple) for c in h.calls[count:]))
    def test_pause_changed_during_postchecks_is_never_removed(self):
        h=Host();h.mutator=lambda host,args:setattr(host,'drain','operator') if 'upgrade' in args else None
        with self.assertRaisesRegex(m.Refused,'pause_owner_changed'):self.run_at(h)
        self.assertEqual(h.drain,'operator')
    def test_new_operator_drain_prevents_next_apt_step(self):
        h=Host(reboot=True);h.mutator=lambda host,args:setattr(host,'drain','operator') if 'update' in args else None
        with self.assertRaisesRegex(m.Refused,'pause_owner_changed'):self.run_at(h)
        commands=[c for c in h.calls if isinstance(c,tuple)]
        self.assertEqual(len(commands),1);self.assertIn('update',commands[0]);self.assertEqual(h.drain,'operator')
    def test_committed_overlap_allowed_unknown_or_unbound_refused(self):
        binding={'scope':'bound'};gate=dict(binding,mode='allowed',boot_id='boot',grants=[],operation_id='op',release_hash='seal',fingerprint='new')
        status=dict(ok=True,binding=binding,head=dict(active_operation='op'),host=dict(phase='committed',paused=False,seal='seal',target='new',new={'pem':'hash'}),current={'pem':'hash'},cleanup=dict(phase='planned'))
        self.assertEqual(m.stable_rotation(status,gate,binding,'boot')['fingerprint'],'new')
        for phase in ('prepared','adopting','proof_unknown'):
            altered=deepcopy(status);altered['host']['phase']=phase
            with self.assertRaises(m.Refused):m.stable_rotation(altered,gate,binding,'boot')
        status['head']['active_operation']=None
        with self.assertRaises(m.Refused):m.stable_rotation(status,gate,binding,'boot')
        status['closed_confirmed']=True;self.assertIsNone(m.stable_rotation(status,gate,binding,'boot')['operation_id'])

class DrainOwnershipTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('runtime',Path(__file__).with_name('host-runtime.py'))
        self.runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.runtime)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'draining';self.path.write_bytes(b'original')
        @contextmanager
        def lock(path,**_): yield path!=getattr(self,'busy',None)
        self.host=SimpleNamespace(DRAIN_FILE=str(self.path),PROCESSING_LOCK='processing',
            host_lock=lock,protected=Path,controlled_directory=Path,command=lambda *_:'',
            draining=lambda:self.path.exists())
        self.sync=patch.object(self.runtime,'sync_directory',lambda _:None);self.sync.start();self.addCleanup(self.sync.stop)

    def test_service_stop_preserves_owner_and_busy_drain_remains_bounded(self):
        self.runtime.drain(self.host,time.monotonic()+45,preserve_existing=True)
        self.assertEqual(self.path.read_bytes(),b'original')
        self.busy=self.runtime.LIFECYCLE_LOCK
        with self.assertRaisesRegex(ValueError,'host_drain_busy'):
            self.runtime.drain(self.host,time.monotonic()+45,preserve_existing=True)
        self.assertEqual(self.path.read_bytes(),b'original')

    def test_new_explicit_drain_changes_epoch_during_start(self):
        def ready(*_):
            self.runtime.drain(self.host,time.monotonic()+45)  # Default is a NEW operator request.
        item=dict(id='same',state=dict(Running=True,Health=dict(Status='healthy')))
        with patch.object(self.runtime,'inspect_container',lambda *_:item),patch.object(self.runtime,'ready',ready):
            self.runtime.start({},'unused',self.host,time.monotonic()+45)
        self.assertTrue(self.path.exists())
        self.assertNotEqual(self.path.read_bytes(),b'original')  # Startup cannot clear the newer epoch.

    def test_service_stop_without_marker_creates_pause(self):
        self.path.unlink()
        self.runtime.drain(self.host,time.monotonic()+45,preserve_existing=True)
        self.assertRegex(self.path.read_text(),r'^[0-9a-f]{32}$')


if __name__=='__main__':unittest.main()
