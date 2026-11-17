"""Private handover checkpoints in the existing RootJournal, never an API mount."""
import hashlib
import os
import re

from app.graph import GraphError,protected_bytes
from app.graph_access import boot_id
from app.notification_certificate import CertificateMaterial
from app.notification_model import graph_scope,identity
from app.rotation_journal import sync_directory
from app.rotation_model import sha,uuid

ROLES={"api","processing","notifications"}
PHASES={"prepared","activation_started","activated","consumers_verified","proof_started",
    "proof_unknown","proof_verified","committed","rollback_unknown"}
FIELDS={"version","operation_id","scope_key","source_commit","deployment_id","instance_id","boot_id",
    "old","new","images","paused","drain_identity","target","phase","revision","consumers","proof_intent",
    "proof","seal","started_at"}
PROBE_FIELDS={"ok","code","source_commit","deployment_id","instance_id","scope_key","operation_id","epoch",
    "purpose","consumer_role","consumer_id","pem_hash","fingerprint","at","proof_revision","proof_at","receipt_hash"}


def image(value):
    if not isinstance(value,str) or not re.fullmatch("sha256:[0-9a-f]{64}",value):
        raise GraphError("rotation_consumer_invalid")
    return value


def metadata(material):
    return dict(fingerprint=material.fingerprint,pem_hash=hashlib.sha256(material.pem).hexdigest(),expires_at=material.expires_at)


class AdoptionJournal:
    """Caller holds RootJournal.session; host still proves real locks/quiet/binds."""
    def __init__(self,journal,binding):
        self.root,self.binding=journal,binding
        if binding.scope_key!=journal.binding.scope or binding.instance_id!=journal.binding.instance_id:
            raise GraphError("rotation_scope_changed")

    def state(self,operation):
        value=self.root._read(uuid(operation)+".host.json")
        if value is None:return None
        try:
            if (not isinstance(value,dict) or set(value)!=FIELDS or type(value["version"]) is not int or value["version"]!=1
                    or value["operation_id"]!=operation or value["target"] not in {"old","new"} or value["phase"] not in PHASES
                    or type(value["revision"]) is not int or value["revision"]<0 or type(value["paused"]) is not bool
                    or type(value["started_at"]) is not int or value["started_at"]<0
                    or any(value[name]!=expected for name,expected in self.binding.fields().items())):raise ValueError()
            uuid(value["boot_id"])
            if set(value["images"])!=ROLES:raise ValueError()
            for item in value["images"].values():image(item)
            for name in ("old","new"):
                item=value[name]
                if set(item)!={"fingerprint","pem_hash","expires_at"} or type(item["expires_at"]) is not int:raise ValueError()
                sha(item["fingerprint"]);sha(item["pem_hash"])
            if value["drain_identity"] is not None:sha(value["drain_identity"])
            if not isinstance(value["consumers"],dict) or not set(value["consumers"])<=ROLES:raise ValueError()
            core=self.root.state(operation)
            if core is None or value["old"]["fingerprint"]!=core["old_fingerprint"] or value["new"]!=metadata(self.root.material(operation)):
                raise ValueError()
            original=CertificateMaterial.parse(protected_bytes(self.root.directory/(operation+".old.pem")))
            if value["old"]!=metadata(original):raise ValueError()
            if value["phase"] in {"consumers_verified","proof_started","proof_unknown","proof_verified","committed"}:
                if set(value["consumers"])!=ROLES:raise ValueError()
                for role,item in value["consumers"].items():
                    self._probe(value,role,item,purpose="consumer-read",now=item["probe"]["at"])
                    if item["probe"]["proof_revision"] is not None or item["probe"]["proof_at"] is not None:raise ValueError()
            if value["phase"] in {"proof_started","proof_unknown","proof_verified","committed"}:
                intent=value["proof_intent"]
                if (not isinstance(intent,dict) or set(intent)!={"consumer_id","container_id","image","epoch","base_revision","at"}
                        or intent["consumer_id"]!=self._consumer(value,"notifications",dict(
                            container_id=intent["container_id"],image=intent["image"],probe=None))
                        or type(intent["epoch"]) is not int or intent["epoch"]<=max(item["probe"]["epoch"] for item in value["consumers"].values())
                        or type(intent["base_revision"]) is not int or intent["base_revision"]<0
                        or type(intent["at"]) is not int or intent["at"]<0):raise ValueError()
            if value["phase"] in {"proof_verified","committed"}:
                item=value["proof"];probe=self._probe(value,"notifications",item,purpose="finalize-proof",now=item["probe"]["at"])
                self._proof_matches(value,probe,probe["at"])
            if value["phase"]=="committed":
                sha(value["seal"])
                if value["seal"]!=identity({name:item for name,item in value.items() if name!="seal"}):raise ValueError()
            elif value["seal"] is not None:raise ValueError()
            return value
        except (KeyError,TypeError,ValueError,GraphError):raise GraphError("rotation_adoption_invalid") from None

    def _current(self,operation,phases):
        value=self.state(operation)
        if value is None or value["phase"] not in phases:raise GraphError("rotation_transition_invalid")
        if value["boot_id"]!=boot_id():raise GraphError("rotation_adoption_boot_changed")
        return value

    def _save(self,value,**changes):
        result=dict(value,**changes,revision=value["revision"]+1)
        self.root._write(value["operation_id"]+".host.json",result)
        return result

    def prepare(self,operation,old,images,*,paused,drain_identity,now):
        existing=self.state(operation)
        if existing is not None:return existing
        core=self.root.state(operation)
        if (core is None or core["phase"] not in {"registered","candidate_verified"}
                or core["old_fingerprint"]!=old.fingerprint or type(paused) is not bool
                or type(now) is not int or not old.not_before<=now<old.expires_at or set(images)!=ROLES):
            raise GraphError("rotation_adoption_invalid")
        if drain_identity is not None:sha(drain_identity)
        for item in images.values():image(item)
        target=self.root.material(operation)
        backup=self.root.directory/(uuid(operation)+".old.pem")
        if backup.exists() or backup.is_symlink():
            if protected_bytes(backup)!=old.pem:raise GraphError("rotation_backup_changed")
        else:
            fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,"wb") as output:
                output.write(old.pem);output.flush();os.fsync(output.fileno())
            sync_directory(self.root.directory)
        value=dict(version=1,operation_id=operation,**self.binding.fields(),boot_id=boot_id(),old=metadata(old),
            new=metadata(target),images=dict(images),paused=paused,drain_identity=drain_identity,target="new",
            phase="prepared",revision=0,consumers={},proof_intent=None,proof=None,seal=None,started_at=now)
        self.root._write(operation+".host.json",value)
        return value

    def old_material(self,operation):
        value=self.state(operation)
        if value is None:raise GraphError("rotation_adoption_invalid")
        material=CertificateMaterial.parse(protected_bytes(self.root.directory/(operation+".old.pem")))
        if metadata(material)!=value["old"]:raise GraphError("rotation_backup_changed")
        return material

    def activation_started(self,operation):
        value=self._current(operation,{"prepared"})
        if self.root.state(operation)["phase"]!="candidate_verified":raise GraphError("rotation_transition_invalid")
        return self._save(value,phase="activation_started")

    def activated(self,operation):
        return self._save(self._current(operation,{"activation_started"}),phase="activated")

    def rollback(self,operation,now):
        value=self._current(operation,PHASES)
        if value["target"]!="new" or self.old_material(operation).expires_at<=now:
            raise GraphError("rotation_rollback_unavailable")
        return self._save(value,target="old",phase="activation_started",consumers={},proof_intent=None,proof=None,seal=None)

    def rollback_unknown(self,operation):
        value=self._current(operation,PHASES-{"prepared","committed"})
        if value["target"]!="old":raise GraphError("rotation_transition_invalid")
        return self._save(value,phase="rollback_unknown")

    def recover(self,operation,*,pem_hash,quiet_evidence,observed,now,paused,drain_identity):
        """Only after host confirms stopped old consumers and locked current DB read."""
        value=self.state(operation);sha(pem_hash);sha(quiet_evidence)
        if value is None or type(now) is not int or type(paused) is not bool:raise GraphError("rotation_recovery_invalid")
        targets=[name for name in ("old","new") if value[name]["pem_hash"]==pem_hash]
        if len(targets)!=1 or value[targets[0]]["expires_at"]<=now:raise GraphError("rotation_recovery_invalid")
        if drain_identity is not None:sha(drain_identity)
        if value["phase"] in {"proof_started","proof_unknown"}:
            intent=value["proof_intent"]
            if not isinstance(observed,dict) or set(observed)!={"revision","proof"}:raise GraphError("rotation_proof_unreconciled")
            if observed["revision"]!=intent["base_revision"]:
                proof=observed["proof"];config=self.root.binding.config
                scope=graph_scope(config.tenant_id,config.client_id,config.mailbox)
                if (observed["revision"]!=intent["base_revision"]+1 or not isinstance(proof,dict)
                        or set(proof)!={"fingerprint","scope_key","at"}
                        or proof["fingerprint"]!=value[value["target"]]["fingerprint"] or proof["scope_key"]!=scope
                        or type(proof["at"]) is not int or not intent["at"]<=proof["at"]<=now):
                    raise GraphError("rotation_proof_unreconciled")
        # Preserve every previous intent/seal before fresh consumer/proof work.
        filename=operation+".host-checkpoint-"+str(value["revision"])+".json"
        checkpoint=dict(checkpoint=value,quiet_evidence=quiet_evidence,observed_proof=observed,
            pem_hash=pem_hash,recovered_at=now)
        prior=self.root._read(filename)
        if prior is not None and prior!=checkpoint:raise GraphError("rotation_recovery_changed")
        if prior is None:self.root._write(filename,checkpoint)
        return self._save(value,boot_id=boot_id(),target=targets[0],phase="activated",paused=value["paused"] or paused,
            drain_identity=drain_identity,consumers={},proof_intent=None,proof=None,seal=None)

    def _consumer(self,value,role,item):
        if not isinstance(item,dict) or set(item)!={"container_id","image","probe"}:raise GraphError("rotation_consumer_invalid")
        sha(item["container_id"])
        if image(item["image"])!=value["images"][role]:raise GraphError("rotation_consumer_invalid")
        return hashlib.sha256(item["container_id"].encode("ascii")).hexdigest()

    def _probe(self,value,role,item,*,purpose,now):
        consumer=self._consumer(value,role,item);probe=item["probe"]
        if (not isinstance(probe,dict) or set(probe)!=PROBE_FIELDS or probe["ok"] is not True or probe["code"]!="graph_probe_verified"
                or any(probe[name]!=value[name] for name in self.binding.fields())
                or probe["operation_id"]!=value["operation_id"] or probe["purpose"]!=purpose
                or probe["consumer_role"]!=role or probe["consumer_id"]!=consumer
                or type(probe["epoch"]) is not int or probe["epoch"]<1
                or type(probe["at"]) is not int or not 0<=now-probe["at"]<=60
                or any(probe[name]!=value[value["target"]][name] for name in ("pem_hash","fingerprint"))
                or probe["receipt_hash"]!=identity({name:item for name,item in probe.items() if name!="receipt_hash"})):
            raise GraphError("rotation_consumer_invalid")
        return probe

    def consumers_verified(self,operation,consumers,now):
        value=self._current(operation,{"activated"})
        if not isinstance(consumers,dict) or set(consumers)!=ROLES:raise GraphError("rotation_consumer_invalid")
        for role,item in consumers.items():
            probe=self._probe(value,role,item,purpose="consumer-read",now=now)
            if probe["proof_revision"] is not None or probe["proof_at"] is not None:raise GraphError("rotation_consumer_invalid")
        return self._save(value,phase="consumers_verified",consumers=consumers)

    def proof_started(self,operation,consumer,*,epoch,base_revision,now):
        value=self._current(operation,{"consumers_verified"})
        consumer_id=self._consumer(value,"notifications",consumer)
        if (type(epoch) is not int or epoch<=max(item["probe"]["epoch"] for item in value["consumers"].values())
                or type(base_revision) is not int or base_revision<0 or type(now) is not int):raise GraphError("rotation_proof_invalid")
        return self._save(value,phase="proof_started",proof_intent=dict(consumer_id=consumer_id,
            container_id=consumer["container_id"],image=consumer["image"],epoch=epoch,base_revision=base_revision,at=now))

    def proof_unknown(self,operation):
        return self._save(self._current(operation,{"proof_started"}),phase="proof_unknown")

    def proof_verified(self,operation,consumer,now):
        value=self._current(operation,{"proof_started","proof_unknown"})
        probe=self._probe(value,"notifications",consumer,purpose="finalize-proof",now=now)
        self._proof_matches(value,probe,now)
        return self._save(value,phase="proof_verified",proof=consumer)

    def _proof_matches(self,value,probe,now):
        intent=value["proof_intent"]
        if (probe["consumer_id"]!=intent["consumer_id"] or probe["epoch"]!=intent["epoch"]
                or type(probe["proof_revision"]) is not int or probe["proof_revision"]!=intent["base_revision"]+1
                or type(probe["proof_at"]) is not int or not intent["at"]<=probe["proof_at"]<=now
                or now-probe["proof_at"]>60):raise GraphError("rotation_proof_invalid")

    def commit(self,operation,*,now,paused,drain_identity):
        value=self._current(operation,{"proof_verified"})
        if (type(paused) is not bool or paused!=value["paused"] or drain_identity!=value["drain_identity"]
                or value[value["target"]]["expires_at"]<=now
                or not 0<=now-value["proof"]["probe"]["proof_at"]<=60):raise GraphError("rotation_release_invalid")
        committed=dict(value,phase="committed",revision=value["revision"]+1)
        committed["seal"]=identity({name:item for name,item in committed.items() if name!="seal"})
        self.root._write(operation+".host.json",committed)
        return committed
