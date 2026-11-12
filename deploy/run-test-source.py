"""Linux operator: private opaque-byte handoff between two isolated containers."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
import uuid


def checked_file(value):
    path = Path(value)
    info = path.lstat()
    if not path.is_absolute() or not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o027:
        raise ValueError()
    return str(path)


def invoke(arguments, environment, timeout):
    result = subprocess.run(arguments, env=environment, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout)
    if len(result.stdout) > 65536:
        raise ValueError()
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError()
    return result.returncode, value


def operate(command, case, attachment, source_image, classifier_image):
    if os.name != "posix" or os.geteuid() != 0:
        raise ValueError()
    if not all(re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in (source_image, classifier_image)):
        raise ValueError()
    environment = dict(os.environ)
    for name in ("GRAPH_CONFIG_HOST_FILE", "GRAPH_CREDENTIAL_HOST_FILE", "TEST_SOURCE_BINDING_HOST_FILE"):
        environment[name] = checked_file(environment[name])
    environment.update(TEST_SOURCE_IMAGE=source_image, CLASSIFIER_IMAGE=classifier_image)
    source_file = checked_file(environment["TEST_SOURCE_COMPOSE_HOST_FILE"])
    classifier_file = checked_file(environment["CLASSIFIER_COMPOSE_HOST_FILE"])
    pin_file = checked_file(environment["CLASSIFIER_PIN_ENV_HOST_FILE"])
    lines = [line.strip() for line in Path(pin_file).read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if lines != ["CLASSIFIER_IMAGE=" + classifier_image]:
        raise ValueError()
    project = "invoice-test-" + uuid.uuid4().hex
    source_name, classifier_name = project + "-source", project + "-classifier"
    source_compose = ["docker", "compose", "-p", project, "-f", source_file, "--profile", "test-source-operator"]
    classifier_compose = ["docker", "compose", "-p", project, "--env-file", pin_file, "-f", classifier_file, "--profile", "classifier-operator"]
    with tempfile.TemporaryDirectory(prefix="invoice-test-", dir="/dev/shm") as working:
        os.chown(working, 10001, 10001)
        os.chmod(working, 0o700)
        environment["TEST_SOURCE_OUTPUT_HOST_DIR"] = working
        try:
            selection = [] if command == "scan" else ["--case", str(case), "--attachment", str(attachment)]
            status, result = invoke(source_compose + ["run", "--no-deps", "--rm", "-T", "--name", source_name,
                                                     "test-source", command, *selection], environment, 200)
            if status != 0 or not result.get("ok") or command == "scan":
                return result
            document = Path(working) / "document"
            info = document.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 10001 or info.st_mode & 0o377
                    or not 0 <= info.st_size <= 25 * 1024 * 1024):
                raise ValueError()
            environment["CLASSIFIER_INPUT_HOST_FILE"] = str(document)
            status, finding = invoke(classifier_compose + ["run", "--no-deps", "--rm", "-T", "--name", classifier_name,
                                                          "classifier"], environment, 150)
            if finding.get("status") not in ("recognized", "ignored", "unknown", "failed"):
                raise ValueError()
            return {"ok": status == 0, "source": "test", "case": case, "attachment": attachment, **finding}
        finally:
            # Only the two names and network of this random, private operation.
            network_cleaned = False
            for cleanup in (["docker", "rm", "-f", source_name, classifier_name],
                            source_compose + ["down", "--remove-orphans"]):
                try:
                    cleaned = subprocess.run(cleanup, env=environment, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, timeout=20)
                    if "down" in cleanup:
                        network_cleaned = cleaned.returncode == 0
                except (OSError, subprocess.SubprocessError):
                    pass
            if not network_cleaned:
                raise ValueError("operator_cleanup_failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("scan", "fetch"))
    parser.add_argument("--case", type=int)
    parser.add_argument("--attachment", type=int)
    parser.add_argument("--source-image", required=True)
    parser.add_argument("--classifier-image", required=True)
    args = parser.parse_args()
    if args.command == "fetch" and (args.case is None or args.attachment is None
                                    or not 1 <= args.case <= 50 or not 1 <= args.attachment <= 100):
        parser.error("Fetch requires a bounded explicit case/attachment selection.")
    def interrupted(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        result = operate(args.command, args.case, args.attachment, args.source_image, args.classifier_image)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, KeyboardInterrupt):
        result = {"ok": False, "source": "test", "code": "test_operator_failed"}
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
