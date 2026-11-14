"""Synthetic B fixtures: real Fernet and generated RSA certificates, no accounts/network."""
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import httpx
import sqlalchemy as sa
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from app.graph import GraphClient, GraphConfig
from app.notification_certificate import CERTIFICATE_TOKEN, CertificateMaterial
from app.notification_model import DEFAULTS, OperationBudget, graph_scope
from app.notification_schema007 import metadata, settings
from app.notification_service import NotificationService
from app.notification_state import NotificationStore
from app.schema import metadata as security_metadata
from app.processing_state import metadata as processing_metadata
from app.storage_state import metadata as storage_metadata

NOW = int(datetime(2026,12,1,12,tzinfo=timezone.utc).timestamp())
CONFIG = GraphConfig("11111111-1111-1111-1111-111111111111","22222222-2222-2222-2222-222222222222","invoice@example.invalid")
SCOPE = graph_scope(CONFIG.tenant_id,CONFIG.client_id,CONFIG.mailbox)
INSTANCE = "33333333-3333-3333-3333-333333333333"
_key = None

def material(*,days=30,before=-30):
    global _key
    if _key is None:_key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"notification.example.invalid")])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.fromtimestamp(NOW+before*86400,timezone.utc))
        .not_valid_after(datetime.fromtimestamp(NOW+days*86400,timezone.utc)).sign(_key,hashes.SHA256()))
    pem=cert.public_bytes(serialization.Encoding.PEM)+_key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    return CertificateMaterial.parse(pem)

class Fixture:
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database=Path(self.temp.name)/"synthetic.sqlite"
        self.engine=sa.create_engine("sqlite:///"+str(self.database),poolclass=sa.pool.NullPool,
            connect_args={"check_same_thread":False,"timeout":10})
        self.addCleanup(self.engine.dispose)
        for value in (security_metadata,processing_metadata,storage_metadata,metadata):value.create_all(self.engine)
        self.key=Fernet.generate_key()
        self.cipher=Fernet(self.key)
        self.now=[NOW]
        with self.engine.begin() as c:
            c.execute(settings.insert().values(singleton=1,version=0,actor="schema007",updated_at=0))
            c.exec_driver_sql("CREATE TABLE app_metadata (singleton INTEGER PRIMARY KEY, instance_id VARCHAR(36))")
            c.execute(sa.text("INSERT INTO app_metadata VALUES (1,:instance)"),dict(instance=INSTANCE))
        self.store=NotificationStore(self.engine,self.cipher,INSTANCE,clock=lambda:self.now[0])
        self.config=dict(DEFAULTS,recipients=["first@example.invalid","second@example.invalid"])
        self.http_calls=[]

    def configure(self,**changes):
        self.config=dict(self.config,**changes)
        return self.store.save_settings(self.store.configuration()["version"],self.config,SCOPE,"operator")

    def budget(self):
        return OperationBudget(clock=lambda:self.now[0])

    def service(self,certificate,*,handler=None):
        value=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)
        return NotificationService(self.store,CONFIG,certificate,observation_revision=value["revision"] if value else 0,
            client_factory=self.factory(handler))

    def factory(self,handler=None):
        @contextmanager
        def create(config,certificate):
            def respond(request):
                self.http_calls.append(request)
                if handler:return handler(request)
                return httpx.Response(200,json={"id":"synthetic-inbox"}) if request.method=="GET" else httpx.Response(202)
            credential=SimpleNamespace(get_token=lambda _:SimpleNamespace(token="synthetic-token"))
            with httpx.Client(transport=httpx.MockTransport(respond),trust_env=False) as http:
                # These are transport doubles; actual process deadlines are tested separately.
                with patch("app.graph_deadline.request_deadline",side_effect=lambda *a,**k:nullcontext()):
                    yield GraphClient(config,credential,http,read_attempts=1)
        return create

    def request_row(self):
        return self.store.request_test(str(uuid4()),self.store.configuration()["version"],SCOPE,"operator")
