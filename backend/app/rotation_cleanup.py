"""One durable removal permission for an inventoried, inactive predecessor key."""
from app.graph import GraphError
from app.notification_model import graph_scope
from app.rotation_model import records_hash,sha,uuid

OVERLAP_SECONDS=7*86400
PHASES={"planned","removal_started","removal_unknown","remote_absent","unmanaged_retained","completed"}
FIELDS={"version","operation_id","scope_key","source_commit","deployment_id","instance_id","old","new",
    "adoption_seal","overlap_started_at","not_before","owned","successor_key_id","phase","revision","baseline",
    "proof","error_code"}


class CleanupJournal:
    def __init__(self,adoption):
        self.adoption=adoption;self.root=adoption.root

    def state(self,operation):
        value=self.root._read(uuid(operation)+".cleanup.json")
        if value is None:return None
        try:
            if (not isinstance(value,dict) or set(value)!=FIELDS or type(value["version"]) is not int or value["version"]!=1 or value["operation_id"]!=operation
                    or any(value[name]!=expected for name,expected in self.adoption.binding.fields().items())
                    or value["phase"] not in PHASES or type(value["revision"]) is not int or value["revision"]<0
                    or type(value["overlap_started_at"]) is not int or type(value["not_before"]) is not int
                    or value["not_before"]!=min(value["overlap_started_at"]+OVERLAP_SECONDS,value["old"]["expires_at"])):
                raise ValueError()
            sha(value["adoption_seal"]);uuid(value["successor_key_id"])
            for name in ("old","new"):
                if set(value[name])!={"fingerprint","pem_hash","expires_at"} or type(value[name]["expires_at"]) is not int:raise ValueError()
                sha(value[name]["fingerprint"]);sha(value[name]["pem_hash"])
            if value["old"]["fingerprint"]==value["new"]["fingerprint"]:raise ValueError()
            owned=value["owned"]
            if owned is not None:
                if set(owned)!={"key_id","fingerprint","operation_id","origin","evidence"} or owned["origin"] not in {"created","adopted"}:raise ValueError()
                uuid(owned["key_id"]);uuid(owned["operation_id"]);sha(owned["evidence"])
                if owned["fingerprint"]!=value["old"]["fingerprint"] or owned["key_id"]==value["successor_key_id"]:raise ValueError()
            if value["phase"] in {"removal_started","removal_unknown","remote_absent"}:
                if owned is None or value["baseline"] is None or value["proof"] is None:raise ValueError()
                records_hash(value["baseline"])
            return value
        except (KeyError,TypeError,ValueError,GraphError):raise GraphError("rotation_cleanup_invalid") from None

    def save(self,value,**changes):
        result=dict(value,**changes,revision=value["revision"]+1)
        self.root._write(value["operation_id"]+".cleanup.json",result)
        return result

    def plan(self,operation):
        previous=self.state(operation);host=self.adoption.state(operation);core=self.root.state(operation)
        if host is None or host["phase"]!="committed" or host["target"]!="new":raise GraphError("rotation_cleanup_unavailable")
        if previous is not None:
            if any(previous[name]!=host[name] for name in ("old","new")):raise GraphError("rotation_cleanup_changed")
            return previous
        matches=[dict(item,key_id=key) for key,item in self.root.inventory()["keys"].items()
            if item["fingerprint"]==host["old"]["fingerprint"]]
        if len(matches)>1:raise GraphError("rotation_cleanup_ownership_ambiguous")
        started=host["proof"]["probe"]["proof_at"]
        value=dict(version=1,operation_id=operation,**self.adoption.binding.fields(),old=host["old"],new=host["new"],
            adoption_seal=host["seal"],overlap_started_at=started,not_before=min(started+OVERLAP_SECONDS,host["old"]["expires_at"]),
            owned=matches[0] if matches else None,successor_key_id=core["registered_key_id"],phase="planned",revision=0,
            baseline=None,proof=None,error_code=None)
        self.root._write(operation+".cleanup.json",value)
        return self.state(operation)

    def current(self,operation,graph,material,proof,now):
        value=self.state(operation);host=self.adoption.state(operation)
        if (value is None or host is None or host["phase"]!="committed" or host["target"]!="new"
                or any(value[name]!=host[name] for name in ("old","new"))
                or material.fingerprint!=value["new"]["fingerprint"] or graph.signer.pem!=material.pem
                or graph.binding!=self.root.binding or not material.not_before<=now<material.expires_at):
            raise GraphError("rotation_cleanup_successor_changed")
        import hashlib
        if hashlib.sha256(material.pem).hexdigest()!=value["new"]["pem_hash"]:raise GraphError("rotation_cleanup_successor_changed")
        config=self.root.binding.config;scope=graph_scope(config.tenant_id,config.client_id,config.mailbox)
        if (not isinstance(proof,dict) or set(proof)!={"fingerprint","scope_key","at"}
                or proof["fingerprint"]!=material.fingerprint or proof["scope_key"]!=scope
                or type(proof["at"]) is not int or not 0<=now-proof["at"]<=60):raise GraphError("rotation_cleanup_proof_required")
        if value["owned"] is not None:
            owned=value["owned"];actual=self.root.inventory()["keys"].get(owned["key_id"])
            if actual!={key:item for key,item in owned.items() if key!="key_id"}:raise GraphError("rotation_cleanup_ownership_changed")
        return value

    def reconcile(self,value,records):
        key=value["owned"]["key_id"];remaining=[item for item in records if item["key_id"]!=key]
        target=[item for item in records if item["key_id"]==key]
        expected=[item for item in value["baseline"] if item["key_id"]!=key]
        if (target or records_hash(remaining)!=records_hash(expected)):
            return self.save(value,phase="removal_unknown",error_code="rotation_cleanup_unknown")
        return self.save(value,phase="remote_absent",error_code=None)

    def remove(self,operation,graph,material,proof,now):
        """Caller proves the current normal gate and fresh successor GET; no mail."""
        value=self.current(operation,graph,material,proof,now)
        if value["phase"] in {"remote_absent","unmanaged_retained","completed"}:return value
        if now<value["not_before"]:return value
        if value["owned"] is None:return self.save(value,phase="unmanaged_retained",error_code="rotation_old_key_unmanaged")
        records=graph.read()
        if value["phase"] in {"removal_started","removal_unknown"}:return self.reconcile(value,records)
        key=value["owned"]["key_id"]
        target=[item for item in records if item["key_id"]==key]
        successor=[item for item in records if item["key_id"]==value["successor_key_id"]]
        if (len(target)!=1 or target[0]["fingerprint"]!=value["old"]["fingerprint"]
                or target[0]["expires_at"]!=value["old"]["expires_at"] or len(successor)!=1
                or successor[0]["fingerprint"]!=material.fingerprint or successor[0]["expires_at"]!=material.expires_at):
            raise GraphError("rotation_cleanup_remote_changed")
        # The one send permission is durable before entering credential/transport code.
        value=self.save(value,phase="removal_started",baseline=records,proof=proof)
        try:graph.remove(key)
        except GraphError:
            return self.save(value,phase="removal_unknown",error_code="rotation_cleanup_unknown")
        value=self.save(value,phase="removal_unknown",error_code="rotation_cleanup_unknown")
        try:return self.reconcile(value,graph.read())
        except GraphError:return value
