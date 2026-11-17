# CT E-Rechnungsimporter

![E-Favicon](frontend/public/favicon.svg)

Projekt für den automatischen Import von Rechnungsanhängen aus einem
Microsoft-365-Postfach über Microsoft Graph. Ziel ist die kategorisierte
SMB-Ablage von E-Rechnungen, Rechnungs-PDFs, Zahlungsavisen und Mahnungen mit einem
internen Webportal für Protokolle, Fehler und Dubletten.

## Projektstatus

**Stand: 17. November 2026. AP01 ist durch den Kunden vollständig abgenommen.
AP02a–c ist im vereinbarten Grundlagenumfang technisch abgeschlossen und
bereitgestellt. AP04 ist technisch im isolierten Grundlagenumfang abgeschlossen.
AP05 ist im definierten manuellen Umfang technisch abgeschlossen und bereitgestellt:
Sechs Inboxziele und begrenzter manueller Leerlauf sind belegt.
AP06 mit echten Journalansichten, Korrekturen, technischen Wiederholungen und
PDF-Vorschau ist technisch abgeschlossen. AP07 ist geprüft und bereitgestellt:
Schema 007 sowie API und Web aus derselben festen Quelle sind getrennt bestätigt,
bestehende Instanz, LDAP-Konfiguration und Datenbankdienst erhalten.
AP08 ist im vereinbarten Umfang technisch abgeschlossen und aus
`413095f823702d39b02bc8b3c989b526fdf808d0` bereitgestellt.
Startdienst und fünf Timer sind seit 16.11.2026, 19:44:23 Europe/Berlin aktiv.
Geplante Inbox-/Korrekturläufe mit 0 Quanten sowie je ein Tages-/Wochenbericht
mit Graphannahme 202 sind bestätigt. Kontrollierter Reboot und erster geplanter
TLS-Stundenlauf um 20:00 sind belegt. Der danach um 20:15:08 separat gesetzte
Statusphasenversatz auf Sekunde 20 ist in drei aufeinanderfolgenden automatischen
Zyklen um 20:16:21, 20:17:21 und 20:18:21 mit Status active bestätigt.
Anwendung, Hostskripte und Images bleiben auf der genannten C-Quelle.**

| Paket | Stand |
| --- | --- |
| AP00 – technische Grundlage | Abgeschlossen: SSH/SMB, Zertifikate und begrenzter Graph-Zugriff einschließlich Testversand geprüft. |
| AP01 – Design und Grundbetrieb | Docker-/MariaDB-/HTTPS-Grundbetrieb und Oberfläche unabhängig geprüft und bereitgestellt. HTTP leitet auf HTTPS um. |
| AP01 – AD und Administration | Echte LDAPS-Anmeldung, Gruppenrechte, sichere Sitzungen, versionierte Einstellungen und Änderungsprotokoll implementiert. Vollzugriffstest durch den Betreiber bestätigt. |
| AP01 – Kundenabnahme | Gesamtabnahme nach Kundentermin durch den Betreiber bestätigt. Bestehende AD-Anmeldung bleibt; SSO wurde verworfen. |
| AP02 – Graph und Postfacheingang | Abgeschlossen: echte Zertifikatsanmeldung und gefilterter Leerabruf bestätigt; fünf Inbox-Zielordner samt Wiederverwendung live geprüft. Paging, Anhangabruf und getrennte persistente Aktionen isoliert geprüft; additives Schema003 bereitgestellt. |
| AP03 – Anhänge erkennen | Revision4: Quellprüfung bestanden, separates Runtimeimage gebaut und isolierter Dateinachtest abgeschlossen. Unbekannt sowie Mahnung/Zahlungserinnerung ergänzt. Fachliche Restfälle und Gesamtabnahme bleiben offen. |
| AP04 – SMB-Ablage und Dubletten | Grundlagen technisch abgeschlossen: Quellreview, 115 native Backendtests einschließlich aller 28 AP04-Tests sowie fünf synthetische Fälle auf echtem CIFS bestanden. In AP05 in den gemeinsamen manuellen Pfad integriert. Siehe [AP04-Vertrag](docs/AP04-ABLAGE.md). |
| AP05 – gemeinsamer Verarbeitungspfad | Im definierten manuellen Umfang technisch abgeschlossen. 155 native Backendtests einschließlich 40 AP05-Gruppen, gezielte Ausgabegrenz-/Timeoutprüfung und echter synthetischer CIFS-Handoff bestanden. Schema 005 und sechstes Inboxziel Mahnung bereitgestellt; Scan/manueller Tick bestätigen 0 passende Mails/0 Quanten. Zum AP05-Abschluss blieben API/GUI unverändert. Keine Timer oder produktive Dateipublikation. Siehe [AP05-Vertrag](docs/AP05-PROCESSING.md) und [Runtime](docs/AP05-RUNTIME.md). |
| AP06 – Webprotokoll, Korrektur und PDF-Vorschau | Technisch abgeschlossen und bereitgestellt: echte Journalansichten, generationgebundene Freigabe/Retry, Einstellungen, Archiv und großer PDFdialog. Native006-/Sicherheits-/Konkurrenzprüfungen sowie fünf isolierte Browsergruppen mit sichtbarer Original-PDF bestanden. Kundenmigration auf006, Dienstpins, HTTPS und leeres echtes Journal getrennt zurückgelesen. Siehe [AP06](docs/AP06-WEB.md). |
| AP07 – Berichte und Benachrichtigungen | Technisch abgeschlossen und bereitgestellt aus `5ecfd59270b63947d3f92af98a1b9f8e5a267aeb`, Schema 007. A/B vollständig geprüft, C-Quellenreview, 21 C-Fälle auf MariaDB und acht isolierte HTTPS-Browsergruppen bestanden. Administration→Berichte, Benachrichtigungseinstellungen, feste Vorschau/Testaktion, Verlauf und Zertifikats-/Loginhinweise geliefert. Echte Graph-Zertifikatsanmeldung und genau eine feste Testmail mit HTTP 202/Reservierung 1/getrenntem Statusabgleich bestätigt; Empfang im eigenen Abnahmepostfach nachgewiesen. Zum AP07-Abschluss blieb die Automatik inaktiv. Siehe [AP07](docs/AP07-NOTIFICATIONS.md) und [Betreiberweg](docs/AP07-OPERATOR.md). |
| AP12 – Graph-Zertifikatsrotation und Adminreiter | In Umsetzung. Quellstand bis C7: gebundene Graphfreigabe, Hostübernahme/Rückweg, Bereinigung, Adminreiter, feste Automatik und ausdrückliche Rootzuordnung. Kern B/C1 und C2a-/C2B-R1-Einzelumfänge nativ bestätigt; auf festem C3-Pin zusätzlich Bootstrap, Normalwechsel und expliziter Rückweg gegen synthetische Entra-Gegenstelle. C4–C6 Quellen-/lokaler Review bestanden; C7 lokal geprüft. Weitere native Fehler-/Boot-/Cleanup-/Browser-/Timer-/Zuordnungsnachweise offen. Kundenbetrieb bleibt AP08/Schema007. Siehe [AP12](docs/AP12-GRAPH-ZERTIFIKATSROTATION.md) und [Lieferstand/Übergabe](docs/AP12-UEBERGABE.md). |
| AP08 – Betriebsübergang | Im vereinbarten Umfang technisch abgeschlossen. C-Quelle `413095f823702d39b02bc8b3c989b526fdf808d0` bereitgestellt; Instanz, Schema 007, Konfiguration und DBzustand erhalten. Reale HTTPSübernahme mit folgendem No-op, Notificationvorlauf ohne neue Testmail, aktive Zeitpläne und normale Leerlaufläufe bestätigt. Tages-/Wochenbericht je einmal mit HTTP 202 angenommen. Kontrollierter Wiederanlauf, geplanter TLS-Stundenlauf um 20:00 und drei automatische Statuszyklen nach dem separaten Sekunde-20-Versatz bestanden. Siehe [AP08](docs/AP08-BETRIEB.md). |
| Weitere Pakete | AP09/10/11 ohne Umsetzungs-Go. AP12 ist nach AP08 und vor dem Handbuch in Umsetzung. |

Der begrenzte Titelvariantennachtrag wurde unabhängig geprüft und aus `e49ccdb`
als separates Runtimeimage gebaut. Die zusätzlichen Pre-Notifikations- und datierten
Mahnungsüberschriften wurden im isolierten Dateinachtest bestätigt. Verbleibende
fachliche Restfälle sind davon getrennt; eine Gesamtfreigabe folgt daraus nicht.

Die Mailzielpriorität für gemischte Anhänge ist seit 13.11.2026 fachlich bestätigt;
siehe [Anforderungen](docs/ANFORDERUNGEN.md#mailabschluss-und-fahne). Ihre Umsetzung
ist im gemeinsamen AP05-Verarbeitungspfad implementiert und geprüft.

AP04 liefert die geprüfte Ablagebibliothek und ein additives Ablageregister.
Die anschließende AP05-Integration ist isoliert sowie mit synthetischen Quellen
auf echtem CIFS geprüft. Historische Entnahmeproben prüfen die Wiederaufnahme
anhand bestehender Ablagebelege. DMS-Anbindung, -Konfiguration und -Prüfung liegen
vollständig außerhalb des Auftrags und sind keine AP06-Abnahmebedingung.

AP06 zeigt ausschließlich tatsächlich gespeicherte Journalvorgänge; eine leere
Datenbank ergibt eine leere Ansicht. Die frühere Demo-API ist entfernt.
Die Kundenoberfläche ist inzwischen auf AP07 umgeschaltet. Anmeldung und
Administration verwenden die bestehende AD-Anbindung; die echte AD-Abnahme aus
AP01 bleibt der historische Nachweis. Eine neue tatsächliche Kundenanmeldung
nach AP07 ist nicht nachgewiesen. Ein Empfangsnachweis der Testmail liegt ausschließlich
für das eigene Abnahmepostfach vor. Drei Empfänger sind privat konfiguriert.

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
  Für den geschützten Originalabruf erhält der API-Service zusätzlich genau zwei
  nur lesbare Einzeldateien für Graph-Konfiguration und Zertifikatsanmeldung.
  Für Benachrichtigungen kommt ein eigener, vom LDAP-Konfigurationsschlüssel
  unabhängiger Schlüssel hinzu.
  Der Vorschauprozess erlaubt ausschließlich GET. Der Migrationsdienst erhält
  diese Bindungen nicht; API und Migration erhalten weder CIFS noch Docker-Socket.
- Echte Journalübersicht mit Suche, Filtern und Seitenwahl; Details zeigen Erstbefund,
  aktuellen Befund, Freigaben, Wiederholungen, Ablagebelege und verständliche Fehler.
- Unbekannte Anhänge einzeln ausdrücklich zuordnen; technische Wiederholungen
  getrennt freigeben. Schreibaktionen benötigen Verwaltungsrechte und CSRF-Nachweis.
- PDF-Originale im großen Dialog lesen, im neuen Tab öffnen oder unverändert
  herunterladen. Andere Formate werden als Download angeboten. Zwei gleichzeitige
  Originalantworten bis je 25 MiB, privater Vorschauspeicher mit 128 MiB und feste Fristen.
- Reines Webarchiv nach zwei Kalenderjahren; keine Datenlöschung oder Mailbewegung.
- Administration mit getrennten Berichten, Benachrichtigungen
  und Verbindungseinstellungen. Tages-/Wochen-/freie Berichtszeiträume verwenden
  echte Journalwerte; Lesen erzeugt keinen Versandauftrag. Benachrichtigungen haben
  versionierte Einstellungen, feste Testvorschau und gespeicherten Versandverlauf.
  Zertifikatswarnungen erscheinen im Portal und zusätzlich nach Login für beide Rollen.
  Gespeicherte Zeiten aktivieren keine Jobs; die dauerhafte Aktivierung gehört zu AP08.

### Ergänzter AP12-Quellstand

Die folgenden Funktionen sind implementiert und zur getrennten Abnahme geliefert.
Der Kundenbetrieb verwendet weiterhin den oben genannten AP08-Stand.

- Administration → Graph-Zertifikat mit aktuellem Fingerprint/Ablauf, getrennten
  Prüf-/Versuchs-/Erneuerungszeiten, Überlappung, Bereinigung und Auftragsverlauf.
- GR_CEO liest; GR_Rechnung kann die automatische Erneuerung erlauben und
  „Jetzt erneuern“ auslösen. Der Klick speichert einen gebundenen Auftrag.
  Antwortverlust, Neuanmeldung und mehrere Fenster behalten dessen ursprüngliche UUID.
- Gemeinsamer Rootablauf für manuelle und automatische Anforderungen: lokaler
  Nachfolger, einmalige Registrierung, frische Anmeldung, drei tatsächliche
  Verbraucher und gesonderter Abschlussproof vor dauerhafter Freigabe.
- Feste Tagesprüfung um03:35 Europe/Berlin, Erneuerungsbeginn ab30 Tagen Restzeit
  und minütliche Auftragsbearbeitung. Gespeicherte Einstellung und nachgewiesene
  Hosttimer bleiben getrennte Angaben; veralteter Status ist unbestätigt.
- Überlappung höchstens sieben Tage innerhalb der Altgültigkeit, gezielte
  Bereinigung ausschließlich eigener Altkeys/-dateien und gebundener Rückweg.
  Vorhandenes Altmaterial bleibt bis zur ausdrücklichen Rootzuordnung unverwaltet.

Quellen-/lokale Nachweise sind von nativer Host-/Browserabnahme und Bereitstellung
getrennt. Der vorbereitete [Browserprüfumfang](docs/AP12-BROWSERPRUEFUNG.md) verwendet
das gebaute Frontend und private APIfixtures; er behauptet keine echte ADanmeldung.
Führender [Lieferstand und Betriebsübergabe](docs/AP12-UEBERGABE.md).

Der Zugang erfolgt ausschließlich im Kundennetz beziehungsweise über die
vorgesehene VPN und die konfigurierte HTTPS-Adresse. Tatsächliche Hostnamen,
Konten und Zugangsdaten werden separat verwaltet.

Der gemeinsame manuelle Backendpfad verbindet Graph, Erkennung, SMB-Ablage,
Dubletten und Mailabschluss. Webprotokoll, Korrekturoberfläche und Archiv sind in
AP06 implementiert und isoliert geprüft. Benachrichtigungen sind mit AP07
bereitgestellt. AP08 ist im vereinbarten Umfang technisch abgeschlossen und die
Zeitplanung seit 16.11.2026 aktiviert. Normale Leerlaufläufe, zwei automatische
Berichtsannahmen, Wiederanlauf nach kontrolliertem Reboot und TLS-Stundenlauf um
20:00 sind belegt. Drei automatische Kontrollzyklen bestätigen den anschließend
separat gesetzten Statusversatz auf Sekunde 20.
Bestehende frei lizenzierte Bibliotheken werden vor Eigenentwicklung geprüft.

Der vereinbarte [GUI-/Erkennungsnachtrag](docs/ANFORDERUNGEN.md#webkorrektur-und-erkennungsverbesserung)
gehört zu AP05/AP06: unbekannte Anhänge gezielt zuordnen, freigeben und verarbeiten;
bestätigte Korrekturen für spätere geprüfte Erkennungsregeln nutzen. Oberfläche und
Freigabeschreibwege sind implementiert. Eine Freigabe erzeugt zunächst einen
dauerhaften Auftrag; der vorhandene manuelle Korrekturmodus übernimmt ihn.
Die 5-/15-Minuten-Zeitplanung ist seit 16.11.2026 aktiviert. Einzelne Zuordnungen ändern keine
globalen Erkennungsregeln; AP03 bleibt eingefroren.

## Prüfstand

- AP06: additive Migration 005→006 mit erhaltenen Altzeilen und Instanzkennung,
  aktuelle Sperr-/Retry-/Freigabeprüfungen und geschützte Originalantworten nativ
  geprüft. Fünf vollständige Browsergruppen bestanden: Rollen/PDF/Download/Mobil,
  Freigabe und Retry trotz Antwortverlust/Neuanmeldung, Teilvorgänge/Archiv/Quellfehler
  sowie zwei langsame 25-MiB-Streams über Nginx. Rund 100 MiB Spitze im 128-MiB-Speicher;
  dritter Abruf mit HTTP 503, nach Frist beide Plätze frei und temporäre Dateien entfernt.
  Die echte PDF-Seite wurde im Dialog und neuen Tab visuell geprüft. Isolierte
  Testjournale sind kein Import alter Kundenmails. Die Kundenbereitstellung ist
  getrennt belegt: Schema 006, erhaltene Instanz/Konfiguration und Datenbank,
  neue API/Web, HTTPS im Journalmodus, HTTP-Weiterleitung und Zugriffsschutz.
  Vollständiger Graph-GET-Scan findet weiterhin 0 passende Mails/Anhänge ab dem
  unveränderten Stichtag. Eine erneute tatsächliche Kundenanmeldung für AP06
  wurde nicht durchgeführt; Rollen und Bedienabläufe sind isoliert geprüft.
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
braucht Benutzerklärung. Korrekturoberfläche und Freigabeschreibwege sind in AP06
implementiert und isoliert geprüft.
Der gemeinsame manuelle Wiederaufnahmepfad ist in AP05 implementiert und geprüft.
Zum AP05-/AP06-Abschluss blieb die 5-/15-Minuten-Zeitplanung inaktiv;
die aktuelle Aktivierung gehört zum oben beschriebenen AP08-Stand.

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
