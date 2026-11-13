# AP04 – Ablagevertrag und Prüfstand

Stand: 13.11.2026. AP04 ist freigegeben und in Entwicklung; automatische Ablage,
Kundenmigration und Produktivjobs sind nicht aktiviert. AP03 bleibt eingefroren.

`backend/app/storage_plan.py` enthält die reine Planung für unveränderliche
Anhangsdaten. Nur erkannte E-Rechnung/PDF/Zahlungsavis/Mahnung dürfen eine Ablage
planen. Ziel: Kategorie/Kalenderjahr/Monat/KW aus ursprünglichem Maileingang,
umgerechnet nach Europe/Berlin. Monat und KW haben keine führende Null.

Neue Dublettenreservierungen verwenden die aktuelle Berliner ISO-Woche der
Bearbeitungszeit. ISO-Wochenjahr/KW sind unabhängig von Empfangsjahr, Monat und
Kategorie. Fachliche Merkmale sind ausschließlich exakter Originalname und
Bytegröße; Groß-/Kleinschreibung und Unicodezeichen werden dabei nicht verändert.
SHA256 dient nur Integritätsprüfung/Abgleich. Wiederaufnahmen müssen die zuerst
gespeicherte Quellen-/Wochenzuordnung behalten. Ein dauerhaft bestätigter
Ablagebeleg bleibt auch nach Entfernung durch das DMS gültig.

Sichere Blattnamen bis 180 UTF-8-Bytes bleiben erhalten. Ungültige oder problematische
Windowsnamen, Traversal, Separatoren, ADS, Steuer-/Formatzeichen, führende
Punkte/Leerzeichen und abschließende Punkte/Leerzeichen werden durch einen
generierten Namen ersetzt. Eine sichere alphanumerische Endung bleibt erhalten.
Der exakte Originalname bleibt in den unveränderlichen Eingabedaten und später im
Register. Ein Kollisionszusatz steht vor der letzten Endung. Physische
case-insensitive Namenskollisionen sind getrennt vom fachlichen Dublettenschlüssel.

Vorhandene Bausteine: Python/zoneinfo, Linux-CIFS sowie SQLAlchemy/Alembic/MariaDB.
Ein zusätzliches SMB-SDK oder Queue-System hat keine belegte Lücke zu schließen.
`pathvalidate` wurde als vorhandene Dateinamenbibliothek geprüft; die begrenzte
Annahme sicherer Namen mit generiertem Ersatz benötigt keine neue Abhängigkeit.
Die vorhandene DB-Engine und Reservierungsmuster werden im additiven
`storage_operations`-Register samt Migration004 wiederverwendet; Graphzustände
und Migration003 bleiben unverändert. Noch keine Kundenmigration ausgeführt.
Quellenidentität und fachliche Wochenreservierung sind getrennt eindeutig.
Konkurrenten eines unbestätigten Erstvorgangs warten; erst stored erlaubt duplicate.
Jeder Staging-Owner erhält einen eigenen temporären Namen. Ein persistenter
Übergang nach publishing erlaubt genau einen Publikationsversuch. Nur ein
eindeutig abgelehntes EEXIST erlaubt einmal den reservierten Kollisionsnamen.
Leaseablauf erlaubt nach publishing ausschließlich einen Abgleich.
Ein bekanntes EEXIST bleibt zusätzlich dauerhaft als abgelehnter Versuch erhalten.
Register und Dateischicht sind an dieselbe CIFS-Quelle, denselben Pfad innerhalb
der Freigabe und denselben Stagingbereich gebunden. Ein alter Quellenbeleg darf
bei geändertem Ablagebereich nicht stillschweigend umgedeutet werden.

`store_attachment(store, files, request, input_file)` verbindet Register und
Dateischicht. Rückgaben sind stored, duplicate, busy, failed oder operator_required
mit Aktionsschlüssel, ggf. relativem Ziel und neutralem Grund. Bei Wiederaufnahme
einer unklaren Veröffentlichung reicht ein passendes Ziel allein nicht: eigene
Stagingdatei muss fehlen, Größe/SHA müssen passen und es darf kein bekannter
abgelehnter Versuch vorliegen. Sonst bleibt der Vorgang operator_required.
Das ist eine Bibliothek für den späteren Gesamtpfad; noch kein aktivierter
API-Endpunkt, Operatorprofil, Postfachlauf oder Scheduler.

Als Linux-Dateischicht implementiert, native Prüfung noch offen: vollständiges
Staging auf demselben CIFS-Dateisystem außerhalb des
DMS-Importbereichs, Größe/Hash/Flush prüfen, dann atomar mit
`renameat2(RENAME_NOREPLACE)` veröffentlichen. Kein Copy-/Replace-Fallback. Mount
muss im tatsächlichen Prozessnamespace zur erwarteten CIFS-Quelle gehören.
Stagingausschluss durch das DMS ist vor produktiver Nutzung gesondert nachzuweisen;
ein Punktpräfix ist kein Nachweis. Der Stagingbereich muss ausschließlich dem
Importer gehören; DMS und fremde Writer dürfen ihn weder verändern noch bereinigen.
Eine unklare Veröffentlichung mit anschließend
fehlender Datei darf wegen möglicher DMS-Entfernung weder wiederholt noch als
erfolgreich bestätigt werden. DB und SMB besitzen keine gemeinsame Transaktion.

Lokaler Nachweis: fünf synthetische Testgruppen für Datums-/Wochen-/Namensgrenzen,
exakte Dublettenmerkmale und abgewiesene Eingaben sowie sechs SQLite-Testgruppen
für Reservierung, Parallelität, Ownerwechsel, Kollisionsgrenze und dauerhafte
Quellen-/Dublettenbelege unter Windows/Python3.14. Keine dieser Prüfungen belegt
MariaDB-Sperrsemantik oder CIFS-Verhalten.
Weitere zehn SQLite-/Dateidouble-Testgruppen prüfen den Ablauf einschließlich
Absturz während Staging, vor/nach Rename, sofortiger DMS-Entfernung, verlorenem
DB-Erfolgsbeleg und passendem fremdem Ziel. Ein Alembic-/SQLite-Test prüft additives,
zweimaliges Upgrade und die Sperre gegen destruktiven Downgrade. Zusammen mit dem
Mountfixture-Test bestehen 23 lokale Tests; weitere 5 native Tests sind übersprungen.
Der Mountparser/-Gate besitzt zusätzlich einen synthetischen Test mit fd-/mountinfo-
Fixtures; fünf native Linux-Dateitests werden unter Windows ausdrücklich
übersprungen. Sie prüfen später unter anderem No-replace-Rennen, Flushfehler,
Symlinks und fehlende/falsche Mounts auf lokalem Testdateisystem. Das ersetzt
auch unter Linux keinen tatsächlichen CIFS-Nachweis.
SQLAlchemy 2.1.8 entspricht dem vorhandenen Produktlock; tzdata 2026.6 wurde nur
für die private Windows-Testumgebung verwendet.

Erster nativer Lauf aus fd477fa: alle 28 AP04-Tests unter Linux/Python 3.13.18
bestanden, einschließlich der fünf Dateitests und der Registertests auf isolierter
echter MariaDB 12.3. CLI-Migration001→004 zweimal mit erhaltener Instanz-ID und
Bash-Syntaxprüfung bestanden. Der gesamte Backendlauf war dennoch fehlgeschlagen:
ein bestehender AP03-Operatortest konnte den Helfer im allgemeinen Testimage nicht
importieren (110 Tests, ein Importfehler). AP04-N1, Korrekturversuch1: vorhandenen
Helfer gemäß bestehendem Testquellen-Testimage auch in Dockerfile.test übernehmen.
Keine Helfer-/Erkennungslogik geändert. Gesamtnachprüfung steht aus; kein Gesamt-PASS.
Echte CIFS- und DMS-Betriebsnachweise stehen weiterhin aus. Keine CIFS-Binds oder
Kundengeheimnisse in diesem Lauf, keine Kundenmigration oder API-Umschaltung.

Der vorhandene isolierte Docker-/MariaDB-Runner ist mit
`scripts/test-storage-mariadb.sh` für Schema004 erweitert. Er erzeugt ausschließlich
neue Testressourcen ohne Hostports, prüft wiederholtes Upgrade/Instanz-ID,
Regressionen und Wiederaufnahme in drei getrennten Prozessen. API_IMAGE und
TEST_IMAGE müssen unveränderliche sha256-IDs des festen Quellstandes sein.
Teilweise ausgeführt wie oben; die nach den Tests folgenden Prozess-/HTTP-
Regressionsschritte waren beim ersten Lauf noch nicht erreicht. Kein Aufruf gegen
die Kundendatenbank. Die erste tatsächliche CIFS-Probe braucht vorab Quellreview und
eine separate synthetische Ablage außerhalb der Produktionskategorien.

Primärquellen: [Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html),
[Linux renameat2](https://man7.org/linux/man-pages/man2/rename.2.html),
[pathvalidate](https://pathvalidate.readthedocs.io/en/latest/pages/reference/function.html).
