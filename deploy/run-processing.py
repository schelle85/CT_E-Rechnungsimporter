"""Bounded Linux processing tick. Protected python3 -I -B; installs no jobs."""
import argparse
from collections import Counter, deque
from contextlib import contextmanager
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
PROCESSING_LOCK = "/run/invoice-importer/processing.lock"
TICK_SECONDS = 780
AUTOMATIC_MAX_QUANTA = 20


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


def controlled_directory(path):
    path=Path(path)
    if not path.is_absolute():raise ValueError()
    for part in [*reversed(path.parents),path]:
        info=part.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):raise ValueError()
    return path


@contextmanager
def host_lock(path,*,wait=0):
    import fcntl
    path=Path(path);controlled_directory(path.parent)
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);acquired=False
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o077 or info.st_nlink!=1:raise ValueError()
        until=time.monotonic()+wait
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True;break
            except BlockingIOError:
                if time.monotonic()>=until:break
                time.sleep(min(.02,max(0,until-time.monotonic())))
        yield acquired
    finally:
        if acquired:fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)


def queue_step(value,*,request=None,start=False,complete=None,ok=True,not_before=None,now=0):
    """Two fixed modes only; durable coalescing and alternation, no job registry."""
    modes={"inbox","corrections"}
    if (not isinstance(value,dict) or set(value)!={"due","last","active","not_before"}
            or not isinstance(value["due"],dict) or set(value["due"])!=modes
            or any(type(item) is not bool for item in value["due"].values())
            or value["last"] not in modes|{None} or value["active"] not in modes|{None}
            or type(value["not_before"]) is not int or not 0<=value["not_before"]<=9223372036854775807):raise ValueError()
    value=dict(value,due=dict(value["due"]));selected=None
    if request is not None:
        if request not in modes:raise ValueError()
        value["due"][request]=True
    if start:
        if value["active"] is not None:value["due"][value["active"]]=True
        due=[mode for mode in ("inbox","corrections") if value["due"][mode]]
        selected=next((mode for mode in due if mode!=value["last"]),due[0] if due else None) if now>=value["not_before"] else None
        value["active"]=selected
        if selected:value["last"]=selected;value["due"][selected]=False
    if complete is not None:
        if complete not in modes or value["active"]!=complete:raise ValueError()
        value["active"]=None
        if not ok:value["due"][complete]=True
    if not_before is not None:
        if type(not_before) is not int or not 0<=not_before<=9223372036854775807:raise ValueError()
        value["not_before"]=max(value["not_before"],not_before)
    return value,selected


def scheduled_queue(path,**change):
    path=Path(path);controlled_directory(path.parent)
    with host_lock(str(path)+".lock",wait=5) as acquired:
        if not acquired:raise ValueError("processing_schedule_busy")
        try:value=json.loads(protected(path).read_text(encoding="utf-8"))
        except FileNotFoundError:value=dict(due=dict(inbox=False,corrections=False),last=None,active=None,not_before=0)
        value,selected=queue_step(value,**change)
        fd,name=tempfile.mkstemp(prefix=".processing-",dir=path.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as output:
                json.dump(value,output,separators=(",",":"));output.flush();os.fsync(output.fileno())
            os.replace(name,path)
            parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(parent)
            finally:os.close(parent)
        finally:
            if os.path.exists(name):os.unlink(name)
        return value,selected


def mount_identity(fd,expected_source):
    match=re.search(r"^mnt_id:\s*(\d+)$",Path(f"/proc/self/fdinfo/{fd}").read_text(encoding="ascii"),re.M)
    info=os.fstat(fd);device=f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}"
    if not match:raise ValueError("processing_cifs_required")
    for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
        parts=line.split()
        if not parts or parts[0]!=match[1]:continue
        if "-" not in parts:raise ValueError("processing_cifs_required")
        split=parts.index("-")
        if split<6 or len(parts)<split+4:raise ValueError("processing_cifs_required")
        source=re.sub(r"\\([0-7]{3})",lambda value:chr(int(value[1],8)),parts[split+2])
        options=set(parts[5].split(","))|set(parts[split+3].split(","))
        if (parts[split+1]!="cifs" or parts[2]!=device or source.rstrip("/").casefold()!=expected_source.rstrip("/").casefold()
                or "ro" in options or "nostrictsync" in options or "cache=loose" in options
                or not options.intersection({"cache=strict","cache=none"})):raise ValueError("processing_cifs_required")
        return int(match[1]),info.st_dev,info.st_ino
    raise ValueError("processing_cifs_required")


def open_directory(path):
    path=Path(path)
    if not path.is_absolute() or path==Path("/"):raise ValueError()
    fd=os.open("/",os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        return fd
    except BaseException:os.close(fd);raise


class CifsBinding:
    def __init__(self,config):self.config=config;self.fd=None
    def __enter__(self):
        values=json.loads(protected(self.config["processing_config"]).read_text(encoding="utf-8"))
        self.source=values["expected_source"]
        if not isinstance(self.source,str) or not self.source.startswith("//"):raise ValueError()
        self.fd=open_directory(self.config["storage_root"])
        try:self.identity=mount_identity(self.fd,self.source)
        except BaseException:os.close(self.fd);self.fd=None;raise
        self.path=f"/proc/{os.getpid()}/fd/{self.fd}"
        return self
    def check(self):
        current=open_directory(self.config["storage_root"])
        try:
            if mount_identity(current,self.source)!=self.identity or mount_identity(self.fd,self.source)!=self.identity:raise ValueError("processing_mount_changed")
        finally:os.close(current)
    def __exit__(self,*_):
        if self.fd is not None:os.close(self.fd);self.fd=None


def profile(path,*,storage=True):
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
    if not root.is_absolute() or root == Path("/") or storage and (root.resolve(strict=True) != root or not root.is_dir()):
        raise ValueError()
    if any("," in value[name] or any(ord(char) < 32 for char in value[name])
           for name in ("graph_config", "graph_credential", "processing_config", "db_password", "storage_root")):
        raise ValueError()
    return value


def command(args, timeout, *, json_output=False):
    arguments = DOCKER + args
    reap_deadline = time.monotonic() + timeout
    deadline = reap_deadline - min(1,timeout/5)
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
        process.wait(timeout=max(.001,reap_deadline-time.monotonic()))
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
        # Hold the verified CIFS FD through create/start/cleanup. Docker receives
        # this host process's descriptor path, never an unchecked local directory.
        with CifsBinding(self.config) as binding:
            return self._coordinator(arguments,working,deadline,binding)

    def _coordinator(self, arguments, working, deadline, binding):
        name = "invoice-processing-" + uuid.uuid4().hex
        config = self.config
        def remaining():
            seconds = min(180, deadline - time.monotonic() - 35)
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
                (binding.path, "/importer", False), (working, "/exchange", False)):
            args += ["--mount", "type=bind,source=" + str(source) + ",target=" + target + (",readonly" if readonly else "")]
        args += [self.image, "python", "-m", "app.processing_cli", *arguments]
        try:
            binding.check()
            command(args, min(15, remaining()))
            for network in config["networks"][1:]:
                command(["network", "connect", network, name], min(10, remaining()))
            binding.check()
            status, value = command(["start", "-a", name], remaining(), json_output=True)
            if status != 0 or value.get("ok") is not True:
                raise ValueError()
            return value
        finally:
            self.cleanup(name,deadline)

    def classifier(self, document, deadline):
        name = "invoice-processing-classifier-" + uuid.uuid4().hex
        remaining = min(150, deadline - time.monotonic() - 35)
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
            self.cleanup(name,deadline)

    @staticmethod
    def cleanup(name,deadline=None,*,list_seconds=10,remove_seconds=20):
        # One operation's random exact container name; never remove networks/volumes.
        try:
            def seconds(maximum):
                remaining=maximum if deadline is None else min(maximum,deadline-time.monotonic())
                if remaining<=0:raise ValueError()
                return remaining
            result = command(["container", "ls", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}"], seconds(list_seconds))
            if result:
                if result != name:
                    raise ValueError()
                command(["rm", "-f", name], seconds(remove_seconds))
        except (OSError, ValueError, subprocess.SubprocessError):
            raise CleanupFailure("processing_cleanup_failed") from None


def operate(mode, image, config, max_quanta=100,*,scheduled_state=None):
    if os.name != "posix" or os.geteuid() != 0 or mode not in {"inbox", "corrections"} or not 1 <= max_quanta <= 100:
        raise ValueError()
    until=time.monotonic()+TICK_SECONDS
    if scheduled_state:scheduled_queue(scheduled_state,request=mode)
    with host_lock(PROCESSING_LOCK) as acquired:
        if not acquired:return dict(ok=True,mode=mode,deferred=True,quanta=0,code="processing_host_busy")
        # A killed host client may have left a daemon-owned container running.
        if command(["container","ls","-a","--filter","label=invoice.processing.operation","--format","{{.Names}}"],10):
            raise CleanupFailure("processing_prior_operation_unreconciled")
        schedule,selected=scheduled_queue(scheduled_state,start=True,now=int(time.time())) if scheduled_state else ({},mode)
        if selected is None:return dict(ok=True,mode=mode,quanta=0,states={},remaining=0,deferred=True,retry_not_before=schedule.get("not_before",0))
        result=None
        try:
            result=operate_locked(selected,image,config,AUTOMATIC_MAX_QUANTA if scheduled_state else max_quanta,until)
            return result
        finally:
            if scheduled_state:scheduled_queue(scheduled_state,complete=selected,ok=result is not None and result.get("ok") is True,
                not_before=result.get("retry_not_before",0) if result else 0)


def operate_locked(mode,image,config,max_quanta,until):
    runtime = Runtime(config, image)
    with tempfile.TemporaryDirectory(prefix="invoice-processing-", dir="/dev/shm") as working:
        os.chown(working, 10001, 10001)
        os.chmod(working, 0o700)
        selected = runtime.coordinator(["select", "--mode", mode, "--limit", "50"], working,min(time.monotonic()+180,until-40))
    keys = selected.get("message_keys")
    if not isinstance(keys, list) or len(keys) > 50 or any(not isinstance(key, str) or not KEY.fullmatch(key) for key in keys):
        raise ValueError()
    queue, counts = deque(dict.fromkeys(keys)), Counter()
    not_before=selected.get("retry_not_before",0)
    if type(not_before) is not int or not 0<=not_before<=9223372036854775807:raise ValueError()
    for _ in range(max_quanta):
        if not queue or not_before>int(time.time()) or until-time.monotonic()<540:
            break
        key = queue.popleft()
        deadline = min(time.monotonic()+500,until-40)  # Always retain a full quantum and cleanup reserve.
        with tempfile.TemporaryDirectory(prefix="invoice-processing-", dir="/dev/shm") as working:
            os.chown(working, 10001, 10001)
            os.chmod(working, 0o700)
            result = handoff(lambda args: runtime.coordinator(args, working, deadline),
                             lambda document: runtime.classifier(document, deadline), key, working)
        state = result.get("status")
        if state not in {"progress", "busy", "idle", "done", "failed", "waiting_correction", "operator_required"}:
            raise ValueError()
        counts[state] += 1
        until_retry=result.get("retry_not_before",0)
        if type(until_retry) is not int or not 0<=until_retry<=9223372036854775807:raise ValueError()
        not_before=max(not_before,until_retry)
        if not_before>int(time.time()):break
        if state == "progress":
            queue.append(key)
    return {"ok": True, "mode": mode, "quanta": sum(counts.values()), "states": dict(counts), "remaining": len(queue),"retry_not_before":not_before}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inbox", "corrections"))
    parser.add_argument("--image", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--max-quanta", type=int, default=100, choices=range(1, 101), metavar="1..100")
    parser.add_argument("--scheduled-state")
    args = parser.parse_args()
    def interrupted(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if not sys.flags.isolated or not sys.dont_write_bytecode:
            raise ValueError()
        protected(__file__)
        result = operate(args.mode, args.image, profile(args.profile), args.max_quanta,scheduled_state=args.scheduled_state)
    except (OSError, ValueError, TypeError, KeyError, CleanupFailure, subprocess.SubprocessError, KeyboardInterrupt):
        result = {"ok": False, "code": "processing_operator_failed", "uncertain": True}
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

