"""Internal main-thread worker. Input/output bounded, errors neutral, no retry."""
import json
import logging
import sys

def main():
    logging.disable(logging.CRITICAL)
    try:
        raw = sys.stdin.buffer.read(16385)
        if len(raw) > 16384:raise ValueError()
        job = json.loads(raw)
        if not isinstance(job,dict):raise ValueError()
        from app.notification_runtime import run_job
        value = run_job(job)
    except Exception as error:
        from app.notification_model import NotificationError
        from app.graph import GraphError
        value = dict(ok=False,persisted=False,
            code=error.code if isinstance(error,(NotificationError,GraphError)) else "notification_runtime_unavailable")
    sys.stdout.write(json.dumps(value,separators=(",",":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
