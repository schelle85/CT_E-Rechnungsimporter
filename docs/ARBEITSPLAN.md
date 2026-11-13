# Arbeitspakete

Stand: 13. November 2026. **AP00 ist im definierten Grundbereitstellungsumfang abgeschlossen;
AP01 ist vollständig durch den Kunden abgenommen. AP02a–c ist technisch abgeschlossen;
AP03a–c ist freigegeben und in Entwicklung, AP04 bis AP10 sind noch nicht freigegeben.** AP10 ist für die spätere wöchentliche Wartung ergänzt.
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
| AP05b | Persistente Zustände und gemeinsamer Wiederaufnahmepfad ohne Doppelablage: Eingang alle fünf Minuten, freigegebene Kundenkorrekturen alle 15 Minuten; Bedienung folgt in AP06 |
| AP05c | Kontrollierter Gesamtpfad; Erfolg erst nach erforderlicher Ablage und Mailaktionen |

Prüfstand 13.11.2026: Implementierung sowie Dienst-, Runtime- und CIFS-Helperreview
bestanden. Letzter vollständiger nativer Gesamtlauf: 155 Backendtests einschließlich
40 AP05-Gruppen ohne Fehler/Skips; spätere Ausgabegrenz-/Timeoutkorrektur gezielt
nativ geprüft. Einmaliger synthetischer Handoff mit echter XML-/OCR-Klassifikation
und echtem CIFS im exklusiven Testverzeichnis bestanden, einschließlich
DMS-Entnahme, Belegwiederverwendung und Cleanup. Der manuelle Kundenabschluss
mit Schema-/Graph-/Operator-Readback wird separat nachgewiesen. Keine Aktivierung
der 5-/15-Minuten-Zeitplanung; dauerhafter Automatikbetrieb bleibt AP08.

## AP06: Webprotokoll, Korrektur, Wiederholung und Archiv - DEV

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP06a | Übersicht/Details mit Suchfiltern, Entscheidungen, Dateien, Dubletten und Fehlern; Kachel „Prüfen“ durch „Unbekannt“ mit eigener Zuordnungsansicht ersetzen |
| AP06b | Unbekannte Anhänge einzeln zuordnen und zur Verarbeitung freigeben; Status Freigegeben → In Verarbeitung → Verarbeitet, Rechte und bestätigtes Erkennungsfeedback nachvollziehbar speichern |
| AP06c | Zwei Jahre aktiv, danach Webarchiv; keine zusätzliche Mailarchivierung |
| AP06d | Geschützte Wiederholung technisch fehlgeschlagener Vorgänge und Einstellungen |

Nur unbekannte Anhänge benötigen eine Kundenzuordnung. Erkannte Dokumente laufen
automatisch weiter. Bestätigte Korrekturen als Beispiele für gezielt geprüfte
Regeln oder Lieferantenvorlagen nutzen; kein automatisches Selbsttraining durch
einen Klick. invoice2data nur bei belegtem Nutzen ergänzen. Der vereinbarte
[GUI-/Erkennungsnachtrag](ANFORDERUNGEN.md#webkorrektur-und-erkennungsverbesserung)
ist geplant; Oberfläche und Freigabeschreibwege sind noch nicht implementiert.
Der gemeinsame manuelle Verarbeitungspfad für bereits freigegebene Korrekturen
ist in AP05 implementiert und geprüft. Seine Zeitplanung ist nicht aktiviert.

## AP07: Automatische Benachrichtigungen - DEV

| Teil | Ergebnis und Prüfung |
| --- | --- |
| AP07a | Graph-Versand, konfigurierbare Empfänger und nachvollziehbare Testmail |
| AP07b | Tägliche Zertifikatswarnung ab zehn Resttagen; Ablauf-/Fehlerfälle synthetisch prüfen |
| AP07c | Konfigurierbare Fehler-, Ausfall-, Tages- und Wochenmeldungen ohne Mailflut |

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
| AP09a | Kundenanleitung als PDF mit den tatsächlich verfügbaren Bedienwegen |
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

## Reihenfolge und offene Punkte

AP00 → AP01 → AP02 → AP03 → AP04 → AP05 → AP06 → AP07 → AP08 → AP09.
Dokumentation wird während aller Pakete gepflegt; AP09 finalisiert sie.

Mailpriorität einschließlich Unbekannt, Mahnung und gemischter Dubletten-Mails ist
seit 13.11.2026 bestätigt; Details in den [Anforderungen](ANFORDERUNGEN.md#mailabschluss-und-fahne).
Noch für die betroffenen Pakete festzulegen: Ende der Zertifikatswarnserie nach
gültigem Zertifikatswechsel und Sicherungsumfang externer SMB-Daten. Diese offenen
Punkte blockieren nicht pauschal unabhängige Arbeit.
