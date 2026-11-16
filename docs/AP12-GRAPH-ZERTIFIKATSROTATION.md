# AP12 – Graph-Zertifikatsrotation und Administration

Stand: 16. November 2026. Vorschlag durch den Betreiber angenommen und als
eigenes Arbeitspaket eingeplant. **Noch kein AP12-Umsetzungs-Go.** Der zusätzliche
Reiter und die Rotation sind geplant; der bereitgestellte AP07-Stand enthält
bereits Überwachung und Warnungen, aber keinen automatischen Zertifikatswechsel.

Geplant nach AP08 und vor AP11/der finalen AP09-Übergabe. Technische Grundlage ist
AP07. Vorhandene Betriebsbausteine aus AP08/AP10 nutzen, soweit vorhanden; keine
anderen AP-Freigaben aus diesem Plan ableiten.

## Zusätzlicher Reiter in der Administration

Name: **Administration → Graph-Zertifikat**. Er ergänzt Berichte,
Benachrichtigungen sowie Verbindungen/Verarbeitung und verwendet die vorhandene
Zertifikatsanzeige/-prüfung aus AP07.

- Aktives Graph-Anmeldezertifikat, öffentlicher Fingerprint und Ablauf.
- Letzter Versuch, letzte erfolgreiche Prüfung und letzte erfolgreiche Erneuerung
  getrennt anzeigen; nächster geplanter Prüflauf mit Solltermin.
- Laufender Wechsel, Ergebnis und verständlicher Fehler-/Handlungsstatus.
- Bisheriges und neues Zertifikat während der Übergangsfrist, Rückweg und
  ausstehende Bereinigung.
- Aktion „Jetzt erneuern“ über denselben begrenzten Ablauf wie die Automatik.

Bestehende AD-Gruppen gelten: GR_CEO liest; GR_Rechnung darf verwalten und den
festen Erneuerungsauftrag auslösen. Aktuelle AD-Prüfung, Origin/CSRF und
serverseitige Aktionsbindung vor Auftragszugriff verwenden. Ein Klick darf bei
Wiederholung oder Antwortverlust keinen zweiten Wechsel erzeugen.

Der Browser erhält keine privaten Schlüssel, PFX-Kennwörter oder Schlüsseldateien.
Ein PFX-Upload, ein Download privater Schlüssel und eine SMB-Abholautomatik gehören
nicht zum Standardumfang. Das vorhandene HTTPS-/Wildcardzertifikat bleibt ein
separater Betriebsweg.

## Ein gemeinsamer kontrollierter Wechsel

1. Vorhandene Konfiguration, Zertifikatsgültigkeit und ausstehende Aktionen prüfen.
   Einen dauerhaften Wechselauftrag mit Identität/Zustand und Sperre anlegen.
2. Neues Schlüsselpaar und passendes Zertifikat lokal auf Linux erzeugen.
   Laufzeit und Gültigkeit müssen die geltenden Entra-Richtlinien berücksichtigen.
3. Nur den öffentlichen Teil zusätzlich an derselben konfigurierten Entra-App
   registrieren. Vorhandene funktionierende Registrierung zunächst erhalten.
4. Mit dem neuen Zertifikat ausdrücklich einen frischen Token und einen minimalen
   Graph-GET prüfen. Ein alter Cachetoken ist kein Nachweis des neuen Zertifikats.
5. Zertifikatsdatei kontrolliert aktivieren. Laufende Aktionen berücksichtigen und
   alle betroffenen Verbraucher auf das neue Material umstellen; bei einzelnen
   Docker-Dateibindungen erforderliche gezielte Neuerstellung vorsehen.
   Anschließend die tatsächlich betriebene Laufzeit erneut prüfen.
6. Erfolgreichen Wechsel und den vorhandenen AP07-Nachfolgernachweis speichern.
   Bei Fehlern bleibt der alte funktionierende Stand verfügbar beziehungsweise
   wird über den festgelegten Rückweg wiederhergestellt.
7. Nach bestätigtem Betrieb und definierter Überlappung ausschließlich die selbst
   verwaltete alte Registrierung/Datei gezielt bereinigen. Keine fremden
   App-Zertifikate oder übrigen Zugangsdaten entfernen.

Ziel ist ein begrenzter Betreiberauftrag auf dem Host. Der API-Container bekommt
dafür keinen allgemeinen Root-/Shellzugriff, keinen Dockersocket und kein
Schreibrecht auf die private Zertifikatsablage. Schnittstelle und Berechtigungen
vor Implementierung konkret entwerfen und unabhängig prüfen.

Wechsel-ID, auslösender berechtigter Benutzer beziehungsweise Automatik,
öffentlicher Fingerprint, registrierte Schlüssel-ID und Fortschritt dauerhaft
erfassen. Die aktive Vorgangsbindung über Doppelklick, Antwortverlust, Neustart
und gleichzeitigen Zeitplanaufruf erhalten. Nach Abbruch oder verlorener Graph-Antwort zuerst den
bekannten Vorgang abgleichen; Registrierung, Aktivierung oder Entfernung nicht
blind wiederholen. Parallele manuelle und automatische Wechsel verhindern.

## Automatik und Wiederherstellung

Vorgesehene Standardwerte: tägliche Prüfung, Beginn der Erneuerung 30 Tage vor
Ablauf, sieben Tage Überlappung bei ausreichender Restgültigkeit. Zeitsteuerung
und gültige Einstellgrenzen werden im AP12-Entwurf festgelegt und geprüft.
Fehlgeschlagene Erneuerung sowie ausgebliebene Prüfläufe müssen sichtbar sein.
Ein abgelaufenes Altzertifikat bietet keinen Rückweg; sieben Tage sind ein Zielwert
innerhalb der tatsächlichen Gültigkeit. Notfall-/Eskalationsfrist im Entwurf
festlegen. Ein Ausfall der gesamten VM oder Datenbank kann nicht zuverlässig durch
dieselbe Anwendung alarmiert werden; dafür ist eine unabhängige Betriebsüberwachung
erforderlich, ohne sie aus diesem AP als bereits vorhanden abzuleiten.

Die AP07-Pflichtwarnung ab zehn Tagen und die roten Hinweise ab einem Resttag,
bei null und danach bleiben erhalten. Eine Warnserie wird weiterhin erst nach
dem bestätigten gültigen Nachfolger beendet.

Für die Selbstrotation verlangt Microsoft einen Besitznachweis mit einem
bestehenden gültigen Zertifikat; für das Rollen eigener Schlüssel dokumentiert
Microsoft keine zusätzliche spezielle Appberechtigung. Diesen Weg im Zielmandanten
gezielt prüfen, ohne pauschale tenantweite App-Verwaltungsrechte vorauszusetzen.
Sind alle Zertifikate abgelaufen, ist ein dokumentierter administrativer
Wiederherstellungsweg erforderlich. Warnmails über dieselbe ausgefallene
Graph-Anmeldung bieten dann keine Zustellgarantie.

Vorhandene Python-/Zertifikats- und Graph-Bausteine nutzen. Keine zusätzliche
gekaufte Zertifikatsverwaltung voraussetzen.

## Prüfung und Unterlagen

AP12 umfasst den Entwurf, das manuell geprüfte Betreiberskript, den Adminreiter,
die gezielte Aktivierung der Automatik und deren Abnahme. Gezielt prüfen:
Rollen/CSRF, Wiederholung/Konkurrenz, neue Anmeldung und tatsächliche Übernahme,
unterbrochene/unklare Schritte, Rückweg, Bereinigung, abgelaufene Ausgangslage
und fehlender Prüflauf. Kundendaten durch synthetische, isolierte Fälle ersetzen,
soweit möglich; tatsächliche Entra-Änderungen erst auf geprüftem konkretem Ablauf.

AP11 beschreibt den ausgelieferten Reiter und die erlaubten Bedienwege.
AP09 ergänzt technische Durchführung, Rückweg und administrative Wiederherstellung.
Keine Geheimnisse oder privaten Betriebswerte in die öffentlichen Unterlagen.

Primärquellen:
[Microsoft addKey](https://learn.microsoft.com/en-us/graph/api/application-addkey?view=graph-rest-1.0),
[Microsoft removeKey](https://learn.microsoft.com/en-us/graph/api/application-removekey?view=graph-rest-1.0),
[Graph PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.applications/add-mgapplicationkey?view=graph-powershell-1.0).
