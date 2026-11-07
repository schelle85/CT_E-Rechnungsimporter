# Arbeitsregeln

## Rollen und Start

- ORGA koordiniert Anforderungen, Pakete, Übergaben, Git-Stand und Abnahme.
- Anwendungsentwicklung und technische Implementierung führt DEV aus.
- REVIEW prüft feste Lieferstände und übernimmt ungelöste Fehler nach Eskalation.
- ORGA implementiert keinen Anwendungscode als Ersatz für DEV.
- Dieser Stand bereitet nur das Repository vor. Der Entwicklungsstart hängt von
  der bestätigten Bereitstellung der VM einschließlich SMB ab.
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
