# AP05 – gemeinsamer Verarbeitungspfad

Stand 13.11.2026. AP05 ist im definierten manuellen Umfang technisch abgeschlossen
und bereitgestellt. Der gemeinsame Pfad ist implementiert und unabhängig geprüft.
GUI und Freigabeschreibwege bleiben AP06, Produktivautomatik bleibt AP08.

Vorhandene Bausteine sind verbunden: AP02-Graphadapter/Aktionsjournal, eingefrorene
AP03-Klassifikation mit PDF/XML/OCR und AP04-Ablagejournal/Dateischicht. Vorhandene
SQLAlchemy-/Alembic-/MariaDB-, Docker- und Standardbibliotheksbausteine reichen;
keine neue Queue, Plattform oder Produktabhängigkeit.

Implementiert sind der Identitäts-/Routingvertrag, drei additive Tabellen in
Migration005, der gemeinsame Dienst ProcessingService.advance und die manuelle
[Runtime](AP05-RUNTIME.md). Das Journal bindet vollständiges Manifest, tatsächliche
Originalbytes, ursprüngliche Findings, wirksame Korrekturen und stabile Effektkeys.
600s-Ownerlease gilt je begrenztem Quantum; verspätete Owner/Rückgaben werden
abgewiesen. Vor Mailmutation und vor Abschlussquittung werden Quelle und
Anhangsmanifest erneut geprüft. Sichere Anhangsfehler lassen erfolgreiche
Geschwister weiterlaufen; ungewisse Publikationen sperren den Mailabschluss.

Prüfstand:155 native Backendgruppen ohne Fehler/Skips, darunter40AP05-Gruppen,
auf einer neu erzeugten isolierten MariaDB. Migration001→005zweimal,
Metadatenidentität, getrennte Prozesspersistenz und API-Kompatibilität bestanden.
Zusätzlich echter Zweiroles-Handoff desselben vollständigen Processingimages:
XML-E-Rechnung, OCR-Rechnungs-PDF und ignoriertes Inlinebild, zwei Ablagen mit
unveränderten Bytes sowie bestätigtes ZielNachfragen/Fahne im synthetischen Graph.
Nach simulierter DMS-/Quellentfernung kein erneutes Publizieren. Classifierquellen,
Paket-/Modellhashes und sämtliche41Lockversionen gegen die eingefrorene Basis
geprüft. Absichtlich blockierter Container wird durch denselben Host-Cleanuppfad
beendet; fehlende Konfiguration der echten CLI bleibt ein neutraler Fehler.

Der Gesamtlauf verwendete Fake-Graph und synthetische Datei-Doubles. Zusätzlich
hat ORGA den gleichen Handoff einmal mit echtem CIFS in einem ausschließlich neu
angelegten Testunterverzeichnis geprüft: XML und OCR-PDF wurden bytegleich mit
je genau einem Publikationsversuch abgelegt. Die Inlinebild-Ausnahme sowie
Nachfragen und die Fahne nach dem Move wurden im Fake-Graph bestätigt. Nach
simulierter DMS-Entnahme blieb der Vorgang idle ohne erneute Publikation.
Eigener Readback bestätigt vollständigen Cleanup und unveränderte Kundencontainer.
Der CIFS-Test verwendete private SQLite und synthetische Quellen; er ist kein
Nachweis einer verarbeiteten echten Kundenmail oder einer DMS-Konfigurationsprüfung.
Dienst-/Runtime-Quellreview einschließlich S1/S2/R1 bestanden; gezielte native
Ausgabegrenz-/Timeout-/Cleanupproben einschließlich exakt65536Bytes bestanden.
Der CIFS-Helperreview ist ebenfalls bestanden. ORGA hat nach geschütztem Backup
Kundenschema003 über die additiven Migrationen004/005 auf005 gebracht. Instanz,
Konfigurationskopf und vorhandene Zähler blieben erhalten. Mahnung wurde über den
bestehenden Ordnerpfad als sechstes Inboxziel ergänzt und separat zurückgelesen.
Der echte vollständige Scan ab 01.12.2026, 00:00 Europe/Berlin, fand 0 Mails/0 Anhänge;
derselbe manuelle Hostoperator lieferte bei max-quanta 1 genau 0 Quanten/keinen Rest.
Die vier neuen Tabellen sind leer; zusätzliche Graphaktion nur für Mahnung.
API/GUI, laufende Container und Zeitplanung bleiben unverändert, HTTPS ist ready.
Es wurde keine echte Kundenmail verarbeitet und kein produktives _staging angelegt.
POSIX-Datei- und Prozessgrenzen wurden nativ unter Linux geprüft.

Die sechs festgelegten Graphziele einschließlich Mahnung sind bereitgestellt.
Für AP05-Abschlussrevisionen gibt
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

Eine Zählausnahme benötigt gemeinsam Graph-Typ file, isInline, normalisierten
image-MIME und ein auf die vollständig geladenen Originalbytes hashgebundenes
AP03-Finding ignored/reason=unsupported_attachment. Erst finding(), nicht Listing
oder content(), leitet den gespeicherten Bool ab. Keine manuelle Hashliste,
Signaturpflege oder neue Bild-/Bodyanalyse. Alle Anlagen bleiben im Manifest.
Andere Findings/Typen, fehlender oder abweichender Hash, unvollständiger Download
und nicht-inline Bilder bleiben gezählt bzw. technisch offen. PDF/XML mit falschem
image-MIME werden weiterhin klassifiziert/verarbeitet und nicht ausgeblendet.
Das ist eine Zählkonvention für bereits durch AP03 ignorierte Inlinebilder,
kein semantischer Beweis für Bildinhalt; AP03 einschließlich OCR bleibt unverändert.

Manuelle Entscheidungen sind nur für gespeicherte gewöhnliche Dokumentart-
Unklarheit vorgesehen. Strukturelle Hybrid-/Namespace-/Versionswidersprüche und
mehrdeutige eingebettete Rechnungsstrukturen werden dadurch nicht übergangen.
AP03-Entscheidungsregeln werden weder geändert noch aus Klicks automatisch gelernt.

Vorbereitete [Runtime](AP05-RUNTIME.md): vollständiges vorhandenes Classifier-/OCR-Image
um vorhandene Backendteile ergänzen; dasselbe gepinnte Image in getrennten Rollen verwenden.
Der Classifier erhält weiterhin nur opaken RO-Input, keinen Netzwerkzugriff,
keine Graph-/DB-Secrets und keinen CIFS-Schreibbind. Enger vorhandener
Host-Dateihandoff ohne Docker-Socket in App/API, keine neue Netzwerkplattform.
Eingang5Minuten und Korrekturen15Minuten nutzen in der vorbereiteten CLI denselben
wiederaufnehmbaren Dienstpfad mit getrennten Fälligkeiten. Image, echter Handoff,
isolierte MariaDB und die begrenzte echte CIFS-Probe sind belegt. Die Vorlagen für
die Zeitplanung bleiben deaktiviert; derzeit sind nur manuelle Aufrufe vorgesehen.

Der Betreiber hat DMS-Ausschluss und ausschließliche Importernutzung des
Stagingbereichs bestätigt. Das ist eine Betreiberbestätigung, keine eigene
DMS-Konfigurationsinspektion und keine automatische Produktionsaktivierung.
