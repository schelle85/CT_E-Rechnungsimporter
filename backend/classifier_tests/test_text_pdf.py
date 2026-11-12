from hashlib import sha256
import unittest
from unittest.mock import patch
from classifier.core import classify
from classifier.cli import bounded_classify
from classifier.text_pdf import MAX_PAGE_TEXT
from fixtures import hybrid, text_document

INVOICE = ["Beispiel Lieferant GmbH", "Rechnung Nr. SYN-2026-001", "Rechnungsdatum: 12.11.2026",
           "Artikel und Leistungen", "Nettobetrag: 100,00 EUR", "Umsatzsteuer 19%: 19,00 EUR",
           "Gesamtbetrag: 119,00 EUR", "Zahlungsziel 14 Tage"]
ENGLISH = ["Example Supplier", "Invoice No. SYN-2026-001", "Invoice date: 2026-11-12",
           "Services rendered", "Net amount: 100.00 EUR", "VAT: 19.00 EUR", "Total: 119.00 EUR"]
AVIS = ["Beispiel Kunde GmbH", "Zahlungsavis", "Wir überweisen die folgenden Rechnungen.",
        "Rechnungsnummer: SYN-2026-001", "Zahlungsdatum: 12.11.2026", "Zahlbetrag: 119,00 EUR"]


class TextPdfTests(unittest.TestCase):
    def check_pdf(self, pages, status, category=None, reason=None):
        data = text_document(pages)
        before = sha256(data).hexdigest()
        result = classify(data)
        self.assertEqual(result["status"], status, result)
        self.assertEqual(result["category"], category, result)
        if reason:
            self.assertEqual(result["reason"], reason)
        self.assertEqual(result["original_sha256"], before)
        self.assertNotIn("SYN-2026-001", str(result))
        return result

    def test_german_invoice_and_umlauts(self):
        self.check_pdf([INVOICE + ["Vielen Dank für Ihre Aufträge"]], "recognized", "PDF")

    def test_english_invoice(self):
        self.check_pdf([ENGLISH], "recognized", "PDF")

    def test_advice_with_invoice_references_is_not_invoice(self):
        self.check_pdf([AVIS], "recognized", "Zahlungsavis")
        self.check_pdf([AVIS[:2] + ["Rechnung Nr. SYN-2026-001"] + AVIS[2:]], "recognized", "Zahlungsavis")

    def test_clear_other_document_types_with_invoice_reference(self):
        for title in ("Angebot", "Bestellung", "Lieferschein", "Newsletter", "AGB"):
            with self.subTest(title=title):
                self.check_pdf([[title, "Bezug zur Rechnung Nr. SYN-2026-001", "Datum: 12.11.2026", "Gesamtbetrag: 119,00 EUR"]],
                               "ignored", reason="irrelevant_document_type")

    def test_explicit_negation_and_proforma_are_not_invoices(self):
        for negation in ("Dies ist keine Rechnung", "Not an invoice", "Proforma Rechnung"):
            with self.subTest(negation=negation):
                self.check_pdf([INVOICE + [negation]], "ignored", reason="explicit_non_invoice")

    def test_single_keyword_or_bank_details_never_suffice(self):
        self.check_pdf([["Bitte prüfen Sie die Rechnung.", "IBAN DE12345678901234567890", "Betrag: 119,00 EUR"]],
                       "unknown", reason="ambiguous_pdf")
        self.check_pdf([["Rechnung", "Willkommen und vielen Dank für Ihr Interesse"]], "unknown", reason="ambiguous_invoice")

    def test_conflicting_followup_page_and_mixed_types_fail(self):
        self.check_pdf([INVOICE, ["Angebot", "Dies ist ein anderer vollständiger Geschäftsvorgang"]],
                       "unknown", reason="ambiguous_mixed_document")
        self.check_pdf([INVOICE, AVIS], "unknown", reason="ambiguous_mixed_document")

    def test_conflicting_document_titles_on_same_page_fail(self):
        self.check_pdf([INVOICE + AVIS], "unknown", reason="ambiguous_mixed_document")
        self.check_pdf([INVOICE + ["Weitere Angaben zum Vorgang"] * 15 + AVIS],
                       "unknown", reason="ambiguous_mixed_document")
        self.check_pdf([INVOICE + ["Angebot", "Ein unabhängiger zweiter Geschäftsvorgang"]],
                       "unknown", reason="ambiguous_mixed_document")

    def test_terms_appendix_and_multipage_total(self):
        for heading in ("Allgemeine Geschäftsbedingungen", "Datenschutz", "Zahlungsbedingungen"):
            with self.subTest(appendix=heading):
                self.check_pdf([INVOICE, [heading, "Es gelten unsere üblichen Lieferbedingungen.",
                                         "Diese allgemeinen Informationen sind keine Rechnung."]], "recognized", "PDF")
        self.check_pdf([INVOICE[:5], INVOICE[5:]], "recognized", "PDF")

    def test_b_f1_independent_sections_in_every_order(self):
        offer = ["Angebot", "Ein eigenständiger weiterer Geschäftsvorgang"]
        separate_invoice = ["Rechnung", "Rechnungsnummer: SYN-2026-002"] + INVOICE[2:]
        for first, second in ((offer, INVOICE), (INVOICE, offer), (AVIS, separate_invoice),
                              (separate_invoice, AVIS), (AVIS, INVOICE), (INVOICE, AVIS)):
            with self.subTest(first=first[0], second=second[0]):
                self.check_pdf([first + second], "unknown", reason="ambiguous_mixed_document")
                self.check_pdf([first + ["Zusätzliche Hinweise zum Vorgang"] * 25 + second],
                               "unknown", reason="ambiguous_mixed_document")
        self.check_pdf([INVOICE, ["Allgemeine Geschäftsbedingungen"] + AVIS],
                       "unknown", reason="ambiguous_mixed_document")
        self.check_pdf([["Allgemeine Geschäftsbedingungen"] + AVIS, INVOICE],
                       "unknown", reason="ambiguous_mixed_document")
        self.check_pdf([AVIS[:2] + ["Rechnung Nr. SYN-2026-001"] + AVIS[2:]], "recognized", "Zahlungsavis")

    def test_b_f2_companion_sections_on_same_or_separate_page(self):
        for heading in ("Allgemeine Geschäftsbedingungen", "Datenschutz", "Zahlungsbedingungen"):
            appendix = [heading, "Diese allgemeinen Informationen sind keine Rechnung."]
            with self.subTest(heading=heading):
                self.check_pdf([INVOICE + appendix], "recognized", "PDF")
                self.check_pdf([INVOICE, appendix], "recognized", "PDF")
                self.check_pdf([appendix + AVIS, INVOICE], "unknown", reason="ambiguous_mixed_document")
        for negative in ("Dies ist keine Rechnung", "Proforma Rechnung", "Not an invoice"):
            self.check_pdf([INVOICE + [negative]], "ignored", reason="explicit_non_invoice")

    def test_b_f3_repetitive_long_text_never_allows_partial_success(self):
        for noise in (["A" * 40] * 20, ["ABCD" * 20] * 20, ["AAAA AAAA AAAA AAAA"] * 20):
            self.check_pdf([noise], "failed", reason="ocr_unreadable")
            self.check_pdf([INVOICE, noise], "failed", reason="ocr_unreadable")
        self.check_pdf([INVOICE[:5], INVOICE[5:]], "recognized", "PDF")

    def test_b_f1_generic_date_sections_remain_independent(self):
        offer = ["Angebot", "Ein eigenständiger weiterer Geschäftsvorgang"]
        for label in ("Datum", "Date", "Invoice date", "Rechnungsdatum"):
            invoice = [line.replace("Rechnungsdatum:", label + ":") for line in INVOICE]
            with self.subTest(label=label):
                self.check_pdf([invoice], "recognized", "PDF")
                for other in (offer, AVIS):
                    self.check_pdf([other + invoice], "unknown", reason="ambiguous_mixed_document")
                    self.check_pdf([invoice + other], "unknown", reason="ambiguous_mixed_document")
                    self.check_pdf([["Allgemeine Geschäftsbedingungen"] + other + invoice],
                                   "unknown", reason="ambiguous_mixed_document")
        self.check_pdf([AVIS[:2] + ["Rechnung Nr. SYN-2026-001"] + AVIS[2:]], "recognized", "Zahlungsavis")

    def test_b_f3_repetition_across_whitespace_and_lines(self):
        for separator in (" ", "  ", "\t"):
            noise = [separator.join(["ABCD"] * 4)] * 20
            self.check_pdf([noise], "failed", reason="ocr_unreadable")
            self.check_pdf([INVOICE, noise], "failed", reason="ocr_unreadable")
        self.check_pdf([INVOICE[:5], INVOICE[5:]], "recognized", "PDF")

    def test_invoice_type_does_not_require_every_single_field(self):
        self.check_pdf([[line for line in INVOICE if "Gesamtbetrag" not in line]], "recognized", "PDF", reason="invoice_title_reference_date")
        self.check_pdf([[line.replace("12.11.2026", "32.13.2026") for line in INVOICE]], "recognized", "PDF", reason="invoice_title_total_transaction")

    def test_blank_and_mixed_unreadable_pages_fail_after_ocr(self):
        self.check_pdf([[]], "failed", reason="ocr_unreadable")
        self.check_pdf([INVOICE, []], "failed", reason="ocr_unreadable")

    def test_real_pdfium_text_limit_is_closed(self):
        with patch("classifier.text_pdf.MAX_PAGE_TEXT", 20):
            self.check_pdf([INVOICE], "failed", reason="text_size_limit")

    def test_hybrid_is_decided_before_text_rules(self):
        result = classify(hybrid())
        self.assertEqual(result["status"], "recognized")
        self.assertEqual(result["category"], "E-Rechnung")

    def test_actual_bounded_worker_with_text_engine(self):
        data = text_document([INVOICE])
        result = bounded_classify(data)
        self.assertEqual(result["status"], "recognized", result)
        self.assertEqual(result["category"], "PDF")
        self.assertEqual(result["original_sha256"], sha256(data).hexdigest())

    def test_bounded_worker_accepts_unknown_and_reminder_results(self):
        for lines, status, category in ((["Bitte prüfen Sie die beigefügten Unterlagen."], "unknown", None),
                (["Zahlungserinnerung", "Bitte begleichen Sie die offenen Posten.", "Gesamtbetrag: 119,00 EUR"],
                 "recognized", "Mahnung")):
            data = text_document([lines])
            result = bounded_classify(data)
            self.assertEqual((result["status"], result["category"]), (status, category), result)
            self.assertEqual(result["original_sha256"], sha256(data).hexdigest())
            self.assertEqual(result["rule_version"], "ap03-4")

    def test_empty_user_password_preserves_all_other_pdf_guards(self):
        from io import BytesIO
        import pikepdf
        data = text_document([INVOICE])
        with pikepdf.Pdf.open(BytesIO(data)) as pdf:
            output = BytesIO()
            pdf.save(output, encryption=pikepdf.Encryption(owner="synthetic-owner", user=""))
        result = classify(output.getvalue())
        self.assertEqual((result["status"], result["category"]), ("recognized", "PDF"), result)


if __name__ == "__main__":
    unittest.main()
