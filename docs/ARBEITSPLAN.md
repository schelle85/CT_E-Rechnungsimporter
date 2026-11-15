# Arbeitspakete

Stand: 15. November 2026. **AP00 ist im definierten Grundbereitstellungsumfang abgeschlossen;
AP01 ist vollständig durch den Kunden abgenommen. AP02a–c ist technisch abgeschlossen;
AP03 ist eingefroren, AP04 ist im Grundlagenumfang technisch abgeschlossen.
AP05a–c ist im definierten manuellen Umfang technisch abgeschlossen und bereitgestellt.
AP06a–d samt PDF-Vorschau ist technisch abgeschlossen und bereitgestellt;
Kundenmigration auf006 und getrenntes Rücklesen bestanden. AP07a–c ist freigegeben
und in Prüfung; A-Quell-/Native-Nachweis und B-Quellreview bestanden,
C implementiert und gezielt lokal geprüft, unabhängige C-Abnahme offen.
AP08 und spätere Pakete bleiben ohne Go;
dauerhafter Automatikbetrieb gehört in AP08.**
AP10 ist für die spätere wöchentliche Wartung ergänzt.
ORGA koordiniert, DEV implementiert, REVIEW prüft.
Die Repositoryvorbereitung ist kein Beginn der Anwendungsentwicklung.

Jedes Unterpaket liefert ein abgegrenztes Ergebnis mit passender Prüfung,
Dokumentationsnachtrag und geprüftem GitHub-Upload. Abhängigkeiten und ungelöste
Fehler offen benennen. Kein pauschales Go je Unterpaket erforderlich.
Jedes AP benötigt sein eigenes Go; die Freigabe von AP00 gibt keine späteren AP frei.
Graph-Grundanbindung in AP00d geprüft: Zertifikatszugriff, begrenzte Mailrechte,
positive/negative Leseprobe sowie tatsächlicher Testversand und Empfang.
Details und Grenzen im [Betriebsstand](BETRIEBSSTAND.md).

## AP00: Technik vorbereiten - Betreiber

| Teil | Ergebnis |
| --- | --- |
| AP00a | Linux-VM, Ressourcen, Netz und internes DNS bereit |
| AP00b | Schlüsselzugang und administrative Ausführung geprüft; SSH-Passwortanmeldung deaktiviert, positive/negative Prüfung bestanden |
| AP00c | Import-/SSL-Freigaben per Fstab eingebunden; Lese-/Schreibrechte und Kategorieordner geprüft |
| AP00d | AD-Gruppen/Verbindung, Graph-App/Zertifikat und HTTPS-Dateien verfügbar |
| AP00e | Lokale Datenvolumes und tägliche VM-/Offsite-Sicherung zugeordnet |
| AP00f | VM einschließlich SMB als bereit bestätigt |

AP00-Grundbereitschaft ist nach unabhängiger Nachweisprüfung bestätigt; siehe
[Betriebsstand](BETRIEBSSTAND.md). LDAP-Login, HTTPS-/Anwendungsbetrieb,
vollständige Graph-Funktionen und Wiederherstellung werden in ihren späteren
Arbeitspaketen geprüft. Das eigene AP01-Go liegt inzwischen vor.

## AP01: Design, Administration und AD-Anmeldung - DEV

Vorgabe vom 08.11.2026: Den Entwurf direkt auf dem vorgesehenen Kundenserver
bereitstellen und schon während der Entwicklung über HTTPS prüfen.
Gestaltung an [CT Beschläge](https://www.ct-beschlaege.de/) anlehnen;
das Kundenlogo ist optional. Falls verwendet, gerade und mit unverzerrtem
Seitenverhältnis darstellen; seine Übernahme ist kein Abnahmekriterium.
Vorgesehener Webserver ist Nginx Open Source im Docker-Setup: statische
Weboberfläche, HTTPS und Reverse Proxy zur Python-API. Vorhandene Zertifikate
geschützt serverseitig übernehmen; PFX bei Bedarf in PEM überführen und
Zertifikatswechsel einschließlich Konfigurationsprüfung und Reload vorsehen.
AP01-Go am 08.11.2026 erteilt; DEV beginnt mit Design und HTTPS-Grundgerüst,
danach folgen AD-Anmeldung, Administrationsgrundlage und gemeinsame Abnahme.

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP01a | Abgenommen: synthetischer Oberflächenentwurf, Desktop-/Mobilprüfung; Anmeldung und Administration noch gesperrt |
| AP01b | Abgenommen: Docker-/Python-/TypeScript-/MariaDB-Grundbetrieb, echtes HTTPS/HTTP-Weiterleitung, Containerpersistenz und TLS-Reload |
| AP01c | Abgenommen: verschlüsselte LDAP-Anmeldung, Gruppenrechte, Sitzungen und Abmeldung; positive/negative Zugriffsprüfung |
| AP01d | Abgenommen: Administrationsgrundlage; geschützte Einstellungen und Änderungsprotokoll |
| AP01e | Abgenommen: Oberfläche und Backendrechte geprüft; Kundengesamtabnahme12.11.2026 bestätigt |

## AP02: Graph und Postfacheingang - DEV

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP02a | Implementiert/geprüft: Zertifikatsclient und manuelle Betreiberprobe; kein dauernder Graphdienst |
| AP02b | Abgeschlossen: Paging/Stichtag/Anhangabruf isoliert; echte gefilterte Leerprobe bestätigt |
| AP02c | Abgeschlossen: additive003 und fünf Inboxziele mit Wiederverwendung bereitgestellt; Move/Flag isoliert geprüft, keine echten Mailmutationen |

## AP03: Anhänge erkennen - DEV

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP03a | Implementiert und isoliert geprüft: ZUGFeRD1/2, Factur-X und XRechnung3.0 mit vorhandenen Bibliotheken, keine Vollvalidierung |
| AP03b | Implementiert/isoliert geprüft: nachvollziehbare Textentscheidung mit echten PDF-Gegenfällen und erlaubten Begleitseiten |
| AP03c | Implementiert/isoliert geprüft: bedarfsweise lokale OCR, Scans/Mischseiten/Drehung, Prozessabbruch/Cleanup und unveränderte Originale |

## AP04: SMB-Ablage und Dubletten - DEV

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP04a | Kategorie/Jahr/Monat/KW nach Maileingang; Mount- und Datumsgrenzen prüfen |
| AP04b | Originalnamen, eindeutige Zusätze und Ablage ohne Überschreiben |
| AP04c | Dubletten anhand Originalname/Bytegröße nur innerhalb aktueller KW erkennen |

## AP05: Vollständiger Verarbeitungslauf - DEV

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP05a | Mehrfachanhänge und Fahnen; bestätigte Mailpriorität Failed → unzugeordnet → Mahnung → Nachfragen → Zahlungsavis → Success umsetzen; Anhänge unabhängig passend ablegen |
| AP05b | Persistente Zustände und gemeinsamer manueller Wiederaufnahmepfad ohne Doppelablage; Bedienung in AP06 implementiert. Geplante 5-/15-Minuten-Timer bleiben inaktiv. |
| AP05c | Kontrollierter Gesamtpfad; Erfolg erst nach erforderlicher Ablage und Mailaktionen |

Prüfstand 13.11.2026: Implementierung sowie Dienst-, Runtime- und CIFS-Helperreview
bestanden. Letzter vollständiger nativer Gesamtlauf: 155 Backendtests einschließlich
40 AP05-Gruppen ohne Fehler/Skips; spätere Ausgabegrenz-/Timeoutkorrektur gezielt
nativ geprüft. Einmaliger synthetischer Handoff mit echter XML-/OCR-Klassifikation
und echtem CIFS im exklusiven Testverzeichnis bestanden, einschließlich
simulierter DMS-Entnahme, Belegwiederverwendung und Cleanup. Geschütztes Backup, additives
Kundenschema003→005, unveränderte Instanz/Konfiguration sowie sechs Inboxziele
einschließlich Mahnung sind belegt. Echter Scan ab unverändertem Stichtag und
manueller Operatorlauf bestätigen 0 passende Mails/0Quanten. API/GUI und die drei
laufenden Dienste bleiben unverändert; keine Timer oder produktive Dateipublikation.
Damit ist AP05 im definierten manuellen Umfang technisch abgeschlossen.
Die 5-/15-Minuten-Zeitplanung bleibt inaktiv; dauerhafter Automatikbetrieb ist AP08.

## AP06: Webprotokoll, Korrektur, Wiederholung und Archiv - DEV

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP06a | Implementiert und isoliert geprüft: echte Journalübersicht/Details, Suche/Filter/Seitenwahl, einzelne unbekannte Anhänge, Fehler/Dubletten/Belege und großer geschützter PDFdialog mit Tab-/Downloadfallback |
| AP06b | Implementiert und isoliert geprüft: ausdrückliche generationgebundene Zuordnung je Anhang; Erstbefund, aktueller Befund, Freigeber und Verlauf getrennt. Freigegeben → In Verarbeitung → Verarbeitet erst nach erforderlichen Wirkungsbelegen. Antwortverlust/Reload/Neuanmeldung geprüft. |
| AP06c | Implementiert und isoliert geprüft: zwei Kalenderjahre aktiv, danach schreibgeschütztes Webarchiv; keine Löschung oder Mailarchivierung |
| AP06d | Implementiert und isoliert geprüft: dauerhafte technische Retryabsicht, Wiederverwendung bestehender Quellen-/Wirkungsbelege sowie versionierte Vorschau-/Retryeinstellungen |

Nur unbekannte Anhänge benötigen eine Kundenzuordnung. Erkannte Dokumente laufen
im gemeinsamen manuellen Verarbeitungspfad ohne zusätzliche Freigabe weiter.
Bestätigte Korrekturen als Beispiele für gezielt geprüfte
Regeln oder Lieferantenvorlagen nutzen; kein automatisches Selbsttraining durch
einen Klick. invoice2data nur bei belegtem Nutzen ergänzen. Der vereinbarte
[GUI-/Erkennungsnachtrag](ANFORDERUNGEN.md#webkorrektur-und-erkennungsverbesserung)
ist mit Oberfläche und Freigabeschreibwegen implementiert und isoliert geprüft.
Der gemeinsame manuelle Verarbeitungspfad für bereits freigegebene Korrekturen
ist in AP05 implementiert und geprüft. Seine Zeitplanung ist nicht aktiviert.

Abschlussnachweis vom 14.11.2026: Quellreview, gezielte native Migration-/Sicherheits-/
Konkurrenz-/Vorschauprüfungen und fünf tatsächliche Browsergruppen bestanden.
PDF-Sicht im Dialog und neuen Tab bestätigt. Zwei langsame 25-MiB-Abrufe bleiben
im Vorschauspeicher mit 128 MiB begrenzt; dritter Abruf mit HTTP 503, Frist/Cleanup bestanden.
Kundenmigration auf006 und neue API/Web sind davon getrennt bereitgestellt und
zurückgelesen: Instanz/Konfiguration und Datenbank erhalten, HTTPS-Journalmodus,
Zugriffsschutz, vollständiger Graph-GET-Leerscan und inaktive Timer bestätigt.
Keine erneute tatsächliche AP06-Kundenanmeldung aus diesem Betriebsnachweis ableiten.
DMS-Anbindung, -Konfiguration und -Prüfung sind keine Auftrags-/Abnahmebestandteile.

## AP07: Automatische Benachrichtigungen - DEV

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP07a | A-Request-/Einmalverträge und B-Sender im Quellenreview bestanden. C-Webkonfiguration, ursprüngliche AD-/UUIDbindung, feste Vorschau/Testaktion/Status und ASGI-Gesamtbudget implementiert, gezielt lokal geprüft. Unabhängiger C-Review/native Web-/Initialprobe separat. |
| AP07b | B-Nachfolgerproof und Serienbindung einschließlich B2 bestanden. Negative Restzeit bleibt best effort warnpflichtig. C-Portal-/Loginhinweis für beide Rollen trennt lokale PEMmetadaten, offene Serie und gespeicherten Proof. Pflichtwarnung nicht abschaltbar; Browserabnahme offen. |
| AP07c | C verbindet tatsächliche Journalfehler und begrenzte API-/Graphproben mit den vorhandenen A-Snapshots/Wiederholsperren. Administration→Berichte zeigt echte Tages-/Wochen-/freie Journalzeiträume und korrekte Leere. Gezielte lokale Prüfungen bestanden; native-/Browserabnahme offen. |

AP07-Go vom14.11.2026. A-Quell-/Native-Nachweise und B-Quellreview bestanden;
B2 nachVersuch1 geschlossen. C-Leseteil und Testaktion als getrennte Teilpins,
Beobachter als eigener Teilstand; C-Review/native-/Browserprüfung auf festem Pin.
Keine Kundenabnahme daraus. AP11-Planung bleibt unverändert ohne Umsetzungs-Go.
Kundenschema bleibt006, keine echteSendMail, Kundenmigration oder Timeraktivierung.
Vertrag und Grenzen: [AP07](AP07-NOTIFICATIONS.md), [Betreiber-CLI](AP07-OPERATOR.md).

## AP08: Betriebsprüfung und Übergang - DEV / REVIEW / ORGA

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP08a | Zusammenhängende Gesamtprüfung einschließlich Neustart, Mounts, Rollen und SSL-Übernahme |
| AP08b | Bestehende Sicherung berücksichtigen; isolierten Wiederanlauf mit belegtem Umfang koordinieren |
| AP08c | Kontrollierter Automatikbetrieb mit wirksamem Stichtag und eindeutigem Vorgangsstand |
| AP08d | Betreiberabläufe, Überwachung, Updates und Rückkehr zum Vorzustand zugeordnet |

## AP09: Abschlussdokumentation und Übergabe - ORGA / DEV / REVIEW

| Teil | Ergebnis |
| --- | --- |
| AP09a | Kundenunterlagen zusammenführen; das vollständige Nutzerhandbuch aus AP11 als führende Kundenanleitung übernehmen |
| AP09b | Technische Dokumentation für Betreiber/Kunde, als Markdown-Quelle und PDF |
| AP09c | KI-Dokumentation als Markdown mit festem Stand, Invarianten und Wiedereinstieg |
| AP09d | Inhalt gegen Liefercommit prüfen, PDFs rendern/sichten, finale Unterlagen hochladen |

DEV liefert technische Fakten und Prüfbelege. ORGA führt die Dokumentation zusammen;
REVIEW prüft Widersprüche und nicht belegte Behauptungen. PDFs erst aus dem
tatsächlich implementierten Stand erstellen, keine fertige Installation vortäuschen.

## AP10: Wöchentliche Wartung und Kontrolle - DEV / ORGA

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP10a | Umfang: sonntags 03:00 Europe/Berlin Linux-Updates und Neustart bei Bedarf |
| AP10b | DEV erstellt Wartungsskript mit Sperre, Fehlerbehandlung und Vor-/Nachprotokoll |
| AP10c | Serverzeitplan und Wiederanlauf mit echten Mounts und gesunden Diensten |
| AP10d | ORGA-Nachkontrolle nach dem Wartungsfenster; fehlender Zugang als nicht prüfbar melden |
| AP10e | Kontrollierter Probelauf, Dokumentation und anschließender regelmäßiger Betrieb |

Kein Wartungsskript oder Timer ist bereits installiert. Keine ungeprüften
Anwendungs-/Datenbankschemaupgrades aus der Linux-Wartungsfreigabe ableiten.
AP10-Einrichtung und Prüfung vor der Finalisierung der Abschlussunterlagen berücksichtigen.

## AP11: Handbuch zum Produkt - ORGA / DEV / REVIEW

Am 14.11.2026 ausdrücklich als eigenes Arbeitspaket ergänzt. Status: geplant;
die Erstellung beginnt mit dem gesonderten AP11-Go.

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP11a | Alle tatsächlich gelieferten Bereiche, Begriffe und Bedienwege erfassen; Unterschiede zwischen Lesen und Verwaltung erklären |
| AP11b | Anmeldung, Übersicht, Vorgänge, Suche/Filter, Kategorien, Mailordner und Mehrfachanhänge schrittweise erklären |
| AP11c | Unbekannt-Zuordnung, PDF-Vorschau, Korrekturen, technische Wiederholung, Dubletten und Archiv mit Beispielen erklären |
| AP11d | Administration einschließlich Berichten, Empfängern, Benachrichtigungen, Zertifikatshinweisen und erlaubten Einstellungen erklären |
| AP11e | Alltagsszenarien, häufige Fragen, typische Fehlermeldungen und den Weg zur Betreuung ergänzen; Grenzen und erwartete Wartezustände benennen |
| AP11f | Pflegbare Markdown-Quelle und vollständige PDF mit Inhaltsverzeichnis, passenden Bildschirmbildern und eindeutigem Produktstand erstellen |
| AP11g | Jeden beschriebenen Bedienweg am Lieferstand abgleichen; PDF vollständig rendern/sichten, REVIEW und Kundenrückmeldung einarbeiten |

Das Handbuch umfasst sämtliche verfügbaren Softwarefunktionen für Nutzer und
kundenseitige Administratoren. Bildschirmbilder verwenden den geprüften
Auslieferungsstand und geeignete neutrale beziehungsweise synthetische Beispiele.
AP09a übernimmt diese eine führende Nutzeranleitung; technische Dokumentation und
KI-Dokumentation bleiben eigene Lieferungen. Umfang und Ausgabe siehe
[Dokumentationsplan](DOKUMENTATIONSPLAN.md).

## Reihenfolge und offene Punkte

AP00 → AP01 → AP02 → AP03 → AP04 → AP05 → AP06 → AP07 → AP08 → AP11 → AP09.
AP11 beschreibt den geprüften Funktionsstand nach AP08. Die Einrichtung und
Prüfung von AP10 wird bei den betroffenen Betriebsunterlagen berücksichtigt;
der laufende Wochenbetrieb ist kein Endtermin für das Handbuch.
Dokumentation wird während aller Pakete gepflegt; AP09 finalisiert das Lieferpaket.

Mailpriorität einschließlich Unbekannt, Mahnung und gemischter Dubletten-Mails ist
seit 13.11.2026 bestätigt; Details in den [Anforderungen](ANFORDERUNGEN.md#mailabschluss-und-fahne).
Das Ende einer Zertifikatswarnserie ist bestätigt: erst nach erfolgreicher frischer
Anmeldung mit einem gültigen Nachfolger. Der vorhandene bestätigte Sicherungsweg
wird in den Betriebsunterlagen mit seinen Zuständigkeiten festgehalten.
