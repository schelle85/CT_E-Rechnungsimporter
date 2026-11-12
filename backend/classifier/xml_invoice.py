"""Namespace/profile/structure recognition, explicitly not invoice validation."""
from dataclasses import dataclass
import re
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError
from classifier.model import RecognitionError

MAX_XML = 1024 * 1024
MAX_NODES = 20000
MAX_DEPTH = 48
MAX_ATTRIBUTE = 8192
RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
XR = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
PROFILES = {
    "urn:factur-x.eu:1p0:minimum": "MINIMUM",
    "urn:factur-x.eu:1p0:basicwl": "BASIC WL",
    "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic": "BASIC",
    "urn:cen.eu:en16931:2017": "EN 16931",
    "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended": "EXTENDED",
}


@dataclass(frozen=True)
class Identity:
    family: str
    syntax: str
    profile: str


def looks_xml(data):
    # Only sniff the first non-whitespace code unit. Do not silently truncate
    # valid XML before the root; parsing/size enforcement remains in safe_xml.
    whitespace = b" \t\r\n"
    offset, byteorder = 0, None
    if data.startswith(b"\xff\xfe"):
        offset, byteorder = 2, "little"
    elif data.startswith(b"\xfe\xff"):
        offset, byteorder = 2, "big"
    elif len(data) >= 2 and data[0] in whitespace + b"<" and data[1] == 0:
        byteorder = "little"
    elif len(data) >= 2 and data[0] == 0 and data[1] in whitespace + b"<":
        byteorder = "big"
    if byteorder is not None:
        while offset + 1 < len(data):
            unit = int.from_bytes(data[offset:offset + 2], byteorder)
            if unit not in whitespace:
                return unit == ord("<")
            offset += 2
        return False
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.lstrip(whitespace).startswith(b"<")


def safe_xml(data):
    if len(data) > MAX_XML:
        raise RecognitionError("xml_size_limit")
    try:
        root = ET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException:
        raise RecognitionError("unsafe_xml") from None
    except (ParseError, ValueError, UnicodeError):
        raise RecognitionError("malformed_xml") from None
    pending, count = [(root, 1)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise RecognitionError("xml_structure_limit")
        if node.tag == "{http://www.w3.org/2001/XInclude}include":
            raise RecognitionError("unsafe_xml")
        if any(len(k) + len(v) > MAX_ATTRIBUTE for k, v in node.attrib.items()):
            raise RecognitionError("xml_attribute_limit")
        if "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation" in node.attrib:
            # It is inert metadata: never load a schema or follow this location.
            pass
        pending.extend((child, depth + 1) for child in node)
    return root


def one(root, path, *, text=False):
    values = root.findall(path)
    if len(values) != 1 or text and not (values[0].text or "").strip():
        raise RecognitionError("malformed_invoice")
    return values[0]


def amount(root, path):
    value = (one(root, path, text=True).text or "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise RecognitionError("malformed_invoice")


def identity(data):
    root = safe_xml(data)
    if root.tag == "{urn:ferd:CrossIndustryDocument:invoice:1p0}CrossIndustryDocument":
        legacy_rsm = "urn:ferd:CrossIndustryDocument:invoice:1p0"
        legacy_ram = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:12"
        legacy_udt = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:15"
        profile = one(root, f"{{{legacy_rsm}}}SpecifiedExchangedDocumentContext/{{{legacy_ram}}}GuidelineSpecifiedDocumentContextParameter/{{{legacy_ram}}}ID", text=True).text.strip()
        profiles = {"urn:ferd:CrossIndustryDocument:invoice:1p0:" + p: p.upper() for p in ("basic", "comfort", "extended")}
        if profile not in profiles:
            raise RecognitionError("unsupported_invoice_profile")
        document = one(root, f"{{{legacy_rsm}}}HeaderExchangedDocument")
        one(document, f"{{{legacy_ram}}}ID", text=True)
        if one(document, f"{{{legacy_ram}}}TypeCode", text=True).text.strip() not in {"380", "381", "384", "386", "389"}:
            raise RecognitionError("unsupported_invoice_type")
        one(document, f"{{{legacy_ram}}}IssueDateTime/{{{legacy_udt}}}DateTimeString", text=True)
        transaction = one(root, f"{{{legacy_rsm}}}SpecifiedSupplyChainTradeTransaction")
        agreement = one(transaction, f"{{{legacy_ram}}}ApplicableSupplyChainTradeAgreement")
        for party in ("SellerTradeParty", "BuyerTradeParty"):
            if not list(one(agreement, f"{{{legacy_ram}}}{party}")):
                raise RecognitionError("malformed_invoice")
        settlement = one(transaction, f"{{{legacy_ram}}}ApplicableSupplyChainTradeSettlement")
        one(settlement, f"{{{legacy_ram}}}InvoiceCurrencyCode", text=True)
        totals = one(settlement, f"{{{legacy_ram}}}SpecifiedTradeSettlementMonetarySummation")
        total_name = "DuePayableAmount" if totals.findall(f"{{{legacy_ram}}}DuePayableAmount") else "GrandTotalAmount"
        amount(totals, f"{{{legacy_ram}}}{total_name}")
        return Identity("zugferd1", "CII-1", profiles[profile])
    if root.tag in ("{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice",
                    "{urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2}CreditNote"):
        customization = (one(root, f"{{{CBC}}}CustomizationID", text=True).text or "").strip()
        if customization != XR:
            raise RecognitionError("unsupported_invoice_profile")
        credit = root.tag.endswith("CreditNote")
        for name in ("ID", "IssueDate", "DocumentCurrencyCode", "CreditNoteTypeCode" if credit else "InvoiceTypeCode"):
            one(root, f"{{{CBC}}}{name}", text=True)
        type_code = one(root, f"{{{CBC}}}" + ("CreditNoteTypeCode" if credit else "InvoiceTypeCode"), text=True).text.strip()
        if type_code not in ({"381"} if credit else {"380", "384", "386", "389"}):
            raise RecognitionError("unsupported_invoice_type")
        for name in ("AccountingSupplierParty", "AccountingCustomerParty"):
            party = one(root, f"{{{CAC}}}{name}/{{{CAC}}}Party")
            if not list(party):
                raise RecognitionError("malformed_invoice")
        amount(root, f"{{{CAC}}}LegalMonetaryTotal/{{{CBC}}}PayableAmount")
        lines = root.findall(f"{{{CAC}}}" + ("CreditNoteLine" if credit else "InvoiceLine"))
        if not lines:
            raise RecognitionError("malformed_invoice")
        for line in lines:
            one(line, f"{{{CBC}}}ID", text=True)
            one(line, f"{{{CAC}}}Item")
            amount(line, f"{{{CBC}}}LineExtensionAmount")
        return Identity("xrechnung", "UBL-CreditNote" if credit else "UBL-Invoice", "XRECHNUNG")
    if root.tag == f"{{{RSM}}}CrossIndustryInvoice":
        context = f"{{{RSM}}}ExchangedDocumentContext/{{{RAM}}}GuidelineSpecifiedDocumentContextParameter/{{{RAM}}}ID"
        profile = (one(root, context, text=True).text or "").strip()
        if profile != XR and profile not in PROFILES:
            raise RecognitionError("unsupported_invoice_profile")
        document = one(root, f"{{{RSM}}}ExchangedDocument")
        for name in ("ID", "TypeCode"):
            one(document, f"{{{RAM}}}{name}", text=True)
        if one(document, f"{{{RAM}}}TypeCode", text=True).text.strip() not in {"380", "381", "384", "386", "389"}:
            raise RecognitionError("unsupported_invoice_type")
        one(document, f"{{{RAM}}}IssueDateTime/{{{UDT}}}DateTimeString", text=True)
        transaction = one(root, f"{{{RSM}}}SupplyChainTradeTransaction")
        agreement = one(transaction, f"{{{RAM}}}ApplicableHeaderTradeAgreement")
        for party in ("SellerTradeParty", "BuyerTradeParty"):
            if not list(one(agreement, f"{{{RAM}}}{party}")):
                raise RecognitionError("malformed_invoice")
        settlement = one(transaction, f"{{{RAM}}}ApplicableHeaderTradeSettlement")
        one(settlement, f"{{{RAM}}}InvoiceCurrencyCode", text=True)
        amount(settlement, f"{{{RAM}}}SpecifiedTradeSettlementHeaderMonetarySummation/{{{RAM}}}DuePayableAmount")
        if profile not in ("urn:factur-x.eu:1p0:minimum", "urn:factur-x.eu:1p0:basicwl"):
            lines = transaction.findall(f"{{{RAM}}}IncludedSupplyChainTradeLineItem")
            if not lines:
                raise RecognitionError("malformed_invoice")
            for line in lines:
                one(line, f"{{{RAM}}}AssociatedDocumentLineDocument/{{{RAM}}}LineID", text=True)
                one(line, f"{{{RAM}}}SpecifiedTradeProduct/{{{RAM}}}Name", text=True)
                amount(line, f"{{{RAM}}}SpecifiedLineTradeSettlement/{{{RAM}}}SpecifiedTradeSettlementLineMonetarySummation/{{{RAM}}}LineTotalAmount")
        return Identity("xrechnung" if profile == XR else "facturx", "CII", "XRECHNUNG" if profile == XR else PROFILES[profile])
    local = root.tag.rsplit("}", 1)[-1]
    if local in ("Invoice", "CreditNote", "CrossIndustryInvoice", "CrossIndustryDocument"):
        raise RecognitionError("unsupported_invoice_namespace")
    return None
