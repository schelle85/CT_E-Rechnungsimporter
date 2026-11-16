"""Root-private AP12 effect journal. Linux policy is mandatory, never an API bind."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from app.graph import GraphError, protected_bytes
from app.notification_certificate import CertificateMaterial
from app.notification_model import canonical
from app.rotation_model import candidate, records_hash, sha, unique_json, uuid

FIELDS = {"version", "operation_id", "scope_key", "old_fingerprint", "candidate_fingerprint",
    "candidate_pem_hash", "phase", "baseline", "baseline_hash", "response_key_id", "registered_key_id"}
PHASES = {"prepared", "registration_started", "registration_unknown", "registration_rejected", "registered", "candidate_verified"}
STEPS = {"prepared": {"registration_started"},
    "registration_started": {"registration_unknown", "registration_rejected", "registered"},
    "registration_unknown": {"registration_unknown", "registered"}, "registered": {"candidate_verified"}}


def directory_policy(directory):
    if os.name != "posix" or os.geteuid() != 0 or not directory.is_absolute():
        raise GraphError("rotation_host_required")
    for part in (*reversed(directory.parents), directory):
        info = part.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise GraphError("rotation_directory_invalid")
    if stat.S_IMODE(directory.stat().st_mode) != 0o700:
        raise GraphError("rotation_directory_invalid")


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class RootJournal:
    def __init__(self, directory, binding):
        self.directory, self.binding = Path(directory), binding
        directory_policy(self.directory)
        self._locked = False

    @contextmanager
    def session(self):
        import fcntl
        if self._locked:
            raise GraphError("rotation_journal_busy")
        directory_policy(self.directory)
        path = self.directory / "rotation.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
                raise GraphError("rotation_journal_invalid")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise GraphError("rotation_journal_busy") from None
            self._locked = True
            try:
                yield self
            finally:
                self._locked = False
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _require(self):
        if not self._locked:
            raise GraphError("rotation_journal_lock_required")
        directory_policy(self.directory)

    def _read(self, name):
        self._require()
        path = self.directory / name
        if not path.exists():
            # A dangling symlink is not an absent record.
            if path.is_symlink():
                raise GraphError("rotation_journal_invalid")
            return None
        try:
            return json.loads(protected_bytes(path), object_pairs_hook=unique_json)
        except (ValueError, UnicodeError):
            raise GraphError("rotation_journal_invalid") from None

    def _write(self, name, value):
        self._require()
        raw = canonical(value).encode("ascii")
        if len(raw) > 65536:
            raise GraphError("rotation_journal_limit")
        # Reject an existing unsafe destination before the atomic replacement.
        if (self.directory / name).exists() or (self.directory / name).is_symlink():
            protected_bytes(self.directory / name)
        fd, temporary = tempfile.mkstemp(prefix=".rotation-", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as output:
                os.fchmod(output.fileno(), 0o600)
                output.write(raw); output.flush(); os.fsync(output.fileno())
            os.replace(temporary, self.directory / name)
            sync_directory(self.directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def state(self, operation):
        uuid(operation)
        value = self._read(operation + ".json")
        if value is None:
            return None
        if (not isinstance(value, dict) or set(value) != FIELDS or type(value["version"]) is not int
                or value["version"] != 1 or value["operation_id"] != operation
                or value["scope_key"] != self.binding.scope or value["phase"] not in PHASES
                or not isinstance(value["baseline"], list) or len(value["baseline"]) > 64):
            raise GraphError("rotation_journal_invalid")
        for name in ("old_fingerprint", "candidate_fingerprint", "candidate_pem_hash", "baseline_hash"):
            sha(value[name])
        if len(set(value["baseline"])) != len(value["baseline"]):
            raise GraphError("rotation_journal_invalid")
        for key in value["baseline"]:
            uuid(key)
        for name in ("response_key_id", "registered_key_id"):
            if value[name] is not None:
                uuid(value[name])
        if value["phase"] in {"registered", "candidate_verified"} and value["registered_key_id"] is None:
            raise GraphError("rotation_journal_invalid")
        return value

    def material(self, operation):
        state = self.state(operation)
        if state is None:
            raise GraphError("rotation_journal_missing")
        raw = protected_bytes(self.directory / (uuid(operation) + ".pem"))
        material = CertificateMaterial.parse(raw)
        if (hashlib.sha256(raw).hexdigest() != state["candidate_pem_hash"]
                or material.fingerprint != state["candidate_fingerprint"]):
            raise GraphError("rotation_candidate_changed")
        return material

    def prepare(self, operation, old_fingerprint, records, now):
        self._require(); uuid(operation); sha(old_fingerprint)
        state = self.state(operation)
        if state is not None:
            if state["old_fingerprint"] != old_fingerprint:
                raise GraphError("rotation_request_conflict")
            self.material(operation)
            return state
        baseline = [uuid(item["key_id"]) for item in records]
        if len(set(baseline)) != len(baseline) or len(baseline) > 64:
            raise GraphError("rotation_key_metadata_invalid")
        path = self.directory / (operation + ".pem")
        if path.exists() or path.is_symlink():
            # Crash after writing PEM but before metadata: use those exact bytes.
            material = CertificateMaterial.parse(protected_bytes(path))
        else:
            material = candidate(now)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(material.pem); output.flush(); os.fsync(output.fileno())
            sync_directory(self.directory)
        if any(item.get("fingerprint") == material.fingerprint for item in records):
            raise GraphError("rotation_candidate_already_present")
        state = dict(version=1, operation_id=operation, scope_key=self.binding.scope,
            old_fingerprint=old_fingerprint, candidate_fingerprint=material.fingerprint,
            candidate_pem_hash=hashlib.sha256(material.pem).hexdigest(), phase="prepared",
            baseline=baseline, baseline_hash=records_hash(records), response_key_id=None, registered_key_id=None)
        self._write(operation + ".json", state)
        return state

    def transition(self, operation, phase, *, response_key_id=None, registered_key_id=None):
        state = self.state(operation)
        if state is None or phase not in STEPS.get(state["phase"], set()):
            raise GraphError("rotation_transition_invalid")
        for value in (response_key_id, registered_key_id):
            if value is not None:
                uuid(value)
        state = dict(state, phase=phase,
            response_key_id=response_key_id or state["response_key_id"],
            registered_key_id=registered_key_id or state["registered_key_id"])
        self._write(operation + ".json", state)
        return state

    def inventory(self):
        value = self._read("inventory.json")
        if value is None:
            return dict(version=1, scope_key=self.binding.scope, keys={})
        if (not isinstance(value, dict) or set(value) != {"version", "scope_key", "keys"}
                or type(value["version"]) is not int or value["version"] != 1 or value["scope_key"] != self.binding.scope
                or not isinstance(value["keys"], dict) or len(value["keys"]) > 64):
            raise GraphError("rotation_inventory_invalid")
        for key, item in value["keys"].items():
            uuid(key)
            if (not isinstance(item, dict) or set(item) != {"fingerprint", "operation_id", "origin", "evidence"}
                    or item["origin"] not in {"created", "adopted"}):
                raise GraphError("rotation_inventory_invalid")
            sha(item["fingerprint"]); uuid(item["operation_id"]); sha(item["evidence"])
        return value

    def record_created(self, operation):
        state = self.state(operation)
        if state is None or state["phase"] not in {"registered", "candidate_verified"}:
            raise GraphError("rotation_inventory_invalid")
        key = uuid(state["registered_key_id"])
        if key in state["baseline"]:
            raise GraphError("rotation_inventory_invalid")
        inventory = self.inventory()
        item = dict(fingerprint=state["candidate_fingerprint"], operation_id=operation,
            origin="created", evidence=state["candidate_pem_hash"])
        if key in inventory["keys"] and inventory["keys"][key] != item:
            raise GraphError("rotation_inventory_conflict")
        inventory["keys"][key] = item
        self._write("inventory.json", inventory)

    def adopt_existing(self, operation, record, *, evidence):
        """Explicit Root attestation only; never infer ownership from selected GET."""
        uuid(operation); sha(evidence); key = uuid(record["key_id"]); sha(record["fingerprint"])
        inventory = self.inventory()
        item = dict(fingerprint=record["fingerprint"], operation_id=operation, origin="adopted", evidence=evidence)
        if key in inventory["keys"] and inventory["keys"][key] != item:
            raise GraphError("rotation_inventory_conflict")
        inventory["keys"][key] = item
        self._write("inventory.json", inventory)

    def reconcile_removal(self, key, records):
        """Read-only result. Presence/unknown never grants another removeKey POST."""
        key = uuid(key)
        owned = self.inventory()["keys"].get(key)
        if owned is None:
            raise GraphError("rotation_key_unmanaged")
        matches = [item for item in records if item["key_id"] == key]
        if len(matches) > 1 or matches and matches[0]["fingerprint"] != owned["fingerprint"]:
            raise GraphError("rotation_inventory_conflict")
        return "present" if matches else "absent"
