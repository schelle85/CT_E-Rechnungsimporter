"""Read only already registered attachments in their journal-bound known folder."""
import json
from app.graph import GraphError
from app.graph_actions import GraphActions
from app.graph_mail import Mailbox
from app.processing_plan import message_key


class JournalMailbox(Mailbox):
    def __init__(self, client, receipt, attachment_receipts):
        super().__init__(client)
        if receipt["message_key"] != message_key(client.config.mailbox, receipt["graph_id"]):
            raise GraphError("graph_journal_identity_invalid")
        self.receipt = receipt
        self.expected = {}
        for row in attachment_receipts:
            if row["message_key"] != receipt["message_key"]:
                raise GraphError("graph_journal_identity_invalid")
            self.expected[row["graph_id"]] = json.loads(row["source"])

    def inbox_id(self):
        actual_inbox = Mailbox(self.client).inbox_id()
        folders = GraphActions(self.client, None).folders()
        if (self.receipt["source_parent"] != actual_inbox
                or self.receipt["current_parent"] not in {actual_inbox, *folders.values()}):
            raise GraphError("graph_journal_parent_invalid")
        return self.receipt["current_parent"]

    def message(self, message_id):
        if message_id != self.receipt["graph_id"]:
            raise GraphError("graph_journal_identity_invalid")
        item = super().message(message_id)
        if item.received_at.isoformat() != self.receipt["received_at"] or item.parent_id != self.inbox_id():
            raise GraphError("graph_journal_source_changed")
        return item

    def attachments(self, message_id, started=None):
        items = super().attachments(message_id, started)
        for value in items:
            current = [value.id, value.name, value.size, value.content_type, value.inline, value.kind]
            if self.expected.get(value.id) != current:
                raise GraphError("graph_journal_manifest_changed")
        # Missing siblings do not invalidate an already confirmed storage receipt.
        # A requested missing source still fails attachment_content's exact-ID selection.
        return items

    def messages(self, started=None):
        raise GraphError("graph_journal_scan_forbidden")

    def scan(self):
        raise GraphError("graph_journal_scan_forbidden")
