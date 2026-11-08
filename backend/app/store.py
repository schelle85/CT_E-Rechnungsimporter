import hashlib
import json
import secrets
import time
import sqlalchemy as sa
from app.schema import versions, head, sessions, attempts, audit
from app.errors import AccessError
from app.settings import LdapSettings

def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

class Store:
    def __init__(self, engine, clock=time.time):
        self.engine, self.clock = engine, clock

    def log(self, connection, actor, action, result="ok", fields=(), config_id=None):
        connection.execute(audit.insert().values(occurred_at=int(self.clock()), actor=actor[:256],
            action=action, result=result, changed_fields=json.dumps(list(fields)), config_id=config_id))

    def active(self):
        with self.engine.connect() as c:
            row=c.execute(sa.select(versions).join(head, versions.c.id==head.c.active_id)).mappings().first()
            if row is None:
                raise AccessError(503, "LDAP-Konfiguration noch nicht bereit.")
            return dict(row)

    def version(self, version_id):
        with self.engine.connect() as c:
            row=c.execute(sa.select(versions).where(versions.c.id==version_id)).mappings().first()
            if row is None:
                raise AccessError(404, "Konfigurationsstand nicht vorhanden.")
            return dict(row)

    def activate(self, settings, cipher, actor, expected, restore_id=None):
        now=int(self.clock())
        with self.engine.begin() as c:
            current=c.execute(sa.select(head).with_for_update()).mappings().first()
            actual=current["active_id"] if current else None
            if actual != expected:
                raise AccessError(409, "Konfiguration wurde zwischenzeitlich geändert.")
            if restore_id is None:
                new_id=c.execute(versions.insert().values(settings=settings.model_dump_json(),
                    bind_cipher=cipher, created_at=now, actor=actor[:256])).inserted_primary_key[0]
            else:
                new_id=restore_id
            if current:
                c.execute(head.update().values(active_id=new_id, previous_id=actual))
            else:
                c.execute(head.insert().values(singleton=1, active_id=new_id))
            c.execute(sessions.delete())
            self.log(c,actor,"config_restore" if restore_id else "config_activate",
                     fields=list(LdapSettings.model_fields)+["bind_secret"],config_id=new_id)
            return new_id

    def session(self, token):
        if not token or len(token)>128:
            return None
        now=int(self.clock())
        with self.engine.begin() as c:
            row=c.execute(sa.select(sessions).where(sessions.c.id_hash==digest(token))).mappings().first()
            if row is None:
                return None
            idle=1800 if row["guid"] else 600
            if row["expires_at"]<=now or row["last_seen"]+idle<=now:
                c.execute(sessions.delete().where(sessions.c.id_hash==row["id_hash"]))
                return None
            return dict(row)

    def new_session(self, principal=None, config_id=None, old_token=None):
        token=secrets.token_urlsafe(32)
        csrf=secrets.token_urlsafe(32)
        now=int(self.clock())
        with self.engine.begin() as c:
            c.execute(sessions.delete().where(sessions.c.expires_at<=now))
            if old_token:
                c.execute(sessions.delete().where(sessions.c.id_hash==digest(old_token)))
            c.execute(sessions.insert().values(id_hash=digest(token),csrf=csrf,
                guid=principal.guid if principal else None,dn=principal.dn if principal else None,
                username=principal.username if principal else None,config_id=config_id,
                created_at=now,last_seen=now,expires_at=now+(28800 if principal else 600)))
            if principal:
                self.log(c,principal.username,"login")
        return token, csrf

    def revoke(self, token, action="logout"):
        with self.engine.begin() as c:
            row=c.execute(sa.select(sessions).where(sessions.c.id_hash==digest(token))).mappings().first()
            c.execute(sessions.delete().where(sessions.c.id_hash==digest(token)))
            if row and row["guid"]:
                self.log(c,row["username"],action)

    def touch(self, row):
        now=int(self.clock())
        with self.engine.begin() as c:
            current=c.execute(sa.select(sessions).where(sessions.c.id_hash==row["id_hash"]).with_for_update()).mappings().first()
            if not current or current["expires_at"]<=now or current["last_seen"]+1800<=now:
                return False
            c.execute(sessions.update().where(sessions.c.id_hash==row["id_hash"]).values(last_seen=now))
            return True

    def throttle(self, scope, value, limit, period):
        now=int(self.clock())
        bucket=scope+":"+digest(value)+":"+str(now//period)
        with self.engine.begin() as c:
            c.execute(attempts.delete().where(attempts.c.expires_at<=now))
            values=dict(bucket=bucket,count=1,expires_at=(now//period+1)*period)
            if self.engine.dialect.name in ("mysql","mariadb"):
                from sqlalchemy.dialects.mysql import insert
                stmt=insert(attempts).values(**values)
                stmt=stmt.on_duplicate_key_update(count=attempts.c.count+1)
            elif self.engine.dialect.name=="sqlite":
                from sqlalchemy.dialects.sqlite import insert
                stmt=insert(attempts).values(**values)
                stmt=stmt.on_conflict_do_update(index_elements=["bucket"],set_={"count":attempts.c.count+1})
            else:
                raise RuntimeError("Unsupported throttle store")
            c.execute(stmt)
            count=c.execute(sa.select(attempts.c.count).where(attempts.c.bucket==bucket)).scalar_one()
        if count>limit:
            raise AccessError(429, "Zu viele Anmeldeversuche. Bitte später erneut versuchen.")

    def failed(self, actor, action):
        with self.engine.begin() as c:
            self.log(c,actor,action,"rejected")

    def audit_rows(self):
        with self.engine.connect() as c:
            rows=c.execute(sa.select(audit).order_by(audit.c.id.desc()).limit(100)).mappings()
            return [dict(x, changed_fields=json.loads(x["changed_fields"])) for x in rows]
