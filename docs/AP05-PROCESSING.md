# AP05 – gemeinsamer Verarbeitungspfad

Stand13.11.2026. AP05a–c ist freigegeben und in Entwicklung; keine neue
Kundenmigration, API-/Compose-Umschaltung, Live-Mailaktion oder Jobaktivierung.
GUI und Freigabeschreibwege bleiben AP06, Produktivautomatik bleibt AP08.

Vorhandene Bausteine werden verbunden: AP02-Graphadapter und Aktionsjournal,
eingefrorene AP03-Klassifikation mit PDF/XML/OCR und AP04-Ablagejournal/Dateischicht.
SQLAlchemy/Alembic/MariaDB, Standardbibliothek und bestehende Dockerrollen reichen;
keine neue Queue, Plattform oder Produktabhängigkeit. Geplant ist ein additives
Gesamtjournal mit Mail-, Anhangs- und Korrekturzuständen nach Migration004.

Implementierter erster Baustein `processing_plan.py`: case-sensitive Immutable-
Mail-/Anhangsidentität, vollständiges unveränderliches Manifest, Stichtagsgrenze,
Annahme erlaubter AP03-Findings und Mailzielentscheidung. Sechs synthetische
Testgruppen unter Windows/Python3.14 bestanden. Zusätzlich implementiert:
`ProcessingStore` mit drei additiven Tabellen/Migration005, vollständigem Manifest,
600s-Ownerlease pro begrenztem Quantum, ursprünglichen/aktuellen Entscheidungen,
stabilen Effektreservierungen, Abschlussabsichten und Annahme bereits freigegebener
Korrekturen. Zwölf weitere lokale SQLite-Testgruppen einschließlich Migration001→005
zweimal, Ownerübernahme, verspäteter Rückgaben und Korrekturrevision bestanden.
Zusammen mit sechs Graph-Integrationsgruppen bestehen 24 lokale AP05-Tests.
Journal und Planner verwenden dieselbe MIME-/Signaturprüfung; bestätigter Rohhash
und Inlinebild bleiben zwingend. Der Regressionstest umfasst Parameter/Leerraum
im MIME-Wert sowie Ablehnung unbestätigter Hashes, Inline-PDF und nicht-inline Bild.
Der vorhandene Graphaktionstest bestand zusätzlich14 Gruppen, eine echte
MariaDB-Konkurrenzgruppe blieb lokal übersprungen. Synchrone Transportdoubles
verwenden dabei unter Windows Deadline-Stubs; keine nativen Zeitgrenzen oder
realen Mailaktionen daraus ableiten. Noch kein realer MariaDB-/Gesamtpfad-/
Runtime-PASS für AP05.

Graphziele enthalten jetzt zusätzlich Mahnung. Für AP05-Abschlussrevisionen gibt
es eng bewachte neue Aktionsidentitäten; alte Standardschlüssel bleiben gleich,
erfolgreiche neue Revisionsbelege werden bei späterem Zielwechsel nicht zurückgesetzt.
Der JournalMailbox-Abruf prüft bekannte Quelle/Ordner/Empfang und das gespeicherte
Manifest. Neue Anhänge oder geänderte Metadaten werden abgewiesen; fehlende schon
abgelegte Geschwister invalidieren deren Receipt nicht. Der bisherige Mailbox-
Standard bleibt Inbox-only, der gebundene Reader darf keine neuen Ordner scannen.

Neue Quellen ausschließlich direkte Inbox ab bestehendem Stichtag. Paging vor
äußeren Wirkungen abschließen. Rohbytegröße/SHA stammen aus dem vollständigen
Download, nicht aus Graph-size. Ablagequellenkey bleibt über Mailverschiebung,
Wiederaufnahme und Korrekturrevision unverändert. Eine neue explizite Mailabsicht
je berechtigter Revision darf alte erfolgreiche Absichten nicht zurücksetzen.

Mailpriorität: Failed > unzugeordnet(Unknown/Dublette) > Mahnung > Nachfragen(PDF)
> Zahlungsavis > Success; ohne Relevantes unzugeordnet. Erkanntes unabhängig von
anderen Anhängen ablegen. busy/pending sind kein Abschluss; ungewisse Publikation
wird vor jeder neuen Fehlerroute abgeglichen. Nach bestätigtem Move erforderliche
Fahne setzen und Ziel/Fahne gemeinsam nachprüfen. Erfolg erst nach erforderlichen
Ablage- und Mailaktionen.

Inline/MIME allein beweisen kein Signaturlogo. Nur ein Inlinebild mit tatsächlichem
Hash in einer geschützten bestätigten Signaturhashliste wird von der Mehrfachzählung
ausgenommen. Unbestätigte Inlineanhänge einschließlich PDF/XML bleiben in
Verarbeitung/Zählung; ohne bestätigte Liste wird kein Anhang als Signatur ausgeblendet.

Manuelle Entscheidungen sind nur für gespeicherte gewöhnliche Dokumentart-
Unklarheit vorgesehen. Strukturelle Hybrid-/Namespace-/Versionswidersprüche und
mehrdeutige eingebettete Rechnungsstrukturen werden dadurch nicht übergangen.
AP03-Entscheidungsregeln werden weder geändert noch aus Klicks automatisch gelernt.

Geplante Runtime: vollständiges vorhandenes Classifier-/OCR-Image um vorhandene
Backendteile ergänzen; dasselbe gepinnte Image in getrennten Rollen verwenden.
Der Classifier erhält weiterhin nur opaken RO-Input, keinen Netzwerkzugriff,
keine Graph-/DB-Secrets und keinen CIFS-Schreibbind. Enger vorhandener
Host-Dateihandoff ohne Docker-Socket in App/API, keine neue Netzwerkplattform.
Eingang5Minuten und Korrekturen15Minuten sollen denselben wiederaufnehmbaren
Dienstpfad nutzen; vorerst nur begrenzte einmalige Aufrufe, kein Livejob.

Der Betreiber hat DMS-Ausschluss und ausschließliche Importernutzung des
Stagingbereichs bestätigt. Das ist eine Betreiberbestätigung, keine eigene
DMS-Konfigurationsinspektion und keine automatische Produktionsaktivierung.
