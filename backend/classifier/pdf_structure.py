"""Use qpdf's parsed objects; never execute actions, extract paths or save the PDF."""
from hashlib import sha256
from io import BytesIO
import pikepdf
import re
import zlib
from classifier.model import Finding, RecognitionError
from classifier.xml_invoice import MAX_XML, identity, looks_xml, safe_xml

MAX_PAGES = 30
MAX_OBJECTS = 50000
MAX_FILES = 32
MAX_EMBEDDED_TOTAL = 4 * MAX_XML
XMP_NAMESPACES = {
    "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#",
    "urn:zugferd:pdfa:CrossIndustryDocument:invoice:2p0#",
    "urn:zugferd:pdfa:CrossIndustryDocument:invoice:2p1#",
    "urn:ferd:pdfa:CrossIndustryDocument:invoice:1p0#",
}
FIELDS = {"DocumentType", "DocumentFileName", "ConformanceLevel", "Version"}


def object_key(obj):
    number, generation = obj.objgen
    return (number, generation) if number else ("direct", id(obj))


def metadata_claim(pdf):
    stream = pdf.Root.get("/Metadata")
    if stream is None:
        return None
    raw = stream.read_bytes()
    root = safe_xml(raw)
    claims = {}
    for node in root.iter():
        entries = [(node.tag, (node.text or "").strip()), *node.attrib.items()]
        for key, value in entries:
            if not key.startswith("{") or "}" not in key:
                continue
            namespace, local = key[1:].split("}", 1)
            if namespace in XMP_NAMESPACES and local in FIELDS:
                claims.setdefault(namespace, {}).setdefault(local, set()).add(value)
    if not claims:
        return None
    if len(claims) != 1:
        raise RecognitionError("ambiguous_hybrid_metadata")
    fields = next(iter(claims.values()))
    if set(fields) != FIELDS or any(len(v) != 1 for v in fields.values()):
        raise RecognitionError("malformed_hybrid_metadata")
    result = {key: next(iter(value)) for key, value in fields.items()}
    result["namespace"] = next(iter(claims))
    if result["DocumentType"] != "INVOICE" or not result["DocumentFileName"]:
        raise RecognitionError("malformed_hybrid_metadata")
    if result["Version"] not in ("1.0", "2.0", "2.1", "2.2", "2.3", "2.4") and not (
            result["Version"] == "3.0" and result["namespace"] == "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"
            and result["ConformanceLevel"] == "XRECHNUNG"):
        raise RecognitionError("unsupported_hybrid_version")
    return result


def embedded_files(pdf):
    records, visited, tree_count = {}, set(), 0
    def add(spec, name=None, associated=False):
        if not isinstance(spec, pikepdf.Dictionary):
            raise RecognitionError("malformed_embedded_files")
        key = object_key(spec)
        if key not in records:
            if len(records) >= MAX_FILES:
                raise RecognitionError("embedded_count_limit")
            records[key] = {"spec": spec, "names": set(), "associated": False}
        record = records[key]
        record["associated"] |= associated
        for value in (name, spec.get("/UF"), spec.get("/F")):
            if value is not None:
                label = str(value)
                if len(label) > 1024:
                    raise RecognitionError("embedded_name_limit")
                record["names"].add(label)
    def name_tree(node, depth=0):
        nonlocal tree_count
        tree_count += 1
        if depth > 8 or tree_count > 256 or not isinstance(node, pikepdf.Dictionary):
            raise RecognitionError("embedded_tree_limit")
        key = object_key(node)
        if key in visited:
            raise RecognitionError("malformed_embedded_files")
        visited.add(key)
        names = node.get("/Names", [])
        if len(names) % 2:
            raise RecognitionError("malformed_embedded_files")
        for index in range(0, len(names), 2):
            add(names[index + 1], names[index])
        for child in node.get("/Kids", []):
            name_tree(child, depth + 1)
    names = pdf.Root.get("/Names")
    if names is not None and names.get("/EmbeddedFiles") is not None:
        name_tree(names["/EmbeddedFiles"])
    for spec in pdf.Root.get("/AF", []):
        add(spec, associated=True)
    for page in pdf.pages:
        for spec in page.obj.get("/AF", []):
            add(spec, associated=True)
        for annotation in page.obj.get("/Annots", []):
            if annotation.get("/Subtype") == pikepdf.Name.FileAttachment and annotation.get("/FS") is not None:
                add(annotation["/FS"])
    return tuple(records.values())


def checked_stream_warnings(pdf, data, messages):
    """Only complete DEFLATE streams with a missing Adler trailer; no PDF repair."""
    offsets = set()
    for message in messages:
        match = re.fullmatch(r"WARNING: stream .+ \(offset (\d+)\): input stream is complete but output may still be valid", message)
        if not match or int(match[1]) in offsets:
            raise RecognitionError("malformed_pdf")
        offsets.add(int(match[1]))
    found = {}
    for obj in pdf.objects:
        if not isinstance(obj, pikepdf.Stream) or str(obj.get("/Filter", "")) != "/FlateDecode" or obj.get("/DecodeParms") is not None:
            continue
        compressed = obj.read_raw_bytes()
        matched = [offset for offset in offsets if data[offset:offset+len(compressed)] == compressed]
        if not matched:
            continue
        if len(matched) != 1 or any(value[0] == matched[0] for value in found.values()):
            raise RecognitionError("malformed_pdf")
        if (len(compressed) < 3 or compressed[0] & 15 != 8 or compressed[0] >> 4 > 7
                or int.from_bytes(compressed[:2], "big") % 31 or compressed[1] & 32):
            raise RecognitionError("malformed_pdf")
        decoder = zlib.decompressobj(-15)
        try:
            decoded = decoder.decompress(compressed[2:], MAX_XML + 1)
        except zlib.error:
            raise RecognitionError("malformed_pdf") from None
        checksum = zlib.adler32(decoded).to_bytes(4, "big")
        if (len(decoded) > MAX_XML or not decoder.eof or decoder.unconsumed_tail
                or len(decoder.unused_data) >= 4 or decoder.unused_data != checksum[:len(decoder.unused_data)]
                or decoded != obj.read_bytes()):
            raise RecognitionError("malformed_pdf")
        found[object_key(obj)] = (matched[0], decoded)
    if len(found) != len(offsets):
        raise RecognitionError("malformed_pdf")
    return found


def detect_pdf(data):
    try:
        with pikepdf.Pdf.open(BytesIO(data), attempt_recovery=False, suppress_warnings=True) as pdf:
            # Opening with the default empty password already succeeded. Owner
            # restrictions alone do not make a document unreadable; non-empty
            # user passwords still raise PasswordError below. All guards remain.
            if not 1 <= len(pdf.pages) <= MAX_PAGES or len(pdf.objects) > MAX_OBJECTS:
                raise RecognitionError("pdf_structure_limit")
            icc_references = set()
            for intent in pdf.Root.get("/OutputIntents", []):
                if (isinstance(intent, pikepdf.Dictionary) and str(intent.get("/Type", "")) == "/OutputIntent"
                        and str(intent.get("/S", "")) == "/GTS_PDFA1"
                        and isinstance(intent.get("/DestOutputProfile"), pikepdf.Stream)):
                    icc_references.add(object_key(intent["/DestOutputProfile"]))
            pending, visited, count = list(pdf.objects), set(), 0
            while pending:
                obj = pending.pop()
                if not isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream, pikepdf.Array)):
                    continue
                if obj.objgen[0]:
                    if obj.objgen in visited:
                        continue
                    visited.add(obj.objgen)
                count += 1
                if count > MAX_OBJECTS:
                    raise RecognitionError("pdf_structure_limit")
                if isinstance(obj, pikepdf.Array):
                    pending.extend(obj)
                else:
                    if obj.get("/JS") is not None or str(obj.get("/S", "")) in ("/JavaScript", "/Launch", "/SubmitForm", "/ImportData"):
                        raise RecognitionError("unsafe_pdf_action")
                    pending.extend(obj.values())
                if len(pending) > MAX_OBJECTS:
                    raise RecognitionError("pdf_structure_limit")
            syntax = pdf.check_pdf_syntax()
            warned = checked_stream_warnings(pdf, data, syntax) if syntax else {}
            accepted_warnings = set()
            # Only an actually referenced RGB ICC profile can accompany the bound invoice stream.
            for key in icc_references & set(warned):
                stream = pdf.get_object(key); raw = warned[key][1]
                if (stream.get("/N") == 3 and len(raw) >= 128 and raw[16:20] == b"RGB "
                        and raw[36:40] == b"acsp" and int.from_bytes(raw[:4], "big") == len(raw)):
                    accepted_warnings.add(key)
            claim = metadata_claim(pdf)
            found, total = {}, 0
            claim_file_seen = False
            for record in embedded_files(pdf):
                spec = record["spec"]
                expected = claim is not None and claim["DocumentFileName"] in record["names"]
                claim_file_seen |= expected
                ef = spec.get("/EF")
                if ef is None:
                    if expected:
                        raise RecognitionError("external_invoice_attachment")
                    continue  # Never follow external /F or /UF.
                stream_ids = set()
                for _, stream in ef.items():
                    if not isinstance(stream, pikepdf.Stream):
                        raise RecognitionError("malformed_embedded_files")
                    key = object_key(stream)
                    if key in stream_ids:
                        continue
                    stream_ids.add(key)
                    params = stream.get("/Params")
                    if params is not None and int(params.get("/Size", 0)) > MAX_XML:
                        raise RecognitionError("embedded_size_limit")
                    raw = stream.read_bytes()  # Native decoding is fenced by the worker RAM/CPU deadline.
                    total += len(raw)
                    if len(raw) > MAX_XML or total > MAX_EMBEDDED_TOTAL:
                        raise RecognitionError("embedded_size_limit")
                    if not looks_xml(raw):
                        if expected:
                            raise RecognitionError("malformed_hybrid_invoice")
                        continue
                    invoice = identity(raw)
                    if invoice is None:
                        if expected:
                            raise RecognitionError("malformed_hybrid_invoice")
                        continue
                    if invoice.syntax not in ("CII", "CII-1"):
                        raise RecognitionError("unsupported_hybrid_syntax")
                    if (claim is None or not expected or not record["associated"]
                            or str(spec.get("/AFRelationship", "")) not in ("/Alternative", "/Data", "/Source")):
                        raise RecognitionError("missing_hybrid_context")
                    if claim["Version"] == "3.0" and not (invoice.family == "xrechnung" and invoice.syntax == "CII"):
                        raise RecognitionError("unsupported_hybrid_version")
                    acceptable = {invoice.profile}
                    if invoice.family == "xrechnung":
                        acceptable.add("EN 16931")
                    if claim["ConformanceLevel"] not in acceptable:
                        raise RecognitionError("hybrid_profile_mismatch")
                    legacy_namespace = "urn:ferd:pdfa:CrossIndustryDocument:invoice:1p0#"
                    facturx_namespace = "urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"
                    if invoice.family == "zugferd1":
                        compatible = claim["namespace"] == legacy_namespace and claim["Version"] == "1.0"
                    else:
                        compatible = (claim["namespace"] == facturx_namespace and (claim["Version"] == "1.0"
                                      or claim["Version"] == "3.0" and invoice.family == "xrechnung" and invoice.syntax == "CII")
                                      or claim["namespace"].startswith("urn:zugferd:") and claim["Version"].startswith("2."))
                    if not compatible:
                        raise RecognitionError("hybrid_namespace_mismatch")
                    found[sha256(raw).hexdigest()] = invoice
                    if key in warned:
                        accepted_warnings.add(key)
            if len(found) > 1:
                raise RecognitionError("ambiguous_embedded_invoices")
            if found:
                if set(warned) - accepted_warnings:
                    raise RecognitionError("malformed_pdf")
                warnings = (["pdf_stream_missing_checksum"] if warned else []) + (
                    ["hybrid_xrechnung_metadata_version"] if claim["Version"] == "3.0" else [])
                return Finding("recognized", "E-Rechnung", "ZUGFeRD/Factur-X", "hybrid_invoice_structure", warnings=tuple(warnings))
            if warned:
                raise RecognitionError("malformed_pdf")
            if claim is not None:
                raise RecognitionError("malformed_hybrid_invoice" if claim_file_seen else "missing_hybrid_invoice")
            return None  # Ordinary PDF: AP03b must examine every page's text/OCR.
    except RecognitionError:
        raise
    except pikepdf.PasswordError:
        raise RecognitionError("encrypted_pdf") from None
    except (pikepdf.PdfError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise RecognitionError("malformed_pdf") from None
