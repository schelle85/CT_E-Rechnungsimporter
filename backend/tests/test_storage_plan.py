from dataclasses import replace
from datetime import datetime
import unittest
from app.storage_plan import StorageError, StorageRequest, filename, path_key, safe_leaf, target_directory, week_key


def moment(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def request(**changes):
    values = dict(scope="synthetic-ap04", source_key="message/attachment-1", original_name="Rechnung.pdf",
                  byte_size=8, sha256="a" * 64, received_at=moment("2026-11-01T23:30:00Z"), category="PDF")
    values.update(changes)
    return StorageRequest(**values)


class StoragePlanTests(unittest.TestCase):
    def test_reception_calendar_and_iso_week_are_separate(self):
        for timestamp, target, week in [
            ("2021-01-01T12:00:00Z", "PDF/2021/1/KW53", "2020-W53"),
            ("2026-11-01T23:30:00Z", "PDF/2026/11/KW45", "2026-W45"),
            ("2026-03-31T22:30:00Z", "PDF/2026/4/KW14", "2026-W14"),
            ("2026-10-25T00:30:00Z", "PDF/2026/10/KW43", "2026-W43"),
            ("2026-10-25T01:30:00Z", "PDF/2026/10/KW43", "2026-W43"),
        ]:
            with self.subTest(timestamp=timestamp):
                self.assertEqual(target_directory("PDF", moment(timestamp)), target)
                self.assertEqual(week_key(moment(timestamp)), week)
        with self.assertRaises(StorageError):
            target_directory("PDF", datetime(2026, 1, 1))

    def test_business_duplicate_uses_processing_week_name_and_size_only(self):
        first = request()
        now = moment("2026-11-13T10:00:00Z")
        for variant in [replace(first, category="Mahnung"), replace(first, sha256="b" * 64),
                        replace(first, received_at=moment("2026-01-01T00:00:00Z")), replace(first, source_key="other")]:
            self.assertEqual(first.duplicate_key(now), variant.duplicate_key(now))
        for variant in [replace(first, original_name="rechnung.pdf"), replace(first, byte_size=9), replace(first, scope="other")]:
            self.assertNotEqual(first.duplicate_key(now), variant.duplicate_key(now))
        self.assertNotEqual(first.duplicate_key(now), first.duplicate_key(moment("2026-11-16T00:00:00Z")))
        self.assertEqual(first.duplicate_key(moment("2020-12-31T12:00:00Z")), first.duplicate_key(moment("2021-01-01T12:00:00Z")))

    def test_names_preserved_or_replaced_as_one_bounded_component(self):
        token = "1" * 32
        for name in ["Rechnung.pdf", "Müller & Söhne.xml", "invoice", "a" * 176 + ".pdf"]:
            self.assertTrue(safe_leaf(name))
            self.assertEqual(filename(name, token), name)
            result = filename(name, token, collision=True)
            self.assertIn("--" + token, result)
            self.assertLessEqual(len(result.encode("utf-8")), 255)
        for name in ["../evil.pdf", "..", ".hidden", "a/b.pdf", "a\\b.pdf", "a:stream.pdf", "NUL.pdf",
                     "lpt¹.xml", "COM1", "A?.pdf", "trailing. ", "a\x00.pdf", "a\u202e.pdf", "ä" * 100 + ".pdf"]:
            with self.subTest(name=ascii(name)):
                self.assertFalse(safe_leaf(name))
                self.assertRegex(filename(name, token), r"^document-[0-9a-f]{32}\.[A-Za-z0-9]{1,12}$")

    def test_case_collision_does_not_change_exact_original_name_rule(self):
        self.assertEqual(path_key("test", "PDF/a.pdf"), path_key("test", "PDF/A.pdf"))
        first, second = request(original_name="é.pdf"), request(original_name="e\u0301.pdf")
        self.assertNotEqual(first.duplicate_key(moment("2026-11-13T00:00:00Z")), second.duplicate_key(moment("2026-11-13T00:00:00Z")))

    def test_unrecognized_and_invalid_input_cannot_plan_a_write(self):
        for changes in [dict(category="unknown"), dict(status="unknown"), dict(status="ignored"), dict(status="failed"),
                        dict(byte_size=True), dict(byte_size=-1), dict(byte_size=25 * 1024 * 1024 + 1),
                        dict(sha256="not-a-hash"), dict(source_key=""), dict(original_name="\ud800.pdf")]:
            with self.subTest(changes=ascii(changes)), self.assertRaises(StorageError):
                request(**changes)
        with self.assertRaises(StorageError):
            filename("test.pdf", "../bad")
