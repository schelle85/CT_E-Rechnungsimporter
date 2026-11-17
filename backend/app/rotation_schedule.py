"""Root-private daily evidence and original automatic intent; no timer installation."""
from datetime import datetime,timedelta
import re
import time
from uuid import uuid4

from app.graph import GraphError
from app.graph_access_runtime import operation as graph_operation
from app.notification_certificate import certificate_client,record_certificate
from app.notification_model import BERLIN,NotificationError,graph_scope
from app.notification_state import NotificationStore
from app.rotation_cleanup import CleanupJournal
from app.rotation_model import sha,uuid

FIELDS={"version","scope_key","last_check","last_successful_daily_check_at","last_attempt","last_renewal"}


def due_slot(now):
    local=datetime.fromtimestamp(now,BERLIN);slot=local.replace(hour=3,minute=35,second=0,microsecond=0)
    if slot.timestamp()>now:slot-=timedelta(days=1)
    return int(slot.timestamp())


class ScheduleJournal:
    def __init__(self,root):self.root=root

    def state(self):
        value=self.root._read(".schedule.json")
        if value is None:return dict(version=1,scope_key=self.root.binding.scope,last_check=None,last_successful_daily_check_at=None,last_attempt=None,last_renewal=None)
        try:
            def stamp(v):
                if type(v) is not int or v<=0:raise ValueError()
            if set(value)!=FIELDS or type(value["version"]) is not int or value["version"]!=1 or value["scope_key"]!=self.root.binding.scope:raise ValueError()
            check=value["last_check"]
            if check is not None:
                if set(check)!={"slot","at","ok","code"} or type(check["ok"]) is not bool:raise ValueError()
                stamp(check["at"]);stamp(check["slot"])
                if check["slot"]!=due_slot(check["slot"]) or check["at"]<check["slot"]:raise ValueError()
                if check["code"] is not None and (not isinstance(check["code"],str) or not re.fullmatch("[a-z][a-z0-9_]{0,63}",check["code"])):raise ValueError()
            success=value["last_successful_daily_check_at"]
            if success is not None:
                stamp(success)
                if check is None or success>check["at"]:raise ValueError()
            for name,fields in (("last_attempt",{"operation_id","at"}),("last_renewal",{"operation_id","at","fingerprint"})):
                row=value[name]
                if row is not None:
                    if set(row)!=fields:raise ValueError()
                    uuid(row["operation_id"]);stamp(row["at"])
                    if name=="last_renewal":sha(row["fingerprint"])
            return value
        except (TypeError,KeyError,ValueError,GraphError):raise GraphError("rotation_schedule_invalid") from None

    def save(self,**changes):
        value=dict(self.state(),**changes);self.root._write(".schedule.json",value);return self.state()

    def attempt(self,operation,now):
        uuid(operation);previous=self.state()["last_attempt"]
        if previous and previous["operation_id"]==operation:return previous
        if previous and previous["at"]>now:raise GraphError("rotation_schedule_clock_changed")
        self.save(last_attempt=dict(operation_id=operation,at=now));return self.state()["last_attempt"]

    def renewed(self,operation,cleanup):
        if cleanup["operation_id"]!=operation:raise GraphError("rotation_schedule_invalid")
        value=dict(operation_id=uuid(operation),at=cleanup["overlap_started_at"],fingerprint=cleanup["new"]["fingerprint"])
        previous=self.state()["last_renewal"]
        if previous and previous["operation_id"]==operation:
            if previous!=value:raise GraphError("rotation_schedule_renewal_changed")
            return previous
        if previous and previous["at"]>=value["at"]:return previous
        return self.save(last_renewal=value)["last_renewal"]

    def automatic(self,store,current,now,*,create=False):
        """One immutable UUID per certificate generation, also after lost SQL commit response."""
        name=".automatic-"+sha(current.fingerprint)+".json";intent=self.root._read(name)
        if intent is not None:
            if (set(intent)!={"version","operation_id","scope_key","expected_revision","old_fingerprint"}
                    or type(intent["version"]) is not int or intent["version"]!=1 or intent["scope_key"]!=self.root.binding.scope
                    or intent["old_fingerprint"]!=current.fingerprint or type(intent["expected_revision"]) is not int or intent["expected_revision"]<0):
                raise GraphError("rotation_schedule_invalid")
            uuid(intent["operation_id"])
            # Replay reads the immutable original before current settings/revision checks.
            try:store.read(intent["operation_id"])
            except GraphError as error:
                if error.code!="rotation_not_found":raise
            else:
                return store.request(intent["operation_id"],"system",intent["expected_revision"],intent["old_fingerprint"],trigger="automatic")
        head=store.status()
        eligible=(head["enabled"] and head["active_operation"] is None and head["blocked_fingerprint"]!=current.fingerprint
            and current.not_before<=now and 3600<=current.expires_at-now<=30*86400)
        if not eligible:return None
        if intent is None:
            if not create:return None
            intent=dict(version=1,operation_id=str(uuid4()),scope_key=self.root.binding.scope,expected_revision=head["revision"],old_fingerprint=current.fingerprint)
            self.root._write(name,intent)  # fsync BEFORE the first SQL request.
        return store.request(intent["operation_id"],"system",intent["expected_revision"],intent["old_fingerprint"],trigger="automatic",
            validate_new=lambda:self.validate_new(current,int(time.time())))

    @staticmethod
    def validate_new(current,now):
        if not current.not_before<=now or not 3600<=current.expires_at-now<=30*86400:raise GraphError("rotation_automatic_window_closed")

    def check(self,store,access,current,deadline,read_monitor):
        from app.graph_access import AccessGate
        gate=AccessGate(access);release=gate.read();gate._bound(release);gate._material(release,current.pem,current.fingerprint)
        if release["mode"]!="allowed":return dict(ok=True,deferred="graph_paused")
        now=int(time.time());slot=due_slot(now);previous=self.state()["last_check"]
        if previous and previous["slot"]>=slot:
            if previous["slot"]>slot:raise GraphError("rotation_schedule_clock_changed")
            try:row=self.automatic(store,current,now)
            except GraphError:
                self.save(last_check=dict(previous,ok=False,code="rotation_automatic_request_unconfirmed"));row=None
            return dict(ok=True,due=False,operation_id=row["operation_id"] if row else None)
        # An interrupted check stays visible and is not blindly repeated every minute.
        self.save(last_check=dict(slot=slot,at=now,ok=False,code="rotation_check_interrupted"))
        try:
            if not current.not_before<=now<current.expires_at:raise GraphError("rotation_signer_expired")
            bound=self.root.binding;scope=graph_scope(bound.tenant_id,bound.client_id,bound.mailbox)
            until=min(deadline,time.monotonic()+40)
            with graph_operation(bound.config,current,expected_instance=bound.instance_id) as permit:
                observed=read_monitor();base=observed["revision"]
                with certificate_client(bound.config,current) as client:
                    client.deadline=until
                    if client.probe()!={"mailbox_access":"ok"}:raise GraphError("rotation_daily_probe_failed")
                    proof=dict(fingerprint=current.fingerprint,scope_key=scope,at=int(time.time()))
                permit.check(current.pem,current.fingerprint)
                notifications=NotificationStore(store.engine,None,bound.instance_id,clock=lambda:time.time())
                record_certificate(notifications,scope,current.metadata(int(time.time())),expected_revision=base,fresh_proof=proof)
                permit.check(current.pem,current.fingerprint)
                self.save(last_check=dict(slot=slot,at=proof["at"],ok=True,code=None),last_successful_daily_check_at=proof["at"])
                row=self.automatic(store,current,int(time.time()),create=True)
            return dict(ok=True,due=True,operation_id=row["operation_id"] if row else None)
        except (GraphError,NotificationError):
            # No raw Graph/SDK detail is published. A fresh proof, if committed, remains a separate fact.
            self.save(last_check=dict(slot=slot,at=int(time.time()),ok=False,code="rotation_daily_check_failed"))
            return dict(ok=True,due=True,check_failed=True)


def overview(store,host,access,current):
    """Project whitelisted public facts without giving the API any Root journal access."""
    from app.graph_access import AccessGate
    gate=AccessGate(access);release=gate.read();head=store.status();schedule=ScheduleJournal(host.root).state()
    if any(release.get(name)!=expected for name,expected in access.fields().items()):raise GraphError("rotation_release_invalid")
    active=head["active_operation"];operation=active or release["operation_id"]
    state=host.state(operation);cleanup=CleanupJournal(host).state(operation) if state else None
    public=None
    if state:
        public=dict(operation_id=operation,phase=state["phase"],target=state["target"],
            **{name:{key:state[name][key] for key in ("fingerprint","expires_at")} for name in ("old","new")},
            cleanup_phase=cleanup["phase"] if cleanup else None,cleanup_not_before=cleanup["not_before"] if cleanup else None,
            managed_old=cleanup["owned"] is not None if cleanup else None)
    attempt=schedule["last_attempt"]
    if attempt:
        row=store.read(attempt["operation_id"]);attempt=dict(attempt,state=row["state"],code=row["error_code"])
    renewal=schedule["last_renewal"]
    if renewal:
        proven=CleanupJournal(host).state(renewal["operation_id"])
        if proven is None or proven["overlap_started_at"]!=renewal["at"] or proven["new"]["fingerprint"]!=renewal["fingerprint"]:
            raise GraphError("rotation_schedule_renewal_changed")
    check=schedule["last_check"]
    return dict(ok=True,binding=access.fields(),last_check={key:check[key] for key in ("at","ok","code")} if check else None,
        last_successful_daily_check_at=schedule["last_successful_daily_check_at"],last_attempt=attempt,last_renewal=renewal,operation=public)
