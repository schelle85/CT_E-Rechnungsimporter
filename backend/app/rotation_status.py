"""Read-only public Root projection; never expose its journal or infer a live timer."""
import json
import re

from app.graph import GraphError,protected_bytes
from app.graph_access import boot_id,GraphAccessError
from app.rotation_model import sha,uuid,unique_json,PHASES

PATH="/run/importer/operations/graph-access/rotation-status.json"
FIELDS={"schema_version","source_commit","deployment_id","instance_id","scope_key","boot_id","observed_at",
    "last_check","last_successful_daily_check_at","last_attempt","last_renewal","operation","timers","check_due_at","check_overdue"}


def validate(value,binding,now):
    def stamp(item):
        if type(item) is not int or not 0<item<=value["observed_at"]:raise ValueError()
    def code(item):
        if item is not None and (not isinstance(item,str) or not re.fullmatch("[a-z][a-z0-9_]{0,63}",item)):raise ValueError()
    if (not isinstance(value,dict) or set(value)!=FIELDS or type(value["schema_version"]) is not int or value["schema_version"]!=1
            or any(value[name]!=expected for name,expected in binding.fields().items()) or value["boot_id"]!=boot_id()
            or type(value["observed_at"]) is not int or not 0<=now-value["observed_at"]<=180):raise ValueError()
    check=value["last_check"]
    if check is not None:
        if set(check)!={"at","ok","code"} or type(check["ok"]) is not bool:raise ValueError()
        stamp(check["at"]);code(check["code"])
    success=value["last_successful_daily_check_at"]
    if success is not None:
        stamp(success)
        if check is None or success>check["at"]:raise ValueError()
    from app.rotation_schedule import due_slot
    due=due_slot(value["observed_at"])
    if (type(value["check_due_at"]) is not int or value["check_due_at"]!=due or type(value["check_overdue"]) is not bool
            or value["check_overdue"]!=(value["observed_at"]>=due+7200 and (check is None or check["at"]<due))):raise ValueError()
    attempt=value["last_attempt"]
    if attempt is not None:
        if set(attempt)!={"operation_id","at","state","code"} or attempt["state"] not in PHASES:raise ValueError()
        uuid(attempt["operation_id"]);stamp(attempt["at"]);code(attempt["code"])
    renewal=value["last_renewal"]
    if renewal is not None:
        if set(renewal)!={"operation_id","at","fingerprint"}:raise ValueError()
        uuid(renewal["operation_id"]);stamp(renewal["at"]);sha(renewal["fingerprint"])
    operation=value["operation"]
    if operation is not None:
        from app.rotation_adoption import PHASES as HOST_PHASES
        from app.rotation_cleanup import PHASES as CLEANUP_PHASES
        if (set(operation)!={"operation_id","phase","target","old","new","cleanup_phase","cleanup_not_before","managed_old"}
                or operation["phase"] not in HOST_PHASES or operation["target"] not in {"old","new"}
                or operation["cleanup_phase"] is not None and operation["cleanup_phase"] not in CLEANUP_PHASES
                or operation["managed_old"] is not None and type(operation["managed_old"]) is not bool):raise ValueError()
        uuid(operation["operation_id"])
        for name in ("old","new"):
            if set(operation[name])!={"fingerprint","expires_at"} or type(operation[name]["expires_at"]) is not int:raise ValueError()
            sha(operation[name]["fingerprint"])
        if operation["cleanup_not_before"] is not None and (type(operation["cleanup_not_before"]) is not int or operation["cleanup_not_before"]<=0):raise ValueError()
    timers=value["timers"]
    if set(timers)!={"daily","opportunity","next_check_at"} or any(type(timers[name]) is not bool for name in ("daily","opportunity")):raise ValueError()
    if timers["next_check_at"] is not None and (not timers["daily"] or type(timers["next_check_at"]) is not int
            or not value["observed_at"]<timers["next_check_at"]<=value["observed_at"]+172800):raise ValueError()
    return value


def read(binding,now):
    try:
        value=json.loads(protected_bytes(PATH),object_pairs_hook=unique_json)
        validate(value,binding,now)
        return dict(available=True,**value)
    except (OSError,ValueError,TypeError,KeyError,GraphError,GraphAccessError):
        return dict(available=False,code="rotation_status_unconfirmed")
