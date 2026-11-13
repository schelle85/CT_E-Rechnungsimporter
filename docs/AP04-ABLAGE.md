# AP04 – Ablagevertrag und Prüfstand

Stand13.11.2026. AP04 ist freigegeben und in Entwicklung; automatische Ablage,
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

Sichere Blattnamen bis180 UTF8-Bytes bleiben erhalten. Ungültige oder problematische
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
Der Mountparser/-Gate besitzt zusätzlich einen synthetischen Test mit fd-/mountinfo-
Fixtures; fünf native Linux-Dateitests werden unter Windows ausdrücklich
übersprungen. Sie prüfen später unter anderem No-replace-Rennen, Flushfehler,
Symlinks und fehlende/falsche Mounts auf lokalem Testdateisystem. Das ersetzt
auch unter Linux keinen tatsächlichen CIFS-Nachweis.
SQLAlchemy2.1.8 entspricht dem vorhandenen Produktlock; tzdata2026.6 wurde nur
für die private Windows-Testumgebung verwendet. Linux-, echte MariaDB-/CIFS-
und DMS-Betriebsnachweise stehen aus. Keine Kundenverbindung für diese Tests.

Primärquellen: [Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html),
[Linux renameat2](https://man7.org/linux/man-pages/man2/rename.2.html),
[pathvalidate](https://pathvalidate.readthedocs.io/en/latest/pages/reference/function.html).
