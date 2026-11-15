"""Bounded manual observation of actual journal errors and API/Graph availability."""
import json
import re
import httpx
import sqlalchemy as sa
from app.graph import GraphError
from app.graph_deadline import request_deadline
from app.notification_model import NotificationError,identity
from app.notification_planning import observe_incident,outage_slot,error_bundle
from app.notification_schema007 import monitor,outbox
from app.process_queries import ProcessQueries
from app.processing_state import messages,attachments
from app.storage_plan import digest

def neutral_code(value):
    return value if isinstance(value,str) and re.fullmatch(r"[a-z0-9_]{1,64}",value) else "processing_failure"

def record_incident(store,scope,token,*,source,failed,code=None,reference=None):
    # Retry only a known rejected CAS, never an uncertain committed write.
    for attempt in range(3):
        previous=store.monitor_state(scope,"incident",token)
        value=observe_incident(previous["data"] if previous else None,now=int(store.clock()),failed=failed,code=code)
        value.update(source=source,token=token,reference=reference)
        try:return store.put_monitor(scope,"incident",token,value,expected_revision=previous["revision"] if previous else 0)
        except NotificationError as error:
            if error.code != "notification_monitor_changed" or attempt==2:raise

def probe_api(instance,budget,*,client_factory=httpx.Client):
    seconds=min(5,budget.remaining())
    if seconds <= 0:raise NotificationError("notification_deadline",504)
    try:
        with request_deadline(seconds),client_factory(timeout=seconds,trust_env=False,follow_redirects=False) as http:
            with http.stream("GET","http://api:8000/api/health/ready") as response:
                if response.status_code != 200:return False,"notification_api_unavailable"
                raw=bytearray()
                for chunk in response.iter_bytes(1024):
                    raw.extend(chunk)
                    if len(raw)>4096:return False,"notification_api_unavailable"
                value=json.loads(raw)
                if not isinstance(value,dict) or value.get("status") != "ready" or value.get("instance_id") != instance:
                    return False,"notification_api_identity"
        return True,None
    except (httpx.HTTPError,GraphError,ValueError):
        return False,"notification_api_unavailable"

def journal_errors(store,scope,mailbox):
    """Newest bounded errors plus oldest tracked causes for reconciliation.

    Unselected old causes are checked by their exact reference; a scan limit can
    never turn an unseen failure into a recovery. No imports/jobs are inferred.
    """
    mailbox_key=digest([mailbox.lower()]);current={};resolved=[];message_rows=[];attachment_codes={}
    def reference(kind,row,message_revision):
        code=row["error_code"]
        if not code and kind=="attachment":
            finding=json.loads(row["effective_finding"]) if row["effective_finding"] else {}
            code=finding.get("reason")
        return dict(table=kind,key=row[kind+"_key"],revision=message_revision,
            finding_revision=row.get("finding_revision"),code=neutral_code(code))
    with ProcessQueries(store.engine).snapshot() as c:
        rows=c.execute(sa.select(messages).where(messages.c.mailbox_key==mailbox_key,
            messages.c.state.in_(("failed","operator_required"))).order_by(messages.c.updated_at.desc(),messages.c.message_key).limit(100)).mappings()
        message_rows=list(rows)
        rows=c.execute(sa.select(attachments,messages.c.revision.label("message_revision")).join(messages,
            attachments.c.message_key==messages.c.message_key).where(messages.c.mailbox_key==mailbox_key,
                sa.or_(attachments.c.effective_status=="failed",attachments.c.storage_state.in_(("failed","operator_required"))))
            .order_by(messages.c.updated_at.desc(),attachments.c.attachment_key).limit(100)).mappings()
        for row in rows:
            ref=reference("attachment",row,row["message_revision"]);current[identity(["processing",ref])]=ref
            attachment_codes.setdefault(row["message_key"],set()).add(ref["code"])
        for row in message_rows:
            ref=reference("message",row,row["revision"])
            if row["message_key"] in attachment_codes and (not row["error_code"] or ref["code"] in attachment_codes[row["message_key"]]):continue
            current[identity(["processing",ref])]=ref
        watched=c.execute(sa.select(monitor.c.payload).where(monitor.c.scope_key==scope,monitor.c.kind=="incident",
            monitor.c.payload.like('%"source":"processing"%'),monitor.c.payload.like('%"active":true%'))
            .order_by(monitor.c.updated_at,monitor.c.monitor_key).limit(100)).scalars()
        for raw in watched:
            value=json.loads(raw);ref=value.get("reference");token=value.get("token")
            if not isinstance(ref,dict) or not token:continue
            if token in current:continue
            if ref["table"]=="message":
                row=c.execute(sa.select(messages).where(messages.c.message_key==ref["key"],messages.c.mailbox_key==mailbox_key)).mappings().first()
                active=row and row["state"] in {"failed","operator_required"} and reference("message",row,row["revision"])==ref
            else:
                row=c.execute(sa.select(attachments,messages.c.revision.label("message_revision")).join(messages,
                    attachments.c.message_key==messages.c.message_key).where(attachments.c.attachment_key==ref["key"],messages.c.mailbox_key==mailbox_key)).mappings().first()
                active=row and (row["effective_status"]=="failed" or row["storage_state"] in {"failed","operator_required"}) and reference("attachment",row,row["message_revision"])==ref
            if active:current[token]=ref
            else:resolved.append((token,ref))
    return current,resolved

def retire_closed_plans(store,scope):
    """A closed/replaced cause cannot leave an old unreserved head blocking dispatch."""
    with store.transaction() as c:
        store._scope(store._head(c),scope)
        rows=list(c.execute(sa.select(outbox).where(outbox.c.scope_key==scope,outbox.c.kind.in_(("errors","outage","recovery")),
            outbox.c.state=="prepared",outbox.c.reservations==0).order_by(outbox.c.created_at).limit(200).with_for_update()).mappings())
        bindings=[(row,json.loads(row["monitor_keys"])) for row in rows]
        keys={member["key"] for _,members in bindings for member in members if isinstance(member,dict) and "key" in member}
        sources={key:json.loads(raw) for key,raw in c.execute(sa.select(monitor.c.monitor_key,monitor.c.payload).where(
            monitor.c.monitor_key.in_(keys),monitor.c.scope_key==scope,monitor.c.kind=="incident").with_for_update())} if keys else {}
        for row,members in bindings:
            stale=not members
            for member in members:
                if not isinstance(member,dict):stale=True;continue
                value=sources.get(member.get("key"),{})
                fields=("episode","first_seen","code") if row["kind"]=="errors" else ("episode","first_seen","code","resolved_at")
                if (not value or any(value.get(name)!=member.get(name) for name in fields)
                        or value.get("active") is not (row["kind"]!="recovery")):stale=True
            if stale:
                c.execute(outbox.update().where(outbox.c.slot_key==row["slot_key"],outbox.c.reservations==0).values(
                    state="obsolete",error_code="notification_monitor_changed",owner=None,lease_until=0,updated_at=int(store.clock())))

def eligible_errors(store,scope,config,now):
    first=sa.cast(sa.func.json_extract(monitor.c.payload,"$.first_seen"),sa.BigInteger)
    last=sa.cast(sa.func.json_extract(monitor.c.payload,"$.last_reserved_at"),sa.BigInteger)
    with ProcessQueries(store.engine).snapshot() as c:
        rows=c.execute(sa.select(monitor).where(monitor.c.scope_key==scope,monitor.c.kind=="incident",
            monitor.c.payload.like('%"source":"processing"%'),monitor.c.payload.like('%"active":true%'),
            first<=now-config["error_bundle_minutes"]*60,sa.func.coalesce(last,0)<=now-config["error_repeat_hours"]*3600)
            .order_by(first,monitor.c.monitor_key).limit(100)).mappings()
        return [dict(monitor_key=row["monitor_key"],data=json.loads(row["payload"])) for row in rows]

def observe_and_plan(service,*,budget,api_probe=probe_api):
    """One explicit CLI plan cycle, no permanent worker and no send here."""
    store,scope=service.store,service.scope
    graph=service.observe(probe=True,budget=budget)
    graph_code=graph.get("probe_code") or ("notification_certificate_unavailable" if service.material is None else None)
    if graph_code != "notification_transport_deferred":
        record_incident(store,scope,identity(["availability","graph"]),source="graph",failed=graph_code is not None,code=graph_code)
    ready,code=api_probe(store.instance,budget)
    record_incident(store,scope,identity(["availability","api"]),source="api",failed=not ready,code=code)
    errors,resolved=journal_errors(store,scope,service.config.mailbox)
    for failed,values in ((True,errors.items()),(False,resolved)):
        for token,ref in values:
            if budget.remaining() <= 3:raise NotificationError("notification_deadline",504)
            record_incident(store,scope,token,source="processing",failed=failed,code=ref["code"] if failed else None,reference=ref)
    retire_closed_plans(store,scope)
    configuration=store.configuration();config=configuration["settings"];now=int(store.clock())
    plans=[]
    for source in ("api","graph"):
        token=identity(["availability",source]);observed=store.monitor_state(scope,"incident",token)
        if not observed:continue
        slot=outage_slot(token,observed["data"],config,now)
        if slot:
            facts=dict(source=source,first_seen=slot.first_seen,last_seen=slot.last_seen,count=1,codes=[slot.code])
            row=store.prepare(slot,scope,facts,expected_version=configuration["version"],as_of=now,
                origin=service.origin,members=[observed["monitor_key"]])
            if row:plans.append(row)
    bundled=error_bundle(eligible_errors(store,scope,config,now),config,now)
    if bundled:
        slot,facts,members=bundled
        row=store.prepare(slot,scope,facts,expected_version=configuration["version"],as_of=now,origin=service.origin,members=members)
        if row:plans.append(row)
    return plans
