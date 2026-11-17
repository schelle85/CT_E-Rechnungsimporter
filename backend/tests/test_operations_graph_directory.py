"""Real profile/directory enumeration; POSIX ownership/modes are explicit local doubles."""
from contextlib import ExitStack
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_automation_runtime as fixtures
from test_operations_host import ops
from operations_test_support import SOURCE,DEPLOYMENT,INSTANCE


class GraphDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.output=self.root/"public";self.output.mkdir();self.results=self.root/"results";self.results.mkdir()
        self.config=self.root/"status.json";self.runtime=self.root/"runtime.json"
        self.cfg=dict(source_commit=SOURCE,deployment_id=DEPLOYMENT,automation_profile="synthetic",result_directory=str(self.results),output_directory=str(self.output))
        self.config.write_text(json.dumps(self.cfg));self.runtime.write_text(json.dumps(dict(instance_id=INSTANCE)))
        (self.output/"status.json").write_text('{"synthetic":true}');(self.output/".status-own-stage").write_text("synthetic")
        self.metadata={};self.stack=ExitStack();self.addCleanup(self.stack.close);original=Path.stat
        def metadata(path,*args,**kwargs):
            info=original(path,follow_symlinks=False);directory=stat.S_ISDIR(info.st_mode)
            public=path==self.output or path==self.output/"graph-access"
            values=dict(st_uid=0,st_gid=10001 if public else 0,st_mode=(stat.S_IFDIR|(0o750 if public else 0o700)) if directory else stat.S_IFREG|0o600,st_size=info.st_size)
            values.update(self.metadata.get(path,{}));return SimpleNamespace(**values)
        self.stack.enter_context(patch.object(Path,"stat",metadata));self.stack.enter_context(patch.object(Path,"lstat",metadata))
        self.automation=dict(runtime_profile=str(self.runtime))
        self.host=SimpleNamespace(protected=lambda path:Path(path),controlled_directory=fixtures.host.controlled_directory,
            load_peer=lambda _:SimpleNamespace(profile=lambda path,host:self.automation))

    def test_original_ap08_directory_and_profile_remain_valid(self):
        value,automation,binding=ops.profile(self.config,self.host)
        self.assertEqual(value,self.cfg);self.assertEqual(automation,self.automation);self.assertEqual(binding,dict(instance_id=INSTANCE))

    def test_exact_root_owned_public_graph_subdirectory_is_accepted_without_reading_its_payload(self):
        gate=self.output/"graph-access";gate.mkdir();(gate/"graph-access.json").write_text("synthetic public gate, no collector interpretation")
        before={path.name:path.read_bytes() for path in self.output.iterdir() if path.name!="graph-access"}
        self.assertEqual(ops.profile(self.config,self.host)[0],self.cfg)
        self.assertEqual({path.name:path.read_bytes() for path in self.output.iterdir() if path.name!="graph-access"},before)
        self.assertEqual((gate/"graph-access.json").read_text(),"synthetic public gate, no collector interpretation")

    def test_other_names_and_unsafe_graph_directory_type_owner_group_or_mode_are_rejected(self):
        foreign=self.output/"foreign";foreign.mkdir()
        with self.assertRaises(ValueError):ops.profile(self.config,self.host)
        foreign.rmdir();gate=self.output/"graph-access";gate.mkdir()
        for change in (dict(st_uid=10001),dict(st_gid=0),dict(st_mode=stat.S_IFDIR|0o770),dict(st_mode=stat.S_IFDIR|0o755),
                dict(st_mode=stat.S_IFLNK|0o777),dict(st_mode=stat.S_IFREG|0o440)):
            self.metadata[gate]=change
            with self.subTest(change=change),self.assertRaises(ValueError):ops.profile(self.config,self.host)
