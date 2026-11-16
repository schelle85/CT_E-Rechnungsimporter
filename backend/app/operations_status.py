"""Strict public operations projection. Stdlib only; also installed on the host."""
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

JOBS=("inbox","corrections","notifications","tls")
RESULTS={"ok","deferred","failed","unknown","none"}
STATES={"active","paused","degraded","unknown"}
STATUS_FILE="/run/importer/operations/status.json"
BOOT_FILE="/proc/sys/kernel/random/boot_id"
MAX_BYTES=32768
ROOT_FIELDS={"schema_version","source_commit","deployment_id","instance_id","boot_id","generated_at","timezone","startup","jobs","mounts","draining","processing_running"}
START_FIELDS={"configured","active","ready","database_ready","nginx_ready","last_result","last_run_at"}
JOB_FIELDS={"configured","active","running","blocked","last_result","last_run_at","next_run_at"}


def canonical_uuid(value):
    try:return isinstance(value,str) and len(value)==36 and str(uuid.UUID(value))==value
    except (ValueError,AttributeError):return False


def json_object(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError("duplicate_status_field")
        value[key]=item
    return value


def integer(value):return type(value) is int and 0<=value<=9007199254740991
def flag(value):return value is None or type(value) is bool
def instant(value):return value is None or integer(value) and value<=8640000000000


def boot_id():
    try:
        value=Path(BOOT_FILE).read_text(encoding="ascii").strip()
        return value if canonical_uuid(value) else None
    except (OSError,ValueError):return None


def empty_job():
    return dict(configured=None,active=None,running=None,blocked=None,last_result="unknown",last_run_at=None,next_run_at=None)


def unknown(now,reason):
    return dict(schema_version=1,state="unknown",reason=reason,checked_at=now,generated_at=None,expires_at=None,
        source_commit=None,deployment_id=None,instance_id=None,boot_id=None,timezone="Europe/Berlin",
        startup=dict(configured=None,active=None,ready=None,database_ready=None,nginx_ready=None,last_result="unknown",last_run_at=None),
        jobs={name:dict(empty_job(),state="unknown") for name in JOBS},mounts=dict(importer=None,tls_source=None),draining=None,processing_running=None,
        automatic_schedule_active=None,automatic_schedule_state="unknown")


def validate_raw(value):
    if (not isinstance(value,dict) or set(value)!=ROOT_FIELDS or type(value["schema_version"]) is not int or value["schema_version"]!=1
            or not isinstance(value["source_commit"],str) or not re.fullmatch(r"[0-9a-f]{40}",value["source_commit"])
            or any(not canonical_uuid(value[name]) for name in ("deployment_id","instance_id","boot_id"))
            or not integer(value["generated_at"]) or value["timezone"]!="Europe/Berlin" or not flag(value["draining"]) or not flag(value["processing_running"])):raise ValueError()
    startup=value["startup"]
    if (not isinstance(startup,dict) or set(startup)!=START_FIELDS
            or any(not flag(startup[key]) for key in ("configured","active","ready","database_ready","nginx_ready"))
            or startup["last_result"] not in RESULTS or not instant(startup["last_run_at"])):raise ValueError()
    if not isinstance(value["jobs"],dict) or set(value["jobs"])!=set(JOBS):raise ValueError()
    for row in value["jobs"].values():
        if (not isinstance(row,dict) or set(row)!=JOB_FIELDS
                or any(not flag(row[key]) for key in ("configured","active","running","blocked"))
                or row["last_result"] not in RESULTS or not instant(row["last_run_at"]) or not instant(row["next_run_at"])):raise ValueError()
        if row["last_run_at"] is not None and row["last_run_at"]>value["generated_at"]+30:raise ValueError()
        if row["configured"] is not True and row["active"] is True:raise ValueError()
    if startup["last_run_at"] is not None and startup["last_run_at"]>value["generated_at"]+30:raise ValueError()
    if startup["configured"] is not True and startup["active"] is True:raise ValueError()
    mounts=value["mounts"]
    if not isinstance(mounts,dict) or set(mounts)!={"importer","tls_source"} or any(not flag(item) for item in mounts.values()):raise ValueError()
    return value


def project(value,*,now,source_commit,deployment_id,instance_id,current_boot):
    try:
        if (not isinstance(source_commit,str) or not re.fullmatch(r"[0-9a-f]{40}",source_commit)
                or not canonical_uuid(deployment_id) or not canonical_uuid(instance_id)):return unknown(now,"unbound")
        validate_raw(value)
    except (ValueError,TypeError,KeyError):return unknown(now,"invalid")
    if (value["source_commit"],value["deployment_id"],value["instance_id"])!=(source_commit,deployment_id,instance_id):return unknown(now,"binding")
    if current_boot is None or value["boot_id"]!=current_boot:return unknown(now,"boot")
    if value["generated_at"]>now+30:return unknown(now,"future")
    if value["generated_at"]<now-180:return unknown(now,"stale")
    jobs={}
    for name,row in value["jobs"].items():
        state="unknown"
        if row["active"] is False:state="paused"
        elif row["active"] is True:
            required=[value["startup"]["configured"],value["startup"]["active"],value["draining"] is False,row["blocked"] is False]
            if name in {"inbox","corrections"}:required += [value["startup"]["ready"],value["mounts"]["importer"]]
            elif name=="notifications":required += [value["startup"]["database_ready"]]
            else:required += [value["startup"]["nginx_ready"],value["mounts"]["tls_source"]]
            state="active" if all(item is True for item in required) and row["last_result"] not in {"failed","unknown"} else "degraded"
        jobs[name]=dict(row,state=state)
    states={row["state"] for row in jobs.values()}
    overall="unknown" if "unknown" in states else "paused" if states=={"paused"} else "active" if states=={"active"} else "degraded"
    return dict(value,jobs=jobs,state=overall,reason=None,checked_at=now,expires_at=value["generated_at"]+180,
        automatic_schedule_active=jobs["notifications"]["active"],automatic_schedule_state=jobs["notifications"]["state"])


def read_status(instance_id,*,now=None):
    now=int(time.time()) if now is None else int(now)
    try:
        fd=os.open(STATUS_FILE,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,"rb") as source:
            info=os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_gid!=10001 or stat.S_IMODE(info.st_mode)!=0o440
                    or info.st_nlink!=1 or not 0<info.st_size<=MAX_BYTES):return unknown(now,"invalid")
            raw=source.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:return unknown(now,"invalid")
        value=json.loads(raw,object_pairs_hook=json_object)
    except FileNotFoundError:return unknown(now,"missing")
    except (OSError,ValueError,TypeError,AttributeError):return unknown(now,"unreadable")
    return project(value,now=now,source_commit=os.environ.get("OPERATIONS_SOURCE_COMMIT"),
        deployment_id=os.environ.get("OPERATIONS_DEPLOYMENT_ID"),instance_id=instance_id,current_boot=boot_id())
