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

## Noch ausstehend

AP02b ergänzt vollständiges Paging und begrenzte Anhangdownloads mit unveränderlichem
Stichtag01.12.2026 Europe/Berlin =30.11.2026 23:00 UTC. AP02c ergänzt getrennte
persistente Folder-/Move-/Flag-Absichten und additive DB-Revision003.
Diese Funktionen sind in diesem ersten Lieferstand noch nicht vorhanden.
Live-Ordneranlage, echte Leerabfrage und spätere begrenzte synthetische
Mutationsproben erfolgen ausschließlich nach festem Review-/Betreiberplan.
