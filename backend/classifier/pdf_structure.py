"""Use qpdf's parsed objects; never execute actions, extract paths or save the PDF."""
from hashlib import sha256
from io import BytesIO
import pikepdf
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
    if result["Version"] not in ("1.0", "2.0", "2.1", "2.2", "2.3", "2.4"):
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


def detect_pdf(data):
    try:
        with pikepdf.Pdf.open(BytesIO(data), attempt_recovery=False, suppress_warnings=True) as pdf:
            if pdf.is_encrypted:
                raise RecognitionError("encrypted_pdf")
            if not 1 <= len(pdf.pages) <= MAX_PAGES or len(pdf.objects) > MAX_OBJECTS:
                raise RecognitionError("pdf_structure_limit")
            for obj in pdf.objects:
                if isinstance(obj, pikepdf.Dictionary):
                    if obj.get("/JS") is not None or str(obj.get("/S", "")) in ("/JavaScript", "/Launch", "/SubmitForm", "/ImportData"):
                        raise RecognitionError("unsafe_pdf_action")
            if pdf.check_pdf_syntax():
                raise RecognitionError("malformed_pdf")
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
                        compatible = (claim["namespace"] == facturx_namespace and claim["Version"] == "1.0"
                                      or claim["namespace"].startswith("urn:zugferd:") and claim["Version"].startswith("2."))
                    if not compatible:
                        raise RecognitionError("hybrid_namespace_mismatch")
                    found[sha256(raw).hexdigest()] = invoice
            if len(found) > 1:
                raise RecognitionError("ambiguous_embedded_invoices")
            if found:
                return Finding("recognized", "E-Rechnung", "ZUGFeRD/Factur-X", "hybrid_invoice_structure")
            if claim is not None:
                raise RecognitionError("malformed_hybrid_invoice" if claim_file_seen else "missing_hybrid_invoice")
            return None  # Ordinary PDF: AP03b must examine every page's text/OCR.
    except RecognitionError:
        raise
    except pikepdf.PasswordError:
        raise RecognitionError("encrypted_pdf") from None
    except (pikepdf.PdfError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise RecognitionError("malformed_pdf") from None
