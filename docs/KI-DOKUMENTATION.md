# KI-Dokumentation

Stand: 13. November 2026. Lebende Markdown-Dokumentation, noch kein Gesamtabschlussbericht.

## Wiedereinstieg

1. [Arbeitsregeln](../AGENTS.md) lesen.
2. [Anforderungen](ANFORDERUNGEN.md) und [Arbeitsplan](ARBEITSPLAN.md) abgleichen.
3. Tatsächlichen Git-Stand, Arbeitsbaum und den konkreten ORGA-Auftrag prüfen.
4. Nur das zugewiesene Paket bearbeiten; Ergebnisse und Prüfungen dokumentieren.

## Aktueller Stand

- AP00/AP02 technisch abgeschlossen, AP01 durch den Kunden abgenommen.
- AD-Kennwortanmeldung bleibt; SSO verworfen. Schema003 und fünf Inboxziele bereit.
- AP03-Revision4 samt Titelvariantennachtrag: Quellreview auf `e49ccdb` bestanden,
  B-F1 bleibt nach Versuch3 geschlossen. Separates Runtimeimage gebaut und isolierter
  abschließender Dateinachtest durchgeführt; weitere fachliche Restfälle bleiben offen.
- `unknown` für lesbare unklare Zuordnung; Mahnung umfasst Zahlungserinnerung.
  Titel-/Label-/Avisregeln und Übergabeverträge geprüft. Fachliche Restfälle bleiben offen.
- Bestehende API/Web/DB und Produktivprofile unverändert; keine automatische Verarbeitung,
  echte Mailmutation oder Frontend-/Jobaktivierung aus dem Dateinachtest ableiten.
- Historische Ergebnisse und Originale erhalten. Details und technische Pins werden in
  den getrennten internen Lauf-/Abnahmebelegen geführt, nicht als Kundendaten im Repo.
- AP04a–c seit 13.11. freigegeben, AP03 eingefroren. Ablagebibliothek, additives
  Register/Migration004 und begrenzte CIFS-Dateischicht implementiert. 23 lokale
  Tests bestanden, 5 native Tests übersprungen. Echtes MariaDB/CIFS, Bashprüfung
  und DMS-Betriebsvoraussetzungen offen; kein Gesamt-PASS.
  Keine Kundenmigration oder automatische Ablage aktiviert. AP05+ ohne Go.
- Verträge: [AP02](AP02-GRAPH.md), [AP03](AP03-RECOGNITION.md), [AP04](AP04-ABLAGE.md).
  [Testquelle](AP03-TEST-SOURCE.md) nur manuell mit fester Ordner-/Parentbindung.

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

- Ende der Warnserie nach geprüftem gültigem Zertifikatswechsel.
- Tatsächliche Anschlussinformationen, SMB-Sicherungsumfang und Betriebszuständigkeiten.

## Nächster Schritt

ORGA gleicht Quellen-, Runtime- und Dateitestbelege ab und bespricht die fachlichen
Restfälle vor einem Gesamtabschluss. Auf main erst nach ORGA-Abgleich übernehmen.
Keine weitere Erkennungsänderung oder neue Testserie aus offenen Fällen automatisch
starten. Kein Test schaltet Produktivverarbeitung frei. Pro Ursache höchstens fünf
gezielte DEV-Korrekturversuche; bestätigte Zähler werden nicht zurückgesetzt.

## AP03-Quellrevision ap03-4

Unknown für lesbare unklare Zuordnung, Failed für technische/strukturelle Fehler;
Mahnung umfasst Zahlungserinnerung. Gezielte Titel-/Label-/Avisregeln in vorhandener
Pipeline, CLI-/Testoperator-Allowlisten ergänzt. Quellreview bestanden, separates
Runtimeimage gebaut und isolierter Dateinachtest durchgeführt; historische Daten
unverändert. Fachliche Restfälle offen. Erkannte PDF-/E-Rechnungen laufen künftig
automatisch; Benutzerklärung nur bei Unbekannt. Die Mailzielpriorität ist seit
13.11.2026 bestätigt: Failed → unzugeordnet (Unbekannt/Dublette) → Mahnung →
Nachfragen → Zahlungsavis → Success. Jeder erkannte Anhang wird unabhängig davon
passend abgelegt. Korrekturjob, Frontend und Umsetzung der Mailpriorität bleiben
späteren freigegebenen AP vorbehalten.

Eine Webkorrektur mit späterer Wiederaufnahme ist ein Vorschlag für AP05/AP06.
Insbesondere ist noch keine 15-Minuten-Wiederaufnahme oder entsprechende Oberfläche aktiv.
