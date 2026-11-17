"""Fixed AP12 timer opportunities and public status; protected Root-only stdlib peer."""
from datetime import datetime,timedelta
import re
import subprocess
import tempfile
import time
from zoneinfo import ZoneInfo

BERLIN=ZoneInfo("Europe/Berlin")
START="invoice-importer.service"
TIMERS={name:"invoice-rotation-"+name+".timer" for name in ("daily","opportunity")}
SERVICES={name:"invoice-rotation-"+name+".service" for name in TIMERS}
CALENDARS=dict(daily="*-*-* 03:35:00 Europe/Berlin",opportunity="*-*-* *:*:40 Europe/Berlin")
PROPERTIES="Id,LoadState,ActiveState,SubState,UnitFileState,TimersCalendar,Triggers,NextElapseUSecRealtime,ExecStart,User,UMask,KillMode,Persistent,RandomizedDelayUSec,AccuracyUSec"
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C.UTF-8","TZ":"UTC","SYSTEMD_COLORS":"0"}
PUBLIC_FIELDS={"last_check","last_successful_daily_check_at","last_attempt","last_renewal","operation"}


def calendar(now):
    local=datetime.fromtimestamp(now,BERLIN);point=local.replace(hour=3,minute=35,second=0,microsecond=0)
    if point.timestamp()>now:return int((point-timedelta(days=1)).timestamp()),int(point.timestamp())
    return int(point.timestamp()),int((point+timedelta(days=1)).timestamp())


def parse_units(text):
    units={}
    for block in text.strip().split("\n\n"):
        row={}
        for line in block.splitlines():
            if "=" not in line:continue
            name,value=line.split("=",1)
            if name in row:raise ValueError("rotation_timer_unconfirmed")
            row[name]=value
        if row.get("Id") in {START,*TIMERS.values(),*SERVICES.values()}:
            if row["Id"] in units:raise ValueError("rotation_timer_unconfirmed")
            units[row["Id"]]=row
    return units


def systemd(until):
    remaining=min(3,until-time.monotonic())
    if remaining<=0:raise ValueError("rotation_host_deadline")
    with tempfile.TemporaryFile() as output:
        result=subprocess.run(["/usr/bin/systemctl","show","--all","--no-pager","--timestamp=unix","--property="+PROPERTIES,
            START,*TIMERS.values(),*SERVICES.values()],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.DEVNULL,env=ENV,timeout=remaining)
        if result.returncode not in (0,1) or output.tell()>32768:raise ValueError("rotation_timer_unconfirmed")
        output.seek(0);return parse_units(output.read().decode("utf-8"))


def timer_status(controller):
    result=dict(daily=False,opportunity=False,next_check_at=None)
    try:units=systemd(controller.until)
    except (OSError,ValueError,subprocess.SubprocessError):return result
    startup=units.get(START,{})
    if startup.get("LoadState")!="loaded" or startup.get("ActiveState")!="active":return result
    for name in TIMERS:
        timer=units.get(TIMERS[name],{});service=units.get(SERVICES[name],{})
        calendars=re.findall(r"OnCalendar=([^;]+);",timer.get("TimersCalendar",""))
        commands=re.findall(r"argv\[\]=([^;]+);",service.get("ExecStart",""))
        expected="/usr/bin/python3 -I -B /etc/invoice-importer/run-rotation.py "+name+" --profile "+controller.profile_path
        result[name]=(timer.get("LoadState")=="loaded" and timer.get("ActiveState")=="active" and timer.get("UnitFileState")=="enabled"
            and len(calendars)==1 and " ".join(calendars[0].split())==CALENDARS[name] and timer.get("Triggers","").split()==[SERVICES[name]]
            and timer.get("Persistent")=="yes" and timer.get("RandomizedDelayUSec") in {"0","0s"} and timer.get("AccuracyUSec")=="1s"
            and service.get("LoadState")=="loaded" and service.get("User")=="root" and service.get("UMask")=="0077"
            and service.get("KillMode")=="control-group" and len(commands)==1 and " ".join(commands[0].split())==expected)
        if name=="daily" and result[name]:
            match=re.fullmatch(r"@(\d+)(?:\.\d+)?",timer.get("NextElapseUSecRealtime",""))
            if match and int(match[1])==calendar(int(time.time()))[1]:result["next_check_at"]=int(match[1])
    return result


def publish(controller):
    controller.writer._require()
    boot=controller.model.boot_id();facts=controller.worker("overview")
    if facts.get("binding")!=controller.access.fields() or set(facts)!={"ok","binding",*PUBLIC_FIELDS}:raise ValueError("rotation_status_unconfirmed")
    timers=timer_status(controller);now=int(time.time());due,_=calendar(now)
    check=facts["last_check"]
    value=dict(schema_version=1,**controller.access.fields(),boot_id=boot,observed_at=now,
        **{name:facts[name] for name in PUBLIC_FIELDS},timers=timers,check_due_at=due,
        check_overdue=now>=due+7200 and (check is None or check["at"]<due))
    if controller.model.boot_id()!=boot:raise ValueError("rotation_status_boot_changed")
    controller.write(controller.gate_directory/"rotation-status.json",value,mode=0o440,gid=10001)
    return True


def gate_ready(controller):
    value=controller.writer.gate.read()
    return (value["mode"]=="allowed" and value["boot_id"]==controller.model.boot_id()
        and all(value.get(name)==expected for name,expected in controller.access.fields().items()) and controller.external_drain() is None)


def run(controller,mode):
    if mode not in TIMERS:raise ValueError("rotation_schedule_mode_invalid")
    try:
        with controller.writer.session():
            result=dict(ok=False,code="rotation_schedule_unconfirmed")
            try:
                controller.recover_job();status=controller.worker("status")
                if status["binding"]!=controller.access.fields():raise ValueError("rotation_binding_changed")
                operation=status["head"]["active_operation"]
                if operation and (controller.journal/(operation+".controller.json")).exists():controller.control_record(operation)
                timers=timer_status(controller)
                check=status["daily_check"];due=check is None or check["slot"]<calendar(int(time.time()))[0]
                if (mode=="daily" or timers["daily"]) and (due or status["automatic_pending"]) and gate_ready(controller):
                    with controller.lifecycle_locks():
                        if gate_ready(controller):
                            controller.api();controller.runtime.ready(controller.binding,controller.auto["public_origin"],controller.host,controller.until)
                            controller.worker("scheduled-check")
                    status=controller.worker("status")
                release=controller.writer.gate.read()
                if release["mode"]=="paused" or release["mode"]!="blocked" and controller.external_drain() is not None:
                    result=dict(ok=True,deferred=True,code="rotation_schedule_paused")
                else:
                    row=status.get("request");state=status["host"];selected="resume";proceed=True
                    if row and row["trigger_kind"]=="automatic" and (state is None or state["phase"]=="prepared"):
                        old=state["old"] if state else status["current"]
                        if old["expires_at"]-time.time()<3600:
                            if state is None:
                                result=dict(ok=False,code="rotation_automatic_window_closed");proceed=False
                            else:selected="rollback"
                    if proceed:result=controller.operate(selected,locked=True)
            except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
                result=dict(ok=False,code="rotation_schedule_unconfirmed")
            try:recorded=publish(controller)
            except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):recorded=False
            return dict(result,status_recorded=recorded)
    except ValueError as error:
        if str(error)=="graph_gate_writer_busy":return dict(ok=True,deferred=True,code="rotation_schedule_busy",status_recorded=False)
        raise
