# AP06 – Webansichten und berechtigte Originalanzeige

Stand14.11.2026. AP06a–d samt PDF-Vorschau ist freigegeben und in Entwicklung.
Die bestehende Kundenoberfläche ist noch nicht auf AP06 umgeschaltet.
AP03-Erkennung und Dezemberstichtag bleiben unverändert, keine Timeraktivierung.
DMS-Anbindung, DMS-Konfiguration und DMS-Prüfung sind kein Projektumfang.

Erster Teilstand: `ProcessQueries` liest die vorhandenen AP05-Journale und
verknüpft Anhangs-, Freigabe- und Storagebelege. Keine Claims, Klassifikation,
Registrierung oder Graph-/Dateiaktionen aus diesen Leseoperationen.
Serverseitige Suche/Filter, stabile Pagination bis50Vorgänge, Details,
offene Unknown-Anhänge und Status-/Dubletten-/Fehlerzähler sind implementiert.
Anhangsfilter verwenden Exists statt vervielfachender Joins. Abfragen laufen
in einem konsistenten Snapshot, damit alte Mailrevision und neue Anhangswirkung
nicht fälschlich zu einem fertigen Vorgang kombiniert werden.

Archiv ist eine reine Leseauswahl nach der ersten Journalanlage: zwei
Kalenderjahre in Europe/Berlin, exakte Grenzsekunde gehört zur aktiven Ansicht.
29.Februar wird beim Rückgang in ein Nichtschaltjahr auf28.Februar begrenzt.
Daten bleiben vollständig erhalten; keine Löschung oder Mailarchivierung.

Sieben lokale SQLite-Gruppen bestanden: leere echte DB, Zählung mehrerer Anlagen,
Freigabezustände/strukturelle Sperre, erforderliche Mail- und Dateibelege,
begrenzte Filter/Pagination, Archiv/Schaltjahr, unveränderte Journale und echte
Snapshotkonsistenz bei paralleler Revisionsänderung. Kein nativer MariaDB-,
API-/Browser- oder Gesamt-PASS aus diesem Teilstand.

Geplant im laufenden AP06: bestehende AD-/CSRF-Grenzen an echte APIansichten
anbinden; zulässige Unknown-Entscheidungen ausdrücklich freigeben; technischen
Retry nur mit denselben Quellen-/Wirkungskeys und ohne Blindwiederholung;
großer PDFdialog über geschützte Originalroute und vorhandenen Browserviewer.
Keine zusätzliche Viewerbibliothek, kein neues ML und keine neue Plattform.

Nächster Teilstand: GET /api/processes, /api/processes/stats, /api/processes/{key}
und /api/unknown verwenden diese echten Journalprojektionen unter der bestehenden
AD-/Sitzungsgrenze. Die frühere Demo-API entfällt. Bestehende Sicherheitstests
adressieren jetzt /api/processes; drei neue HTTP-Gruppen prüfen echte leere und
gefüllte Journale, beide Rollen, Gruppenentzug und neutrale Eingabefehler.
Syntaxprüfung erfolgt; native HTTP-Ausführung ist für diesen Commit noch offen.

AP06-L1/L2, jeweils gezielter Korrekturversuch1: Der blockierte Mailzustand
operator_required hat jetzt Vorrang vor einer lediglich begonnenen Korrektur.
Der Korrekturbeleg bleibt unverändert. Auswahl, Archivkennzeichen, Leaseanzeige
und Freigabemöglichkeit verwenden pro Abfrage denselben Zeit-Snapshot.
Neun lokale SQLite-Gruppen bestanden, darunter beide gezielten Reproduktionen.
Am vorausgehenden API-Stand17ce54c bestanden native Linux-HTTP-/Sicherheitsprüfungen:
26 unterschiedliche Tests, durch importierte Testklassen49 Ausführungen. Die
Testimports sind bereinigt; kein MariaDB-/Browser-/Deployment-PASS daraus.

AP06-M1: Migration005 verwendet nun ausdrücklich ihre eingefrorenen ursprünglichen
Tabellendefinitionen (processing_schema005). Dadurch fügt ausschließlich006 neue
AP06-Strukturen hinzu. Der vorhandene005-Migrationskettennachweis und weitere
12ProcessingState-Gruppen bestanden lokal; nativer006-Nachweis folgt separat.

Freigabe-/Retryteilstand006: aktuelle Findingkopie und Generation getrennt vom
unveränderlichen Erstbefund; additive Findinghistorie, Retrybelege und versionierte
Websteuerung. Approval und Übernahme prüfen denselben aktuellen Befund samt Hash
und Generation. Webanfragen werden je Request-ID idempotent belegt, auch nach
Übernahme. Freigeber/Zeit stammen vom Server; Absicht, Übernahme und Ergebnis
werden atomar im bestehenden Audit verknüpft. Archiv bleibt schreibgeschützt.

Technischer Retry erzeugt ausschließlich eine Absicht im bestehenden manuellen
Korrekturmodus. Neue Befundgeneration nur nach abgeschlossenem Vorgänger.
Bestehende unklare Wirkungen werden in derselben Revision mit unveränderten Keys,
Receipts und Publikationszählern abgeglichen. Eine vor Publikation gescheiterte
Ablage darf nur mit belegtem Zähler0 und ohne aktiven Storageowner zurück auf
pending; erfolgreiche oder reservierte Veröffentlichungen werden nicht genullt.
Bereits wirksame Kundenzuordnungen bleiben erhalten. Kein Scheduler/Job aktiviert.

GET/PUT /api/admin/processing steuert ausschließlich neue technische Retryfreigaben
und neue Vorschauabrufe. Ein bereits freigegebener Retry bleibt ein dauerhafter
Auftrag. POST-Freigaben/Retry und PUT nutzen vorhandene admin-/Origin-/CSRF-Grenze.
Die Vorschauoption wird mit dem folgenden Originalabrufteil wirksam verdrahtet;
aktuell gibt es daraus noch keine Originaldateiroute oder fertige Oberfläche.

Lokale Nachweise:10 neue Decision-/Migration-/Konkurrenzgruppen,13 bestehende
ProcessingState-Gruppen und9 Projektionsgruppen bestanden. Native006-/MariaDB-
und neue HTTP-Schreibtests stehen am festen Commit noch aus. Kundenschema bleibt005.

NativeLinux/MariaDB zum festen006-Standf3d6e6c: neue Processing-/Testimages offline
gebaut, eingefrorene Classifierlayer unverändert. Frische echte CLI001→006 zweimal
mit gleicher Instanzkennung bestanden.53 gezielte Tests ausgeführt:52PASS,
ein HTTP-Testfehler durch uneinheitliche Testuhren (API real, Consumer eingefroren).
AP06-T1 Versuch1 vereinheitlicht beide Uhren ausschließlich im HTTP-Testfixture;
gezielter nativer Nachweis folgt. Tatsächlicher alter005→006-Pfad noch offen.
