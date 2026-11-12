from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import pikepdf
from classifier.core import classify
from classifier.cli import bounded_classify
from classifier.xml_invoice import identity, XR
from fixtures import REFERENCES, hybrid, legacy_hybrid, plain_pdf, reference_xml


def mutate_pdf(data, operation):
    with pikepdf.Pdf.open(BytesIO(data)) as pdf:
        operation(pdf)
        output = BytesIO()
        pdf.save(output)
        return output.getvalue()


class FormatTests(unittest.TestCase):
    def test_independent_kosit_ubl_and_cii(self):
        for name in ("ubl.xml", "cii.xml"):
            data = (REFERENCES / name).read_bytes()
            result = classify(data)
            self.assertEqual(result["status"], "recognized", name)
            self.assertEqual(result["category"], "E-Rechnung")
            self.assertTrue(result["format"].startswith("XRechnung-"))
            self.assertEqual(result["original_sha256"], sha256(data).hexdigest())

    def test_official_historical_xrechnung22_and23_both_syntaxes(self):
        for version in ("xr22", "xr23"):
            for name in ("ubl.xml", "cii.xml"):
                data = (REFERENCES / version / name).read_bytes()
                with self.subTest(version=version, syntax=name):
                    result = classify(data)
                    self.assertEqual(result["status"], "recognized", result)
                    self.assertTrue(result["format"].startswith("XRechnung-"))

    def test_independent_creditnote_tree_with_explicit_profile_adaptation(self):
        folder = REFERENCES / "creditnote"
        original = (folder / "original-peppol.xml").read_bytes()
        adapted = (folder / "profile-adapted-xrechnung.xml").read_bytes()
        self.assertEqual(classify(original)["reason"], "unsupported_invoice_profile")
        result = classify(adapted)
        self.assertEqual(result["status"], "recognized", result)
        self.assertEqual(result["format"], "XRechnung-UBL-CreditNote")
        old = b"urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
        self.assertEqual(original.replace(old, XR.encode(), 1), adapted)

    def test_independent_facturx_profiles(self):
        for profile in ("minimum", "basicwl", "basic", "en16931", "extended"):
            with self.subTest(profile=profile):
                data = hybrid(profile)
                result = classify(data)
                self.assertEqual(result["status"], "recognized", result)
                self.assertEqual(result["format"], "ZUGFeRD/Factur-X")
                self.assertEqual(result["original_sha256"], sha256(data).hexdigest())

    def test_independent_legacy_xml_and_pypdf_hybrid(self):
        for profile in ("basic", "comfort", "extended"):
            with self.subTest(profile=profile):
                self.assertEqual(identity(reference_xml("zugferd-" + profile)).family, "zugferd1")
                result = classify(legacy_hybrid(profile))
                self.assertEqual(result["status"], "recognized", result)
                self.assertEqual(result["format"], "ZUGFeRD/Factur-X")

    def test_generic_wrong_namespace_and_profile_spoofs(self):
        self.assertEqual(classify(b"<root><Invoice>ordinary text</Invoice></root>")["status"], "ignored")
        for data in (b"<Invoice xmlns='evil'>invoice</Invoice>",
                     (f"<Invoice xmlns='urn:oasis:names:specification:ubl:schema:xsd:Invoice-2' xmlns:c='urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'><c:CustomizationID>{XR}</c:CustomizationID></Invoice>").encode(),
                     (REFERENCES / "ubl.xml").read_bytes().replace(XR.encode(), b"urn:unknown:invoice")):
            result = classify(data)
            self.assertEqual(result["status"], "failed")
            self.assertIsNone(result["category"])

    def test_utf16_and_namespace_prefixes(self):
        data = (REFERENCES / "ubl.xml").read_text()
        data = data.replace('encoding="UTF-8"', 'encoding="UTF-16"').replace("<ubl:", "<different:").replace("</ubl:", "</different:").replace("xmlns:ubl=", "xmlns:different=")
        self.assertEqual(classify(data.encode("utf-16"))["status"], "recognized")

    def test_xml_root_after_long_legal_whitespace_and_encodings(self):
        source = (REFERENCES / "ubl.xml").read_text()
        body = source.split("?>", 1)[1]
        whitespace = " \t\r\n" * 1024
        samples = [
            (whitespace + body).encode("utf-8"),
            b"\xef\xbb\xbf" + (whitespace + body).encode("utf-8"),
            ('<?xml version="1.0" encoding="UTF-8"?>' + whitespace + body).encode("utf-8"),
            (whitespace + body).encode("utf-16"),
            ('<?xml version="1.0" encoding="UTF-16"?>' + whitespace + body).encode("utf-16"),
            ('<?xml version="1.0" encoding="UTF-16LE"?>' + whitespace + body).encode("utf-16-le"),
            ('<?xml version="1.0" encoding="UTF-16BE"?>' + whitespace + body).encode("utf-16-be"),
        ]
        for index, data in enumerate(samples):
            with self.subTest(encoding_case=index):
                self.assertEqual(classify(data)["status"], "recognized")
                self.assertEqual(classify(data)["original_sha256"], sha256(data).hexdigest())
        for name in ("ubl.xml", "cii.xml"):
            original = (REFERENCES / name).read_bytes().split(b"?>", 1)[1]
            for count in (512, 513):
                for bom in (b"", b"\xef\xbb\xbf"):
                    data = bom + b" " * count + original
                    with self.subTest(syntax=name, prefix=count, bom=bool(bom)):
                        result = classify(data)
                        self.assertEqual(result["status"], "recognized")
                        self.assertEqual(result["original_sha256"], sha256(data).hexdigest())
        self.assertEqual(classify(b" " * 513 + b"<Invoice><broken>")["status"], "failed")
        self.assertEqual(classify(b" " * 1048576 + body.encode())["reason"], "xml_size_limit")
        self.assertEqual(classify(b" " * 8192 + b"ordinary non-XML content")["status"], "ignored")

    def test_xxe_dtd_xinclude_and_limits(self):
        attacks = [b"<!DOCTYPE root [<!ENTITY e SYSTEM 'file:///etc/passwd'>]><root>&e;</root>",
                   "<!DOCTYPE root [<!ENTITY e 'expanded'>]><root>&e;</root>".encode("utf-16"),
                   b"<root xmlns:x='http://www.w3.org/2001/XInclude'><x:include href='https://evil.invalid'/></root>",
                   ("<r>" * 50 + "x" + "</r>" * 50).encode(),
                   b"<r value='" + b"x" * 9000 + b"'/>",
                   b"<r>" + b"<x/>" * 20001 + b"</r>", b"<r>" + b"x" * 1048576 + b"</r>"]
        for data in attacks:
            with self.subTest(size=len(data)):
                self.assertEqual(classify(data)["status"], "failed")

    def test_wrong_extension_irrelevant_image_and_ordinary_pdf(self):
        # No filename or MIME parameter exists in the positive decision path.
        self.assertEqual(classify(b"\x89PNG\r\n\x1a\nsynthetic")["status"], "ignored")
        self.assertNotEqual(classify(plain_pdf())["category"], "E-Rechnung")
        self.assertEqual(classify(b"%PDF-1.7\ntruncated")["status"], "failed")

    def test_generic_embedding_does_not_create_einvoice(self):
        def add(pdf):
            pdf.attachments["factur-x.xml"] = pikepdf.AttachedFileSpec(pdf, b"<unrelated/>")
        result = classify(mutate_pdf(plain_pdf(), add))
        self.assertNotEqual(result["category"], "E-Rechnung")

    def test_broken_claimed_xml_does_not_fall_back(self):
        def break_xml(pdf):
            pdf.attachments["factur-x.xml"] = pikepdf.AttachedFileSpec(pdf, b"<broken>")
        result = classify(mutate_pdf(hybrid(), break_xml))
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["category"])

    def test_nested_name_tree_and_duplicate_names_are_not_hidden(self):
        original = hybrid()
        def nested(pdf):
            tree = pdf.make_indirect(pdf.Root.Names.EmbeddedFiles)
            tree.Limits = pikepdf.Array([tree.Names[0], tree.Names[-2]])
            pdf.Root.Names.EmbeddedFiles = pdf.make_indirect(pikepdf.Dictionary(Kids=pikepdf.Array([tree])))
        self.assertEqual(classify(mutate_pdf(original, nested))["status"], "recognized")
        def duplicate(pdf):
            names = pdf.Root.Names.EmbeddedFiles.Names
            second = pikepdf.AttachedFileSpec(pdf, reference_xml("factur-x-en16931").replace(b"102", b"103", 1), filename="factur-x.xml")
            second.obj.AFRelationship = pikepdf.Name.Alternative
            names.append(pikepdf.String("factur-x.xml"))
            names.append(second.obj)
            pdf.Root.AF.append(second.obj)
        result = classify(mutate_pdf(original, duplicate))
        self.assertEqual(result["status"], "failed", result)

    def test_missing_af_and_conflicting_metadata(self):
        def no_af(pdf):
            del pdf.Root.AF
        self.assertEqual(classify(mutate_pdf(hybrid(), no_af))["status"], "failed")
        def conflict(pdf):
            raw = pdf.Root.Metadata.read_bytes().replace(b"EN 16931", b"MINIMUM")
            pdf.Root.Metadata.write(raw)
        self.assertEqual(classify(mutate_pdf(hybrid(), conflict))["status"], "unknown")

    def test_spoofed_hybrid_namespace_cannot_replace_legacy_context(self):
        def spoof(pdf):
            raw = pdf.Root.Metadata.read_bytes().replace(
                b"urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#",
                b"urn:ferd:pdfa:CrossIndustryDocument:invoice:1p0#")
            pdf.Root.Metadata.write(raw)
        self.assertEqual(classify(mutate_pdf(hybrid(), spoof))["reason"], "hybrid_namespace_mismatch")

    def test_all_ef_platform_stream_variants_are_checked(self):
        def equal_variants(pdf):
            spec = pdf.Root.AF[0]
            raw = spec.EF.F.read_bytes()
            spec.EF.UF = pdf.make_stream(raw)
        self.assertEqual(classify(mutate_pdf(hybrid(), equal_variants))["status"], "recognized")
        def conflicting_variants(pdf):
            spec = pdf.Root.AF[0]
            raw = ET.fromstring(spec.EF.F.read_bytes())
            raw.find("{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocument/{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID").text = "SECOND-SYNTHETIC-INVOICE"
            spec.EF.UF = pdf.make_stream(ET.tostring(raw))
        self.assertEqual(classify(mutate_pdf(hybrid(), conflicting_variants))["reason"], "ambiguous_embedded_invoices")

    def test_pageaf_annotation_and_repeated_reference_candidates(self):
        def annotation(pdf, spec):
            return pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Annot,
                Subtype=pikepdf.Name.FileAttachment, FS=spec, Rect=pikepdf.Array([0, 0, 10, 10])))
        def repeated(pdf):
            spec = pdf.Root.AF[0]
            pdf.pages[0].obj.AF = pikepdf.Array([spec])
            pdf.pages[0].obj.Annots = pikepdf.Array([annotation(pdf, spec)])
        self.assertEqual(classify(mutate_pdf(hybrid(), repeated))["status"], "recognized")
        def page_only(pdf):
            spec = pdf.Root.AF[0]
            pdf.pages[0].obj.AF = pikepdf.Array([spec])
            del pdf.Root.AF
            del pdf.Root.Names.EmbeddedFiles
        self.assertEqual(classify(mutate_pdf(hybrid(), page_only))["status"], "recognized")
        def second_candidate(pdf, via_page):
            raw = ET.fromstring(reference_xml("factur-x-en16931"))
            raw.find("{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}ExchangedDocument/{urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100}ID").text = "SECOND-SYNTHETIC-INVOICE"
            spec = pikepdf.AttachedFileSpec(pdf, ET.tostring(raw), filename="factur-x.xml")
            spec.obj.AFRelationship = pikepdf.Name.Alternative
            if via_page:
                pdf.pages[0].obj.AF = pikepdf.Array([spec.obj])
            else:
                pdf.pages[0].obj.Annots = pikepdf.Array([annotation(pdf, spec.obj)])
        for via_page in (True, False):
            result = classify(mutate_pdf(hybrid(), lambda pdf: second_candidate(pdf, via_page)))
            self.assertEqual(result["status"], "unknown" if via_page else "failed", result)
            self.assertEqual(result["reason"], "ambiguous_embedded_invoices" if via_page else "missing_hybrid_context")
        def annotation_only(pdf):
            spec = pdf.Root.AF[0]
            pdf.pages[0].obj.Annots = pikepdf.Array([annotation(pdf, spec)])
            del pdf.Root.AF
            del pdf.Root.Names.EmbeddedFiles
        self.assertEqual(classify(mutate_pdf(hybrid(), annotation_only))["reason"], "missing_hybrid_context")

    def test_encryption_actions_and_size_limits(self):
        with pikepdf.Pdf.open(BytesIO(plain_pdf())) as pdf:
            output = BytesIO()
            pdf.save(output, encryption=pikepdf.Encryption(owner="synthetic", user="synthetic"))
            self.assertEqual(classify(output.getvalue())["reason"], "encrypted_pdf")
        def action(pdf):
            pdf.Root.OpenAction = pdf.make_indirect(pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS=pikepdf.String("synthetic")))
        self.assertEqual(classify(mutate_pdf(plain_pdf(), action))["reason"], "unsafe_pdf_action")
        self.assertEqual(classify(b"x" * (25 * 1024 * 1024 + 1))["reason"], "input_size_limit")

    def test_fixtures_match_recorded_independent_origins(self):
        for origin in REFERENCES.rglob("ORIGIN.json"):
            manifest = json.loads(origin.read_text())
            self.assertEqual(len(manifest["commit"]), 40)
            for name, details in manifest["files"].items():
                self.assertEqual(sha256((origin.parent / name).read_bytes()).hexdigest(), details["sha256"])

    def test_process_deadline_and_original_hash(self):
        data = (REFERENCES / "ubl.xml").read_bytes()
        before = sha256(data).hexdigest()
        self.assertEqual(bounded_classify(data)["status"], "recognized")
        timed_out = bounded_classify(data, seconds=0.0001)
        self.assertEqual(timed_out["reason"], "document_timeout")
        self.assertEqual(timed_out["original_sha256"], before)
        self.assertEqual(sha256(data).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
