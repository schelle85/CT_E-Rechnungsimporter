# AP12 – vorbereiteter Browserprüfumfang

Der private Prüfstand setzt den vorhandenen AP08-Playwright-Harness fort.
Unveränderte Produktdateien werden aus einem festen Webimage über dessen Nginx
und isoliertes HTTPS geladen. Node-/Playwright-/Chromiumgrundlage, Prüfung der
Image-/Quell-/Export-/Assetbytes, TLS-Schlüsselbindung, begrenzte Laufzeit und
gezielte eigene Ressourcenbereinigung bleiben erhalten. Keine neue Testplattform.

Alle APIantworten einschließlich Sitzung, Login und Rollen sind ausdrücklich
private Browser-Routenfixtures. Sie sind weder Bestandteil des Produkts noch
ein neuer Backendendpunkt. Es gibt keinen Produktionsschalter zur Umgehung der
Authentifizierung. Die separat geprüften tatsächlichen ASGI-/Sitzungs-/ADrollen-/
Origin-/CSRFpfade bleiben der Sicherheitsnachweis. Sichtbare ADkennzeichnungen im
Produkt werden im Browserfall durch Fixtureantworten gespeist und sind dort
kein Nachweis einer tatsächlichen ADanmeldung.

| Gruppe | Geprüfte Browserwirkung |
| --- | --- |
| Adminstatus/Einstellung | Getrennte Zeitangaben; Automatikeinstellung erzeugt keinen Erneuerungsauftrag |
| Leser/Überlappung/Mobil | Keine Schreibbedienung; Alt/Neu und unverwalteter Bestand;390×844 ohne Seitenüberlauf, Fingerprints umbrechen |
| Verlorene Annahmeantwort | Genau ein gespeicherter ursprünglicher Auftrag; gleicher Browserbestand nach Ab-/Anmeldung und Neuladen |
| Noch fehlende Annahme | Leere GETquittung bleibt unterscheidbar; erneutes Übermitteln ausschließlich derselben vollständigen Absicht |
| Widersprüchliche Quittung | Fehlender oder fremder Beleg löscht/ersetzt die ursprüngliche Absicht nicht |
| Zwei Fenster | Tatsächliche Web-Lock-Konkurrenz und gemeinsamer localStorage; kein zweiter neuer Auftrag |
| Veralteter Timerstatus | Unbestätigter Hoststatus und absichtlich181s alte Projektion erzeugen keine aktive Timerbehauptung |

Vor jedem simulierten Erneuerungs-POST liest der Harness die bereits dauerhaft
gespeicherte Absicht aus dem tatsächlichen Browser und vergleicht sämtliche
Payloadfelder. Nur fest erklärte Login-/Logout-/Konfigurations-/Auftragsrouten
dürfen Schreibantworten simulieren. Unerwartete Methoden, Routen oder fremde
Ursprünge führen zum Fehlschlag. Keine APIanforderung darf den separaten
503-Prüfupstream erreichen; dessen Log muss leer bleiben.

Erwarteter Antwortverlust ist an den konkreten Request und Fehler gebunden.
Aufräumfehler, unerwartete Browser-/Konsolen-/Netzfehler und abweichende Assets
lassen den Gesamtfall scheitern. Screenshots und Ereignisse werden privat
gespeichert und separat zurückgelesen. Mobile Screenshots benötigen zusätzlich
Sichtprüfung; ein Layoutmaß allein bestätigt nicht die visuelle Darstellung.

Vorbereitet sind diese Browserabläufe sowie lokale Fixture-/Antwortvertragsprüfungen.
Die Browserfälle sind durch ihre Vorbereitung noch nicht ausgeführt oder bestanden.
ORGA bindet vor Ausführung den tatsächlichen gebauten Webimage-Identifier und
die geprüften Export-/Hostpfade an den festen Quellstand. Die ungebundene Vorlage
ist nicht ausführbar. Der abschließende Nachweis benötigt echten Chromiumlauf,
HTTPS-/Assetbelege, private Screenshots und getrennten Ergebnis-/Ressourcenreadback.
VM-/Browsercontaineraktionen bleiben beim betreuenden Betreiber.
