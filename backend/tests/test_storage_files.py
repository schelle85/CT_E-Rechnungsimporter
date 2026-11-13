from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from app.storage_files import CifsFiles, StorageCollision, destination_binding, mount_identity, parse_mounts, rename_no_replace
from app.storage_plan import StorageError
from test_storage_plan import request

MOUNTS = "41 25 0:39 / /synthetic\\040share rw,relatime - cifs //files.example.invalid/import$ rw,cache=strict,vers=3.1.1\n"


class MountGateTests(unittest.TestCase):
    def test_actual_fd_mount_id_source_device_and_options_required(self):
        info = type("Status", (), {"st_dev": 39})()
        def read(path, **_):
            return "mnt_id:\t41\n" if "fdinfo" in str(path) else MOUNTS
        with patch.object(Path, "read_text", read), patch("app.storage_files.os.fstat", return_value=info), \
             patch("app.storage_files.os.major", return_value=0, create=True), patch("app.storage_files.os.minor", return_value=39, create=True):
            self.assertEqual(mount_identity(7, "//files.example.invalid/import$"), (41, 39))
            with self.assertRaises(StorageError):
                mount_identity(7, "//other.example.invalid/import$")
            for changed in [MOUNTS.replace("- cifs", "- ext4"), MOUNTS.replace("0:39", "0:40"),
                            MOUNTS.replace("cache=strict", "cache=loose"), MOUNTS.replace("cache=strict", "cache=strict,nostrictsync")]:
                with self.subTest(changed=changed), patch.object(Path, "read_text", lambda path, **_: "mnt_id:\t41\n" if "fdinfo" in str(path) else changed):
                    with self.assertRaises(StorageError):
                        mount_identity(7, "//files.example.invalid/import$")
        self.assertEqual(parse_mounts(MOUNTS)[41]["point"], "/synthetic share")
        with patch.object(Path, "read_text", return_value=MOUNTS):
            first = destination_binding("/synthetic share/Test/AP04", 41, "_staging")
        bind = MOUNTS.replace("/ /synthetic\\040share", "/Test/AP04 /container")
        with patch.object(Path, "read_text", return_value=bind):
            self.assertEqual(destination_binding("/container", 41, "_staging"), first)
            self.assertNotEqual(destination_binding("/container/other", 41, "_staging"), first)
        with self.assertRaises(StorageError):
            parse_mounts("invalid mount record")


@unittest.skipUnless(sys.platform == "linux", "Native directory-fd/rename tests require Linux; this is not a CIFS test")
class LinuxFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "share"
        self.root.mkdir()
        self.source = Path(self.temp.name) / "source.pdf"
        self.source.write_bytes(b"synthetic bytes\x00\xff")
        self.item = request(byte_size=self.source.stat().st_size, sha256=hashlib.sha256(self.source.read_bytes()).hexdigest())
        # Only this native local-filesystem test replaces the CIFS gate.
        self.gate = patch("app.storage_files.mount_identity", side_effect=lambda fd, _: (41, os.fstat(fd).st_dev))
        self.gate.start()
        self.addCleanup(self.gate.stop)
        self.binding = patch("app.storage_files.destination_binding", return_value="d" * 64)
        self.binding.start()
        self.addCleanup(self.binding.stop)
        self.files = CifsFiles(str(self.root), "//files.example.invalid/import$", "_staging", staging_excluded=True)
        self.addCleanup(self.files.close)
        self.stage = "a" * 96
        self.target = self.item.target(self.item.key[:32])

    def test_staging_integrity_and_atomic_publish_preserve_bytes(self):
        self.files.stage(self.stage, self.source, self.item)
        self.assertFalse((self.root / "PDF").exists())
        self.files.publish(self.stage, self.target)
        self.assertEqual((self.root / self.target).read_bytes(), self.source.read_bytes())
        self.assertFalse((self.root / "_staging" / self.stage).exists())
        self.assertTrue(self.files.matches(self.target, self.item))
        (self.root / self.target).unlink()  # Synthetic DMS consumption.
        self.assertFalse(self.files.matches(self.target, self.item))

    def test_existing_target_and_racing_publish_never_overwrite(self):
        self.files.stage(self.stage, self.source, self.item)
        target = self.root / self.target
        target.parent.mkdir(parents=True)
        target.write_bytes(b"existing different content")
        with self.assertRaises(StorageCollision):
            self.files.publish(self.stage, self.target)
        self.assertEqual(target.read_bytes(), b"existing different content")
        self.assertTrue((self.root / "_staging" / self.stage).exists())
        other = "b" * 96
        self.files.stage(other, self.source, self.item)
        race_target = self.target + ".race.pdf"
        def publish(name):
            try:
                self.files.publish(name, race_target)
                return "stored"
            except StorageCollision:
                return "collision"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(publish, [self.stage, other]))
        self.assertEqual(sorted(outcomes), ["collision", "stored"])
        self.assertEqual((self.root / race_target).read_bytes(), self.source.read_bytes())

    def test_wrong_content_and_flush_failure_never_create_category(self):
        with self.assertRaises(StorageError):
            self.files.stage(self.stage, self.source, replace(self.item, sha256="0" * 64))
        with patch("app.storage_files.os.fsync", side_effect=OSError(errno.EIO, "synthetic flush failure")):
            with self.assertRaises(OSError):
                self.files.stage("b" * 96, self.source, self.item)
        self.assertFalse((self.root / "PDF").exists())

    def test_symlink_and_mount_change_fail_before_writes(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.root / "_staging").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            self.files.stage(self.stage, self.source, self.item)
        self.assertEqual(list(outside.iterdir()), [])
        (self.root / "_staging").unlink()
        with patch("app.storage_files.mount_identity", side_effect=StorageError("storage_cifs_required")):
            with self.assertRaises(StorageError):
                self.files.stage(self.stage, self.source, self.item)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_root_is_not_created_and_no_rename_fallback(self):
        missing = self.root / "absent"
        with self.assertRaises(FileNotFoundError):
            CifsFiles(str(missing), "//files.example.invalid/import$", "_staging", staging_excluded=True)
        self.assertFalse(missing.exists())
        with patch("app.storage_files.ctypes.CDLL", return_value=object()):
            with self.assertRaises(StorageError):
                rename_no_replace(1, "source", 2, "target")
