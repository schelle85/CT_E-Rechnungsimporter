#!/usr/bin/env bash
# Generic destructive-only-to-new-test-resources integration check; no customer inputs.
set -euo pipefail
umask 077
: "${API_IMAGE:?Pass immutable sha256 API image ID}"
: "${TEST_IMAGE:?Pass immutable sha256 test image ID}"
[[ "$API_IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]] || exit 2
[[ "$TEST_IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]] || exit 2
docker image inspect --format '{{json .RootFS.Layers}}' "$API_IMAGE" "$TEST_IMAGE" | python3 -c 'import json,sys; rows=[json.loads(x) for x in sys.stdin if x.strip()]; assert len(rows)==2 and rows[1][:len(rows[0])]==rows[0]; print("Immutable test image descends from exact API layers: PASS")'
db_image=mariadb:12.3@sha256:d46e102fa8b9b72bfcdeb56f9dd538742092119dc8b11f31fe662605cd234cd9
case_id="invoice-cde-test-$(date -u +%Y%m%dT%H%M%S)-$$"
network="$case_id-net"; volume="$case_id-data"; db="$case_id-db"; api="$case_id-api"
temp_dir=$(mktemp -d /tmp/invoice-cde-test.XXXXXX)
net_created=0; volume_created=0; db_created=0; api_created=0
cleanup() {
 result=$?; trap - EXIT
 if [ "$api_created" = 1 ]; then docker rm -f "$api" >/dev/null || result=90; fi
 if [ "$db_created" = 1 ]; then docker rm -f "$db" >/dev/null || result=91; fi
 if [ "$net_created" = 1 ]; then docker network rm "$network" >/dev/null || result=92; fi
 if [ "$volume_created" = 1 ]; then
  if [ "$(docker volume inspect --format '{{index .Labels "invoice.cde.test"}}' "$volume")" = "$case_id" ]; then
   docker volume rm "$volume" >/dev/null || result=93
  else result=94; fi
 fi
 rm -f "$temp_dir/app-password" "$temp_dir/root-password" "$temp_dir/config-key" "$temp_dir/bootstrap.json" "$temp_dir/http-state.json"
 rmdir "$temp_dir" || result=95
 printf 'Own integration resources cleanup: exit=%s\n' "$result"
 exit "$result"
}
trap cleanup EXIT
openssl rand -hex 32 > "$temp_dir/app-password"
openssl rand -hex 32 > "$temp_dir/root-password"
docker run --rm --network none "$API_IMAGE" python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' > "$temp_dir/config-key"
cp "$(dirname "$0")/../deploy/ldap-bootstrap.example.json" "$temp_dir/bootstrap.json"
chmod 444 "$temp_dir/app-password" "$temp_dir/root-password" "$temp_dir/config-key" "$temp_dir/bootstrap.json"
docker network create --internal --label "invoice.cde.test=$case_id" "$network" >/dev/null
net_created=1
docker volume create --label "invoice.cde.test=$case_id" "$volume" >/dev/null
volume_created=1
docker create --name "$db" --label "invoice.cde.test=$case_id" --network "$network" --network-alias db \
 --mount "type=volume,source=$volume,target=/var/lib/mysql" \
 --mount "type=bind,source=$temp_dir/app-password,target=/run/secrets/db_password,readonly" \
 --mount "type=bind,source=$temp_dir/root-password,target=/run/secrets/db_root_password,readonly" \
 --env MARIADB_DATABASE=importer --env MARIADB_USER=importer \
 --env MARIADB_PASSWORD_FILE=/run/secrets/db_password --env MARIADB_ROOT_PASSWORD_FILE=/run/secrets/db_root_password \
 --health-cmd 'healthcheck.sh --connect --innodb_initialized' --health-interval 2s --health-timeout 5s --health-retries 40 \
 "$db_image" >/dev/null
db_created=1; docker start "$db" >/dev/null
healthy=0
for attempt in $(seq 1 40); do
 if [ "$(docker inspect --format '{{.State.Health.Status}}' "$db")" = healthy ]; then healthy=1; break; fi
 sleep 2
done
test "$healthy" = 1
test "$(docker inspect --format '{{len .HostConfig.PortBindings}}' "$db")" = 0
printf 'New isolated MariaDB12.3 healthy; no hostports; case=%s\n' "$case_id"
db_run() {
 image="$1"; shift
 docker run --rm --network "$network" --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
 --cap-drop ALL --security-opt no-new-privileges:true \
 --mount "type=bind,source=$temp_dir/app-password,target=/run/secrets/db_password,readonly" \
 --env DB_HOST=db --env DB_NAME=importer --env DB_USER=importer --env INTEGRATION_DB=1 "$image" "$@"
}
uuid_query='from app.database import make_engine; from sqlalchemy import text; e=make_engine(); c=e.connect(); rows=c.execute(text("SELECT singleton,instance_id FROM app_metadata")).all(); assert len(rows)==1 and rows[0][0]==1; print(rows[0][1]); c.close();e.dispose()'
db_run "$API_IMAGE" alembic upgrade 001_app_metadata
before=$(db_run "$API_IMAGE" python -c "$uuid_query")
db_run "$API_IMAGE" alembic upgrade head
db_run "$API_IMAGE" alembic upgrade head
after=$(db_run "$API_IMAGE" python -c "$uuid_query")
test "$before" = "$after"
printf 'Actual CLI001->002 twice, preserved metadata UUID=%s\n' "$after"
db_run "$TEST_IMAGE" python -m unittest discover -s tests -v
test "$(db_run "$API_IMAGE" python -c "$uuid_query")" = "$before"
api_mounts=(
 --mount "type=bind,source=$temp_dir/app-password,target=/run/secrets/db_password,readonly"
 --mount "type=bind,source=$temp_dir/app-password,target=/run/secrets/ldap_bind_password,readonly"
 --mount "type=bind,source=$temp_dir/config-key,target=/run/secrets/config_key,readonly"
 --mount "type=bind,source=$temp_dir/bootstrap.json,target=/run/importer/ldap-bootstrap.json,readonly"
 --mount "type=bind,source=/etc/ssl/certs/ca-certificates.crt,target=/run/importer/ldap-ca.pem,readonly"
 --env DB_HOST=db --env DB_NAME=importer --env DB_USER=importer --env PUBLIC_ORIGIN=https://test.invalid
)
api_utility() {
 docker run --rm --network "$network" --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m \
 --cap-drop ALL --security-opt no-new-privileges:true "${api_mounts[@]}" "$API_IMAGE" "$@"
}
# Only this newly created test DB. Seed fixture without adding a runtime auth bypass.
seed='from app.security import build_runtime;from app.schema import metadata;from app.settings import LdapSettings,read_secret;from pathlib import Path
r=build_runtime()
with r.engine.begin() as c:
    for table in reversed(metadata.sorted_tables):
        c.execute(table.delete())
cfg=LdapSettings.model_validate_json(Path("/run/importer/ldap-bootstrap.json").read_text())
cipher=r.cipher.encrypt(read_secret(r.bind_file).encode()).decode()
version=r.store.activate(cfg,cipher,"isolated-test-seed",None)
print("Isolated encrypted configuration fixture committed, version="+str(version))
r.engine.dispose()'
api_utility python -c "$seed"
config_check='from app.security import build_runtime;from app.settings import read_secret;r=build_runtime();row,cfg,pw=r.configuration();assert pw==read_secret(r.bind_file);print("Persisted encrypted configuration decrypts with stable test key, version="+str(row["id"]));r.engine.dispose()'
api_utility python -c "$config_check"
create_api() {
 docker create --name "$api" --label "invoice.cde.test=$case_id" --network "$network" --network-alias api \
 --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m --cap-drop ALL --security-opt no-new-privileges:true \
 "${api_mounts[@]}" "$API_IMAGE" >/dev/null
 api_created=1
 docker start "$api" >/dev/null
 test "$(docker inspect --format '{{.Image}}' "$api")" = "$API_IMAGE"
 test "$(docker inspect --format '{{.Config.User}}' "$api")" = 10001:10001
 test "$(docker inspect --format '{{len .HostConfig.PortBindings}}' "$api")" = 0
 docker inspect --format 'Actual API image={{.Image}} CMD={{json .Config.Cmd}} user={{.Config.User}} readOnly={{.HostConfig.ReadonlyRootfs}}' "$api"
}
create_api
http_first='import http.cookies,json,os,time,urllib.request,urllib.error
base="http://api:8000"
for attempt in range(40):
    try:
        with urllib.request.urlopen(base+"/api/health/ready",timeout=3) as r:
            ready=json.load(r);assert r.status==200
        break
    except urllib.error.URLError:
        if attempt==39: raise
        time.sleep(0.25)
assert ready["instance_id"]==os.environ["EXPECTED_UUID"] and ready["status"]=="ready"
try:
    urllib.request.urlopen(base+"/api/demo/processes",timeout=3)
except urllib.error.HTTPError as e:
    assert e.code==401
else: raise AssertionError("Anonymous demo path open")
with urllib.request.urlopen(base+"/api/auth/session",timeout=3) as r:
    data=json.load(r);cookie=r.headers["Set-Cookie"]
assert data["authenticated"] is False and data["csrf_token"]
for flag in ("secure","httponly","samesite=strict","path=/"):
    assert flag in cookie.lower()
jar=http.cookies.SimpleCookie();jar.load(cookie)
token=jar["__Host-importer_session"].value
print(json.dumps({"token":token,"csrf":data["csrf_token"]}))'
docker run --rm --network "$network" --read-only --cap-drop ALL --security-opt no-new-privileges:true \
 --env "EXPECTED_UUID=$before" "$API_IMAGE" python -c "$http_first" > "$temp_dir/http-state.json"
chmod 444 "$temp_dir/http-state.json"
printf 'Actual Uvicorn: HTTPready200/UUID exact; anonymous401; secure preauth challenge created (tokens not printed).\n'
old_api=$(docker inspect --format '{{.Id}}' "$api")
docker rm -f "$api" >/dev/null; api_created=0
create_api
test "$(docker inspect --format '{{.Id}}' "$api")" != "$old_api"
http_second='import json,os,time,urllib.request,urllib.error
from pathlib import Path
state=json.loads(Path("/state.json").read_text())
for attempt in range(40):
    try:
        with urllib.request.urlopen("http://api:8000/api/health/ready",timeout=3) as r:
            data=json.load(r);assert r.status==200 and data["instance_id"]==os.environ["EXPECTED_UUID"]
        break
    except urllib.error.URLError:
        if attempt==39: raise
        time.sleep(0.25)
request=urllib.request.Request("http://api:8000/api/auth/session",headers={"Cookie":"__Host-importer_session="+state["token"]})
with urllib.request.urlopen(request,timeout=3) as r:
    data=json.load(r);assert r.status==200
assert data=={"authenticated":False,"csrf_token":state["csrf"]}
print("After API recreation: HTTP200/same metadata UUID and persisted preauth session/CSRF, PASS")'
docker run --rm --network "$network" --read-only --cap-drop ALL --security-opt no-new-privileges:true \
 --mount "type=bind,source=$temp_dir/http-state.json,target=/state.json,readonly" \
 --env "EXPECTED_UUID=$before" "$API_IMAGE" python -c "$http_second"
api_utility python -c "$config_check"
test "$(db_run "$API_IMAGE" python -c "$uuid_query")" = "$before"
printf 'CDE MariaDB CLI/security/Uvicorn/persistence regression: PASS\n'
