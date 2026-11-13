"""Manual Linux AP05 tick. Run a protected copy with python3 -I -B; installs no jobs."""
import argparse
from collections import Counter, deque
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

DOCKER = ["docker", "--host", "unix:///var/run/docker.sock"]
ENVIRONMENT = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}
KEY = re.compile(r"[0-9a-f]{64}")
OWNER = re.compile(r"[0-9a-f]{32}")


class CleanupFailure(RuntimeError):
    pass


def protected(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError()
    for parent in [*reversed(path.parents), path]:
        info = parent.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise ValueError()
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027 or info.st_size > 65536:
        raise ValueError()
    return path


def profile(path):
    value = json.loads(protected(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"graph_config", "graph_credential", "processing_config",
            "db_password", "db_host", "db_name", "db_user", "networks", "storage_root", "storage_gid"}:
        raise ValueError()
    for name in ("graph_config", "graph_credential", "processing_config", "db_password"):
        value[name] = str(protected(value[name]))
    for name in ("db_host", "db_name", "db_user"):
        if not isinstance(value[name], str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", value[name]):
            raise ValueError()
    networks = value["networks"]
    if (not isinstance(networks, list) or not 1 <= len(networks) <= 2 or len(set(networks)) != len(networks)
            or any(not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", name) for name in networks)
            or type(value["storage_gid"]) is not int or not 1 <= value["storage_gid"] <= 2147483647):
        raise ValueError()
    root = Path(value["storage_root"])
    if not root.is_absolute() or root == Path("/") or root.resolve(strict=True) != root or not root.is_dir():
        raise ValueError()
    if any("," in value[name] or any(ord(char) < 32 for char in value[name])
           for name in ("graph_config", "graph_credential", "processing_config", "db_password", "storage_root")):
        raise ValueError()
    return value


def command(args, timeout, *, json_output=False):
    arguments = DOCKER + args
    deadline = time.monotonic() + timeout
    output = bytearray()
    process = subprocess.Popen(arguments, env=ENVIRONMENT, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise subprocess.TimeoutExpired(arguments, timeout)
            chunk = os.read(process.stdout.fileno(), min(8192, 65537 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > 65536:
                raise ValueError("processing_output_limit")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(arguments, timeout)
        returncode = process.wait(timeout=remaining)
    except BaseException:
        # Keep the leader unreaped until signalling its private group; no PID reuse.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        raise
    finally:
        selector.close()
        process.stdout.close()
    # Stderr is discarded directly, never captured. At most 65537 stdout bytes
    # existed in memory, including the single-byte over-limit sentinel.
    if json_output:
        value = json.loads(output)
        if not isinstance(value, dict):
            raise ValueError()
        return returncode, value
    if returncode:
        raise ValueError()
    return output.decode("utf-8").strip()


def handoff(coordinate, classify, key, working):
    result = coordinate(["advance", "--message-key", key])
    if result.get("status") != "classification_required":
        return result
    if (result.get("message_key") != key or not KEY.fullmatch(result.get("attachment_key") or "")
            or not OWNER.fullmatch(result.get("owner") or "") or type(result.get("revision")) is not int
            or result["revision"] < 0 or not KEY.fullmatch(result.get("original_sha256") or "")
            or type(result.get("byte_size")) is not int or not 0 <= result["byte_size"] <= 26214400):
        raise ValueError()
    document = Path(working) / "document"
    fd = os.open(document, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 10001 or info.st_mode & 0o077
                or info.st_size != result["byte_size"]):
            raise ValueError()
        checksum = hashlib.sha256()
        while chunk := source.read(65536):
            checksum.update(chunk)
        if checksum.hexdigest() != result["original_sha256"]:
            raise ValueError()
    document.chmod(0o400)
    try:
        finding = classify(document)
    except (OSError, ValueError, subprocess.SubprocessError):
        # A failed, bounded classifier handoff is local to this exact attachment.
        finding = {"status": "failed", "category": None, "reason": "processing_classifier_unavailable",
                   "original_sha256": result["original_sha256"], "rule_version": "ap03-4"}
    encoded = json.dumps(finding).encode("utf-8")
    if len(encoded) > 4096:
        raise ValueError()
    target = Path(working) / "finding.json"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, "wb") as output:
        output.write(encoded)
        output.flush()
        os.fsync(output.fileno())
        os.fchown(output.fileno(), 10001, 10001)
    return coordinate(["advance", "--message-key", key, "--owner", result["owner"],
        "--revision", str(result["revision"]), "--attachment-key", result["attachment_key"],
        "--finding", "/exchange/finding.json"])


class Runtime:
    def __init__(self, config, image):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError()
        if command(["image", "inspect", "--format", "{{.Id}}", image], 10) != image:
            raise ValueError()
        self.config, self.image = config, image

    def coordinator(self, arguments, working, deadline):
        name = "invoice-processing-" + uuid.uuid4().hex
        config = self.config
        def remaining():
            seconds = min(180, deadline - time.monotonic())
            if seconds <= 0:
                raise ValueError()
            return seconds
        args = ["create", "--init", "--name", name, "--label", "invoice.processing.operation=" + name,
            "--network", config["networks"][0], "--user", "10001:10001", "--group-add", str(config["storage_gid"]),
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--memory", "512m", "--memory-swap", "512m", "--cpus", "1", "--pids-limit", "96",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--workdir", "/app",
            "--env", "DB_HOST=" + config["db_host"], "--env", "DB_NAME=" + config["db_name"],
            "--env", "DB_USER=" + config["db_user"], "--env", "DB_PASSWORD_FILE=/run/secrets/db_password"]
        for source, target, readonly in (
                (config["graph_config"], "/run/importer/graph.json", True),
                (config["graph_credential"], "/run/secrets/graph_credential", True),
                (config["processing_config"], "/run/importer/processing.json", True),
                (config["db_password"], "/run/secrets/db_password", True),
                (config["storage_root"], "/importer", False), (working, "/exchange", False)):
            args += ["--mount", "type=bind,source=" + str(source) + ",target=" + target + (",readonly" if readonly else "")]
        args += [self.image, "python", "-m", "app.processing_cli", *arguments]
        try:
            command(args, min(15, remaining()))
            for network in config["networks"][1:]:
                command(["network", "connect", network, name], min(10, remaining()))
            status, value = command(["start", "-a", name], remaining(), json_output=True)
            if status != 0 or value.get("ok") is not True:
                raise ValueError()
            return value
        finally:
            self.cleanup(name)

    def classifier(self, document, deadline):
        name = "invoice-processing-classifier-" + uuid.uuid4().hex
        remaining = min(150, deadline - time.monotonic())
        if remaining <= 0:
            raise ValueError()
        args = ["run", "--rm", "--init", "--name", name, "--label", "invoice.processing.operation=" + name,
            "--network", "none", "--user", "10001:10001", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--memory", "1536m", "--memory-swap", "1536m", "--cpus", "1", "--pids-limit", "64",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m", "--workdir", "/app",
            "--mount", "type=bind,source=" + str(document) + ",target=/input/document,readonly",
            self.image, "python", "-m", "classifier.cli", "/input/document"]
        try:
            status, finding = command(args, remaining, json_output=True)
            if status not in (0, 1) or finding.get("status") not in {"recognized", "unknown", "ignored", "failed"}:
                raise ValueError()
            return finding
        finally:
            self.cleanup(name)

    @staticmethod
    def cleanup(name):
        # One operation's random exact container name; never remove networks/volumes.
        try:
            result = command(["container", "ls", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}"], 10)
            if result:
                if result != name:
                    raise ValueError()
                command(["rm", "-f", name], 20)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise CleanupFailure("processing_cleanup_failed") from None


def operate(mode, image, config, max_quanta=100):
    if os.name != "posix" or os.geteuid() != 0 or mode not in {"inbox", "corrections"} or not 1 <= max_quanta <= 100:
        raise ValueError()
    runtime = Runtime(config, image)
    with tempfile.TemporaryDirectory(prefix="invoice-processing-", dir="/dev/shm") as working:
        os.chown(working, 10001, 10001)
        os.chmod(working, 0o700)
        selected = runtime.coordinator(["select", "--mode", mode, "--limit", "50"], working, time.monotonic() + 180)
    keys = selected.get("message_keys")
    if not isinstance(keys, list) or len(keys) > 50 or any(not isinstance(key, str) or not KEY.fullmatch(key) for key in keys):
        raise ValueError()
    queue, counts = deque(dict.fromkeys(keys)), Counter()
    for _ in range(max_quanta):
        if not queue:
            break
        key = queue.popleft()
        deadline = time.monotonic() + 500  # Reserve <=40s for abort/reap plus final cleanup; whole quantum <=540s.
        with tempfile.TemporaryDirectory(prefix="invoice-processing-", dir="/dev/shm") as working:
            os.chown(working, 10001, 10001)
            os.chmod(working, 0o700)
            result = handoff(lambda args: runtime.coordinator(args, working, deadline),
                             lambda document: runtime.classifier(document, deadline), key, working)
        state = result.get("status")
        if state not in {"progress", "busy", "idle", "done", "failed", "waiting_correction", "operator_required"}:
            raise ValueError()
        counts[state] += 1
        if state == "progress":
            queue.append(key)
    return {"ok": True, "mode": mode, "quanta": sum(counts.values()), "states": dict(counts), "remaining": len(queue)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inbox", "corrections"))
    parser.add_argument("--image", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--max-quanta", type=int, default=100, choices=range(1, 101), metavar="1..100")
    args = parser.parse_args()
    def interrupted(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if not sys.flags.isolated or not sys.dont_write_bytecode:
            raise ValueError()
        protected(__file__)
        result = operate(args.mode, args.image, profile(args.profile), args.max_quanta)
    except (OSError, ValueError, TypeError, KeyError, CleanupFailure, subprocess.SubprocessError, KeyboardInterrupt):
        result = {"ok": False, "code": "processing_operator_failed", "uncertain": True}
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

