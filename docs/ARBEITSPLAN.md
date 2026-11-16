# Arbeitspakete

Stand: 16. November 2026. **AP00 ist im definierten Grundbereitstellungsumfang abgeschlossen;
AP01 ist vollständig durch den Kunden abgenommen. AP02a–c ist technisch abgeschlossen;
AP03 ist eingefroren, AP04 ist im Grundlagenumfang technisch abgeschlossen.
AP05a–c ist im definierten manuellen Umfang technisch abgeschlossen und bereitgestellt.
AP06a–d samt PDF-Vorschau ist technisch abgeschlossen und bereitgestellt;
Kundenmigration auf006 und getrenntes Rücklesen bestanden. AP07a–c ist technisch
abgeschlossen und bereitgestellt: A/B vollständig, C-Quellenreview, 21 native
C-MariaDBfälle und acht isolierte HTTPS-Browsergruppen bestanden. Aktuell Schema 007,
API/Web aus gleicher fester Quelle, Instanz/LDAP-Konfiguration und DBdienst erhalten.
AP08 ist im vereinbarten Umfang technisch abgeschlossen und aus
413095f823702d39b02bc8b3c989b526fdf808d0 bereitgestellt. Echte HTTPSübernahme/No-op
und Notificationvorlauf sind bestätigt; Startdienst/fünf Timer seit 16.11.2026,
19:44:23 Europe/Berlin enabled/active. Geplante Leerlaufläufe und je ein angenommener
Tages-/Wochenbericht sind bestätigt. Wiederanlauf nach kontrolliertem Reboot und
TLS-Stundenlauf um 20:00 sind belegt. Drei automatische Statuszyklen nach dem
separat gesetzten Phasenversatz sind bestanden.
AP12 ist seit 16.11.2026 zur Umsetzung freigegeben; Kern B als Quellstand geliefert.
AP09/10/11 bleiben ohne Umsetzungs-Go.**
AP10 ist für die spätere wöchentliche Wartung ergänzt.
AP12 ist seit 16.11.2026 für Graph-Zertifikatsrotation und einen zusätzlichen
Adminreiter freigegeben; aktuelle Lieferung und Grenzen unten.
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
| AP05b | Persistente Zustände und gemeinsamer manueller Wiederaufnahmepfad ohne Doppelablage; Bedienung in AP06 implementiert. Zum AP05-Abschluss blieben die geplanten 5-/15-Minuten-Timer inaktiv. |
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
Zum AP05-Abschluss blieb die 5-/15-Minuten-Zeitplanung inaktiv; aktuelle Aktivierung unter AP08.

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
| AP07a | Bereitgestellt: versionierte Einstellungen, eigener Notificationkey, ursprüngliche AD-/UUIDbindung, feste Vorschau/Testaktion/Status und gemeinsames 80-s-Budget. A/B-/C-Quellen- und native Prüfungen bestanden; echte Anmeldung und genau eine Testmail (HTTP 202) mit Reservierung 1/getrenntem Status bestätigt. Empfang im eigenen Abnahmepostfach belegt. |
| AP07b | Bereitgestellt und isoliert im Browser geprüft: lokale PEMmetadaten, offene Serie und gespeicherter Nachfolgerproof getrennt; exakte 10d-/1d-/0-/Negativschwellen, laufender Portal- und gesonderter Loginhinweis für beide Rollen. Pflichtwarnung nicht abschaltbar, negative Restzeit bleibt best effort warnpflichtig. |
| AP07c | Bereitgestellt: tatsächliche Journal-/API-/Graphbeobachter und vorhandene Wiederholsperren; Administration→Berichte mit echten Tages-/Wochen-/freien Journalzeiträumen und korrekter Leere. 21 C-Fälle auf MariaDB, acht HTTPS-Browsergruppen und zusätzlicher synthetischer CLIplan bestanden. Zum AP07-Abschluss war die Automatik inaktiv. |

AP07-Go vom 14.11.2026; technisch abgeschlossen und am 15.11.2026 bereitgestellt aus
`5ecfd59270b63947d3f92af98a1b9f8e5a267aeb`. Schema 007, API/Web, erhaltene Instanz/
LDAP-Konfiguration und DBdienst getrennt bestätigt. Drei Empfänger privat initialisiert;
Empfang der einen Testmail ausschließlich im eigenen Abnahmepostfach nachgewiesen.
Keine frische tatsächliche Kundenanmeldung nach AP07; echte AD-Abnahme aus AP01
bleibt historisch. Zum AP07-Abschluss waren die Zeitpläne inaktiv, Zeiten gespeichert.
Die aktuelle Aktivierung ist unten in AP08 dokumentiert; AP09/10/11 bleiben ohne Freigabe.
AP11-Planung bleibt erhalten.
Vertrag und Grenzen: [AP07](AP07-NOTIFICATIONS.md), [Betreiber-CLI](AP07-OPERATOR.md).

## AP08: Betriebsprüfung und Übergang - DEV / REVIEW / ORGA

Status: Seit 16.11.2026 im vereinbarten Umfang technisch abgeschlossen. A: Laufzeitbasis,
Testmailausschluss, Sperre, Grenzen und Fairness. B: Start/Drain, Timer und
geprüfte HTTPSübernahme. C: eigener begrenzter Hoststatus, geschützte GETroute
für beide Rollen und frische konsistente GUIanzeige, inzwischen aus 413095f
bereitgestellt. Base-Apply und Readback erhalten DBzustand/Schema 007/Instanz/
Konfiguration; C-GUI isoliert bestanden. Echte TLSübernahme und folgender No-op
sowie Notificationvorlauf mit Nullvorschauen bestätigt. Startdienst/fünf Timer
seit 16.11.2026 19:44:23 Europe/Berlin enabled/active. Korrekturen um 19:45 und
Inbox um 19:50 nach Sperrdeferred je 0 Quanten / 0 remaining bestätigt; Tages-/Wochenbericht
je einmal 202 accepted, keine offenen Postwirkungen. Preboot-Gate um 19:50:28 bestanden;
kontrollierter Reboot und geplanter TLS-Stundenlauf um 20:00 belegt. Nach dem
Reboot wurde am 16.11.2026 um 20:15:08 Europe/Berlin separat der Statusversatz
gesetzt: genau ein Kalender auf Sekunde 20, Timer active/enabled. Drei
aufeinanderfolgende automatische Kontrollzyklen um 20:16:21, 20:17:21 und 20:18:21
bestätigen active, abgeschlossene Notificationläufe und erhaltene Bindungen.
Führender Vertrag:
[AP08-Betrieb](AP08-BETRIEB.md).

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP08a | Abgeschlossen: C bereitgestellt; Base-/Status-/GUI-/Mount-/TLSnachweise, kontrollierter Wiederanlauf mit erhaltenen Bindungen und drei automatische Statuszyklen nach dem separaten Phasenversatz bestanden. Isolierte Rollenprüfung ist keine neue Kundenanmeldung. |
| AP08b | Im belegten Sicherungs-/isolierten Wiederanlaufumfang abgeschlossen. Die bestehenden Nachweise bleiben erhalten; ein vollständiger VMrestore ist nicht nachgewiesen. |
| AP08c | Abgeschlossen: Startdienst/fünf Timer enabled/active; geplante Inbox-/Korrekturleerlaufläufe samt Sperrdeferred/Folgegelegenheit, zwei einmalige 202-Berichtsannahmen und TLS-Stundenlauf um 20:00 bestätigt. Nachbootläufe erhalten eindeutige Mailbelege; drei automatische Statuszyklen nach dem Versatz bestanden. Stichtag unverändert. |
| AP08d | Abgeschlossen: Betreiber-/Drain-/Rückwege, Statusvertrag, Preboot-Gate und kontrollierter Wiederanlauf belegt. Statusphasenversatz nach dem Reboot um 20:15:08 separat gesetzt und automatisch kontrolliert. Anwendung bleibt 413095f; kein zweiter Reboot daraus abgeleitet. |

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
Nach Lieferung von AP12 Wartung und Zertifikatswechsel koordinieren, damit ein
Neustart nicht unkontrolliert in einen laufenden Wechsel eingreift.

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

## AP12: Graph-Zertifikatsrotation und Administration - DEV / REVIEW / ORGA

Am 16.11.2026 als eigenes Arbeitspaket angenommen und eingeplant.
Status: Eigenes Umsetzungs-Go seit 16.11.2026. Entwurf samt K1 zur dauerhaften
Graphgrenze akzeptiert. Kern B liefert Appadapter/PoP/Kandidat, additive 008-Aufträge,
Rootwirkungsjournal, lesenden Wiederabgleich und Keyinventar als Quellstand;
28 gezielte lokale Fälle bestanden. Noch kein Deployment oder Wechsel im Betrieb.
Host-/API-Freigabe, Verbraucherübernahme, Reiter und Zeitplanung folgen getrennt.
AP08 bleibt der tatsächlich bereitgestellte Betriebsstand.

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP12a | Vorhandene Graph-/Zertifikatsbausteine prüfen; begrenzten Hostauftrag, AD-Rechte, Wechselzustand und Rückweg entwerfen |
| AP12b | Betreiberskript: lokal erzeugen, öffentlichen Teil zusätzlich registrieren, frische Anmeldung und tatsächliche Verbraucher prüfen, kontrolliert aktivieren |
| AP12c | Reiter Administration → Graph-Zertifikat mit Status, Verlauf und geschützter Aktion „Jetzt erneuern“; GR_CEO liest, GR_Rechnung verwaltet |
| AP12d | Tägliche Prüfung und automatische Erneuerung planen/gezielt aktivieren; vorgesehener Vorlauf 30 Tage, gleiche Sperre und gleicher Ablauf wie beim manuellen Start |
| AP12e | Sieben Tage Überlappung bei ausreichender Gültigkeit, nur verwaltete Altkeys bereinigen; Abbruch-/Rückweg und administrative Wiederherstellung dokumentieren |
| AP12f | Gezielte Rechte-, Wiederholungs-, Konkurrenz-, Graph-, Übernahme- und Fehlerprüfungen; unabhängige Abnahme |
| AP12g | Bedienfakten an AP11 und technische Abläufe an AP09 übergeben; README/KI-/Betriebsdokumentation aktualisieren |

Umfang und Grenzen: [AP12-Plan](AP12-GRAPH-ZERTIFIKATSROTATION.md).
Privater Schlüssel bleibt auf Linux; Webauslöser verwendet einen festen Hostauftrag.
HTTPS-Zertifikat und bestehende Pflichtwarnung bleiben getrennt berücksichtigt.

## Reihenfolge und offene Punkte

AP00 → AP01 → AP02 → AP03 → AP04 → AP05 → AP06 → AP07 → AP08 → AP12 → AP11 → AP09.
AP12 baut auf AP07 auf und ist nach AP08, vor Handbuch und Übergabe eingeplant.
AP11 beschreibt den geprüften Funktionsstand einschließlich eines ausgelieferten AP12. Die Einrichtung und
Prüfung von AP10 wird bei den betroffenen Betriebsunterlagen berücksichtigt;
der laufende Wochenbetrieb ist kein Endtermin für das Handbuch.
Dokumentation wird während aller Pakete gepflegt; AP09 finalisiert das Lieferpaket.

Mailpriorität einschließlich Unbekannt, Mahnung und gemischter Dubletten-Mails ist
seit 13.11.2026 bestätigt; Details in den [Anforderungen](ANFORDERUNGEN.md#mailabschluss-und-fahne).
Das Ende einer Zertifikatswarnserie ist bestätigt: erst nach erfolgreicher frischer
Anmeldung mit einem gültigen Nachfolger. Der vorhandene bestätigte Sicherungsweg
wird in den Betriebsunterlagen mit seinen Zuständigkeiten festgehalten.
