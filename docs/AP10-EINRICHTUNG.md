# AP10: Einrichtungs-, Rückweg- und Abnahmeplan

Stand: 18.11.2026. Vor Quellenreview und frischem Instanzabgleich **nicht ausführen**.
Dies ist der konkret vorgesehene Betreiberablauf, keine erfolgte Installation.
Der tatsächliche aktuelle Host-/APTbestand ist bei dieser lokalen DEV-Lieferung
noch nicht frisch bestätigt. VPN/SSH war bei ORGAs erster Aufnahme nicht erreichbar.
Beispiele enthalten ausschließlich generische Linuxpfade.

## 1. Feste Quellen und Voraussetzungen

Festen AP10-Liefercommit und SHA256manifest aus dem DEV-Prüfbericht verwenden.
API/Web/Worker bleiben auf d9/008. Neue Wartungsdateien, explizite Ordnungs-Drop-ins
und genau ein Hostpatch an `host-runtime.py` installieren. Dieser ergänzt den
markerbewahrenden Dienststopp; der ausdrückliche Betreiber-Drain behält seine
neue Marker-Epoche. Alle anderen Peers bleiben unverändert. Kein Gitpull, Imagebuild/pull, Schema-
oder Bootstrapwechsel. Das Backupverfahren HornetVMbackup täglich einschließlich
Offsite bleibt unverändert. Letzten erfolgreichen Sicherungslauf privat bestätigen;
dadurch keinen tatsächlich geprüften Vollrestore behaupten.

Root liest vorab, ohne Konfiguration zu ändern:

```sh
date -Is
cat /proc/sys/kernel/random/boot_id
systemctl is-active invoice-importer.service docker.service
systemctl list-timers --all --no-pager
systemctl cat invoice-importer.service invoice-processing@.service invoice-notifications.service invoice-tls.service invoice-status.service invoice-rotation-daily.service invoice-rotation-opportunity.service
systemctl cat apt-daily.timer apt-daily.service apt-daily-upgrade.timer apt-daily-upgrade.service unattended-upgrades.service
dpkg --audit
apt-mark showhold
apt-get --version
systemd-analyze --version
```

Zusätzlich privat: OS/Kernel/Host-Machine-ID, Paketliste, APTquellen/Preferences/
Hooks/Periodic-/Unattended-Rebootregeln, aktive APT/dpkg-/unattended-Prozesse und
Locks, `/run/reboot-required`, tatsächliche Boot-/Image-/Instanz-/Schema-/Mount-
und HTTPSnachweise, sieben Timerspezifikationen, Gate/aktueller Rotationsbeleg und
Rootjobs. Keine Secrets oder vollständige APTauth-/LDAP-/Graphdateien ausgeben.
Auf diesem Host muss Nginx tatsächlich SIGQUIT als StopSignal verwenden.

Ein aktiver/unklarer Paketjob wird **nicht** beendet. Einrichtung verschieben,
bis er regulär endet und sein Ergebnis abgeglichen ist. Zusätzliche Paket- oder
Rebootzeitpläne, nicht freigegebene Paketquellen, abweichende Docker-/Cgroup-/
Imagebindung oder offene Rotation zuerst gezielt behandeln und den Plan neu prüfen.
Normale bestätigte Überlappung und historische terminale Fehler nicht als laufende
Rotation missdeuten. Vorhandene Benutzeraktionen bleiben erhalten.

## 2. Lokal/nativ prüfen, bevor Dateien installiert werden

Auf einem passenden isolierten Linux-Prüfstand oder in einem von ORGA ausdrücklich
freigegebenen temporären Quellenverzeichnis ohne echte Profile:

```sh
python3 -I -B deploy/test_maintenance.py
sudo python3 -I -B deploy/test_maintenance_native.py
systemd-analyze calendar --iterations=4 'Sun *-*-* 03:00:00 Europe/Berlin'
systemd-analyze calendar --base-time='2027-03-27 12:00:00 Europe/Berlin' 'Sun *-*-* 03:00:00 Europe/Berlin'
systemd-analyze calendar --base-time='2027-10-30 12:00:00 Europe/Berlin' 'Sun *-*-* 03:00:00 Europe/Berlin'
```

Die vier Unitvorlagen im Prüfverzeichnis ohne `.example` ablegen und mit
`systemd-analyze verify` prüfen; bestehende Referenzen auf Docker-/Importerunits
müssen im isolierten Prüfpfad auflösbar sein. Geplante Drop-ins zusammen mit den
tatsächlichen vorhandenen Units prüfen, nicht nur Textmuster vergleichen.
Kein `systemctl start` des Paketservices als Syntaxprüfung.

Lokaler DEVrechner ist Windows ohne installiertes WSL. 22 gezielte Tests einschließlich
echter ZoneInfo-Kalenderberechnung und synthetischer Marker-/Startkonkurrenz sind
bestanden. Vier ausführbare native Tests prüfen unter Linux/root ausschließlich
temporäre eigene Dateien in /run: echte Prozess-flock-Konkurrenz, Dateirechte und
Symlink-/Hardlinkabwehr, Markerbesitz, atomare große Paketbestände und konkurrierende
Drainabsichten. Sie führen weder Docker, APT noch reale Importerprofile aus.
Diese vier Tests und die systemd-Verifikation sind noch nicht ausgeführt.
Vor Kundenaktivierung verbindlich nachholen. Nach erfolgreicher unveränderter Prüfung keine
unbegründeten Serienwiederholungen.

## 3. Ziele sichern und konkret bereitstellen

Nur wenn alle neuen Ziel**dateien** frei sind, Pakethashes stimmen, die bisherigen
Dienst-/Timerzustände gesichert sind und das aktuelle Wartungsfenster ausgeschlossen
ist. Bestehende Verzeichnisse dürfen weitere fremde Drop-ins enthalten; diese nicht
überschreiben oder entfernen. Pro Ziel neue Datei schon vor dem Schreiben in die
private Rückfallliste aufnehmen. Root-Sicherung0700 mit Metadaten/Hashes und
Enabled-/Active-Zuständen anlegen; Paket-/Applikationsbackup nicht verändern.
Zusätzlich die vorhandene `/etc/invoice-importer/host-runtime.py` mit Modus/Eigentümer
sichern und ihren tatsächlichen Hash gegen den d9-Ausgangsbeleg prüfen. Bei anderer
Quelle stoppen und Diff neu prüfen. Nur diesen belegten Patch ersetzen.

| Quelle in deploy | Ziel | Modus |
| --- | --- | --- |
| run-maintenance.py | /etc/invoice-importer/run-maintenance.py | 0700 root:root |
| maintenance-effects.py | /etc/invoice-importer/maintenance-effects.py | 0700 root:root |
| host-runtime.py (einziger vorhandener Peerpatch) | /etc/invoice-importer/host-runtime.py | gesicherten rootgeschützten Modus beibehalten |
| privates ausgefülltes Profil | /etc/invoice-importer/maintenance-host.json | 0600 root:root |
| invoice-maintenance.tmpfiles.example | /etc/tmpfiles.d/invoice-maintenance.conf | 0644 root:root |
| invoice-maintenance.service.example | /etc/systemd/system/invoice-maintenance.service | 0644 root:root |
| invoice-maintenance.timer.example | /etc/systemd/system/invoice-maintenance.timer | 0644 root:root |
| invoice-maintenance-guard.service.example | /etc/systemd/system/invoice-maintenance-guard.service | 0644 root:root |
| invoice-maintenance-recover.service.example | /etc/systemd/system/invoice-maintenance-recover.service | 0644 root:root |
| invoice-maintenance-start-order.conf.example | /etc/systemd/system/invoice-importer.service.d/30-maintenance.conf | 0644 root:root |
| invoice-maintenance-worker-order.conf.example | Je 30-maintenance.conf in den sechs nachfolgend genannten .d-Verzeichnissen | 0644 root:root |

Die sechs Worker-Verzeichnisse gehören zu `invoice-processing@.service`,
`invoice-notifications.service`, `invoice-tls.service`, `invoice-status.service`,
`invoice-rotation-daily.service` und `invoice-rotation-opportunity.service`.
Der Template-Drop-in gilt für beide Processinginstanzen. Die vorhandenen sieben
Timerdateien und ihre Phasen bleiben unverändert. 15 neue Zieldateien plus genau
ein gesicherter Peerpatch ergeben 16 Installationstargets. Der Importer-Drop-in
setzt zusätzlich ExecStop auf `service-drain`; die ursprüngliche explizite
Drain-CLI bleibt unverändert. Die neue Scheduledunit verwendet
Wants/After statt Requires auf die Importerdienste, damit ein nativer Dockerrestart
nicht über deren Stopabhängigkeiten die Pakettransaktion abbrechen lässt.
Der Guard verwendet ebenfalls Wants/After auf Docker und bleibt beim paketbedingten
Docker-Stopp aktiv. Die vollständige Reihenfolge und einen 45s-busy-Stopphook bei
gehaltener Wartungssperre auf einem isolierten systemd-Prüfstand nachweisen.

Mit festem Quellverzeichnis `/root/ap10-reviewed` als Beispiel:

```sh
install -o root -g root -m 0700 /root/ap10-reviewed/deploy/run-maintenance.py /etc/invoice-importer/run-maintenance.py
install -o root -g root -m 0700 /root/ap10-reviewed/deploy/maintenance-effects.py /etc/invoice-importer/maintenance-effects.py
install -o root -g root -m 0644 /root/ap10-reviewed/deploy/invoice-maintenance.tmpfiles.example /etc/tmpfiles.d/invoice-maintenance.conf
for unit in invoice-maintenance.service invoice-maintenance.timer invoice-maintenance-guard.service invoice-maintenance-recover.service; do
  install -o root -g root -m 0644 "/root/ap10-reviewed/deploy/$unit.example" "/etc/systemd/system/$unit"
done
install -d -o root -g root -m 0755 /etc/systemd/system/invoice-importer.service.d
install -o root -g root -m 0644 /root/ap10-reviewed/deploy/invoice-maintenance-start-order.conf.example /etc/systemd/system/invoice-importer.service.d/30-maintenance.conf
for unit in invoice-processing@.service invoice-notifications.service invoice-tls.service invoice-status.service invoice-rotation-daily.service invoice-rotation-opportunity.service; do
  install -d -o root -g root -m 0755 "/etc/systemd/system/$unit.d"
  install -o root -g root -m 0644 /root/ap10-reviewed/deploy/invoice-maintenance-worker-order.conf.example "/etc/systemd/system/$unit.d/30-maintenance.conf"
done
systemd-tmpfiles --create /etc/tmpfiles.d/invoice-importer.conf /etc/tmpfiles.d/invoice-maintenance.conf
```

Für den Peerpatch nach gesicherter und abgeglichener Ausgangsdatei etwa:

```sh
test ! -e /root/ap10-host-runtime.before
cp --preserve=mode,ownership,timestamps /etc/invoice-importer/host-runtime.py /root/ap10-host-runtime.before
sha256sum /root/ap10-host-runtime.before
test ! -e /etc/invoice-importer/.host-runtime.ap10
test ! -L /etc/invoice-importer/.host-runtime.ap10
install -o root -g root -m 0700 /root/ap10-reviewed/deploy/host-runtime.py /etc/invoice-importer/.host-runtime.ap10
chmod --reference=/root/ap10-host-runtime.before /etc/invoice-importer/.host-runtime.ap10
mv -T /etc/invoice-importer/.host-runtime.ap10 /etc/invoice-importer/host-runtime.py
```

Vor dem ersten Kopieren den tatsächlichen Sicherungsmodus geschützt prüfen;
keine fremde vorhandene Sicherungsdatei überschreiben. Der Patch kann von einem
bereits laufenden kurzlebigen Hostprozess noch nicht geladen sein. Deshalb vor
Änderung einen freien Hostworkerbestand abgleichen, laufende Arbeit regulär enden
lassen und anschließend die wirksame neue Hülle nachweisen.

Vorlage `maintenance-host.example.json` privat ausfüllen: tatsächliche Machine-ID,
Ubuntu26.04, Produktpin d9 und bestehende geschützte Rotations-/Statusprofile.
Für die erste ausschließliche Hashaufnahme kann der Aptdigest aus64Nullen bestehen;
alle Units/Timer bleiben dabei deaktiviert und es darf noch keinen Wartungszustand
geben. Profil0600 bereitstellen, dann:

```sh
python3 -I -B /etc/invoice-importer/run-maintenance.py policy-digest
```

Ausgegebenen Hash **erst nach inhaltlichem Quellen-/Hookreview** ins private Profil
übernehmen, atomar0600 speichern und privat hashen. Bei offenem Wartungszustand
Profil nicht zur Umgehung austauschen. Alle 16 Zieldateien und tatsächlichen
zusammengeführten Units/Drop-ins nochmals gegen Manifest/Plan abgleichen.

## 4. Konflikte, Startreihenfolge und heutige Probe

Nach Quellenreview und freiem APTbestand ausschließlich den bestätigten bisherigen
`apt-daily-upgrade.timer` deaktivieren. Disabled/inactive ist im Paket eine
Vorbedingung; Services werden nicht unterbrochen. Alte Zustände für den Rückweg
privat sichern. Keine weiteren Zeitpläne aus Vermutung entfernen.

```sh
systemctl disable --now apt-daily-upgrade.timer
systemctl daemon-reload
systemd-analyze verify invoice-maintenance.service invoice-maintenance.timer invoice-maintenance-guard.service invoice-maintenance-recover.service invoice-importer.service invoice-processing@.service invoice-notifications.service invoice-tls.service invoice-status.service invoice-rotation-daily.service invoice-rotation-opportunity.service
systemctl is-active invoice-importer.service docker.service
systemctl start invoice-maintenance-guard.service
systemctl start invoice-maintenance-recover.service
python3 -I -B /etc/invoice-importer/run-maintenance.py check
```

Die Recoverunit verwendet ausschließlich `verify-boot`; `recover` mit exakter
Laufquittierung bleibt dem ausdrücklich abgestimmten manuellen Weg vorbehalten.
Der neue SQLleser ist ausschließlich eine Hostquelle, kein neues Image. Vor
Aktivierung auf dem isolierten nativen Prüfstand die echte d9-Image-/MariaDB-
Einbindung, READ-ONLY-Sitzung, Scope-/Instanzabwehr, Zeitgrenzen und tatsächliche
Containerbereinigung qualifiziert nachweisen. Die lokalen SQLitefälle prüfen
Zustandsauswahl, ersetzen diesen nativen Nachweis aber nicht.
Guard und Recover dürfen bei leerem Wartungsjournal weder Pakete noch Reboot
ausführen. Der vorhandene Importer muss vorher aktiv/gesund sein; dadurch startet
die leere Recoverprüfung ihn nicht neu. Bei Fehler Aktivierung abbrechen, keine
Korrektur durch Erzeugen eines gefälschten erfolgreichen Journals.

Die heutige Mittwochprobe umfasst Check, synthetische Kommandotests, Offslotguard
und lesenden Bestand. Ein koordinierter `scheduled`-Aufruf außerhalb Sonntag03:00
bis03:15 muss `skipped/outside_start_window` liefern. Vor-/Nachboot-ID, Paketbestand,
Containerzustände, Pause und alle vorhandenen Timer unverändert rücklesen. Der
Check nimmt kurz Sperren und einen lokalen Statusworker; das ist keine Garantie
vollständig unbeeinflusster paralleler Graphrequests. Vorher mit Betreiber abstimmen.
Kein echtes Upgrade, kein Kundenreboot und keine künstliche Boot-/Paketbedarfsdatei.

Danach, weiterhin außerhalb des Fensters und erst nach vollständigem Readback:

```sh
systemctl enable --now invoice-maintenance.timer
systemctl list-timers invoice-maintenance.timer --all --no-pager
systemctl show invoice-maintenance.timer -p TimersCalendar -p Persistent -p AccuracyUSec -p RandomizedDelayUSec -p NextElapseUSecRealtime
```

Nächster Sonntagtermin muss stimmen, keine unmittelbare Ausführung und keine
Persistenznachholung. Keine neue Codexautomation anlegen. Der beauftragte
Wartungschat übernimmt den folgenden Nachkontrollvertrag; er installiert nicht parallel.

## 5. Erster echter Lauf und lesende Nachkontrolle

Einrichtung/Simulation beweist noch keinen echten Paket-/Reboot-/Wiederanlauf.
Erster Sonntagslauf bleibt offen. Root führt dafür vorab den tatsächlichen
Backup-/Zugang-/Wiederanlaufabgleich durch. Ob überhaupt Pakete/Rebootbedarf
vorliegen, ist erst dann feststellbar. Keine unnötige echte Mittwochsprobe.

Die bestehende KI-Nachkontrolle bleibt **Sonntag 03:30 Europe/Berlin**. Keine zweite
Automation und keine Terminverschiebung. Aktivierung erst nach qualifizierter
Einrichtung, Review und gesondertem Rücklesen; der bisherige Eintrag bleibt bis
dahin pausiert. Der technische Betreiber verantwortet den Hostlauf; der bestehende
Wartungschat führt ausschließlich die lesende Nachkontrolle und meldet dem Betreiber.

Um 03:30 den aktuellen profil-/instanzgebundenen Laufbeleg und tatsächlichen
Scheduledprozess zusammen lesen. Eine passende aktive Oneshot-Ausführung mit
laufender nativer Paketarbeit ist **laufend**, kein Erfolg und kein bewiesener
Fehler. Fehlende Abschlussbelege bei unklarem Prozessausgang sind **offen**;
ein belegter Fehler bleibt **Fehler**. `apt_in_progress=true` bei fehlendem
passendem Prozess ist unbestätigter Ausgang und wird nicht automatisch quittiert.

Bei regulär laufender gebundener Arbeit im selben Wartungschat höchstens alle
fünf Minuten lesend weiter beobachten, längstens bis **05:30 Europe/Berlin**.
Toolfreie Warteabschnitte zählen nicht zur Supportzeit. Tatsächliches Ende löst
die abschließende Rücklese im bestehenden aktiven Chat aus; Abschlussbelege gegen
denselben Originalvorzustand prüfen. Ein Fehler wird sofort gemeldet. APT wird
auch nach 04:30 regulär abgewartet; ab 04:30 kein neuer Rebootauftrag. Ein laufender
Paketprozess wird niemals wegen Ende der Beobachtung gestoppt.

Ist um 05:30 noch kein bestätigter Abschluss vorhanden, als **offen, weiterhin
laufend** beziehungsweise **Ausgang unbestätigt** mit Laufkennung, letzter
bestätigter Phase und nächster Zuständigkeit an den technischen Betreiber
übergeben. Dieser veranlasst das endgültige lesende Rücklesen nach tatsächlichem
Ende im selben Wartungschat. Spätestens am nächsten Arbeitstag um 08:00 erfolgt
ein manueller Statusauftrag durch den Betreiber; läuft die Arbeit dann noch,
bleibt der Abschluss weiter offen und nach tatsächlichem Ende nachzulesen.
Kein neuer Scheduler. Fehlendes VPN wird bei 03:30
als nicht prüfbar erfasst; höchstens zwei weitere lesende Zugangsversuche um
03:35/03:40, dann offene Übergabe an den Betreiber und Fortsetzung nach bestätigtem
Zugang. Keine verdeckte Dauerwartezeit und kein Erfolg aus einer SSHunterbrechung.

Bei jeder Kontrolle den tatsächlichen Historybestand zählen. Ab 40 abgeschlossenen
Einträgen Vorwarnung an den technischen Betreiber und Archivierung nach Abschnitt7
vor dem nächsten Sonntagslauf beauftragen. Bei52 blockiert weitere Paketarbeit;
keine Umgehung durch Löschen von Journal oder aktuellem Lauf.

Für den Wartungschat:

```sh
date -Is
cat /proc/sys/kernel/random/boot_id
systemctl status invoice-maintenance.service invoice-maintenance-guard.service invoice-maintenance-recover.service --no-pager
journalctl -u invoice-maintenance.service -u invoice-maintenance-guard.service -u invoice-maintenance-recover.service --since '-8 days' --no-pager
systemctl list-timers --all --no-pager
```

Privates `state.json` mit zugehörigen Paket- und Historydateien lesen, nicht ändern.
Erfolgskriterien: beideAPT-Exitcodes0, dpkg-Audit leer, nativeBedarfsentscheidung,
bei Reboot tatsächliche neue Boot-ID und Nachprüfung, bestätigte richtigeImages/
DB-/Nginxidentität, echteImport-/TLSmounts, regulär geprüftesHTTPS, aktuellesGate
allowed mit passendem Material, siebenBestandstimer plus neuerSonntagstimer aktiv,
eigenerDrain entfernt beziehungsweise fremdePause unverändert und frischer passender
Status. Ein gerade laufender normaler Job kann den Status einschränken; Befund
präzise wiedergeben statt dauerhaft gesund zu behaupten. KeinProbeversand.
`terminal_uncertain` bedeutet einen erhaltenen, verbrauchten besitzerfreien
Einmalversuch unter bestätigter Ruhe; dies allein ist kein Wartungsfehler und
kein Zustellnachweis. Offene Besitzer-/Sending-/Publishing-/TLSzustände bleiben
Handlungsbedarf. GUI-Abschluss ist nur Browserzustand und keine globale Freigabe.

LaufendeAPTarbeit nicht beenden. `failed`, `awaiting_reboot`, unbekannteWirkung,
fehlendeNachbelege, fremdePause oder nichtprüfbarerZugang als Handlungsbedarf melden.
Keine neuenUpdates, Reboots, Statusresets, Bereinigungen oder Buchungen durch den
Nachkontrollchat. Ein belegtes `recovered` beschreibt Wiederanlauf, keinen Paketrollback.

## 6. Rückweg

Bei reinem Einrichtungsfehler ohne gestartete Paketarbeit: neuenTimer deaktivieren,
etwaige laufende Guard-/Recoverprüfung regulär enden lassen. Tatsächlich installierte
Dateiliste gegen vorherigeFreiliste/Manifest abgleichen und ausschließlich diese
Neuanlagen entfernen. FremdeDrop-ins/Rootprofile, alteImages, DB und bestehende
Status-/Rotationsjournale erhalten. Leere selbst angelegte .d-Verzeichnisse nur
mit `rmdir` entfernen. `daemon-reload`, ursprünglicheUnitdefinitionen und alle
ursprünglichenTimerzustände zurücklesen. BestehendeImporterunit nicht als reflexartigen
Rückweg neu starten. AltenAPT-Timer nur nach bestätigter ursprünglicherAbsicht und
außerhalb eines wirksamen Nachholfensters wieder aktivieren; Persistenz beachten.

Zusätzlich nur den gesicherten Peerpatch zurücknehmen, wenn seine aktuelle Datei
noch exakt den gelieferten AP10-Hash hat und kein offener Wartungszustand besteht:

```sh
test ! -e /etc/invoice-importer/.host-runtime.rollback
test ! -L /etc/invoice-importer/.host-runtime.rollback
cp --preserve=mode,ownership,timestamps /root/ap10-host-runtime.before /etc/invoice-importer/.host-runtime.rollback
mv -T /etc/invoice-importer/.host-runtime.rollback /etc/invoice-importer/host-runtime.py
sha256sum /etc/invoice-importer/host-runtime.py
systemctl daemon-reload
```

Zurückgelesener Hash, Modus und Eigentümer müssen dem gesicherten Original
entsprechen. Bei Fremdänderung nicht überschreiben. Nach offener Paketwirkung
auch den Hostpatch zusammen mit Guard/Drop-ins bis zur Klärung erhalten.

Wenn `state.json` offen oder nativeAPTarbeit gestartet/unklar ist: **nur neue
Sonntagsauslösung anhalten**, Guard/Ordnungsdateien und Journale erhalten. Kein
Stop-/Killauftrag für APT, kein Löschen der Pause oder Rohdaten. Nach known failure
ist `recover --acknowledge-run <exakte-Laufkennung>` ausschließlich als explizit
abgestimmte manuelle Wiederanlaufprüfung erlaubt,
mit vorheriger leerer Audit-/Lock-/Prozessprüfung und aktivem Guard. Bei
`apt_in_progress=true` verweigert das Werkzeug; dafür konkreten administrativen
Abgleich anhand nativer APT-/dpkg-Belege planen. Keine unbewiesene Zustandsquittung.

Nur nach ausdrücklicher Abstimmung, bekannten Paketresultaten, vollständigen
Originalvorbelegen und Prüfung der konkreten unveränderten Laufkennung:

```sh
python3 -I -B /etc/invoice-importer/run-maintenance.py recover --acknowledge-run '<exakte-Laufkennung-aus-state.json>'
```

Diese manuelle Quittierung ersetzt keinen fehlenden Paket-/Rebootnachweis und
wird niemals in eine automatisch angeforderte Unit eingetragen. Gespeicherte
Rebootabsicht verlangt auch im Fehlerstatus einen tatsächlich neuen Boot.

Bereits installierte Pakete werden durch Entfernen der AP10dateien nicht rückgängig
gemacht. Paketdowngrade oder VMrestore braucht einen gesondert geprüften Plan.
Weder tägliche Sicherung noch dieses Quellpaket beweisen einen Vollrestore.

## 7. Journalarchivierung

Verantwortlich ist der technische Betreiber. Ab 40 Historyeinträgen wird der
Archivauftrag vor dem nächsten Sonntag erledigt; die Kapazitätsgrenze52 bleibt
unverändert. Der Wartungschat meldet ausschließlich, führt keine Archivierung aus.
Keine zusätzliche E-Mailfunktion und kein automatischer Löschdienst.

Kontrollierter Weg in einem ausdrücklich abgestimmten ruhigen Betreiberabschnitt:

1. Neuen Sonntagstimer vorübergehend deaktivieren und ursprünglichen Zustand
   festhalten. Laufende Wartung regulär enden lassen. Dieselbe Wartungssperre
   `/run/invoice-importer/maintenance.lock` exklusiv und nicht blockierend halten.
   Kein offener aktueller Lauf, keine native Paketarbeit und keine unbekannten
   Jobs. `state.json` einschließlich Hash nur lesen, niemals bearbeiten.
2. Exakt 20 älteste vollständig abgeschlossene Historybelege mit Phase `completed`
   oder `recovered` und passender belegter Instanz-/Profilzuordnung auswählen.
   Aktuelle `state.json`-Laufkennung auch bei zufälligem Historyduplikat ausschließen.
   Originale Fehler-/Wiederaufnahmeangaben im JSON unverändert erhalten.
3. Neues rootgeschütztes0700-Verzeichnis
   `/var/lib/invoice-importer/maintenance-archive/<UTC-Zeitstempel>` anlegen.
   Für jede ausgewählte UUID den bisherigen `history/<UUID>.json` und alle
   zugehörigen tatsächlich vorhandenen `<UUID>.*.packages` mit Modus/Owner0600
   in einer konkreten Dateiliste erfassen. Keine Symlinks, fremden Dateien oder
   zusätzlichen offenen Laufdateien aufnehmen. Fehlende historische Teilbelege
   als fehlend dokumentieren und nicht neu erzeugen.
4. SHA256manifest über genau diese Originalbytes erstellen; privaten Betreiberauftrag,
   Auswahl, Originalpfade, Originalmetadaten und Zeitpunkt ergänzen. Dateien zuerst
   metadatentreu ins neue Archiv kopieren, dort `sha256sum --check` vollständig
   erfolgreich ausführen und Kopie getrennt rücklesen. Bei Abweichung abbrechen,
   Originale erhalten. Belege und Paketbestände gehören gemeinsam ins Archiv.
5. Ausschließlich die exakt ausgewählten und nochmals hashgleichen Originaldateien
   durch einzeln benannte Moves in das verifizierte Archiv überführen; keine Inhaltsänderung, kein pauschales
   Aufräumen und kein Löschen von Belegen. Den unveränderten Hash von `state.json`
   und allen nicht ausgewählten Dateien bestätigen. Historybestand muss um20
   zurückgegangen sein; sämtliche archivierten JSON-/Paketbytes bleiben per Manifest
   nachweisbar vorhanden. Archiv in die bestehende Sicherungsrücklese aufnehmen;
   daraus keinen vollständig geprüften VMrestore ableiten.
6. Sperre freigeben, ursprünglichen neuen Timerzustand geordnet wiederherstellen
   und Kalender/NextTermin außerhalb des Eintrittsfensters rücklesen. Archivmanifest
   und Ergebnis an den Betreiber übergeben. Erst danach Kapazität als erledigt melden.

Bei einem teilweise fehlgeschlagenen Move Auswahl/Manifest erhalten und anhand
der unveränderten Hashes jedes bereits überführte und jedes verbliebene Original
einzeln abgleichen. Timer bis zur geklärten vollständigen Überführung deaktiviert
lassen. Kein weiterer Lauf und kein pauschales Wiederholen einer Dateiliste.

Wenn ein aktueller Lauf offen oder eine Fremdänderung vorhanden ist, keinen Teil
dieses Archivwegs durchführen. Nur den Kapazitätsbefund und das weitere
Betreiberhandeln festhalten. Aktueller Zustand und aktuelle Paket-/Fehlerbelege
werden weder gelöscht noch verändert.
