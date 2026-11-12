"""Synthetic counterparts of confirmed title/layout and document-kind gaps."""
import unittest

from classifier.text_pdf import decide_pages, has_date


INVOICE = "Rechnung Nr. SAMPLE-123\nRechnungsdatum: 12.11.2026\nGesamtbetrag: 119,00 EUR\nArtikel und Leistungen"
ADVICE = "Zahlungsavis\nWir überweisen die folgenden offenen Posten.\nZahlbetrag: 119,00 EUR"
REMINDER = "Zahlungserinnerung\nBitte begleichen Sie den offenen Rechnungsbetrag.\nGesamtbetrag: 119,00 EUR"


class DecisionRevisionTests(unittest.TestCase):
    def check(self, text, status, category=None):
        result = decide_pages([text])
        self.assertEqual((result.status, result.category), (status, category), result)
        return result

    def test_outgoing_and_spaced_titles(self):
        for heading in ("Ausgangsrechnung", "R E C H N U N G", "r e c h n u n g", "Invoice"):
            with self.subTest(heading=heading):
                self.check(heading + "\nArtikel und Leistungen\nGesamtbetrag: 119,00 EUR", "recognized", "PDF")
        self.check("Bitte beachten Sie das Wort R E C H N U N G in dieser Anleitung.\nGesamtbetrag: 119,00 EUR",
                   "unknown")

    def test_date_and_total_on_nearby_lines(self):
        self.check("Rechnung Nr. SAMPLE-123\nDatum:\n12.11.2026\nGesamtbetrag:\n119,00 EUR\nArtikel und Leistungen",
                   "recognized", "PDF")
        self.assertTrue(has_date(["datum:", "zusätzliche angabe", "12.11.2026"]))
        self.assertFalse(has_date(["datum:", "weitere angabe", "weitere angabe", "12.11.2026"]))
        self.assertFalse(has_date(["datum:", "32.13.2026"]))
        self.assertFalse(has_date(["datum:", "angebot", "12.11.2026"]))

    def test_missing_fields_do_not_erase_the_document_kind(self):
        for text in ("Rechnung Nr. SAMPLE-123\nDatum: 12.11.2026\nLieferung der bestellten Waren",
                     "Rechnung Nr. SAMPLE-123\nGesamtbetrag: 119,00 EUR\nLieferung der bestellten Waren",
                     "Rechnung\nArtikel und Leistungen\nGesamtbetrag: 119,00 EUR"):
            self.check(text, "recognized", "PDF")
        self.check("Rechnung\nVielen Dank für Ihr Interesse", "unknown")
        self.check("Rechnung\nGesamtbetrag: 119,00 EUR\nVielen Dank für Ihr Interesse", "unknown")

    def test_advice_does_not_require_invoice_number_or_date(self):
        self.check(ADVICE, "recognized", "Zahlungsavis")
        self.check(ADVICE + "\nDies ist keine Rechnung.", "recognized", "Zahlungsavis")
        self.check("Zahlungsavis\nBitte prüfen Sie die beigefügten Unterlagen.", "unknown")

    def test_pre_notification_requires_payment_context_and_amount(self):
        for heading in ("Pre-Notifikation", "SEPA-Firmenlastschrift (Pre-Notifikation)", "Vorabankündigung"):
            self.check(heading + "\nWir belasten Ihr Konto per Lastschrift.\nZahlbetrag: 119,00 EUR",
                       "recognized", "Zahlungsavis")
        self.check("Pre-Notifikation\nAllgemeine Informationen zum vereinbarten Verfahren.", "unknown")
        self.check("SEPA-Lastschriftmandat\nWir belasten Ihr Konto.\nZahlbetrag: 119,00 EUR", "unknown")

    def test_reminders_and_invoice_references(self):
        for heading in ("Mahnung", "2. Mahnung", "Freundliche Zahlungserinnerung", "Zahlungserinnerung"):
            text = REMINDER.replace("Zahlungserinnerung", heading)
            self.check(text, "recognized", "Mahnung")
            self.check(text + "\nRechnung Nr. SAMPLE-123", "recognized", "Mahnung")
        self.check("Zahlungserinnerung\nBitte prüfen Sie die beigefügten Unterlagen.", "unknown")

    def test_reminder_mentions_in_terms_are_not_a_second_document(self):
        self.check(INVOICE + "\nAllgemeine Geschäftsbedingungen\nBei Mahnung können weitere Kosten entstehen.",
                   "recognized", "PDF")

    def test_independent_primary_documents_remain_unknown_in_both_orders(self):
        for first, second in ((INVOICE, REMINDER), (REMINDER, INVOICE), (ADVICE, REMINDER), (REMINDER, ADVICE)):
            result = self.check(first + "\n" + second, "unknown")
            self.assertEqual(result.reason, "ambiguous_mixed_document")

    def test_b_f1_3_dateless_invoice_is_independent_in_both_orders_and_layouts(self):
        invoices = ("Rechnung Nr. SAMPLE-123\nArtikel und Leistungen\nGesamtbetrag: 119,00 EUR",
                    "Rechnung Nr. SAMPLE-123\nGesamtbetrag: 119,00 EUR",
                    "Rechnung Nr. SAMPLE-123\nArtikel und Leistungen\nZahlbetrag: 119,00 EUR")
        for invoice in invoices:
            self.check(invoice, "recognized", "PDF")
            for other in (ADVICE, REMINDER, "Angebot\nEin eigenständiger weiterer Geschäftsvorgang"):
                for first, second in ((other, invoice), (invoice, other)):
                    for pages in ([first + "\n" + second], [first, second]):
                        with self.subTest(invoice=invoice, other=other, pages=len(pages), first=first):
                            result = decide_pages(pages)
                            self.assertEqual((result.status, result.reason), ("unknown", "ambiguous_mixed_document"))

    def test_b_f1_3_payment_fields_do_not_turn_numbered_references_into_invoices(self):
        references = ("Rechnung Nr. SAMPLE-123",
                      "Rechnung Nr. SAMPLE-123\nZahlungsdatum: 12.11.2026\nZahlbetrag: 119,00 EUR",
                      "Rechnung Nr. SAMPLE-123\nValuta:\n12.11.2026\nZahlbetrag:\n119,00 EUR")
        for other, category in ((ADVICE, "Zahlungsavis"), (REMINDER, "Mahnung")):
            for reference in references:
                with self.subTest(category=category, reference=reference):
                    self.check(other + "\n" + reference, "recognized", category)

    def test_b_f1_3_terms_reference_convention_is_preserved(self):
        self.check("Allgemeine Geschäftsbedingungen\nBeispiel für die Zuordnung:\n"
                   "Rechnung Nr. SAMPLE-123\nArtikel und Leistungen\nGesamtbetrag: 119,00 EUR",
                   "ignored")

    def test_uncertainty_preserves_method_and_technical_failure_stays_failed(self):
        result = decide_pages(["Bitte prüfen Sie die beigefügten Unterlagen."], "ocr")
        self.assertEqual((result.status, result.method), ("unknown", "ocr"))
        self.assertEqual(decide_pages([""]).status, "failed")


if __name__ == "__main__":
    unittest.main()
