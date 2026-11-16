"""Shared CLI/ASGI absolute budget; one child, bounded reap, durable final readback."""
import asyncio
import json
import os
import sys
import time
from uuid import uuid4
from app.notification_model import NotificationError, canonical, checked_key

ENVIRONMENT = {"PATH","SystemRoot","SYSTEMROOT","LANG","TZ","PYTHONPATH",
    "DB_HOST","DB_NAME","DB_USER","DB_PASSWORD_FILE","NOTIFICATION_KEY_FILE",
    "GRAPH_CONFIG_FILE","GRAPH_CREDENTIAL_FILE","PUBLIC_ORIGIN"}

def worker_environment():
    return {**{key:value for key,value in os.environ.items() if key in ENVIRONMENT},
        "PYTHONDONTWRITEBYTECODE":"1","PYTHONUNBUFFERED":"1"}

async def _reap(process,seconds):
    if process.returncode is not None:
        await process.wait()
        return True
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(),seconds/2)
        return True
    except TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(),seconds/2)
            return True
        except TimeoutError:
            return False

async def invoke(job,*,deadline,worker="app.notification_worker",cleanup_seconds=2):
    """The worker module override is a test seam, never a CLI/HTTP input."""
    process = None
    spawn = None
    stopped = True
    result = None
    try:
        work_deadline = deadline-cleanup_seconds
        remaining = work_deadline-time.monotonic()
        if remaining <= 0:
            return None,True
        body = canonical(dict(job,deadline=work_deadline)).encode("ascii")
        if len(body) > 16384:
            raise NotificationError("notification_job_invalid",422)
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(sys.executable,"-B","-m",worker,
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,
            env=worker_environment()))
        process = await asyncio.wait_for(asyncio.shield(spawn),remaining)
        async def collect():
            process.stdin.write(body)
            await process.stdin.drain()
            process.stdin.close()
            output = bytearray()
            while True:
                chunk = await process.stdout.read(min(4096,32769-len(output)))
                if not chunk:break
                output.extend(chunk)
                if len(output) > 32768:
                    raise ValueError()
            await process.wait()
            value = json.loads(output)
            if process.returncode != 0 or not isinstance(value,dict):
                raise ValueError()
            return value
        result = await asyncio.wait_for(collect(),max(0,work_deadline-time.monotonic()))
    except (TimeoutError,OSError,ValueError,EOFError,asyncio.CancelledError):
        pass
    finally:
        if process is not None:
            stopped = await _reap(process,cleanup_seconds)
        elif spawn is not None:
            # Cancellation of OS spawn cannot grant a later child fresh time/POST permission.
            # If its eventual process handle is unavailable, never claim a reconciled outcome.
            stopped = False
            def kill_late(task):
                if not task.cancelled():
                    try:
                        late = task.result()
                        if late.returncode is None:late.kill()
                    except Exception:
                        pass
            spawn.add_done_callback(kill_late)
    return result,stopped

async def execute_notification(job,*,budget,runner=invoke):
    """Caller creates the budget before preflight; this function never resets it."""
    command = job["command"]
    if command == "automatic":
        # One original CLI budget covers planning, selection, send and readback.
        if set(job) != {"command"}:raise NotificationError("notification_job_invalid",422)
        if budget.child_seconds() <= 0:return dict(ok=False,persisted=False,code="notification_deadline")
        planned,stopped=await runner(dict(command="plan"),deadline=time.monotonic()+budget.child_seconds())
        if not stopped or not planned or planned.get("ok") is not True:
            return dict(ok=False,persisted=False,code="notification_status_unavailable")
        return await execute_notification(dict(command="dispatch",limit=1),budget=budget,runner=runner)
    keys = []
    owner = uuid4().hex
    if command == "dispatch":
        limit = job.get("limit",1)
        if type(limit) is not int or not 1 <= limit <= 5:
            raise NotificationError("notification_limit_invalid",422)
        if budget.child_seconds() <= 0:
            return dict(ok=False,persisted=False,code="notification_deadline")
        selected,stopped = await runner(dict(command="pending",limit=limit),
            deadline=time.monotonic()+min(10,budget.child_seconds()))
        if not stopped or not selected or not selected.get("ok"):
            return dict(ok=False,persisted=False,code="notification_status_unavailable")
        keys = selected["keys"]
        if not isinstance(keys,list) or len(keys)>limit or len(set(keys))!=len(keys):
            raise NotificationError("notification_limit_invalid",422)
        keys=[checked_key(key) for key in keys]
    elif command == "send":
        keys = [checked_key(job["slot_key"])]
    if command in {"send","dispatch"}:
        if not keys:
            return dict(ok=True,persisted=True,receipts=[])
        if budget.child_seconds() <= 0:
            return dict(ok=False,persisted=False,code="notification_deadline",keys=keys)
        _,stopped = await runner(dict(command="send-automatic" if command=="dispatch" else "send",keys=keys,owner=owner),
            deadline=time.monotonic()+budget.child_seconds())
        if not stopped or budget.remaining() <= 3:
            return dict(ok=False,persisted=False,code="notification_status_unavailable",keys=keys)
        value,stopped = await runner(dict(command="readback",keys=keys,owner=owner),
            deadline=time.monotonic()+min(5,max(0,budget.remaining()-3)))
        if not stopped or not value or not value.get("ok"):
            return dict(ok=False,persisted=False,code="notification_status_unavailable",keys=keys)
        return dict(value,ok=all(row["state"] == "accepted" for row in value["receipts"]),persisted=True)
    if budget.child_seconds() <= 0:
        return dict(ok=False,persisted=False,code="notification_deadline")
    value,stopped = await runner(job,deadline=time.monotonic()+budget.child_seconds())
    if command == "request-test" and stopped and budget.remaining() > 3:
        # Exact original request lookup, never another request/create/send operation.
        checked,_ = await runner(dict(command="status",request_id=job["request_id"],expected_version=job["expected_version"]),
            deadline=time.monotonic()+min(5,max(0,budget.remaining()-3)))
        if checked and checked.get("ok") and checked.get("receipt") is not None:
            return checked
        if value and not value.get("ok"):
            return value
        return dict(ok=False,persisted=False,code="notification_status_unavailable",request_id=job["request_id"])
    return value or dict(ok=False,persisted=False,code="notification_status_unavailable")
