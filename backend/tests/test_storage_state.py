from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
import unittest
import sqlalchemy as sa
from app.storage_plan import StorageError
from app.storage_state import StorageStore, metadata, operations
from test_storage_plan import moment, request


class StorageStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        if os.environ.get("INTEGRATION_DB") == "1":
            from app.database import make_engine
            self.engine = make_engine()  # Only the isolated test runner may set INTEGRATION_DB.
        else:
            self.engine = sa.create_engine("sqlite:///" + str(Path(self.temp.name) / "storage.sqlite"))
        self.addCleanup(self.engine.dispose)
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(operations.delete())
        self.now = [int(moment("2026-11-13T10:00:00Z").timestamp())]
        self.store = StorageStore(self.engine, clock=lambda: self.now[0])

    def stored(self, item):
        row = self.store.claim(item)
        self.store.begin_publication(item.key, row["owner"])
        self.store.finish(item.key, row["owner"], "stored")
        return self.store.get(item.key)

    def test_receipt_survives_consumption_and_source_resume_after_week_change(self):
        item = request()
        receipt = self.stored(item)
        # No filesystem existence participates in the persistent business decision.
        duplicate = self.store.claim(request(source_key="other", sha256="b" * 64, category="Mahnung"))
        self.assertEqual(duplicate["state"], "duplicate")
        self.assertEqual(duplicate["target"], receipt["target"])
        self.now[0] += 7 * 86400
        self.assertEqual(self.store.claim(item)["state"], "stored")
        self.assertEqual(self.store.claim(request(source_key="other", sha256="b" * 64, category="Mahnung"))["state"], "duplicate")
        fresh = self.store.claim(request(source_key="next-week"))
        self.assertEqual(fresh["mode"], "stage")
        self.assertNotEqual(fresh["dedupe_week"], receipt["dedupe_week"])
        self.assertNotEqual(fresh["target"], receipt["target"])

    def test_pending_duplicate_waits_and_keeps_original_week_assignment(self):
        first, second = request(), request(source_key="second")
        owner = self.store.claim(first)
        self.assertEqual(self.store.claim(second)["mode"], "busy")
        week = self.store.get(second.key)["dedupe_week"]
        self.now[0] += 7 * 86400
        self.store.finish(first.key, owner["owner"], "operator_required", error="synthetic_uncertain")
        self.assertEqual(self.store.claim(second)["mode"], "operator_required")
        self.assertEqual(self.store.get(second.key)["dedupe_week"], week)

    def test_same_name_different_size_and_case_collide_physically_only(self):
        first = self.stored(request())
        different = self.store.claim(request(source_key="different-size", byte_size=9))
        case = self.store.claim(request(source_key="different-case", original_name="rechnung.pdf"))
        for row in (different, case):
            self.assertEqual(row["mode"], "stage")
            self.assertEqual(row["collision"], 1)
            self.assertIn("--", row["target"])
            self.assertNotEqual(row["target"], first["target"])
        with self.assertRaises(StorageError):
            self.store.claim(request(byte_size=9))  # Stable source cannot change content.

    def test_expired_stager_is_fenced_but_publishing_is_never_reacquired(self):
        item = request()
        old = self.store.claim(item)
        self.assertEqual(self.store.claim(item)["mode"], "busy")
        self.now[0] += self.store.LEASE_SECONDS + 1
        current = self.store.claim(item)
        self.assertEqual(current["mode"], "stage")
        self.assertNotEqual(current["stage_name"], old["stage_name"])
        with self.assertRaises(StorageError):
            self.store.begin_publication(item.key, old["owner"])
        self.store.begin_publication(item.key, current["owner"])
        self.now[0] += self.store.LEASE_SECONDS + 1
        resumed = self.store.claim(item)
        self.assertEqual(resumed["mode"], "reconcile")
        with self.assertRaises(StorageError):
            self.store.begin_publication(item.key, resumed["owner"])
        with self.assertRaises(StorageError):
            self.store.finish(item.key, current["owner"], "stored")
        self.store.finish(item.key, resumed["owner"], "operator_required", error="storage_publication_uncertain")
        self.assertEqual(self.store.claim(item)["mode"], "reconcile")
        self.assertEqual(self.store.get(item.key)["publication_attempts"], 1)

    def test_only_definitive_collision_allows_one_alternative(self):
        item = request()
        row = self.store.claim(item)
        self.store.begin_publication(item.key, row["owner"])
        alternate = self.store.collision(item, row["owner"])
        self.assertNotEqual(alternate, row["target"])
        self.store.begin_publication(item.key, row["owner"])
        with self.assertRaises(StorageError):
            self.store.collision(item, row["owner"])
        self.assertEqual(self.store.get(item.key)["publication_attempts"], 2)

    def test_concurrent_claims_reserve_one_source_and_one_business_key(self):
        item = request()
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(lambda _: self.store.claim(item), range(6)))
        self.assertEqual(sum(row["mode"] == "stage" for row in rows), 1)
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(lambda index: self.store.claim(request(source_key=f"competitor-{index}")), range(6)))
        self.assertTrue(all(row["mode"] == "busy" for row in rows))
        with self.engine.connect() as connection:
            count = connection.execute(sa.select(sa.func.count()).select_from(operations).where(operations.c.dedupe_key.is_not(None))).scalar_one()
        self.assertEqual(count, 1)
