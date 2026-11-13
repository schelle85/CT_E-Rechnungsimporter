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
Testgruppen unter Windows/Python3.14 bestanden; noch kein Gesamtpfad-/Runtime-PASS.

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
