"""Fixed Linux AP12 host controller. Root-only; no API socket or general commands."""
import argparse
from contextlib import ExitStack,contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

PROFILE="/etc/invoice-importer/rotation-host.json"
WORKER_DIRECTORY="/var/lib/invoice-importer/rotation"
API_COMMAND=["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--no-server-header","--no-access-log"]


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError("rotation_profile_invalid")
        result[key]=value
    return result


def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("ascii")
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def peer(filename):
    path=Path(__file__).with_name(filename)
    for part in (*reversed(path.parents),path):
        info=part.lstat()
        if info.st_uid!=0 or info.st_mode&0o022 or part.is_symlink():raise ValueError("rotation_peer_invalid")
    spec=importlib.util.spec_from_file_location("invoice_rotation_"+filename.replace("-","_"),path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def seconds(until,maximum):
    value=min(maximum,until-time.monotonic())
    if value<=0:raise ValueError("rotation_host_deadline")
    return value


def input_command(host,args,payload,until):
    """Existing host subprocess rules with bounded private stdin and stdout."""
    raw=canonical(payload)
    if len(raw)>16384:raise ValueError("rotation_request_limit")
    process=subprocess.Popen(host.DOCKER+args,env=host.ENVIRONMENT,stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
    poll=selectors.DefaultSelector();output=bytearray();offset=0
    try:
        os.set_blocking(process.stdin.fileno(),False);os.set_blocking(process.stdout.fileno(),False)
        poll.register(process.stdin,selectors.EVENT_WRITE,"input");poll.register(process.stdout,selectors.EVENT_READ,"output")
        while poll.get_map():
            events=poll.select(seconds(until,85))
            if not events:raise ValueError("rotation_host_deadline")
            for key,_ in events:
                if key.data=="input":
                    offset+=os.write(process.stdin.fileno(),raw[offset:])
                    if offset==len(raw):poll.unregister(process.stdin);process.stdin.close()
                else:
                    data=os.read(process.stdout.fileno(),min(8192,65537-len(output)))
                    if not data:poll.unregister(process.stdout)
                    else:
                        output.extend(data)
                        if len(output)>65536:raise ValueError("rotation_response_limit")
        status=process.wait(timeout=seconds(until,2))
        result=json.loads(output,object_pairs_hook=unique)
        if status or not isinstance(result,dict) or result.get("ok") is not True:raise ValueError("rotation_command_unconfirmed")
        return result
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=seconds(until+2,2))
        raise
    finally:
        poll.close()
        if not process.stdin.closed:process.stdin.close()
        process.stdout.close()


class Controller:
    def __init__(self,path=PROFILE,*,until=None):
        if os.name!="posix" or os.geteuid()!=0:raise ValueError("rotation_host_required")
        self.until=until or time.monotonic()+780
        self.host=peer("run-processing.py");self.runtime=peer("host-runtime.py")
        self.automation=peer("run-automation.py");self.gates=peer("graph-access-host.py");self.model=peer("graph-access-model.py")
        if self.command(["info","--format","{{.CgroupDriver}}/{{.CgroupVersion}}"] )!="systemd/2":
            raise ValueError("rotation_cgroup_v2_required")
        self.profile=json.loads(self.host.protected(path).read_text(encoding="utf-8"),object_pairs_hook=unique)
        if set(self.profile)!={"source_commit","api_image","automation_profile","journal_directory","compose_directory","compose_env","compose_files"}:
            raise ValueError("rotation_profile_invalid")
        if not re.fullmatch("[0-9a-f]{40}",self.profile["source_commit"]) or not re.fullmatch("sha256:[0-9a-f]{64}",self.profile["api_image"]):
            raise ValueError("rotation_profile_invalid")
        self.auto=self.automation.profile(self.profile["automation_profile"],self.host)
        self.processing=self.host.profile(self.auto["processing_profile"],storage=False)
        self.binding=self.runtime.profile(self.auto["runtime_profile"],self.host)
        mounts=self.gates.consumer_mounts(self.host.protected,self.host.controlled_directory)
        self.binding_file,self.gate_directory=map(lambda item:Path(item[0]),mounts)
        value=json.loads(self.host.protected(self.binding_file).read_text(encoding="utf-8"),object_pairs_hook=unique)
        if set(value)!={"schema_version","source_commit","deployment_id","instance_id","application_id","scope_key"} or value["schema_version"]!=1:
            raise ValueError("rotation_binding_invalid")
        self.access=self.model.AccessBinding(**{name:value[name] for name in self.model.BINDING_FIELDS})
        if self.access.source_commit!=self.profile["source_commit"] or self.access.instance_id!=self.binding["instance_id"]:
            raise ValueError("rotation_binding_invalid")
        self.journal=self.host.controlled_directory(self.profile["journal_directory"])
        if self.journal.stat().st_mode&0o777!=0o700:raise ValueError("rotation_journal_invalid")
        self.host.protected(self.profile["compose_env"]);self.compose_directory=self.host.controlled_directory(self.profile["compose_directory"])
        files=self.profile["compose_files"]
        if not isinstance(files,list) or not 1<=len(files)<=8 or len(set(files))!=len(files):raise ValueError("rotation_compose_invalid")
        for item in files:
            path=self.host.protected(item)
            if path.parent!=self.compose_directory or "," in str(path):raise ValueError("rotation_compose_invalid")
        self.images=dict(api=self.profile["api_image"],processing=self.auto["processing_image"],notifications=self.auto["notification_image"])
        gate=self.model.AccessGate(self.access,directory=self.gate_directory)
        previous=gate.read() if (self.gate_directory/"graph-access.json").exists() else None
        if previous and (previous["instance_id"]!=self.access.instance_id or previous["scope_key"]!=self.access.scope_key):
            raise ValueError("rotation_binding_invalid")
        gate_binding=self.model.AccessBinding(**{name:previous[name] for name in self.model.BINDING_FIELDS}) if previous else self.access
        self.writer=self.gates.GraphGateWriter(self.gate_directory,gate_binding,self.host,self.model)
        self.control=None

    def job_path(self,name):
        if not re.fullmatch("invoice-rotation-[0-9a-f]{32}",name):raise ValueError("rotation_job_invalid")
        return self.journal/(name+".job.json")

    def command(self,args,maximum=5,*,json_output=False):
        return self.host.command(args,seconds(self.until,maximum),json_output=json_output)

    def write(self,path,value,*,mode=0o600,gid=None):
        self.host.controlled_directory(path.parent)
        if path.exists() or path.is_symlink():self.host.protected(path)
        fd,name=tempfile.mkstemp(prefix=".rotation-",dir=path.parent)
        try:
            with os.fdopen(fd,"wb") as output:
                if gid is not None:os.fchown(output.fileno(),0,gid)
                os.fchmod(output.fileno(),mode);output.write(value if isinstance(value,bytes) else canonical(value));output.flush();os.fsync(output.fileno())
            os.replace(name,path);self.runtime.sync_directory(path.parent)
        finally:
            if os.path.exists(name):os.unlink(name)

    def image(self,image):
        status,value=self.command(["image","inspect","--format","{{json .}}",image],json_output=True)
        if status or value.get("Id")!=image or value.get("Config",{}).get("Labels",{}).get("org.opencontainers.image.revision")!=self.access.source_commit:
            raise ValueError("rotation_image_changed")

    def inspect(self,name,image,uid):
        status,value=self.command(["inspect","--format","{{json .}}",name],json_output=True)
        config=value.get("Config",{});host=value.get("HostConfig",{})
        if (status or value.get("Image")!=image or not re.fullmatch("[0-9a-f]{64}",value.get("Id",""))
                or config.get("User")!=uid or host.get("ReadonlyRootfs") is not True or host.get("Privileged") is True
                or host.get("CgroupParent") not in (None,"","system.slice") or host.get("PidMode") not in (None,"")
                or "ALL" not in host.get("CapDrop",[]) or not any(item in {"no-new-privileges","no-new-privileges:true"} for item in host.get("SecurityOpt",[]))):
            raise ValueError("rotation_container_changed")
        return value

    def cgroup(self,item):
        pid=item["State"]["Pid"]
        expected=Path("/sys/fs/cgroup/system.slice")/("docker-"+item["Id"]+".scope")
        if pid==0 and not item["State"].get("Running"):return expected
        if type(pid) is not int or pid<=0:raise ValueError("rotation_pid_unconfirmed")
        rows=Path("/proc",str(pid),"cgroup").read_text().splitlines()
        if len(rows)!=1 or not rows[0].startswith("0::/"):raise ValueError("rotation_cgroup_v2_required")
        relative=rows[0][3:]
        if item["Id"] not in relative or ".." in Path(relative).parts:raise ValueError("rotation_cgroup_unconfirmed")
        path=Path("/sys/fs/cgroup")/relative.lstrip("/")
        if path!=expected or not path.is_dir():raise ValueError("rotation_cgroup_unconfirmed")
        return path

    def quiet(self,path,*,main=None):
        try:values={int(value) for value in (path/"cgroup.procs").read_text().split()}
        except FileNotFoundError:values=set()
        if values!=({main} if main is not None else set()):raise ValueError("rotation_consumers_not_quiet")
        try:events=dict(line.split() for line in (path/"cgroup.events").read_text().splitlines())
        except FileNotFoundError:
            if main is not None or path.exists():raise ValueError("rotation_cgroup_unconfirmed")
            return
        if events.get("populated")!=("1" if main is not None else "0") or events.get("frozen")!="0":
            raise ValueError("rotation_consumers_not_quiet")

    def wait_quiet(self,path,*,main=None):
        self.runtime.wait_readiness(lambda:self.quiet(path,main=main),min(self.until,time.monotonic()+10))

    def stop(self,item):
        if item["State"].get("Paused"):raise ValueError("rotation_api_paused")
        path=self.cgroup(item)
        self.command(["stop","--time","20",item["Id"]],30)
        status,state=self.command(["inspect","--format","{{json .State}}",item["Id"]],json_output=True)
        if status or state.get("Running") or state.get("Pid")!=0:raise ValueError("rotation_stop_unconfirmed")
        self.wait_quiet(path)
        return dict(container_id=item["Id"],stopped=True,cgroup=str(path))

    def mounts(self,pem,*,worker=False):
        values=[(self.processing["graph_config"],"/run/importer/graph.json",True),(pem,"/run/secrets/graph_credential",True),
            (self.binding_file,"/run/importer/graph-access-binding.json",True),(self.gate_directory,"/run/importer/operations/graph-access",True),
            (self.processing["db_password"],"/run/secrets/db_password",True)]
        if worker:values.append((self.journal,WORKER_DIRECTORY,False))
        return values

    def create(self,image,uid,command,operation,pem,*,worker=False,role=None):
        self.image(image);name="invoice-rotation-"+uuid4().hex
        args=["create","--interactive","--init","--cgroup-parent","system.slice","--name",name,"--label","invoice.rotation.operation="+operation,
            "--network",self.processing["networks"][0],"--user",uid,"--read-only","--cap-drop","ALL", "--security-opt","no-new-privileges:true",
            "--memory","512m","--memory-swap","512m","--cpus","1","--pids-limit","96","--workdir","/app","--tmpfs","/tmp:rw,noexec,nosuid,size=64m"]
        for key,value in {"DB_HOST":self.processing["db_host"],"DB_NAME":self.processing["db_name"],"DB_USER":self.processing["db_user"],"DB_PASSWORD_FILE":"/run/secrets/db_password"}.items():
            args.extend(["--env",key+"="+value])
        for source,target,readonly in self.mounts(pem,worker=worker):
            args.extend(["--mount","type=bind,source="+str(source)+",target="+target+(",readonly" if readonly else "")])
        if role=="processing":
            args.extend(["--group-add",str(self.processing["storage_gid"]),"--mount","type=bind,source="+self.processing["processing_config"]+",target=/run/importer/processing.json,readonly"])
        if role=="notifications":args.extend(["--mount","type=bind,source="+self.auto["notification_key"]+",target=/run/secrets/notification_key,readonly"])
        args.extend([image,"python","-B","-m",command])
        self.write(self.job_path(name),dict(kind="container",name=name,image=image,uid=uid,operation_id=operation,command=command,
            **self.access.fields()))
        self.command(args,15)
        for network in self.processing["networks"][1:]:self.command(["network","connect",network,name])
        item=self.inspect(name,image,uid)
        if item["Config"].get("Cmd")!=["python","-B","-m",command]:raise ValueError("rotation_command_changed")
        return item

    def cleanup(self,item):
        current=self.inspect(item["Id"],item["Image"],item["Config"]["User"])
        if current["State"].get("Running"):self.stop(current)
        else:self.wait_quiet(self.cgroup(current))
        self.command(["rm",item["Id"]],10)
        if self.command(["container","ls","-aq","--filter","id="+item["Id"]]):raise ValueError("rotation_cleanup_unconfirmed")

    def finish_job(self,name):
        path=self.job_path(name);self.host.protected(path)
        os.unlink(path);self.runtime.sync_directory(path.parent)

    def worker(self,command,operation=None,**values):
        item=self.create(self.images["notifications"],"0:10001","app.rotation_worker",operation or str(uuid4()),self.processing["graph_credential"],worker=True)
        try:return input_command(self.host,["start","-a","-i",item["Id"]],dict(command=command,operation_id=operation,**values),min(self.until,time.monotonic()+85))
        finally:self.cleanup(item);self.finish_job(item["Name"].lstrip("/"))

    @contextmanager
    def lifecycle_locks(self):
        with ExitStack() as locks:
            for path in (self.runtime.LIFECYCLE_LOCK,self.host.PROCESSING_LOCK,"/run/invoice-importer/notification.lock"):
                if not locks.enter_context(self.host.host_lock(path,wait=seconds(self.until,45))):raise ValueError("rotation_host_busy")
            yield

    def recover_exec(self,value):
        ids=self.command(["container","ls","-aq","--filter","id="+value["container_id"]])
        if ids:
            item=self.inspect(value["container_id"],value["image"],"10001:10001")
            self.stop(item)  # Unknown exec: whole known API cgroup, never only Docker client.
        else:
            if not re.fullmatch("[0-9a-f]{64}",value["container_id"]):raise ValueError("rotation_job_changed")
            self.wait_quiet(Path("/sys/fs/cgroup/system.slice")/("docker-"+value["container_id"]+".scope"))

    def recover_job(self,*,locked=False):
        paths=list(self.journal.glob("invoice-rotation-*.job.json"))
        if len(paths)>16:raise ValueError("rotation_jobs_unreconciled")
        for path in paths:
            value=json.loads(self.host.protected(path).read_text(),object_pairs_hook=unique)
            if self.job_path(value["name"])!=path or any(value.get(name)!=expected for name,expected in self.access.fields().items()):raise ValueError("rotation_job_changed")
            if value["kind"]=="exec":
                self.block(value["operation_id"])
                if locked:
                    self.writer._require(exclusive=True)
                    self.recover_exec(value)
                else:
                    self.drain(value["operation_id"])
                    with self.lifecycle_locks():
                        self.recover_exec(value)
                        current=self.writer.gate.read()
                        with self.writer.exclusive(value["operation_id"],expected_epoch=current["epoch"],until=min(self.until,time.monotonic()+90)):
                            self.finish_job(value["name"])
                    continue
            elif value["kind"]=="container":
                names=self.command(["container","ls","-a","--filter","name=^/"+value["name"]+"$","--format","{{.Names}}"])
                if names:
                    if names!=value["name"]:raise ValueError("rotation_job_changed")
                    item=self.inspect(value["name"],value["image"],value["uid"])
                    if item["Config"].get("Labels",{}).get("invoice.rotation.operation")!=value["operation_id"]:raise ValueError("rotation_job_changed")
                    self.cleanup(item)
            else:raise ValueError("rotation_job_invalid")
            self.finish_job(value["name"])

    def probe(self,operation,role,purpose,pem,*,api=None,before=None):
        image=self.images["api" if role=="api" else "notifications" if role=="candidate" else role]
        item=api if api is not None else self.create(image,"10001:10001","app.graph_access_probe",operation,pem,role=role)
        consumer_id=hashlib.sha256(item["Id"].encode()).hexdigest();current=self.writer.gate.read()
        secret,state=self.writer.issue_probe(operation,expected_epoch=current["epoch"],purpose=purpose,consumer_role=role,consumer_id=consumer_id)
        packet=dict(schema_version=1,operation_id=operation,epoch=state["epoch"],purpose=purpose,consumer_role=role,consumer_id=consumer_id,secret=secret.hex())
        path=None;job=item["Name"].lstrip("/") if api is None else "invoice-rotation-"+uuid4().hex
        try:
            if before is not None:before(dict(container_id=item["Id"],image=image,probe=None),state["epoch"])
            if api is not None:
                path=self.cgroup(item);self.quiet(path,main=item["State"]["Pid"])
                self.write(self.job_path(job),dict(kind="exec",name=job,container_id=item["Id"],image=image,uid="10001:10001",
                    operation_id=operation,**self.access.fields()))
                result=input_command(self.host,["exec","-i","--user","10001:10001",item["Id"],"python","-B","-m","app.graph_access_probe"],packet,min(self.until,time.monotonic()+50))
                self.wait_quiet(path,main=item["State"]["Pid"])
            else:result=input_command(self.host,["start","-a","-i",item["Id"]],packet,min(self.until,time.monotonic()+50))
            if (result.get("consumer_id")!=consumer_id or result.get("epoch")!=state["epoch"] or result.get("purpose")!=purpose
                    or result.get("operation_id")!=operation or result.get("consumer_role")!=role
                    or any(result.get(name)!=expected for name,expected in self.access.fields().items())
                    or any(result.get(name)!=state[name] for name in ("pem_hash","fingerprint"))
                    or type(result.get("at")) is not int or not 0<=time.time()-result["at"]<=60
                    or result.get("receipt_hash")!=digest({key:value for key,value in result.items() if key!="receipt_hash"})):
                raise ValueError("rotation_probe_unconfirmed")
            return dict(container_id=item["Id"],image=image,probe=result)
        finally:
            if api is None:self.cleanup(item)
            elif path is not None:
                try:self.quiet(path,main=item["State"]["Pid"])
                except (OSError,ValueError):self.stop(item)
            if self.job_path(job).exists():self.finish_job(job)
            latest=self.writer.gate.read();self.writer.revoke_probe(operation,expected_epoch=latest["epoch"])

    def api(self,*,image=None):
        item=self.inspect(self.binding["containers"]["api"]["name"],image or self.binding["containers"]["api"]["image"],"10001:10001")
        if item["Config"].get("Cmd")!=API_COMMAND or item["Config"].get("Entrypoint") not in (None,[]) or item["HostConfig"].get("Init") is True:
            raise ValueError("rotation_api_changed")
        required={"/run/importer/graph.json":self.processing["graph_config"],"/run/secrets/graph_credential":self.processing["graph_credential"],
            "/run/importer/graph-access-binding.json":str(self.binding_file),"/run/importer/operations/graph-access":str(self.gate_directory),
            "/run/secrets/notification_key":self.auto["notification_key"]}
        for target,source in required.items():
            matches=[mount for mount in item["Mounts"] if mount.get("Destination")==target]
            if len(matches)!=1 or matches[0].get("RW") is not False or matches[0].get("Source")!=source:raise ValueError("rotation_api_mount_changed")
        if any(mount.get("RW") is True and mount.get("Type")!="tmpfs" for mount in item["Mounts"]):raise ValueError("rotation_api_writable_mount")
        return item

    def no_other_graph_consumers(self,api_id):
        ids=self.command(["container","ls","-aq"]).splitlines()
        if len(ids)>128:raise ValueError("rotation_consumer_inventory_limit")
        for identifier in ids:
            status,value=self.command(["inspect","--format","{{json .}}",identifier],json_output=True)
            if status:raise ValueError("rotation_consumer_inventory_changed")
            relevant=any(mount.get("Destination")=="/run/secrets/graph_credential" and (
                mount.get("Source")==self.processing["graph_credential"] or str(mount.get("Source","")).startswith(str(self.journal)+"/")) for mount in value.get("Mounts",[]))
            if relevant and value["Id"]!=api_id:
                if value["State"].get("Running"):raise ValueError("rotation_unreconciled_consumer")
                self.quiet(self.cgroup(value))

    def marker(self):
        path=Path(self.host.DRAIN_FILE)
        try:
            raw=self.host.protected(path).read_bytes();info=path.stat()
        except FileNotFoundError:return None
        return dict(device=info.st_dev,inode=info.st_ino,sha256=hashlib.sha256(raw).hexdigest(),boot_id=self.model.boot_id())

    def external_drain(self):
        current=self.marker()
        if current is None:return None
        if self.control and current==self.control.get("owned_drain"):return None
        return digest(current)

    def control_record(self,operation,*,paused=False):
        path=self.journal/(operation+".controller.json")
        if path.exists():
            self.control=json.loads(self.host.protected(path).read_text(),object_pairs_hook=unique)
            if (any(self.control.get(name)!=expected for name,expected in self.access.fields().items()) or self.control.get("operation_id")!=operation
                    or type(self.control.get("graph_paused",False)) is not bool):
                raise ValueError("rotation_controller_changed")
        else:
            self.control=dict(operation_id=operation,**self.access.fields(),owned_drain=None,owned_value=None)
        desired=self.control.get("graph_paused",False) or paused
        if self.control.get("graph_paused") is not desired:
            self.control["graph_paused"]=desired;self.write(path,self.control)
        return path

    def block(self,operation):
        current=self.writer.gate.read()
        # Preserve the observed operator pause before its gate representation is
        # overwritten, including loss before any lifecycle lock or worker call.
        self.control_record(operation,paused=current["mode"]=="paused")
        return self.writer.block(operation,expected_epoch=current["epoch"])

    def drain(self,operation):
        path=self.control_record(operation)
        with self.host.host_lock(self.runtime.GATE_LOCK,wait=seconds(self.until,5)) as acquired:
            if not acquired:raise ValueError("rotation_gate_busy")
            current=self.marker()
            if current is None:
                self.control.update(owned_value=uuid4().hex,owned_drain=None)
                self.write(path,self.control)
                self.write(Path(self.host.DRAIN_FILE),self.control["owned_value"].encode())
                self.control["owned_drain"]=self.marker();self.write(path,self.control)
            elif self.control["owned_drain"] is None and self.control["owned_value"] is not None and current["sha256"]==hashlib.sha256(self.control["owned_value"].encode()).hexdigest():
                self.control["owned_drain"]=current;self.write(path,self.control)
            elif not path.exists():self.write(path,self.control)

    def clear_drain(self):
        with self.host.host_lock(self.runtime.GATE_LOCK,wait=seconds(self.until,5)) as acquired:
            if not acquired:raise ValueError("rotation_gate_busy")
            if self.control and self.control.get("owned_drain") is not None and self.marker()==self.control["owned_drain"]:
                os.unlink(self.host.DRAIN_FILE);self.runtime.sync_directory(Path(self.host.DRAIN_FILE).parent)

    def material(self,operation,metadata,*,old=False,readable=False):
        path=self.journal/(operation+(".old.pem" if old else ".pem"))
        raw=self.host.protected(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=metadata["pem_hash"]:raise ValueError("rotation_material_changed")
        if readable:
            target=self.journal/(operation+".probe.pem")
            self.write(target,raw,mode=0o440,gid=10001)
            return target
        return raw

    def activate(self,raw,expected_hash):
        if hashlib.sha256(raw).hexdigest()!=expected_hash:raise ValueError("rotation_material_changed")
        path=self.host.protected(self.processing["graph_credential"]);info=path.stat()
        self.write(path,raw,mode=info.st_mode&0o777,gid=info.st_gid)
        if hashlib.sha256(self.host.protected(path).read_bytes()).hexdigest()!=expected_hash:raise ValueError("rotation_activation_unconfirmed")

    def candidate_gate(self,operation,material):
        current=self.writer.gate.read()
        return self.writer.candidate(operation,expected_epoch=current["epoch"],pem_hash=material["pem_hash"],fingerprint=material["fingerprint"])

    def rebind(self,operation,material):
        self.writer._require(exclusive=True)
        current=self.writer.gate.read()
        value=dict(current,**self.access.fields(),boot_id=self.model.boot_id(),epoch=current["epoch"]+1,admission_epoch=0,
            operation_id=operation,pem_hash=material["pem_hash"],fingerprint=material["fingerprint"],release_hash=None,grants=[])
        self.model.validate(value)
        self.write(self.gate_directory/"graph-access.json",value,mode=0o440,gid=10001)
        self.writer.binding=self.access;self.writer.gate.binding=self.access

    def archive(self,path,value):
        if path.exists():
            if json.loads(self.host.protected(path).read_text(),object_pairs_hook=unique)!=value:
                raise ValueError("rotation_archive_changed")
        else:self.write(path,value)

    def exchange(self,operation):
        path=self.journal/(operation+".api-exchange.json")
        if not path.exists():return None
        value=json.loads(self.host.protected(path).read_text(),object_pairs_hook=unique)
        if (value.get("version")!=1 or value.get("operation_id")!=operation
                or any(value.get(name)!=expected for name,expected in self.access.fields().items())
                or value.get("name")!=self.binding["containers"]["api"]["name"] or value.get("image")!=self.images["api"]
                or not re.fullmatch("[0-9a-f]{32}",value.get("nonce",""))
                or not re.fullmatch("[0-9a-f]{64}",value.get("pem_hash",""))
                or value.get("phase") not in {"planned","created","confirmed"}
                or set(value.get("preserved",{}))!={"db","nginx"}):raise ValueError("rotation_exchange_changed")
        if value["new_id"] is not None and not re.fullmatch("[0-9a-f]{64}",value["new_id"]):raise ValueError("rotation_exchange_changed")
        old=value["old"]
        if old is not None and (set(old)!={"id","image"} or not re.fullmatch("[0-9a-f]{64}",old["id"])
                or not re.fullmatch("sha256:[0-9a-f]{64}",old["image"])):raise ValueError("rotation_exchange_changed")
        return value

    def bound_api(self,operation,*,legacy=False):
        """Absent/replaced API is allowed only by the durable, private exchange intent."""
        value=self.exchange(operation);name=self.binding["containers"]["api"]["name"]
        names=self.command(["container","ls","-a","--filter","name=^/"+name+"$","--format","{{.Names}}"])
        if not names:
            if value is None:raise ValueError("rotation_api_absence_unbound")
            for identifier in (value["old"]["id"] if value["old"] else None,value["new_id"]):
                if identifier:self.wait_quiet(Path("/sys/fs/cgroup/system.slice")/("docker-"+identifier+".scope"))
            return None
        if names!=name:raise ValueError("rotation_api_changed")
        if value is not None:
            try:
                item=self.api(image=value["image"]);labels=item["Config"].get("Labels",{})
                if (labels.get("invoice.rotation.operation")!=operation or labels.get("invoice.rotation.exchange")!=value["nonce"]
                        or value["new_id"] not in (None,item["Id"])):raise ValueError("rotation_exchange_changed")
                return item
            except ValueError:
                if value["old"] is None or value["phase"]!="planned":raise
                old=value["old"];item=self.inspect(name,old["image"],"10001:10001") if legacy else self.api(image=old["image"])
                if item["Id"]!=old["id"]:raise ValueError("rotation_exchange_changed")
        else:item=self.inspect(name,self.binding["containers"]["api"]["image"],"10001:10001") if legacy else self.api()
        if item["Config"].get("Cmd")!=API_COMMAND:raise ValueError("rotation_api_changed")
        return item

    def recreate_api(self,operation):
        self.writer._require(exclusive=True);self.image(self.images["api"])
        path=self.journal/(operation+".api-exchange.json");previous=self.exchange(operation)
        api=self.bound_api(operation,legacy=(self.journal/".bootstrap.json").exists() and not (self.journal/(operation+".host.json")).exists())
        pem_hash=hashlib.sha256(self.host.protected(self.processing["graph_credential"]).read_bytes()).hexdigest()
        before={kind:self.runtime.inspect_container(self.binding,kind,self.host,self.until) for kind in ("db","nginx")}
        if previous is not None:self.preserved(previous["preserved"])
        if previous is None or previous["pem_hash"]!=pem_hash:
            if previous is not None:self.archive(self.journal/(operation+".api-exchange-"+previous["nonce"]+".json"),previous)
            value=dict(version=1,**self.access.fields(),operation_id=operation,name=self.binding["containers"]["api"]["name"],
                old=dict(id=api["Id"],image=api["Image"]) if api else None,image=self.images["api"],nonce=uuid4().hex,
                pem_hash=pem_hash,preserved={kind:dict(id=item["id"]) for kind,item in before.items()},new_id=None,phase="planned")
            self.write(path,value)
        else:value=previous
        override=self.journal/(operation+".api.json")
        labels={"invoice.rotation.operation":operation,"invoice.rotation.exchange":value["nonce"]}
        self.write(override,dict(services=dict(api=dict(image=self.images["api"],container_name=value["name"],labels=labels))))
        args=["compose","--project-directory",str(self.compose_directory),"--env-file",self.profile["compose_env"]]
        for compose_file in [*self.profile["compose_files"],str(override)]:args.extend(["-f",compose_file])
        status,definition=self.command([*args,"config","--format","json"],10,json_output=True)
        candidate=definition.get("services",{}).get("api",{})
        if (status or candidate.get("image")!=self.images["api"] or candidate.get("user")!="10001:10001"
                or candidate.get("read_only") is not True or "ALL" not in candidate.get("cap_drop",[]) or candidate.get("privileged") is True
                or candidate.get("container_name")!=value["name"] or any(candidate.get("labels",{}).get(key)!=item for key,item in labels.items())):
            raise ValueError("rotation_compose_changed")
        if api is not None and api["Config"].get("Labels",{}).get("invoice.rotation.exchange")==value["nonce"]:
            if not api["State"].get("Running"):self.command(["start",api["Id"]],15)
        else:self.command([*args,"up","-d","--no-deps","--no-build","--pull","never","--force-recreate","api"],60)
        item=self.bound_api(operation)
        if item is None:raise ValueError("rotation_api_unready")
        value=dict(value,new_id=item["Id"],phase="created");self.write(path,value)
        self.binding["containers"]["api"]["image"]=self.images["api"]
        self.runtime.wait_readiness(lambda:self.api(),min(self.until,time.monotonic()+45))
        # Keep nginx's identity and TLS files; refresh its existing static API DNS.
        nginx=self.runtime.inspect_container(self.binding,"nginx",self.host,self.until)
        if nginx["id"]!=value["preserved"]["nginx"]["id"]:raise ValueError("rotation_non_api_container_changed")
        if nginx["state"].get("Running"):
            self.command(["exec",nginx["id"],"nginx","-t"],10)
            self.command(["exec",nginx["id"],"nginx","-s","reload"],10)
        else:self.command(["start",nginx["id"]],10)
        self.runtime.wait_readiness(lambda:self.runtime.ready(self.binding,self.auto["public_origin"],self.host,self.until),min(self.until,time.monotonic()+45))
        self.write(Path(self.auto["runtime_profile"]),self.binding)
        item=self.api()
        if not item["State"].get("Running") or item["State"].get("Health",{}).get("Status")!="healthy":raise ValueError("rotation_api_unready")
        self.preserved(value["preserved"]);self.write(path,dict(value,phase="confirmed"))
        return item

    def preserved(self,before):
        for kind in ("db","nginx"):
            current=self.runtime.inspect_container(self.binding,kind,self.host,self.until)
            if current["id"]!=before[kind]["id"]:raise ValueError("rotation_non_api_container_changed")

    def finish(self,operation,api,before,*,pause_retry=False):
        receipts={"api":self.probe(operation,"api","consumer-read",self.processing["graph_credential"],api=api)}
        with self.host.CifsBinding(self.processing) as cifs:
            cifs.check();receipts["processing"]=self.probe(operation,"processing","consumer-read",self.processing["graph_credential"]);cifs.check()
        receipts["notifications"]=self.probe(operation,"notifications","consumer-read",self.processing["graph_credential"])
        self.worker("consumers",operation,receipts=receipts)
        observed=self.worker("monitor",operation)["observed"]
        def intent(consumer,epoch):self.worker("proof-started",operation,consumer=consumer,epoch=epoch,base_revision=observed["revision"])
        try:proof=self.probe(operation,"notifications","finalize-proof",self.processing["graph_credential"],before=intent)
        except BaseException:
            state=self.worker("read",operation)["host"]
            if state["phase"]=="proof_started":self.worker("proof-unknown",operation)
            raise
        self.worker("proof-verified",operation,receipt=proof)
        state=self.worker("read",operation)["host"]
        self.preserved(before);current_api=self.api()
        if current_api["Id"]!=api["Id"]:raise ValueError("rotation_api_changed")
        if hashlib.sha256(self.host.protected(self.processing["graph_credential"]).read_bytes()).hexdigest()!=state[state["target"]]["pem_hash"]:
            raise ValueError("rotation_material_changed")
        if self.external_drain()!=state["drain_identity"]:
            if pause_retry:raise ValueError("rotation_pause_changed")
            group=self.cgroup(current_api);self.quiet(group,main=current_api["State"]["Pid"])
            self.worker("recover",operation,pem_hash=state[state["target"]]["pem_hash"],quiet_evidence=digest(dict(
                api_id=current_api["Id"],pid=current_api["State"]["Pid"],cgroup=str(group),quiet=True)),
                paused=state["paused"],drain_identity=self.external_drain())
            return self.finish(operation,current_api,before,pause_retry=True)
        state=self.worker("commit",operation,paused=state["paused"],drain_identity=self.external_drain())["host"]
        if self.external_drain()!=state["drain_identity"]:raise ValueError("rotation_pause_changed")
        latest=self.writer.gate.read()
        self.writer.release(operation,expected_epoch=latest["epoch"],release_hash=state["seal"],pause=state["paused"])
        try:self.clear_drain();self.worker("publish",operation)
        except (OSError,ValueError):return dict(ok=False,operation_id=operation,material_confirmed=True,code="rotation_completion_pending")
        return dict(ok=True,operation_id=operation,target=state["target"],phase="committed",paused=state["paused"],seal=state["seal"])

    def stop_current_api(self,operation):
        item=self.bound_api(operation)
        return self.stop(item) if item is not None else dict(absent=True)

    def switch(self,operation,state,mode,before,quiet):
        current_hash=hashlib.sha256(self.host.protected(self.processing["graph_credential"]).read_bytes()).hexdigest()
        if mode=="rollback" or state["phase"]!="prepared" or state["boot_id"]!=self.model.boot_id() or state["paused"]:
            state=self.worker("recover",operation,pem_hash=current_hash,quiet_evidence=digest(quiet),paused=state["paused"],drain_identity=self.external_drain())["host"]
        if mode=="rollback" and state["target"]=="new":state=self.worker("rollback",operation)["host"]
        if state["phase"]=="prepared":
            self.candidate_gate(operation,state["new"])
            pem=self.material(operation,state["new"],readable=True)
            receipt=self.probe(operation,"candidate","candidate-read",pem)
            self.worker("candidate-verified",operation,receipt=receipt)
            state=self.worker("activation-started",operation)["host"]
        if state["phase"]=="activation_started":
            raw=self.material(operation,state[state["target"]],old=state["target"]=="old")
            self.activate(raw,state[state["target"]]["pem_hash"])
            state=self.worker("activated",operation)["host"]
        self.candidate_gate(operation,state[state["target"]])
        return self.finish(operation,self.recreate_api(operation),before)

    def return_old(self,operation,before):
        self.recover_job(locked=True);quiet=self.stop_current_api(operation)
        state=self.worker("read",operation)["host"]
        if state["target"]=="old":
            if state["phase"]!="committed":self.worker("rollback-unknown",operation)
            raise ValueError("rotation_rollback_unconfirmed")
        current_hash=hashlib.sha256(self.host.protected(self.processing["graph_credential"]).read_bytes()).hexdigest()
        state=self.worker("recover",operation,pem_hash=current_hash,quiet_evidence=digest(quiet),
            paused=state["paused"] or bool(self.control and self.control["graph_paused"]),drain_identity=self.external_drain())["host"]
        if state["target"]=="new":state=self.worker("rollback",operation)["host"]
        raw=self.material(operation,state["old"],old=True);self.activate(raw,state["old"]["pem_hash"])
        if state["phase"]=="activation_started":self.worker("activated",operation)
        self.candidate_gate(operation,state["old"])
        try:return self.finish(operation,self.recreate_api(operation),before)
        except BaseException:
            state=self.worker("read",operation)["host"]
            if state["phase"]!="committed":self.worker("rollback-unknown",operation)
            raise

    def bootstrap(self,status):
        """Install/recover guarded consumers with unchanged current key, no addKey."""
        if status["head"]["active_operation"] is not None:raise ValueError("rotation_bootstrap_active_request")
        pointer=self.journal/".bootstrap.json"
        if pointer.exists():
            record=json.loads(self.host.protected(pointer).read_text(),object_pairs_hook=unique)
            if any(record.get(name)!=expected for name,expected in self.access.fields().items()) or record["current"]!=status["current"]:
                raise ValueError("rotation_bootstrap_changed")
            operation=record["operation_id"]
            if record.get("seal") is not None and record["seal"]!=digest({key:value for key,value in record.items() if key!="seal"}):
                raise ValueError("rotation_bootstrap_changed")
            current=self.writer.gate.read()
            desired_pause=record["paused"] or current["mode"]=="paused"
        else:
            current=self.writer.gate.read() if (self.gate_directory/"graph-access.json").exists() else None
            operation=str(uuid4());record=dict(operation_id=operation,**self.access.fields(),current=status["current"],
                paused=current is not None and (current["mode"]=="paused" or current["mode"]=="blocked" and current["admission_epoch"]==0),
                proof_intent=None,revision=0,seal=None,old_api=None)
            self.write(pointer,record)
            desired_pause=record["paused"]
        if not (self.gate_directory/"graph-access.json").exists():
            self.writer.initialize(operation,status["current"]["pem_hash"],status["current"]["fingerprint"])
        self.drain(operation)
        self.block(operation);desired_pause=desired_pause or self.control["graph_paused"]
        with self.lifecycle_locks():
            before={kind:self.runtime.inspect_container(self.binding,kind,self.host,self.until) for kind in ("db","nginx")}
            api=self.bound_api(operation,legacy=True)
            if api is not None:
                if record["old_api"] is None:
                    record["old_api"]=dict(id=api["Id"],image=api["Image"]);self.write(pointer,record)
                self.stop(api);api_id=api["Id"]
            else:api_id=None
            self.runtime.wait_readiness(lambda:self.no_other_graph_consumers(api_id),min(self.until,time.monotonic()+90))
            current=self.writer.gate.read()
            with self.writer.exclusive(operation,expected_epoch=current["epoch"],until=min(self.until,time.monotonic()+90)):
                if record["proof_intent"] is not None and record["seal"] is None:
                    observed=self.worker("monitor")["observed"];intent=record["proof_intent"];proof=observed["proof"]
                    if observed["revision"]!=intent["base_revision"] and not (observed["revision"]==intent["base_revision"]+1
                            and isinstance(proof,dict) and proof.get("fingerprint")==status["current"]["fingerprint"]
                            and proof.get("scope_key")==status["notification_scope"] and type(proof.get("at")) is int and proof["at"]>=intent["at"]):
                        raise ValueError("rotation_bootstrap_proof_unreconciled")
                self.archive(self.journal/(operation+".bootstrap-checkpoint-"+str(record["revision"])+".json"),record)
                record=dict(record,revision=record["revision"]+1,proof_intent=None,seal=None,paused=desired_pause)
                self.write(pointer,record);self.rebind(operation,status["current"])
                api=self.recreate_api(operation)
                receipts={"api":self.probe(operation,"api","consumer-read",self.processing["graph_credential"],api=api)}
                with self.host.CifsBinding(self.processing) as cifs:
                    cifs.check();receipts["processing"]=self.probe(operation,"processing","consumer-read",self.processing["graph_credential"]);cifs.check()
                receipts["notifications"]=self.probe(operation,"notifications","consumer-read",self.processing["graph_credential"])
                observed=self.worker("monitor")["observed"]
                def intent(consumer,epoch):
                    record["proof_intent"]=dict(base_revision=observed["revision"],at=int(time.time()),consumer=consumer,epoch=epoch)
                    self.write(pointer,record)
                proof=self.probe(operation,"notifications","finalize-proof",self.processing["graph_credential"],before=intent)
                observed=self.worker("monitor")["observed"];saved=observed["proof"]
                if (observed["revision"]!=record["proof_intent"]["base_revision"]+1 or saved is None
                        or saved.get("fingerprint")!=status["current"]["fingerprint"] or saved.get("scope_key")!=status["notification_scope"]
                        or saved.get("at")!=proof["probe"]["proof_at"] or not 0<=time.time()-saved["at"]<=60):
                    raise ValueError("rotation_bootstrap_proof_invalid")
                self.preserved(before);self.api()
                record.update(receipts=receipts,proof=proof,observed=observed,drain_identity=self.external_drain())
                record["seal"]=digest({key:value for key,value in record.items() if key!="seal"});self.write(pointer,record)
                latest=self.writer.gate.read();self.writer.release(operation,expected_epoch=latest["epoch"],release_hash=record["seal"],pause=record["paused"])
                self.clear_drain()
                return dict(ok=True,code="rotation_guarded_consumers_ready",operation_id=operation,seal=record["seal"],paused=record["paused"])

    def maintain(self,operation,published):
        cleanup=published.get("cleanup")
        if cleanup is None or cleanup["phase"]=="completed":return dict(phase=cleanup["phase"] if cleanup else None)
        if cleanup["phase"]=="planned" and time.time()<cleanup["not_before"]:return dict(phase="planned",not_before=cleanup["not_before"])
        if self.external_drain() is not None or self.writer.gate.read()["mode"]!="allowed":return dict(deferred="paused")
        with self.lifecycle_locks():
            if self.external_drain() is not None or self.writer.gate.read()["mode"]!="allowed":return dict(deferred="paused")
            self.api();self.runtime.ready(self.binding,self.auto["public_origin"],self.host,self.until)
            result=self.worker("cleanup",operation)
            return dict(phase=result["cleanup"]["phase"],state=result["request"]["state"],error_code=result["cleanup"]["error_code"])

    def operate(self,mode,*,startup=False):
        with self.writer.session():
            self.recover_job()
            status=self.worker("status")
            if status["binding"]!=self.access.fields():raise ValueError("rotation_binding_changed")
            operation=status["head"]["active_operation"]
            if mode=="bootstrap":return self.bootstrap(status)
            if operation is None:
                if not (self.gate_directory/"graph-access.json").exists() or self.writer.binding!=self.access:
                    return dict(ok=False,code="rotation_bootstrap_required")
                current=self.writer.gate.read()
                if current["mode"]=="blocked" or current["boot_id"]!=self.model.boot_id():
                    pointer=self.journal/".bootstrap.json"
                    record=json.loads(self.host.protected(pointer).read_text(),object_pairs_hook=unique) if pointer.exists() else None
                    if record and current["operation_id"]==record["operation_id"]:
                        if current["mode"]!="blocked" and current["release_hash"]!=record.get("seal"):
                            return dict(ok=False,code="rotation_blocked_unreconciled")
                        return self.bootstrap(status)
                    # A published return or completed cleanup has no active request. Claim only
                    # the exact closed gate/SQL/journal binding, never an arbitrary ID.
                    self.worker("resume-closed",current["operation_id"],seal=current["release_hash"])
                    status=self.worker("status");operation=status["head"]["active_operation"]
                else:return dict(ok=True,code="rotation_no_active_request")
            if self.writer.binding!=self.access:raise ValueError("rotation_bootstrap_required")
            initial_gate=self.writer.gate.read()
            if (mode!="rollback" and status["host"] and status["host"]["phase"]=="committed"
                    and initial_gate["mode"] in {"allowed","paused"} and initial_gate["boot_id"]==self.model.boot_id()
                    and initial_gate["release_hash"]==status["host"]["seal"] and status["current"]==status["host"][status["host"]["target"]]):
                published=self.worker("publish",operation)
                path=self.journal/(operation+".controller.json")
                if path.exists():self.control_record(operation);self.clear_drain()
                cleanup=self.maintain(operation,published)
                return dict(ok=True,operation_id=operation,phase="committed",target=status["host"]["target"],unchanged=True,cleanup=cleanup)
            if mode in {"run","resume"}:
                if status["host"] is None and (status["core"] is None or status["core"]["phase"]=="prepared"):
                    if startup:self.runtime.start(self.binding,self.auto["public_origin"],self.host,self.until,preserve_drain=True)
                    else:self.runtime.ready(self.binding,self.auto["public_origin"],self.host,self.until)
                    with self.host.CifsBinding(self.processing) as cifs:cifs.check()
                result=self.worker("register",operation)
                if result["core"]["phase"] not in {"registered","candidate_verified"}:return dict(ok=False,operation_id=operation,code=result["core"]["phase"])
            status=self.worker("status");state=status["host"]
            current=self.writer.gate.read()
            if state is None:
                state=self.worker("prepare",operation,images=self.images,paused=current["mode"]=="paused" or current["mode"]=="blocked" and current["admission_epoch"]==0,
                    drain_identity=self.external_drain())["host"]
            elif current["mode"]=="paused":state=dict(state,paused=True)
            self.drain(operation)
            self.block(operation);state=dict(state,paused=state["paused"] or self.control["graph_paused"])
            with self.lifecycle_locks():
                before={kind:self.runtime.inspect_container(self.binding,kind,self.host,self.until) for kind in ("db","nginx")}
                api=self.bound_api(operation);quiet=self.stop(api) if api is not None else dict(absent=True)
                self.runtime.wait_readiness(lambda:self.no_other_graph_consumers(api["Id"] if api is not None else None),min(self.until,time.monotonic()+90))
                current=self.writer.gate.read()
                with self.writer.exclusive(operation,expected_epoch=current["epoch"],until=min(self.until,time.monotonic()+90)):
                    try:return self.switch(operation,state,mode,before,quiet)
                    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):return self.return_old(operation,before)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("bootstrap","run","resume","rollback"));parser.add_argument("--profile",default=PROFILE)
    args=parser.parse_args()
    try:result=Controller(args.profile).operate(args.mode)
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError,KeyboardInterrupt):result=dict(ok=False,code="rotation_host_unconfirmed")
    print(json.dumps(result,separators=(",",":")))
    return 0 if result.get("ok") else 1


if __name__=="__main__":raise SystemExit(main())
