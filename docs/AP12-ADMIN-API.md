# AP12 – geschützte API für Zertifikatsaufträge

Der erste Adminbaustein liefert feste APIwege im Quellstand. Der sichtbare Reiter,
der Root-Statuspublisher, Hosttimer und deren native Bereitstellung folgen. Die
API hat weiterhin keinen Dockersocket, keine Rootfunktion und keine schreibbare
Schlüsselablage. Bestehende AD-/Sitzungs-/Origin-/CSRFprüfungen werden verwendet.

| Weg | Zweck |
| --- | --- |
| GET /api/rotation/status | Lokales Zertifikat, SQLauftrag, Einstellungen und bestätigte öffentliche Hostprojektion |
| GET /api/rotation/history | Begrenzte Historie der aktuell gebundenen App/Instanz,20 Einträge je Seite |
| GET /api/rotation/request | Ursprüngliche manuelle Anforderung mit vollständiger Actor-/Scope-/UUID-/Revisions-/Alt-Fingerprintbindung abgleichen |
| POST /api/rotation/request | Genau einen dauerhaften manuellen SQLauftrag anlegen oder dessen ursprüngliche Quittung zurückgeben |
| PUT /api/rotation/config | Automatische Erneuerung versionsgebunden ein-/ausschalten; keine frei wählbaren Pfade oder Termine |

GR_CEO und GR_Rechnung dürfen lesen. Schreiben verlangt die aktuelle
Verwaltungsrolle, Origin und CSRF vor jedem Auftragszugriff, auch bei Wiederholung.
Der Actor stammt aus der aktuell geprüften ADidentität; der Browser kann ihn nicht
setzen. Der Statusabgleich einer manuellen Anforderung verlangt denselben Actor.
Die gemeinsame Historie ist für beide erlaubten Rollen lesbar.

Vor einem neuen Auftrag werden aktueller öffentlicher Fingerprint und tatsächliche
Zertifikatsgültigkeit innerhalb der serialisierten Anforderung geprüft. Ein
bereits vorhandener identischer Auftrag wird davor zurückgegeben: neue PEMdatei,
Konfigurationsrevision oder Sitzung erzeugen keinen Ersatzauftrag. Veränderte
Payload, App/Instanz/Scope, falsche aktuelle Zertifikatsidentität und konkurrierende
andere Aufträge werden abgewiesen. Eine unbekannte Antwort wird über die
ursprüngliche Bindung gelesen; kein neues UUID als Ersatz.

Ein POST startet keinen Graphzugriff und keine Hostaktion innerhalb der API.
Der bestehende Rootablauf übernimmt den gespeicherten Auftrag später. Der
Einstellwert enabled allein bestätigt noch keinen installierten oder aktiven Timer.
Die fest vereinbarten Sollwerte03:35 Europe/Berlin,30 Tage Vorlauf und höchstens
sieben Tage Überlappung werden getrennt von tatsächlichen Laufnachweisen geliefert.

## Öffentliche Betriebsprojektion

rotation_status.py liest ausschließlich rotation-status.json im bereits RO
eingebundenen Gateordner. Die API sieht kein Rootjournal. Das feste Format enthält
nur gebundene öffentliche Metadaten: Quelle/Deployment/Instanz/Scope/Boot,
Beobachtungszeit, letzte Prüfung, letzter Versuch, letzte erfolgreiche Erneuerung,
alte/neue öffentliche Zertifikatsmetadaten und bestätigte Timerwerte.

Datei und vollständiges Schema müssen gültig sein, Bindung/Boot passen und die
Beobachtung darf höchstens180 Sekunden alt sein. Fehlende, zusätzliche, veränderte
oder veraltete Daten werden als unbestätigt angezeigt. Es wird kein erfolgreicher
Lauf aus einem gesetzten Zeitplan, SQLauftragsdatum oder bloßer Dateigültigkeit
erfunden. Die letzte erfolgreiche Graphprüfung kommt zusätzlich aus dem passenden
AP07-Proof und wird nur für aktuellen Fingerprint/Scope mit nicht zukünftigem
Zeitpunkt angezeigt. Auftrag, Prüfung und Erneuerung bleiben getrennte Fakten.

Der Publisher und die beiden Hosttimer werden im nächsten Paket verbunden. Bis
dahin ist der Hoststatus regulär unbestätigt. Das AP08-Statusformat und seine vier
Jobs bleiben unverändert.

## Lokale Nachweise

Zehn gezielte Fälle bestehen mit tatsächlichem ASGI-/Sitzungs-/AD-Rollen-/CSRF-
Code, SQLite, Migrationen und Kryptografie. Verzeichnisdienst und geschützte
Hostdateizugriffe sind ausdrücklich synthetisch. Bestätigt sind Rollenentzug,
Origin/CSRF vor Replay, gleiche Anfrage nach neuem Zertifikat/Kopfrevision/Sitzung,
zwei konkurrierende HTTPanforderungen, gebundene Quittung, strikte Eingaben,
abgelaufenes/falsches Zertifikat und fehlende/veränderte/veraltete Projektion.
Credential- und Rootworkeraufrufe sind als verbotene Testgrenzen abgesichert.
Kein tatsächlicher Browser-, AD-, MariaDB-, Hosttimer- oder Kundenlauf daraus.
