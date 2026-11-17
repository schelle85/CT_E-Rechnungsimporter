# AP12 – begrenzte Altkeybereinigung

Die C4-Bausteine sind private Journalbibliotheken, noch ohne Host-/Timer-
oder APIaufruf. Bestehende Rootinventar-, Zertifikats-, PoP- und Graphadapter werden
weiterverwendet; keine zusätzlichen Bibliotheken oder Rechte.

`rotation_cleanup.py` plant ausschließlich nach einem vollständig bestätigten
Wechsel auf neues Material. Die Überlappung beginnt beim ersten bestätigten
Nachfolgerproof und endet nach sieben Tagen oder spätestens mit der tatsächlichen
Altgültigkeit. Der gespeicherte Termin wird bei späteren Wiederaufnahmen nicht
neu berechnet. Eine eigene alte Registrierung muss eindeutig im Rootinventar
stehen. Fehlende Eigentumsattestierung führt zu `unmanaged_retained`; fremde Keys
werden nicht entfernt. Mehrdeutige oder veränderte Herkunft wird abgelehnt.

Vor einem Entfernen verlangt die Bibliothek unverändertes aktives Nachfolgermaterial,
den passenden vollständig bestätigten Hostzustand, eine frische Nachfolgerprobe,
dieselbe App-/Instanzbindung und einen selektiven Graphbestand mit exaktem alten
Ziel und gültigem bestätigtem Nachfolger. Der spätere feste Hostaufrufer muss diese
Probe unter der normalen bestehenden Graphfreigabe selbst ausführen; Eingabewerte
aus einer API oder einem Browser reichen nicht.

Die Entfernung hat genau eine dauerhaft gespeicherte Sendefreigabe. Nach Beginn
wird ausschließlich lesend abgeglichen; weder Ablehnung, Antwortverlust noch
Prozessabbruch erlauben einen weiteren removeKey-POST. Erfolgreiches Zurücklesen
muss das Fehlen des eigenen Altkeys und den unveränderten übrigen Bestand zeigen.
Andernfalls bleibt `removal_unknown` erhalten.

Nach bestätigtem Remoteabschluss darf `finish_local` ausschließlich die vorher
gebundenen inaktiven alten PEMkopien im privaten Rootjournal entfernen. Aktuelles
Nachfolgermaterial und vollständig bestätigtes Hostjournal müssen weiterhin
übereinstimmen. Nur bekannte Auftragsdateinamen mit gleicher Materialidentität
und belegter Herkunft kommen in das dauerhaft gespeicherte Löschverzeichnis.
Unbekannte Dateinamen, aktuelles Material und nicht verwaltete Altkeys bleiben.
Eine lokale Datei allein erteilt keine Eigentums- oder Remotelöschberechtigung.

Vor jeder Entfernung wird eine öffentliche Materialattestierung atomar gesichert:
öffentlicher Zertifikatsteil, bisheriger Materialhash, Fingerprint/Gültigkeit,
eigene Key-/Auftrags-/Scopebindung und BelegSHA256. Sie ist an das dauerhafte
Cleanupverzeichnis und das unveränderte Rootinventar gebunden. So bleiben alte
Hostbelege samt unveränderter Versiegelung überprüfbar, nachdem ihre privaten
PEMs entfernt wurden. Ein fehlendes PEM ohne genau passende Attestierung wird
weiterhin abgelehnt. Die Attestierung ersetzt keinen Schlüssel für Anmeldung
oder Rückweg; diese Wege verlangen weiterhin tatsächliche gültige private Bytes.

Abbruch nach Attestierung oder nach Dateientfernung lässt `local_pending` stehen.
Wiederaufnahme verwendet dieselben Dateibindungen ohne weiteren removeKey-POST;
bereits geschriebene Attestierungen werden nicht neu erfunden. Erst alle
bestätigten lokalen Schritte führen zu `completed`. Bei nicht verwaltetem Altkey
bleiben Material und Hinweis `rotation_old_key_unmanaged` auch im Abschluss erhalten.

Neun gezielte lokale Fälle prüfen Besitz-/Nachfolgerbindungen, echte
Überlappungsgrenzen, einen einzelnen POST, Antwortverlust, Prozessverlust vor und
nach Wirkung, unbekannte/rejeziert bleibende Entfernung und erhaltene fremde Keys.
Reale lokale Dateien und Kryptografie; Graph ist synthetisch und die vorhandenen
POSIX-Rootgrenzen sind unter Windows ausdrücklich ersetzt. Kein nativer oder
produktiver Cleanupnachweis und noch keine neue Bedienfunktion.

Acht ergänzende lokale Fälle prüfen lokale Entfernung, erhaltene versiegelte
Historie, unbekannte Remotewirkung, Abbruch vor/nach unlink, fehlende oder
veränderte Attestierungen, frühere eigene Kandidaten-/Probekopien, aktuellen
Nachfolger-/Hostzustand und beibehaltenes nicht verwaltetes Material. Die feste
Hostanbindung mit tatsächlichem normalen Gate und frischer Nachfolgerprobe folgt
separat; Browser-/APIwerte können diesen Bibliotheksweg nicht auslösen.
