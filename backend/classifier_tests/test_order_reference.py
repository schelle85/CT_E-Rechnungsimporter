"""Anonymous purchase-order field regression; no customer data or parser doubles."""
import unittest
from hashlib import sha256
from io import BytesIO
from classifier.text_pdf import decide_pages, sections, title

HEADER = ["Synthetic Supplier", "Rechnung Nr. TEST-INV-101", "Ansprechpartner Einkauf"]
TRANSACTION = ["Rechnungsdatum: 12.11.2026", "Artikel und Leistungen", "Nettobetrag: 100,00 EUR",
               "Umsatzsteuer: 19,00 EUR", "Gesamtbetrag: 119,00 EUR"]
TABLE_HEADER = "Pos. Artikel-Nr. / Bezeichnung Menge Einheit Einzelpreis Netto"
INVOICE_METADATA = ["Ihre Kdn.-Nr.:","TEST-CUSTOMER-101","Auftrag:","TEST-ORDER-101","Ihre USt.-Id: Lieferung:"]


class OrderReferenceTests(unittest.TestCase):
    def test_real_pdfium_text_from_anonymous_pdf_retains_original_bytes(self):
        import pypdfium2 as pdfium
        from reportlab.pdfgen import canvas
        output=BytesIO()
        writer=canvas.Canvas(output,invariant=1)
        for index,line in enumerate(HEADER+["Bestellung:","PO-TEST-101"]+TRANSACTION):
            writer.drawString(40,790-20*index,line)
        writer.showPage();writer.save()
        data=output.getvalue()
        before=sha256(data).hexdigest()
        with pdfium.PdfDocument(data) as document:
            page=document[0]
            try:
                text=page.get_textpage()
                try:
                    value=decide_pages([text.get_text_range()])
                finally:
                    text.close()
            finally:
                page.close()
        self.assertEqual((value.status,value.category),("recognized","PDF"))
        self.assertEqual(sha256(data).hexdigest(),before)

    def test_order_field_keeps_later_invoice_evidence(self):
        page = "\n".join(HEADER + ["Bestellung:", "PO-TEST-101"] + TRANSACTION)
        self.assertEqual(title(page), "invoice")
        self.assertEqual([kind for kind,_ in sections(page)], [None,"invoice"])
        result = decide_pages([page])
        self.assertEqual((result.status,result.category),("recognized","PDF"))

    def test_incomplete_invoice_then_binding_order_text_is_not_an_invoice(self):
        page = "\n".join(["Rechnung Nr. TEST-101", "Unvollständige Abrechnungsunterlagen", "Bestellung:",
                          "Hiermit bestellen wir folgende Artikel verbindlich.", "Artikel und Leistungen",
                          "Gesamtbetrag: 119,00 EUR"])
        self.assertEqual(decide_pages([page]).reason,"ambiguous_mixed_document")

    def test_empty_order_field_followed_by_invoice_position_table(self):
        page="\n".join(HEADER+INVOICE_METADATA+["Bestellung:",TABLE_HEADER,"1 TEST-ARTICLE Position 1 Stück 100,00 EUR"]+TRANSACTION)
        result=decide_pages([page])
        self.assertEqual((result.status,result.category),("recognized","PDF"))

    def test_reference_number_or_table_never_hides_explicit_order_intent(self):
        for reference in (["PO-TEST-101"],[TABLE_HEADER],["PO-TEST-101","Rechnungsdatum: 12.11.2026"]):
            with self.subTest(reference=reference):
                page="\n".join(HEADER+INVOICE_METADATA+["Bestellung:"]+reference+
                    ["Hiermit bestellen wir folgende Artikel verbindlich."]+TRANSACTION)
                self.assertEqual(decide_pages([page]).reason,"ambiguous_mixed_document")

    def test_weak_or_missing_reference_context_is_not_enough(self):
        for following in ("Artikel und Leistungen", "PO-TEST-101", "Pos. Artikel-Nr. Menge"):
            with self.subTest(following=following):
                page="\n".join(HEADER+["Bestellung:",following,"Weitere Angaben zum Vorgang"]+TRANSACTION)
                self.assertEqual(decide_pages([page]).reason,"ambiguous_mixed_document")
        page="\n".join(["Rechnung","Unvollständige Abrechnungsunterlagen"]+INVOICE_METADATA+["Bestellung:",TABLE_HEADER]+TRANSACTION)
        self.assertEqual(decide_pages([page]).reason,"ambiguous_mixed_document")

    def test_position_table_requires_positive_invoice_metadata(self):
        for removed in ("Ihre Kdn.-Nr.:","Auftrag:","Ihre USt.-Id: Lieferung:"):
            with self.subTest(removed=removed):
                metadata=[line for line in INVOICE_METADATA if line!=removed]
                page="\n".join(HEADER+metadata+["Bestellung:",TABLE_HEADER]+TRANSACTION)
                self.assertEqual(decide_pages([page]).reason,"ambiguous_mixed_document")

    def test_real_order_after_complete_invoice_is_still_mixed(self):
        for heading in ("Bestellung", "Bestellung:", "Bestellung Nr. TEST-ORDER-202"):
            with self.subTest(heading=heading):
                page = "\n".join(HEADER+TRANSACTION+[heading,"Ein eigenständiger Auftrag", "Gesamtbetrag: 238,00 EUR"])
                self.assertEqual(decide_pages([page]).reason,"ambiguous_mixed_document")

    def test_standalone_or_followup_order_is_not_hidden(self):
        order = "Bestellung:\nEin eigenständiger Auftrag über Artikel\nGesamtbetrag: 238,00 EUR"
        self.assertEqual(decide_pages([order]).status,"ignored")
        self.assertEqual(decide_pages(["\n".join(HEADER+TRANSACTION),order]).reason,"ambiguous_mixed_document")

    def test_other_document_types_and_incomplete_invoice_stay_guarded(self):
        for heading in ("Angebot:","Zahlungsavis", "Mahnung"):
            with self.subTest(heading=heading):
                self.assertEqual(decide_pages(["\n".join(HEADER+[heading]+TRANSACTION)]).reason,"ambiguous_mixed_document")
        page = "\n".join(HEADER+["Bestellung:","PO-TEST-101", "Bitte die beigefügten Unterlagen prüfen"])
        self.assertEqual(decide_pages([page]).reason,"ambiguous_mixed_document")


if __name__ == "__main__":
    unittest.main()
