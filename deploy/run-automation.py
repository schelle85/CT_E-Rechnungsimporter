"""Fixed AP08 host entry points. Protected python3 -I -B; installs no jobs."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import uuid
from urllib.parse import urlsplit


def load_processing():
    # This peer is operator-installed with the same root-only protection.
    path=Path(__file__).with_name("run-processing.py")
    for target in (Path(__file__),path):
        for part in [*reversed(target.parents),target]:
            info=part.lstat()
            if info.st_uid!=0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):raise ValueError()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027 or info.st_size>65536:raise ValueError()
    spec=importlib.util.spec_from_file_location("invoice_processing_host",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.protected(__file__);module.protected(path)
    return module


def profile(path,host):
    value=json.loads(host.protected(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict) or set(value)!={"processing_image","processing_profile","processing_state","notification_image","notification_key","public_origin"}:
        raise ValueError()
    for name in ("processing_image","notification_image"):
        if not isinstance(value[name],str) or not re.fullmatch(r"sha256:[0-9a-f]{64}",value[name]):raise ValueError()
    origin=value["public_origin"]
    if not isinstance(origin,str) or any(ord(char)<33 for char in origin):raise ValueError()
    parsed=urlsplit(origin)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:raise ValueError()
    for name in ("processing_profile","notification_key"):
        value[name]=str(host.protected(value[name]))
        if "," in value[name] or any(ord(char)<32 for char in value[name]):raise ValueError()
    state=Path(value["processing_state"])
    host.controlled_directory(state.parent)
    if not state.is_absolute() or state.name in {".",".."}:raise ValueError()
    return value


def notify(value,host,config):
    # Original CLI budget remains 80 seconds, including plan/send/readback.
    # The encompassing host budget also bounds preflight and exact cleanup.
    until=time.monotonic()+95
    with host.host_lock("/run/invoice-importer/notification.lock") as acquired:
        if not acquired:return dict(ok=True,deferred=True,code="notification_host_busy")
        def seconds(maximum,*,cleanup=False):
            remaining=min(maximum,until-time.monotonic()-(0 if cleanup else 10))
            if remaining<=0:raise ValueError()
            return remaining
        if host.command(["container","ls","-a","--filter","label=invoice.notification.operation","--format","{{.Names}}"],seconds(3)):
            raise host.CleanupFailure("notification_prior_operation_unreconciled")
        image=value["notification_image"]
        if host.command(["image","inspect","--format","{{.Id}}",image],seconds(5))!=image:raise ValueError()
        name="invoice-notification-"+uuid.uuid4().hex
        args=["create","--init","--name",name,"--label","invoice.notification.operation="+name,
            "--network",config["networks"][0],"--user","10001:10001","--read-only",
            "--cap-drop","ALL","--security-opt","no-new-privileges:true","--memory","512m",
            "--memory-swap","512m","--cpus","1","--pids-limit","96","--workdir","/app",
            "--tmpfs","/tmp:rw,noexec,nosuid,size=64m"]
        for key,item in {"DB_HOST":config["db_host"],"DB_NAME":config["db_name"],"DB_USER":config["db_user"],
                "DB_PASSWORD_FILE":"/run/secrets/db_password","NOTIFICATION_KEY_FILE":"/run/secrets/notification_key",
                "GRAPH_CONFIG_FILE":"/run/importer/graph.json","GRAPH_CREDENTIAL_FILE":"/run/secrets/graph_credential",
                "PUBLIC_ORIGIN":value["public_origin"]}.items():
            args += ["--env",key+"="+item]
        for source,target in ((config["graph_config"],"/run/importer/graph.json"),
                (config["graph_credential"],"/run/secrets/graph_credential"),
                (config["db_password"],"/run/secrets/db_password"),
                (value["notification_key"],"/run/secrets/notification_key")):
            args += ["--mount","type=bind,source="+source+",target="+target+",readonly"]
        args += [image,"python","-B","-m","app.notification_cli","automatic"]
        try:
            host.command(args,seconds(5))
            for network in config["networks"][1:]:
                host.command(["network","connect",network,name],seconds(3))
            status,result=host.command(["start","-a",name],seconds(85),json_output=True)
            return dict(ok=status==0 and result.get("ok") is True,persisted=result.get("persisted") is True,
                code="notification_automatic_complete" if status==0 and result.get("ok") is True else "notification_automatic_unconfirmed")
        finally:
            # Only this invocation's exact random name, including failed create.
            host.Runtime.cleanup(name,until,list_seconds=3,remove_seconds=5)


def operate(mode,value,host):
    if os.name!="posix" or os.geteuid()!=0:raise ValueError()
    config=host.profile(value["processing_profile"],storage=mode!="notifications")
    if mode in {"inbox","corrections"}:
        return host.operate(mode,value["processing_image"],config,host.AUTOMATIC_MAX_QUANTA,scheduled_state=value["processing_state"])
    if mode=="notifications":return notify(value,host,config)
    raise ValueError()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("inbox","corrections","notifications"))
    parser.add_argument("--profile",required=True)
    args=parser.parse_args()
    def interrupted(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,interrupted)
    try:
        if not sys.flags.isolated or not sys.dont_write_bytecode:raise ValueError()
        host=load_processing()
        result=operate(args.mode,profile(args.profile,host),host)
    except (OSError,ValueError,TypeError,KeyError,RuntimeError,subprocess.SubprocessError,KeyboardInterrupt):
        result=dict(ok=False,uncertain=True,code="automation_host_failed")
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__=="__main__":raise SystemExit(main())
