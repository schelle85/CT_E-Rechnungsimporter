"""Explicit operator commands. No AD impersonation, import tick or timer."""
import argparse
import asyncio
import json
import time
from app.notification_model import NotificationError, OperationBudget, checked_key, test_request
from app.graph import GraphError
from app.notification_process import execute_notification

def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("configuration","configure-init","request-test","status",
        "preview","observe","plan","send","dispatch","automatic"))
    parser.add_argument("--config",default="/run/importer/notification-init.json")
    parser.add_argument("--request-id")
    parser.add_argument("--expected-version",type=int)
    parser.add_argument("--slot-key")
    parser.add_argument("--probe",action="store_true")
    parser.add_argument("--limit",type=int,default=1)
    args = parser.parse_args(argv)
    job = dict(command=args.command)
    try:
        if args.command in {"send","preview"} or args.command == "status" and args.slot_key:
            job["slot_key"] = checked_key(args.slot_key)
        elif args.command in {"request-test","status"}:
            job.update(test_request(args.request_id,args.expected_version))
        if args.command == "dispatch":
            if not 1 <= args.limit <= 5:raise NotificationError("notification_limit_invalid",422)
            job["limit"] = args.limit
        if args.command == "configure-init":job["config"] = args.config
        if args.command == "observe":job["probe"] = args.probe
    except NotificationError as error:
        parser.error(error.code)
    return job

def main(argv=None):
    budget = OperationBudget(clock=time.monotonic)  # Includes argument/preflight/spawn/cleanup/readback time.
    try:
        value = asyncio.run(execute_notification(arguments(argv),budget=budget))
    except (NotificationError,GraphError,OSError,ValueError) as error:
        value = dict(ok=False,persisted=False,code=error.code if isinstance(error,(NotificationError,GraphError)) else "notification_runtime_unavailable")
    print(json.dumps(value))
    return 0 if value.get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())
