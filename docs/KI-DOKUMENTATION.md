# KI-Dokumentation

Stand: 8. November 2026. Lebende Markdown-Dokumentation, noch kein Abschlussbericht.

## Wiedereinstieg

1. [Arbeitsregeln](../AGENTS.md) lesen.
2. [Anforderungen](ANFORDERUNGEN.md) und [Arbeitsplan](ARBEITSPLAN.md) abgleichen.
3. Tatsächlichen Git-Stand, Arbeitsbaum und den konkreten ORGA-Auftrag prüfen.
4. Nur das zugewiesene Paket bearbeiten; Ergebnisse und Prüfungen dokumentieren.

## Aktueller Stand

- Repositorygrundstand und geprüfte SSH-/SMB-Vorbereitung vorhanden.
- AP00 ausdrücklich freigegeben und begonnen; Graph-App registriert,
  Zertifikatsanmeldung und begrenzte Mailrechte noch einzurichten/zu prüfen.
- DEV und REVIEW durch ORGA angelegt; interne Zuordnungen separat geführt.
- AP01 bis AP10: nicht begonnen und noch nicht freigegeben.
- Keine Anwendung, Datenbankstruktur oder produktive Verarbeitung implementiert.
- Keine Testmail aus dieser Vorbereitung versendet.
- Keine Betriebs- oder Wiederherstellungsprüfung als bestanden behaupten.

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

Technikbereitschaft abwarten. Danach beginnt DEV mit AP01a gemäß konkreter
ORGA-Übergabe. Implementierungs- und Prüfbefehle erst dokumentieren, sobald sie
tatsächlich existieren und ausgeführt wurden. Keine erfundenen Startanweisungen.

## Fortschreibung je Unterpaket

Paket, Commit, Ergebnis, passende Prüfung, Fehlerstatus, geänderte Invarianten
und nächsten Schritt ergänzen. Für Review einen festen Commit sowie bei Fehlern
Reproduktion und Versuchszähler angeben. Finale Markdown-Fassung in AP09c prüfen.
