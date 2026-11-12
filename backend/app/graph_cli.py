"""Explicit operator command. Nothing is run during API import/startup."""
import argparse
import json
import logging
from app.graph import GraphError, operator_client
from app.graph_mail import Mailbox, CUTOFF_GRAPH
from app.graph_deadline import bounded_operation
from app.graph_actions import GraphActions, FOLDERS
from app.graph_state import ActionStore
from app.database import make_engine


def execute(args):
    # HTTP diagnostics can contain resource IDs. This command emits only summaries.
    logging.disable(logging.CRITICAL)
    engine = None
    try:
        with operator_client(args.config, args.certificate) as client:
            if args.command == "probe":
                result = client.probe()
            elif args.command == "scan":
                values = Mailbox(client).scan()
                result = {"scan_complete": True, "cutoff_utc": CUTOFF_GRAPH, "messages": len(values),
                          "attachments": sum(len(a) for _, a in values)}
            else:
                engine = make_engine()
                actions = GraphActions(client, ActionStore(engine))
                if args.command == "ensure-folders":
                    folders = actions.ensure_folders()
                    result = {"folders_ready": len(folders)}
                elif args.command == "flag":
                    actions.flag(args.message_id)
                    result = {"action": "flag", "state": "done"}
                else:
                    actions.move(args.message_id, args.destination)
                    result = {"action": "move", "state": "done"}
        return {"ok": True, **result}
    except GraphError as error:
        return {"ok": False, "code": error.code, "status": error.status, "uncertain": error.uncertain}
    finally:
        if engine is not None:
            engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["probe", "scan", "ensure-folders", "flag", "move"])
    parser.add_argument("--config", default="/run/importer/graph.json")
    parser.add_argument("--certificate", default="/run/secrets/graph_credential")
    parser.add_argument("--message-id")
    parser.add_argument("--destination", choices=FOLDERS)
    args = parser.parse_args()
    if args.command in ("flag", "move") and not args.message_id:
        parser.error("This action requires one exact --message-id.")
    if args.command == "move" and not args.destination:
        parser.error("Move requires one allowed --destination.")
    writing = args.command in ("ensure-folders", "flag", "move")
    result = bounded_operation(execute, (args,), seconds=60 if args.command == "probe" else 180, uncertain=writing)
    if writing and not result.get("ok") and result.get("code") == "graph_runtime_unavailable":
        # A DB/child failure can occur after Graph applied the write. Consult the journal.
        result["uncertain"] = True
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
