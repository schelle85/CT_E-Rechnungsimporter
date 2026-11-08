"""Operator-only CLI: no network endpoint, no credential output."""
import argparse
import json
import os
from pathlib import Path
from app.security import build_runtime
from app.settings import LdapSettings
from app.errors import AccessError, DirectoryDenied, DirectoryUnavailable

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["init","list","restore","revoke-sessions"])
    parser.add_argument("--version",type=int)
    args=parser.parse_args()
    runtime=build_runtime()
    try:
        if args.action=="init":
            try:
                runtime.store.active()
            except AccessError as error:
                if error.status!=503:
                    raise
            else:
                raise AccessError(409,"Konfiguration bereits initialisiert.")
            cfg=LdapSettings.model_validate_json(Path(os.environ.get("LDAP_BOOTSTRAP_FILE","/run/importer/ldap-bootstrap.json")).read_text())
            from app.settings import read_secret
            runtime.directory.validate(cfg,read_secret(runtime.bind_file))
            version=runtime.store.activate(cfg,None,"operator-bootstrap",None)
            print(json.dumps({"activated_version":version}))
        elif args.action=="restore":
            if not args.version or args.version<1:
                raise AccessError(422,"Versionsnummer erforderlich.")
            current=runtime.store.active()
            target=runtime.store.version(args.version)
            _,cfg,password=runtime.configuration(target)
            runtime.directory.validate(cfg,password)
            version=runtime.store.activate(cfg,target["bind_cipher"],"operator-restore",current["id"],restore_id=target["id"])
            print(json.dumps({"activated_version":version,"sessions_revoked":True}))
        elif args.action=="revoke-sessions":
            from app.schema import sessions
            with runtime.engine.begin() as c:
                count=c.execute(sessions.delete()).rowcount
                runtime.store.log(c,"operator","sessions_revoke")
            print(json.dumps({"revoked_sessions":count}))
        else:
            import sqlalchemy as sa
            from app.schema import versions,head
            with runtime.engine.connect() as c:
                rows=c.execute(sa.select(versions.c.id,versions.c.created_at,versions.c.actor).order_by(versions.c.id.desc())).mappings()
                print(json.dumps({"versions":[dict(x) for x in rows],"active":runtime.store.active()["id"]}))
    except Exception:
        print("Operator action failed; active configuration retained. Check protected runtime files/directory availability.")
        raise SystemExit(1) from None
    finally:
        runtime.engine.dispose()

if __name__=="__main__":
    main()
