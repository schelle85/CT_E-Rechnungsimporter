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

Neun zusätzliche synthetische AP02b-Tests decken Grenzzeit/Offsets, direkte
Altmailsperre, überlappende/leere Seiten, fehlerhafte Fortsetzungen/Teilabbruch,
Inline-/Anhangtypen und Paging, Originalbytes von File/Item, sichere temporäre
Pfade, Download-/Encoding-/Collectiongrenzen und geänderten Inboxbestand ab.

## Noch ausstehend

AP02c ergänzt getrennte persistente Folder-/Move-/Flag-Absichten und additive
DB-Revision003. Diese Funktionen sind in diesem Lieferstand noch nicht vorhanden.
Live-Ordneranlage, echte Leerabfrage und spätere begrenzte synthetische
Mutationsproben erfolgen ausschließlich nach festem Review-/Betreiberplan.
