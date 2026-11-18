"""AP10 host-only APT maintenance. No package replay, image pull or schema change."""
import argparse
from contextlib import contextmanager, ExitStack
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
from uuid import uuid4
from zoneinfo import ZoneInfo
import importlib.util

ROOT = Path('/var/lib/invoice-importer/maintenance')
PROFILE = '/etc/invoice-importer/maintenance-host.json'
TIMERS = ('invoice-processing-inbox.timer', 'invoice-processing-corrections.timer',
          'invoice-notifications.timer', 'invoice-tls.timer', 'invoice-status.timer',
          'invoice-rotation-daily.timer', 'invoice-rotation-opportunity.timer')
CALENDARS = ('*-*-* *:00/5:00 Europe/Berlin', '*-*-* *:00/15:00 Europe/Berlin',
             '*-*-* *:*:00 Europe/Berlin', '*-*-* *:00:00 Europe/Berlin',
             '*-*-* *:*:20 Europe/Berlin', '*-*-* 03:35:00 Europe/Berlin',
             '*-*-* *:*:40 Europe/Berlin')
ENV = dict(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8',
           DEBIAN_FRONTEND='noninteractive', NEEDRESTART_MODE='l', NEEDRESTART_SUSPEND='1')
DONE = {'completed', 'recovered'}


class Refused(RuntimeError): pass


def rotation_peer():
    path=Path(__file__).with_name('run-rotation.py')
    for entry in (Path(__file__),path):
        for part in [*reversed(entry.parents),entry]:
            info=part.lstat()
            if info.st_uid or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode): raise Refused('peer_policy')
        if not stat.S_ISREG(info.st_mode) or info.st_size>65536: raise Refused('peer_policy')
    spec=importlib.util.spec_from_file_location('maintenance_rotation',path)
    rotation=importlib.util.module_from_spec(spec);spec.loader.exec_module(rotation)
    return rotation


def window(epoch, *, reboot=False):
    local = datetime.fromtimestamp(epoch, ZoneInfo('Europe/Berlin'))
    minute = local.hour * 60 + local.minute
    return local.weekday() == 6 and 180 <= minute < (270 if reboot else 195)


def stable_rotation(status, gate, binding, boot):
    if (status.get('ok') is not True or status.get('binding') != binding
            or gate.get('mode') != 'allowed' or gate.get('boot_id') != boot
            or any(gate.get(k) != v for k, v in binding.items()) or gate.get('grants')):
        raise Refused('graph_not_confirmed')
    operation = status['head']['active_operation']
    if operation is None:
        if status.get('closed_confirmed') is not True: raise Refused('closed_rotation_unconfirmed')
    if operation is not None:
        host, current, cleanup = status.get('host'), status.get('current'), status.get('cleanup')
        if (not host or host['phase'] != 'committed' or host['paused']
                or gate['operation_id'] != operation or gate['release_hash'] != host['seal']
                or current != host[host['target']]
                or cleanup is not None and cleanup['phase'] not in {'planned', 'completed'}):
            raise Refused('rotation_not_committed')
    return dict(operation_id=operation, mode=gate['mode'], fingerprint=gate['fingerprint'],
                release_hash=gate['release_hash'])


class Native:
    def __init__(self, filename):
        rotation = rotation_peer()
        self.host = rotation.peer('run-processing.py')
        self.host.protected(__file__)
        raw = self.host.protected(filename).read_bytes()
        self.cfg = json.loads(raw, object_pairs_hook=rotation.unique)
        if (set(self.cfg) != {'machine_id', 'ubuntu_release', 'product_source', 'rotation_profile', 'status_profile', 'apt_policy_digest'}
                or not re.fullmatch('[0-9a-f]{32}', self.cfg['machine_id'])
                or self.cfg['ubuntu_release'] != '26.04'
                or not all(re.fullmatch('[0-9a-f]{64}', self.cfg[k]) for k in ('apt_policy_digest',))
                or not re.fullmatch('[0-9a-f]{40}', self.cfg['product_source'])): raise Refused('profile_invalid')
        if Path('/etc/machine-id').read_text().strip() != self.cfg['machine_id']: raise Refused('wrong_machine')
        os_release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        if os_release.get('ID', '').strip('"') != 'ubuntu' or os_release.get('VERSION_ID', '').strip('"') != self.cfg['ubuntu_release']:
            raise Refused('wrong_distribution')
        self.profile_hash = hashlib.sha256(raw).hexdigest()
        self.host.protected(self.cfg['status_profile'])
        self.c = rotation.Controller(self.cfg['rotation_profile'], until=time.monotonic()+900)
        if self.c.access.source_commit != self.cfg['product_source']: raise Refused('source_changed')
        self.runtime = self.c.runtime
        self.cancelled = False
        self.host.controlled_directory(ROOT)
        if stat.S_IMODE(ROOT.stat().st_mode) != 0o700: raise Refused('state_permissions')

    def read(self):
        path = ROOT/'state.json'
        if not path.exists(): return None
        value = json.loads(self.host.protected(path).read_text())
        if (value['schema'] != 1 or value['profile_hash'] != self.profile_hash
                or not re.fullmatch('[0-9a-f]{32}', value['token'])): raise Refused('state_binding')
        return value

    def save(self, value):
        raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        if len(raw) > 65536: raise Refused('journal_limit')
        self.c.write(ROOT/'state.json', raw)

    def archive(self, value):
        history = ROOT/'history'; self.host.controlled_directory(history)
        if len(list(history.iterdir())) >= 52: raise Refused('journal_capacity')
        self.c.archive(history/(value['token']+'.json'), value)

    def boot(self): return self.c.model.boot_id()
    def marker(self): return self.runtime.gate(self.host)

    def pause(self, value):
        with self.host.host_lock(self.runtime.GATE_LOCK, wait=5) as acquired:
            if not acquired: raise Refused('pause_busy')
            current = self.marker()
            wanted = value['token'].encode('ascii')
            if current is None: self.c.write(Path(self.host.DRAIN_FILE), wanted)
            elif current != wanted: raise Refused('operator_pause_preserved')

    def unpause(self, value):
        with self.host.host_lock(self.runtime.GATE_LOCK, wait=5) as acquired:
            if not acquired or self.marker() != value['token'].encode('ascii'): raise Refused('pause_owner_changed')
            os.unlink(self.host.DRAIN_FILE); self.runtime.sync_directory(Path(self.host.DRAIN_FILE).parent)

    def confirm_pause(self, value):
        with self.host.host_lock(self.runtime.GATE_LOCK,wait=5) as acquired:
            if not acquired or self.marker()!=value['token'].encode('ascii'): raise Refused('pause_owner_changed')

    @contextmanager
    def guards(self):
        self.c.until = time.monotonic()+900
        with self.c.writer.session(), self.c.lifecycle_locks():
            if next(self.c.journal.glob('invoice-rotation-*.job.json'), None): raise Refused('rotation_job_unknown')
            for label in ('invoice.processing.operation', 'invoice.notification.operation'):
                if self.c.command(['container','ls','-aq','--filter','label='+label]): raise Refused('worker_unknown')
            self.c.no_other_graph_consumers(self.c.api()['Id'])
            fd = self.c.writer.gate._lock()
            try:
                until = time.monotonic()+45
                while True:
                    try: self.c.model.flock(fd, exclusive=True); break
                    except self.c.model.GraphAccessError:
                        if time.monotonic() >= until: raise Refused('graph_busy')
                        time.sleep(.1)
                self.c.writer.gate._identity(fd)
                yield
            finally: os.close(fd)

    def rotation(self):
        self.c.until = time.monotonic()+180
        status=self.c.worker('status');gate=self.c.writer._current()
        if status['head']['active_operation'] is None:
            bootstrap=self.c.journal/'.bootstrap.json'
            if bootstrap.exists():
                record=json.loads(self.host.protected(bootstrap).read_text())
            else: record=None
            if record and record.get('operation_id')==gate['operation_id']:
                status['closed_confirmed']=(record.get('seal')==gate['release_hash']
                    and hashlib.sha256(json.dumps({k:v for k,v in record.items() if k!='seal'},sort_keys=True,
                        separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()==record['seal']
                    and record.get('current')==status['current'] and record.get('paused') is False
                    and all(record.get(k)==v for k,v in self.c.access.fields().items()))
            else:
                saved=self.c.worker('read',gate['operation_id'])['host']
                status['closed_confirmed']=bool(saved and saved['phase']=='committed' and not saved['paused']
                    and saved['seal']==gate['release_hash'] and saved[saved['target']]==status['current'])
        return stable_rotation(status, gate, self.c.access.fields(), self.boot())

    def command(self, args, timeout=15, *, apt=False):
        if apt:
            # No transaction timeout/kill: wait for native APT/dpkg to finish even after SIGTERM.
            started_at=int(time.time());started=time.monotonic()
            digest = hashlib.sha256(); count = 0
            with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=ENV) as process:
                while chunk := process.stdout.read(65536): digest.update(chunk); count += len(chunk)
                code = process.wait()
            return dict(exit=code,output_sha256=digest.hexdigest(),output_bytes=count,
                        started_at=started_at,finished_at=int(time.time()),duration_seconds=int(time.monotonic()-started))
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
                                    env=ENV, timeout=timeout)
            if output.tell() > 1048576: raise Refused('command_output_limit')
            output.seek(0); raw = output.read()
        if result.returncode: raise Refused('native_check_failed')
        return raw.decode('utf-8')

    def policy_digest(self):
        digest = hashlib.sha256()
        paths = []
        for name in ('sources.list', 'preferences', 'apt.conf'):
            if (Path('/etc/apt')/name).exists(): paths.append(Path('/etc/apt')/name)
        for name in ('sources.list.d','preferences.d','apt.conf.d'):
            folder = Path('/etc/apt')/name
            if folder.exists(): paths.extend(folder.iterdir())
        if not paths or len(paths) > 128: raise Refused('apt_policy_limit')
        for path in sorted(paths):
            if path.name == '01autoremove-kernels': continue  # Native generated kernel retention policy.
            for part in [*reversed(path.parents),path]:
                info=part.lstat()
                if info.st_uid or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode): raise Refused('apt_policy_permissions')
            if not path.is_file() or path.stat().st_size > 1048576: raise Refused('apt_policy_file')
            digest.update(str(path).encode()+b'\0'+path.read_bytes()+b'\0')
        return digest.hexdigest()

    def policy(self):
        if self.policy_digest() != self.cfg['apt_policy_digest']: raise Refused('apt_policy_changed')

    def packages(self, value, point):
        if self.command(['/usr/bin/dpkg','--audit']).strip(): raise Refused('dpkg_audit')
        text = self.command(['/usr/bin/dpkg-query','-W','-f=${binary:Package}\t${Version}\t${db:Status-Abbrev}\n'])
        # Inventories can exceed the existing peer's 64-KiB JSON/file limit.
        path=ROOT/(value['token']+'.'+point+'.packages')
        self.host.controlled_directory(path.parent)
        if path.exists() or path.is_symlink():
            info=path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_nlink!=1
                    or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>1048576):
                raise Refused('inventory_permissions')
        fd,name=tempfile.mkstemp(prefix='.packages-',dir=ROOT)
        try:
            with os.fdopen(fd,'wb') as output:
                os.fchmod(output.fileno(),0o600);output.write(text.encode());output.flush();os.fsync(output.fileno())
            os.replace(name,path);self.runtime.sync_directory(ROOT)
        finally:
            if os.path.exists(name): os.unlink(name)
        return dict(audit_empty=True, inventory_sha256=hashlib.sha256(text.encode()).hexdigest())

    def timers(self):
        facts = {}
        for name, calendar in zip(TIMERS,CALENDARS):
            text = self.command(['/usr/bin/systemctl','show',name,'--property=LoadState,ActiveState,UnitFileState,TimersCalendar'])
            row = dict(line.split('=',1) for line in text.splitlines() if '=' in line)
            values = re.findall(r'OnCalendar=([^;]+);',row.get('TimersCalendar',''))
            if (row.get('LoadState')!='loaded' or row.get('ActiveState')!='active' or row.get('UnitFileState')!='enabled'
                    or len(values)!=1 or ' '.join(values[0].split())!=calendar): raise Refused('timer_unconfirmed')
            facts[name] = dict(active=True, enabled=True, calendar=calendar)
        return facts

    def preflight(self):
        self.policy()
        for unit in ('invoice-importer.service','invoice-maintenance-guard.service','invoice-maintenance-recover.service'):
            self.command(['/usr/bin/systemctl','is-active','--quiet',unit])
        # Existing updater must be disabled at installation, never stopped mid-transaction here.
        for unit in ('apt-daily-upgrade.timer','apt-daily.service','apt-daily-upgrade.service'):
            text=self.command(['/usr/bin/systemctl','show',unit,'--property=ActiveState,UnitFileState'])
            row=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
            if row.get('ActiveState') not in {'inactive','failed'}: raise Refused('apt_job_active')
            if unit.endswith('.timer') and row.get('UnitFileState') not in {'disabled','masked'}: raise Refused('apt_updater_enabled')

    def facts(self):
        self.c.until=time.monotonic()+180
        self.runtime.ready(self.c.binding,self.c.auto['public_origin'],self.host,self.c.until)
        config=self.host.profile(self.c.auto['processing_profile'])
        with self.host.CifsBinding(config) as files: files.check()
        tls=self.runtime.tls_profile(self.c.auto['tls_profile'],self.host)
        with self.runtime.Source(tls,self.host) as files: files.check()
        containers={kind:self.runtime.inspect_container(self.c.binding,kind,self.host,self.c.until) for kind in ('db','api','nginx')}
        return dict(boot_id=self.boot(), at=int(time.time()), https_ready=True, mounts=dict(importer=True,tls_source=True),
                    containers={kind:dict(id=item['id'],image=item['image']) for kind,item in containers.items()},
                    graph=self.rotation(), timers=self.timers())

    def stop(self):
        self.c.until=time.monotonic()+600
        for kind, limit in (('nginx',330),('api',60),('db',180)):
            self.c.until=time.monotonic()+limit+30
            item=self.runtime.inspect_container(self.c.binding,kind,self.host,self.c.until)
            if kind=='nginx':
                _, config=self.c.command(['inspect','--format','{{json .Config}}',item['id']],json_output=True)
                if config.get('StopSignal') != 'SIGQUIT': raise Refused('nginx_not_graceful')
            group=Path('/sys/fs/cgroup/system.slice')/('docker-'+item['id']+'.scope')
            self.c.command(['stop','--time',str(limit),item['id']],limit+10)
            stopped=self.runtime.inspect_container(self.c.binding,kind,self.host,self.c.until)
            if (stopped['id']!=item['id'] or stopped['state'].get('Running') or stopped['state'].get('Pid')!=0
                    or stopped['state'].get('ExitCode')!=0): raise Refused('stop_not_graceful')
            self.c.quiet(group)
            if kind=='api': self.rotation()  # Recheck SQL only after admission has closed.

    def start(self):
        self.c.until=time.monotonic()+240
        for kind in ('db','api','nginx'):
            before=self.runtime.inspect_container(self.c.binding,kind,self.host,self.c.until)
            self.c.command(['start',before['id']],15)
            def check():
                item=self.runtime.inspect_container(self.c.binding,kind,self.host,self.c.until)
                if (item['id']!=before['id'] or not item['state'].get('Running') or
                        kind!='nginx' and item['state'].get('Health',{}).get('Status')!='healthy'): raise ValueError()
            self.runtime.wait_readiness(check,self.c.until)
        self.runtime.wait_readiness(lambda:self.runtime.ready(self.c.binding,self.c.auto['public_origin'],self.host,self.c.until),self.c.until)

    def parent_start(self): self.command(['/usr/bin/systemctl','start','invoice-importer.service'],300)

    def reboot_required(self): return Path('/run/reboot-required').exists()

    def refresh_status(self):
        self.command(['/usr/bin/python3','-I','-B',str(Path(__file__).with_name('run-automation.py')),
                      'status','--profile',self.cfg['status_profile']],25)
        cfg=json.loads(self.host.protected(self.cfg['status_profile']).read_text())
        status=json.loads(self.host.protected(str(Path(cfg['output_directory'])/'status.json')).read_text())
        if (status['boot_id']!=self.boot() or status['source_commit']!=self.cfg['product_source']
                or status['instance_id']!=self.c.access.instance_id or not 0<=time.time()-status['generated_at']<=180):
            raise Refused('status_unconfirmed')
        return dict(generated_at=status['generated_at'],draining=status['draining'],
                    jobs={k:dict(last_result=v['last_result'],running=v['running']) for k,v in status['jobs'].items()})


def finish(native, value, *, recovered=False):
    native.parent_start()  # No recursive lifecycle/writer lock acquisition.
    with native.guards():
        after=native.facts()
        inventory=native.packages(value,'verified')
        if value.get('packages_after') and inventory!=value['packages_after']: raise Refused('package_inventory_changed')
        for kind in ('db','nginx'):
            if after['containers'][kind]!=value['before']['containers'][kind]: raise Refused('preserved_container_changed')
        if after['graph']['fingerprint']!=value['before']['graph']['fingerprint']: raise Refused('graph_material_changed')
        if native.cancelled: raise Refused('cancelled_before_resume')
        value['after']=after; native.unpause(value)
    value['status']=native.refresh_status()
    value.update(phase='recovered' if recovered else 'completed',finished_at=int(time.time()))
    native.save(value)


def execute(native, mode, *, clock=time.time):
    if mode=='policy-digest': return dict(ok=True,apt_policy_digest=native.policy_digest())
    value=native.read()
    if mode=='boot-guard':
        if value and value['phase'] not in DONE: native.pause(value)
        return dict(ok=True,guarded=bool(value and value['phase'] not in DONE))
    if mode=='check':
        native.preflight()
        with native.guards(): facts=native.facts()
        return dict(ok=True,check_only=True,facts=facts,pending=value is not None and value['phase'] not in DONE)
    if mode=='recover':
        if not value or value['phase'] in DONE: return dict(ok=True,nothing_pending=True)
        if value['phase']=='awaiting_reboot' and native.boot()==value['boot_before']: raise Refused('reboot_not_observed')
        native.pause(value)
        # Never repeat APT or a reboot from an interrupted/failed transaction.
        if value.get('apt_in_progress'): raise Refused('apt_outcome_unconfirmed')
        with native.guards():
            native.start()
            if 'before' not in value:
                value['before']=native.facts();value['before_reconstructed_on_recovery']=True;native.save(value)
        finish(native,value,recovered=value['phase']!='awaiting_reboot')
        return dict(ok=True,phase=value['phase'])
    if not window(clock()): return dict(ok=True,skipped=True,code='outside_start_window')
    if value and value['phase'] not in DONE: raise Refused('previous_run_unresolved')
    native.preflight()
    if native.marker() is not None: raise Refused('operator_pause_preserved')
    if value: native.archive(value)
    value=dict(schema=1,token=uuid4().hex,profile_hash=native.profile_hash,phase='preflight',started_at=int(clock()),boot_before=native.boot())
    native.save(value)
    try:
        with native.guards():
            value['before']=native.facts(); value['packages_before']=native.packages(value,'before')
            native.pause(value);value['phase']='drained';native.save(value)
            native.stop()
            if not window(clock()) or native.cancelled: raise Refused('start_window_closed')
            native.confirm_pause(value)
            value.update(phase='apt_update',apt_in_progress=True);native.save(value)
            base=['/usr/bin/apt-get','-o','DPkg::Lock::Timeout=60','-o','Acquire::Retries=2',
                  '-o','Acquire::http::Timeout=60','-o','Acquire::https::Timeout=60']
            value['update']=native.command(base+['update','--error-on=any'],apt=True)
            value['apt_in_progress']=False;native.save(value)
            if value['update']['exit'] or not window(clock()) or native.cancelled: raise Refused('apt_update_failed_or_window_closed')
            native.confirm_pause(value)
            value.update(phase='apt_upgrade',apt_in_progress=True);native.save(value)
            value['upgrade']=native.command(base+['-o','Dpkg::Options::=--force-confdef','-o','Dpkg::Options::=--force-confold',
                '--assume-yes','--with-new-pkgs','--no-remove','upgrade'],apt=True)
            value['apt_in_progress']=False;native.save(value)
            if value['upgrade']['exit'] or native.cancelled: raise Refused('apt_upgrade_failed_or_cancelled')
            native.confirm_pause(value)
            value['packages_after']=native.packages(value,'after')
            native.start();value['post_update']=native.facts()
            value['reboot_required']=native.reboot_required()
            if value['reboot_required']:
                if not window(clock(),reboot=True) or native.cancelled: raise Refused('reboot_window_closed')
                native.stop()
                if not window(clock(),reboot=True) or native.cancelled: raise Refused('reboot_window_closed')
                native.confirm_pause(value)
                value.update(phase='awaiting_reboot',reboot_requested_at=int(clock()),reboot_request_accepted=False);native.save(value)
                native.command(['/usr/bin/systemctl','--no-block','reboot'],15)
                value['reboot_request_accepted']=True;native.save(value)
                return dict(ok=True,reboot_requested=True,verification_pending=True)
            value['phase']='post_checks';native.save(value)
        finish(native,value)
        return dict(ok=True,phase=value['phase'])
    except BaseException as error:
        value.update(failed_phase=value['phase'],phase='failed',failed_at=int(clock()),
                     code=str(error) if isinstance(error,Refused) else 'maintenance_unconfirmed')
        native.save(value)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('check','scheduled','recover','boot-guard','policy-digest','service-drain'))
    parser.add_argument('--profile',default=PROFILE)
    args=parser.parse_args()
    try:
        if os.name!='posix' or os.geteuid()!=0 or not sys.flags.isolated or not sys.dont_write_bytecode: raise Refused('root_isolated_required')
        os.umask(0o077)
        if args.mode=='service-drain':
            # ExecStop must work while the weekly process owns maintenance/lifecycle locks.
            # Existing drain waiting stays bounded; a busy maintenance lock is never taken.
            rotation=rotation_peer();host=rotation.peer('run-processing.py')
            runtime=rotation.peer('host-runtime.py')
            result=runtime.drain(host,time.monotonic()+45,preserve_existing=True)
            print(json.dumps(result,separators=(',',':')))
            return 0
        native=Native(args.profile)
        signal.signal(signal.SIGTERM,lambda *_:setattr(native,'cancelled',True))
        signal.signal(signal.SIGINT,lambda *_:setattr(native,'cancelled',True))
        with native.host.host_lock('/run/invoice-importer/maintenance.lock') as acquired:
            if not acquired: raise Refused('maintenance_busy')
            result=execute(native,args.mode)
    except BaseException as error:
        result=dict(ok=False,code=str(error) if isinstance(error,Refused) else 'maintenance_unconfirmed')
    print(json.dumps(result,separators=(',',':')))
    return 0 if result.get('ok') else 1


if __name__=='__main__': raise SystemExit(main())
