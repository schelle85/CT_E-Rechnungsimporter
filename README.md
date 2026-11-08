# CT E-Rechnungsimporter

![E-Favicon](frontend/public/favicon.svg)

Projekt für den automatischen Import von Rechnungsanhängen aus einem
Microsoft-365-Postfach über Microsoft Graph. Ziel ist die kategorisierte
SMB-Ablage von E-Rechnungen, Rechnungs-PDFs und Zahlungsavisen mit einem
internen Webportal für Protokolle, Fehler und Dubletten.

## Projektstatus

**Stand: 9. November 2026. AP01 ist technisch bereitgestellt; der CEO-Lesetest
steht noch aus. AP01 bleibt bis zu dieser Abnahme offen.**

| Paket | Stand |
| --- | --- |
| AP00 – technische Grundlage | Abgeschlossen: SSH/SMB, Zertifikate und begrenzter Graph-Zugriff einschließlich Testversand geprüft. |
| AP01 – Design und Grundbetrieb | Docker-/MariaDB-/HTTPS-Grundbetrieb und Oberfläche unabhängig geprüft und bereitgestellt. HTTP leitet auf HTTPS um. |
| AP01 – AD und Administration | Echte LDAPS-Anmeldung, Gruppenrechte, sichere Sitzungen, versionierte Einstellungen und Änderungsprotokoll implementiert. Vollzugriffstest durch den Betreiber bestätigt. |
| AP01 – Leserabnahme | Isolierte Rollen-/Browserprüfungen bestanden; tatsächlicher CEO-Lesetest noch offen. |
| AP02 und folgende Pakete | Noch nicht freigegeben. Automatischer Postfachlauf und Rechnungsverarbeitung folgen dort. |

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
- Host-SMB-Mounts für die spätere Dokumentablage und vorhandene TLS-Zertifikate;
  Quellcode und Datenbank liegen auf lokalem VM-Speicher.

Der Zugang erfolgt ausschließlich im Kundennetz beziehungsweise über die
vorgesehene VPN und die konfigurierte HTTPS-Adresse. Tatsächliche Hostnamen,
Konten und Zugangsdaten werden separat verwaltet.

Für den weiteren Ausbau vorgesehen: Graph-Postfachlauf, Formaterkennung/OCR,
SMB-Ablage, Dublettenbehandlung, Mailzuordnung, Benachrichtigungen und Webarchiv.
Bestehende frei lizenzierte Bibliotheken werden vor Eigenentwicklung geprüft.

## Prüfstand

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
der Betreiber hat den Vollzugriff bestätigt, die CEO-Leserabnahme folgt noch.

## Unterlagen

- [Anforderungen](docs/ANFORDERUNGEN.md)
- [Arbeitspakete](docs/ARBEITSPLAN.md)
- [Dokumentationslieferungen](docs/DOKUMENTATIONSPLAN.md)
- [KI-Dokumentation und Wiedereinstieg](docs/KI-DOKUMENTATION.md)
- [Arbeitsregeln für beteiligte KI-Chats](AGENTS.md)
- [AP01: Anmeldung, Konfiguration und Betreiberabläufe](docs/AP01-SECURITY.md)
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
