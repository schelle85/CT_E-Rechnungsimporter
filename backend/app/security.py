import hmac
import os
from dataclasses import asdict
from app.errors import AccessError, DirectoryDenied, DirectoryUnavailable
from app.settings import LdapSettings, read_secret, load_cipher, public_origin
from app.store import Store
from app.directory import LdapDirectory
from app.database import make_engine

COOKIE="__Host-importer_session"

class Runtime:
    def __init__(self, engine, cipher, directory, origin, bind_file):
        self.engine, self.cipher, self.directory = engine,cipher,directory
        self.origin, self.bind_file = origin,bind_file
        self.store=Store(engine)

    def configuration(self, version=None):
        row=version or self.store.active()
        cfg=LdapSettings.model_validate_json(row["settings"])
        try:
            password=self.cipher.decrypt(row["bind_cipher"].encode()).decode() if row["bind_cipher"] else read_secret(self.bind_file)
        except Exception:
            raise AccessError(503,"LDAP-Konfiguration nicht verfügbar.") from None
        return row,cfg,password

    def csrf(self, request, row):
        if request.headers.get("origin")!=self.origin or not row or not hmac.compare_digest(request.headers.get("x-csrf-token","").encode("utf-8"),row["csrf"].encode("utf-8")):
            raise AccessError(403,"Ungültiger CSRF-Nachweis.")

    def require(self, request, revalidate=True):
        token=request.cookies.get(COOKIE,"")
        row=self.store.session(token)
        if not row or not row["guid"]:
            raise AccessError()
        if revalidate:
            active,cfg,password=self.configuration()
            if row["config_id"]!=active["id"]:
                self.store.revoke(token,"session_revoked")
                raise AccessError()
            try:
                principal=self.directory.revalidate(cfg,password,row["guid"])
            except DirectoryDenied:
                self.store.revoke(token,"session_revoked")
                raise AccessError() from None
            except DirectoryUnavailable:
                raise AccessError(503,"Verzeichnis vorübergehend nicht erreichbar.") from None
            if not self.store.touch(row):
                raise AccessError()
        else:
            principal=None
        return row,principal

    def login(self, request, credentials):
        token=request.cookies.get(COOKIE,"")
        row=self.store.session(token)
        self.csrf(request,row)
        peer=request.client.host if request.client else "unknown"
        self.store.throttle("login-peer",peer,30,60)
        self.store.throttle("login-user",credentials.username.casefold(),5,600)
        active,cfg,password=self.configuration()
        try:
            principal=self.directory.authenticate(cfg,password,credentials.username,credentials.password.get_secret_value())
        except DirectoryDenied:
            self.store.failed(credentials.username,"login")
            raise AccessError() from None
        except DirectoryUnavailable:
            raise AccessError(503,"Verzeichnis vorübergehend nicht erreichbar.") from None
        # Reject a concurrent configuration switch before creating a new session.
        if self.store.active()["id"]!=active["id"]:
            raise AccessError(409,"Konfiguration geändert. Bitte erneut anmelden.")
        new_token,csrf=self.store.new_session(principal,active["id"],token)
        return new_token, {"authenticated":True,"user":asdict(principal),"csrf_token":csrf}

    def save_config(self, principal, candidate):
        active,cfg,password=self.configuration()
        if active["id"]!=candidate.expected_version:
            raise AccessError(409,"Konfiguration wurde zwischenzeitlich geändert.")
        ciphertext=active["bind_cipher"]
        if candidate.bind_password is not None:
            password=candidate.bind_password.get_secret_value()
            ciphertext=self.cipher.encrypt(password.encode()).decode()
        try:
            self.directory.validate(candidate.settings,password)
            new_principal=self.directory.revalidate(candidate.settings,password,principal.guid)
            if new_principal.role!="admin":
                raise DirectoryDenied()
        except (DirectoryDenied,DirectoryUnavailable):
            self.store.failed(principal.username,"config_validate")
            raise AccessError(422,"Kandidat nicht aktiviert: Verbindungs-/Gruppenprüfung fehlgeschlagen.") from None
        return self.store.activate(candidate.settings,ciphertext,principal.username,candidate.expected_version)

def build_runtime():
    return Runtime(make_engine(),
        load_cipher(os.environ.get("CONFIG_KEY_FILE","/run/secrets/config_key")),
        LdapDirectory(os.environ.get("LDAP_CA_FILE","/run/importer/ldap-ca.pem")),
        public_origin(os.environ.get("PUBLIC_ORIGIN","")),
        os.environ.get("LDAP_BIND_PASSWORD_FILE","/run/secrets/ldap_bind_password"))
