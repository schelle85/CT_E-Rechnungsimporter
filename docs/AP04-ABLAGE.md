# AP04 – Ablagevertrag und Prüfstand

Stand: 13.11.2026. **AP04 ist technisch im isolierten Grundlagenumfang abgeschlossen;
Quellreview bestanden.** Schema004 wurde nicht in die Kundendatenbank migriert,
kein Kunden-API-Image gewechselt und kein Job aktiviert. AP03 bleibt eingefroren.

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

Die native Linux-Dateischicht wurde isoliert und auf echtem CIFS mit synthetischen
Dateien geprüft: vollständiges Staging auf demselben CIFS-Dateisystem außerhalb der
Kategorieziele, Größe/Hash/Flush prüfen, dann atomar mit
`renameat2(RENAME_NOREPLACE)` veröffentlichen. Kein Copy-/Replace-Fallback. Mount
muss im tatsächlichen Prozessnamespace zur erwarteten CIFS-Quelle gehören.
Stagingausschluss durch das DMS ist vor produktiver Nutzung gesondert nachzuweisen;
ein Punktpräfix ist kein Nachweis. Der Stagingbereich muss ausschließlich dem
Importer gehören; DMS und fremde Writer dürfen ihn weder verändern noch bereinigen.
Eine unklare Veröffentlichung mit anschließend
fehlender Datei darf wegen möglicher DMS-Entfernung weder wiederholt noch als
erfolgreich bestätigt werden. DB und SMB besitzen keine gemeinsame Transaktion.

## Abgeschlossene Nachweise

Quellreview für Ablagebibliothek und abgegrenzte Probehelfer bestanden.
**115 native Backendtests ohne Fehler oder Skips** aus `c781896`, einschließlich
aller 28 AP04-Tests, unter Linux/Python 3.13.18 bestanden. Sie prüfen unter anderem
Berliner Datums-/ISO-Wochengrenzen, exakte Dublettenmerkmale, unsichere Namen,
konkurrierende Reservierungen, Ownerwechsel, Kollisionsgrenzen, Abbrüche vor/nach
Veröffentlichung, sofortige DMS-Entfernung und fremde passende Zieldateien.
Die fünf nativen Dateitests decken zusätzlich directory-fd-/No-replace-Rennen,
unveränderte Bytes, Flushfehler, Symlinks und fehlende/falsche Mounts ab.

Der vorhandene `scripts/test-storage-mariadb.sh` erzeugte ausschließlich neue
Testressourcen ohne Hostports. Auf echter isolierter MariaDB 12.3 bestanden
CLI001→004 zweimal mit erhaltener Testinstanz-ID, Reservierungsparallelität,
Graph-/Ablagepersistenz in drei getrennten Prozessen sowie API-Neuerzeugung,
Sitzungserhalt und Kompatibilität des bisherigen API-Images. Bashprüfung bestanden;
Testcontainer, Netz und Volume entfernt. Keine Kundendatenbank oder
Kundengeheimnisse eingebunden. API_IMAGE und TEST_IMAGE sind dabei feste sha256-IDs.

**Davon getrennt fünf synthetische Fälle auf echtem CIFS bestanden**, nach
Quellreview durch ORGA ausgeführt, mit unprivilegiertem Writer und ausschließlich
eigener Testablage außerhalb der Produktionskategorien:

1. Normale Veröffentlichung mit unveränderten Bytes und passender Größe/SHA.
2. Gleicher Originalname und gleiche Bytegröße als Dublette ohne Neupublikation.
3. Andere Bytegröße mit eindeutigem Zusatz vor der Endung, ohne Überschreiben.
4. Echtes No-replace-EEXIST gegen das eigene vorhandene synthetische Ziel.
5. Wiederaufnahme und Dublette nach bestätigter simulierter DMS-Entfernung anhand
   des dauerhaften Belegs, ohne erneute Veröffentlichung.

Der Lauf endete mit Exit0 und vollständigem Erfolgsresultat. Unabhängiger
ORGA-Readback bestätigt den korrekten Pfad PDF/2026/11/KW46, das nach der Simulation
fehlende ursprüngliche Ziel und ausschließlich die eigene synthetische
Kollisionsdatei plus den bewusst erhaltenen No-replace-Stagingbeleg. Keine Probe-
oder Diagnosecontainer verblieben. Kundencontainer behalten IDs, Images,
Startzeiten und Neustartzähler; API/DB bleiben gesund. Interne Lauf-/Image-/
Helferpins und Belege werden getrennt vom öffentlichen Repository aufbewahrt.

## Grenze zum Produktivbetrieb

Der Abschluss gilt für den isolierten Grundlagenumfang von AP04. Kunden-Schema004,
API-Umschaltung und Jobs wurden nicht aktiviert. Ein tatsächlicher produktiver
DMS-Stagingausschluss und exklusiver Importerzugriff sind vor Veröffentlichung
im später freizugebenden AP05 durch den Betreiber nachzuweisen. Die separate
Testablage belegt weder diesen Ausschluss noch DMS-Import oder einen vollständigen
Mail-/Verarbeitungspfad. AP05 und folgende Pakete bleiben ohne Go.

Primärquellen: [Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html),
[Linux renameat2](https://man7.org/linux/man-pages/man2/rename.2.html),
[pathvalidate](https://pathvalidate.readthedocs.io/en/latest/pages/reference/function.html).
