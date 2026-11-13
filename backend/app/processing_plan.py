"""AP05 identities and mail decisions. No I/O, job activation or classification rules."""
from dataclasses import dataclass
import re
from app.graph_mail import CUTOFF, identifier
from app.storage_plan import CATEGORIES, aware_utc, digest


class ProcessingError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def message_key(mailbox, message_id):
    if not isinstance(mailbox, str) or not mailbox or len(mailbox) > 254:
        raise ProcessingError("processing_mailbox_invalid")
    return digest([mailbox.lower(), identifier(message_id)])


def attachment_key(mailbox, message_id, attachment_id):
    return digest([message_key(mailbox, message_id), identifier(attachment_id)])


def signature_image(attachment, finding=None, original_sha256=None):
    mime = (attachment.content_type or "").split(";", 1)[0].strip().lower()
    if attachment.kind != "file" or not attachment.inline or not mime.startswith("image/"):
        return False
    try:
        value = checked_finding(finding, original_sha256)
    except ProcessingError:
        return False
    return value["status"] == "ignored" and value["reason"] == "unsupported_attachment"


def requires_flag(attachments, raw_hashes=None, findings=None):
    raw_hashes = raw_hashes or {}
    findings = findings or {}
    values = {item.id: item for item in attachments}
    return sum(not signature_image(item, findings.get(item.id), raw_hashes.get(item.id)) for item in values.values()) > 1


def source_manifest(mailbox, message, attachments):
    timestamp = aware_utc(message.received_at)
    if timestamp < CUTOFF:
        raise ProcessingError("processing_before_cutoff")
    values = {}
    for item in attachments:
        key = attachment_key(mailbox, message.id, item.id)
        if (not isinstance(item.name, str) or len(item.name) > 1024 or type(item.size) is not int
                or item.size < 0 or type(item.inline) is not bool
                or item.kind not in {"file", "item", "reference", "unsupported"}
                or item.content_type is not None and not isinstance(item.content_type, str)):
            raise ProcessingError("processing_attachment_invalid")
        value = [item.id, item.name, item.size, item.content_type, item.inline, item.kind]
        if key in values and values[key] != value:
            raise ProcessingError("processing_manifest_conflict")
        values[key] = value
    canonical = sorted(values.values(), key=lambda value: value[0])
    return {"message_key": message_key(mailbox, message.id), "received_at": timestamp.isoformat(),
            "manifest_key": digest(canonical), "attachments": canonical, "attachment_count": len(canonical)}


def checked_finding(value, original_sha256):
    required = {"status", "category", "reason", "original_sha256", "rule_version"}
    allowed = required | {"format", "method"}
    if (not isinstance(original_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", original_sha256)
            or not isinstance(value, dict) or not required <= set(value) or set(value) - allowed
            or value.get("original_sha256") != original_sha256 or value.get("rule_version") != "ap03-4"
            or value.get("status") not in {"recognized", "unknown", "ignored", "failed"}
            or not isinstance(value.get("reason"), str) or not re.fullmatch(r"[a-z0-9_]{1,128}", value["reason"])):
        raise ProcessingError("processing_finding_invalid")
    category = value["category"]
    if value["status"] == "recognized":
        if not isinstance(category, str) or category not in CATEGORIES:
            raise ProcessingError("processing_finding_invalid")
    elif category is not None:
        raise ProcessingError("processing_finding_invalid")
    for field in ("format", "method"):
        item = value.get(field)
        if item is not None and (not isinstance(item, str) or len(item) > 128 or any(ord(char) < 32 for char in item)):
            raise ProcessingError("processing_finding_invalid")
    return dict(value)


def correction_allowed(finding):
    # The frozen classifier emits these document-type ambiguities only after its structural guards.
    return (finding.get("status") == "unknown" and finding.get("reason") in {
        "ambiguous_mixed_document", "ambiguous_payment_advice", "ambiguous_reminder", "ambiguous_invoice", "ambiguous_pdf"
    } and finding.get("method") in {"pdf_text", "ocr", "pdf_text_ocr"})


@dataclass(frozen=True)
class AttachmentOutcome:
    status: str
    category: str | None = None
    storage: str | None = None

    def __post_init__(self):
        if self.status not in {"pending", "recognized", "unknown", "ignored", "failed"}:
            raise ProcessingError("processing_outcome_invalid")
        if self.status == "recognized":
            if not isinstance(self.category, str) or self.category not in CATEGORIES:
                raise ProcessingError("processing_outcome_invalid")
        elif self.category is not None or self.storage is not None:
            raise ProcessingError("processing_outcome_invalid")
        if self.storage not in {None, "stored", "duplicate", "busy", "failed", "operator_required"}:
            raise ProcessingError("processing_outcome_invalid")


@dataclass(frozen=True)
class MailDecision:
    destination: str | None
    state: str


def mail_decision(outcomes):
    values = tuple(outcomes)
    if any(value.status == "pending" or value.status == "recognized" and value.storage in {None, "busy"} for value in values):
        raise ProcessingError("processing_attachments_pending")
    if any(value.storage == "operator_required" for value in values):
        return MailDecision(None, "operator_required")  # Reconcile uncertainty before any new move.
    if any(value.status == "failed" or value.storage == "failed" for value in values):
        return MailDecision("Failed", "failed")
    if any(value.status == "unknown" for value in values):
        return MailDecision("unzugeordnet", "waiting_correction")
    if any(value.storage == "duplicate" for value in values):
        return MailDecision("unzugeordnet", "done")
    categories = {value.category for value in values if value.status == "recognized"}
    for category, target in (("Mahnung", "Mahnung"), ("PDF", "Nachfragen"), ("Zahlungsavis", "Zahlungsavis"), ("E-Rechnung", "Success")):
        if category in categories:
            return MailDecision(target, "done")
    return MailDecision("unzugeordnet", "done")
