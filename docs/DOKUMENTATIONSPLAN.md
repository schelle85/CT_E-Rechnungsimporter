# Dokumentationslieferungen

Stand: 7. November 2026. Die folgenden Abschlussunterlagen sind beauftragt.
Es existiert noch keine fertige Anwendung; die finalen PDFs werden erst zum
Projektabschluss aus dem geprüften Lieferstand erzeugt.

## AP09a: Kundenanleitung als PDF

Zielgruppe: Anwender und kundenseitige Administratoren.

- Zweck, Zugangsweg und Anmeldung mit dem Firmenkonto.
- Unterschiede zwischen Lesen und Vollzugriff.
- Verarbeitung, Kategorien, Mailordner und Fahne verständlich erklären.
- Protokoll, Fehlergründe, Dubletten und Webarchiv bedienen.
- Erlaubte Einstellungen, Empfänger und Benachrichtigungspläne ändern.
- Fehlgeschlagene Vorgänge kontrolliert wiederholen.
- Grenzen der Formaterkennung, Stichtag und verbleibende manuelle Aufgaben.
- Screenshots erst aus der tatsächlich gelieferten Oberfläche.

Geplante Ausgabe: `docs/handbuecher/Kundenanleitung.pdf`.

## AP09b: Technische Dokumentation für Betreiber und Kunde

- Architektur, Komponenten und eingesetzte Versionen/Lizenzen.
- Deployment, Daten-/Mountzuordnung und Konfigurationsreferenz mit Platzhaltern.
- AD-Anmeldung, Gruppenrechte, Sitzungen und Graph-Rechte.
- Datei-/Mailzustände, Dubletten und Wiederaufnahme bei Teilfehlern.
- HTTPS-Erneuerungsübernahme und Graph-Zertifikatsüberwachung.
- Protokolle, Archiv, Benachrichtigungen und Betriebsüberwachung.
- Vorhandener Backupweg, belegte Wiederherstellung und Zuständigkeiten.
- Start/Stop, Update, Rollback, Fehlersuche und bekannte Grenzen.
- Abnahmefälle mit tatsächlich erbrachten Ergebnissen und offenen Restpunkten.

Geplante Quellen/Ausgaben: `docs/TECHNISCHE-DOKUMENTATION.md` und
`docs/handbuecher/Technische-Dokumentation.pdf`.
Echte Kundenzugänge, Schlüssel und private Konfiguration nicht in die öffentliche
Version aufnehmen. Nötige vertrauliche Betriebsangaben separat übergeben.

## AP09c: KI-Dokumentation als Markdown

`docs/KI-DOKUMENTATION.md` wird ab Repositoryvorbereitung fortgeschrieben.
Sie enthält Wiedereinstieg, führende Dateien, Architekturentscheidungen,
fachliche Invarianten, Paketstatus, Tests, offene Punkte und nächsten Auftrag.
Keine privaten Chatprotokolle oder Geheimnisse übernehmen.

## AP09d: Prüfung und Veröffentlichung

- Lieferstand und Produktcommit eindeutig benennen.
- Dokumentation gegen tatsächliches Verhalten und Konfiguration prüfen.
- Jede PDF rendern; vollständige Seiten auf abgeschnittenen Text, Tabellen,
  Lesbarkeit, Seitenwechsel und Schriftzeichen sichten.
- Quellen und erzeugte Ausgaben konsistent halten, Dateien auf GitHub hochladen.
- Finale Dokumentation nicht allein aufgrund ihrer Erstellung als Betriebsabnahme melden.
