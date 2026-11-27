from dataclasses import replace
from datetime import datetime
from itertools import combinations
import unittest
from app.graph_mail import Attachment, Message
from app.processing_plan import (AttachmentOutcome as Outcome, ProcessingError, attachment_key, checked_finding,
                                 correction_allowed, mail_decision, message_key, requires_flag, source_manifest)


def mail(**changes):
    value = Message("immutable-message", datetime.fromisoformat("2026-11-23T00:00:00+01:00"), "inbox", "notFlagged")
    return replace(value, **changes)


def attachment(aid="a1", **changes):
    return replace(Attachment(aid, "invoice.pdf", 999, "application/pdf", False, "file"), **changes)


class ProcessingPlanTests(unittest.TestCase):
    def test_bounded_warning_codes_preserve_legacy_findings_and_reject_unbound_warnings(self):
        value=dict(status='recognized',category='E-Rechnung',reason='hybrid_invoice_structure',format='ZUGFeRD/Factur-X',
                   method='structure',original_sha256='a'*64,rule_version='ap03-4')
        self.assertEqual(checked_finding(value,'a'*64),value)
        allowed=['pdf_stream_missing_checksum','hybrid_xrechnung_metadata_version']
        self.assertEqual(checked_finding(dict(value,warnings=allowed),'a'*64)['warnings'],allowed)
        for warnings in ([],['private/path'],['pdf_stream_missing_checksum']*2,['pdf_stream_missing_checksum']*3,[{}]):
            with self.assertRaises(ProcessingError):checked_finding(dict(value,warnings=warnings),'a'*64)
        for changes in (dict(status='failed',category=None),dict(category='PDF'),dict(method='ocr'),dict(reason='different')):
            with self.assertRaises(ProcessingError):checked_finding(dict(value,warnings=allowed,**changes),'a'*64)

    def test_all_priority_edges_and_independent_attachment_order(self):
        priorities = [(Outcome("failed"), "Failed"), (Outcome("unknown"), "unzugeordnet"),
                      (Outcome("recognized", "PDF", "duplicate"), "unzugeordnet"),
                      (Outcome("recognized", "Mahnung", "stored"), "Mahnung"),
                      (Outcome("recognized", "PDF", "stored"), "Nachfragen"),
                      (Outcome("recognized", "Zahlungsavis", "stored"), "Zahlungsavis"),
                      (Outcome("recognized", "E-Rechnung", "stored"), "Success")]
        for (first, target), (second, _) in combinations(priorities, 2):
            for values in ((first, second), (second, first)):
                with self.subTest(values=values):
                    self.assertEqual(mail_decision(values).destination, target)
        self.assertEqual(mail_decision([]).destination, "unzugeordnet")
        self.assertEqual(mail_decision([Outcome("ignored")]).destination, "unzugeordnet")
        self.assertEqual(mail_decision([Outcome("unknown")]).state, "waiting_correction")
        self.assertEqual(mail_decision([Outcome("recognized", "PDF", "operator_required")]).state, "operator_required")
        self.assertIsNone(mail_decision([Outcome("recognized", "PDF", "operator_required")]).destination)

    def test_pending_is_not_a_duplicate_or_completed_mail(self):
        for value in (Outcome("pending"), Outcome("recognized", "PDF"), Outcome("recognized", "PDF", "busy")):
            with self.subTest(value=value), self.assertRaises(ProcessingError):
                mail_decision([Outcome("failed"), value])

    def test_source_identity_is_case_sensitive_and_independent_of_decision_and_week(self):
        first = attachment_key("invoice@example.invalid", "MessageA", "AttachmentA")
        self.assertEqual(first, attachment_key("INVOICE@example.invalid", "MessageA", "AttachmentA"))
        self.assertNotEqual(first, attachment_key("invoice@example.invalid", "messagea", "AttachmentA"))
        self.assertNotEqual(first, attachment_key("invoice@example.invalid", "MessageA", "attachmenta"))
        self.assertNotEqual(first, attachment_key("other@example.invalid", "MessageA", "AttachmentA"))
        self.assertNotEqual(message_key("invoice@example.invalid", "MessageA"), first)

    def test_manifest_counts_actual_attachments_without_inline_signature_or_page_overlap(self):
        signature = attachment("signature", inline=True, content_type="image/png")
        first, second = attachment(), attachment("a2", inline=True)
        snapshot = source_manifest("invoice@example.invalid", mail(), [first, first, signature])
        finding = {"status": "ignored", "category": None, "reason": "unsupported_attachment",
                   "original_sha256": "a" * 64, "rule_version": "ap03-4"}
        self.assertFalse(requires_flag([first, first, signature], {"signature": "a" * 64}, {"signature": finding}))
        self.assertTrue(requires_flag([first, signature]))  # Inline/image metadata alone is no signature proof.
        self.assertEqual(len(snapshot["attachments"]), 2)
        two = source_manifest("invoice@example.invalid", mail(), [signature, second, first])
        self.assertTrue(requires_flag([signature, second, first], {"signature": "a" * 64}, {"signature": finding}))
        self.assertEqual(two["manifest_key"], source_manifest("invoice@example.invalid", mail(), [first, second, signature])["manifest_key"])
        with self.assertRaises(ProcessingError):
            source_manifest("invoice@example.invalid", mail(), [first, replace(first, size=1000)])

    def test_manifest_enforces_inclusive_import_cutoff(self):
        before = mail(received_at=datetime.fromisoformat("2026-11-22T22:59:59.999999Z"))
        with self.assertRaises(ProcessingError) as error:
            source_manifest("invoice@example.invalid", before, [])
        self.assertEqual(error.exception.code, "processing_before_cutoff")
        for stamp in ("2026-11-22T23:00:00+00:00", "2026-11-22T23:00:00.000001+00:00"):
            with self.subTest(stamp=stamp):
                item = mail(received_at=datetime.fromisoformat(stamp))
                manifest = source_manifest("invoice@example.invalid", item, [attachment()])
                self.assertEqual(manifest["received_at"], stamp)

    def test_only_frozen_classifier_status_category_version_and_hash_combinations(self):
        good = {"status": "recognized", "category": "PDF", "reason": "invoice_fields", "format": "PDF",
                "method": "pdf_text", "original_sha256": "a" * 64, "rule_version": "ap03-4"}
        self.assertEqual(checked_finding(good, "a" * 64), good)
        for change in ({"status": "other"}, {"category": "Other"}, {"category": []}, {"rule_version": "other"},
                       {"original_sha256": "b" * 64}, {"reason": "raw\ntext"}, {"status": "unknown"}, {"extra": True}):
            with self.subTest(change=change), self.assertRaises(ProcessingError):
                checked_finding(dict(good, **change), "a" * 64)

    def test_structural_unknown_is_not_a_manual_document_type_correction(self):
        ordinary = {"status": "unknown", "reason": "ambiguous_pdf", "method": "pdf_text"}
        self.assertTrue(correction_allowed(ordinary))
        self.assertTrue(correction_allowed(dict(ordinary, method="pdf_text_ocr")))
        for reason in ("hybrid_profile_mismatch", "hybrid_namespace_mismatch", "unsupported_hybrid_version", "ambiguous_embedded_invoice"):
            self.assertFalse(correction_allowed(dict(ordinary, reason=reason)))
        self.assertFalse(correction_allowed(dict(ordinary, status="failed")))
