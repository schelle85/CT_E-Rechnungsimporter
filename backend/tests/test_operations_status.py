"""C freshness/binding policy and bounded reader; OS metadata doubles on Windows."""
import io
import json
import os
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from app import operations_status as model
from operations_test_support import SOURCE,DEPLOYMENT,INSTANCE,BOOT,NOW,raw,changed


class ProjectionTests(unittest.TestCase):
    def project(self,value,**changes):
        return model.project(value,**dict(dict(now=NOW,source_commit=SOURCE,deployment_id=DEPLOYMENT,instance_id=INSTANCE,current_boot=BOOT),**changes))

    def test_active_paused_and_configured_are_distinct(self):
        value=raw();self.assertEqual(self.project(value)["state"],"active")
        for row in value["jobs"].values():row["active"]=False
        projected=self.project(value)
        self.assertEqual(projected["state"],"paused");self.assertFalse(projected["automatic_schedule_active"])
        self.assertTrue(projected["jobs"]["inbox"]["configured"])
        value["jobs"]["inbox"]["configured"]=False
        self.assertEqual(self.project(value)["jobs"]["inbox"]["state"],"paused")

    def test_missing_dependencies_failed_runs_backoff_and_drain_never_green(self):
        for path,item,job in ((["mounts","importer"],None,"inbox"),(["startup","ready"],False,"corrections"),
                (["startup","database_ready"],False,"notifications"),(["mounts","tls_source"],False,"tls"),
                (["jobs","notifications","last_result"],"failed","notifications"),(["jobs","inbox","blocked"],True,"inbox"),
                (["draining"],True,"tls")):
            with self.subTest(path=path):
                value=self.project(changed(raw(),path,item))
                self.assertEqual(value["jobs"][job]["state"],"degraded")
                self.assertTrue(value["jobs"][job]["active"])
        value=self.project(changed(raw(),["startup","ready"],False))
        self.assertEqual(value["jobs"]["notifications"]["state"],"active")

    def test_exact_ttl_future_and_boot_boundaries(self):
        for age,reason in ((180,None),(181,"stale"),(-30,None),(-31,"future")):
            value=self.project(raw(NOW-age))
            self.assertEqual(value["reason"],reason)
            if reason:self.assertIsNone(value["automatic_schedule_active"])
        for boot in (None,DEPLOYMENT):
            self.assertEqual(self.project(raw(),current_boot=boot)["reason"],"boot")

    def test_source_deployment_instance_and_schema_fail_closed_without_metadata(self):
        cases=[changed(raw(),["source_commit"],"b"*40),changed(raw(),["deployment_id"],INSTANCE),changed(raw(),["instance_id"],BOOT),
            changed(raw(),["schema_version"],True),changed(raw(),["boot_id"],"x"*36),dict(raw(),private_path="secret"),
            changed(raw(),["jobs","inbox","active"],"true"),changed(raw(),["jobs","inbox","configured"],False),
            changed(raw(),["jobs","tls","last_result"],["ok"]),changed(raw(),["jobs","tls","next_run_at"],9007199254740991)]
        for value in cases:
            with self.subTest(value=value):
                result=self.project(value)
                self.assertEqual(result["state"],"unknown");self.assertIsNone(result["source_commit"])
                self.assertIsNone(result["automatic_schedule_active"]);self.assertNotIn("secret",json.dumps(result))
        self.assertEqual(self.project(raw(),source_commit=None)["reason"],"unbound")

    def test_partial_unknown_is_not_reported_as_inactive(self):
        value=raw();value["jobs"]["notifications"].update(configured=None,active=None)
        result=self.project(value)
        self.assertEqual(result["state"],"unknown");self.assertIsNone(result["automatic_schedule_active"])
        self.assertEqual(result["automatic_schedule_state"],"unknown")

    def read(self,body,**metadata):
        class Source(io.BytesIO):
            def fileno(self):return 43
        info=dict(st_mode=stat.S_IFREG|0o440,st_uid=0,st_gid=10001,st_nlink=1,st_size=len(body));info.update(metadata)
        with patch.object(model.os,"O_NOFOLLOW",0x20000,create=True),patch.object(model.os,"O_NONBLOCK",0x800,create=True),\
                patch.object(model.os,"open",return_value=43) as opened,patch.object(model.os,"fdopen",return_value=Source(body)),\
                patch.object(model.os,"fstat",return_value=SimpleNamespace(**info)),patch.object(model,"boot_id",return_value=BOOT),\
                patch.dict(os.environ,OPERATIONS_SOURCE_COMMIT=SOURCE,OPERATIONS_DEPLOYMENT_ID=DEPLOYMENT):
            value=model.read_status(INSTANCE,now=NOW)
        self.assertEqual(opened.call_args.args[1]&0x20800,0x20800)
        return value

    def test_reader_rejects_links_permissions_oversize_and_duplicate_json(self):
        body=json.dumps(raw()).encode()
        self.assertEqual(self.read(body)["state"],"active")
        for metadata in (dict(st_nlink=2),dict(st_uid=10001),dict(st_gid=0),dict(st_mode=stat.S_IFREG|0o644),dict(st_mode=stat.S_IFIFO|0o440),dict(st_size=32769)):
            self.assertEqual(self.read(body,**metadata)["state"],"unknown")
        for broken in (b"{",b'{"schema_version":1,"schema_version":1}',b"x"*32769):
            self.assertEqual(self.read(broken)["state"],"unknown")

    def test_missing_and_unreadable_status_are_neutral(self):
        for error,reason in ((FileNotFoundError(),"missing"),(PermissionError(),"unreadable")):
            with patch.object(model.os,"O_NOFOLLOW",0x20000,create=True),patch.object(model.os,"O_NONBLOCK",0x800,create=True),patch.object(model.os,"open",side_effect=error):
                value=model.read_status(INSTANCE,now=NOW)
            self.assertEqual(value["reason"],reason);self.assertIsNone(value["automatic_schedule_active"])
