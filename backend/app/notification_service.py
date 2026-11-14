"""Bounded notification work only; never a scheduler, importer or mail editor."""
from app.graph import GraphError
from app.notification_certificate import CERTIFICATE_TOKEN, certificate_client, record_certificate
from app.notification_model import calendar_slot, graph_scope
from app.notification_queries import report_cohort
from app.storage_plan import digest

DEFINITE_REJECTIONS = {400,401,403,404,405,413,415,422,429}

class NotificationService:
    def __init__(self,store,config,material,*,observation_revision,client_factory=certificate_client,origin=None):
        self.store,self.config,self.material = store,config,material
        self.scope = graph_scope(config.tenant_id,config.client_id,config.mailbox)
        self.client_factory,self.origin = client_factory,origin
        self.observation_revision = observation_revision

    def _record(self,current,*,fresh_proof=None):
        value = record_certificate(self.store,self.scope,current,expected_revision=self.observation_revision,
            fresh_proof=fresh_proof)
        self.observation_revision = value["revision"]
        return value

    def local_observation(self, *, code="notification_certificate_unavailable"):
        current = self.material.metadata(int(self.store.clock())) if self.material else dict(code=code)
        return self._record(current)

    def _proof(self):
        now = int(self.store.clock())
        current = self.material.metadata(now)
        proof = dict(fingerprint=self.material.fingerprint,scope_key=self.scope,at=now) if current["valid"] else None
        return self._record(current,fresh_proof=proof)

    def _backoff(self,error):
        until = int(self.store.clock())+900
        if error.status == 429:
            until = error.retry_not_before or until
            self.store.scope_backoff(self.scope,until)
        return until

    def observe(self, *, probe=False,budget=None):
        value = self.local_observation()
        if not probe or self.material is None:
            return value
        if self.store.transport_not_before(self.scope) > int(self.store.clock()):
            return dict(value,probe_code="notification_transport_deferred")
        try:
            with self.client_factory(self.config,self.material) as client:
                if budget is not None:client.deadline = budget.deadline
                client.probe()  # Fresh credential, same parsed PEM bytes, mailbox-bound GET only.
                return self._proof()
        except GraphError as error:
            self._backoff(error)
            return dict(value,probe_code=error.code)

    def plan(self):
        observation = self.local_observation()
        configuration = self.store.configuration()
        config,version = configuration["settings"],configuration["version"]
        now = int(self.store.clock())
        result = []
        warning = observation["warning"]
        if warning:
            slot = calendar_slot("certificate",now,config,certificate=warning["fingerprint"])
            facts = dict(fingerprint=warning["fingerprint"],expires_at=warning["expires_at"],
                remaining_seconds=warning["expires_at"]-now)
            row = self.store.prepare(slot,self.scope,facts,expected_version=version,as_of=now,origin=self.origin)
            if row:result.append(row)
        for kind in ("daily","weekly"):
            if not config[kind+"_enabled"]:
                continue
            slot = calendar_slot(kind,now,config)
            report = report_cohort(self.store.engine,slot,digest([self.config.mailbox.lower()]),as_of=now)
            row = self.store.prepare(slot,self.scope,report["counts"],expected_version=version,as_of=now,origin=self.origin)
            if row:result.append(row)
        return result

    def send(self,key,*,budget,owner):
        if budget.remaining() <= 0:
            return self.store.read(key)
        self.local_observation()
        ticket = self.store.claim(key,self.scope,owner=owner)
        if ticket is None:
            return self.store.read(key)
        if self.material is None:
            return self.store.defer(ticket,"notification_certificate_unavailable",int(self.store.clock())+900)
        if budget.remaining() <= 0 or self.store.transport_not_before(self.scope) > int(self.store.clock()):
            return self.store.defer(ticket,"notification_transport_deferred",max(int(self.store.clock())+1,
                self.store.transport_not_before(self.scope)))
        try:
            with self.client_factory(self.config,self.material) as client:
                client.deadline = budget.deadline
                # Auth/read failure is known before reserving a possible external POST.
                client.probe()
                self._proof()
                if not self.store.reserve(ticket,budget=budget):
                    return self.store.read(key)
                payload = self.store.begin_post(ticket,budget=budget)
                if payload is None:
                    return self.store.read(key)
                if budget.remaining() <= 0:
                    return self.store.finish(ticket,"unknown",error_code="notification_deadline_before_transport")
                try:
                    client._write("POST",client.root+"/sendMail",payload,expected=202)
                except GraphError as error:
                    self._backoff(error)
                    state = "rejected" if error.status in DEFINITE_REJECTIONS and not error.uncertain else "unknown"
                    return self.store.finish(ticket,state,http_status=error.status,error_code=error.code)
                return self.store.finish(ticket,"accepted",http_status=202)
        except GraphError as error:
            until = self._backoff(error)
            # Includes close failures after a durable accepted commit: defer cannot overwrite it.
            return self.store.defer(ticket,error.code,until)
