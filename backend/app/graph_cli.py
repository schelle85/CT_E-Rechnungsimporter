"""Explicit operator command. Nothing is run during API import/startup."""
import argparse
import json
import logging
from app.graph import GraphError, operator_client
from app.graph_mail import Mailbox, CUTOFF_GRAPH
from app.graph_deadline import bounded_operation


def execute(args):
    # HTTP diagnostics can contain resource IDs. This command emits only summaries.
    logging.disable(logging.CRITICAL)
    try:
        with operator_client(args.config, args.certificate) as client:
            if args.command == "probe":
                result = client.probe()
            else:
                values = Mailbox(client).scan()
                result = {"scan_complete": True, "cutoff_utc": CUTOFF_GRAPH, "messages": len(values),
                          "attachments": sum(len(a) for _, a in values)}
        return {"ok": True, **result}
    except GraphError as error:
        return {"ok": False, "code": error.code, "status": error.status, "uncertain": error.uncertain}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["probe", "scan"])
    parser.add_argument("--config", default="/run/importer/graph.json")
    parser.add_argument("--certificate", default="/run/secrets/graph_credential")
    args = parser.parse_args()
    result = bounded_operation(execute, (args,), seconds=60 if args.command == "probe" else 180)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
