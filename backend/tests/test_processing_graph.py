from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
import sqlalchemy as sa
from app.graph import GraphClient, GraphError
from app.graph_actions import FOLDERS, GraphActions
from app.graph_mail import Mailbox
from app.graph_state import ActionStore, actions, metadata
from app.processing_graph import JournalMailbox
from app.processing_plan import attachment_key, message_key
from test_graph import CONFIG, Credential
from test_graph_actions import ActionRemote
from test_graph_mail import attachment, message


class ProcessingGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = sa.create_engine("sqlite:///" + str(Path(self.temp.name) / "graph.sqlite"))
        self.addCleanup(self.engine.dispose)
        metadata.create_all(self.engine)
        self.remote = ActionRemote()
        self.remote.folders = {name: {"id": "folder-" + name, "displayName": name, "parentFolderId": "inbox", "isHidden": False} for name in FOLDERS}
        self.http = httpx.Client(transport=httpx.MockTransport(self.remote), trust_env=False)
        self.addCleanup(self.http.close)
        self.client = GraphClient(CONFIG, Credential(), self.http, sleep=lambda _: None)
        self.store = ActionStore(self.engine)
        self.api = GraphActions(self.client, self.store)
        # Synchronous synthetic transport only; Linux wallclock tests remain in the native suite.
        self.deadline = patch("app.graph_deadline.request_deadline", side_effect=lambda *a, **k: nullcontext())
        self.deadline.start()
        self.addCleanup(self.deadline.stop)
        self.content_deadline = patch("app.graph_mail.request_deadline", side_effect=lambda *a, **k: nullcontext())
        self.content_deadline.start()
        self.addCleanup(self.content_deadline.stop)

    def test_six_targets_and_revision_move_from_unassigned_without_resetting_old_receipt(self):
        self.assertEqual(set(FOLDERS), {"Success", "Failed", "Nachfragen", "Zahlungsavis", "unzugeordnet", "Mahnung"})
        first, second = "a" * 64, "b" * 64
        self.api.move("m1", "unzugeordnet", intent_key=first, source_parent="inbox", guard=lambda: None)
        self.api.move("m1", "Nachfragen", intent_key=second, source_parent="folder-unzugeordnet", guard=lambda: None)
        self.api.flag("m1", intent_key=second, guard=lambda: None)
        count = len(self.remote.writes)
        # Even a late old-generation call cannot mutate or erase its historical success.
        self.api.move("m1", "unzugeordnet", intent_key=first, source_parent="inbox", guard=lambda: None)
        self.api.move("m1", "Nachfragen", intent_key=second, source_parent="folder-unzugeordnet", guard=lambda: None)
        self.assertEqual(len(self.remote.writes), count)
        self.assertEqual(self.remote.messages["m1"]["flag"]["flagStatus"], "flagged")
        with self.engine.connect() as connection:
            states = connection.execute(sa.select(actions.c.state, actions.c.reservations)).all()
        self.assertEqual(states, [("done", 1)] * 3)

    def test_revision_requires_guard_and_destination_id_is_bound(self):
        with self.assertRaises(GraphError):
            self.api.move("m1", "Mahnung", intent_key="a" * 64)
        with self.assertRaises(GraphError):
            self.api.move("m1", "Mahnung", source_parent="folder-unzugeordnet")
        with self.assertRaises(GraphError):
            self.api.move("m1", "Mahnung", intent_key="a" * 64, destination_id="changed", guard=lambda: None)
        self.assertEqual(self.remote.writes, [])

    def test_guard_loss_immediately_before_write_prevents_new_mutation(self):
        checks = []
        def guard():
            checks.append(True)
            if len(checks) >= 3:
                raise GraphError("processing_owner_conflict")
        with self.assertRaises(GraphError):
            self.api.move("m1", "Mahnung", intent_key="a" * 64, source_parent="inbox", guard=guard)
        self.assertEqual(self.remote.writes, [])

    def journal_reader(self):
        self.remote.messages["m1"] = message(parent="folder-unzugeordnet")
        source = attachment()
        self.remote.attachments["m1"] = [source]
        key = message_key(CONFIG.mailbox, "m1")
        receipt = {"message_key": key, "graph_id": "m1", "source_parent": "inbox", "current_parent": "folder-unzugeordnet",
                   "received_at": "2026-11-30T23:00:00+00:00"}
        rows = [{"message_key": key, "graph_id": "a1", "source": json.dumps(["a1", source["name"], 7, source["contentType"], False, "file"])}]
        return JournalMailbox(self.client, receipt, rows), receipt

    def test_journal_content_after_move_while_default_stays_inbox_only(self):
        reader, _ = self.journal_reader()
        with self.assertRaises(GraphError):
            Mailbox(self.client).attachments("m1")
        with reader.attachment_content("m1", "a1") as content:
            self.assertEqual(content.read(), self.remote.raw)
        with self.assertRaises(GraphError):
            reader.scan()
        self.assertTrue(all(request.headers.get("Prefer") == 'IdType="ImmutableId"' for request in self.remote.calls))

    def test_journal_rejects_changed_parent_time_identity_and_manifest(self):
        reader, receipt = self.journal_reader()
        for changed in (message(parent="elsewhere"), message(parent="folder-unzugeordnet", timestamp="2026-12-02T00:00:00Z")):
            self.remote.messages["m1"] = changed
            with self.assertRaises(GraphError):
                reader.attachments("m1")
        self.remote.messages["m1"] = message(parent="folder-unzugeordnet")
        self.remote.attachments["m1"].append(attachment("new"))
        with self.assertRaises(GraphError):
            reader.attachments("m1")
        with self.assertRaises(GraphError):
            reader.message("other")

    def test_default_action_identity_remains_compatible_and_uncertain_revision_never_replays(self):
        key, owner, may_send = self.store.claim(CONFIG.mailbox, "move", "m1", "Mahnung")
        self.assertTrue(may_send)
        self.store.finish(key, owner, "done", result="m1")
        same, _, send = self.store.claim(CONFIG.mailbox, "move", "m1", "Mahnung")
        self.assertEqual(key, same)
        self.assertFalse(send)
        self.remote.write_failure = "before"
        with self.assertRaises(GraphError):
            self.api.move("m1", "Mahnung", intent_key="f" * 64, guard=lambda: None)
        self.remote.write_failure = None
        count = len(self.remote.writes)
        with self.assertRaises(GraphError):
            self.api.move("m1", "Mahnung", intent_key="f" * 64, guard=lambda: None)
        self.assertEqual(len(self.remote.writes), count)
