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
