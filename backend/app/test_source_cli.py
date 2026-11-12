"""Separate manual test source. Fixed protected operator paths, no Graph writes."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile

from app.graph import GraphError, operator_client
from app.graph_deadline import bounded_operation
from app.test_source import ReadOnlyGraphClient, TestBinding, TestSource, download


def execute(command, message_id, attachment_id, directory, case=None, attachment=None):
    logging.disable(logging.CRITICAL)
    try:
        with operator_client("/run/importer/graph.json", "/run/secrets/graph_credential") as base:
            binding = TestBinding.load("/run/importer/test-source.json", base.config.mailbox)
            client = ReadOnlyGraphClient(base.config, base.credential, base.http, clock=base.clock, sleep=base.sleep)
            source = TestSource(client, binding)
            if command == "scan" or case is not None:
                messages = sorted(source.messages(), key=lambda item: (item.received_at, item.id))
                if command == "scan":
                    cases, count = [], 0
                    for number, message in enumerate(messages, 1):
                        values = sorted(source.attachments(message.id), key=lambda item: item.id)
                        count += len(values)
                        if count > 200:
                            raise GraphError("graph_collection_limit")
                        cases.append({"case": number, "attachments": [
                            {"attachment": index, "kind": value.kind, "inline": value.inline, "bytes": value.size}
                            for index, value in enumerate(values, 1)]})
                    return {"ok": True, "source": "test", "messages": len(messages), "cases": cases}
                if not 1 <= case <= len(messages):
                    raise GraphError("graph_test_selection_invalid")
                message_id = messages[case - 1].id
                values = sorted(source.attachments(message_id), key=lambda item: item.id)
                if not 1 <= attachment <= len(values):
                    raise GraphError("graph_test_selection_invalid")
                attachment_id = values[attachment - 1].id
            result = download(source, message_id, attachment_id, directory)
            return {"ok": True, "source": "test", **result}
    except GraphError as error:
        return {"ok": False, "source": "test", "code": error.code}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("scan", "fetch"))
    parser.add_argument("--message-id")
    parser.add_argument("--attachment-id")
    parser.add_argument("--case", type=int)
    parser.add_argument("--attachment", type=int)
    args = parser.parse_args()
    exact = bool(args.message_id and args.attachment_id and args.case is None and args.attachment is None)
    ordinal = bool(args.case is not None and args.attachment is not None and not args.message_id and not args.attachment_id
                   and 1 <= args.case <= 50 and 1 <= args.attachment <= 100)
    if args.command == "fetch" and not (exact or ordinal):
        parser.error("Fetch requires one exact ID pair or one bounded case/attachment pair.")
    try:
        with tempfile.TemporaryDirectory(prefix="fetch-", dir="/output") as working:
            result = bounded_operation(execute, (args.command, args.message_id, args.attachment_id, working, args.case, args.attachment), seconds=180)
            if args.command == "fetch" and result.get("ok"):
                path = Path(working) / "document"
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, "rb") as stream:
                    raw = stream.read(TestSource.MAX_DOWNLOAD + 1)
                if (len(raw) != result.get("bytes") or len(raw) > TestSource.MAX_DOWNLOAD
                        or hashlib.sha256(raw).hexdigest() != result.get("sha256")):
                    raise ValueError()
                # Link cannot overwrite an existing destination, unlike rename.
                os.link(path, "/output/document", follow_symlinks=False)
            result.pop("sha256", None)
    except (OSError, ValueError):
        result = {"ok": False, "source": "test", "code": "graph_test_output_unavailable"}
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
