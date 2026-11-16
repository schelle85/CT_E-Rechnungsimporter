# KI-Dokumentation

Stand: 16. November 2026. Lebende Markdown-Dokumentation, noch kein Gesamtabschlussbericht.

## Wiedereinstieg

1. [Arbeitsregeln](../AGENTS.md) lesen.
2. [Anforderungen](ANFORDERUNGEN.md) und [Arbeitsplan](ARBEITSPLAN.md) abgleichen.
3. Tatsächlichen Git-Stand, Arbeitsbaum und den konkreten ORGA-Auftrag prüfen.
4. Nur das zugewiesene Paket bearbeiten; Ergebnisse und Prüfungen dokumentieren.

## Aktueller Stand

Planungsnachtrag vom 16.11.2026: [AP12](AP12-GRAPH-ZERTIFIKATSROTATION.md) für
Graph-Zertifikatsrotation und Administration → Graph-Zertifikat angenommen.
Noch kein Umsetzungs-Go; keine neue Funktion daraus als bereitgestellt bezeichnen.
Nach AP08 und vor AP11/09 eingeplant. Bestehende AP07-Prüfung, Warnserie und
Schlüsselgrenzen wiederverwenden; neuer Hostauftrag zuerst konkret prüfen.

AP07a–c ist am 15.11.2026 technisch abgeschlossen und bereitgestellt aus
`5ecfd59270b63947d3f92af98a1b9f8e5a267aeb`. Aktueller Kundenstand: Schema 007,
API/Web aus derselben festen Quelle, bestehende Instanz/LDAP-Konfiguration und
DBdienst erhalten, getrennt zurückgelesen. Eigener Notificationkey, getrennte
minimale manuelle CLI und drei privat initialisierte Empfänger eingerichtet.

A/B vollständig geprüft; C-Quellenreview, 21 C-Fälle auf MariaDB und acht isolierte
HTTPS-Browsergruppen bestanden. Dazu gehören 80,006 s-Gesamtfrist, Antwortverlust,
neue Sitzung und Konfigversion ohne Doppel-POST. Zusätzlicher synthetischer
CLIplan geprüft. Administration→Berichte mit echten Tages-/Wochen-/freien
Journalzeiträumen, Einstellungen, Vorschau/Test/Historie und exakte Graph-
Zertifikatswarnung10d/1d/0/negativ samt Loginhinweis für beide Rollen geliefert.

Echte Graph-Zertifikatsanmeldung und genau eine feste Testmail (HTTP 202) mit
Reservierung 1 sowie getrenntem Statusabgleich bestätigt. Empfang im eigenen
Abnahmepostfach belegt; kein Empfangsnachweis für die beiden weiteren Empfänger.
Nach AP07 keine neue tatsächliche Kundenanmeldung behaupten. Die echte AD-
Abnahme aus AP01 bleibt historisch, aktuelle Rollen-/Bedienprüfungen sind isoliert.

Wesentliche Verträge: additive eingefrorene007-Tabellen; Notificationcipher
unabhängig vom LDAPcipher; ursprüngliche Actor-/Scope-/UUID-/Versionsbindung;
eine dauerhafte Reservierung und höchstens eine POST-Freigabe. Ungewisse
Versandversuche werden nicht zurückgesetzt. Zertifikatspläne bleiben an ihre
ursprüngliche offene Serie gebunden, Ausfallpläne an ihre beobachtete Episode;
Fehlerbündel an ursprüngliche Auswahl und tatsächliche Reservierungsabstände.
Gleicher Request liefert nach aktuellen AD-/Origin-/CSRF-Prüfungen seine
Quittung vor dem Vergleich mit der inzwischen aktiven Notificationversion.
Das absolute 80-s-Webbudget beginnt vor AD/DB/Bodyvorprüfung. Status und Berichte
lesen gespeicherte Daten, ohne einen neuen Versandauftrag zu erzeugen.

CLIplan verbindet tatsächliche neutrale Journalfehler mit begrenzten API-/
Graphproben und den vorhandenen Kalender-/Snapshotplanern. Keine rekursive
Meldung über Benachrichtigungsfehler. Bei Ausfall der eigenen VM/DB keine
zuverlässige Selbstalarmierung. APIkind teilt die API-Dateisystemgrenze;
Envstrip ist keine physische Isolation. Externe CLI bleibt minimal gebunden.

Import-/Korrektur-/Notificationautomatik ist weiterhin inaktiv. Gespeicherte
Zeiten werden erst nach AP08-Go dauerhaft aktiviert. AP08/09/10/11 sind nicht
freigegeben; AP11-Planung, Dezemberstichtag, AP03 und DMS-Abgrenzung erhalten.
Siehe [AP07-Vertrag](AP07-NOTIFICATIONS.md), [Operatorvertrag](AP07-OPERATOR.md)
und [Betriebsstand](BETRIEBSSTAND.md).

Historischer AP06-Stand: echte Journalansichten, generationgebundene Korrektur/
Retry und PDF-Vorschau mit nativen006-/HTTP-/Konkurrenznachweisen und fünf
isolierten Browsergruppen einschließlich sichtbarer PDF bestanden. Damaliger
Produktcode `3fd5fef`, Kundenschema006 und leeres Journal wurden separat bestätigt.
AP07 ersetzt diesen Laufzeitstand; die AP06-Fachfunktionen bleiben erhalten.
[AP06-Vertrag](AP06-WEB.md).

- AP00/AP02 technisch abgeschlossen, AP01 durch den Kunden abgenommen.
- AD-Kennwortanmeldung bleibt; SSO verworfen. Bei AP06 wurde Schema 006 bereitgestellt, aktuell gilt007; die sechs Inboxziele einschließlich Mahnung stammen aus AP05.
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

- Dauerhafte Import-/Korrektur-/Benachrichtigungsaktivierung erst nach AP08-Go.
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
