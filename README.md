# CT E-Rechnungsimporter

Geplanter Importdienst für Rechnungsanhänge aus einem Microsoft-365-Postfach über
Microsoft Graph. Erkannte E-Rechnungen, gewöhnliche Rechnungs-PDFs und Zahlungsavise
werden kategorisiert in einer SMB-Ablage gespeichert. Eine interne Weboberfläche
zeigt Verarbeitung, Fehler und Dubletten.

## Projektstatus

Stand: 7. November 2026. Repository und Projektplanung werden vorbereitet.
**Es gibt noch keine implementierte Anwendung und keine produktive Installation.**
Die Entwicklung beginnt nach Bereitstellung der vorgesehenen VM einschließlich SMB.

## Vorgesehener Aufbau

- Linux-VM mit Docker Compose.
- Python für Importdienst und API, TypeScript für die Weboberfläche.
- MariaDB mit persistenten Daten auf der VM.
- Anmeldung mit bestehenden Windows-AD-Konten über verschlüsseltes LDAP.
- Gruppenbasierter Vollzugriff oder Lesezugriff.
- Microsoft Graph für Postfachzugriff und automatische Benachrichtigungen.
- SMB-Mounts auf dem Host für Dokumentablage und vorhandene HTTPS-Zertifikate.

Bestehende frei lizenzierte Bibliotheken werden vor Eigenimplementierung geprüft.
Graph-Authentifizierung, PDF/XML-Parser und OCR werden nicht neu entwickelt.

## Unterlagen

- [Anforderungen](docs/ANFORDERUNGEN.md)
- [Arbeitspakete](docs/ARBEITSPLAN.md)
- [Dokumentationslieferungen](docs/DOKUMENTATIONSPLAN.md)
- [KI-Dokumentation und Wiedereinstieg](docs/KI-DOKUMENTATION.md)
- [Arbeitsregeln für beteiligte KI-Chats](AGENTS.md)

Diese Unterlagen beschreiben den vereinbarten Umfang und kennzeichnen noch offene
Punkte. Eine geplante Funktion ist kein Nachweis ihrer Implementierung.

## Konfiguration und Kundendaten

Dieses Repository ist öffentlich. Es enthält keine echten Zugangsdaten, privaten
Schlüssel, Zertifikatspakete, Postfachinhalte oder kundenspezifischen
Verbindungsinformationen. Beispiele verwenden Platzhalter. Die tatsächliche
Konfiguration und interne Organisationsunterlagen werden separat verwaltet.

## Abschlusslieferungen

Zum Abschluss sind eine Kundenanleitung als PDF, eine technische Dokumentation
für Betreiber und Kunde sowie eine fortgeschriebene KI-Dokumentation als Markdown
vorgesehen. Diese entstehen aus dem tatsächlich implementierten und geprüften Stand.

## AP01-Vorschau

[Synthetische A/B-Oberfläche und Grundgerüst](docs/AP01-PREVIEW.md):
Quellstand und Builds vorhanden; Laufzeit-/HTTPS-Abnahme noch offen.

[AP01 AD-Anmeldung/geschützte Konfiguration – Quell- und Prüfstand](docs/AP01-SECURITY.md).
