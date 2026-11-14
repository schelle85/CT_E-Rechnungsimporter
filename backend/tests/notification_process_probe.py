"""Only in the test image: synthetic EOF/kill/DB-boundary probe, no network."""
import json
import os
from pathlib import Path
import sys
import threading
import time

def main():
    job=json.loads(sys.stdin.buffer.read(16385))
    mode=job.get("mode","where")
    if job.get("ready_file"):Path(job["ready_file"]).write_text("started",encoding="ascii")
    if mode=="where":
        print(json.dumps(dict(ok=True,main_thread=threading.current_thread() is threading.main_thread(),
            forbidden_env=[name for name in ("CONFIG_KEY_FILE","LDAP_BIND_PASSWORD_FILE","LDAP_BOOTSTRAP_FILE",
                "TLS_PRIVATE_KEY_FILE","HTTPS_PROXY","SYNTHETIC_FORBIDDEN") if name in os.environ],deadline=job["deadline"])))
        return
    if mode=="sleep":time.sleep(30);return
    if mode=="eof":return
    if mode=="oversize":sys.stdout.write("x"*40000);return
    import sqlalchemy as sa
    from cryptography.fernet import Fernet
    from app.notification_model import OperationBudget
    from app.notification_state import NotificationStore
    engine=sa.create_engine("sqlite:///"+job["database"],poolclass=sa.pool.NullPool,connect_args={"timeout":30})
    store=NotificationStore(engine,Fernet(Path(job["key_file"]).read_bytes()),job["instance"],clock=lambda:job["now"])
    if job["command"]=="readback":
        print(json.dumps(dict(ok=True,receipts=[store.recover(key,stopped_owner=job["owner"]) for key in job["keys"]])))
        engine.dispose();return
    key=job["keys"][0]
    ticket=store.claim(key,job["scope"],owner=job["owner"])
    if ticket is None:raise AssertionError("synthetic claim failed")
    if mode=="unreserved-eof":os._exit(0)
    budget=OperationBudget(clock=time.monotonic,seconds=max(.001,min(60,job["deadline"]-time.monotonic())))
    budget.deadline=job["deadline"]
    assert store.reserve(ticket,budget=budget)
    if mode=="reserve-eof":os._exit(0)
    assert store.begin_post(ticket,budget=budget) is not None  # Permission only; no actual sender exists here.
    if mode=="accept-eof":store.finish(ticket,"accepted",http_status=202)
    if mode=="post-sleep":time.sleep(30)
    os._exit(0)

if __name__=="__main__":main()
