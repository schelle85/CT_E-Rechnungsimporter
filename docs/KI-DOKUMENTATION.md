# KI-Dokumentation

Stand: 8. November 2026. Lebende Markdown-Dokumentation, noch kein Abschlussbericht.

## Wiedereinstieg

1. [Arbeitsregeln](../AGENTS.md) lesen.
2. [Anforderungen](ANFORDERUNGEN.md) und [Arbeitsplan](ARBEITSPLAN.md) abgleichen.
3. Tatsächlichen Git-Stand, Arbeitsbaum und den konkreten ORGA-Auftrag prüfen.
4. Nur das zugewiesene Paket bearbeiten; Ergebnisse und Prüfungen dokumentieren.

## Aktueller Stand

- Stand12.11.2026: AP00 abgeschlossen; AP01 vollständig durch den Kunden abgenommen.
- AD-Kennwortanmeldung bleibt bestehen; SSO wurde verworfen.
- AP02a–c hat ausdrückliches Go und wird auf dev/ap02 entwickelt.
- AP02a: Azure Identity1.27.0/HTTPX0.28.1, geschützter Zertifikatsclient und manuelles
  Betreiberprofil vorhanden; isolierte Tests, keine Kundenbereitstellung.
- Keine neuen Graph-Secrets in Dauer-API/Nginx/Migrator; ausschließlich Graph-CLI.
- AP02b: Paging/Stichtag/Anhangmetadaten und begrenzte Rohbytefunktion implementiert,
  isoliert geprüft; reale gefilterte einmalige Leerabfrage0/0 durch ORGA bestätigt.
- AP02c: getrennte persistente Folder-/Move-/Flag-Aktionen implementiert und auf
  isolierter MariaDB geprüft. Revision003_graph_actions, kein produktiver Schemawechsel.
- 65Backendtests auf echter isolierter MariaDB bestanden; vorherige API kompatibel
  mit additivem003-Schema, kein alter Migrator gegen003. Operatorvertrag im AP02-Dokument.
- Keine Klassifikation, SMB-Ausgabe, Benachrichtigung oder automatische Verarbeitung.
- AP03+ bleibt ohne Go. Kein vollständiger VM-/Offsite-Restore nachgewiesen.
- Aktueller Vertrag, Grenzen und Prüfbefehle: [AP02-Graph](AP02-GRAPH.md).

## Rollen

ORGA koordiniert und verwaltet Lieferstände. DEV implementiert. REVIEW prüft und
übernimmt ungelöste Fehler nach maximal fünf DEV-Korrekturversuchen. Fehlversuche
werden nicht durch Modellwechsel oder Aufteilung desselben Fehlers zurückgesetzt.
Modellfreigaben und interne Chatzuordnung werden außerhalb dieses öffentlichen
Repositorys durch ORGA gesteuert. Keine eigenständigen Zusatzagenten starten.

## Geplante Architektur

Python-Importdienst/API, TypeScript-Web, lokale persistente MariaDB, Linux/Docker
Compose. Vorhandene AD-Konten über LDAP, Graph-Postfachzugriff und Host-SMB-Mounts.
Geheimnisse/Kundenwerte separat; öffentliche Beispiele ausschließlich mit Platzhaltern.

## Fachliche Invarianten

- Nur das vorgesehene Postfach und Mails ab dem Stichtag verarbeiten.
- Altmails unangetastet lassen.
- Formaterkennung genügt; keine zusätzliche Vollvalidierung einführen.
- ZUGFeRD als Original-PDF ablegen; DMS-Import erfolgt kundenseitig.
- Jede relevante Anlage kategorisiert ablegen, andere ignorieren.
- Name/Bytegröße bestimmen Dubletten nur innerhalb der aktuellen KW.
- Namenskonflikte ohne Dublette mit Zusatz lösen; nicht überschreiben.
- Erfolg erst nach vollständiger erforderlicher Ablage verbuchen.
- Mehrere Anhänge markieren, Signaturbilder nicht mitzählen.
- Leserrechte serverseitig erzwingen; Verwaltungsänderungen protokollieren.
- Zwei Jahre aktive Protokolle, danach Webarchiv; keine zusätzliche Mailpflege automatisieren.
- Warnungen nur über Graph, solange möglich; kein Ersatzversand.
- Ein Neustart oder Rollback darf keine unbemerkte Doppelverarbeitung auslösen.

## Bestehende Bausteine

Zu prüfende Kandidaten: Microsoft Graph SDK/Azure Identity, Python `factur-x`,
`pdfplumber`, bei Scanbedarf Tesseract/OCRmyPDF, LDAP-Bibliothek und FastAPI.
Versionen, Lizenzketten und tatsächliche Formatabdeckung im jeweiligen DEV-Paket
prüfen und festhalten. KoSIT/Mustang wurden recherchiert, sind wegen des auf
Erkennung begrenzten Umfangs keine zwingenden zusätzlichen Komponenten.

Primärquellen: [Graph SDKs](https://learn.microsoft.com/en-us/graph/sdks/sdks-overview),
[factur-x](https://github.com/akretion/factur-x),
[pdfplumber](https://github.com/jsvine/pdfplumber),
[OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF),
[LDAP-Bind](https://ldap3.readthedocs.io/en/latest/bind.html).

## Offene Punkte

- Mailabschluss bei neuen Anhängen und Dubletten in derselben Mail.
- Ende der Warnserie nach geprüftem gültigem Zertifikatswechsel.
- Tatsächliche Anschlussinformationen, SMB-Sicherungsumfang und Betriebszuständigkeiten.

## Nächster Schritt

AP02 in abgegrenzten festen Commits liefern und prüfen. Live-Ordneranlage,
Schemaänderung und Betreiberbereitstellung erst nach REVIEW/ORGA. Alte AP01-
Zwischenstände in Paketdokumenten sind historische Belege. Prüfergebnisse,
Image-IDs und tatsächliche Bereitstellung getrennt benennen; kein Test schaltet
Verarbeitung frei. Pro Fehler höchstens fünf gezielte DEV-Korrekturversuche.
