"""Immutable attachment inputs and bounded paths; no filesystem or database I/O."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from zoneinfo import ZoneInfo

CATEGORIES = frozenset({"E-Rechnung", "PDF", "Zahlungsavis", "Mahnung"})
MAX_BYTES = 25 * 1024 * 1024
_TOKEN = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])\Z", re.I)


class StorageError(Exception):
    """Only neutral reason codes cross the operator interface."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def digest(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode("ascii")).hexdigest()


def aware_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise StorageError("storage_timestamp_invalid")
    return value.astimezone(timezone.utc)


def week_key(value):
    year, week, _ = aware_utc(value).astimezone(ZoneInfo("Europe/Berlin")).isocalendar()
    return f"{year}-W{week}"


def target_directory(category, received_at):
    if category not in CATEGORIES:
        raise StorageError("storage_category_invalid")
    received = aware_utc(received_at).astimezone(ZoneInfo("Europe/Berlin"))
    return f"{category}/{received.year}/{received.month}/KW{received.isocalendar().week}"


def safe_leaf(name):
    if not isinstance(name, str) or not name or name.startswith((".", " ")) or name.endswith((".", " ")):
        return False
    if any(char in '<>:"/\\|?*' or unicodedata.category(char).startswith("C") for char in name):
        return False
    if _RESERVED.fullmatch(name.split(".", 1)[0].rstrip(" ")):
        return False
    return len(name.encode("utf-8")) <= 180


def filename(original_name, token, *, collision=False):
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        raise StorageError("storage_token_invalid")
    if safe_leaf(original_name):
        base = original_name
    else:
        extension = original_name.rpartition(".")[2] if isinstance(original_name, str) else ""
        extension = extension if re.fullmatch(r"[A-Za-z0-9]{1,12}", extension) else "bin"
        base = f"document-{token}.{extension}"
    if not collision:
        return base
    stem, separator, extension = base.rpartition(".")
    return f"{stem}--{token}.{extension}" if separator else f"{base}--{token}"


def path_key(scope, relative_path):
    # Conservative physical reservation for case-insensitive SMB, not a business duplicate.
    return digest([scope, relative_path.casefold()])


@dataclass(frozen=True)
class StorageRequest:
    scope: str
    source_key: str
    original_name: str
    byte_size: int
    sha256: str
    received_at: datetime
    category: str
    status: str = "recognized"

    def __post_init__(self):
        for value, maximum in ((self.scope, 128), (self.source_key, 4096), (self.original_name, 4096)):
            if not isinstance(value, str) or not value or len(value.encode("utf-8", errors="replace")) > maximum:
                raise StorageError("storage_input_invalid")
            if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
                raise StorageError("storage_input_invalid")
        if type(self.byte_size) is not int or not 0 <= self.byte_size <= MAX_BYTES:
            raise StorageError("storage_size_invalid")
        if not isinstance(self.sha256, str) or not _SHA.fullmatch(self.sha256):
            raise StorageError("storage_hash_invalid")
        object.__setattr__(self, "received_at", aware_utc(self.received_at))
        if self.status != "recognized" or self.category not in CATEGORIES:
            raise StorageError("storage_not_recognized")

    @property
    def key(self):
        return digest([self.scope, self.source_key])

    @property
    def immutable(self):
        return [self.scope, self.original_name, self.byte_size, self.sha256,
                self.received_at.isoformat(), self.category, self.status]

    def duplicate_key(self, processing_at):
        return digest([self.scope, week_key(processing_at), self.original_name, self.byte_size])

    def target(self, token, *, collision=False):
        return target_directory(self.category, self.received_at) + "/" + filename(self.original_name, token, collision=collision)
