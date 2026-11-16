"""Fixed startup, drain and external TLS adoption; host-only stdlib/OpenSSL."""
from contextlib import ExitStack
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import stat
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
import uuid

LIFECYCLE_LOCK="/run/invoice-importer/lifecycle.lock"
GATE_LOCK="/run/invoice-importer/gate.lock"
CERTIFICATE=re.compile(rb"-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\s*")
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C.UTF-8"}
OPENSSL="/usr/bin/openssl"
CA_PATH="/etc/ssl/certs"


def seconds(until,maximum=5):
    value=min(maximum,until-time.monotonic())
    if value<=0:raise ValueError("host_deadline")
    return value


def profile(path,host):
    value=json.loads(host.protected(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict) or set(value)!={"containers","instance_id","tls_root","peer_address"}:raise ValueError()
    if not isinstance(value["instance_id"],str) or str(uuid.UUID(value["instance_id"]))!=value["instance_id"]:raise ValueError()
    if not isinstance(value["peer_address"],str):raise ValueError()
    ipaddress.ip_address(value["peer_address"])
    host.controlled_directory(value["tls_root"])
    if not isinstance(value["containers"],dict) or set(value["containers"])!={"db","api","nginx"}:raise ValueError()
    names=[]
    for item in value["containers"].values():
        if (not isinstance(item,dict) or set(item)!={"name","image"}
                or not isinstance(item["name"],str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}",item["name"])
                or not isinstance(item["image"],str) or not re.fullmatch(r"sha256:[0-9a-f]{64}",item["image"])):raise ValueError()
        names.append(item["name"])
    if len(set(names))!=3:raise ValueError()
    return value


def inspect_container(binding,kind,host,until):
    item=binding["containers"][kind]
    template='{"id":{{json .Id}},"image":{{json .Image}},"state":{{json .State}},"mounts":{{json .Mounts}},"user":{{json .Config.User}},"readonly":{{json .HostConfig.ReadonlyRootfs}},"command":{{json .Config.Cmd}},"entrypoint":{{json .Config.Entrypoint}}}'
    code,value=host.command(["inspect","--format",template,item["name"]],seconds(until),json_output=True)
    if (code or value.get("image")!=item["image"] or not re.fullmatch(r"[0-9a-f]{64}",value.get("id", ""))
            or not isinstance(value.get("state"),dict) or not isinstance(value.get("mounts"),list)):raise ValueError("host_container_changed")
    expected={"db":["mariadbd"],"api":["uvicorn","app.main:app","--host","0.0.0.0","--port","8000",
        "--workers","1","--no-server-header","--no-access-log"],"nginx":["-g","daemon off;"]}
    if value.get("command")!=expected[kind]:raise ValueError("host_command_changed")
    if kind=="api" and (value.get("entrypoint") not in (None,[]) or value["user"]!="10001:10001" or value["readonly"] is not True):
        raise ValueError("host_api_binding_changed")
    if kind=="nginx":
        mounts=[mount for mount in value["mounts"] if mount.get("Destination")=="/etc/importer-tls"]
        if (value.get("entrypoint")!=["nginx"] or value["user"]!="10002:10002" or value["readonly"] is not True or len(mounts)!=1
                or mounts[0].get("RW") is not False or mounts[0].get("Source")!=binding["tls_root"]):raise ValueError("host_tls_binding_changed")
    return value


def peer(binding,origin,until,expected=None):
    parsed=urlsplit(origin)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(capath=CA_PATH)
    with socket.create_connection((binding["peer_address"],parsed.port or 443),timeout=seconds(until)) as plain:
        with context.wrap_socket(plain,server_hostname=parsed.hostname) as connection:
            fingerprint=hashlib.sha256(connection.getpeercert(binary_form=True)).hexdigest()
            if expected is not None and fingerprint!=expected:raise ValueError("tls_peer_changed")
            connection.settimeout(seconds(until))
            connection.sendall(("GET /api/health/ready HTTP/1.0\r\nHost: "+parsed.netloc+"\r\nConnection: close\r\n\r\n").encode("ascii"))
            data=bytearray()
            while True:
                connection.settimeout(seconds(until))
                chunk=connection.recv(min(4096,16385-len(data)))
                if not chunk:break
                data.extend(chunk)
                if len(data)>16384:raise ValueError("host_ready_invalid")
    header,body=bytes(data).split(b"\r\n\r\n",1)
    status=header.split(b"\r\n",1)[0].split()
    value=json.loads(body)
    if (len(status)<2 or status[1]!=b"200" or not isinstance(value,dict) or value.get("status")!="ready"
            or value.get("mode")!="journal" or value.get("instance_id")!=binding["instance_id"]):raise ValueError("host_ready_invalid")
    return fingerprint


def ready(binding,origin,host,until,*,notifications=False):
    for kind in (("db",) if notifications else ("db","api")):
        item=inspect_container(binding,kind,host,until)
        if not item["state"].get("Running") or item["state"].get("Health",{}).get("Status")!="healthy":raise ValueError("host_not_ready")
    if not notifications:
        item=inspect_container(binding,"nginx",host,until)
        if not item["state"].get("Running"):raise ValueError("host_not_ready")
        _,directory=current_release(binding["tls_root"],host)
        fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert((directory/"cert.pem").read_text(encoding="ascii"))).hexdigest()
        peer(binding,origin,until,fingerprint)


def gate(host):
    try:return host.protected(host.DRAIN_FILE).read_bytes()
    except FileNotFoundError:return None


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def drain(host,until):
    with host.host_lock(GATE_LOCK,wait=seconds(until,5)) as acquired:
        if not acquired:raise ValueError("host_gate_busy")
        parent=Path(host.DRAIN_FILE).parent;host.controlled_directory(parent)
        fd,name=tempfile.mkstemp(prefix=".drain-",dir=parent)
        try:
            with os.fdopen(fd,"wb") as output:
                output.write(uuid.uuid4().hex.encode("ascii"));output.flush();os.fsync(output.fileno())
            os.replace(name,host.DRAIN_FILE);sync_directory(parent)
        finally:
            if os.path.exists(name):os.unlink(name)
    with ExitStack() as stack:
        for path in (LIFECYCLE_LOCK,host.PROCESSING_LOCK,"/run/invoice-importer/notification.lock"):
            if not stack.enter_context(host.host_lock(path,wait=seconds(until,40))):raise ValueError("host_drain_busy")
        for label in ("invoice.processing.operation","invoice.notification.operation"):
            if host.command(["container","ls","-a","--filter","label="+label,"--format","{{.Names}}"],seconds(until)):
                raise ValueError("host_drain_unreconciled")
    return dict(ok=True,drained=True)


def start(binding,origin,host,until):
    with host.host_lock(LIFECYCLE_LOCK) as acquired:
        if not acquired:raise ValueError("host_lifecycle_busy")
        previous_gate=gate(host)
        for kind in ("db","api","nginx"):
            item=inspect_container(binding,kind,host,until)
            if not item["state"].get("Running"):host.command(["start",item["id"]],seconds(until,10))
            while True:
                current=inspect_container(binding,kind,host,until)
                if current["id"]!=item["id"]:raise ValueError("host_container_changed")
                if current["state"].get("Running") and (kind=="nginx" or current["state"].get("Health",{}).get("Status")=="healthy"):break
                time.sleep(seconds(until,1))
        ready(binding,origin,host,until)
        with host.host_lock(GATE_LOCK,wait=seconds(until,5)) as acquired:
            if not acquired:raise ValueError("host_gate_busy")
            if gate(host)==previous_gate and previous_gate is not None:
                os.unlink(host.DRAIN_FILE);sync_directory(Path(host.DRAIN_FILE).parent)
        return dict(ok=True,ready=True,draining=host.draining())


def openssl(args,until):
    # Fixed commands only. Private output goes to protected -out files, never
    # stdout/stderr or a returned result. The capture contains public metadata.
    with tempfile.TemporaryFile() as output:
        subprocess.run([OPENSSL,*map(str,args)],stdin=subprocess.DEVNULL,stdout=output,
            stderr=subprocess.DEVNULL,env=ENV,timeout=seconds(until)-.1,check=True)
        if output.tell()>65536:raise ValueError("tls_output_limit")
        output.seek(0);return output.read()


def certificate(path,until):
    output=openssl(["x509","-in",path,"-noout","-startdate","-enddate","-fingerprint","-sha256","-subject","-issuer","-nameopt","RFC2253"],until).decode("ascii")
    fields=dict(line.split("=",1) for line in output.splitlines())
    fingerprint=fields["sha256 Fingerprint"].replace(":","").lower()
    if not re.fullmatch(r"[0-9a-f]{64}",fingerprint):raise ValueError("tls_certificate_invalid")
    return dict(fingerprint=fingerprint,not_before=int(ssl.cert_time_to_seconds(fields["notBefore"])),
        expires=int(ssl.cert_time_to_seconds(fields["notAfter"])),subject=fields["subject"],issuer=fields["issuer"])


class SourceChanged(RuntimeError):pass


class Source:
    def __init__(self,value,host):self.value=value;self.host=host;self.fd=None
    def __enter__(self):
        self.fd=self.host.open_directory(self.value["source_root"])
        try:self.identity=self.host.mount_identity(self.fd,self.value["expected_source"],readonly=True)
        except BaseException:os.close(self.fd);self.fd=None;raise
        return self
    def __exit__(self,*_):
        if self.fd is not None:os.close(self.fd)
    def check(self):
        current=self.host.open_directory(self.value["source_root"])
        try:
            if (self.host.mount_identity(current,self.value["expected_source"],readonly=True)!=self.identity
                    or self.host.mount_identity(self.fd,self.value["expected_source"],readonly=True)!=self.identity):raise SourceChanged("tls_source_changed")
        finally:os.close(current)
    def names(self):
        names=[name for name in os.listdir(self.fd) if name.lower().endswith(".pfx")]
        if not 1<=len(names)<=32 or any(not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}\.pfx",name) for name in names):raise ValueError("tls_source_invalid")
        return sorted(names)
    def read(self,name):
        self.check()
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=self.fd)
        with os.fdopen(fd,"rb") as source:
            before=os.fstat(source.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid!=0 or before.st_mode & 0o027
                    or not 1<=before.st_size<=1048576):raise ValueError("tls_source_invalid")
            first=source.read(1048577);source.seek(0);second=source.read(1048577)
            after=os.fstat(source.fileno())
            identity=lambda info:(info.st_dev,info.st_ino,info.st_mtime_ns,info.st_ctime_ns,info.st_size)
            if len(first)!=before.st_size or first!=second or identity(before)!=identity(after):raise SourceChanged("tls_source_changed")
        self.check()
        return first,hashlib.sha256(first).hexdigest(),identity(before)


def tls_profile(path,host):
    value=json.loads(host.protected(path).read_text(encoding="utf-8"))
    if (not isinstance(value,dict) or set(value)!={"source_root","expected_source","password_file","legacy_rc2"}
            or not isinstance(value["expected_source"],str) or not value["expected_source"].startswith("//")
            or type(value["legacy_rc2"]) is not bool or not Path(value["source_root"]).is_absolute()):raise ValueError()
    host.protected(value["password_file"])
    return value


def current_release(root,host):
    link=Path(root)/"current"
    target=os.readlink(link)
    if not re.fullmatch(r"releases/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}",target):raise ValueError("tls_current_invalid")
    directory=Path(root)/target;host.controlled_directory(directory)
    for name in ("cert.pem","chain.pem","fullchain.pem","privkey.pem"):
        info=host.protected(directory/name).stat()
        if info.st_gid!=10002 or stat.S_IMODE(info.st_mode)!=0o440:raise ValueError("tls_current_permissions_invalid")
    return target,directory


def candidate(snapshot,directory,password,legacy,hostname,until):
    directory.mkdir(mode=0o700)
    source=directory/"source.pfx";source.write_bytes(snapshot)
    passfile=directory/"password";passfile.write_bytes(password.rstrip(b"\r\n")+b"\n")
    prefix=["pkcs12","-in",source,"-passin","file:"+str(passfile)] + (["-legacy"] if legacy else [])
    openssl([*prefix,"-nokeys","-out",directory/"certificates.raw"],until)
    openssl([*prefix,"-nocerts","-noenc","-out",directory/"private.raw"],until)
    private=(directory/"private.raw").read_bytes()
    if len(re.findall(rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",private))!=1:raise ValueError("tls_key_invalid")
    openssl(["pkey","-in",directory/"private.raw","-check","-out",directory/"privkey.pem"],until)
    key_public=openssl(["pkey","-in",directory/"privkey.pem","-pubout"],until).strip()
    blocks=CERTIFICATE.findall((directory/"certificates.raw").read_bytes())
    if not 2<=len(blocks)<=8 or len(set(blocks))!=len(blocks):raise ValueError("tls_chain_invalid")
    certs=[];leaf=None
    for index,block in enumerate(blocks):
        path=directory/("cert-"+str(index)+".pem");path.write_bytes(block)
        info=certificate(path,until)
        if openssl(["x509","-in",path,"-pubkey","-noout"],until).strip()==key_public:
            if leaf is not None:raise ValueError("tls_key_ambiguous")
            leaf=(path,info)
        else:certs.append((path,info))
    if leaf is None:raise ValueError("tls_key_mismatch")
    chain=[];issuer=leaf[1]["issuer"]
    while certs:
        matches=[item for item in certs if item[1]["subject"]==issuer]
        if len(matches)!=1:raise ValueError("tls_chain_invalid")
        item=matches[0];certs.remove(item);chain.append(item[0]);issuer=item[1]["issuer"]
    shutil.copyfile(leaf[0],directory/"cert.pem")
    (directory/"chain.pem").write_bytes(b"".join(path.read_bytes() for path in chain))
    (directory/"fullchain.pem").write_bytes((directory/"cert.pem").read_bytes()+(directory/"chain.pem").read_bytes())
    openssl(["verify","-CApath",CA_PATH,"-purpose","sslserver","-verify_hostname",hostname,
        "-untrusted",directory/"chain.pem",directory/"cert.pem"],until)
    if leaf[1]["not_before"]>int(time.time()) or leaf[1]["expires"]<=int(time.time())+3600:raise ValueError("tls_validity_invalid")
    return dict(leaf[1],directory=directory)


def switch(root,previous,target):
    if os.readlink(Path(root)/"current")!=previous:raise ValueError("tls_current_changed")
    name=Path(root)/(".current-"+uuid.uuid4().hex)
    try:
        os.symlink(target,name);os.replace(name,Path(root)/"current");sync_directory(root)
    finally:
        if name.is_symlink():name.unlink()


def tls_pending(root):return Path(root)/".tls-pending.json"


def clear_tls_pending(root):
    tls_pending(root).unlink();sync_directory(root)


def adopt(binding,origin,host,until,old,target,expected,nginx):
    # Always use the inspected immutable container ID for -t and reload.
    root=binding["tls_root"]
    with tls_pending(root).open("x",encoding="ascii") as output:
        os.chmod(output.name,0o600)
        json.dump(dict(previous=old[0],previous_fingerprint=old[1],target=target,
            fingerprint=expected,container=nginx),output,separators=(",",":"))
        output.flush();os.fsync(output.fileno())
    sync_directory(root)
    reload_attempted=False
    try:
        switch(binding["tls_root"],old[0],target)
        host.command(["exec",nginx,"nginx","-t"],seconds(until))
        reload_attempted=True
        host.command(["exec",nginx,"nginx","-s","reload"],seconds(until))
        peer(binding,origin,until,expected)
        clear_tls_pending(root)
        return dict(ok=True,changed=True,fingerprint=expected)
    except BaseException as error:
        current=os.readlink(Path(binding["tls_root"])/"current")
        if current==target:
            try:
                # Rollback owns the 45-second reserve excluded from forward work.
                rollback=until+45
                switch(binding["tls_root"],target,old[0])
                host.command(["exec",nginx,"nginx","-t"],seconds(rollback))
                if reload_attempted:
                    host.command(["exec",nginx,"nginx","-s","reload"],seconds(rollback))
                peer(binding,origin,rollback,old[1])
                clear_tls_pending(root)
            except BaseException:raise RuntimeError("tls_rollback_unconfirmed") from None
        elif current==old[0]:clear_tls_pending(root)
        else:raise RuntimeError("tls_rollback_unconfirmed") from None
        raise error


def tls(binding,origin,path,host,until):
    with host.host_lock(LIFECYCLE_LOCK) as acquired:
        if not acquired:return dict(ok=True,deferred=True,code="tls_host_busy")
        if host.draining():return dict(ok=True,deferred=True,code="tls_draining")
        work=until-45
        nginx=inspect_container(binding,"nginx",host,work)
        if not nginx["state"].get("Running"):raise ValueError("host_not_ready")
        root=Path(binding["tls_root"]);host.controlled_directory(root/"releases")
        try:host.protected(tls_pending(root))
        except FileNotFoundError:pass
        else:raise RuntimeError("tls_prior_operation_unreconciled")
        old_target,old_directory=current_release(root,host)
        old=certificate(old_directory/"cert.pem",work)
        value=tls_profile(path,host)
        password=host.protected(value["password_file"]).read_bytes()
        if len(password)>1024 or b"\0" in password or b"\n" in password.rstrip(b"\r\n"):raise ValueError("tls_password_file_invalid")
        with Source(value,host) as source,tempfile.TemporaryDirectory(prefix=".tls-stage-",dir=root) as working:
            chosen=None
            for index,name in enumerate(source.names()):
                snapshot,digest,identity=source.read(name)
                try:item=candidate(snapshot,Path(working)/str(index),password,value["legacy_rc2"],urlsplit(origin).hostname,work)
                except (ValueError,KeyError,subprocess.SubprocessError):continue
                if chosen is None or (item["not_before"],item["expires"],item["fingerprint"])>(chosen["not_before"],chosen["expires"],chosen["fingerprint"]):
                    chosen=dict(item,source_name=name,source_hash=digest,source_identity=identity)
            if chosen is None:raise ValueError("tls_no_valid_candidate")
            if chosen["fingerprint"]==old["fingerprint"] or (chosen["not_before"]<=old["not_before"] or chosen["expires"]<old["expires"]):
                peer(binding,origin,work,old["fingerprint"])
                return dict(ok=True,changed=False,fingerprint=old["fingerprint"])
            _,digest,identity=source.read(chosen["source_name"])
            if digest!=chosen["source_hash"] or identity!=chosen["source_identity"]:raise SourceChanged("tls_source_changed")
            release=root/"releases"/("auto-"+uuid.uuid4().hex)
            release.mkdir(mode=0o700)
            for name in ("cert.pem","chain.pem","fullchain.pem","privkey.pem"):
                target=release/name
                with target.open("xb") as output:
                    output.write((chosen["directory"]/name).read_bytes());output.flush();os.fsync(output.fileno())
                os.chown(target,0,10002);os.chmod(target,0o440)
            os.chown(release,0,10002);os.chmod(release,0o750)
            sync_directory(release);sync_directory(release.parent)
            source.check()
            if inspect_container(binding,"nginx",host,work)["id"]!=nginx["id"]:raise ValueError("host_container_changed")
            result=adopt(binding,origin,host,work,(old_target,old["fingerprint"]),"releases/"+release.name,chosen["fingerprint"],nginx["id"])
            return dict(result,source_sha256=chosen["source_hash"])
