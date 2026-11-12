from hashlib import sha256
from classifier.model import Finding, RecognitionError, failed, ignored, unknown
from classifier.xml_invoice import identity, looks_xml
from classifier.pdf_structure import detect_pdf

MAX_INPUT = 25 * 1024 * 1024


def recognize(data):
    if not data:
        return failed("empty_document")
    if len(data) > MAX_INPUT:
        return failed("input_size_limit")
    try:
        if b"%PDF-" in data[:1024]:
            structured = detect_pdf(data)
            if structured is not None:
                return structured
            from classifier.text_pdf import analyze_pdf
            return analyze_pdf(data)
        if looks_xml(data):
            invoice = identity(data)
            if invoice is None:
                return ignored("non_invoice_xml")
            if invoice.family != "xrechnung":
                return failed("hybrid_pdf_required")
            return Finding("recognized", "E-Rechnung", "XRechnung-" + invoice.syntax, "invoice_xml_structure")
        return ignored()
    except RecognitionError as error:
        if error.code.startswith("ambiguous_") or error.code in {
            "unsupported_hybrid_version", "hybrid_profile_mismatch", "hybrid_namespace_mismatch",
        }:
            # Preserve the structural guard and reason; never silently treat a
            # disputed hybrid as an ordinary invoice or a technical parser crash.
            return unknown(error.code)
        return failed(error.code)


def classify(data):
    return recognize(data).result(sha256(data).hexdigest())
