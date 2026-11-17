# Dokumentationslieferungen

Stand: 17. November 2026. Die folgenden Abschlussunterlagen sind beauftragt.
Die Anwendung ist bis AP08 im vereinbarten Umfang technisch abgeschlossen und
bereitgestellt. AP12 für Zertifikatsrotation, zusätzlichen Adminreiter und feste
Automatik ist in Umsetzung. Sein [Quellstand und die Übergabefakten](AP12-UEBERGABE.md)
sind von noch offenen nativen Nachweisen und der Bereitstellung getrennt.
Das vollständige Nutzerhandbuch ist
seit14.11.2026 ein eigenes geplantes AP11. Die finalen Unterlagen entstehen aus
dem geprüften Lieferstand in AP11 beziehungsweise AP09 zum Projektabschluss.

## AP09a: Kundenunterlagen und führende Nutzeranleitung

AP09a übernimmt das vollständige Handbuch aus AP11 als Kundenanleitung. Es wird
eine führende Anleitung gepflegt; die technische Dokumentation ergänzt sie für
den Betrieb. Die frühere geplante separate Kundenanleitung wird damit in AP11
zusammengeführt. AP09 prüft Version, Vollständigkeit und Übergabe des Gesamtpakets.

## AP11: Handbuch zum Produkt

Eigenes Arbeitspaket auf ausdrücklichen Nutzerwunsch vom14.11.2026. Status: geplant,
noch kein AP11-Go und noch kein fertig erstelltes Handbuch. Grundlage ist der
geprüfte Auslieferungsstand nach AP08 und dem eingeplanten AP12.

Zielgruppe: Anwender und kundenseitige Administratoren.

- Zweck, Zugangsweg und Anmeldung mit dem Firmenkonto.
- Unterschiede zwischen Lesen und Vollzugriff.
- Alle Seiten und Bedienelemente mit Zweck und typischem Ablauf.
- Verarbeitung, Kategorien, Mailordner und Fahne verständlich erklären.
- Übersicht, Vorgänge, Suche und Filter sowie Protokoll und Statusanzeigen.
- Unbekannte Anhänge mit PDF-Vorschau prüfen und gezielt zuordnen.
- Korrekturen, Wiederholungen, Dubletten und Webarchiv bedienen.
- Administration → Berichte einschließlich Tages-/Wochenübersichten, Zeiträumen
  und Bedeutung der tatsächlichen Journalzahlen.
- Erlaubte Einstellungen, Empfänger und Benachrichtigungspläne ändern.
- Zertifikatswarnungen, Versandhistorie und unklare Versandausgänge verstehen.
- Nach Lieferung von AP12: Reiter Graph-Zertifikat, Rechte, Erneuerungsstart,
  Wechselstatus und erforderliche Unterstützung erklären.
- Alltagsszenarien, häufige Fragen und typische Fehler mit passenden Handlungsschritten.
- Erwartete Wartezeiten und Zuständigkeiten für Nutzer, Verwaltung und Betreuung.
- Grenzen der Formaterkennung, Stichtag und verbleibende manuelle Aufgaben.
- Inhaltsverzeichnis, verständliche Begriffe, Produktversion und Dokumentstand.
- Bildschirmbilder aus dem geprüften Auslieferungsstand mit neutralen oder
  synthetischen Beispielen; keine Kennwörter oder privaten Mail-/Rechnungsinhalte.

Geplante Quelle: `docs/HANDBUCH-ZUM-PRODUKT.md`.
Geplante Ausgabe: `docs/handbuecher/Handbuch-zum-Produkt.pdf`.
Jeder Bedienweg wird mit der tatsächlich gelieferten Software abgeglichen.
Die PDF wird vollständig gerendert und visuell geprüft. REVIEW prüft Inhalt und
Prüfgrenzen; Kundenrückmeldungen fließen vor der abschließenden Übergabe ein.

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
