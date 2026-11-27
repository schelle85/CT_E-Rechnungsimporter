"""Synthetic incomplete-checksum streams; never customer bytes or repaired PDFs."""
from hashlib import sha256
from io import BytesIO
import struct
import unittest
import zlib
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, EncodedStreamObject, NameObject, NumberObject, TextStringObject
from classifier.core import classify
from fixtures import REFERENCES, plain_pdf


def document(*, version="3.0", xml=None, trailer=0, truncate=False, associated=True, action=False,
             icc=True, bad_icc=False, duplicate=False, level="XRECHNUNG", icc_binding="outputintent"):
    xml=(REFERENCES/"cii.xml").read_bytes() if xml is None else xml
    writer=PdfWriter();writer.append(PdfReader(BytesIO(plain_pdf())))
    def stream(raw, n=None):
        value=EncodedStreamObject();value[NameObject('/Filter')]=NameObject('/FlateDecode')
        data=zlib.compress(raw)
        value._data=data[:len(data)//2] if truncate else data[:-4]+(b'\xff' if trailer else b'')
        if n:value[NameObject('/N')]=NumberObject(n)
        return writer._add_object(value)
    def attach(raw, name):
        file=writer.add_attachment(name,raw)
        file.associated_file_relationship=NameObject('/Alternative')
        encoded=stream(raw)
        file.pdf_object['/EF'][NameObject('/F')]=encoded
        file.pdf_object['/EF'][NameObject('/UF')]=encoded
        return file.pdf_object.indirect_reference
    first=attach(xml,'xrechnung.xml')
    if associated:writer._root_object[NameObject('/AF')]=ArrayObject([first])
    if duplicate:
        second=attach(xml.replace(b'</ram:ID>',b'2</ram:ID>',1),'second.xml')
        writer._root_object['/AF'].append(second)
    if icc:
        profile=bytearray(132);profile[:4]=struct.pack('>I',132);profile[16:20]=b'RGB '
        profile[36:40]=b'nope' if bad_icc else b'acsp'
        profile_stream=stream(bytes(profile),3)
        if icc_binding=='colorspace':
            colors=ArrayObject([NameObject('/ICCBased'),profile_stream])
            writer.pages[0]['/Resources'][NameObject('/ColorSpace')]=writer._add_object(
                DictionaryObject({NameObject('/FixtureRGB'):writer._add_object(colors)}))
        elif icc_binding=='outputintent':
            writer._root_object[NameObject('/OutputIntents')]=ArrayObject([DictionaryObject({
                NameObject('/Type'):NameObject('/OutputIntent'),NameObject('/S'):NameObject('/GTS_PDFA1'),
                NameObject('/DestOutputProfile'):profile_stream})])
        elif icc_binding=='spoofarray':
            writer._root_object[NameObject('/SyntheticExtra')]=writer._add_object(
                ArrayObject([NameObject('/ICCBased'),profile_stream]))
        else:
            extra=writer.add_attachment('opaque.bin',bytes(profile))
            extra.pdf_object['/EF'][NameObject('/F')]=profile_stream
    metadata=DecodedStreamObject()
    metadata.set_data(('''<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:fx="urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"><fx:DocumentType>INVOICE</fx:DocumentType><fx:DocumentFileName>xrechnung.xml</fx:DocumentFileName><fx:Version>'''+version+'''</fx:Version><fx:ConformanceLevel>'''+level+'''</fx:ConformanceLevel></rdf:Description></rdf:RDF></x:xmpmeta>''').encode())
    metadata[NameObject('/Type')]=NameObject('/Metadata');metadata[NameObject('/Subtype')]=NameObject('/XML')
    writer._root_object[NameObject('/Metadata')]=writer._add_object(metadata)
    if action:
        writer._root_object[NameObject('/OpenAction')]=DictionaryObject({NameObject('/S'):NameObject('/JavaScript'),NameObject('/JS'):TextStringObject('synthetic')})
    output=BytesIO();writer.write(output);return output.getvalue()


class HybridWarningTests(unittest.TestCase):
    def test_complete_deflate_with_missing_checksum_and_exact_xrechnung_context(self):
        data=document();original=sha256(data).hexdigest();result=classify(data)
        self.assertEqual(result['status'],'recognized',result)
        self.assertEqual(result['category'],'E-Rechnung')
        self.assertEqual(result['format'],'ZUGFeRD/Factur-X')
        self.assertEqual(result['warnings'],['pdf_stream_missing_checksum','hybrid_xrechnung_metadata_version'])
        self.assertEqual(result['original_sha256'],original);self.assertEqual(sha256(data).hexdigest(),original)

    def test_clean_existing_xml_findings_have_no_new_fields(self):
        result=classify((REFERENCES/'cii.xml').read_bytes())
        self.assertEqual(set(result),{'status','category','format','reason','method','original_sha256','rule_version'})

    def test_pdfa_output_intent_is_bound_but_an_unreferenced_profile_is_not(self):
        self.assertEqual(classify(document(icc_binding='outputintent'))['status'],'recognized')
        self.assertEqual(classify(document(icc_binding=None))['status'],'failed')
        self.assertEqual(classify(document(icc_binding='colorspace'))['status'],'failed')
        self.assertEqual(classify(document(icc_binding='spoofarray'))['status'],'failed')

    def test_truncated_deflate_bad_checksum_and_invalid_icc_stay_closed(self):
        for changes in (dict(truncate=True),dict(trailer=1),dict(bad_icc=True)):
            with self.subTest(changes=changes):self.assertEqual(classify(document(**changes))['status'],'failed')

    def test_unsafe_xml_missing_context_actions_and_multiple_invoices_never_fall_back(self):
        for changes in (dict(xml=b'<broken>'),dict(xml=b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'),
                        dict(associated=False),dict(action=True),dict(duplicate=True)):
            result=classify(document(**changes))
            self.assertIn(result['status'],{'failed','unknown'},result)
            self.assertIsNone(result['category']);self.assertNotIn('warnings',result)

    def test_metadata_exception_does_not_expand_versions_or_other_profiles(self):
        for changes in (dict(version='3.1'),dict(level='EN 16931'),
                        dict(xml=(REFERENCES/'facturx'/'factur-x-en16931.xml').read_bytes())):
            result=classify(document(**changes));self.assertNotEqual(result['status'],'recognized',result)

    def test_normal_version_keeps_all_warning_checks_and_ordinary_pdf_is_not_relaxed(self):
        result=classify(document(version='1.0'))
        self.assertEqual(result['warnings'],['pdf_stream_missing_checksum'])
        self.assertEqual(classify(b'%PDF-1.7\ntruncated')['status'],'failed')


if __name__=='__main__':unittest.main()
