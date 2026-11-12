"""Bounded PDFium text extraction and conservative, explainable document rules."""
from datetime import date
import re
import unicodedata
from classifier.model import Finding, RecognitionError, failed, ignored

MAX_TEXT = 250000
MAX_PAGE_TEXT = 50000
MAX_PAGES = 30
INVOICE_TITLE = re.compile(r"^(?:(?:abschlags|schluss|teil|korrektur)?rechnung|invoice|gutschrift|credit\s+note)(?:\s*(?:(?:s?-?nr\.?|nummer|no\.?|number|#)\s*[:.#-]?\s*)?[a-z0-9./-]*\d[a-z0-9./ -]*)?\s*:?[\s]*$")
AVIS_TITLE = re.compile(r"^(?:zahlungsavis|zahlungsmitteilung|remittance\s+advice|payment\s+advice)(?:\s*(?:nr\.?|no\.?|number|#|:)\s*[a-z0-9./ -]+)?\s*$")
OTHER_TITLES = {"angebot", "bestellung", "auftragsbestatigung", "lieferschein", "mahnung", "newsletter", "werbung"}
TERMS_TITLES = {"agb", "allgemeine geschaftsbedingungen", "terms and conditions",
                "datenschutz", "datenschutzhinweise", "datenschutzerklarung", "privacy policy",
                "zahlungsbedingungen", "payment terms"}
NEGATION = re.compile(r"\b(?:keine?\s+rechnung|nicht\s+(?:als\s+)?(?:eine\s+)?rechnung|not\s+an?\s+invoice|pro[ -]?forma(?:\s+invoice|rechnung)?)\b")
INVOICE_ID = re.compile(r"\b(?:rechnungs?(?:-?nr\.?|nummer)|rechnung(?:\s+(?:nr\.?|nummer|#))?|invoice(?:\s+(?:no\.?|number|#))?|gutschrift(?:s?-?nr\.?|nummer)?)\s*[:.#-]?\s*[a-z0-9/.-]*\d[a-z0-9/.-]*\b")
AMOUNT = re.compile(r"(?<!\d)-?(?:\d{1,3}(?:[. ]\d{3})*|\d+)[,.]\d{2}(?!\d)")
TOTAL = re.compile(r"\b(?:gesamt(?:betrag|summe)?|rechnungsbetrag|zahlbetrag|zu zahlen|brutto|total|summe)\b")
DATE_LABEL = re.compile(r"\b(?:rechnungsdatum|datum|invoice date|date|zahlungsdatum|payment date|valuta)\b")
DATE_VALUE = re.compile(r"\b(?:(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})[./](\d{1,2})[./](\d{4}))\b")
PAYMENT = re.compile(r"\b(?:wir\s+(?:uberweisen|zahlen)|uberweisung|zahlung(?:\s+erfolgt|\s+am)|zahlungsdatum|valuta|we\s+(?:pay|remit)|payment date|transfer(?:red)?)\b")
OWN_INVOICE_DATE = re.compile(r"\b(?:rechnungsdatum|invoice date|gutschriftsdatum)\b")


def normalized(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


def usable(text):
    visible = [c for c in text if not c.isspace()]
    letters = sum(c.isalpha() for c in visible)
    broken = sum(c == "\ufffd" or unicodedata.category(c) in ("Co", "Cs", "Cn", "Cc") for c in visible)
    words = re.findall(r"[^\W\d_]+", normalized(text), re.UNICODE)
    plausible = [word for word in words if 2 <= len(word) <= 35
                 and (len(word) <= 3 or any(c in "aeiouy" for c in word))
                 and max(word.count(c) for c in set(word)) <= max(2, len(word) * 0.7)]
    return (letters >= 12 and broken <= max(1, len(visible) // 50) and len(plausible) >= 3
            and sum(map(len, plausible)) >= letters * 0.7)


def line_kind(line):
    if AVIS_TITLE.fullmatch(line):
        return "avis"
    if INVOICE_TITLE.fullmatch(line):
        return "invoice"
    if line in OTHER_TITLES or any(re.fullmatch(re.escape(t) + r"\s+(?:nr\.?\s*)?[a-z0-9./-]*\d[a-z0-9./ -]*", line) for t in OTHER_TITLES):
        return "other"
    if line in TERMS_TITLES:
        return "terms"
    return None


def sections(text):
    lines = [re.sub(r"\s+", " ", normalized(line)).strip() for line in text.splitlines() if line.strip()]
    headings = [(index, line_kind(line)) for index, line in enumerate(lines) if line_kind(line)]
    result = [(None, lines[:headings[0][0]] if headings else lines)]
    for offset, (index, kind) in enumerate(headings):
        end = headings[offset + 1][0] if offset + 1 < len(headings) else len(lines)
        block = lines[index:end]
        # A numbered reference under advice/other/terms is not a second invoice.
        # A standalone title or its own invoice-date section is independent evidence.
        if (kind == "invoice" and result[-1][0] in ("avis", "other", "terms")
                and any(c.isdigit() for c in lines[index])
                and not any(OWN_INVOICE_DATE.search(line) for line in block[1:])):
            result[-1][1].extend(block)
        else:
            result.append((kind, block))
    return result


def title(text):
    kinds = {kind for kind, _ in sections(text) if kind not in (None, "terms")}
    if len(kinds) > 1:
        return "mixed"
    return next(iter(kinds)) if kinds else ("terms" if any(kind == "terms" for kind, _ in sections(text)) else None)


def has_date(lines):
    for line in lines:
        if not DATE_LABEL.search(line):
            continue
        for match in DATE_VALUE.finditer(line):
            groups = match.groups()
            try:
                date(int(groups[0] or groups[5]), int(groups[1] or groups[4]), int(groups[2] or groups[3]))
                return True
            except ValueError:
                continue
    return False


def decide_pages(pages, method="pdf_text"):
    if not pages or any(not usable(p) for p in pages):
        return failed("ocr_required")
    types = {title(p) for p in pages}
    types.discard(None)
    lines = [line for page in pages for kind, block in sections(page) if kind != "terms" for line in block]
    text = "\n".join(lines)
    if len(text) > MAX_TEXT:
        raise RecognitionError("text_size_limit")
    if "mixed" in types or "invoice" in types and ("avis" in types or "other" in types) or "avis" in types and "other" in types:
        return failed("ambiguous_mixed_document")
    if NEGATION.search(text):
        return ignored("explicit_non_invoice") if "avis" not in types else failed("ambiguous_document")
    has_total = any(TOTAL.search(line) and AMOUNT.search(line) for line in lines)
    invoice_id, dated = bool(INVOICE_ID.search(text)), has_date(lines)
    if "avis" in types:
        if has_total and invoice_id and PAYMENT.search(text) and dated:
            return Finding("recognized", "Zahlungsavis", "PDF-Zahlungsavis", "avis_title_references_payment_date_total", method)
        return failed("ambiguous_payment_advice")
    if "invoice" in types:
        if invoice_id and dated and has_total:
            return Finding("recognized", "PDF", "PDF-Rechnung", "invoice_title_id_date_total", method)
        return failed("ambiguous_invoice")
    if "other" in types or types == {"terms"}:
        return ignored("irrelevant_document_type")
    return failed("ambiguous_pdf")


def extract_pages(data):
    import pypdfium2 as pdfium
    if any(flag in str(pdfium.PDFIUM_INFO).lower() for flag in ("v8", "xfa")):
        raise RecognitionError("unsafe_renderer_build")
    pages, count = [], 0
    try:
        document = pdfium.PdfDocument(data)
        try:
            if not 1 <= len(document) <= MAX_PAGES:
                raise RecognitionError("pdf_structure_limit")
            for index in range(len(document)):
                page = document[index]
                try:
                    textpage = page.get_textpage()
                    try:
                        length = textpage.count_chars()
                        count += length
                        if length > MAX_PAGE_TEXT or count > MAX_TEXT:
                            raise RecognitionError("text_size_limit")
                        pages.append(textpage.get_text_range())
                    finally:
                        textpage.close()
                finally:
                    page.close()
        finally:
            document.close()
        return pages
    except RecognitionError:
        raise
    except Exception:
        raise RecognitionError("pdf_text_failure") from None


def analyze_pdf(data):
    return decide_pages(extract_pages(data))
