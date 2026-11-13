"""Linux CIFS gate and atomic, non-replacing publication. No local fallback."""
from contextlib import contextmanager
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
from app.storage_plan import StorageError, safe_leaf


class StorageCollision(StorageError):
    """Definitive EEXIST from renameat2 only; publication did not apply."""


def _unescape(value):
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


def parse_mounts(text):
    result = {}
    for line in text.splitlines():
        fields = line.split()
        try:
            separator = fields.index("-")
            result[int(fields[0])] = dict(device=fields[2], root=_unescape(fields[3]),
                point=_unescape(fields[4]), options=set(fields[5].split(",")) | set(fields[separator + 3].split(",")),
                kind=fields[separator + 1], source=_unescape(fields[separator + 2]))
        except (ValueError, IndexError):
            raise StorageError("storage_mountinfo_invalid") from None
    return result


def mount_identity(fd, expected_source):
    info = Path(f"/proc/self/fdinfo/{fd}").read_text(encoding="ascii")
    match = re.search(r"^mnt_id:\s*(\d+)$", info, re.M)
    mounts = parse_mounts(Path("/proc/self/mountinfo").read_text(encoding="utf-8"))
    mount = mounts.get(int(match[1])) if match else None
    status = os.fstat(fd)
    device = f"{os.major(status.st_dev)}:{os.minor(status.st_dev)}"
    if not mount or mount["kind"] != "cifs" or mount["device"] != device:
        raise StorageError("storage_cifs_required")
    if mount["source"].rstrip("/").casefold() != expected_source.rstrip("/").casefold():
        raise StorageError("storage_cifs_source_mismatch")
    options = mount["options"]
    if "ro" in options or "nostrictsync" in options or not options.intersection({"cache=strict", "cache=none"}) or "cache=loose" in options:
        raise StorageError("storage_cifs_options_unsafe")
    return int(match[1]), status.st_dev


def rename_no_replace(source_fd, source, target_fd, target):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise StorageError("storage_noreplace_unsupported")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_fd, os.fsencode(source), target_fd, os.fsencode(target), 1) != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise StorageCollision("storage_target_exists")
        if code in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP, errno.EXDEV):
            raise StorageError("storage_noreplace_unsupported")
        raise StorageError("storage_publication_uncertain")


def _parts(relative):
    if not isinstance(relative, str):
        raise StorageError("storage_path_invalid")
    parts = relative.split("/")
    if not parts or any(not safe_leaf(part, max_bytes=255) for part in parts):
        raise StorageError("storage_path_invalid")
    return parts


def _open_absolute_directory(path):
    if not isinstance(path, str) or not path.startswith("/") or "//" in path:
        raise StorageError("storage_root_invalid")
    parts = path.strip("/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise StorageError("storage_root_invalid")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


class CifsFiles:
    def __init__(self, root, expected_source, staging_name, *, staging_excluded):
        if sys.platform != "linux":
            raise StorageError("storage_linux_required")
        if staging_excluded is not True:
            raise StorageError("storage_staging_exclusion_required")
        if not isinstance(expected_source, str) or not expected_source.startswith("//") or len(_parts(staging_name)) != 1:
            raise StorageError("storage_configuration_invalid")
        if staging_name.casefold() in {name.casefold() for name in ("E-Rechnung", "PDF", "Zahlungsavis", "Mahnung")}:
            raise StorageError("storage_staging_invalid")
        self.root, self.expected_source, self.staging_name = root, expected_source, staging_name
        self.fd = _open_absolute_directory(root)  # Never create the configured root.
        try:
            self.identity = mount_identity(self.fd, expected_source)
            self.inode = os.fstat(self.fd).st_ino
        except BaseException:
            os.close(self.fd)
            raise

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _check(self, fd):
        if mount_identity(fd, self.expected_source) != self.identity:
            raise StorageError("storage_mount_changed")

    def guard(self):
        current = _open_absolute_directory(self.root)
        try:
            self._check(current)
            if os.fstat(current).st_ino != self.inode:
                raise StorageError("storage_mount_changed")
            self._check(self.fd)
        finally:
            os.close(current)

    @contextmanager
    def _directory(self, parts, *, create=False):
        self.guard()
        fd = os.dup(self.fd)
        try:
            for part in parts:
                if not safe_leaf(part):
                    raise StorageError("storage_path_invalid")
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    self._check(child)
                except BaseException:
                    os.close(child)
                    raise
                os.close(fd)
                fd = child
            yield fd
        finally:
            os.close(fd)

    def stage(self, name, input_file, request):
        if len(_parts(name)) != 1:
            raise StorageError("storage_stage_invalid")
        with self._directory([self.staging_name], create=True) as parent:
            source = os.open(input_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                info = os.fstat(source)
                if not stat.S_ISREG(info.st_mode) or info.st_size != request.byte_size:
                    raise StorageError("storage_source_invalid")
                output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                try:
                    total, checksum = 0, hashlib.sha256()
                    while True:
                        chunk = os.read(source, min(65536, request.byte_size - total + 1))
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > request.byte_size:
                            raise StorageError("storage_source_invalid")
                        checksum.update(chunk)
                        remaining = memoryview(chunk)
                        while remaining:
                            written = os.write(output, remaining)
                            if written <= 0:
                                raise StorageError("storage_stage_write_failed")
                            remaining = remaining[written:]
                    if total != request.byte_size or checksum.hexdigest() != request.sha256:
                        raise StorageError("storage_integrity_failed")
                    os.fsync(output)
                finally:
                    os.close(output)  # Close/flush errors propagate; publication has not begun.
                os.fsync(parent)
            finally:
                os.close(source)

    def publish(self, name, target):
        if len(_parts(name)) != 1:
            raise StorageError("storage_stage_invalid")
        parts = _parts(target)
        with self._directory([self.staging_name]) as staging, self._directory(parts[:-1], create=True) as destination:
            self.guard()
            if not stat.S_ISREG(os.stat(name, dir_fd=staging, follow_symlinks=False).st_mode):
                raise StorageError("storage_stage_invalid")
            rename_no_replace(staging, name, destination, parts[-1])
            # An error after rename remains an uncertain publication, never a retry permission.
            os.fsync(destination)
            os.fsync(staging)

    def matches(self, target, request):
        parts = _parts(target)
        try:
            with self._directory(parts[:-1]) as parent:
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_size != request.byte_size:
                        return False
                    checksum, total = hashlib.sha256(), 0
                    while True:
                        chunk = os.read(fd, min(65536, request.byte_size - total + 1))
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > request.byte_size:
                            return False
                        checksum.update(chunk)
                    return total == request.byte_size and checksum.hexdigest() == request.sha256
                finally:
                    os.close(fd)
        except FileNotFoundError:
            return False

    def stage_exists(self, name):
        if len(_parts(name)) != 1:
            raise StorageError("storage_stage_invalid")
        try:
            with self._directory([self.staging_name]) as parent:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
                return True
        except FileNotFoundError:
            return False
