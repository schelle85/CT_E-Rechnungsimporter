"""Explicit operator command. Nothing is run during API import/startup."""
import argparse
import json
import logging
from app.graph import GraphError, operator_client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["probe"])
    parser.add_argument("--config", default="/run/importer/graph.json")
    parser.add_argument("--certificate", default="/run/secrets/graph_credential")
    args = parser.parse_args()
    # HTTP diagnostics can contain resource IDs. This command emits only summaries.
    logging.disable(logging.CRITICAL)
    try:
        with operator_client(args.config, args.certificate) as client:
            result = client.probe()
        print(json.dumps({"ok": True, **result}))
        return 0
    except GraphError as error:
        print(json.dumps({"ok": False, "code": error.code, "status": error.status}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
