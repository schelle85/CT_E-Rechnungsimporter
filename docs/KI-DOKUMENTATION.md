# KI-Dokumentation

Stand: 14. November 2026. Lebende Markdown-Dokumentation, noch kein Gesamtabschlussbericht.

## Wiedereinstieg

1. [Arbeitsregeln](../AGENTS.md) lesen.
2. [Anforderungen](ANFORDERUNGEN.md) und [Arbeitsplan](ARBEITSPLAN.md) abgleichen.
3. Tatsächlichen Git-Stand, Arbeitsbaum und den konkreten ORGA-Auftrag prüfen.
4. Nur das zugewiesene Paket bearbeiten; Ergebnisse und Prüfungen dokumentieren.

## Aktueller Stand

AP07a–c ist seit14.11.2026 freigegeben. PaketA ist implementiert und mit19 lokalen
Prüfgruppen geprüft: eingefrorene additive007-Tabellen, reine Termin-/Vorlagen-/
Kohortenlogik und persistente Einstellungen/Outbox mit Planrevision, Requestfence
und einmaliger POST-Freigabe. Ursprüngliche Testrequests werden vor aktueller
Versionsprüfung abgeglichen; unreservierte Pflichtslots bleiben neu planbar.
Native007-/Alt-API-Nachweise werden separat von ORGA/REVIEW geführt.
B implementiert Graphsender, eigenen Notificationkey, lokale Zertifikatsidentität,
frischen Nachfolgerproof und begrenzte Operator-CLI.19Sender-/Cert-/Runtimefälle
und9Prozess-/Bindungsgruppen lokal bestanden, B-Review/native B-Prüfung offen.
Neue Web-/weitere Beobachterintegration folgt in C; Administration→Berichte mit
echten Journal-/Tages-/Wochenübersichten ist verbindlich vorgesehen.
Siehe [AP07](AP07-NOTIFICATIONS.md) und [Betreiberweg](AP07-OPERATOR.md).
Keine echte SendMail, Kundenmigration oder Timeraktivierung aus A/B.
Gezielte A1-Korrektur bindet Ausfallwiederholungen an den tatsächlichen letzten
Versuch derselben Incidentepisode. Versuch1 ließ noch eine Erstanlage-Race offen.
Versuch2 führt die ursprüngliche Episode mit dem Slot mit und prüft Fakten,
Mitgliedschaft und aktuellen Monitor bei Erstanlage/Replay/Replan/Reservierung.
25 lokale Tests und nachgespieltes unabhängiges Race-Setup bestanden; A1 danach
unabhängig im Quellenreview nach Versuch2 geschlossen. Separater A2-Befund im
Fehlerbündelpfad mit Versuch1 korrigiert: eingefrorene Auswahl und aktuelle
atomare1h-/Ursachensperre;30 lokale Tests einschließlich A1 und nachgespieltes
unabhängiges A2-Setup bestanden. A2 nachVersuch1 und gesamter A-Quellreview
inzwischen unabhängig bestanden. Einzelheiten im [AP07-Prüfstand](AP07-NOTIFICATIONS.md).
Der tatsächliche Kundenbetrieb bleibt der folgende bestätigte AP06-/006-Stand.

AP06a–d samt PDF-Vorschau ist technisch abgeschlossen und bereitgestellt. Echte Journalansichten,
getrennte Erst-/aktuelle Befunde, generationgebundene Freigabe und Retry,
versionierte Einstellungen sowie geschützter Originalabruf sind implementiert.
Gezielte native006-, HTTP-, Sperr-/Retry- und Vorschau-Lebensdauernachweise sowie
fünf vollständige Browsergruppen liegen vor. Die tatsächliche PDF-Seite wurde
im Dialog und neuen Tab einzeln visuell bestätigt. Produktlaufzeit aus `3fd5fef`;
Die historischen AP06-Testkorrekturen veränderten weder Anwendung noch Migrationen/Deployment.
Zuordnung und Grenzen im [AP06-Vertrag](AP06-WEB.md). Kundenportal und API sind
umgeschaltet, Schema006 unter Erhalt von Altzeilen/Instanz/Konfiguration bestätigt.
Getrenntes Betreiber-Rücklesen: Datenbank erhalten, HTTPS-Journalmodus und
Zugriffsschutz, vollständiger Graph-GET-Leerscan und inaktive Timer bestätigt.
Das echte Journal ist leer. Eine neue tatsächliche Kundenanmeldung für AP06 wurde
nicht durchgeführt; vollständige Rollen-/Bedienprüfungen erfolgten isoliert.
Keine Timeraktivierung; AP08 und spätere Pakete ohne Go, keine DMS-Abnahmebedingung.


- AP00/AP02 technisch abgeschlossen, AP01 durch den Kunden abgenommen.
- AD-Kennwortanmeldung bleibt; SSO verworfen. Kundenschema006 ist nach AP06
  bereitgestellt; die sechs Inboxziele einschließlich Mahnung stammen aus AP05.
- AP03-Revision4 samt Titelvariantennachtrag: Quellreview auf `e49ccdb` bestanden,
  B-F1 bleibt nach Versuch3 geschlossen. Separates Runtimeimage gebaut und isolierter
  abschließender Dateinachtest durchgeführt; weitere fachliche Restfälle bleiben offen.
- `unknown` für lesbare unklare Zuordnung; Mahnung umfasst Zahlungserinnerung.
  Titel-/Label-/Avisregeln und Übergabeverträge geprüft. Fachliche Restfälle bleiben offen.
- Beim historischen AP03-Dateinachtest blieben API/Web/DB und Produktivprofile unverändert; keine automatische Verarbeitung,
  echte Mailmutation oder Frontend-/Jobaktivierung aus dem Dateinachtest ableiten.
- Historische Ergebnisse und Originale erhalten. Details und technische Pins werden in
  den getrennten internen Lauf-/Abnahmebelegen geführt, nicht als Kundendaten im Repo.
- AP04a–c technisch im isolierten Grundlagenumfang abgeschlossen, Quellreview
  bestanden; AP03 eingefroren. Native Gesamtnachprüfung aus c781896: 115 Backendtests
  ohne Fehler/Skips einschließlich aller 28 AP04-Tests bestanden. Bashprüfung,
  isolierte echte MariaDB-Migration/Persistenz und API-Kompatibilität bestanden.
- Getrennte echte CIFS-Probe durch ORGA: fünf synthetische Fälle bestanden,
  Exit0 und vollständiges Erfolgsresultat; unveränderte Ablage, Dublette,
  Größenkollision, No-replace und Wiederaufnahme nach simulierter DMS-Entfernung.
  Unabhängiger Readback und Cleanup bestätigt, Kundencontainer unverändert gesund.
  AP04-N1 sowie SMOKE-F1/SMOKE-F2 jeweils nach Korrektur1 geschlossen;
  interne Belege und technische Pins bleiben außerhalb öffentlichen Gits.
- AP04-Abschlussstand: Schema004 war nur isoliert geprüft, API und Jobs blieben
  unverändert. Spätere AP05-Bereitstellungswerte werden separat nachgewiesen.
- AP05a–c seit13.11. freigegeben. Gemeinsamer Dienst mit Identitäts-/Routingvertrag,
  Gesamtjournal/Migration005 und engen Graph-Erweiterungen:155 native Backendgruppen
  einschließlich40AP05 ohneFehler/Skips. Frische isolierteMariaDB-Migration/Persistenz,
  API-Kompatibilität und getrennter Handoff mit echter eingefrorener XML-/OCR-Erkennung
  bestanden. Tatsächliches altes Kundenimage zusätzlich auf frischem005 kompatibel.
  Dienst-/Runtime-Quellreview S1/S2/R1 bestanden; gezielte native Ausgabegrenz- und
  Timeoutprüfung nach dem Gesamtlauf bestanden. Einmaliger ORGA-Handoff auf echtem
  CIFS im exklusiven Testverzeichnis bestanden: zwei Publikationen mit je einem
  Versuch, bytegleiche Quellen, Fake-Graph-Ziel/Fahne und idle nach simulierter DMS-Entnahme.
  Eigener Readback und unabhängiger Belegabgleich bestätigen Cleanup und unveränderte
  Kundencontainer. Der separate Kundenabschluss bestätigt nach Backup 003→005,
  gleiche Instanz/Konfiguration, HTTPSready und sechs Ordner. Echter Scan ab dem
  unveränderten Stichtag findet 0 Mails/0 Anhänge; manueller Tick mit max-quanta 1
  liefert 0 Quanten/keinen Rest. Vier neue Tabellen leer, eine zusätzliche Graphaktion
  für Mahnung. Host-/Timerreadback bestanden, API/GUI unverändert. AP05 ist im
  definierten manuellen Umfang technisch abgeschlossen. Keine echte Kundenmail
  wurde verarbeitet; produktives _staging blieb unangetastet. Historische Angaben zur
  exklusiven Stagingnutzung sind keine eigene DMS-Konfigurationsprüfung und kein
  aktuelles Freigabegate. AP03-Regeln bleiben unverändert. Zum AP05-Nachweis keine
  API-/GUI-Umschaltung, Live-Mailmutation oder aktive Jobs aus dieser Sonde.
  AP06 ist seit14.11. einschließlich PDF-Vorschau freigegeben; Produktivautomatik bleibt AP08.
- AP06 auf Basis `818cc76` technisch abgeschlossen und bereitgestellt: Journal-API und echte Oberfläche,
  kontrollierte Schreibwege, PDFdialog/Originaldownload und schreibgeschütztes Archiv.
  Additives Schema 006 erhält bestehende Daten/Instanzkennung; tatsächlicher alter 005-Pfad
  und Rückweg der alten API auf 006 separat geprüft. Antwortverlust/Neuanmeldung,
  Teilvorgänge und langsame Originalantworten über Nginx im Browser bestanden.
  Kundenmigration/Bereitstellung und separates Betreiber-Rücklesen bestanden.
  DMS ist vollständig außerhalb Auftrag/Prüfung/Abnahme. AP07-Go inzwischen erteilt;
  AP08 und spätere Pakete weiterhin ohne Go.
- Signaturzählung ohne manuelle Hashlisten: nur file+inline+normalisierter
  image-MIME und vollständiges hashgebundenes AP03-ignored/unsupported_attachment
  werden nach Findingannahme ausgenommen. Alle anderen Fälle bleiben gezählt/offen.
  J1-MIME-Gegenfall weiterhin geprüft, AP03 unverändert.
- Verträge: [AP02](AP02-GRAPH.md), [AP03](AP03-RECOGNITION.md), [AP04](AP04-ABLAGE.md), [AP05](AP05-PROCESSING.md), [AP06](AP06-WEB.md).
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
passend abgelegt. Der gemeinsame Verarbeitungspfad einschließlich Mailpriorität
und bereits freigegebener Korrekturen ist inzwischen in AP05 implementiert;
Frontend und Freigabeschreibwege sind inzwischen in AP06 implementiert und isoliert geprüft.

Der vereinbarte GUI-/Erkennungsnachtrag für AP05/AP06 ist in den
[Anforderungen](ANFORDERUNGEN.md#webkorrektur-und-erkennungsverbesserung) und im
Arbeitsplan ausdrücklich verankert: Kachel Unbekannt, Zuordnung je Anhang,
Freigabe und gemeinsame Wiederaufnahme alle 15 Minuten sowie nachvollziehbare
Korrekturbeispiele für später geprüfte Regeln/Vorlagen. Keine automatische
Verallgemeinerung einzelner Klicks; invoice2data derzeit nicht integriert.
Die entsprechende Oberfläche und Freigabeerzeugung sind in AP06 implementiert und isoliert geprüft.
Die manuelle Wiederaufnahme ist implementiert und geprüft; 5-/15-Minuten-Timer
sind nicht aktiviert. Diese Dokumentationspräzisierung erteilt kein neues AP-Go.
