"""Synthetic AP12 fixtures. POSIX policy/flock/dir-fsync are explicit Windows doubles."""
from contextlib import ExitStack, contextmanager, nullcontext
import base64
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import httpx

from app.graph import GraphError
from app.rotation_graph import RotationGraph
from app.rotation_journal import RootJournal
from app.rotation_model import RotationBinding, certificate_der, key_record
from notification_test_support import INSTANCE, CONFIG, NOW, material

BINDING = RotationBinding(INSTANCE, CONFIG.tenant_id, CONFIG.client_id,
    "44444444-4444-4444-4444-444444444444", CONFIG.mailbox)
OLD_ID = "55555555-5555-5555-5555-555555555555"
NEW_ID = "66666666-6666-6666-6666-666666666666"


def public_key(certificate, key_id):
    utc = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")
    return dict(keyId=key_id, type="AsymmetricX509Cert", usage="Verify",
        key=base64.b64encode(certificate_der(certificate)).decode(),
        startDateTime=utc(certificate.not_before), endDateTime=utc(certificate.expires_at))


@contextmanager
def local_journal(directory, binding=BINDING):
    """Exercise real files/replace/file-fsync; do not claim Linux policy/lock proof."""
    with ExitStack() as stack:
        stack.enter_context(patch("app.rotation_journal.directory_policy"))
        stack.enter_context(patch("app.rotation_journal.sync_directory"))
        stack.enter_context(patch("app.rotation_journal.protected_bytes", side_effect=lambda p: Path(p).read_bytes()))
        stack.enter_context(patch("app.rotation_journal.os.O_NOFOLLOW", 0, create=True))
        stack.enter_context(patch("app.rotation_journal.os.fchmod", create=True))
        journal = RootJournal(directory, binding)
        journal._locked = True  # Explicit host-lock double; session() remains Linux-only.
        yield journal


class Remote:
    def __init__(self, old):
        self.records = [key_record(public_key(old, OLD_ID))]
        self.signer, self.binding = old, BINDING
        self.adds, self.reads = 0, 0
        self.error = None
        self.visible = True
        self.candidate = None
        self.crash = False
        self.wall = lambda: NOW

    def read(self):
        self.reads += 1
        records = [dict(row) for row in self.records]
        if self.candidate is not None and self.visible:
            records.append(key_record(public_key(self.candidate, NEW_ID)))
        return records

    def add(self, certificate):
        self.adds += 1
        if self.crash:
            raise SystemExit("synthetic process interruption after durable permission")
        if self.error is not None:
            if self.error.uncertain:
                self.candidate = certificate  # accepted remotely, reply lost
            raise self.error
        self.candidate = certificate
        return NEW_ID


@contextmanager
def transport(handler, signer, *, binding=BINDING):
    credential = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="synthetic-token"))
    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as http:
        with patch("app.rotation_graph.request_deadline", side_effect=lambda *a, **k: nullcontext()):
            yield RotationGraph(binding, signer, credential, http, deadline=10**12, wall=lambda:NOW)
