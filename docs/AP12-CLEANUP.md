# AP12 – begrenzte Altkeybereinigung

Der erste C4-Baustein ist eine private Journalbibliothek, noch ohne Host-/Timer-
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
Andernfalls bleibt `removal_unknown` erhalten. Alte private Dateien werden durch
diese Bibliothek noch nicht gelöscht; bestätigter Remotezustand, nachvollziehbare
Materialbelege und eng begrenzte lokale Bereinigung werden separat verbunden.

Neun gezielte lokale Fälle prüfen Besitz-/Nachfolgerbindungen, echte
Überlappungsgrenzen, einen einzelnen POST, Antwortverlust, Prozessverlust vor und
nach Wirkung, unbekannte/rejeziert bleibende Entfernung und erhaltene fremde Keys.
Reale lokale Dateien und Kryptografie; Graph ist synthetisch und die vorhandenen
POSIX-Rootgrenzen sind unter Windows ausdrücklich ersetzt. Kein nativer oder
produktiver Cleanupnachweis und noch keine neue Bedienfunktion.
