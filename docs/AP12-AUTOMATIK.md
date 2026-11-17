# AP12 – feste Tagesprüfung und Hostgelegenheiten

Der erste Baustein liegt als Quellstand vor: Rootjournal der Tagesprüfung,
ursprüngliche automatische Anforderung und öffentliche Faktenprojektion. Die
Hosteinträge und Veröffentlichung folgen als nächster Baustein; keine Aktivierung
oder native Abnahme aus diesen Quellen ableiten. AP08 bleibt getrennt.

## Ein Tagesplatz, ein ursprünglicher Auftrag

Der Solltermin ist03:35 Europe/Berlin. Der jeweils jüngste erreichte Termin wird
mit tatsächlicher Zeitzone berechnet; Sommer-/Winterzeit ergeben23/25 Stunden.
Mehrere verpasste Tage werden auf genau eine nachzuholende Prüfung begrenzt.
Eine dauerhaft gespeicherte Prüfungsabsicht entsteht vor der frischen Anmeldung.
Ein abgebrochener oder fehlgeschlagener Tagesversuch bleibt sichtbar und wird im
selben Tagesplatz nicht minütlich wiederholt. Außerhalb Fälligkeit erfolgt kein GET.

Die frische Credentialinstanz und der minimale Inbox-GET verwenden die bestehende
normale Graphfreigabe. Dieselbe Freigabe bleibt bis zur AP07-Proofspeicherung und
Auftragsentscheidung gehalten. Die Erfolgszeit stammt unmittelbar vom GET, nicht
vom späteren Schließen. Ein zu alter Proof wird abgelehnt. Transport hat höchstens
40 Sekunden Arbeitsfrist innerhalb des bestehenden begrenzten Workerelternpfads.

Automatische Neuanforderungen verlangen enabled, keinen aktiven Auftrag, keine
gesperrte Generation, gültiges aktuelles Material und Restlaufzeit zwischen einer
Stunde und30 Tagen. Bevor SQL erreicht wird, werden ursprüngliche UUID, Scope,
Revision und Fingerprint im Rootjournal dauerhaft gespeichert. Ein späterer Lauf
verwendet dieselbe Generation/UUID; Antwortverlust, geänderte Einstellungen oder
Neustart erlauben keinen Ersatz. Serialisierte SQLkopfprüfung entscheidet gegen
gleichzeitige manuelle Anforderungen. Eine fehlende alte Anfrage mit inzwischen
veränderter Revision bleibt ungeklärt; kein stiller neuer Auftrag.

Registrierungsablehnung, ungewisse Wirkung und fehlgeschlagene Generation erzeugen
keinen automatischen Nachfolger. Das Abschalten entfernt keinen bestehenden
Auftrag. Die tägliche echte Zertifikatsprüfung und die Erlaubnis zur automatischen
Erneuerung sind getrennt. Die Hostintegration muss Pausen/fremden Drain vor dem
Worker prüfen und automatische Aktivierung mit weniger als einer Stunde Restzeit
unterbinden; bereits begonnene Wiederherstellung bleibt gesondert zu behandeln.

## Getrennte Nachweise

Der erste tatsächlich begonnene Registerablauf speichert den Versuchszeitpunkt;
Wiederaufnahme derselben Operation verändert ihn nicht. Die bestätigte Erneuerung
stammt aus dem ursprünglichen Cleanupbeginn nach nachgewiesener Übernahme, nicht
aus einer SQLänderung, einem späteren Bootproof oder dem Bereinigungsabschluss.
Die letzte erfolgreiche Tagesprüfung bleibt zusätzlich zum letzten Tagesversuch
erhalten. Die bestehende AP07-Anmeldequittung bleibt ein separates Datum.

overview liefert nur ausgewählte öffentliche Felder. Private Pfade, PEMbytes,
Materialhashes, Containeridentitäten und Inventarinterna bleiben im Rootjournal.
Ein Bootstrap allein ist keine erfolgreiche Erneuerung. Der neue Hostpublisher
wird diese Fakten mit Quelle/Deployment/Instanz/Scope/Boot und tatsächlichen
Zeitplänen verbinden; API und Oberfläche bleiben bis dahin unbestätigt.

Lokale Prüfungen verwenden tatsächliche Dateien, Kryptografie, SQLite und Berliner
Kalenderlogik. SDK/Graph, Linuxrechte/Sperren und Hostgrenzen sind ausdrücklich
synthetisch. Native Timer-/Prozessverlust-/MariaDB-/Browsernachweise bleiben offen.
