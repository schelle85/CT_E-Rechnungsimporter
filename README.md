# CT E-Rechnungsimporter

![E-Favicon](frontend/public/favicon.svg)

Projekt für den automatischen Import von Rechnungsanhängen aus einem
Microsoft-365-Postfach über Microsoft Graph. Ziel ist die kategorisierte
SMB-Ablage von E-Rechnungen, Rechnungs-PDFs, Zahlungsavisen und Mahnungen mit einem
internen Webportal für Protokolle, Fehler und Dubletten.

## Projektstatus

**Stand: 14. November 2026. AP01 ist durch den Kunden vollständig abgenommen.
AP02a–c ist im vereinbarten Grundlagenumfang technisch abgeschlossen und
bereitgestellt. AP04 ist technisch im isolierten Grundlagenumfang abgeschlossen.
AP05 ist im definierten manuellen Umfang technisch abgeschlossen und bereitgestellt:
Schema005, sechs Inboxziele und begrenzter manueller Leerlauf sind belegt.
Die automatische Rechnungsverarbeitung ist noch nicht aktiviert.**

| Paket | Stand |
| --- | --- |
| AP00 – technische Grundlage | Abgeschlossen: SSH/SMB, Zertifikate und begrenzter Graph-Zugriff einschließlich Testversand geprüft. |
| AP01 – Design und Grundbetrieb | Docker-/MariaDB-/HTTPS-Grundbetrieb und Oberfläche unabhängig geprüft und bereitgestellt. HTTP leitet auf HTTPS um. |
| AP01 – AD und Administration | Echte LDAPS-Anmeldung, Gruppenrechte, sichere Sitzungen, versionierte Einstellungen und Änderungsprotokoll implementiert. Vollzugriffstest durch den Betreiber bestätigt. |
| AP01 – Kundenabnahme | Gesamtabnahme nach Kundentermin durch den Betreiber bestätigt. Bestehende AD-Anmeldung bleibt; SSO wurde verworfen. |
| AP02 – Graph und Postfacheingang | Abgeschlossen: echte Zertifikatsanmeldung und gefilterter Leerabruf bestätigt; fünf Inbox-Zielordner samt Wiederverwendung live geprüft. Paging, Anhangabruf und getrennte persistente Aktionen isoliert geprüft; additives Schema003 bereitgestellt. |
| AP03 – Anhänge erkennen | Revision4: Quellprüfung bestanden, separates Runtimeimage gebaut und isolierter Dateinachtest abgeschlossen. Unbekannt sowie Mahnung/Zahlungserinnerung ergänzt. Fachliche Restfälle und Gesamtabnahme bleiben offen. |
| AP04 – SMB-Ablage und Dubletten | Grundlagen technisch abgeschlossen: Quellreview, 115 native Backendtests einschließlich aller 28 AP04-Tests sowie fünf synthetische Fälle auf echtem CIFS bestanden. In AP05 in den gemeinsamen manuellen Pfad integriert. Siehe [AP04-Vertrag](docs/AP04-ABLAGE.md). |
| AP05 – gemeinsamer Verarbeitungspfad | Im definierten manuellen Umfang technisch abgeschlossen. 155 native Backendtests einschließlich 40 AP05-Gruppen, gezielte Ausgabegrenz-/Timeoutprüfung und echter synthetischer CIFS-Handoff bestanden. Schema005 bereitgestellt, Mahnung als sechstes Inboxziel ergänzt; echter Scan und manueller Tick bestätigen 0 passende Mails/0 Quanten. API/GUI unverändert, keine Timer oder produktive Dateipublikation. Siehe [AP05-Vertrag](docs/AP05-PROCESSING.md) und [Runtime](docs/AP05-RUNTIME.md). |
| AP06 – Webprotokoll, Korrektur und PDF-Vorschau | In Entwicklung: echte Journal-API, generationgebundene Freigabe/Retry und Originalabruf implementiert, gezielte native Nachweise und additives006 isoliert geprüft. Echte Oberfläche mit großem PDFdialog jetzt verdrahtet; Build-/Browser-/Betriebsnachweise noch offen. Kundenoberfläche und Schema005 bleiben bis zur Freigabe unverändert. Siehe [AP06](docs/AP06-WEB.md). |
| AP07 und folgende Pakete | Noch nicht freigegeben. Zeitplanung und dauerhafte automatische Verarbeitung sind inaktiv. |

Der begrenzte Titelvariantennachtrag wurde unabhängig geprüft und aus `e49ccdb`
als separates Runtimeimage gebaut. Die zusätzlichen Pre-Notifikations- und datierten
Mahnungsüberschriften wurden im isolierten Dateinachtest bestätigt. Verbleibende
fachliche Restfälle sind davon getrennt; eine Gesamtfreigabe folgt daraus nicht.

Die Mailzielpriorität für gemischte Anhänge ist seit 13.11.2026 fachlich bestätigt;
siehe [Anforderungen](docs/ANFORDERUNGEN.md#mailabschluss-und-fahne). Ihre Umsetzung
ist im gemeinsamen AP05-Verarbeitungspfad implementiert und geprüft.

AP04 liefert die geprüfte Ablagebibliothek und ein additives Ablageregister.
Die anschließende AP05-Integration ist isoliert sowie mit synthetischen Quellen
auf echtem CIFS geprüft. DMS-Ausschluss und exklusive Importernutzung des
Stagingbereichs wurden vom Betreiber bestätigt. Daraus folgt keine eigene
DMS-Konfigurationsprüfung oder Verarbeitung einer echten Kundenmail.

Die angezeigten Rechnungsvorgänge sind weiterhin **synthetische Beispieldaten**.
Anmeldung und Administration verwenden bereits die tatsächliche AD-Anbindung.
Das blau-weiße E-Favicon ist eingebunden und über HTTPS geprüft.

## Aufbau und verfügbare Funktionen

- Linux und Docker Compose mit getrennten API-, Web- und Datenbankcontainern.
- Python/FastAPI mit SQLAlchemy, PyMySQL und Alembic; React/TypeScript mit
  Vite und Mantine; persistente MariaDB; Nginx als HTTPS-Reverse-Proxy.
- Bestehende Windows-AD-Konten über LDAPS mit CA- und Hostnamenprüfung,
  konfigurierbaren Servern und direkten Gruppenmitgliedschaften.
- Vollzugriff für die Verwaltungsgruppe; Einstellungen und Änderungsprotokoll
  für die Lesergruppe schreibgeschützt. Schreibrechte werden im Backend geprüft.
- Serverseitige Sitzungen, sichere Cookies, CSRF-Schutz, Anmeldebegrenzung,
  Abmeldung und erneute Prüfung von Kontostatus und Gruppenrechten.
- Geschützte LDAP-Konfiguration mit Kandidatenprüfung, Versionshistorie und
  Betreiber-Rückweg. Geheimniswerte werden nicht zurückangezeigt.
- Geprüfte Host-SMB-Mounts für Dokumentablage und vorhandene TLS-Zertifikate;
  Quellcode und Datenbank liegen auf lokalem VM-Speicher.
- Manuelle Graph-Betreiberprofile: Lesen ohne Datenbankzugriff, Aktionen mit
  persistentem Journal und Migration ausschließlich im internen Datenbanknetz.
  Der Graph-Schlüssel ist ausschließlich den benötigenden CLI-Prozessen lesend
  zugänglich; die laufende Web-API erhält ihn nicht.

Der Zugang erfolgt ausschließlich im Kundennetz beziehungsweise über die
vorgesehene VPN und die konfigurierte HTTPS-Adresse. Tatsächliche Hostnamen,
Konten und Zugangsdaten werden separat verwaltet.

Der gemeinsame manuelle Backendpfad verbindet Graph, Erkennung, SMB-Ablage,
Dubletten und Mailabschluss. Webprotokoll, Korrekturoberfläche, Benachrichtigungen,
Archiv und der dauerhafte automatische Betrieb folgen in den jeweiligen AP.
Bestehende frei lizenzierte Bibliotheken werden vor Eigenentwicklung geprüft.

Der vereinbarte [GUI-/Erkennungsnachtrag](docs/ANFORDERUNGEN.md#webkorrektur-und-erkennungsverbesserung)
gehört zu AP05/AP06: unbekannte Anhänge gezielt zuordnen, freigeben und verarbeiten;
bestätigte Korrekturen für spätere geprüfte Erkennungsregeln nutzen. Oberfläche und
Freigabeschreibwege bleiben AP06. Der gemeinsame manuelle Pfad zur Verarbeitung
bereits freigegebener Korrekturen ist implementiert; seine Zeitplanung ist inaktiv.

## Prüfstand

- AP04: Quellreview bestanden; 115 native Backendtests ohne Fehler oder Skips,
  einschließlich aller 28 AP04-Tests, isolierter MariaDB-Migration/Persistenz und
  API-Kompatibilität. Davon getrennt fünf echte CIFS-Fälle mit synthetischen Dateien
  bestanden: unveränderte Ablage, Dublette, Größenkollision ohne Überschreiben,
  No-replace sowie Wiederaufnahme nach simulierter DMS-Entfernung. Unabhängiger
  Readback und Cleanup bestätigt; Kundencontainer unverändert gesund.
- AP03: Erkennungs-, OCR- und Lesegrenzen synthetisch geprüft. Revision4 einschließlich
  der Abschnittsgrenzen unabhängig im Quellreview bestätigt; separates Runtimeimage
  aus diesem Stand gebaut und im isolierten Dateinachtest verwendet. Originale und
  historische Ergebnisse erhalten. Die verbleibenden fachlichen Zuordnungen brauchen
  weitere Abstimmung; keine allgemeine Erkennungsqualität oder Gesamtfreigabe ableiten.
- AP02: 66 Backendtests auf isolierter MariaDB 12.3 bestanden, einschließlich
  Paging-/Deadline-/Downloadfehlern, Aktionswiederaufnahme und Konkurrenz.
  Additive003-Migration erhält die Instanzkennung; bisherige API bleibt kompatibel.
- Echte Graph-Leseprobe vollständig mit null Nachrichten vor dem festgelegten
  Stichtag. Fünf direkte sichtbare Inbox-Ziele unabhängig geprüft; ein zweiter
  Ordnerlauf verwendet dieselben IDs und abgeschlossenen Journalzustände wieder.
  Live wurden keine Nachrichten verschoben oder gekennzeichnet. Der leere
  Abruf ersetzt keine Paging-/Move-/Flag-Prüfung; diese erfolgte isoliert.
- 20 Backendtests einschließlich Rollen, Sitzungen, CSRF, Kontosperre,
  Rechteentzug, Konfigurationswechsel und TLS-Fehlerpfaden bestanden.
- Vier Node-Tests für den Loginablauf und drei Browserproben für erneuerte
  Voranmeldung sowie die Leseransicht bestanden.
- Echte MariaDB-/CLI-Migrationen, API-Start und Persistenz isoliert geprüft.
- Kundenbereitstellung mit unveränderter Instanzkennung und erhaltenem
  Datenbankcontainer; HTTPS, Weiterleitung, Zugriffsschutz und Cookieflags geprüft.
- SVG-Auslieferung, MIME-Typ, Sicherheitsheader und Favicon-Darstellung bei
  16 und 32 Pixeln geprüft.

Quellstände und technische Bereitstellungsbelege wurden unabhängig unter Astra
geprüft. Isolierte LDAP-/Browsertests ersetzen keine tatsächliche Benutzerabnahme;
der Betreiber hat am12.11.2026 die vollständige Kundenabnahme gemeldet.
Diese Kundenabnahme betrifft AP01. AP03-Quellprüfung, separater Runtime-Nachtest und
fachliche Gesamtabnahme sind getrennte Schritte. Der Classifier-Nachtest hat keine
laufende API-/Web-/Datenbankinstanz ersetzt und keinen Produktivworker gestartet.
Erkannte PDF-/E-Rechnungen sollen künftig automatisch weiterlaufen; nur Unbekannt
braucht Benutzerklärung. Korrekturoberfläche und Freigabeschreibwege folgen in AP06.
Der gemeinsame manuelle Wiederaufnahmepfad ist in AP05 implementiert und geprüft.
Die 5-/15-Minuten-Zeitplanung bleibt inaktiv; dauerhafter Automatikbetrieb ist AP08.

## Unterlagen

- [Anforderungen](docs/ANFORDERUNGEN.md)
- [Arbeitspakete](docs/ARBEITSPLAN.md)
- [Dokumentationslieferungen](docs/DOKUMENTATIONSPLAN.md)
- [KI-Dokumentation und Wiedereinstieg](docs/KI-DOKUMENTATION.md)
- [Arbeitsregeln für beteiligte KI-Chats](AGENTS.md)
- [AP01: Anmeldung, Konfiguration und Betreiberabläufe](docs/AP01-SECURITY.md)
- [AP02: Graph-Vertrag und isolierte Prüfung](docs/AP02-GRAPH.md)
- [AP03: Erkennungsumfang, Isolation und Prüfungen](docs/AP03-RECOGNITION.md)
- [AP03: separate manuelle Testquelle](docs/AP03-TEST-SOURCE.md)
- [AP01: ursprünglicher Vorschauumfang](docs/AP01-PREVIEW.md)

Diese README nennt den aktuellen Gesamtstand. Frühere Prüfstandsangaben in
Paketdokumenten beschreiben die jeweiligen Zwischenstände; detaillierte interne
Abnahme- und Betriebsbelege werden separat geführt.

## Konfiguration und Kundendaten

Dieses Repository ist öffentlich. Es enthält keine echten Zugangsdaten, privaten
Schlüssel, Zertifikatspakete, Postfachinhalte oder kundenspezifischen
Verbindungsinformationen. Beispiele verwenden Platzhalter. Die tatsächliche
Konfiguration und interne Organisationsunterlagen werden separat verwaltet.

## Abschlusslieferungen

Zum Abschluss sind eine Kundenanleitung als PDF, eine technische Dokumentation
für Betreiber und Kunde sowie eine fortgeschriebene KI-Dokumentation als Markdown
vorgesehen. Diese entstehen aus dem tatsächlich implementierten und geprüften Stand.
