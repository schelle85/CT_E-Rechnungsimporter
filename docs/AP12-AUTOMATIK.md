# AP12 – feste Tagesprüfung und Hostgelegenheiten

Als Quellstand liegen Rootjournal der Tagesprüfung, ursprüngliche automatische
Anforderung, feste Hosteinträge und öffentliche Faktenprojektion vor. Keine
Aktivierung oder native Abnahme aus diesen Quellen ableiten. AP08 bleibt getrennt.

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
Worker prüfen. Sie verschiebt noch nicht vorbereitete automatische Aufträge unter
einer Stunde Restzeit und führt vorbereitete Übernahmen über den vorhandenen
Rückweg. Unmittelbar vor dem tatsächlichen neuen Dateitausch wird die Stundenfrist
erneut geprüft, auch wenn die Kandidatenprobe zwischenzeitlich Zeit verbraucht hat.
Bereits aktiviertes Material wird über den bestehenden Wiederherstellungsweg
abgeglichen; die Frist erzeugt keine zweite Registrierung.

## Getrennte Nachweise

Der erste tatsächlich begonnene Registerablauf speichert den Versuchszeitpunkt;
Wiederaufnahme derselben Operation verändert ihn nicht. Die bestätigte Erneuerung
stammt aus dem ursprünglichen Cleanupbeginn nach nachgewiesener Übernahme, nicht
aus einer SQLänderung, einem späteren Bootproof oder dem Bereinigungsabschluss.
Die letzte erfolgreiche Tagesprüfung bleibt zusätzlich zum letzten Tagesversuch
erhalten. Die bestehende AP07-Anmeldequittung bleibt ein separates Datum.

overview liefert nur ausgewählte öffentliche Felder. Private Pfade, PEMbytes,
Materialhashes, Containeridentitäten und Inventarinterna bleiben im Rootjournal.
Ein Bootstrap allein ist keine erfolgreiche Erneuerung. Der Hostpublisher bindet
diese Fakten an Quelle/Deployment/Instanz/Scope/Boot und tatsächliche Zeitpläne.
Eine committed-Übernahme erscheint nur bei passender aktueller Gate-/Seal-/Boot-
Freigabe; bei normaler Freigabe muss auch die tatsächlich gelesene PEMdatei passen.

## Feste Hosteinträge

Vier deaktivierte Beispiele liegen in deploy: invoice-rotation-daily.timer/service
und invoice-rotation-opportunity.timer/service, jeweils mit Suffix.example. Die
Kalender sind03:35:00 täglich und jede Minute Sekunde40, beide Europe/Berlin,
Persistent=true,1s Genauigkeit und keine Zufallsverzögerung. Rootdienst mit fester
daily-/opportunity-Aktion, geschütztem Profil, UMask0077 und KillMode=control-group.
Die Beispiele installieren oder aktivieren sich nicht selbst.

Beide Aktionen halten den vorhandenen Graph-Writer. Fällige Tagesarbeit verwendet
anschließend Lifecycle → Processing → Notification, aktuelle APIidentität und
tatsächliche HTTPSbereitschaft. Ein vorhandener eigener Drain wird anhand seines
dauerhaften Belegs erkannt; fremder Drain und Graphpause werden erhalten. Ein
belegter blockierter Zwischenstand darf über den vorhandenen Ablauf wiederaufgenommen
werden. Minuten ohne Fälligkeit starten keine zusätzliche Tagesprobe. Eine nach
fsync noch fehlende originale SQLanforderung wird gezielt wieder abgeglichen.

Die Minutenaktion bearbeitet manuelle Aufträge auch bei enabled=false und ruft den
bestehenden run/resume-/Cleanupablauf innerhalb derselben Writersitzung auf. Eine
belegte Writerkonkurrenz verschiebt den Lauf ohne neuen Worker und ohne frischen
Statusbeleg. Außerhalb einer gehaltenen Writersitzung ist der interne direkte
Fortsetzungsweg nicht zulässig. Lange Übernahmen können die minütliche Publikation
verzögern; nach180s ist die Anzeige entsprechend unbestätigt.

Der Publisher schreibt ausschließlich rotation-status.json in den bereits RO
eingebundenen Gateordner, atomar mit Root:10001 und0440. Ein Worker liefert die
ausgewählten Rootfakten; die tatsächliche Boot-ID wird vor/nach Sammlung geprüft.
Die Tages-/Minutentimer werden nur bei geladenem aktivem Importer, geladenem und
aktivem/enabled Timer, exakt einem passenden Kalender/Zieldienst sowie passendem
Rootbefehl/Profil/UMask/KillMode/Persistenz bestätigt. Der nächste Solltermin stammt
aus systemd und muss dem nächsten tatsächlichen Berliner03:35-Termin entsprechen.

Das öffentliche AP12-Format ergänzt getrennt last_successful_daily_check_at,
check_due_at und check_overdue. Ab Solltermin+2h ohne Tagesversuch ist die Prüfung
sichtbar überfällig. Ein fehlgeschlagener Tagesversuch bleibt daneben ausdrücklich
fehlgeschlagen. Die API prüft diese Zeitbeziehungen sowie die bisherige180s-
Frischegrenze. AP08-status.json und dessen vier Jobs bleiben unverändert. Der
Reiter unterscheidet Tageserfolg, Erneuerungsversuch, Erneuerung und den zusätzlichen
AP07-Anmeldenachweis des aktuellen Zertifikats; unter24h zeigt er die Eskalationsfrist.

Lokale Prüfungen verwenden tatsächliche Dateien, Kryptografie, SQLite und Berliner
Kalenderlogik. SDK/Graph, Linuxrechte/Sperren und Hostgrenzen sind ausdrücklich
synthetisch. Native Timer-/Prozessverlust-/MariaDB-/Browsernachweise bleiben offen.
Die Testimagevorlage enthält den neuen Hostpeer und genau die vier Timer-/
Dienstbeispiele. Ein Imagebau oder eine systemd-Aktivierung wurde damit nicht ausgeführt.
