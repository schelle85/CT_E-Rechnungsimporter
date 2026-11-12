import json
import contextlib
import io
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import httpx
import sqlalchemy as sa
from app.database import make_engine
from app.graph import GraphClient, GraphError
from app.graph_actions import GraphActions, FOLDERS
from app.graph_state import ActionStore, metadata, actions
from test_graph import CONFIG, Credential
from test_graph_mail import InboxDouble, message


class ActionRemote(InboxDouble):
    def __init__(self):
        super().__init__()
        self.folders = {}
        self.writes = []
        self.write_failure = None
        self.after_write_reads_fail = False

    def __call__(self, request):
        path = request.url.path.split("/users/invoice@example.invalid")[-1]
        if request.method != "GET":
            self.calls.append(request)
            self.writes.append(request)
            payload = json.loads(request.content)
            applied = self.write_failure != "before"
            if applied:
                if path == "/mailFolders/inbox/childFolders":
                    name = payload["displayName"]
                    self.folders[name] = {"id": "folder-" + name, "displayName": name, "parentFolderId": "inbox", "isHidden": False}
                elif path.endswith("/move"):
                    mid = path.split("/")[2]
                    self.messages[mid]["parentFolderId"] = payload["destinationId"]
                elif request.method == "PATCH":
                    mid = path.split("/")[2]
                    self.messages[mid]["flag"].update(payload["flag"])
                else:
                    raise AssertionError("Unexpected mutation")
            if self.write_failure:
                raise httpx.ReadTimeout("synthetic uncertain write", request=request)
            return httpx.Response(200 if request.method == "PATCH" else 201, json={"body": "synthetic write response never consumed"})
        if self.writes and self.after_write_reads_fail:
            self.calls.append(request)
            return httpx.Response(403)
        if path == "/mailFolders/inbox/childFolders":
            self.calls.append(request)
            if self.override:
                response = self.override(request)
                if response is not None:
                    return response
            return httpx.Response(200, json={"value": list(self.folders.values())})
        return super().__call__(request)


class GraphActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = make_engine() if os.environ.get("INTEGRATION_DB") == "1" else sa.create_engine("sqlite:///" + str(Path(self.temp.name) / "actions.sqlite"))
        self.addCleanup(self.engine.dispose)
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(actions.delete())
        self.now = [1000]
        self.store = ActionStore(self.engine, clock=lambda: self.now[0])
        self.remote = ActionRemote()
        self.http = httpx.Client(transport=httpx.MockTransport(self.remote), trust_env=False)
        self.addCleanup(self.http.close)
        self.client = GraphClient(CONFIG, Credential(), self.http, sleep=lambda _: None)
        self.api = GraphActions(self.client, self.store)

    def ready_folders(self):
        self.remote.folders = {name: {"id": "folder-" + name, "displayName": name, "parentFolderId": "inbox", "isHidden": False} for name in FOLDERS}

    def test_folders_create_once_and_reuse_full_paging(self):
        self.assertEqual(set(self.api.ensure_folders()), set(FOLDERS))
        self.assertEqual(len(self.remote.writes), 5)
        self.assertEqual(set(self.api.ensure_folders()), set(FOLDERS))
        self.assertEqual(len(self.remote.writes), 5)
        rows = list(self.remote.folders.values())
        collection = self.client.root + "/mailFolders/inbox/childFolders"
        def pages(request):
            if not request.url.path.endswith("/childFolders"):
                return None
            if request.url.params.get("$skiptoken"):
                return httpx.Response(200, json={"value": rows[2:]})
            self.assertEqual(request.url.params["includeHiddenFolders"], "true")
            return httpx.Response(200, json={"value": rows[:3], "@odata.nextLink": collection + "?$skiptoken=next"})
        self.remote.override = pages
        self.assertEqual(len(self.api.folders()), 5)

    def test_ambiguous_hidden_or_wrong_parent_folder_never_mutates(self):
        for problem in ("duplicate", "hidden", "parent"):
            self.ready_folders()
            if problem == "duplicate":
                self.remote.folders["duplicate"] = dict(self.remote.folders["Success"], id="another", displayName="success")
            elif problem == "hidden":
                self.remote.folders["Success"]["isHidden"] = True
            else:
                self.remote.folders["Success"]["parentFolderId"] = "elsewhere"
            with self.subTest(problem=problem), self.assertRaises(GraphError):
                self.api.ensure_folders()
        self.assertFalse(self.remote.writes)

    def test_folder_timeout_after_apply_reconciles_without_second_post(self):
        self.remote.write_failure = "after"
        self.assertEqual(len(self.api.ensure_folders()), 5)
        self.assertEqual(len(self.remote.writes), 5)
        self.api.ensure_folders()
        self.assertEqual(len(self.remote.writes), 5)

    def test_flag_move_are_separate_and_keep_immutable_id_and_flag(self):
        self.ready_folders()
        self.assertEqual(self.api.flag("m1"), "m1")
        self.assertEqual(self.api.move("m1", "Success"), "m1")
        self.assertEqual(self.remote.messages["m1"]["flag"]["flagStatus"], "flagged")
        self.assertEqual(self.remote.messages["m1"]["parentFolderId"], "folder-Success")
        self.api.flag("m1")
        self.api.move("m1", "Success")
        self.assertEqual([r.method for r in self.remote.writes], ["PATCH", "POST"])
        self.assertTrue(all(r.headers["Prefer"] == 'IdType="ImmutableId"' for r in self.remote.writes))
        with self.engine.connect() as c:
            self.assertEqual(set(c.execute(sa.select(actions.c.kind)).scalars()), {"flag", "move"})

    def test_every_direct_mutation_blocks_old_or_missing_time(self):
        self.ready_folders()
        for stamp in ("2026-11-30T22:59:59.999999Z", None):
            for operation in (self.api.flag, lambda mid: self.api.move(mid, "Success")):
                self.remote.messages["m1"] = message(timestamp=stamp)
                with self.subTest(stamp=stamp), self.assertRaises(GraphError):
                    operation("m1")
        self.assertFalse(self.remote.writes)

    def test_completed_flag_and_invalid_destination_are_preserved(self):
        self.ready_folders()
        self.remote.messages["m1"] = message(flag="complete")
        with self.assertRaises(GraphError):
            self.api.flag("m1")
        for destination in ("archive", "../Success", "foreign-folder-id"):
            with self.assertRaises(GraphError):
                self.api.move("m1", destination)
        self.assertFalse(self.remote.writes)
        self.assertEqual(self.remote.messages["m1"]["flag"]["flagStatus"], "complete")

    def test_lost_response_after_move_then_new_process_state_reconciles(self):
        self.ready_folders()
        self.remote.write_failure = "after"
        self.remote.after_write_reads_fail = True
        with self.assertRaises(GraphError):
            self.api.move("m1", "Success")
        self.assertEqual(len(self.remote.writes), 1)
        self.remote.after_write_reads_fail = False
        self.remote.write_failure = None
        fresh = GraphActions(self.client, ActionStore(self.engine, clock=lambda: self.now[0]))
        self.assertEqual(fresh.move("m1", "Success"), "m1")
        self.assertEqual(len(self.remote.writes), 1)

    def test_crash_before_local_confirmation_and_lease_expiry(self):
        self.ready_folders()
        with patch.object(self.store, "finish", side_effect=RuntimeError("synthetic process exit after server apply")):
            with self.assertRaises(RuntimeError):
                self.api.flag("m1")
        with self.assertRaises(GraphError) as raised:
            self.api.flag("m1")
        self.assertEqual(raised.exception.code, "graph_action_busy")
        self.now[0] += 301
        fresh = GraphActions(self.client, ActionStore(self.engine, clock=lambda: self.now[0]))
        self.assertEqual(fresh.flag("m1"), "m1")
        self.assertEqual(len(self.remote.writes), 1)

    def test_uncertain_not_applied_requires_operator_no_retry(self):
        self.ready_folders()
        self.remote.write_failure = "before"
        with self.assertRaises(GraphError):
            self.api.move("m1", "Success")
        self.remote.write_failure = None
        with self.assertRaises(GraphError) as raised:
            self.api.move("m1", "Success")
        self.assertEqual(raised.exception.code, "graph_action_operator_required")
        self.assertEqual(len(self.remote.writes), 1)

    def test_folder_timeout_then_restart_reconciles_existing_folder(self):
        self.remote.write_failure = "after"
        self.remote.after_write_reads_fail = True
        with self.assertRaises(GraphError):
            self.api.ensure_folders()
        self.remote.write_failure = None
        self.remote.after_write_reads_fail = False
        self.assertEqual(len(GraphActions(self.client, ActionStore(self.engine)).ensure_folders()), 5)
        self.assertEqual(len(self.remote.writes), 5)

    def test_crash_before_write_is_not_replayed_after_lease(self):
        with patch.object(self.api, "folders", side_effect=RuntimeError("synthetic crash before write")):
            with self.assertRaises(RuntimeError):
                self.api.ensure_folders()
        self.now[0] += 301
        with self.assertRaises(GraphError) as raised:
            self.api.ensure_folders()
        self.assertEqual(raised.exception.code, "graph_action_operator_required")
        self.assertFalse(self.remote.writes)

    def test_conflicting_move_target_and_case_sensitive_message_id(self):
        self.ready_folders()
        self.api.move("m1", "Success")
        with self.assertRaises(GraphError) as raised:
            self.api.move("m1", "Failed")
        self.assertEqual(raised.exception.code, "graph_action_conflict")
        self.remote.messages["M1"] = message("M1")
        self.api.move("M1", "Failed")
        self.assertEqual(len(self.remote.writes), 2)

    def test_operator_child_or_db_failure_remains_uncertain(self):
        from app.graph_cli import main
        output = io.StringIO()
        with patch("sys.argv", ["graph", "flag", "--message-id", "synthetic-message"]), patch(
                "app.graph_cli.bounded_operation", return_value={"ok": False, "code": "graph_runtime_unavailable"}), contextlib.redirect_stdout(output):
            self.assertEqual(main(), 1)
        self.assertTrue(json.loads(output.getvalue())["uncertain"])

    @unittest.skipUnless(os.environ.get("INTEGRATION_DB") == "1", "Row-lock concurrency needs real MariaDB")
    def test_real_mariadb_only_one_concurrent_claim(self):
        barrier = threading.Barrier(2)
        def claim():
            barrier.wait(timeout=5)
            try:
                return self.store.claim(CONFIG.mailbox, "move", "concurrent-message", "Success")
            except GraphError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sum(isinstance(r, tuple) and r[2] for r in results), 1)
        self.assertIn("graph_action_busy", results)


if __name__ == "__main__":
    unittest.main()
