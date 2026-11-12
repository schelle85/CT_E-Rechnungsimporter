"""Manual, credential-free classifier with a process-group wallclock boundary."""
import argparse
import hashlib
import json
import logging
import multiprocessing
import os
from pathlib import Path
import resource
import signal
import stat
import time

MAX_INPUT = 25 * 1024 * 1024
WALLCLOCK = 120


def child(send, data):
    os.setsid()
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    logging.disable(logging.CRITICAL)
    with open(os.devnull, "wb") as quiet:
        os.dup2(quiet.fileno(), 1)
        os.dup2(quiet.fileno(), 2)
        try:
            from classifier.core import classify
            result = classify(data)
        except MemoryError:
            result = {"status": "failed", "category": None, "format": None, "reason": "memory_limit"}
        except BaseException:
            result = {"status": "failed", "category": None, "format": None, "reason": "parser_failure"}
        try:
            send.send_bytes(json.dumps(result).encode())
        finally:
            send.close()


def bounded_classify(data, seconds=WALLCLOCK):
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=child, args=(send, data))
    common = {"original_sha256": hashlib.sha256(data).hexdigest(), "rule_version": "ap03-2"}
    started = time.monotonic()
    try:
        process.start()
        send.close()
        if receive.poll(max(0, seconds - (time.monotonic() - started))):
            try:
                result = json.loads(receive.recv_bytes(4096))
                if result.get("status") not in ("recognized", "ignored", "failed"):
                    raise ValueError()
                return {**result, **common}
            except (EOFError, OSError, ValueError):
                return {"status": "failed", "category": None, "format": None, "reason": "parser_process_failed", **common}
        return {"status": "failed", "category": None, "format": None, "reason": "document_timeout", **common}
    finally:
        receive.close()
        send.close()
        if process.pid:
            # Do not reap the leader before signalling its private group: retaining
            # the PID prevents accidental signalling after PID/group-number reuse.
            for termination_signal in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(process.pid, termination_signal)
                except ProcessLookupError:
                    try:
                        os.kill(process.pid, termination_signal)
                    except ProcessLookupError:
                        pass
                if termination_signal == signal.SIGTERM:
                    time.sleep(0.03)
            process.join(1)
            process.close()


def read_input(path):
    source = Path(path)
    if (not source.is_absolute() or not source.is_relative_to("/input") or ".." in source.parts
            or not source.resolve(strict=True).is_relative_to("/input")):
        raise ValueError()
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT:
            raise ValueError()
        data = stream.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise ValueError()
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    args = parser.parse_args()
    try:
        result = bounded_classify(read_input(args.input))
    except (OSError, ValueError, RuntimeError):
        result = {"status": "failed", "category": None, "format": None, "reason": "input_unavailable"}
    print(json.dumps(result))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
