# AP03 – Erkennungsumfang und Isolation

Stand12.11.2026: AP03a–c freigegeben. Quellrevision `ap03-4` einschließlich der
Abschnitts- und Titelkorrektur auf `e49ccdb` unabhängig geprüft. Separates Runtimeimage aus
diesem Stand gebaut und im isolierten Dateinachtest verwendet. Fachliche Restfälle
bleiben offen; kein AP03-Gesamt-PASS. XML-/Hybridstruktur, PDF-Text und bedarfsweise
lokale OCR bleiben getrennt geprüft. Die [streng lesende Testmailquelle](AP03-TEST-SOURCE.md)
ist ein separater manueller Operatorweg, kein Produktivworker. Der Nachtest verwendete
vorhandene Dateien und benötigte keinen erneuten Postfachabruf. Laufende API/Web/DB
und Produktivprofile wurden nicht umgeschaltet; AP04+ bleibt ohne pauschales Go.

Geprüfter Titelvariantennachtrag: Pre-Notifikation mit `/` als Titeltrenner und
Mahnung/Zahlungserinnerung mit `vom <Datum>` als Überschrift. Beide zusätzlichen
vollständig verankerten Titelformen wurden im isolierten Dateinachtest bestätigt.
Beliebige Textpräfixe werden nicht entfernt; keine zusätzliche Layout-/Feldnormalisierung.

## Vorhandene Bausteine

Die eigentliche Dokumentverarbeitung bleibt bei vorhandenen OSS-Bibliotheken:
[pikepdf](https://pikepdf.readthedocs.io/en/latest/topics/attachments.html)10.18.0
mit gebündeltem qpdf12.4.2 liest PDF-Objekte und Einbettungen. pikepdf steht unter
MPL2, qpdf unter Apache2. [defusedxml](https://github.com/tiran/defusedxml)0.7.1
(PSF2) parst XML mit verbotenen DTDs, Entitäten und externem Zugriff.

[factur-x](https://github.com/akretion/factur-x) ist als BSD3-Fachbibliothek
geeignet, ihr allgemeiner Extraktor bringt aber Dateinamenfilter, erste Treffer,
zusätzliche Validierungswege und Bibliothekslogs mit. Hier wird er ausschließlich
als unabhängiger Testgenerator verwendet. Eigener Code begrenzt Ressourcen und
prüft Namespace/Profil/Strukturkontext; keine eigene PDF-/XML-Engine.

Für Text/OCR werden PDFium und Tesseract verwendet. OCRmyPDF ist eine geeignete
Alternative mit zusätzlicher PDF-Erzeugung und seit17.0 optionalem PDFium-
Rasterizer; Ghostscript ist keine pauschale Voraussetzung. Ein zusätzlicher
OCRmyPDF-Pfad wird nicht eingebaut. Versionen und transitive Abhängigkeiten stehen in den
getrennten `requirements-classifier*.lock`; API-Abhängigkeiten bleiben unverändert.
Keine kostenpflichtige SDK oder Cloud-API erforderlich; Paket-/Nativepflege und
CPU/RAM bleiben Betriebsaufwand, keine unbelegten Laufkostenbeträge.

## Unterstützte strukturierte Formate

| Eingabe | Unterstützter Kontext | Ergebnis |
| --- | --- | --- |
| XML | XRechnung2.2/2.3/3.0, exakte bekannte Profilkennungen; UBL-Invoice/CreditNote oder CII100 | E-Rechnung, Original-XML |
| PDF | Factur-X1.x/ZUGFeRD2.x-CII: MINIMUM, BASIC WL, BASIC, EN16931, EXTENDED | E-Rechnung, Original-PDF |
| PDF | ZUGFeRD1.0-CII12: BASIC, COMFORT, EXTENDED mit Legacy-XMP | E-Rechnung, Original-PDF |
| XML mit Hybridprofil ohne PDF | Erkanntes Hybrid-Rechnungs-XML, kein XRechnungsprofil | Failed/hybrid_pdf_required |
| Andere XML | Keine unterstützte Rechnungsstruktur, etwa Order-X oder generischesXML | ignored |
| XML-Rechnung mit unbekanntem Namespace/Profil/Typcode | Kein sicher zugesagtes Format | Failed/unsupported_* |
| Hybrid-PDF mit unverstandener Version oder Profil-/Namespacewiderspruch | Keine sichere Hybridzuordnung, kein Textfallback | unknown mit neutralem Strukturgrund |
| Gewöhnliche Text-PDF | Titel und Belegzusammenhang | PDF-Rechnung, Zahlungsavis, Mahnung, irrelevant, unknown oder technischer Failed |
| Scan/fehlende brauchbare Textebene | Begrenzte seitenbezogene OCR auf Arbeitsbildern | Dieselben Kategorien/Regeln; unlesbar oder Fehler ergibt Failed |

Unterstützte Dokumenttypcodes:380/381/384/386/389; UBL-CreditNote381, UBL-Invoice
die übrigen. XRechnung-Profil genau
`urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0`;
historische2.2/2.3 exakt mit `#urn:xoev-de:kosit:standard:xrechnung_2.2`
beziehungsweise2.3 statt des neueren URN-Namensraums. Keine offene Versionsregex.
Keine Aussage über XSD-/Schematron-Konformität, Echtheit oder Betragsrichtigkeit.
Profilkennung allein genügt nicht: Dokument-ID/Datum, Parteien, Währung,
Monetärstruktur und bei line-basierten Profilen strukturierte Positionen prüfen.
Legacy BASIC darf GrandTotal ohne das dort optionale DuePayableAmount enthalten.

PDF-Einbettungen werden über Names-Tree/Kids, Root-/Page-AF und FileAttachment-
Annotationen vollständig im begrenzten Umfang gesammelt. Gleiche Namen werden
nicht über ein Mapping auf den ersten Inhalt reduziert. XML-Inhalt, AF-Beziehung,
referenzierter Dateiname und konsistente XMP-Familie/Version/Profil müssen zusammen
passen. Annotation-only ohne AF wird nicht als gültiger Hybridkontext akzeptiert.
Mehrere unterschiedliche gültige Rechnungs-XMLs ergeben Unbekannt; beschädigte
Kandidaten bleiben Failed. Widersprüchliche Hybridclaims werden nicht automatisch
verarbeitet; kein Rückfall auf gewöhnliche PDF. Kein separates XML-
Produktartefakt. Dateien werden niemals über ihren eingebetteten Namen geöffnet.

## Ergebnis und Grenzen

### AP03b: Textentscheidung, Revision ap03-4

PDFium liest alle begrenzten Seiten. Plausibilitäts-/Wiederholungsprüfungen und
bedarfsweise OCR bleiben bestehen. Unterstützte Titel umfassen Ausgangsrechnung,
gesperrtes Rechnung, Invoice und die bestehenden Rechnungs-/Gutschriftsvarianten.
Nur die Titelzeile wird gezielt normalisiert; beiläufige Wörter/Bankdaten genügen nicht.

Datums-/Summenlabels dürfen Werte auf derselben oder den folgenden zwei nichtleeren
Zeilen haben. Eine neue Dokumentüberschrift beendet die Suche; Datumswerte bleiben
kalendergeprüft. Keine allgemeine Layoutanalyse. Eine explizite Rechnungsüberschrift
braucht Referenz und Datum, Referenz und Gesamtbetrag oder Gesamtbetrag plus
Positions-/Leistungs-/Steuermerkmale. Die vollständige alte Kombination behält ihren
neutralen Grund. Fehlende Einzelfelder schließen die Dokumentart nicht pauschal aus;
keine steuerliche Rechnungsvalidierung oder willkürliche Wahrscheinlichkeit.

Avis/Payment Advice und Pre-Notifikation/Vorabankündigung brauchen Hauptüberschrift,
Zahlungs-/Einzugskontext und Gesamtbetrag; Referenz/Datum sind nicht zwingend.
Ein bloßes SEPA-Mandat wird dadurch nicht zum Avis. Mahnung/Zahlungserinnerung teilen
Kategorie `Mahnung`: eigene Überschrift plus Betrag oder Referenz/Datum. Zitierte
Rechnungsnummern sind kein zweiter Beleg. Beiläufige Mahnungshinweise in AGB sind
keine eigene Mahnung. Ein Avis/eine Mahnung darf sagen, keine Rechnung zu sein.

Alle Textzeilen, Folgeseiten und unabhängig von ihrer Reihenfolge vorhandene Haupt-
abschnitte bleiben geprüft. Widersprüchliche eigenständige Titel ergeben `unknown`.
Rechnungsnummern unter Avis/Mahnung bleiben Referenzen; eigenständiges Rechnungsdatum
oder eigener Rechnungsbelegzusammenhang bleibt ein unabhängiger Beleg, auch ohne Datum.
Abschnittsbildung und Rechnungsentscheidung verwenden dieselbe Belegevidenz.
Zahlungsdatum/Zahlbetrag allein sind Referenzkontext; eigene Positionsangaben können
den Rechnungszusammenhang herstellen. Die AGB-Beispielkonvention bleibt erhalten.
Ein alleinstehender Rechnungstitel wird weiter separat erfasst. Begleitabschnitte
AGB/Datenschutz/Zahlungsbedingungen liefern keine Belegevidenz, verdecken spätere
Hauptabschnitte aber nicht. Explizite Nicht-Rechnung/Proforma verhindert die
Rechnungsentscheidung; Einzelwort und IBAN reichen weiterhin nicht.

Vier Ergebnisse: `recognized`, `ignored`, `unknown`, `failed`. Lesbare unklare
Dokumentarten bleiben `unknown` mit neutralem `ambiguous_*`-Grund und Methode.
Echte technische Lese-/Struktur-/Parser-/Ressourcenfehler bleiben `failed`.
Unverstandene Hybridversion bzw. widersprüchliches Hybridprofil/Namespace ergibt
`unknown` ohne gewöhnlichen PDF-Fallback. Alle übrigen Struktur-/XML-/Sicherheits-
und Budgetprüfungen bleiben bestehen. Ohne Benutzerpasswort geöffnete PDFs werden
trotz Eigentümerschutz vollständig geprüft; Passwortbedarf bleibt `encrypted_pdf`.

invoice2data-API/Textpfad und Vorlagen wurden geprüft. Keine neue Abhängigkeit in
dieser kleinen Revision: allgemeine Titel-/Label- und Strukturlücken werden dadurch
nicht ohne zusätzliche Vorlagen-/Extraktionspflege gelöst. Spätere schlanke lokale
Anbindung bei belegtem Vorlagennutzen gesondert prüfen. Keine zweite PDF-/OCR-/LLM-Stufe.

### AP03c: OCR auf Arbeitsbildern

[PDFium](https://pypdfium2.readthedocs.io/en/stable/python_api.html) rendert ganze
betroffene Seiten mit 200 DPI, Graustufen, ohne Formularinitialisierung und mit
begrenztem Imagecache. Höchstens 10 OCR-Seiten, 8 Millionen Rasterpixel je Seite
und 40 Millionen insgesamt; alle Dimensionen/Seitenbudgets vor dem ersten Rendern
prüfen. PDFium berücksichtigt UserUnit nicht bei seiner DPI-Umrechnung; die
Rasterpixelgrenze gilt trotzdem für die tatsächlich angeforderten Bitmaps.

[Tesseract](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)
5.5.0 (`5.5.0-1+b1`), Leptonica1.84.1, Sprachpakete deu/eng/osd jeweils
`1:4.1.0-2`, vollständig im Image. 71 native Zusatz-/geänderte Pakete gegen den
festen Python-Basisdigest sind in `requirements-classifier-native.lock` gepinnt.
`/usr/local/share/classifier-native-packages.txt` enthält das vollständige
Debian-Inventar, `classifier-model-hashes.txt` die drei SHA256-Modellprüfsummen.
APT-Rebuild setzt die Verfügbarkeit der fest gepinnten Debian-Pakete voraus;
das geprüfte Image über seinen unveränderlichen Digest aufbewahren. Keine
automatische Versionsauflösung oder Sprachmodelldownload im Kundenlauf.
Tesseract/Modelle Apache2, Leptonica BSD-artig; Copyright-/Lizenzdateien der
nativen Abhängigkeiten bleiben unter `/usr/share/doc/*/copyright` im Image.
Python/PDFium-Lizenzen aus dem bisherigen separaten Lock weiterhin beachten.

Feste lokale CLI-Argumente, deu+eng, PSM1 mit Orientierungserkennung, ein Thread,
keine Shell oder Dokumentnamen als Schalter/Pfad. OCR-TSV nur in privatem
Arbeitsverzeichnis, höchstens2MiB je Aufruf und20s; keine Textausgabe/Sidecars im
Produktresultat. Begrenzte Wortkonfidenz dient nur als technische Lesbarkeitsgrenze
(gewichteter Mittelwert mindestens55, maximal25% Zeichen in Wörtern unter40),
niemals als Rechnungswahrscheinlichkeit. Dieselbe Wort-/Wiederholungsplausibilität
und dieselben fachlichen Regeln wie beim Text-PDF anschließend anwenden.
Methoden `pdf_text`, `ocr` oder `pdf_text_ocr`, Regelversion `ap03-4`.

Der überwachende Elternprozess besitzt das private temporäre Wurzelverzeichnis.
Nach Ergebnis, Fehler oder120s Gesamttimeout beendet er die private Workergruppe
einschließlich OCR-Nachfahren und entfernt die Arbeitsdateien. Workergrenzen:
512MiB Adressraum,90s CPU,16MiB pro Arbeitsdatei,128 Dateideskriptoren; OCR-Ausgabe
hat zusätzlich ihr eigenes hartes2MiB-Dateilimit. Container mit init für verwaiste
Nachfahren,128MiB tmpfs,512MiB RAM ohne zusätzlichen Swap,1 CPU/64 PIDs, UID10001,
ohne Netz/Secrets/DB/SMB. Temporärdateien überleben keinen regulären Containerlauf.

15 OCR-Tests verwenden echte Pillow-Rasterbilder in unabhängig mit reportlab
erzeugten PDFs und echte Tesseract-Binaries: Deutsch/Umlaute, Englisch, Avis,
90/180/270Grad-Drehung,3Grad-Schieflage, unlesbare niedrige Auflösung, Text-/Scan-
Mischseiten und Konflikte. Saubere Textseiten starten keine OCR. Fehlende Modelle,
leere Ergebnisse, Ausgabetext-/Datei-/Seiten-/Pixelgrenzen und tatsächliche Timeouts
bleiben Failed. Ein echter Prozessgruppenfall startet OCR und absichtlich hängende
Nachfahren; nach Abbruch weder laufende Nachfahren noch Arbeitsdateien. Originalhash
bei Erfolg und Fehler unverändert. Keine allgemeine Qualitätsgarantie für unbekannte
Kundenscans; lesbare unklare Dokumentarten bleiben Unbekannt, technische OCR-Fehler Failed.

Manueller Aufruf im Classifierimage: `python -m classifier.cli /input/document`.
JSON enthält status, category, format, neutralen reason, method, rule_version
und Original-SHA256; keine extrahierten Texte, Rechnungsnummern oder Dateinamen.
Kein Graph-, DB-, SMB-, LDAP- oder Webzugriff und keine Mailordnerentscheidung.

Quelle25MiB, XML1MiB,20.000XML-Knoten/48Ebenen/8KiB je Attribut,30PDF-Seiten,
50.000PDF-Objekte,32Filespecs/256Namensbaumknoten/8Ebenen,1MiB je dekomprimiertem
Anhang und4MiB insgesamt. Native Dekodierung geschieht im begrenzten Prozess;
eine reine Prüfung nach der Dekompression wäre allein kein Speicherschutz.
DTD/Entities/XInclude verboten, SchemaLocation inert, nichts nachladen. PDF-JS/
Launch/SubmitForm/ImportData abweisen, externe Filespecs nie auflösen.

Worker: maximal120s Wallclock,90s CPU,512MiB Adressraum,128FDs, keine Coredumps.
Elternprozess beendet die private Prozessgruppe einschließlich Nachkommen vor
dem Reaping. Original nur Bytes/RO-Eingabe, keine PDF-Speicherung oder Reparatur.
Bibliotheksausgaben im Worker unterdrückt. CLI-Eingabe nur reguläre Datei unter
dem expliziten `/input`-Bind; Symlinks und aufgelöste fremde Pfade abweisen.

`deploy/compose.classifier.yaml`: ausschließlich manuelles Profil mit festem
Image, UID10001, network:none, read-only,128MiBtmpfs,512MiBSpeicher ohne zusätzlichen
Swap,1CPU,64PIDs, capdrop/no-new-privileges, keine Ports/Secrets/Restart und genau
ein RO-Input-Bind. Vor echter Verwendung REVIEW/ORGA; bestehende Dienste nicht
über die Produkt-Composevorlage ersetzen.

## Referenzen und Prüfung

20 echte Parser-/PDF-Tests: offizielle KoSIT-UBL/CII-Fixtures, fünf Factur-X-
Profile über factur-x7.9, drei Legacy-XMLs aus dessen Referenzsammlung mit pypdf-
Hybridgenerierung, generisches/gefälschtes/kaputtes XML, UTF16 und andere Präfixe,
DTD/XXE/XInclude/Strukturlimits, PDF-Verschlüsselung/JS, falsche Einbettung,
verschachtelte und doppelte Names, widersprüchliche XMP-/AF-Kontexte,
Originalhash und echter Prozessabbruch. Keine reinen Extrakttext-Doubles.
AP03-A-F1 Versuch1: XML-Vorerkennung bis zum ersten nichtleeren Codepunkt statt
eines512Byte-Präfixfensters. Sieben gültige Kombinationen aus langem Leerraum,
BOM, XML-Deklaration, UTF8 und UTF16LE/BE geprüft. Größenlimit und Ablehnung
gewöhnlicher Nicht-XML-Daten bleiben erhalten; der Parser entscheidet weiterhin.
Zusätzliche Belege: historische offizielle UBL/CII jeweils für2.2/2.3, abweichende
EF-F/UF-Streams, ausschließlich Page-AF/Annotation erreichbare zweite Kandidaten,
gleicher Inhalt über mehrere zulässige Referenzen sowie Annotation-only-Grenze.
CreditNote stammt aus phax/ddd; der veröffentlichte Peppol-Baum bleibt strukturell
unverändert und erhält nur für den Erkennungstest die kanonische XRechnung3.0-
CustomizationID. Original und abgeleitete Fixture samt genau dieser Modifikation
und Apache2-Lizenz sind getrennt dokumentiert; kein unabhängiger XR-Norm-PASS.

KoSIT-Referenzen: Apache2, Commit1ce1dafffd035e5ce59a7ab0d3bf44ac14af16c9.
factur-x-Referenzen: BSD3, Commit650cfe34ec524ec39ea106a09df6d0cc259813a4.
Herkunft, Dateien und SHA256 in den jeweiligen ORIGIN.json neben mitgeführten
Lizenzen. Öffentliche synthetische Referenzen, keine Kundenrechnungen.
Historische KoSIT-Commits5a89ca5e73754270072ad54590b314eb15641438 und
77f0b0814624d038479bd0c8412d81ebc491f44b; CreditNote-Baum aus
phax/ddd98f34f68600b416c8b1e54c6d3820aa701690b68. DDD ist ein vorhandener
Java-Formatdetektor; seine Übernahme würde eine zusätzliche JVM/Java-Bibliothek
einführen. Hier bleibt die kleine bekannte Profilallowlist beim vorhandenen
Python-Parser, die Fachstruktur- und Isolationsregeln wären weiterhin erforderlich.
Testwerkzeuge reportlab/pypdf/factur-x sind nur im separaten Testimage.

### Ergebnisübergabe und spätere Verarbeitung

CLI-Worker/Testreader akzeptieren `unknown` und die erkannte Kategorie `Mahnung`.
Unbekannt ist kein technischer Übergabefehler; CLI-Exitcode nur bei `failed` ungleich0.
Bestehende API/DB und Profile werden hier nicht migriert. Historische Ist-Ergebnisse
bleiben erhalten. Neue Ergebnisse separat speichern. Erkannte PDF-/E-Rechnungen
künftig automatisch verarbeiten; Benutzerklärung nur bei Unbekannt. Korrekturjob,
Frontend und Mischmail-Priorität bleiben späteren freigegebenen AP vorbehalten.
