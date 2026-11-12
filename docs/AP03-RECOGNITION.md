# AP03 – Erkennungsumfang und Isolation

Stand12.11.2026: AP03a–c freigegeben. Dieser erste Lieferstand enthält den
strukturierten XML-/Hybrid-PDF-Kern. Textklassifikation, OCR und zusätzliche
streng lesende Testmailquelle folgen; keine Kundenbereitstellung oder echte
Testmailabholung. AP04+ und automatische Verarbeitung sind nicht freigegeben.

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

Für Text/OCR sind PDFium und Tesseract vorgesehen. OCRmyPDF ist eine geeignete
Alternative mit zusätzlicher PDF-Erzeugung und seit17.0 optionalem PDFium-
Rasterizer; Ghostscript ist keine pauschale Voraussetzung. Noch kein OCR-Pfad
in diesem Commit. Versionen und transitive Python-Abhängigkeiten stehen in den
getrennten `requirements-classifier*.lock`; API-Abhängigkeiten bleiben unverändert.
Keine kostenpflichtige SDK oder Cloud-API erforderlich; Paket-/Nativepflege und
CPU/RAM bleiben Betriebsaufwand, keine unbelegten Laufkostenbeträge.

## Unterstützte strukturierte Formate

| Eingabe | Unterstützter Kontext | Ergebnis |
| --- | --- | --- |
| XML | XRechnung3.0, exakte Profilkennung; UBL-Invoice/CreditNote oder CII100 | E-Rechnung, Original-XML |
| PDF | Factur-X1.x/ZUGFeRD2.x-CII: MINIMUM, BASIC WL, BASIC, EN16931, EXTENDED | E-Rechnung, Original-PDF |
| PDF | ZUGFeRD1.0-CII12: BASIC, COMFORT, EXTENDED mit Legacy-XMP | E-Rechnung, Original-PDF |
| XML mit Hybridprofil ohne PDF | Erkanntes Hybrid-Rechnungs-XML, kein XRechnungsprofil | Failed/hybrid_pdf_required |
| Andere XML | Keine unterstützte Rechnungsstruktur, etwa Order-X oder generischesXML | ignored |
| Bekannte Rechnung mit unbekanntem Namespace/Profil/Typcode | Kein sicher zugesagtes Format | Failed/unsupported_* |
| Gewöhnliche PDF | Noch keine Text-/OCR-Auswertung in AP03a | Failed/text_analysis_pending; keine E-Rechnungszusage |

Unterstützte Dokumenttypcodes:380/381/384/386/389; UBL-CreditNote381, UBL-Invoice
die übrigen. XRechnung-Profil genau
`urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0`.
Keine Aussage über XSD-/Schematron-Konformität, Echtheit oder Betragsrichtigkeit.
Profilkennung allein genügt nicht: Dokument-ID/Datum, Parteien, Währung,
Monetärstruktur und bei line-basierten Profilen strukturierte Positionen prüfen.
Legacy BASIC darf GrandTotal ohne das dort optionale DuePayableAmount enthalten.

PDF-Einbettungen werden über Names-Tree/Kids, Root-/Page-AF und FileAttachment-
Annotationen vollständig im begrenzten Umfang gesammelt. Gleiche Namen werden
nicht über ein Mapping auf den ersten Inhalt reduziert. XML-Inhalt, AF-Beziehung,
referenzierter Dateiname und konsistente XMP-Familie/Version/Profil müssen zusammen
passen. Annotation-only ohne AF wird nicht als gültiger Hybridkontext akzeptiert.
Mehrere unterschiedliche Rechnungs-XMLs, beschädigte Kandidaten und widersprüchliche
Claims führen zu Failed; kein Rückfall auf gewöhnliche PDF. Kein separates XML-
Produktartefakt. Dateien werden niemals über ihren eingebetteten Namen geöffnet.

## Ergebnis und Grenzen

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

15 echte Parser-/PDF-Tests: offizielle KoSIT-UBL/CII-Fixtures, fünf Factur-X-
Profile über factur-x7.9, drei Legacy-XMLs aus dessen Referenzsammlung mit pypdf-
Hybridgenerierung, generisches/gefälschtes/kaputtes XML, UTF16 und andere Präfixe,
DTD/XXE/XInclude/Strukturlimits, PDF-Verschlüsselung/JS, falsche Einbettung,
verschachtelte und doppelte Names, widersprüchliche XMP-/AF-Kontexte,
Originalhash und echter Prozessabbruch. Keine reinen Extrakttext-Doubles.

KoSIT-Referenzen: Apache2, Commit1ce1dafffd035e5ce59a7ab0d3bf44ac14af16c9.
factur-x-Referenzen: BSD3, Commit650cfe34ec524ec39ea106a09df6d0cc259813a4.
Herkunft, Dateien und SHA256 in den jeweiligen ORIGIN.json neben mitgeführten
Lizenzen. Öffentliche synthetische Referenzen, keine Kundenrechnungen.
Testwerkzeuge reportlab/pypdf/factur-x sind nur im separaten Testimage.
