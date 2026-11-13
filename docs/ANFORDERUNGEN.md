# Anforderungen

Stand: 13. November 2026. Vereinbarter Sollumfang; den tatsächlichen
Umsetzungsstand zeigt die [README](../README.md).
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

**Bestätigt am 13.11.2026:** Neue relevante Anhänge auch bei gleichzeitig vorhandenen
Dubletten passend ablegen; Dubletten überspringen. Die Mail kommt nach
`unzugeordnet`, sofern kein Verarbeitungsfehler mit höherer Priorität vorliegt.

## Mailabschluss und Fahne

Jeden relevanten Anhang einzeln ablegen. Nach bestätigter Vorgabe vom12.11.2026
laufen erkannte PDF- und E-Rechnungen automatisch. Eine manuelle Bestätigung
gewöhnlicher Rechnungs-PDFs ist nicht mehr vorgesehen. Nur bei `unknown` muss
der Benutzer die Dokumentart klären; das Ziel ist `unzugeordnet`.

Die Mail erst nach den erforderlichen erfolgreichen Schritten abschließen.
Am **13.11.2026 bestätigt**: Für die gesamte Mail gilt die höchste vorliegende
Zielordner-Priorität:

1. `Failed`: erforderliche Verarbeitung fehlgeschlagen.
2. `unzugeordnet`: mindestens ein Anhang noch unbekannt oder eine Dublette vorhanden.
3. `Mahnung`: Mahnung oder Zahlungserinnerung enthalten.
4. `Nachfragen`: gewöhnliche PDF-Rechnung enthalten.
5. `Zahlungsavis`: Zahlungsavis enthalten.
6. `Success`: ausschließlich E-Rechnungen als relevante Anhänge erfolgreich abgelegt.

Jeden erkannten Anhang unabhängig vom Mailziel passend ablegen. Ignorierte
Anhänge sind kein technischer Fehler; Mails ohne relevante Anhänge kommen nach
`unzugeordnet`. Nach Klärung unbekannter Anhänge das Mailziel erneut nach dieser
Priorität bestimmen. Dieser Dokumentvertrag startet keinen Worker oder Korrekturjob.

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

## Webkorrektur und Erkennungsverbesserung

Vereinbarter Nachtrag für AP05/AP06; noch keine implementierte Korrekturoberfläche
oder aktivierter Korrekturjob:

- Die Designkachel „Prüfen“ heißt künftig „Unbekannt“ und zählt nur Anhänge mit
  offener Zuordnung. Erkannte PDF-/E-Rechnungen, Avise und Mahnungen benötigen
  keine zusätzliche Bestätigung durch den Kunden.
- In einer eigenen Ansicht Originalanhang, Dateiname und verständlichen Grund
  anzeigen. Je unbekanntem Anhang PDF-Rechnung, Zahlungsavis,
  Mahnung/Zahlungserinnerung oder Sonstiges/ignorieren wählen und anschließend
  zur Verarbeitung freigeben. Die Verwaltungsgruppe darf korrigieren, die
  Lesergruppe bleibt lesend; Rechte auch serverseitig prüfen. Widersprüchliche
  E-Rechnungsstrukturen oder technische Fehler nicht durch eine Kategorieauswahl
  ungeprüft übergehen.
- Freigegebene Korrekturen alle 15 Minuten über denselben wiederaufnehmbaren
  Verarbeitungspfad übernehmen. Passend auf SMB ablegen und das Mailziel nach
  der bestätigten Priorität neu bestimmen; ursprüngliches Eingangsdatum und
  bereits erfolgreiche Teilschritte erhalten. Keine Doppelablage durch Neustart
  oder Mehrfachklick. Der normale Eingangslauf bleibt bei fünf Minuten.
- Die GUI zeigt Freigegeben → In Verarbeitung → Verarbeitet. Erst nach den
  erforderlichen Ablage- und Mailaktionen Verarbeitet melden. Offene weitere
  Anhänge und technische Fehler bleiben erkennbar; eine gespeicherte
  Kundenzuordnung allein ist noch kein Verarbeitungserfolg.
- Alte Erkennungsentscheidung, Regelversion, bestätigte Kategorie, Benutzer und
  Zeitpunkt nachvollziehbar speichern. Wiederkehrende Dokumentmuster anhand
  dieser Beispiele mit kontrolliert geprüften Regeln oder Lieferantenvorlagen
  besser erkennen. Eine Korrektur gilt zunächst für diesen Anhang und verändert
  keine globalen Regeln automatisch. invoice2data bleibt eine mögliche Ergänzung
  bei belegtem Nutzen; es ist derzeit nicht integriert. Kein neues ML-/LLM-System
  und kein Selbsttraining durch einen einzelnen Korrekturklick.

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
