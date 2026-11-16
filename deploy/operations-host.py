"""Bounded read-only host collector and small whitelisted run receipts."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
import uuid

START="invoice-importer.service"
SERVICES=dict(inbox="invoice-processing@inbox.service",corrections="invoice-processing@corrections.service",
    notifications="invoice-notifications.service",tls="invoice-tls.service")
TIMERS=dict(inbox="invoice-processing-inbox.timer",corrections="invoice-processing-corrections.timer",
    notifications="invoice-notifications.timer",tls="invoice-tls.timer")
CALENDARS=dict(inbox="*-*-* *:00/5:00 Europe/Berlin",corrections="*-*-* *:00/15:00 Europe/Berlin",
    notifications="*-*-* *:*:00 Europe/Berlin",tls="*-*-* *:00:00 Europe/Berlin")
PROPERTIES="Id,LoadState,ActiveState,SubState,Result,ExecMainStatus,ExecMainStartTimestamp,NextElapseUSecRealtime,TimersCalendar,Triggers"
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C.UTF-8","TZ":"UTC","SYSTEMD_COLORS":"0"}


def profile(path,host):
    value=json.loads(host.protected(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict) or set(value)!={"source_commit","deployment_id","automation_profile","result_directory","output_directory"}:raise ValueError()
    if not isinstance(value["source_commit"],str) or not re.fullmatch(r"[0-9a-f]{40}",value["source_commit"]):raise ValueError()
    if str(uuid.UUID(value["deployment_id"]))!=value["deployment_id"]:raise ValueError()
    for key in ("result_directory","output_directory"):
        host.controlled_directory(value[key])
    results=Path(value["result_directory"]);output=Path(value["output_directory"])
    if results==output or stat.S_IMODE(results.stat().st_mode)!=0o700:raise ValueError()
    if output.stat().st_gid!=10001 or stat.S_IMODE(output.stat().st_mode)!=0o750:raise ValueError()
    if any(item.name!="status.json" and not item.name.startswith(".status-") for item in output.iterdir()):raise ValueError()
    automation=host.load_peer("run-automation.py").profile(value["automation_profile"],host)
    binding=json.loads(host.protected(automation["runtime_profile"]).read_text(encoding="utf-8"))
    if str(uuid.UUID(binding["instance_id"]))!=binding["instance_id"]:raise ValueError()
    return value,automation,binding


def atomic(path,value,host,*,public=False):
    parent=host.controlled_directory(Path(path).parent)
    body=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
    if len(body)>32768:raise ValueError()
    fd,name=tempfile.mkstemp(prefix=".status-",dir=parent)
    try:
        with os.fdopen(fd,"wb") as target:
            target.write(body);target.flush()
            os.fchown(target.fileno(),0,10001 if public else 0)
            os.fchmod(target.fileno(),0o440 if public else 0o600)
            os.fsync(target.fileno())
        os.replace(name,path)
        directory=os.open(parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(name):os.unlink(name)


def record(path,mode,result,started_at,host):
    if mode not in {"start",*SERVICES}:raise ValueError()
    cfg,_,binding=profile(path,host)
    model=host.load_peer("operations-status.py")
    boot=model.boot_id()
    if boot is None:raise ValueError()
    outcome="unknown" if result.get("uncertain") is True or result.get("persisted") is False else \
        "deferred" if result.get("deferred") is True else "ok" if result.get("ok") is True else "failed"
    value=dict(schema_version=1,source_commit=cfg["source_commit"],deployment_id=cfg["deployment_id"],
        instance_id=binding["instance_id"],boot_id=boot,started_at=started_at,at=int(time.time()),result=outcome)
    atomic(Path(cfg["result_directory"])/(mode+".json"),value,host)
    return True


def systemd(until):
    remaining=min(3,until-time.monotonic())
    if remaining<=0:raise ValueError("status_deadline")
    with tempfile.TemporaryFile() as output:
        result=subprocess.run(["/usr/bin/systemctl","show","--all","--no-pager","--timestamp=unix","--property="+PROPERTIES,
            START,*TIMERS.values(),*SERVICES.values()],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.DEVNULL,
            env=ENV,timeout=remaining)
        if result.returncode not in (0,1) or output.tell()>32768:raise ValueError()
        output.seek(0);return parse_units(output.read().decode("utf-8"))


def parse_units(text):
    units={}
    for block in text.strip().split("\n\n"):
        row=dict(line.split("=",1) for line in block.splitlines() if "=" in line)
        if row.get("Id") in {START,*TIMERS.values(),*SERVICES.values()}:
            if row["Id"] in units:raise ValueError()
            units[row["Id"]]=row
    return units


def observed(call):
    try:return call()
    except (OSError,ValueError,TypeError,KeyError,RuntimeError,subprocess.SubprocessError):return None


def timestamp(value):
    match=re.fullmatch(r"@(\d+)(?:\.\d+)?",value or "")
    return int(match[1]) if match else None


def loaded(row):
    return True if row.get("LoadState")=="loaded" else False if row.get("LoadState")=="not-found" else None


def active(row):
    return True if row.get("ActiveState")=="active" else False if row.get("ActiveState") in {"inactive","failed"} else None


def running(row):
    if row.get("ActiveState") in {"activating","reloading"} or row.get("SubState")=="running":return True
    if row.get("ActiveState") in {"inactive","failed"} or row.get("SubState")=="exited":return False
    return None


def held(path,host):
    try:info=host.protected(path).stat()
    except FileNotFoundError:return False
    with open("/proc/locks",encoding="ascii") as source:text=source.read(65537)
    if len(text)>65536:raise ValueError()
    for line in text.splitlines():
        fields=line.split()
        if len(fields)>=8 and fields[1:4]==["FLOCK","ADVISORY","WRITE"]:
            major,minor,inode=fields[5].split(":")
            if (int(major,16),int(minor,16),int(inode))==(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino):return True
    return False


def last_result(cfg,binding,mode,row,host,model,now):
    start=timestamp(row.get("ExecMainStartTimestamp"))
    def receipt():
        value=json.loads(host.protected(Path(cfg["result_directory"])/(mode+".json")).read_text(encoding="utf-8"),object_pairs_hook=model.json_object)
        if (set(value)!={"schema_version","source_commit","deployment_id","instance_id","boot_id","started_at","at","result"}
                or type(value["schema_version"]) is not int or value["schema_version"]!=1 or (value["source_commit"],value["deployment_id"],value["instance_id"])!=
                (cfg["source_commit"],cfg["deployment_id"],binding["instance_id"])
                or not model.canonical_uuid(value["boot_id"]) or not model.integer(value["at"]) or not model.integer(value["started_at"])
                or not value["started_at"]<=value["at"]<=now+30 or value["result"] not in model.RESULTS):raise ValueError()
        return value
    value=observed(receipt)
    if value is not None and (start is None or value["at"]>=start):return value["result"],value["at"]
    if row.get("Result") not in {None,"","success"}:return "failed",start
    return ("none",None) if start is None and loaded(row) is not None else ("unknown",start)


def schedule(name,timer,service):
    installed=loaded(timer)
    if installed is False:return False,False
    if installed is not True or loaded(service) is not True:return None,None
    calendars=re.findall(r"OnCalendar=([^;]+);",timer.get("TimersCalendar",""))
    if len(calendars)!=1 or " ".join(calendars[0].split())!=CALENDARS[name] or timer.get("Triggers","").split()!=[SERVICES[name]]:
        return None,None
    return True,active(timer)


def collect(path,host,runtime,until):
    cfg,automation,binding=profile(path,host)
    runtime.profile(automation["runtime_profile"],host)
    model=host.load_peer("operations-status.py")
    boot=model.boot_id()
    if boot is None:raise ValueError()
    with host.host_lock("/run/invoice-importer/status.lock") as acquired:
        if not acquired:return dict(ok=True,deferred=True)
        work=until-2
        units=observed(lambda:systemd(work)) or {}
        now=int(time.time())
        startup=units.get(START,{})
        result,at=last_result(cfg,binding,"start",startup,host,model,now)
        facts={}
        def containers():
            text=host.command(["inspect","--format",runtime.CONTAINER_TEMPLATE,*[binding["containers"][key]["name"] for key in ("db","api","nginx")]],runtime.seconds(work,3))
            values=[json.loads(line) for line in text.splitlines()]
            if len(values)!=3:raise ValueError()
            return {key:runtime.validate_container(binding,key,value) for key,value in zip(("db","api","nginx"),values)}
        current=observed(containers)
        for key in ("db","api","nginx"):
            facts[key]=None if current is None else bool(current[key]["state"].get("Running") and
                (key=="nginx" or current[key]["state"].get("Health",{}).get("Status")=="healthy"))
        def portal():
            if any(item is False for item in facts.values()):return False
            if any(item is None for item in facts.values()):return None
            _,directory=runtime.current_release(binding["tls_root"],host)
            import hashlib,ssl
            fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert((directory/"cert.pem").read_text(encoding="ascii"))).hexdigest()
            runtime.peer(binding,automation["public_origin"],min(work,time.monotonic()+2),fingerprint)
            return True
        ready=observed(portal)
        def importer():
            config=host.profile(automation["processing_profile"])
            with host.CifsBinding(config) as files:files.check()
            return True
        def tls_source():
            value=runtime.tls_profile(automation["tls_profile"],host)
            with runtime.Source(value,host) as source:source.check()
            return True
        def presence(file):
            try:host.protected(file)
            except FileNotFoundError:return False
            return True
        mounts=dict(importer=observed(importer),tls_source=observed(tls_source))
        draining=observed(host.draining)
        blocked_tls=observed(lambda:presence(runtime.tls_pending(binding["tls_root"])))
        locked=observed(lambda:held(host.PROCESSING_LOCK,host))
        def queue():
            try:value=json.loads(host.protected(automation["processing_state"]).read_text(encoding="utf-8"))
            except FileNotFoundError:value=dict(due=dict(inbox=False,corrections=False),last=None,active=None,not_before=0)
            return host.queue_step(value)[0]
        queued=observed(queue)
        jobs={}
        for name in SERVICES:
            timer=units.get(TIMERS[name],{});service=units.get(SERVICES[name],{})
            configured,enabled=schedule(name,timer,service)
            outcome,last=last_result(cfg,binding,name,service,host,model,now)
            run=running(service)
            blocked=blocked_tls if name=="tls" else (queued["not_before"]>now if queued is not None else None) if name in {"inbox","corrections"} else False
            if name in {"inbox","corrections"} and locked is True:run=(queued["active"]==name) if queued and queued["active"] else None
            jobs[name]=dict(configured=configured,active=enabled,running=run,blocked=blocked,last_result=outcome,last_run_at=last,
                next_run_at=timestamp(timer.get("NextElapseUSecRealtime")))
        value=dict(schema_version=1,source_commit=cfg["source_commit"],deployment_id=cfg["deployment_id"],instance_id=binding["instance_id"],
            boot_id=boot,generated_at=int(time.time()),timezone="Europe/Berlin",draining=draining,processing_running=locked,
            startup=dict(configured=loaded(startup),active=active(startup),ready=ready,database_ready=facts["db"],nginx_ready=facts["nginx"],
                last_result=result,last_run_at=at),jobs=jobs,mounts=mounts)
        model.validate_raw(value)
        if model.boot_id()!=boot or time.monotonic()>=until:raise ValueError()
        atomic(Path(cfg["output_directory"])/"status.json",value,host,public=True)
        return dict(ok=True,published=True)
