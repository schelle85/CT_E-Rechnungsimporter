# AP12 – begrenzte Altkeybereinigung

Die C4-Bausteine verbinden das private Journal mit dem festen Rootworker und
Hostcontroller. Timer-/APIeinrichtung und native Abnahme bleiben getrennte Arbeit.
Bestehende Rootinventar-, Zertifikats-, PoP- und Graphadapter werden weiterverwendet;
keine zusätzlichen Bibliotheken oder Rechte. Noch keine Bereitstellung im Betrieb.

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
Ziel und gültigem bestätigtem Nachfolger. Der feste Rootaufrufer führt diese
Probe unter der normalen bestehenden Graphfreigabe selbst aus; Eingabewerte
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
Nachfolger-/Hostzustand und beibehaltenes nicht verwaltetes Material.

## Fester Hostablauf

Die Veröffentlichung einer bestätigten neuen Übernahme schreibt zuerst den
dauerhaften Cleanupplan und projiziert ihn anschließend nach SQL. Ein späterer
run/resume auf derselben bestätigten Übernahme prüft die gespeicherte Fälligkeit.
Graphpause oder fremder Drain verhindern neue Bereinigungsarbeit. Der Controller
hält die bestehende Writersperre, dann Lifecycle/Processing/Notification in ihrer
bisherigen Reihenfolge, und bestätigt APIbindungen und normale HTTPSbereitschaft.
Die API wird für diesen Schritt nicht gestoppt oder neu erstellt.

Der feste Rootworkeraufruf cleanup nimmt ausschließlich die ursprüngliche
operation_id an. Er prüft Gate-/Seal-/Material-/Quell-/Instanzbindung und erwirbt
die normale geteilte Graphfreigabe. Er erzeugt selbst eine frische Credentialinstanz
und führt den minimalen Inbox-GET aus. Dessen Zeitpunkt wird unmittelbar nach
dem GET festgehalten; ein langes Credential-Schließen erneuert ihn nicht.
Das gemeinsame absolute Arbeitsbudget beträgt höchstens40s innerhalb der
vorhandenen begrenzten Workerelternfrist. Für den eigenen Appbestand und removeKey
wird dieselbe Freigabe vor Credential-/HTTParbeit erneut geprüft. Der Nachfolger
signiert weiterhin den ursprünglichen PoP; es gibt weder PATCH noch Zusatzrechte.

Der Rootzustand wird nach cleanup_started, cleanup_unknown oder completed
projiziert. Ein unbekannter POST bleibt lesend abzugleichen. Erst der dauerhafte
lokale Abschluss gibt den ursprünglichen SQLauftrag frei. Verlorene Antworten
lassen sich aus dem Rootjournal nachprojizieren; weder neue UUID noch neuer POST.
Ein fremder/unverwalteter Altkey bleibt erhalten und der Abschluss enthält seinen
neutralen Hinweis. Explizite Eigentumsattestierung bleibt eine Rootentscheidung.
Der feste [Zuordnungsweg](AP12-OWNERSHIP.md) verlangt einen privaten Betreibernachweis,
aktuell bestätigtes Material und einen eigenen Bestandsabgleich vor einem neuen
Rotationsauftrag. Ein bereits laufender Cleanup übernimmt keine nachträgliche Zuordnung.

Auch nach abgeschlossenem Cleanup und leerem active_operation kann ein neuer
Boot genau die ursprüngliche Gate-/SQL-/Journalbindung wieder aufnehmen. Ein
completed/new-Auftrag verlangt zusätzlich seinen bestätigten Cleanupabschluss
und das tatsächliche Nachfolgermaterial. Wiederholte Verbraucher-/Proofbestätigung
erhält Requesthash und Cleanupzeitplan und veröffentlicht wieder completed.
Der vorhandene failed/old-Rückweg bleibt gesondert geprüft. Kein gelöschtes altes
PEM wird rekonstruiert oder für einen vermeintlichen Rückweg ersetzt.

Elf neue gezielte lokale Fälle belegen Fälligkeit, frische Anmeldung, Pausen,
unbekannte Entfernung, verlorenen Abschluss, geschlossenen Bootpfad, veränderte
Bindung und Transportfreigabe; vier direkt betroffene bestehende Verträge bleiben
grün. Zeit-/Graph-/Hostgrenzen sind weiterhin ausdrücklich synthetisch. Reale
Linux-/Cgroup-/MariaDB-/Boot-/Entfernungsbelege müssen separat hinzukommen.
