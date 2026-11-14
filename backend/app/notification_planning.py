"""Pure observed incidents and coalesced slots; no scheduler, network or mail scan."""
import re
from app.notification_model import NotificationError, Slot, identity

def observe_incident(previous, *, now, failed, code=None):
    if (type(now) is not int or type(failed) is not bool or
            failed and (not isinstance(code,str) or not re.fullmatch(r"[a-z0-9_]{1,64}",code))):
        raise NotificationError("notification_observation_invalid",422)
    before = previous or dict(episode=0,active=False,first_seen=None,last_seen=now,
        last_failure=None,resolved_at=None,last_reserved_at=None,code=None,failures=0)
    result = dict(before,last_seen=now)
    if failed:
        if not before["active"] or before["code"] != code:
            result.update(episode=before["episode"]+1,first_seen=now,last_reserved_at=None,failures=0)
        result.update(active=True,code=code,last_failure=now,resolved_at=None,failures=result["failures"]+1)
    elif before["active"]:
        result.update(active=False,resolved_at=now)
    return result

def outage_slot(token, observation, config, now):
    first = observation["first_seen"]
    if first is None or observation["last_failure"] - first < config["outage_after_minutes"]*60:
        return None
    period = config["outage_repeat_hours"]*3600
    tag = identity([token,observation["episode"]])
    if observation["active"]:
        # Cached old failures are a stale status, not a fresh availability claim.
        if now-observation["last_seen"] > 300:
            return None
        last = observation["last_reserved_at"]
        if last is not None and now < last+period:
            return None
        due = first+config["outage_after_minutes"]*60
        cycle = max(0,(now-due)//period)
        return Slot("outage",first+cycle*period,first+(cycle+1)*period,
            due+cycle*period,due+(cycle+1)*period,tag)
    resolved = observation["resolved_at"]
    if resolved is None or now >= resolved+period:
        return None
    return Slot("recovery",first,resolved+1,resolved,resolved+period,tag)

def error_bundle(observations, config, now):
    eligible = []
    for row in observations:
        value = row["data"]
        if (value["active"] and now-value["first_seen"] >= config["error_bundle_minutes"]*60
                and (value["last_reserved_at"] is None or now-value["last_reserved_at"] >= config["error_repeat_hours"]*3600)):
            eligible.append(row)
    eligible.sort(key=lambda row:(row["data"]["first_seen"],row["monitor_key"]))
    selected = eligible[:100]
    if not selected:
        return None
    start = now//3600*3600
    slot = Slot("errors",start,start+3600,start,start+3600)
    data = dict(source="processing",first_seen=min(row["data"]["first_seen"] for row in selected),
        last_seen=max(row["data"]["last_seen"] for row in selected),count=len(selected),
        codes=sorted({row["data"]["code"] for row in selected})[:10])
    return slot,data,[row["monitor_key"] for row in selected]
