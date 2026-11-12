# Anforderungen

Stand: 7. November 2026. Vereinbarter Umfang, noch nicht implementiert.
Echte Postfach-, Gruppen-, Empfänger- und Verbindungswerte werden separat konfiguriert.

## Betrieb und Eingang

- Linux-VM, Docker Compose, Python-Importdienst/API, TypeScript-Weboberfläche.
- MariaDB mit persistentem lokalem Datenvolume auf der VM.
- Weboberfläche ausschließlich im Kundennetz, über HTTPS.
- Designentwurf direkt auf dem vorgesehenen Kundenserver über HTTPS entwickeln
  und zeigen. Gestaltung am öffentlichen CT-Auftritt orientieren. Kundenlogo
  optional; falls verwendet, gerade und ohne Verzerrung darstellen.
- Ein konfiguriertes Microsoft-365-Postfach über Microsoft Graph verarbeiten.
- Alle fünf Minuten den Posteingang abarbeiten, ohne parallele Doppelverarbeitung.
- Nur E-Mails mit Maileingang ab **1. Dezember 2026** berücksichtigen.
- Ältere E-Mails vollständig ignorieren und unverändert lassen.
- Fehlende benötigte Postfachunterordner unter dem Posteingang selbst anlegen.

## Anhänge und Ablage

| Inhalt | Ablagekategorie |
| --- | --- |
| ZUGFeRD | `E-Rechnung`, unveränderte Original-PDF |
| XRechnung | `E-Rechnung`, ursprüngliche XML-Datei |
| Gewöhnliche Rechnungs-PDF | `PDF` |
| Zahlungsavis-PDF einschließlich eindeutiger Zahlungs-Pre-Notifikation | `Zahlungsavis` |
| Mahnung oder Zahlungserinnerung | `Mahnung` |

Erkennung erfolgt anhand des Inhalts. Eine vollständige Validierung sämtlicher
Norm- und Geschäftsregeln ist nicht beauftragt. ZUGFeRD wird anschließend vom
kundenseitig vorhandenen DMS übernommen; eine neue DMS-Anbindung ist kein Projektumfang.

Seltene gescannte Rechnungs-PDFs benötigen Texterkennung. Arbeitskopien für OCR
nutzen und Originalanhänge unverändert aufbewahren. Andere Anhänge ignorieren.
Technische oder strukturelle Verarbeitungsfehler führen zu `failed` mit neutralem
Grund. Lesbare, aber nicht eindeutig zuordenbare Dokumente führen zu `unknown`
(Unbekannt), eindeutig irrelevante Anhänge zu `ignored`. Unbekannt gehört zum
bestehenden Postfachziel `unzugeordnet`; daraus folgt kein neuer SMB-Ordner.

SMB-Struktur unter einer konfigurierten Importfreigabe:

```text
importer/
  E-Rechnung/<Jahr>/<Monat>/KW<Nummer>/<Dateiname>
  PDF/<Jahr>/<Monat>/KW<Nummer>/<Dateiname>
  Zahlungsavis/<Jahr>/<Monat>/KW<Nummer>/<Dateiname>
  Mahnung/<Jahr>/<Monat>/KW<Nummer>/<Dateiname>
```

Grundlage ist der Maileingang. Vorgesehene technische Zeitbasis: Europe/Berlin,
Kalenderjahr und Monat des Eingangsdatums, ISO-Kalenderwoche. Monat und KW ohne
führende Null. Originaldateinamen erhalten; vorhandene Dateien nicht überschreiben.
Bei einer Namenskollision ohne Dublette eindeutigen Zusatz vor der Dateiendung setzen.

## Dubletten

Gleicher Originaldateiname und gleiche Dateigröße in Bytes gelten als Dublette.
Nur innerhalb der aktuellen Kalenderwoche vergleichen, nicht über die gesamte
Historie. Dubletten nicht erneut ablegen; E-Mail nach `unzugeordnet` verschieben
und im Web als Dublette kennzeichnen. Name und Größe bleiben auch nach einer
erforderlichen Umbenennung des gespeicherten Originals nachvollziehbar.

**Noch offen:** genaue Regel für eine E-Mail mit neuen relevanten Anhängen und
Dubletten gleichzeitig. Die Regel vor Implementierung dieses Sonderfalls festlegen.

## Mailabschluss und Fahne

Jeden relevanten Anhang einzeln ablegen. Nach bestätigter Vorgabe vom12.11.2026
laufen erkannte PDF- und E-Rechnungen automatisch. Eine manuelle Bestätigung
gewöhnlicher Rechnungs-PDFs ist nicht mehr vorgesehen. Nur bei `unknown` muss
der Benutzer die Dokumentart klären; das Ziel ist `unzugeordnet`.

Die Mail erst nach den erforderlichen erfolgreichen Schritten abschließen.
Die Mischmail-Priorität für unterschiedliche Kategorien, Unbekannt, Fehler und
Dubletten bleibt vor AP05 zu klären. Ignorierte Anhänge sind kein technischer
Fehler. Dieser Dokumentvertrag startet keinen Worker oder Korrekturjob.

Bei mehreren tatsächlichen Anhängen eine Outlook-Fahne setzen. Eingebettete
Signaturbilder nicht mitzählen. Die Fahne muss nach dem Verschieben erhalten bleiben.
Erfolg erst nach vollständiger erforderlicher Dateiablage verbuchen.

## Zugriff und Administration

- Bestehende Windows-AD-Konten über LDAPS/StartTLS mit geprüfter Serveridentität.
- Eine konfigurierte AD-Gruppe erhält Vollzugriff auf die Anwendung.
- Eine konfigurierte AD-Gruppe erhält ausschließlich Leserechte.
- Keine eigene Passwortverwaltung für diese Benutzer.
- Vollzugriff umfasst Einstellungen, Empfänger und Wiederholung fehlgeschlagener Vorgänge.
- Berechtigungen sowohl in der Oberfläche als auch serverseitig durchsetzen.
- Änderungen und manuell ausgelöste Wiederholungen protokollieren.
- Entzogene Gruppenrechte/gesperrte Konten bei Sitzungs- und Rechteprüfung berücksichtigen.

## Protokoll und Webarchiv

Verarbeitungsläufe, zugehörige Mails/Anhänge, Kategorien, Erkennungs- und Fehlergründe,
Dateiziele, Namenszusätze, Dubletten, Fahnen, Verschiebungen und Wiederholungen
nachvollziehbar anzeigen. Such-/Filtermöglichkeiten vorsehen.

Protokolle zwei Jahre aktiv führen; danach im Webarchiv weiter zugänglich halten.
Keine automatische Löschung ableiten. Die Anwendung übernimmt außer den vereinbarten
Verarbeitungsschritten keine Mailarchivierung oder zeitgesteuerte Maillöschung.
Die weitere Pflege des Postfachs bleibt eine organisatorische Aufgabe beim Kunden.

## Benachrichtigungen

Nur automatische Mails über die bestehende Graph-Anbindung; kein manueller Mail-Editor.
Fehler-, Ausfall-, Tages- und Wochenmeldungen vorsehen. Meldungsauswahl, Empfänger
und Zeitpläne im Web für die Verwaltungsgruppe konfigurierbar machen.

Zertifikatswarnung für das Graph-Anmeldezertifikat:

- Ab zehn Tagen vor Ablauf täglich warnen.
- Auch am Ablauftag und danach weiter versuchen, soweit Graph-Versand funktioniert.
- Ausschließlich vorhandenen Graph-Versand nutzen; kein SMTP-Ersatzweg.
- Keine garantierte Warnzustellung nach Ablauf; Versuch/Fehler im Protokoll anzeigen.
- Tageszustand persistent speichern, damit Neustarts keine doppelten Warnserien erzeugen.
- Ende der Warnserie nach geprüftem Zertifikatswechsel noch konkretisieren.

Graph-Anmeldezertifikat und HTTPS-Zertifikat haben unterschiedliche Aufgaben.
Das vorhandene HTTPS-Zertifikat wird extern alle 60 Tage erneuert. Erneuerte Dateien
prüfen, übernehmen und das tatsächlich verwendete Zertifikat kontrollieren.

## Wöchentliche Wartung

Ein serverseitiges Skript soll sonntags um 03:00 Uhr Europe/Berlin Linux-Updates
installieren und bei Bedarf neu starten. Zustände und Fehler protokollieren,
gleichzeitige Wartungsläufe verhindern und Dienste/SMB-Mounts nach Neustart prüfen.
ORGA kontrolliert die tatsächlichen Ergebnisse nach dem Wartungsfenster.
Noch keine Implementierung oder aktive Terminierung. Automatische ungeprüfte
Anwendungsreleases und Datenbankschemaänderungen sind davon nicht umfasst.

## Speicherung, Sicherung und Tests

SMB-Freigaben werden über `fstab` auf dem Host eingebunden und den Containern
bereitgestellt. Zertifikate nur lesend einbinden. Vor Verarbeitung echte Mounts
prüfen; ein leerer lokaler Mountpunkt darf keine scheinbare SMB-Ablage ermöglichen.

Die bestehende VM-Sicherung läuft täglich einschließlich Offsite-Backup.
Sicherungsumfang externer SMB-Quellen gesondert zuordnen. Wiederherstellbarkeit
nur im tatsächlich geprüften Umfang behaupten.

Testmailversand über das vorgesehene Postfach ist autorisiert. Der Stichtagsfilter
bleibt für Produktivverarbeitung wirksam; frühere Tests können isoliert mit
synthetischen Daten erfolgen. Keine echten Kundendokumente in dieses öffentliche Repo.
