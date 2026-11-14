"""Pure AP07 identities, validated settings, calendar slots and fixed templates."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
KINDS = {"certificate", "daily", "weekly", "errors", "outage", "recovery", "test"}
DEFAULTS = dict(recipients=[], certificate_time="08:00", daily_time="08:15",
    weekly_time="08:30", weekly_day=0, errors_enabled=True, outages_enabled=True,
    daily_enabled=True, weekly_enabled=True, error_bundle_minutes=15,
    error_repeat_hours=24, outage_after_minutes=15, outage_repeat_hours=24)

class NotificationError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)

def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)

def identity(parts):
    return hashlib.sha256(canonical(parts).encode("ascii")).hexdigest()

CERTIFICATE_TOKEN = identity(["graph-credential-certificate"])
CERTIFICATE_SERIES_FIELDS = ("series_id","fingerprint","not_before","expires_at","started_at")

def checked_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise NotificationError("notification_identity_invalid", 422)
    return value

def checked_actor(value):
    if not isinstance(value, str) or not (value in {"system", "operator"} or re.fullmatch(r"ad:[0-9a-fA-F]{32}", value)):
        raise NotificationError("notification_actor_invalid", 422)
    return value.lower()

def graph_scope(tenant, client, mailbox):
    try:
        tenant, client = str(UUID(tenant)), str(UUID(client))
        if (not isinstance(mailbox, str) or len(mailbox) > 254 or mailbox.count("@") != 1
                or any(c.isspace() or ord(c) < 33 or c in "/\\?#%" for c in mailbox)):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise NotificationError("notification_scope_invalid", 422) from None
    return identity([tenant, client, mailbox.lower()])

def test_request(request_id, expected_version):
    try:
        parsed = UUID(request_id)
        if not parsed.int or type(expected_version) is not int or expected_version < 0:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise NotificationError("notification_request_invalid", 422) from None
    return dict(request_id=str(parsed), expected_version=expected_version)

def checked_settings(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise NotificationError("notification_settings_invalid", 422)
    result = dict(DEFAULTS, **value)
    recipients = result["recipients"]
    if not isinstance(recipients, list) or not 1 <= len(recipients) <= 10:
        raise NotificationError("notification_recipients_invalid", 422)
    normalized = []
    for address in recipients:
        if (not isinstance(address, str) or len(address) > 254
                or not re.fullmatch(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", address)
                or "." not in address.split("@")[1] or ".." in address):
            raise NotificationError("notification_recipients_invalid", 422)
        normalized.append(address.lower())
        local, domain = address.split("@")
        if (len(local) > 64 or local.startswith(".") or local.endswith(".")
                or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in domain.split("."))):
            raise NotificationError("notification_recipients_invalid", 422)
    if len(set(normalized)) != len(normalized):
        raise NotificationError("notification_recipients_duplicate", 422)
    result["recipients"] = sorted(normalized)
    for name in ("certificate_time", "daily_time", "weekly_time"):
        if not isinstance(result[name], str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", result[name]):
            raise NotificationError("notification_time_invalid", 422)
    for name in ("errors_enabled", "outages_enabled", "daily_enabled", "weekly_enabled"):
        if type(result[name]) is not bool:
            raise NotificationError("notification_settings_invalid", 422)
    for name, lower, upper in (("weekly_day", 0, 6), ("error_bundle_minutes", 15, 1440),
            ("error_repeat_hours", 24, 168), ("outage_after_minutes", 5, 1440),
            ("outage_repeat_hours", 24, 168)):
        if type(result[name]) is not int or not lower <= result[name] <= upper:
            raise NotificationError("notification_settings_invalid", 422)
    return result

def wall_instant(day, hour):
    wall = datetime.combine(day, time.fromisoformat(hour))
    # Roundtrip rejects a nonexistent local time. Earliest instant resolves a fold.
    for _ in range(181):
        candidates = []
        for fold in (0, 1):
            local = wall.replace(tzinfo=BERLIN, fold=fold)
            utc = local.astimezone(timezone.utc)
            if utc.astimezone(BERLIN).replace(tzinfo=None) == wall:
                candidates.append(int(utc.timestamp()))
        if candidates:
            return min(candidates)
        wall += timedelta(minutes=1)
    raise NotificationError("notification_calendar_invalid", 422)

def midnight(day):
    return wall_instant(day, "00:00")

@dataclass(frozen=True)
class Slot:
    kind: str
    start: int
    end: int
    due: int
    stale: int
    tag: str = ""

    def __post_init__(self):
        if (self.kind not in KINDS or any(type(x) is not int for x in (self.start, self.end, self.due, self.stale))
                or not self.start < self.end or not self.due < self.stale
                or not isinstance(self.tag, str) or len(self.tag) > 128):
            raise NotificationError("notification_slot_invalid", 422)

    def key(self, instance, scope):
        return identity([instance, checked_key(scope), self.kind, self.start, self.end, self.tag])

@dataclass(frozen=True,kw_only=True)
class CertificateSlot(Slot):
    scope_key: str
    series_id: str
    fingerprint: str
    not_before: int
    expires_at: int
    started_at: int

    def __post_init__(self):
        super().__post_init__()
        checked_key(self.scope_key);checked_key(self.fingerprint)
        if (self.kind != "certificate" or not isinstance(self.series_id,str)
                or not re.fullmatch(r"[0-9a-f]{32}",self.series_id)
                or any(type(value) is not int for value in (self.not_before,self.expires_at,self.started_at))
                or self.not_before >= self.expires_at or self.tag != self.fingerprint):
            raise NotificationError("notification_certificate_plan_invalid",422)

    def warning(self):
        return {name:getattr(self,name) for name in CERTIFICATE_SERIES_FIELDS}

def calendar_slot(kind, now, config, *, certificate=""):
    today = datetime.fromtimestamp(now, timezone.utc).astimezone(BERLIN).date()
    if kind == "certificate":
        checked_key(certificate)
        return Slot(kind, midnight(today), midnight(today + timedelta(days=1)),
            wall_instant(today, config["certificate_time"]), midnight(today + timedelta(days=1)), certificate)
    if kind == "daily":
        day = today if now >= wall_instant(today, config["daily_time"]) else today - timedelta(days=1)
        return Slot(kind, midnight(day - timedelta(days=1)), midnight(day),
            wall_instant(day, config["daily_time"]), wall_instant(day + timedelta(days=1), config["daily_time"]))
    if kind == "weekly":
        monday = today - timedelta(days=today.weekday())
        day = monday + timedelta(days=config["weekly_day"])
        if now < wall_instant(day, config["weekly_time"]):
            day -= timedelta(days=7)
        end_day = day - timedelta(days=day.weekday())
        return Slot(kind, midnight(end_day - timedelta(days=7)), midnight(end_day),
            wall_instant(day, config["weekly_time"]), wall_instant(day + timedelta(days=7), config["weekly_time"]))
    raise NotificationError("notification_kind_invalid", 422)

def certificate_slot(scope,warning,now,config):
    slot = calendar_slot("certificate",now,config,certificate=warning["fingerprint"])
    return CertificateSlot(slot.kind,slot.start,slot.end,slot.due,slot.stale,slot.tag,
        scope_key=scope,**{name:warning[name] for name in CERTIFICATE_SERIES_FIELDS})

def certificate_level(expires_at, now):
    remaining = expires_at - now
    return dict(remaining_seconds=remaining, expired=remaining <= 0,
        severity="red" if remaining <= 86400 else "orange" if remaining <= 10 * 86400 else "healthy")

class OperationBudget:
    def __init__(self, *, clock, seconds=80):
        if not 0 < seconds <= 80:
            raise ValueError("Notification total budget must be at most80s")
        self.clock, self.deadline = clock, clock() + seconds

    def remaining(self):
        return max(0, self.deadline - self.clock())

    def child_seconds(self):
        return min(60, max(0, self.remaining() - 10))

SUBJECTS = dict(test="Test der Benachrichtigungen", certificate="Graph-Zertifikat läuft ab",
    daily="Tagesbericht", weekly="Wochenbericht", errors="Verarbeitungsfehler",
    outage="Längerer technischer Ausfall", recovery="Technischer Ausfall beendet")
REPORT_FIELDS = {"messages", "attachments", "unknown_open", "stored_receipts", "duplicates",
    "attachment_errors", "blocked_messages", "E-Rechnung", "PDF", "Zahlungsavis", "Mahnung"}

def make_payload(slot, key, config, data, as_of, *, origin=None):
    # Text comes from fixed vocabulary and typed, bounded server-side facts only.
    if type(as_of) is not int or not isinstance(data, dict):
        raise NotificationError("notification_facts_invalid", 422)
    lines = ["Automatische Meldung des E-Rechnungsimporters.", "Auftrag: " + checked_key(key),
        "Stand: " + datetime.fromtimestamp(as_of, BERLIN).isoformat()]
    if slot.kind == "test":
        if data:
            raise NotificationError("notification_facts_invalid", 422)
        lines += ["Dies ist eine Testnachricht. Sie enthält keine Rechnungs- oder Mailinhalte.",
            "Eine Annahme durch den Maildienst bestätigt noch keinen Empfang."]
    elif slot.kind in {"daily", "weekly"}:
        if set(data) != REPORT_FIELDS or any(type(v) is not int or v < 0 for v in data.values()):
            raise NotificationError("notification_facts_invalid", 422)
        lines += ["Im Zeitraum erstmals protokollierte Vorgänge; Zustände bei Berichtserstellung.",
            "Zeitraum Berlin: " + datetime.fromtimestamp(slot.start, BERLIN).isoformat()
            + " bis ausschließlich " + datetime.fromtimestamp(slot.end, BERLIN).isoformat()]
        labels = {"messages":"Vorgänge", "attachments":"Anhänge", "unknown_open":"Offene unbekannte Anhänge",
            "stored_receipts":"Anhänge mit Ablagebeleg", "duplicates":"Dubletten",
            "attachment_errors":"Anhänge mit technischem Fehler", "blocked_messages":"Gesperrte Vorgänge"}
        lines += [labels.get(name, "Zuordnung " + name) + ": " + str(data[name]) for name in sorted(data)]
    elif slot.kind == "certificate":
        if (set(data) != {"fingerprint", "expires_at", "remaining_seconds"} or
                any(type(data[name]) is not int for name in ("expires_at", "remaining_seconds"))):
            raise NotificationError("notification_facts_invalid", 422)
        lines += ["Graph-Anmeldezertifikat: " + checked_key(data["fingerprint"]),
            "Ablauf: " + datetime.fromtimestamp(data["expires_at"], BERLIN).isoformat(),
            "Verbleibende Zeit in Sekunden: " + str(data["remaining_seconds"]),
            "Die Warnserie endet erst nach geprüfter Anmeldung mit gültigem Nachfolgezertifikat."]
    else:
        if (set(data) != {"source", "first_seen", "last_seen", "count", "codes"}
                or data["source"] not in {"api", "graph", "processing"}
                or any(type(data[name]) is not int or data[name] < 0 for name in ("first_seen", "last_seen", "count"))
                or not isinstance(data["codes"], list) or len(data["codes"]) > 10
                or any(not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", code) for code in data["codes"])):
            raise NotificationError("notification_facts_invalid", 422)
        lines += ["Prüfquelle: " + data["source"], "Beobachtete Ereignisse: " + str(data["count"]),
            "Erstmals: " + datetime.fromtimestamp(data["first_seen"], BERLIN).isoformat(),
            "Zuletzt: " + datetime.fromtimestamp(data["last_seen"], BERLIN).isoformat(),
            "Gründe: " + ", ".join(data["codes"])]
    if origin is not None:
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise NotificationError("notification_origin_invalid", 422)
        lines.append("Anwendung: " + origin.rstrip("/"))
    payload = dict(message=dict(subject="E-Rechnungsimporter – " + SUBJECTS[slot.kind],
        body=dict(contentType="Text", content="\n".join(lines)),
        toRecipients=[dict(emailAddress=dict(address=a)) for a in config["recipients"]],
        internetMessageHeaders=[dict(name="x-importer-notification-key", value=key),
            dict(name="x-importer-template-version", value="ap07-1")]), saveToSentItems=True)
    if len(canonical(payload)) > 16384:
        raise NotificationError("notification_payload_limit", 422)
    return payload
