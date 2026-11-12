# Separate manuelle Testquelle

Dieser zusätzliche AP03-Betreiberweg verwendet dieselbe vorhandene Graph-v1.0-
Integration und Zertifikatsanmeldung wie AP02. Keine weitere Plattform oder
kostenpflichtige API. Eigener Adapter ist erforderlich, um ältere Testmails
ausschließlich aus einem bestätigten Testordner zu lesen und Schreibwege technisch
auszuschließen. Er ist kein Produktivfilter-Schalter und kein Hintergrunddienst.

## Feste Bindung und Leseschutz

`app.test_source` akzeptiert ausschließlich einen `ReadOnlyGraphClient`. Dieser
weist jede Graph-Methode außer GET und jeden Requestbody vor Authentisierung oder
Transport zurück; auch der geerbte Schreibaufruf ist gesperrt. Der eigenständige
Downloader enthält keine Actions-/Journal-/DB-/LDAP-/Parsermodule und keine
entsprechenden Abhängigkeiten. Die Tokenbeschaffung beim Identitätsanbieter ist
weiterhin Teil der bestehenden Zertifikatsanmeldung, keine Graph-Schreibaktion.

Das rootgeschützte Binding enthält exakt `mailbox`, `folder_id`, `parent_id`, siehe
`deploy/test-source.example.json`. Die Mailbox muss mit der vorhandenen geschützten
Graph-Konfiguration übereinstimmen. Keine freie Mailbox-/Ordner-/URL-Eingabe in der
CLI und keine automatische Ordneranlage. Ordner heißt exakt Test, hat die gebundene
Parent-ID und ist der einzige entsprechende Name unter diesem Parent; versteckte
Unterordner werden bei dieser Eindeutigkeitsprüfung berücksichtigt. Andere
Vorkommen von Test in anderen Zweigen werden nicht automatisch ausgewählt.

Vor Nachrichtenabfragen und jeder Anhangseite wird die Bindung erneut geprüft.
Direkter Nachrichtenzugriff prüft ID und tatsächlichen Parent. Vor dem Rohdownload
erfolgt die Prüfung erneut. Nachrichtenseiten, Attachmentseiten und Ordnerseiten
sind vollständig zu lesen; NextLinks müssen bei Origin, Mailbox und Collection
bleiben. Kein beliebiges erstes Suchergebnis, kein Wechsel in Inbox/Unterordner und
keine Verarbeitung aus einem bereits gelesenen Teil bei späterem Fehler. Graph
bietet dabei keine atomare Sperre gegen eine parallel unmittelbar nach der Prüfung
verschobene Nachricht; die erneuten Parentprüfungen begrenzen dieses Zeitfenster.

Der Eingangsstichtag ist nur Metadatum dieser separaten Testquelle. Unverändert
bleiben AP02-Inbox-/Download-/Move-/Flag-Guards und `2026-11-30T23:00:00Z`. Tests
lesen dieselbe Vorstichtagsnachricht im gebundenen Testpfad und weisen sie über
die vorhandene produktive Mailboxfunktion weiterhin ab.

## Ressourcen und Datenfluss

Maximal50 Nachrichten,100 Anhänge je Nachricht,200 Anhangmetadaten pro Scan,
20 Seiten pro Collection,120s Collection-/Downloadbudget,25MiB je Datei,
180s gesamte Source-Operation im überwachten Unterprozess. Herkunfts-/JSON-/HTTP-
Deadlinegrenzen aus AP02 bleiben erhalten. Nur fileAttachment-Rohbytes; Item- und
Referenzanhänge bleiben ausdrücklich unsupported. Inline und Dateisuffix/MIME
entscheiden nicht über den Dateiinhalt. Keine Namen als Pfade oder Shellargumente.

Downloader: UID10001,256MiB RAM ohne zusätzlichen Swap,1CPU/64PIDs, read-only,
32MiB tmpfs, init, capdrop/no-new-privileges, nur Graphnetz und drei explizite
geschützte Konfigurations-/Zertifikatsbinds plus privater Übergabeordner. Keine DB,
SMB-Mounts oder Docker-Socket im Container. Abhängigkeiten separat gepinnt mit
denselben Graph-/Azure-Versionen wie AP02; `pip check` geprüft.

`deploy/run-test-source.py` läuft manuell als Linux-Betreiber mit Docker-Recht.
Es prüft rootgeschützte Betreiberdateien und unveränderliche Image-IDs. Der
Classifier-Pin muss exakt zur geschützten Pin-Envdatei passen. Der Host erzeugt ein
privates temporäres Verzeichnis im lokalen `/dev/shm`, UID10001/0700. Downloader
schreibt nur `document` mit0400, zunächst privat und nach SHA-/Längenprüfung ohne
Überschreiben eines vorhandenen Ziels. Der Classifier startet erst nach Ende des
Downloaders und erhält ausschließlich diese eine Datei RO, network:none und
keine Graphdateien. Das bestehende geprüfte Classifierprofil wird verwendet.

Normales Ende, Fehler, Container-/CLI-Timeout und SIGTERM räumen die eigenen
Container, das eigene zufällig benannte Testnetz und private Dateien auf. Ein
fehlgeschlagenes Docker-Cleanup wird nicht als erfolgreicher Operatorlauf gemeldet.
Ein hartes SIGKILL des Hostprozesses kann keine Python-finally-Bereinigung auslösen;
Operator muss in diesem Ausnahmefall eigene Testcontainer und gleichnamige
`/dev/shm/invoice-test-*`-Reste prüfen und gezielt bereinigen. Kein produktiver
Container oder Mount gehört zum Cleanupumfang.

## Kontrollierter Betreiberablauf nach REVIEW

1. Nur die freigegebenen festen Images/Profile verwenden. Erst nach bestätigter
   Testbereitschaft den konkreten Ordner anhand lesender Ordner-Metadaten im
   erlaubten Postfach bestimmen; Parent/Pfad durch Betreiber bestätigen. Nicht
   Inbox/Test annehmen und keinen rekursiven ersten Namensfund automatisch binden.
   Bei mehreren Kandidaten stoppen. Binding rootgeschützt ablegen und die direkte
   ID/Parent-/Eindeutigkeitsprüfung des Readers verwenden.
2. Geschützte Hostpfade setzen: `GRAPH_CONFIG_HOST_FILE`,
   `GRAPH_CREDENTIAL_HOST_FILE`, `TEST_SOURCE_BINDING_HOST_FILE`,
   `TEST_SOURCE_COMPOSE_HOST_FILE`, `CLASSIFIER_COMPOSE_HOST_FILE`,
   `CLASSIFIER_PIN_ENV_HOST_FILE`. Rootbesitz, reguläre Dateien, keine Symlinks,
   keine weltlesbaren Dateien/unerlaubten Schreibrechte. Bestehende freigegebene
   Classifier-Betreiberdateien weiterverwenden; kein neuer C-Build erforderlich.
3. `python3 deploy/run-test-source.py scan --source-image sha256:<reader-id>
   --classifier-image sha256:<reviewed-classifier-id>` liefert nur neutrale
   Fall-/Anhangnummern, Art/Inlinekennzeichen und Bytegrößen. Keine Betreffzeilen,
   Absender, Dateinamen, Nachrichtentexte oder Graph-IDs ausgeben.
4. Einen begrenzten expliziten Fall wählen:
   `python3 deploy/run-test-source.py fetch --case 1 --attachment 1
   --source-image sha256:<reader-id> --classifier-image sha256:<reviewed-classifier-id>`.
   Nummern sind nach Empfangszeit/ID beziehungsweise Anhang-ID geordnet. Bei
   verändertem Testbestand neu scannen; Nummern sind kein dauerhaftes Journal.
5. Nur Fallnummer, Kategorie/Status, neutralen Grund und Original-SHA berichten.
   Fehler oder Mehrdeutigkeit bleiben Failed. Keine Texte/Rohdateien nach Windows,
   Git oder in Berichte übernehmen. Cleanup und unveränderte Originalhashes prüfen.
   Keine Move-/Flag-/Sendaktion, DB-/Journal-/SMB-Anbindung oder Folgeautomatik.

Direkte Reader-CLI für geschützte Betreiberumgebungen: `scan` oder `fetch` mit
demselben Nummernpaar; optional exaktes Nachrichten-/Anhang-ID-Paar. Keine Ordner-
oder Mailboxparameter. Feste Containerpfade `/run/importer/graph.json`,
`/run/secrets/graph_credential`, `/run/importer/test-source.json`, `/output`.

## Tatsächliche Nachweise und Grenzen

20 synthetische Transport-/Operatortests prüfen GET-only vor Token/HTTP, feste
Mailbox/Ordner/Parent/Eindeutigkeit, vollständige Ordner-/Nachrichten-/Anhangseiten,
fremde IDs/Collections/Origins, Bewegungen vor jeder Anhangseite/Rohabfrage,
Vorstichtagsgrenze, echte blockierende Downloaddeadline, Ressourcen-/Teilantwort-
und Redirectfehler, neutrale Ausgabe,0400 und Erhalt vorhandener Dateien.
Operatorbefehle und Cleanup werden gezielt simuliert; keine echte Kundenprobe
daraus ableiten. Separater echter Zwei-Container-Nachweis überträgt eine öffentliche
KoSIT-XML über den echten Downloader mit synthetischem HTTP-Transport an das feste
netzlose C-Image, prüft Hashgleichheit/Kategorie und entfernt die private Übergabe.

Quellen: [Graph-Ordner](https://learn.microsoft.com/en-us/graph/api/mailfolder-get?view=graph-rest-1.0),
[Unterordner inklusive versteckter](https://learn.microsoft.com/en-us/graph/api/mailfolder-list-childfolders?view=graph-rest-1.0),
[Rohanhänge](https://learn.microsoft.com/en-us/graph/api/attachment-get?view=graph-rest-1.0).
Noch keine Kunden-Erkennungsqualität aus synthetischen Fällen ableiten.
