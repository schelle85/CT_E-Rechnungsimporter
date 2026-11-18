"""Root/Linux-only AP10 checks in a disposable /run directory, without Docker/APT."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import patch


def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'requires Linux root')
class NativeMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='ap10-proof-',dir='/run')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.host=load('run-processing');self.runtime=load('host-runtime')
        self.rotation=load('run-rotation');self.m=load('run-maintenance')

    def test_native_flock_excludes_another_process_and_releases(self):
        path=self.root/'lock'
        code="""import fcntl,os,sys
fd=os.open(sys.argv[1],os.O_RDWR)
try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError: sys.exit(11)
"""
        def probe():
            return subprocess.run([sys.executable,'-I','-B','-c',code,str(path)],timeout=5).returncode
        with self.host.host_lock(path) as acquired:
            self.assertTrue(acquired);self.assertEqual(probe(),11)
        self.assertEqual(probe(),0)
        other=self.root/'hardlink';os.link(path,other)
        with self.assertRaises(ValueError):
            with self.host.host_lock(path): pass

    def test_native_file_permissions_and_symlink_refusal(self):
        path=self.root/'secret';path.write_bytes(b'bound');path.chmod(0o600)
        self.assertEqual(self.host.protected(path),path)
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.host.protected(path)
        path.chmod(0o600);link=self.root/'link';link.symlink_to(path)
        with self.assertRaises(ValueError): self.host.protected(link)

    def test_pause_owner_atomic_write_and_large_inventory_replacement(self):
        host=SimpleNamespace(protected=self.host.protected,controlled_directory=self.host.controlled_directory,
            host_lock=self.host.host_lock,DRAIN_FILE=str(self.root/'draining'))
        runtime=SimpleNamespace(gate=self.runtime.gate,sync_directory=self.runtime.sync_directory,GATE_LOCK=self.root/'gate.lock')
        controller=SimpleNamespace(host=host,runtime=runtime)
        controller.write=MethodType(self.rotation.Controller.write,controller)
        native=object.__new__(self.m.Native);native.host=host;native.runtime=runtime;native.c=controller
        value=dict(token='a'*32)
        native.pause(value);self.assertEqual(Path(host.DRAIN_FILE).read_bytes(),b'a'*32)
        native.confirm_pause(value)
        controller.write(Path(host.DRAIN_FILE),b'operator')
        with self.assertRaises(self.m.Refused): native.confirm_pause(value)
        with self.assertRaises(self.m.Refused): native.unpause(value)
        self.assertEqual(Path(host.DRAIN_FILE).read_bytes(),b'operator')
        controller.write(Path(host.DRAIN_FILE),b'a'*32);native.unpause(value)
        self.assertFalse(Path(host.DRAIN_FILE).exists())
        inventory='package\tversion\tii \n'*8192
        native.command=lambda args: '' if '--audit' in args else inventory
        with patch.object(self.m,'ROOT',self.root):
            first=native.packages(value,'verified');second=native.packages(value,'verified')
        self.assertEqual(first,second)
        path=self.root/(value['token']+'.verified.packages')
        self.assertGreater(path.stat().st_size,65536)
        self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertEqual(path.read_text(),inventory)
        # Exercise the streaming adapter with a harmless child, never apt/dpkg.
        result=self.m.Native.command(native,
            [sys.executable,'-I','-B','-c','import sys;print("public-probe");sys.exit(7)'],apt=True)
        self.assertEqual(result['exit'],7);self.assertGreater(result['output_bytes'],0)
        self.assertGreaterEqual(result['finished_at'],result['started_at'])

    def test_service_pause_preserved_but_explicit_request_changes_epoch_under_busy_lifecycle(self):
        host=SimpleNamespace(protected=self.host.protected,controlled_directory=self.host.controlled_directory,
            host_lock=self.host.host_lock,DRAIN_FILE=str(self.root/'draining'),
            PROCESSING_LOCK=self.root/'processing.lock')
        Path(host.DRAIN_FILE).write_bytes(b'owner');Path(host.DRAIN_FILE).chmod(0o600)
        with patch.object(self.runtime,'GATE_LOCK',self.root/'gate.lock'),patch.object(self.runtime,'LIFECYCLE_LOCK',self.root/'lifecycle.lock'):
            with self.host.host_lock(self.runtime.LIFECYCLE_LOCK) as acquired:
                self.assertTrue(acquired)
                with self.assertRaisesRegex(ValueError,'host_drain_busy'):
                    self.runtime.drain(host,time.monotonic()+.15,preserve_existing=True)
                self.assertEqual(Path(host.DRAIN_FILE).read_bytes(),b'owner')
                with self.assertRaisesRegex(ValueError,'host_drain_busy'):
                    self.runtime.drain(host,time.monotonic()+.15)
                self.assertNotEqual(Path(host.DRAIN_FILE).read_bytes(),b'owner')


if __name__=='__main__': unittest.main()
