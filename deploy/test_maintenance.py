"""AP10 targeted orchestration tests. Native actions replaced by explicit fakes."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sqlite3
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
        self.snapshot=dict(containers={k:dict(id=k,image=k) for k in ('db','api','nginx')},
            graph=dict(fingerprint='new',pem_hash='pem',binding={'source':'bound'},api_attestation=None))
        self.package_changed=False
    def read(self): return deepcopy(self.value)
    def save(self,value): self.value=deepcopy(value)
    def archive(self,value): self.calls.append('archive')
    def history_count(self): return 0
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
        return dict(deepcopy(self.snapshot),boot_id=self.boot_id)
    def packages(self,value,point):
        return dict(audit_empty=True,inventory_sha256=('b' if self.package_changed and point=='verified' else 'a')*64)
    def stop(self): assert self.guarded;self.calls.append('stop')
    def start(self): assert self.guarded;self.calls.append('start')
    def parent_start(self): assert not self.guarded;self.calls.append('parent_start')
    def reboot_required(self): return self.reboot
    def refresh_status(self): return dict(fresh=True)
    def command(self,args,timeout=15,*,apt=False):
        assert self.guarded
        self.calls.append(tuple(args))
        if self.mutator:self.mutator(self,args)
        if apt:return dict(exit=100 if self.fail in args else 0,output_sha256='c'*64,output_bytes=0,
                           started_at=int(SUNDAY),finished_at=int(SUNDAY+1),duration_seconds=1)
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
        with self.assertRaisesRegex(m.Refused,'reboot_not_observed'):self.run_at(h,'verify-boot')
        h.boot_id='after';self.assertEqual(self.run_at(h,'verify-boot')['phase'],'completed')
        self.assertEqual(len([c for c in h.calls if isinstance(c,tuple)]),before)
    def test_long_apt_cannot_authorize_late_reboot(self):
        h=Host(reboot=True);now=[SUNDAY]
        h.mutator=lambda _,args:now.__setitem__(0,SUNDAY+5400) if 'upgrade' in args else None
        with self.assertRaisesRegex(m.Refused,'reboot_window_closed'):self.run_at(h,clock=lambda:now[0])
        self.assertFalse(any(isinstance(c,tuple) and 'reboot' in c for c in h.calls))
    def test_boot_guard_and_unknown_transaction_do_not_replay(self):
        h=Host();self.run_at(h);h.value.update(phase='apt_upgrade',apt_in_progress=True);h.drain=None
        self.assertTrue(self.run_at(h,'boot-guard')['guarded']);count=len(h.calls)
        with self.assertRaisesRegex(m.Refused,'apt_outcome_unconfirmed'):self.run_at(h,'verify-boot')
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
        binding={'scope':'bound'};gate=dict(binding,mode='allowed',boot_id='boot',grants=[],operation_id='op',release_hash='seal',fingerprint='new',pem_hash='pem')
        material=dict(fingerprint='new',pem_hash='pem')
        status=dict(ok=True,binding=binding,head=dict(active_operation='op'),host=dict(phase='committed',paused=False,seal='seal',target='new',new=material),current=material,cleanup=dict(phase='planned'))
        self.assertEqual(m.stable_rotation(status,gate,binding,'boot')['fingerprint'],'new')
        for phase in ('prepared','adopting','proof_unknown'):
            altered=deepcopy(status);altered['host']['phase']=phase
            with self.assertRaises(m.Refused):m.stable_rotation(altered,gate,binding,'boot')
        status['head']['active_operation']=None
        with self.assertRaises(m.Refused):m.stable_rotation(status,gate,binding,'boot')
        status['closed_confirmed']=True;self.assertIsNone(m.stable_rotation(status,gate,binding,'boot')['operation_id'])

    def test_automatic_failure_requires_explicit_manual_ack(self):
        h=Host();h.fail='update'
        with self.assertRaises(m.Refused): self.run_at(h)
        count=len(h.calls);h.fail=None
        with self.assertRaisesRegex(m.Refused,'automatic_recovery_unconfirmed'): self.run_at(h,'verify-boot')
        with self.assertRaisesRegex(m.Refused,'manual_recovery_ack_required'): self.run_at(h,'recover')
        self.assertNotIn('start',h.calls[count:]);self.assertNotIn('unpause',h.calls[count:])
        result=m.execute(h,'recover',acknowledge_run=h.value['token'])
        self.assertEqual(result['phase'],'recovered');self.assertIsNone(h.drain)
        self.assertFalse(any(isinstance(c,tuple) for c in h.calls[count:]))

    def test_automatic_missing_evidence_never_reconstructs(self):
        original=Host(reboot=True);self.run_at(original)
        for field in ('before','packages_before','packages_after','pre_reboot','upgrade','reboot_request_accepted'):
            h=Host();h.value=deepcopy(original.value);h.value.pop(field);h.boot_id='after'
            with self.subTest(field=field),self.assertRaises(m.Refused): self.run_at(h,'verify-boot')
            self.assertNotIn('start',h.calls);self.assertNotIn('unpause',h.calls)
            self.assertNotIn('before_reconstructed_on_recovery',h.value)

    def test_saved_reboot_intent_survives_failed_phase(self):
        h=Host(reboot=True);self.run_at(h);h.value['phase']='failed'
        for mode in ('verify-boot','recover'):
            with self.assertRaisesRegex(m.Refused,'reboot_not_observed'):
                m.execute(h,mode,acknowledge_run=h.value['token'])
        h.boot_id='after'
        with self.assertRaisesRegex(m.Refused,'automatic_recovery_unconfirmed'): self.run_at(h,'verify-boot')
        self.assertEqual(m.execute(h,'recover',acknowledge_run=h.value['token'])['phase'],'recovered')

    def test_manual_missing_original_baseline_refused(self):
        h=Host();h.fail='facts'
        with self.assertRaises(m.Refused): self.run_at(h)
        h.fail=None
        with self.assertRaisesRegex(m.Refused,'recovery_baseline_missing'):
            m.execute(h,'recover',acknowledge_run=h.value['token'])
        self.assertNotIn('start',h.calls);self.assertNotIn('before',h.value)

    def test_original_state_checked_before_second_stop_and_reboot(self):
        for changed in ('db','nginx','fingerprint','pem_hash','binding','api','packages'):
            h=Host(reboot=True)
            def mutate(host,args):
                if 'upgrade' not in args:return
                if changed in ('db','nginx','api'): host.snapshot['containers'][changed]['id']='changed'
                elif changed=='packages': host.package_changed=True
                else: host.snapshot['graph'][changed]='changed'
            h.mutator=mutate
            with self.subTest(changed=changed),self.assertRaises(m.Refused): self.run_at(h)
            self.assertEqual(h.calls.count('stop'),1)
            self.assertFalse(any(isinstance(c,tuple) and 'reboot' in c for c in h.calls))

    def test_api_replacement_requires_bound_current_receipt_and_postboot_preservation(self):
        h=Host()
        def mutate(host,args):
            if 'upgrade' in args:
                host.snapshot['containers']['api']['id']='ap12-new'
                host.snapshot['graph']['api_attestation']=dict(id='ap12-new',image='api',boot_id=host.boot_id)
        h.mutator=mutate;self.assertEqual(self.run_at(h)['phase'],'completed')
        h=Host(reboot=True);self.run_at(h);h.boot_id='after';h.snapshot['containers']['db']['id']='new-db'
        with self.assertRaisesRegex(m.Refused,'preserved_container_changed'): self.run_at(h,'verify-boot')
        self.assertIsNotNone(h.drain);self.assertEqual(h.value['before']['containers']['db']['id'],'db')

class EffectReceiptTests(unittest.TestCase):
    def test_only_current_uncertain_external_receipts_block(self):
        spec=importlib.util.spec_from_file_location('effects',Path(__file__).with_name('maintenance-effects.py'))
        probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
        with sqlite3.connect(':memory:') as db:
            db.executescript("""
                CREATE TABLE notification_outbox(scope_key,state,reservations,owner,lease_until,reserved_at,post_started_at,http_status);
                CREATE TABLE graph_actions(mailbox_key,state,reservations,error_code,owner,lease_until);
                CREATE TABLE storage_operations(action_key,scope_key,state,publication_attempts,publication_rejected,owner,lease_until);
                CREATE TABLE processing_messages(message_key,mailbox_key,owner,lease_until);
                CREATE TABLE processing_attachments(message_key,effect_key,effect_state,effective_status);
                INSERT INTO notification_outbox VALUES ('n','accepted',1,NULL,0,1,2,202),('n','rejected',1,NULL,0,1,2,403),
                    ('n','unknown',1,NULL,0,1,NULL,NULL),('other','sending',1,'foreign',20,1,NULL,NULL);
                INSERT INTO graph_actions VALUES ('g','done',1,NULL,NULL,0),('g','operator_required',1,'graph_before_cutoff',NULL,0),
                    ('g','unknown',1,'graph_timeout',NULL,0);
                INSERT INTO storage_operations VALUES ('known','s','stored',1,0,NULL,0),('rejected','s','operator_required',1,1,NULL,0),
                    ('terminal','s','operator_required',1,0,NULL,0);
                INSERT INTO processing_messages VALUES ('message','p',NULL,0);
                INSERT INTO processing_attachments VALUES ('message',NULL,NULL,'unknown'),('message','known','uncertain','recognized');
            """)
            parameters=dict(notification='n',graph_mailbox='g',storage='s',processing_mailbox='p')
            scan=lambda:probe.scan(lambda sql,p:db.execute(sql,p).fetchone(),parameters)
            self.assertFalse(any(scan().values()))
            observed=probe.scan(lambda sql,p:db.execute(sql,p).fetchone(),parameters,probe.TERMINAL)
            self.assertTrue(all(observed.values()))  # Terminal unknown stays visible, without perpetual blocking.
            examples=[
                ('notifications',"INSERT INTO notification_outbox VALUES ('n','sending',1,NULL,0,1,NULL,NULL)"),
                ('notifications',"INSERT INTO notification_outbox VALUES ('n','prepared',0,'stale',0,NULL,NULL,NULL)"),
                ('notifications',"INSERT INTO notification_outbox VALUES ('n','unknown',0,NULL,0,NULL,NULL,NULL)"),
                ('graph',"INSERT INTO graph_actions VALUES ('g','checking',1,NULL,NULL,0)"),
                ('graph',"INSERT INTO graph_actions VALUES ('g','unknown',1,NULL,'stale',0)"),
                ('storage',"INSERT INTO storage_operations VALUES ('open','s','publishing',1,0,NULL,0)"),
                ('storage',"INSERT INTO storage_operations VALUES ('open','s','operator_required',1,0,'stale',0)"),
                ('file_receipts',"INSERT INTO processing_attachments VALUES ('message','missing','blocked','recognized')"),
                ('processing_owner',"UPDATE processing_messages SET owner='stale' WHERE message_key='message'")]
            for category,sql in examples:
                db.execute('SAVEPOINT trial');db.execute(sql)
                self.assertTrue(scan()[category],category)
                db.execute('ROLLBACK TO trial');db.execute('RELEASE trial')

    def test_tls_pending_refuses_before_creating_any_probe(self):
        with tempfile.TemporaryDirectory() as folder:
            pending=Path(folder)/'.tls-pending.json';pending.write_text('{}')
            native=object.__new__(m.Native)
            native.runtime=SimpleNamespace(tls_pending=lambda _:pending)
            native.host=SimpleNamespace(protected=Path)
            native.c=SimpleNamespace(binding={'tls_root':folder})
            with self.assertRaisesRegex(m.Refused,'tls_pending'): native.effects()

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
