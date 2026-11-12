# AP02 – Graph-Vertrag

Stand12.11.2026: Entwicklung auf separatem Zweig, keine Kundenbereitstellung.
AP01 ist vollständig durch den Kunden abgenommen; AP02a–c hat Go. AP03+ bleibt
gesperrt. Kein Scheduler, keine automatische Aktivierung am Stichtag und kein
neuer Versand. AP00-Lese-/Versandnachweise sind historische Grundprüfungen.

## Bibliothekswahl

Microsofts [Graph-Python-SDK](https://github.com/microsoftgraph/msgraph-sdk-python)
(MIT) bietet generierte Graph-v1.0-Modelle/Clients, benötigt jedoch ein großes
Paket und zusätzliche SDK-/Middlewarepflege. Gewählt sind
[Azure Identity CertificateCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.certificatecredential?view=azure-python)
1.27.0 (MIT) und [HTTPX](https://www.python-httpx.org/quickstart/)0.28.1 (BSD).
Beide benötigen keinen zusätzlichen Dienst und erheben keine Bibliotheksgebühr;
die vorhandene M365-Umgebung und deren Kosten bleiben Voraussetzung. Identity
übernimmt OAuth, RSA-Zertifikat und In-Memory-Tokenverwaltung. MSAL wäre eine
geeignete Alternative, wird aber nur als interne Identity-Abhängigkeit verwendet,
nicht zusätzlich direkt integriert. Vorhandene AP00-Muster werden fortgesetzt.
Eigene Integration betrifft Postfachbindung, Stichtag, Paging und Aktionen.

## AP02a: vorhandener Baustein

`python -m app.graph_cli probe` führt ausdrücklich eine Metadaten-Leseprobe aus.
Ohne diesen Befehl wird weder beim Import noch beim API-Start Graph aufgerufen.
Das Ergebnis enthält nur Erfolg oder neutralen Fehlercode/HTTP-Status. Keine
öffentliche Graph-HTTP-Route, kein Ersatz für die AD-/Session-/CSRF-Prüfung.

Konfiguration: externe geschützte JSON mit ausschließlich `tenant_id`,
`client_id`, `mailbox`; Beispiel in `deploy/graph.example.json`. Zertifikat mit
privatem RSA-Schlüssel separat als PEM. Dateien root-owned, regulär, kein
Symlink, maximal64KiB, kein Gruppen-Schreibrecht oder Weltzugriff. Das
konfigurierte Postfach begrenzt alle URLs. Nur Public-Cloud-Graph-v1.0 über
HTTPS, normale TLS-Prüfung, keine Redirects/Proxy-Übernahme aus Umgebungswerten.
Fortsetzungen müssen zusätzlich zum ursprünglichen Collectionpfad passen.
Tokens nur im Prozessspeicher; keine persistente Cachekonfiguration und kein
Fallback auf Benutzer-/CLI-Identitäten. Geheimnisse niemals als CLI-Wert angeben.

Requestgrenzen: Connect5s/Read20s, JSON2MiB und45s, GET maximal drei Versuche
bei429/500/502/503/504 mit höchstens5s Retry-After. Andere Fehler werden
geschlossen zurückgegeben. POST/PATCH werden nie automatisch wiederholt;
Transportfehler/5xx kennzeichnen einen ungewissen Schreibausgang. Kein upstream
Fehlertext, Token, Schlüssel oder Mailinhalt wird ausgegeben.

Die45s werden im Linux-Hauptthread durch einen POSIX-Requesttimer über Tokenabruf,
Retries und tatsächlichen Empfang begrenzt. Jeder Transportblock wird sofort
geprüft, ohne64KiB-Anwendungspuffer. Der Timerabbruch ist kein vom SDK erneut
versuchbarer Auth-/HTTP-Fehler; Verbindungen werden beim Unwinding geschlossen.
Ein vorhandener fremder Timer, andere Plattform oder Threadnutzung wird geschlossen
abgewiesen. Unterstützte Runtime ist die separate Linux-Betreiber-CLI.

Zusätzlich führt die CLI die gesamte Operation in einem separaten Kindprozess
aus: Probe60s, Scan180s ab Prozessstart einschließlich Initialisierung, Tokenauth,
aller Seiten und Cleanup. Der Elternprozess liest keine Credentials. Bei Ablauf
wird das Kind beendet, nötigenfalls hart getötet; bis zu zwei weitere Sekunden
sind für die Terminierung vorgesehen. Es gibt keinen automatischen Neustart oder
Replay. Dadurch sind auch im nativen Code hängende Aufrufe begrenzt. Ein möglicher
Schreibausgang bleibt ungewiss und muss später persistent abgeglichen werden.
Vier zusätzliche Tests belegen Small-Piece/Slow-Trickle mit kontrollierter Uhr,
blockierenden Read, blockierenden Tokenabruf und Prozessabbruch. Der frühere
64KiB-Pufferfehler ist damit in Korrekturversuch1 adressiert.
F1-Korrekturversuch2 beendet den Download-Empfangstimer ausdrücklich vor der
Übergabe des fertigen Handles. Callerarbeit und verschachtelte spätere Graph-
Aufrufe erben keinen Transporttimer. Zusätzliche Tests belegen dies und den
Downloadabbruch bei kleinen Transportstücken samt geschlossenem Stream.

## Betreiberprofil – noch nicht anwenden

`deploy/compose.graph.yaml` ergänzt ausschließlich einen manuell gestarteten
`graph`-Service im Profil `graph-operator`, UID/GID10001:10001, keine Ports,
kein Neustart/Autostart, schreibgeschütztes Dateisystem und begrenztes tmpfs.
Nur dieser Prozess bekommt GraphJSON und PEM als einzelne RO-Binds. Dauer-API,
Nginx und Migrator behalten ihre bisherige Secretzuordnung. Das Profil enthält
keine echten Pfade, IDs oder Postfachwerte. Für die spätere Bereitstellung sind
ein geprüftes unveränderliches `GRAPH_IMAGE` sowie externe Pfadvariablen nötig.
Rootgeschützte Elternverzeichnisse und Originalschlüssel nicht öffnen.

## Prüfung

Synthetische Transporttests in `backend/tests/test_graph.py`: feste
Postfachbindung/ImmutableId-Header, URL-/Collectionabweichung, Redirect,
401/403, Retrybudget/Retry-After, ungewisser POST-Timeout ohne Replay,
Größenlimit/ungültiges JSON und neutrale Auth-Fehler. Ausführung mit
`python -m unittest discover -s tests -p test_graph.py -v` im Testimage.
Kein echter Graph-Zugriff oder Geheimnis nötig. Lockdateien wurden im isolierten
Linux/Python3.13-Build aufgelöst; bestehende AP01-Versionen bleiben erhalten.

## AP02b: Inbox und Anhänge

`python -m app.graph_cli scan` liest die Inbox mit festem serverseitigem Filter
`receivedDateTime ge 2026-11-30T23:00:00Z` und aufsteigendem Eingangsdatum. Das ist
01.12.2026 00:00 Europe/Berlin. Datum und Offset werden zusätzlich lokal geprüft;
fehlende, ungültige, naive oder frühere Zeiten verhindern jede direkte
Anhangabfrage. Es gibt keinen konfigurierbaren früheren Produktivstichtag.

Alle Nachrichten- und Anhangseiten werden verfolgt, auch leere Zwischenseiten.
Fortsetzungen bleiben unverändert, müssen aber denselben Collectionpfad und
Postfachkontext behalten. ImmutableId-Header bei jedem Request; überlappende IDs
deduplizieren, widersprüchliche Metadaten führen zum Fehler. Erst alle
Nachrichtenseiten sammeln, danach Anhänge lesen; niemals während Paging ändern.
Ein Teilfehler ergibt keinen erfolgreichen vollständigen Scan. Grenzen:
1000Seiten/10000Nachrichten/1000Anhänge je Mail/20000Anhänge je Scan/120s.
Überschreitungen ergeben explizite Fehler. Ein Graph-Paginglauf ist kein atomarer
Snapshot; externe Änderungen können einen neuen vollständigen Lauf erfordern.
Es wird kein Highwatermark fortgeschrieben und kein Vorgang automatisch ausgelöst.

Mailbody, Betreff und Absender werden nicht angefordert. Der CLI-Bericht enthält
nur Vollständigkeit, Stichtag und Zähler. Die Bibliothek hält begrenzte Metadaten
im Prozess. Jede Mail wird auf Anhänge geprüft, auch bei `hasAttachments:false`,
weil Inline-Anhänge darin nicht zuverlässig enthalten sind. Originalname, Größe,
Typ und Inline-Merkmal bleiben erhalten. Datei-/Item-/Referenz-/unbekannte
Anhangtypen werden ausdrücklich unterschieden, ohne Inhaltsklassifikation.

`Mailbox.attachment_content(message_id, attachment_id)` ist eine Bibliotheksfunktion,
kein CLI-Export oder Webdownload. Vor Listen- und Rohbytezugriff wird die echte
Eingangszeit erneut gelesen. Nur File/Item unterstützen Rohbytes; Item ist MIME.
Referenz/unbekannt werden ausdrücklich abgewiesen, externe URLs nie verfolgt.
Der Inhalt landet in einer generierten temporären Datei mit automatisch geschlossenem
Handle, niemals unter dem untrusted Originalnamen. Grenze25MiB/120s pro Download,
Header- und tatsächlich empfangene Größe prüfen, komprimierte HTTP-Antworten
abweisen; keine stille Teilantwort. `attachment.size` ist Metadatum und kann
Overhead enthalten; Rohbytelänge wird nicht unbelegt damit gleichgesetzt.
Keine SMB-Ablage, Formaterkennung, OCR oder Mehrfachanhangentscheidung.

17 synthetische AP02b-Tests decken Grenzzeit/Offsets, direkte
Altmailsperre, überlappende/leere Seiten, fehlerhafte Fortsetzungen/Teilabbruch,
Inline-/Anhangtypen und Paging, Originalbytes von File/Item, sichere temporäre
Pfade, Download-/Encoding-/Collectiongrenzen und geänderten Inboxbestand ab.
F2-Korrekturversuch1: Rohantwort muss200 sein und darf keinen Content-Range
enthalten. 206/204 sowie200mitTeilbereich scheitern ohne Dateiübergabe; reguläre
leere200Datei bleibt erlaubt. Streamabbruch schließt Response und temporären
Handle, neuer Abruf liefert alle Originalbytes. Nach Nachrichten-/Anhangteilfehler
liest ein neuer Scan den vollständigen Bestand; zusätzliche Grenz-/Widerspruchs-
und geänderte-finaler-Guard-Tests verhindern stille Teilresultate.

## AP02c: getrennte persistente Aktionen

Zusätzliche explizite Betreiberbefehle: `ensure-folders`, `flag --message-id <ID>`
und `move --message-id <ID> --destination <Name>`. Kein Aufruf aus `scan`, kein
automatisches Success-Ziel und keine Verarbeitung beim01.12.2026. Die Befehle
geben nur Zähler/Status und neutrale Fehler aus. Konkrete Liveobjekte und Aktionen
gehören in den geprüften Betreiberplan, keine beliebigen produktiven Versuche.

Nur die direkten sichtbaren Inbox-Unterordner Success/Failed/Nachfragen/
Zahlungsavis/unzugeordnet sind Ziele. Vollständiges Listing inklusive verborgener
Ordner, Paging/Überlappungen prüfen. Bestehende IDs wiederverwenden, Namen ohne
Beachtung der Schreibweise abgleichen; Mehrdeutigkeit, verborgene gleichnamige
oder falsche Eltern stoppen. Keine Löschung/Umbenennung. Konkurrenz innerhalb
der Anwendung wird über die DB-Absicht serialisiert. Externe Ordneranlagen sind
keine atomare Graph-Transaktion: Mehrdeutigkeit nach POST wird gemeldet, nicht
durch Löschen scheinbar repariert.

`003_graph_actions` folgt exakt auf `002_security_configuration`; nur die Tabelle
`graph_actions` kommt hinzu. Keine Änderung von AP01-Tabellen oder Instanzkennung.
Gespeichert werden Absicht/opaqueIDs, Ziel, Zustand, Lease, Reservierungsanzahl,
Zeit und neutrale Fehlercodes; keine Mailinhalte, Token, Zertifikate oder Schlüssel.
IDs bleiben case-sensitive über ihren Hashschlüssel und Python-Vergleich.

Vor jeder Absicht: DB-Insert/Rowlock, feste Zielbindung, vor Netzwerkaufruf
durabel höchstens eine Schreibreservierung. Lease300s verhindert konkurrierende
Ausführung während des maximal182s langen CLI-Aufrufs. Keine DB-Transaktion
bleibt über HTTP offen. Zustände pending/sending/checking/unknown/done/
operator_required. Nach Timeout, verlorener Antwort oder Prozessabbruch wird
zuerst der tatsächliche Zustand gelesen. Bereits angewandte Änderungen abschließen,
bei nicht beobachtbarem Ausgang nur weiter abgleichen; bei bekannt nicht erreichtem
Ziel `operator_required`, niemals automatisch erneut POST/PATCH senden. Ein Crash
vor dem tatsächlichen ersten Schreiben kann deshalb bewusst Betreiberklärung
erfordern. Es gibt weder automatische Reservierungsrücksetzung noch Exactly-once-
Zusage. Ein widersprüchliches späteres Move-Ziel ersetzt keine bestehende Absicht.

Nachricht vor jedem direkten Move/Flag erneut über immutableID lesen und echten
Stichtag prüfen. Move nur aus Inbox ins benannte geprüfte Ziel oder bereits dort
als erledigt bestätigen; Flag nur in Inbox/bekannten Zielordnern. Flag setzt nur
flagStatus=flagged, vorhandene flagged bleibt bestehen, complete wird nicht
zurückgesetzt. Schreibantwortbody wird verworfen und Erfolg durch minimale GETs
abgeglichen; stabile IDs ermöglichen Wiederaufnahme nach dem Verschieben. Andere
Markierungen/Lesestatus werden nicht gepatcht. Kein blindes Schreibretry.

Profil `graph-operator` bleibt für `graph` ohne DB-Netz/Secret. Separates Profil
`graph-actions-operator` enthält `graph-actions` mit GraphJSON/PEM und DB-Passwort,
Netzenweb/database, sowie `graph-migrate` ausschließlich mit DB-Passwort und
internaldatabase-Netz. Beide manuell, UID10001, ohnePorts/Restart. Migrator hat
keinen Graph-/LDAP-/TLS-Bind und zeigt standardmäßig nur `current`.

Nach REVIEW, Betreiberbackup und eindeutigem vorherigen002-Stand: neuen Migrator
mit festem Image und `upgrade 003_graph_actions` ausdrücklich ausführen. Danach
`current`/Instanzkennung/alteAPI-Readiness prüfen. Dauer-API und Web können auf ihren
vorherigen Images bleiben; echte isolierte MariaDB bestätigt deren Kompatibilität
mit003. Niemals alten Migrator gegen003 ausführen. Destruktiver Downgrade ist
gesperrt, um ungewisse Aktionen nicht zu verlieren. Rückweg ist das vorherige API-
Image bei erhaltener additiver Tabelle; ein DB-Restore braucht eigenen Betreiberplan
und Abgleich aller eventuell bereits ausgeführten Graph-Aktionen.

Prüfstand:14 Aktionsfälle, davon echte MariaDB-Konkurrenz mit Rowlock. Insgesamt
65Backendtests auf isolierter MariaDB12.3 bestanden, keine übersprungenen Fälle.
Netzloser Lauf65Fälle mit einem ausdrücklich übersprungenen MariaDB-Locktest.
`scripts/test-graph-mariadb.sh` erweitert den vorhandenen isolierten Runner:
Revision001→002_security_configuration→003_graph_actions zweimal, UUID-Erhalt,
separate Prozesse für persistierte Reservierung/Reconciliation/Bestätigung,
Uvicorn/Session-/Konfigurationspersistenz und vorheriges AP01-API auf003.
Nur neue temporäre Testressourcen; keine Kunden-DB oder echten Graph-Secrets.

Live-Ordneranlage, produktive Migration und spätere begrenzte synthetische
Mutationsproben erfolgen ausschließlich nach festem Review-/Betreiberplan.
