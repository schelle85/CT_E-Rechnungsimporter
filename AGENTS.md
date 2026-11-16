# Arbeitsregeln

## Rollen und Start

- ORGA koordiniert Anforderungen, Pakete, Übergaben, Git-Stand und Abnahme.
- Anwendungsentwicklung und technische Implementierung führt DEV aus.
- REVIEW prüft feste Lieferstände und übernimmt ungelöste Fehler nach Eskalation.
- ORGA implementiert keinen Anwendungscode als Ersatz für DEV.
- Jedes AP benötigt die ausdrückliche Freigabe des Betreibers. AP00 ist seit
  08.11.2026 freigegeben; Graph-Grundanbindung ist der erste Einrichtungsschritt.
  Innerhalb eines freigegebenen AP koordiniert ORGA DEV/REVIEW bis zum Abschluss
  oder zu einer konkreten Frage/Blockade. AP01 ist seit 12.11.2026 vollständig
  durch den Kunden abgenommen. AP02a–c ist technisch abgeschlossen.
  AP03 ist eingefroren. AP04 ist technisch im isolierten Grundlagenumfang
  abgeschlossen. AP05a–c ist seit 13.11.2026 im definierten manuellen Umfang
  technisch abgeschlossen: Quellen-/Runtimeprüfung, synthetische echte CIFS-Probe,
  Kundenschema005, sechs Inboxziele und manueller 0eligible-Tick belegt. Zum
  AP05-Abschluss blieben API/GUI unverändert; keine Verarbeitung alter Mails oder Timeraktivierung.
  AP06a–d einschließlich PDF-Vorschau ist seit14.11.2026 freigegeben, technisch
  abgeschlossen und bereitgestellt: native006-/HTTP-/Konkurrenznachweise und fünf
  isolierte Browsergruppen einschließlich tatsächlicher PDF-Sichtprüfung bestanden.
  Kundenmigration auf006 und getrenntes Rücklesen von Instanz/Konfiguration,
  API/Web/DB, HTTPS-Journalmodus, Zugriffsschutz und leerem Journal bestätigt.
  Keine neue tatsächliche AP06-Kundenanmeldung behaupten.
  Vor Kundenmigration/Deployment fester Quellreview und konkreter ORGA-Abgleich.
  AP07a–c ist seit 15.11.2026 technisch abgeschlossen und bereitgestellt aus
  Codepin `5ecfd59270b63947d3f92af98a1b9f8e5a267aeb`, Kundenschema 007.
  API/Web stammen aus derselben festen Quelle; Instanz, LDAP-Konfiguration und
  DBdienst sind erhalten und getrennt zurückgelesen. Eigener Notificationkey,
  minimale manuelle CLI und drei privat initialisierte Empfänger eingerichtet.
  A/B vollständig, C-Quellenreview, 21 C-Fälle auf MariaDB und acht isolierte HTTPS-
  Browsergruppen bestanden, einschließlich 80,006 s-Fristfall und Antwortverlust/
  neuer Sitzung/Konfigversion ohne Doppel-POST. Synthetischer CLIplan geprüft.
  Berichte, Einstellungen/Vorschau/Test/Historie und exakte Zertifikatshinweise
  für beide Rollen geliefert. Echte Graphanmeldung und genau eine feste Testmail
  mit HTTP 202/Reservierung 1/getrenntem Status bestätigt; Empfang ausschließlich im
  eigenen Abnahmepostfach nachgewiesen. Keine neue tatsächliche Kundenanmeldung
  nach AP07 behaupten; AP01-AD-Abnahme bleibt historisch. Bestehende Fehlerzähler erhalten.
  Zum AP07-Abschluss blieb die Automatik inaktiv; gespeicherte Zeiten allein
  aktivieren keine Jobs. AP08 ist seit16.11.2026 zur Umsetzung freigegeben;
  A liefert Laufzeitbasis, B Start/Timer/HTTPSübernahme, C frischen gebundenen
  Betriebsstatus für API/GUI. C ist aus 413095f823702d39b02bc8b3c989b526fdf808d0
  bereitgestellt; Base-Apply erhält Schema 007/Instanz/Konfiguration und DBzustand.
  C-GUI samt getrenntem Readback bestanden, tatsächliche HTTPSübernahme und
  folgender No-op bestätigt; aktueller Peer gültig bis 12.02.2027.
  Notificationvorlauf/Nullvorschauen geprüft, ursprünglicher Testslot accepted/1/202
  erhalten, keine zusätzliche Testmail. Startdienst und fünf Timer seit 16.11.2026
  19:44:23 Europe/Berlin enabled/active; frischer Status active, Publikation minütlich.
  Erste Korrekturen um 19:45 und Inbox um 19:50 nach vorherigem Sperrdeferred erfolgreich,
  je 0 Quanten / 0 remaining. Tages-/Wochenbericht um 19:45/19:46 je einmal mit 202 angenommen;
  keine Zustellbestätigung daraus, Testslot erhalten, keine offenen Postwirkungen.
  Preboot-Gate um 19:50:28 und kontrollierter Reboot erfolgt: neue Boot-ID, gleiche
  Container-IDs/Images, gesundes HTTPS, beide CIFSmounts und DB-/Konfigurations-
  bindungen erhalten. Erster geplanter TLS-Stundenlauf um 20:00 changed=false,
  status_recorded=true. Anwendung/Images bleiben auf 413095f. Nach dem Reboot ist
  seit 16.11.2026, 20:15:08 Europe/Berlin der separate Status-Timerphasenversatz wirksam:
  genau ein Kalender jede Minute Sekunde 20, Timer active/enabled, Ziel
  invoice-status.service. Drei aufeinanderfolgende automatische Kontrollzyklen
  am 16.11.2026 um 20:16:21, 20:17:21 und 20:18:21 Europe/Berlin bestätigen active,
  abgeschlossene Notificationläufe und erhaltene Boot-/Quellbindungen; kein
  manueller Collector. AP08 ist im vereinbarten Umfang technisch abgeschlossen.
  Der Phasenversatz wurde nach dem belegten Reboot gesetzt; kein zweiter Reboot
  oder vollständiger VMrestore ist damit nachgewiesen.
  Führender Vertrag: docs/AP08-BETRIEB.md. AP09/10/11 bleiben ohne Go;
  AP11-Planung erhalten.
  AP12 ist seit16.11.2026 für Graph-Zertifikatsrotation und Administration →
  Graph-Zertifikat geplant, ohne Umsetzungs-Go. Führender Umfang:
  docs/AP12-GRAPH-ZERTIFIKATSROTATION.md. Keine Implementierung aus der Planannahme ableiten.
  DMS-Anbindung, -Konfiguration und -Prüfung liegen außerhalb unseres Auftrags
  und sind keine Abnahmebedingung. AP03 und Stichtag bleiben unverändert.
- Keine zusätzlichen Agenten oder Chats ohne entsprechenden Auftrag.

## Auftrag und vorhandene Lösungen

Vor einem Unterpaket [Anforderungen](docs/ANFORDERUNGEN.md),
[Arbeitsplan](docs/ARBEITSPLAN.md) und [KI-Dokumentation](docs/KI-DOKUMENTATION.md)
lesen. Bestehende geeignete Produkte/Bibliotheken zuerst prüfen. Eigenentwicklung
auf den vereinbarten Ablauf und belegte Lücken begrenzen.

## Fehlerbehebung

DEV hat pro Fehler höchstens fünf gezielte Korrekturversuche. Ein Versuch besteht
aus begründeter Korrektur und passender Nachprüfung. Ursache, Änderung und Ergebnis
festhalten. Ein Modellwechsel oder Umbenennen des Fehlers setzt den Zähler nicht zurück.
Nach fünf erfolglosen Versuchen keine sechste DEV-Korrekturschleife starten:
feste Basis, Reproduktion, erwartetes/tatsächliches Ergebnis und die fünf Versuche
an ORGA für REVIEW übergeben. ORGA verteilt den nachfolgenden Auftrag.

## Git und Ergebnisnachweise

Nach jedem abgeschlossenen Unterpaket oder eigenständigen Korrekturschritt einen
nachvollziehbaren Commit erstellen und auf GitHub hochladen. Nur einen lokalen
Commit als hochgeladen melden, wenn der entfernte Stand nachgewiesen wurde.
Prüfergebnisse und noch offene Fehler wahrheitsgemäß angeben. Nicht bestandene
Zwischenstände als solche auf einem Arbeitszweig halten; kein Force-Push.
REVIEW bekommt stets einen festen Commit und einen abgegrenzten Auftrag.

Vor Commit/Push die tatsächliche Dateiliste und Änderungen prüfen. Nur zu diesem
Auftrag gehörende Dateien aufnehmen. Interne Wartungsunterlagen werden nicht
pauschal in das Produktrepository kopiert.

## Öffentliches Repository

Keine Kennwörter, Token, privaten Schlüssel, Zertifikatspakete, echten Rechnungen,
Mailinhalte, internen Verbindungsdaten oder personenbezogenen Empfängerlisten
einchecken. Verbindungsbeispiele mit Platzhaltern; synthetische Testdaten verwenden.
`.gitignore` ergänzt die Prüfung und ersetzt sie nicht.

## Dokumentation und Abschluss

Dokumentation je Schritt fortschreiben. Kundentexte enthalten nur tatsächlich
verfügbare und geprüfte Bedienwege; geplante Funktionen klar als geplant benennen.
Abschlusslieferungen gemäß [Dokumentationsplan](docs/DOKUMENTATIONSPLAN.md).
PDFs vor Auslieferung rendern und visuell prüfen. KI-Dokumentation bleibt Markdown.
Keine TANSS-Zeiten ohne die konkrete Vorgabe des betreuenden Technikers erfassen.
