"""Historical renewal display after source changes, with actual cleanup validation."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import rotation_schedule as schedule
from app.graph import GraphError
from app.rotation_adoption import AdoptionJournal
from app.rotation_cleanup import CleanupJournal
from test_rotation_cleanup import CleanupTests


class RenewalHistoryTests(unittest.TestCase):
    def setUp(self):
        fixture = CleanupTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        fixture.cleanup.plan(fixture.operation)
        fixture.remove()
        self.completed = fixture.cleanup.finish_local(fixture.operation, fixture.new)
        self.assertEqual(self.completed["phase"], "completed")
        self.old_access = fixture.fixture.binding
        self.new_access = replace(self.old_access, source_commit="b" * 40)
        self.journal = schedule.ScheduleJournal(self.root)
        self.journal.renewed(fixture.operation, self.completed)
        self.journal.attempt(fixture.operation, fixture.now)
        self.store = SimpleNamespace(
            status=lambda: dict(active_operation=None, enabled=True, revision=9),
            read=lambda _: dict(state="completed", error_code=None),
        )

    def overview(self, access):
        # A completed bootstrap uses a fresh operation, without a mutable adoption record.
        release = dict(mode="allowed", operation_id=str(uuid4()), **access.fields())
        gate = SimpleNamespace(read=lambda: release, _bound=lambda _: None, _material=lambda *args: None)
        host = AdoptionJournal(self.root, access)
        with patch("app.graph_access.AccessGate", return_value=gate):
            return schedule.overview(self.store, host, access, self.fixture.new)

    def test_forward_and_return_source_keep_history_without_cleanup_effects(self):
        before = {p.name: p.read_bytes() for p in self.root.directory.iterdir() if p.is_file()}
        with (
            patch.object(self.root, "_write", side_effect=AssertionError("history must be read-only")),
            patch.object(CleanupJournal, "plan", side_effect=AssertionError("no cleanup plan")),
            patch.object(CleanupJournal, "remove", side_effect=AssertionError("no cleanup effect")),
        ):
            old = self.overview(self.old_access)
            new = self.overview(self.new_access)
            returned = self.overview(self.old_access)
        for value in (new, returned):
            self.assertEqual(value["last_renewal"], old["last_renewal"])
            self.assertEqual(value["last_attempt"], old["last_attempt"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.directory.iterdir() if p.is_file()})
        self.assertEqual(self.fixture.graph.removes, 1)

    def test_historical_projection_rejects_other_bindings_and_invalid_proofs(self):
        invalid = [
            dict(scope_key="f" * 64), dict(deployment_id=str(uuid4())), dict(instance_id=str(uuid4())),
            dict(source_commit="not-a-commit"), dict(version=2), dict(operation_id=str(uuid4())),
            dict(phase="planned"), dict(phase="removal_unknown"), dict(phase="local_pending"),
            dict(not_before=self.completed["not_before"] + 1), dict(adoption_seal="bad"),
            dict(proof=dict(self.completed["proof"], fingerprint="f" * 64)),
            dict(proof=dict(self.completed["proof"], scope_key="f" * 64)),
            dict(proof=dict(self.completed["proof"], at=self.completed["not_before"] - 61)),
            dict(new=dict(self.completed["new"], fingerprint="f" * 64)),
            dict(files=[dict(name="invalid.pem", receipt_hash="a" * 64)]),
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                self.root._write(self.fixture.operation + ".cleanup.json", dict(self.completed, **changes))
                with self.assertRaises(GraphError):
                    self.overview(self.new_access)
        self.root._write(self.fixture.operation + ".cleanup.json", self.completed)
        original_binding = self.root.binding
        self.root.binding = replace(original_binding, application_id=str(uuid4()))
        try:
            with self.assertRaises(GraphError):
                self.overview(self.new_access)
        finally:
            self.root.binding = original_binding

    def test_mutable_cleanup_still_requires_current_source(self):
        historical = CleanupJournal(AdoptionJournal(self.root, self.new_access))
        with self.assertRaisesRegex(GraphError, "rotation_cleanup_invalid"):
            historical.state(self.fixture.operation)
        with self.assertRaisesRegex(GraphError, "rotation_cleanup_invalid"):
            historical.plan(self.fixture.operation)
        with self.assertRaisesRegex(GraphError, "rotation_cleanup_invalid"):
            historical.remove(self.fixture.operation, self.fixture.graph, self.fixture.new,
                              self.fixture.proof(), self.fixture.now)
        self.assertEqual(self.fixture.graph.removes, 1)

    def test_historical_projection_retains_schedule_identity_checks(self):
        saved = deepcopy(self.journal.state())
        for field, value in (("at", saved["last_renewal"]["at"] + 1), ("fingerprint", "f" * 64)):
            with self.subTest(field=field):
                self.journal.save(last_renewal=dict(saved["last_renewal"], **{field: value}))
                with self.assertRaises(GraphError):
                    self.overview(self.new_access)
        self.journal.save(last_renewal=saved["last_renewal"])
