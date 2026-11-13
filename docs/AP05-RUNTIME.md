# AP05 – manueller Runtimebetrieb vor Aktivierung

Diese Dateien bereiten einen begrenzten isoliert prüfbaren Lauf vor. Sie ändern die
vorhandene Compose-Anwendung nicht und installieren/aktivieren keinen Timer.
Kundenmigration, reale Mail-/CIFS-Aktionen und spätere dauerhafte Automatik brauchen
den vereinbarten Quellen-/Laufabgleich mit ORGA. AP06-Freigabeerzeugung ist nicht enthalten.

Prüfstand: Vollständiges Image mit unveränderten Classifier-/OCR-Quellen und
Paket-/Modellhashes sowie41Lockversionen geprüft.155Backendgruppen einschließlich
40AP05 ohneFehler/Skips auf neuer isolierterMariaDB bestanden. Separater echter
Handoff mit XML-E-Rechnung, OCR-Rechnungs-PDF und Inlinebild ignoriert, zwei
synthetischen Ablagen und Postmove-Fahne bestanden; späteridle ohneNeupublikation
nach simulierterDMS-/Quellentfernung. Der tatsächliche Host-Cleanuppfad entfernt
einen absichtlich blockierten Container bei skalierter0.5s-Frist; echteCLI ohne
Konfiguration liefert neutralenFehler. KeineCIFS-/Live-Mailwirkung in diesenPrüfungen.
Dienst-/Runtime-Quellreview bestanden. Der Host liest inzwischen schon beim Empfang
begrenzt, akzeptiert exakt65536Bytes und beendet beiÜberlauf/Timeout seine private
Clientprozessgruppe; gezielte native Speicher-/EOF-/Cleanup-Prüfungen bestanden.
Das tatsächliche alte Kundenimage ist zusätzlich auf frischem005 kompatibel.
Zusätzlich hat ORGA den vorhandenen Handoff einmal mit echtem CIFS in einem neuen
exklusiven Testverzeichnis ausgeführt. Zwei bytegleiche Publikationen mit je einem
Versuch, OCR, Inlinebild-Ausnahme, Fake-Graph-Abschluss/Fahne und idle nach
simulierter DMS-Entnahme bestanden. Eigener Readback bestätigt entfernte
Testressourcen und unveränderte Kundencontainer. Keine echte Mail oder Kunden-DB
war Teil dieser Sonde. Der abschließende manuelle Kundenbetrieb wird separat belegt.

## Image und Herkunft

backend/Dockerfile.processing baut auf dem vollständigen eingefrorenen
Classifier-/OCR-Image auf und übernimmt ausschließlich die vorhandene Python-
Backendumgebung aus einem geprüften Backendimage. Beide Buildargumente müssen
angegeben werden. Bei lokalen Tags die aufgelöste unveränderliche Image-ID vor
und nach dem Build prüfen; ein lokales Docker-Image-ID-Argument in FROM ist mit
BuildKit nicht gleichbedeutend mit einem Registrydigest. Zusätzlich Classifier-
Layerpräfix, unveränderte Classifierquellen, native OCR-/Modellhashes und alle
Versionen beider vorhandener Locks im tatsächlichen Resultat prüfen.
Der Build prüft die installierten Lockversionen, benötigt keine neuen Downloads.

Dasselbe resultierende Image wird im Betrieb ausschließlich als sha256:ID an den
Hostoperator übergeben. Der generische API-CMD erleichtert den bestehenden
isolierten Schema-/API-Kompatibilitätstest, startet keinen Server aus dem
Processingoperator: Er überschreibt den Befehl explizit mit processing_cli bzw.
classifier.cli. Keine Änderung der bestehenden API-Compose-Datei.

## Konfiguration und Grenze

processing.example.json enthält die enge Koordinator-Konfiguration. storage_root
im Container ist fest /importer. Stagingausschluss darf nur nach tatsächlicher
Betreiberbestätigung true sein; allein das Beispiel bestätigt keinen DMS-Zustand.
processing-host.example.json benennt vorhandene Hostdateien, die existierenden
Netzwerke und den schon bekannten CIFS-Gruppenwert. Beispiele enthalten Platzhalter.
Keine neue Benutzeranlage oder globale Rechteänderung.

Die freigegebene feste Kopie von run-processing.py und das Hostprofil gehören in
einen root-kontrollierten Pfad. Alle Pfadkomponenten müssen root gehören und dürfen
nicht fremd beschreibbar sein; Konfiguration/Secrets als reguläre Dateien ohne
Weltzugriff, z.B. root:10001/0640 für Containerlesbarkeit. Der Operator importiert
nur die Standardbibliothek, keinen Anwendungscode auf dem Host. Aufruf:
python3 -I -B /etc/invoice-importer/run-processing.py inbox --image sha256:GEPRUEFTE_ID --profile /etc/invoice-importer/processing-host.json
Für Korrekturen dasselbe Kommando mit corrections. Keine Migration im Operator.

Der Koordinator verbindet sich nur mit den explizit angegebenen vorhandenen
Netzwerken und erhält Graphkonfiguration/-credential, DBpasswort und genau den
Import-CIFS-Bind plus seine private Austauschmappe. Nonroot10001, bekannte
zusätzliche CIFS-Gruppe, read-only Root, cap-dropALL, nnp, Init und Grenzen.
Der Classifier startet getrennt mit networknone, ohne Environment-Secrets/DB/CIFS
und mit genau einer RO-Datei /input/document. Kein Docker-Socket im Container,
kein Klassifikations-HTTPdienst. Host-Dockerziel ist ausschließlich der lokale Socket.

## Ein Tick und Wiederaufnahme

select inbox materialisiert zuerst den vollständigen bestehenden Graph-Inboxscan;
nur direkte Inboxquellen mit echtem Empfang ab unverändertem Stichtag werden
registriert. select corrections übernimmt ausschließlich bereits intern freigegebene
Entscheidungen und startet zulässige neue Revisionen. Laufende Korrekturrevisionen
bleiben der Korrekturfälligkeit zugeordnet. Kein Freigabe-CLI und kein Lernschreibweg.

Ein Quantum: advance, bei Bedarf eine opake Datei, credentialfreie classifier.cli,
Rückgabe an dieselbe Mail-/Anhangs-/Owner-/Revisions-/Hashbindung und advance.
Koordinator je180s, Classifier außen150s bei bestehendem120s-Parserlimit;
gemeinsames Arbeitsbudget500s plus höchstens40s für Prozessabbruch/Reap und letztes Cleanup
bleibt unter600s-Quantenlease. Der Operator wiederholt keinen unklaren Befehl.
Bei verlorener Rückgabe später neu claimen und dieselben inneren Journale abgleichen.
Eine begrenzte Parserhandoffstörung wird am gebundenen Anhang als failed gespeichert;
Cleanupfehler brechen den Tick ab. Temporäre Originalbytes nur privat in /dev/shm,
nach jedem Quantum entfernt. Keine dauerhafte Rohdatenablage.

Pro Tick höchstens100Quanten (über --max-quanta weiter begrenzbar), faire Mailauswahl.
Offene Restquanten bleiben im Journal fällig. busy/operator_required wird nicht als
done ausgegeben. Zusammenfassung enthält nur neutrale Statuszahlen, keine Dateinamen,
Findings oder Graph-IDs. Dokumentierte Quell-/Publikationsbelege bleiben in der DB.

## Vorbereitete Planung und Prüfung

Die .example-Systemd-Dateien sind deaktivierte Vorlagen: Eingang alle5Minuten,
Korrekturen alle15Minuten, beide derselbe Hostoperator. Nicht aus dem Repository
installieren/aktivieren, bevor Quellen-, tatsächliche Runtime-, Schema-, Mount- und
Betriebsabgleich erfolgt sind. Dauerhafter Produktivautomatikbetrieb bleibt AP08.
Ein laufender oneshot-Dienst wird von seinem Timer nicht parallel erneut gestartet.

scripts/test-processing-mariadb.sh erweitert den vorhandenen markierten isolierten
Runner auf ein frisches Schema005:001→005zweimal, Metadatenidentität, vollständige
Backendtests, getrennte Prozesspersistenz von Graph/Storage/Processing sowie
API-Neuanlage und altes API auf additivem Schema. Ausschließlich neu erzeugte
Test-DB/Volumes/Netze; keine Kundenparameter oder CIFS. Die Image-Hilfe-/Import-/
OCR-/Versionsprobe muss zuvor am tatsächlichen festen Image bestehen.

