# AP09: Dokumentübergabe

Stand: 17. November 2026. Die einmalige unabhängige Abschlussprüfung des festen
Dokumentpakets `330c749` ist mit PASS ohne notwendige Korrekturbefunde abgeschlossen.
Produktlaufzeit unverändert `d9f32a5a9c9fb642f59a13ed2550f74532fc3ebe`,
Schema `008`. Dokumentversion AP09 bezeichnet keine neue Programmversion.

## Lieferumfang

| Teil | Quelle / Ausgabe und Status |
| --- | --- |
| AP09a | Offen: Vollständiges AP11-Nutzerhandbuch fehlt; AP11 ist nicht freigegeben. Die technische Unterlage ersetzt es nicht. |
| AP09b | [Technische Quelle](TECHNISCHE-DOKUMENTATION.md) und [PDF](handbuecher/Technische-Dokumentation.pdf): Architektur, datierte Versionen, Lizenzorientierung, Konfiguration, Datenfluss, Betrieb, Rotation, Sicherung/Restore und Grenzen. |
| AP09c | [KI-Dokumentation](KI-DOKUMENTATION.md) als aktueller Wiedereinstieg; historische Einzelstände in Originalverträgen und Git erhalten. |
| AP09d | Vollständige Eigenprüfung und genau eine unabhängige Abschlussprüfung bestanden. Öffentliche Dateien im Repository; Veröffentlichung und separate vertrauliche Dateiübergabe durch ORGA. AP09a bleibt offen. |
| Vertraulicher Betrieb | Betriebsblatt separat übergeben; keine privaten Anschlussdaten, Dienst-/Instanzkennungen, Empfänger oder Geheimnisse in diesem Repository. |

## Abgleich und Nachweisgrenzen

Technikquelle wurde gegen die vorhandenen Paketverträge, Deployvorlagen, Locks und
die aktuelle datierte lesende Softwareaufnahme abgeglichen. Die PDF wird mit
dem vorhandenen ReportLab, eingebetteten umlautfähigen Vera-Schriften,
Inhaltsverzeichnis, Lesezeichen, Tabellen und Seitenzahlen erzeugt. [Buildhinweise](handbuecher/README.md)
beschreiben die Reproduktion. Fester Commit, SHA256werte, Werkzeugversionen,
Text-/Link-/Datenschutzabgleich und vollständige gerenderte Seitensicht werden
im getrennten Prüfbericht dokumentiert. Die unabhängige Abschlussprüfung hat
Faktenkonsistenz, Datentrennung, Verweise und PDF-Stichprobe bestätigt. Nachträgliche
Statusfortschreibung ändert weder geprüfte Technikquelle/PDF noch das Betriebsblatt.

Die führende [AP12-Übergabe](AP12-UEBERGABE.md) bleibt unverändert maßgeblich.
Erster echter Wechselversuch mit kontrolliertem Altmaterialrückweg und ungeklärter
Ursache, erfolgreiche zweite Rotation mit demselben abgeglichenen Auftrag,
genau ein AP12-Kundenboot und qualifizierte isolierte Wiederaufnahme werden nicht
zu einer pauschal bestandenen Fehlerfallserie zusammengezogen. Der ursprüngliche
fehlgeschlagene Restorehelper-Aufruf und der native Browser-Ursprungslauf false
bleiben ausdrücklich erhalten. Späterer Erfolg erklärt keine frühere Ursache.

Offen bleiben produktive Altkeybereinigung, zukünftiger automatischer
Erneuerungsauslöser, vollständiger VM-/Offsite-Restore, fachliche Erkennungsrestfälle
und eine neue tatsächliche Kundenanmeldung nach späteren Deployments. AP10wartung
und Berichtsmailgestaltung bleiben geplant. AP03, Importstichtag und DMSausschluss
sind unverändert. Keine App-, Image-, Schema- oder Serveränderung aus AP09 ableiten.

## Abschlussfolge

1. Vollständigen festen Markdown-/PDF-Stand einschließlich separat vertraulichem
   Betriebsblatt eigenprüfen und Root zur gemeinsamen Sichtung übergeben.
2. Einmalige unabhängige Prüfung am vollständigen festen Paket; Ergebnis und
   gegebenenfalls konkret notwendige Korrekturen nachvollziehbar dokumentieren.
3. Veröffentlichung und Kundenübergabe nach dem entsprechenden Auftrag durchführen.
   AP09a bis zur freigegebenen AP11-Lieferung als offen erhalten.
