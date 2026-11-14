"""Pure observed incidents and coalesced slots; no scheduler, network or mail scan."""
import re
from dataclasses import dataclass
from app.notification_model import NotificationError, Slot, checked_key, identity

INCIDENT_FIELDS = ("episode","first_seen","last_seen","last_failure","code","resolved_at")

@dataclass(frozen=True,kw_only=True)
class IncidentSlot(Slot):
    """Original observed episode travels with its slot, never filled from a later read."""
    token: str
    episode: int
    first_seen: int
    last_seen: int
    last_failure: int
    code: str
    resolved_at: int | None

    def __post_init__(self):
        super().__post_init__()
        checked_key(self.token)
        if (self.kind not in {"outage","recovery"} or type(self.episode) is not int or self.episode < 1
                or any(type(value) is not int for value in (self.first_seen,self.last_seen,self.last_failure))
                or not self.first_seen <= self.last_failure <= self.last_seen
                or not isinstance(self.code,str) or not re.fullmatch(r"[a-z0-9_]{1,64}",self.code)
                or self.tag != identity([self.token,self.episode])
                or (self.resolved_at is not None if self.kind == "outage" else
                    type(self.resolved_at) is not int or not self.last_failure <= self.resolved_at <= self.last_seen)):
            raise NotificationError("notification_incident_plan_invalid",422)

    def observation(self):
        return dict({name:getattr(self,name) for name in INCIDENT_FIELDS},
            active=self.kind == "outage",last_reserved_at=None)

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
    snapshot = dict(token=token,**{name:observation[name] for name in INCIDENT_FIELDS})
    if observation["active"]:
        # Cached old failures are a stale status, not a fresh availability claim.
        if not 0 <= now-observation["last_seen"] <= 300:
            return None
        last = observation["last_reserved_at"]
        if last is not None and now < last+period:
            return None
        due = first+config["outage_after_minutes"]*60
        cycle = max(0,(now-due)//period)
        return IncidentSlot("outage",first+cycle*period,first+(cycle+1)*period,
            due+cycle*period,due+(cycle+1)*period,tag,**snapshot)
    resolved = observation["resolved_at"]
    if resolved is None or now >= resolved+period:
        return None
    return IncidentSlot("recovery",first,resolved+1,resolved,resolved+period,tag,**snapshot)

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
