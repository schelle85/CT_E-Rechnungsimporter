# AP01 C/D/E: AD-Anmeldung und geschützte Konfiguration

Quell-/Prüfstand, noch keine Kundenbereitstellung. 16 Sicherheitstests gegen
MariaDB/CLI/Uvicorn bestanden; Root-Sitzungswiderruf und realer TLS-Gegentest
zusätzlich einzeln geprüft. Die dabei ergänzte Socketbereinigung benötigt noch
einen finalen API-Neubau und vollständigen Retest vor Betriebsfreigabe.

Alle Rechnungs-/Archiv-/Meldungsvorgänge bleiben synthetisch; kein AP02+-Import,
Mailversand oder Wiederholungsjob. Anmeldung und Administration verwenden echte
Backendrechte. Kein Runtime-Demo-Login, keine lokale Benutzerpasswortverwaltung.

## Bausteine und Sicherheitsvertrag

ldap3 2.9.1 (LGPLv3) für LDAP/TLS/Filterescaping; cryptography/Fernet für
authentifizierte Bindsecretverschlüsselung; FastAPI/Starlette/SQLAlchemy/PyMySQL
aus der vorhandenen Basis. Exakte Versionen in requirements.lock.
Starlette-Cookiesessions sind clientseitig; starsessions würde ebenfalls einen
SQL-Store benötigen. Die notwendige MariaDB-Integration verwendet opake zufällige
Sitzungs-IDs und die vorhandene SQL-Bibliothek, ohne zusätzlichen IAM-/Redis-Dienst.
Lizenzkosten der gewählten freien Komponenten:0; Betrieb und Pflege bleiben Aufwand.

Alle LDAPS-Server werden mit der betreiberverwalteten CA und ihrem konfigurierten
Hostname geprüft. Keine Klartextoption, keine Referrals, keine beliebige Server-
Discovery. Maximal3 FQDNs; Connect-/Receive-Timeout jeweils1–5s.
Verbindungsfehler erlauben begrenztes Failover; falsche Benutzerkennwörter werden
nicht auf jedem DC erneut versucht. Nur direkte memberOf-Gruppen zählen.
Kontosperre, Kontoablauf und aktuelle Gruppen werden bei jedem geschützten Request
über den Dienstbind geprüft; Verzeichnisausfall bedeutet503 statt Rechtefreigabe.

Cookie: __Host-importer_session, Secure, HttpOnly, SameSite=strict, Path=/,
kein Domain-Attribut. Nur zufälliger Token im Cookie, nur SHA256 davon in MariaDB.
Vor Anmeldung10min; danach absolut8h und Idle30min. Login ersetzt die ID;
Logout widerruft serverseitig, auch bei LDAP-Ausfall. CSRF-Token plus exakter
PUBLIC_ORIGIN sind für Login, Logout und jeden anderen Zustandswechsel nötig.
Persistente Ratenbegrenzung:5 Loginversuche je Benutzer/10min plus30 je
API-Gegenstelle/Minute; Preauth-Neuanlage60/Gegenstelle/Minute. Hinter dem
gemeinsamen Proxy gilt die Gegenstellenbegrenzung gemeinsam für dessen Zugriffe.
Keine CORS-Freigabe. Validierungsfehler spiegeln keine Passwort-/Requestinhalte.

Alle /api/-Pfade sind zentral geschützt außer exakt Health, Sessionzustand und
Login. Letztere prüfen ihre eigenen Challenge-/CSRF-Grenzen.
Leser mit gültiger Sitzung UND gültigem CSRF dürfen weiterhin nicht schreiben.
Administration und Auditansicht benötigen Verwaltungsrecht.
Health/ready bestätigt DB, Schema und aktivierten Konfigurationskopf; kein
dauerhafter LDAP-Verfügbarkeitsnachweis. LDAP wird beim geschützten Zugriff geprüft.

## Runtime-Dateien: nur API, niemals Images oder Public Git

- DB-Passwort wie bisher /run/secrets/db_password.
- LDAP-Secret /run/secrets/ldap_bind_password: genau einen LF/CRLF-Dateiabschluss
  entfernen, sonst unverändert; Benutzerkennwörter werden nicht persistiert.
- Stabile Fernet-Datei /run/secrets/config_key, vom Betreiber erzeugt und getrennt
  von DB-Dumps gesichert. Verlust verhindert Entschlüsselung gespeicherter Secrets.
- CA /run/importer/ldap-ca.pem und /run/importer/ldap-bootstrap.json.
- PUBLIC_ORIGIN als externe Instanzvariable, genau ein HTTPS-Origin.
- Bootstrap-Beispiel unter deploy/ldap-bootstrap.example.json: direkt die dortigen
  Felder, kein settings-Wrapper und kein Kennwort im JSON.
- Keine LDAP-/Key-/CA-Mounts an migrate oder Nginx. Migration erhält nur DB-Secret.
  Nginx erhält nur TLS; Hostrechte auf tatsächliche Dienstidentität abstimmen.

Die Compose-Vorlage benutzt ausschließlich CDE-Tags. Image-IDs vor Bereitstellung
prüfen/festhalten; kein unkontrollierter Rebuild/Pull. Bestehendes A/B-Compose und
dessen Tags/Images bleiben für ORGA eingefroren.

## Migration, Bootstrap und Start durch Betreiber nach Code-Review

Der folgende Ablauf ist eine Bedienfolge für einen freigegebenen Stand,
keine bereits ausgeführte Kundenbereitstellung. Externe Dateipfade/Origin zuvor
anhand des Runtimevertrags einrichten. DB-Container/Datadir/Metadata-UUID erhalten.
Eine eigene eingefrorene CDE-Compose-/Env-Datei verwenden; Pfade sind Platzhalter:

```bash
docker compose --project-directory /path/to/checkout/deploy --env-file /protected/instance-cde.env -f /protected/compose-cde.yaml run --rm --no-deps migrate
docker compose --project-directory /path/to/checkout/deploy --env-file /protected/instance-cde.env -f /protected/compose-cde.yaml run --rm --no-deps api python -m app.bootstrap init
docker compose --project-directory /path/to/checkout/deploy --env-file /protected/instance-cde.env -f /protected/compose-cde.yaml up -d --no-deps --no-build --pull never --wait --wait-timeout 90 api
docker compose --project-directory /path/to/checkout/deploy --env-file /protected/instance-cde.env -f /protected/compose-cde.yaml up -d --no-deps --no-build --pull never nginx
```

Migration002 ist additiv;001/App-Metadata wird nicht verändert. Echter Alembic-
Console-Script-Einstieg und MariaDB-DDL werden durch den Integrationstest geprüft.
Bootstrap init prüft alle LDAPS-Verbindungen und beide Gruppen vor Aktivierung.
Bei bereits vorhandenem aktivem Kopf bricht init ab; kein stiller Reset.
Bootstrap benötigt ausschließlich Dienstbind, keine Endbenutzerkennwörter.
Nach Migration und nach API-Wechsel Health-UUID gegen vorherigen Wert vergleichen.
Nginx frisch starten, damit die neue API-IP aufgelöst wird; HTTPS/API mitprüfen.

## Konfiguration, letzter Stand und Root-Rückweg

GET /api/admin/config liefert Einstellungen/Versionsnummer/Kennwort-vorhanden,
niemals Klartext/Ciphertext. PUT erwartet expected_version und settings; optional
bind_password ersetzt das Secret, Weglassen behält es. Jeder Kandidat wird vor
Aktivierung auf allen konfigurierten DCs und auf fortbestehendes Verwaltungsrecht
des bearbeitenden Kontos geprüft. Fehler erhalten den aktiven Stand. Erfolgreiche
Aktivierung ist atomar, versioniert, protokolliert und widerruft sämtliche Sitzungen.
Der letzte Stand bleibt gespeichert; keine Benutzerpasswörter in der Datenbank.

Operator im gleichen API-Datei-/Imagevertrag:

```bash
python -m app.bootstrap list
python -m app.bootstrap restore --version <bekannte-funktionierende-ID>
python -m app.bootstrap revoke-sessions
```

Über compose run --rm --no-deps api ausführen. restore prüft den gewählten
LDAP-/Gruppenstand vor Aktivierung und erhält bei Fehler den aktuellen Kopf.
revoke-sessions benötigt keine LDAP-Erreichbarkeit und widerruft nur Sitzungen.
Keine HTTP-Recovery-/Auth-Bypassroute. Stable Key und Original-Bootstrap-Binddatei
erhalten; AD-seitig inzwischen ungültige Kennwörter werden durch Versionsrestore
nicht wieder gültig. Keine Datenbankschema-Downgrades oder Datenträgerlöschung.

## Reproduzierbare Prüfung

Testwerkzeuge/DirectoryDouble existieren ausschließlich im separaten Testimage:

```bash
docker build -f backend/Dockerfile -t invoice-importer-api:ap01-cde .
docker image tag sha256:<geprüfte-API-ID> invoice-importer-api:verified-test-base
docker build -f backend/Dockerfile.test --build-arg API_IMAGE=invoice-importer-api:verified-test-base -t invoice-importer-tests:ap01-cde .
API_IMAGE=sha256:<geprüfte-API-ID> TEST_IMAGE=sha256:<geprüfte-Test-ID> bash scripts/test-cde-mariadb.sh
```

Der Runner benötigt Docker-Zugriff, Python3, openssl und ein öffentliches System-CA-Bundle.
Der Runner prüft vorab die API-Layer-Abstammung des Testimages. Er erzeugt nur neue benannte/gelabelte Netze, Testvolume, Container und zufällige
Synthetikdateien. Keine Kundenpfade/-Secrets/-Ports. Cleanup betrifft nur eigene
neue Ressourcen. Echte CLI001->002 zweimal, gleichbleibende Metadata-UUID,
Sicherheitsfälle gegen MariaDB, tatsächlicher Uvicorn-CMD und API-Neuanlage mit
erhaltenem Session-/Konfigurationszustand. Die LDAP-Transport-/Rollenfälle verwenden
Doubles ausschließlich im Testmodul. Tatsächliche AD-Endbenutzerlogins sind
gesondert mit Betreiber/Testkontoinhabern zu prüfen; keine Abnahme daraus ableiten.

Primärquellen: [ldap3](https://ldap3.readthedocs.io/en/latest/connection.html),
[TLS](https://ldap3.readthedocs.io/en/latest/ssltls.html),
[Starlette](https://www.starlette.io/middleware/),
[starsessions](https://github.com/alex-oleshkevich/starsessions),
[Fernet](https://cryptography.io/en/stable/fernet/).

Der kleine ClosingTls-Adapter delegiert TLS-Wrapping/CA-Verifikation an ldap3/OpenSSL
und Hostnamen an ldap3.check_hostname, übernimmt den Socket jedoch vor der
Handshake-/Namensprüfung, damit der Fehlerpfad ihn garantiert schließen kann.
Er behebt die im synthetischen Negativtest beobachtete2.9.1-Ressourcenwarnung;
keine TLS-Prüfung wird übersprungen oder abgeschwächt.
