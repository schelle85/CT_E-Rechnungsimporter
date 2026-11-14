"""Manual bounded coordinator. No migration, scheduler or approval-creation route."""
import argparse
import json
import logging
import os
import re
import stat
from sqlalchemy.exc import SQLAlchemyError
from app.database import make_engine
from app.graph import GraphError, operator_client, protected_bytes
from app.graph_actions import GraphActions
from app.graph_deadline import bounded_operation
from app.graph_state import ActionStore
from app.processing import GraphProcessing, ProcessingService
from app.processing_plan import ProcessingError
from app.processing_state import ProcessingStore
from app.processing_decisions import DecisionStore
from app.storage_files import CifsFiles
from app.storage_plan import StorageError
from app.storage_state import StorageStore


def configuration(path):
    try:
        value = json.loads(protected_bytes(path))
        if (not isinstance(value, dict) or set(value) != {"scope", "storage_root", "expected_source", "staging_name", "staging_excluded"}
                or any(not isinstance(value[name], str) or not value[name] or len(value[name]) > 1024
                       for name in ("scope", "storage_root", "expected_source", "staging_name"))
                or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", value["scope"])
                or value["storage_root"] != "/importer" or value["staging_excluded"] is not True):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ProcessingError("processing_configuration_invalid") from None


def finding_file(path):
    if path != "/exchange/finding.json":
        raise ProcessingError("processing_finding_invalid")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            raise ProcessingError("processing_finding_invalid")
        return json.loads(source.read(4097))


def select(service, mode, limit):
    if mode == "inbox":
        service.scan()
    selected = service.store.due(mode, limit=limit)
    if mode == "corrections":
        for key in selected:
            DecisionStore(service.store).consume_retry(key)
            row = service.store.get_message(key)
            if row["completed_revision"] == row["revision"]:
                service.store.start_corrections(key)
    return {"ok": True, "mode": mode, "message_keys": selected}


def execute(args):
    logging.disable(logging.CRITICAL)
    engine = None
    try:
        config = configuration(args.config)
        engine = make_engine()
        with CifsFiles(config["storage_root"], config["expected_source"], config["staging_name"],
                       staging_excluded=config["staging_excluded"]) as files:
            with operator_client(args.graph_config, args.certificate) as client:
                service = ProcessingService(ProcessingStore(engine),
                    GraphProcessing(client, GraphActions(client, ActionStore(engine))),
                    StorageStore(engine, destination_key=files.destination_key), files, config["scope"])
                if args.command == "select":
                    return select(service, args.mode, args.limit)
                finding = finding_file(args.finding) if args.finding else None
                result = service.advance(args.message_key, "/exchange", owner=args.owner, revision=args.revision,
                                         attachment_key=args.attachment_key, finding=finding)
                return {"ok": True, **result.result()}
    except (GraphError, ProcessingError, StorageError) as error:
        return {"ok": False, "code": error.code, "uncertain": True}
    except (OSError, ValueError, TypeError, SQLAlchemyError):
        return {"ok": False, "code": "processing_runtime_unavailable", "uncertain": True}
    finally:
        if engine is not None:
            engine.dispose()


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("select", "advance"))
    parser.add_argument("--config", default="/run/importer/processing.json")
    parser.add_argument("--graph-config", default="/run/importer/graph.json")
    parser.add_argument("--certificate", default="/run/secrets/graph_credential")
    parser.add_argument("--mode", choices=("inbox", "corrections"), default="inbox")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--message-key")
    parser.add_argument("--owner")
    parser.add_argument("--revision", type=int)
    parser.add_argument("--attachment-key")
    parser.add_argument("--finding")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error("Limit must be 1..100.")
    if args.command == "advance" and not re.fullmatch(r"[0-9a-f]{64}", args.message_key or ""):
        parser.error("Advance requires a stored message key.")
    resume = (args.owner, args.revision, args.attachment_key, args.finding)
    if any(value is not None for value in resume) and (
            args.command != "advance" or not re.fullmatch(r"[0-9a-f]{32}", args.owner or "")
            or type(args.revision) is not int or args.revision < 0
            or not re.fullmatch(r"[0-9a-f]{64}", args.attachment_key or "")
            or args.finding != "/exchange/finding.json"):
        parser.error("Resume requires the complete bounded finding token.")
    return args


def main():
    args = arguments()
    result = bounded_operation(execute, (args,), seconds=180, uncertain=True)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

