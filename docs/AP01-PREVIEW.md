# AP01 A/B – synthetische Vorschau

React/TypeScript/Vite/Mantine, FastAPI/SQLAlchemy/PyMySQL/Alembic, MariaDB und Nginx OSS.
Die Komponenten wurden gegenüber dem FastAPI-Fullstack-Template und React-admin
abgewogen: bestehende UI-/SQL-Bausteine nutzen, fachliche Vorschau ergänzen;
keine PostgreSQL/JWT/Traefik- oder kostenpflichtige Enterprise-Abhängigkeit.

## Grenze

Alle angezeigten Vorgänge sind synthetisch. Kein Graph, Mailversand,
Rechnungsimport, SMB-Zugriff oder Archivbetrieb. Anmeldung, Wiederholung und
Administration sind sichtbar geplant und gesperrt. Rollenansicht ist keine
Authentifizierung. Die API verweigert sämtliche Administrationszugriffe.
Die Vorschau wird nur im genehmigten internen Netz bereitgestellt.

## Bau und Betrieb

Baukontexte sind das Repository, Dockerfiles unter frontend/ und backend/.
Frontend: npm ci --ignore-scripts, npm run build (inklusive Typecheck).
Backend: exakte Anforderungen aus requirements.lock.
Compose-Vorlage: deploy/compose.yaml. Build und Konfigurationsprüfung starten
keinen Anwendungsdienst. Laufzeitfreigabe benötigt einen festen geprüften Commit
und vorbereitete externe Dateien; keine Kundendaten in dieses Repository kopieren.

Extern setzen: SITE_BIND_IP, DB_DATA_DIR, DB_PASSWORD_FILE,
DB_ROOT_PASSWORD_FILE, TLS_DIR. Dateisecrets besitzen reale Hostrechte.
API läuft als UID/GID10001, Nginx10002. MariaDB-UID vor Bereitstellung des
Datenverzeichnisses am konkreten Image prüfen. Bestehende Elternrechte erhalten.
Keine API-/DB-Hostports. Datenbanknetz intern; Client spricht nur Same-Origin.

Compose wartet auf gesunde DB, erfolgreiche Migration und bereite API.
Migration001 erzeugt genau einen persistenten App-Metadatensatz ohne Rechnungsdaten.
Die Readiness gibt dessen instance_id als Persistenzprüfmerkmal zurück.
Containerneuanlage ohne Änderung dieses Werts belegt die begrenzte Persistenz;
dies ist kein vollständiger Backup-/Restore-Nachweis.

TLS-Verzeichnis als Ganzes RO einbinden. Geprüftes Release atomar per current
wählen, nginx -t, Reload, tatsächlich ausgeliefertes Zertifikat prüfen.
Bei Fehler vorheriges gültiges Release wiederherstellen. Keine Schlüssel ausgeben.

## Anschluss C/D/E

LDAP-Dienst-/Benutzerbind mit geprüfter CA, direkte Gruppen, Serversitzungen,
CSRF, Rate-Limits und serverseitige Rollenprüfung fehlen bewusst noch.
Erst danach Administrationsschreiben aktivieren. Passwort nur ersetzen,
niemals zurückliefern. Kontensperre/Rechteentzug auch für Sitzungen prüfen.
Keine Aussage über eine erfolgreiche AD-Anmeldung aus der Vorschau ableiten.

## Nachgewiesener Quell-/Buildstand

A/B: alle sechs Vorschauansichten, Filter und Detaildialog implementiert.
Frontend-Typecheck/Vite-Build und API-Imagebuild auf Ziel-VM bestanden.
Compose-Konfiguration valide; Nginx-Konfiguration isoliert mit synthetischem
Zertifikat geprüft. Kein Kundenzertifikat und kein Laufzeitsecret im Build.
MariaDB-Dienstidentität im geladenen Image: UID/GID999. API10001, Nginx10002.
Basisimages per Digest, npm-/Python-Laufzeitabhängigkeiten per Lockdatei fixiert.
Noch offen: feste Codeprüfung, freigegebener Dienststart, echtes HTTPS,
MariaDB-Persistenztest und Browser-Sichtprüfung. Kein A/B-Gesamtabschluss behauptet.

Gezielte HTTP-/Migrationstests bestanden (3 unittest-Fälle): alle unterstützten
Adminmethoden403; ausschließlich synthetische Daten/keine Importendpunkte;
Readiness503 ohne Schema, erfolgreicher Migrationslauf und stabiler
Metadatenbezeichner bei erneutem Upgrade, danach503 nach Downgrade.
Diese isolierten Tests verwenden SQLite, nicht die produktive MariaDB.
Testwerkzeuge separat in requirements-test.lock; kein Teil des Runtime-Images.
