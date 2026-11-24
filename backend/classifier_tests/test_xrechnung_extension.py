"""Synthetic XRechnung extension fixtures through the real classifier and XML guards."""
import unittest
from classifier.core import classify
from classifier.xml_invoice import XR, XR_EXTENSION


def invoice(profile=XR_EXTENSION, *, credit=False):
    root = "CreditNote" if credit else "Invoice"
    kind, code = ("CreditNoteTypeCode","381") if credit else ("InvoiceTypeCode","380")
    line = "CreditNoteLine" if credit else "InvoiceLine"
    return f'''<d:{root} xmlns:d="urn:oasis:names:specification:ubl:schema:xsd:{root}-2"
      xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
      xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
      <cbc:CustomizationID>{profile}</cbc:CustomizationID><cbc:ID>TEST-INV-101</cbc:ID>
      <cbc:IssueDate>2026-11-12</cbc:IssueDate><cbc:{kind}>{code}</cbc:{kind}>
      <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
      <cac:AccountingSupplierParty><cac:Party><cbc:EndpointID>synthetic-supplier</cbc:EndpointID></cac:Party></cac:AccountingSupplierParty>
      <cac:AccountingCustomerParty><cac:Party><cbc:EndpointID>synthetic-buyer</cbc:EndpointID></cac:Party></cac:AccountingCustomerParty>
      <cac:LegalMonetaryTotal><cbc:PayableAmount>119.00</cbc:PayableAmount></cac:LegalMonetaryTotal>
      <cac:{line}><cbc:ID>1</cbc:ID><cbc:LineExtensionAmount>100.00</cbc:LineExtensionAmount><cac:Item/></cac:{line}>
      </d:{root}>'''.encode()


class ExtensionTests(unittest.TestCase):
    def test_exact_official_extension_and_existing_base_profile(self):
        for profile in (XR_EXTENSION,XR):
            with self.subTest(profile=profile):
                value=classify(invoice(profile))
                self.assertEqual((value["status"],value["category"],value["format"]),
                                 ("recognized","E-Rechnung","XRechnung-UBL-Invoice"))

    def test_similar_unknown_profiles_do_not_bypass_allowlist(self):
        for profile in (XR_EXTENSION+"#other", XR_EXTENSION.replace("xrechnung_3.0","xrechnung_4.0"), "prefix"+XR_EXTENSION):
            with self.subTest(profile=profile):
                self.assertEqual(classify(invoice(profile))["reason"],"unsupported_invoice_profile")

    def test_extension_does_not_broaden_creditnote_syntax(self):
        self.assertEqual(classify(invoice(credit=True))["reason"],"unsupported_invoice_profile")
        self.assertEqual(classify(invoice(XR,credit=True))["status"],"recognized")
        cii=f'''<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
          xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
          <rsm:ExchangedDocumentContext><ram:GuidelineSpecifiedDocumentContextParameter>
          <ram:ID>{XR_EXTENSION}</ram:ID></ram:GuidelineSpecifiedDocumentContextParameter></rsm:ExchangedDocumentContext>
          </rsm:CrossIndustryInvoice>'''.encode()
        self.assertEqual(classify(cii)["reason"],"unsupported_invoice_profile")

    def test_extension_keeps_structure_namespace_and_entity_guards(self):
        data=invoice()
        self.assertEqual(classify(data.replace(b"<cbc:ID>TEST-INV-101</cbc:ID>",b""))["reason"],"malformed_invoice")
        self.assertEqual(classify(data.replace(b"xsd:Invoice-2",b"xsd:Other-2"))["reason"],"unsupported_invoice_namespace")
        unsafe=b'<!DOCTYPE Invoice [<!ENTITY example "unsafe">]>'+data
        self.assertEqual(classify(unsafe)["reason"],"unsafe_xml")


if __name__ == "__main__":
    unittest.main()
