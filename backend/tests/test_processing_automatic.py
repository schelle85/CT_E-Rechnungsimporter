"""AP08 journal fairness and known-rejected read throttling; no external IO."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from app.graph import GraphError
from app.processing import ProcessingService
from app.processing_state import messages
import test_processing_state as fixtures
from test_processing_plan import attachment,mail


class ProcessingAutomaticTests(unittest.TestCase):
    def setUp(self):fixtures.ProcessingStateTests.setUp(self)

    def test_more_than_fifty_due_rows_rotate_after_progress_and_keep_filters(self):
        keys=[self.key]+[self.store.register(self.mailbox,mail(id="synthetic-"+str(i)),[attachment()]) for i in range(54)]
        with self.engine.begin() as c:
            c.execute(messages.update().where(messages.c.message_key==keys[0]).values(state="operator_required",updated_at=0))
            c.execute(messages.update().where(messages.c.message_key==keys[1]).values(next_attempt=2001,updated_at=0))
            c.execute(messages.update().where(messages.c.message_key==keys[2]).values(owner="a"*32,lease_until=2001,updated_at=0))
            c.execute(messages.update().where(messages.c.message_key==keys[3]).values(revision=1,updated_at=0))
        first=self.store.due("inbox",limit=50)
        self.assertEqual(len(first),50);self.assertFalse(set(first)&set(keys[:4]))
        selected=first[0];claim=self.store.claim(selected)
        self.now[0]=1001;self.store.release(selected,claim["owner"],claim["revision"])
        second=self.store.due("inbox",limit=50)
        self.assertNotIn(selected,second)
        self.assertEqual(set(first)|set(second),set(keys[4:]))
        self.assertEqual(self.store.due("corrections",limit=50),[keys[3]])

    def test_known_429_read_preserves_pending_journal_and_retry_after_without_effect(self):
        files=SimpleNamespace(destination_key="synthetic")
        service=ProcessingService(self.store,None,files,files,"synthetic")
        with patch.object(service,"_input",side_effect=GraphError("graph_read_failed",status=429,retry_not_before=9999)):
            result=service.advance(self.key,"/unused")
        self.assertEqual(result.status,"busy")
        row=self.store.get_attachments(self.key)[0]
        self.assertIsNone(row["effective_status"]);self.assertIsNone(row["effect_key"])
        message=self.store.get_message(self.key)
        self.assertEqual(message["next_attempt"],9999);self.assertIsNone(message["owner"])
        self.assertEqual(self.store.due("inbox"),[])
