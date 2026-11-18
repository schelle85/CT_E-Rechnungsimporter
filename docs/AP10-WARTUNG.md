# AP10: Wöchentliche Hostwartung

Stand: 18. November 2026. AP10 ist freigegeben. Dieser Quellstand ist eine
**lokale Lieferung zur Quellen- und Einrichtungsprüfung**, noch keine Installation
oder Betriebsabnahme. Produkt/API/Web/Worker bleiben auf
`d9f32a5a9c9fb642f59a13ed2550f74532fc3ebe`, Schema008. Neue Wartungsdateien haben
einen getrennten Liefercommit. Echte Anschlusswerte und Einrichtungsbelege bleiben privat.

## Entscheidung und vorhandene Bausteine

Native APT-/dpkg-Werkzeuge installieren die Betriebssystempakete. systemd übernimmt
Terminierung und Startreihenfolge. `unattended-upgrades` ist ein geeignetes natives
Werkzeug für Origin-/Securityregeln, stellt aber allein keinen Importer-/Graph-
Drain mit Material-/Commitnachweis bereit. Der bestehende interne MCP-TANSS-
Wartungsweg hat das Muster APTupdate, Upgrade ohne Entfernen, Audit und systemd
bereits erprobt. Dessen Hostname, Dienste, Zertifikate und pauschaler Neustart nach
Erfolg werden hier nicht übernommen. Es entsteht kein neuer Paketmanager.

Die notwendige Ergänzung beschränkt sich auf Importerkoordination, ein kleines
persistentes Wartungsjournal und den bedingten Wiederanlauf. Verwendet werden die
vorhandenen AP08-/AP12-Peers und deren Prüfungen. Ein enger AP10-Patch an
`host-runtime.py` ergänzt ausschließlich `drain(..., preserve_existing=True)`;
der normale ausdrückliche Drain behält seine bisherige neue Marker-Epoche.
Graphkeys, Gate-JSON, Rotationseinstellungen,
Schema, Images und Sicherungskonfiguration werden durch den Wartungswrapper nicht verändert.
Bestehende AP12-Bootwiederaufnahme bleibt der zuständige Zertifikatsablauf.

## Termine und Grenzen

- Timer: Sonntag03:00 `Europe/Berlin`, `Persistent=false`, Genauigkeit1s,
  keine Zufallsverzögerung. Der Timer erzeugt eine Gelegenheit, keinen Sofortnachlauf.
- Eintritt und Beginn beider APTschritte ausschließlich Sonntag03:00 bis vor03:15.
  Vor Upgrade wird die Uhr erneut geprüft. Ausgefallener Termin wartet bis zum
  nächsten Sonntag; kein Nachholen am Mittag oder beim Einschalten.
- Neustart nur nach erfolgreichen APTschritten, leerem dpkg-Audit, erneut
  geprüften Diensten/Mounts/HTTPS/Graphbindung und nativem `/run/reboot-required`.
  Zusätzlich muss es noch Sonntag vor04:30 sein. Direkt vor dem Rebootauftrag
  wird das Fenster nach dem zweiten kontrollierten Stopp erneut geprüft.
- APT/dpkg-Transaktionen haben bewusst keinen gewaltsamen Gesamttimeout. Netzwerk-
  und Lockwartezeiten sind begrenzt; eine bereits laufende Pakettransaktion wird
  bei Überschreitung des Fensters zu Ende abgewartet, niemals durch einen
  Zeitbudget-Kill unterbrochen. Danach kein verspäteter automatischer Neustart.
- SIGTERM/SIGINT markieren Abbruchwunsch; native APTarbeit wird erst beendet
  abgewartet. Danach Fehler und Pause, kein Reboot. Root darf laufende Paketarbeit
  nicht per Dienstkill, eigenem Reboot oder zweitem Paketmanager unterbrechen.

03:00 liegt auch am Berliner Sommer-/Winterzeitwechsel eindeutig nach dem
übersprungenen beziehungsweise doppelten Zwei-Uhr-Bereich. Der Wrapper prüft die
lokale Zeitzone unabhängig von der Hoststandardzeitzone.

## Koordination und Erfolg

Vorherige nicht abgeschlossene Wartung sperrt einen neuen Paketlauf. Vorhandene
Betreiberpause bleibt unverändert und führt zu Abbruch ohne Updates. Der Wrapper
löscht niemals einen fremden Drainmarker. Seine eigene Pause ist ein zufälliger,
vor dem Schreiben dauerhaft gespeicherter Besitzerwert; Freigabe vergleicht ihn
unter der vorhandenen Gate-Sperre erneut.

Der neue Importer-Drop-in ersetzt nur dessen ExecStop durch
`run-maintenance.py service-drain`. Dieser Weg erhält einen bereits vorhandenen
Marker; ohne Marker setzt er eine Pause und prüft wie bisher begrenzt Lifecycle
und Worker. Ein ausdrücklich über `run-automation.py drain` angeforderter neuer
Drain erzeugt weiterhin einen neuen Marker, bevor er auf den Lifecycle wartet.
Ein parallel laufender Start kann diese neue Absicht deshalb nicht freigeben.
Operatorpause und neue Drainabsicht werden nicht als wartungseigen vereinnahmt.
Vor jedem APTschritt, nach Upgrade und unmittelbar vor dem Rebootauftrag wird
der unveränderte Besitzer erneut geprüft. Eine zwischenzeitlich neue fremde Pause
sperrt die nächste Wirkung und wird nicht entfernt.

Während die Wartung ihre Lifecycle-Sperre hält, kann ein von APT veranlasster
Docker-Stopp den Stopphook nach dessen bisherigen 45 Sekunden konservativ als
busy beenden. Der Marker bleibt erhalten; weder dieser Hook noch die neuen
Abhängigkeiten beenden die Pakettransaktion. Der spätere bestehende Startvertrag
wird außerhalb der Wartungssperren wieder aktiviert und geprüft. Dieses Verhalten
ist vor Aktivierung zusätzlich nativ nachzuweisen.

Die Arbeitsreihenfolge ist Wartungssperre, AP12-Writer, Lifecycle, Processing,
Notifications und schließlich Graph-EX. Die vorhandenen Lifecycle-Sperren warten
begrenzt; bei belegter Sperre wird sicher abgebrochen. Aktive Graphfreigaben dürfen
enden; Graph-EX verhindert danach neue externe Graphwirkungen, ohne Gate-JSON oder
Zertifikate umzuschreiben. Unbekannte Worker-/Rotationsjobs werden nicht bereinigt,
sondern sperren die Wartung. Keine doppelten Sperrerwerbe durch Startup unter bereits
gehaltenen Lifecycle-/Writersperren.

Der normale belegte Zustand `committed/new`, SQL-Überlappung und Gate allowed ist
zulässig. Eine geplante Altkeybereinigung gilt nicht als laufender Wechsel. Auch
historische terminale Fehlversuche begründen für sich keine Sperre. Voraussetzung
sind passender aktueller Material-/Seal-/Boot-/Instanzbeleg und kein laufender oder
ungeklärter aktueller Vorgang. Geschlossene Vorgänge benötigen ihren passenden
versiegelten Hostbeleg; der Bootstrapfall seinen gebundenen unveränderten Beleg.

Nach der Vorprüfung wird die eigene Pause gesetzt. Nginx wird mit nachgewiesenem
SIGQUIT und bis zu 330s Schonfrist beendet, anschließend API bis zu 60s und DB bis zu 180s.
Exitcode0, identische Container und tatsächliche Cgroupruhe sind verbindlich. Nach
APIstopp wird SQL-/Rotationsstatus nochmals über den vorhandenen lokalen Statusworker
geprüft, bevor die DB gestoppt wird. Keine äußere Graphoperation aus diesem Statusabruf.
Ein harter oder unbestätigter Stopp erlaubt keine Paketarbeit.

Die zeitweise Portalunterbrechung ist Teil des geplanten Wartungsfensters. So kann
auch ein Paket-Maintainerskript, das Docker neu startet, keine laufende Importer-
oder Kundenanforderung mitten in der Paketinstallation zerreißen. Bereits wirksame
Mail-/Dateiaktionen und ihre Journale werden weder zurückgesetzt noch erneut ausgelöst.

## Native Paketpolitik

Vor jedem Lauf müssen freigegebene Ubuntu26.04-Hostidentität, Rootprofile und
gehashte APTquellen/Preferences/Konfiguration passen. Normale konfigurierte
OS-Paketupdates erfolgen mit:

```text
apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=2 -o Acquire::http::Timeout=60 -o Acquire::https::Timeout=60 update --error-on=any
apt-get -o DPkg::Lock::Timeout=60 -o Acquire::Retries=2 -o Acquire::http::Timeout=60 -o Acquire::https::Timeout=60 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold --assume-yes --with-new-pkgs --no-remove upgrade
```

APT/dpkg-Locks werden nie gelöscht. Native Holds werden nicht übergangen.
Kein Releaseupgrade, dist-upgrade, autoremove, Purge, Imagepull, Anwendungspaket-
oder Datenbankschemawechsel. Neue abhängige OS-Pakete etwa für Kernel sind erlaubt;
Entfernen vorhandener Pakete nicht. APTquellen und Hooks müssen vor Einrichtung
konkret geprüft werden, besonders Drittanbieterquellen. Der Hash allein ist kein
inhaltlicher Vertrauensnachweis. Generierte `01autoremove-kernels` ist vom
Konfigurationshash ausgenommen; es wird trotzdem kein autoremove aufgerufen.

`DEBIAN_FRONTEND=noninteractive`, `--force-confdef` und `--force-confold` begrenzen
Rückfragen und erhalten bestehende Conffiles. `NEEDRESTART_SUSPEND=1` unterdrückt
den zusätzlichen needrestart-APT-Hook, `NEEDRESTART_MODE=l` verhindert einen
interaktiven automatischen Neustartmodus. Paket-Maintainerskripte können dennoch
OSdienste neu starten. Das wird nicht als vollständig unterdrückt behauptet.
Importercontainer werden deshalb vorher kontrolliert ruhig gestellt. Ohne nativen
Rebootbedarf gibt es keinen pauschalen Reboot zur Aktivierung beliebiger übriger
Dienste; eventuelle weitere Dienstneustarts bleiben ein gesonderter Betreiberbefund.

`apt-daily-upgrade.timer` muss nach geprüftem Bestand disabled/inactive sein.
Laufende apt-daily-/upgrade-Services führen zu Abbruch; sie werden nicht gestoppt.
`apt-daily.timer` für Listen bleibt erhalten. Ein zeitgleicher Listenlauf kann
weiterhin einen konservativen APTfehler erzeugen. Zusätzliche Paket-/Rebootjobs
aus einem anderen Bestand sind vor Aktivierung gesondert abzugleichen.

## Wiederanlauf und Journal

Ohne Reboot werden die vorhandenen DB-/API-/Nginxcontainer in dieser Reihenfolge
gestartet und geprüft. Danach werden die Sperren freigegeben, der bestehende
Importer-Startvertrag gegebenenfalls wieder aktiviert und die Nachbedingungen
unter erneutem Schutz gelesen. Erst dann wird ausschließlich die eigene Pause
entfernt und der vorhandene Statussammler aktualisiert.

Bei Rebootbedarf werden zunächst dieselben Nachbedingungen geprüft. Dann werden
die Container erneut kontrolliert gestoppt, der Rebootwunsch dauerhaft gespeichert
und genau einmal angefordert. Die Rückgabe sagt nur `verification_pending`, nicht
"Wiederanlauf bestanden". Kein Replay eines unklaren Rebootauftrags.

Vor dem nächsten Importerstart stellt eine vorgeschaltete Guardunit die eigene
Pause aus dem persistenten Journal wieder her. Der bestehende AP12start darf seine
gebundene Wiederaufnahme ausführen. Erst danach läuft die neue Recoverunit. Die
Workerunits sind nach dieser geordnet; ihre sieben Timer werden nicht umgeschrieben.
Guard und Scheduledunit verwenden auf Docker beziehungsweise Importer nur Wants:
Ein paketbedingter Docker-Stopp darf den Guard nicht deaktivieren und beim erneuten
Importerstart an der bereits gehaltenen Wartungssperre blockieren. Der Importer
selbst behält seinen bisherigen Dockervertrag und benötigt den aktiven Guard.
Die Recoverunit führt niemals APT oder einen weiteren Reboot aus. Für den Abschluss
eines angeforderten Reboots ist eine neue Boot-ID notwendig. Bei jedem Wiederanlauf
sind ein leeres Audit, derselbe bestätigte Paketbestand sowie echte Mounts, HTTPS,
Graphbindung und die sieben aktivierten Bestandstimer Voraussetzungen.
DB-/Nginxidentität muss erhalten sein. Ein von AP12 ordnungsgemäß neu erzeugter
APIcontainer ist nur innerhalb dessen vorhandener geprüfter Bindungen zulässig.

Rootgeschützte Ablage: `/var/lib/invoice-importer/maintenance`,0700. `state.json`
und Paketbestände0600. Sie enthalten Vor-/Nachboot, konkrete Zeiten, Phase,
Paketstatus/-hash, Exitcodes und Outputdigest der APTschritte, Container-/Image-
bindungen, Mounts/HTTPS, Timer, aktuellen Graphfingerabdruck/Seal und Statusstand.
Keine Secrets, Schlüssel oder Maildaten. Rohe APTausgabe wird gestreamt gehasht
und verworfen, nicht in Journald oder Dateien kopiert; sie könnte geheime Repository-
URLs enthalten. Ausnahmen werden nur mit begrenztem neutralem Code ausgegeben.

Ein JSONzustand ist höchstens 64KiB, jede Paketbestandsdatei höchstens 1MiB.
Nach 52 archivierten Läufen wird weitere Arbeit bis zur kontrollierten Archivierung
verweigert. Es gibt keinen automatischen Löschdienst. Unter `history` bleiben
vorige abgeschlossene JSONbelege, Paketdateien tragen die ursprüngliche Laufkennung.
Systemjournal und `state.json` sind gemeinsam auszuwerten; fehlende Nachdaten sind
nicht geprüft, kein stiller Erfolg.

| Phase / Ergebnis | Nachkontrolle |
| --- | --- |
| completed | Paketlauf und Nachprüfung abgeschlossen; bei Reboot neue Boot-ID prüfen. Zeitgebundene Momentaufnahme, keine Dauerverfügbarkeit zugesagt. |
| awaiting_reboot | Auftrag angefordert/gegebenenfalls bestätigt; Boot-/Nachprüfung noch offen. Nicht nochmals rebooten. |
| failed | Grund, APTexitcodes und letzte bestätigte Phase lesen. Pause kann bewusst erhalten sein; keine selbstständige neue Installation. |
| apt_in_progress=true | Abbruch-/Antwortverlust während nativer Arbeit. Keine automatische Wiederholung oder automatische Freigabe; Betreiber muss Paketlocks/Prozesse und native Logs abgleichen. |
| recovered | Kontrollierter Wiederanlauf nach einem Fehler; keine Behauptung eines erfolgreichen Paketupgrades und kein Paketrollback. |
| skipped / outside_start_window | Keine Updates/Reboot und kein Nachholen. Nächste normale Gelegenheit abwarten. |

`recover` ist nach einem bekannten Fehler ein ausdrücklicher Betreiberweg für
Wiederanlauf/Nachprüfung, kein Reparaturbefehl für dpkg und keine Aktualisierung.
Ein unbekannter APTausgang, fremder Marker oder ungeklärte Graphbindung wird weiterhin
abgewiesen. Solche Fälle benötigen einen konkreten administrativen Wiederherstellungsplan,
nicht manuelles Entfernen der Sperren oder ein pauschales Zurücksetzen von JSONfeldern.

## Quellen, Einrichten und Nachkontrolle

Die [Bereitstellungs-/Rückweganleitung](AP10-EINRICHTUNG.md) ist vor jeder Wirkung
gegen den frischen tatsächlichen Hostbestand zu prüfen. Vorlagen in `deploy` sind
deaktiviert. `check` startet keinen Paket-/Rebootlauf, nimmt aber kurz vorhandene
Sperren und einen lokalen SQL-/Materialstatusworker in Anspruch; daher ebenfalls
nur koordiniert verwenden. `policy-digest` liefert ausschließlich den Konfigurationshash.

Die technische AP09-PDF und das AP11-Handbuch sind unveränderte datierte Abgaben.
Dieser Nachtrag ist bis zur Betriebsabnahme führend für AP10. Erst nach tatsächlicher
Einrichtung/Prüfung werden nötige neue PDFausgaben ausdrücklich geplant, erzeugt
und vollständig geprüft. Neue Kundenrückmeldung zum Handbuch bleibt davon getrennt.

Primärgrundlagen: [Ubuntu automatische Updates](https://ubuntu.com/server/docs/how-to/software/automatic-updates/),
[APT26.04](https://manpages.ubuntu.com/manpages/resolute/man8/apt-get.8.html),
[needrestart-Hook](https://github.com/liske/needrestart/blob/master/ex/apt/apt-pinvoke),
[needrestart-Modi](https://github.com/liske/needrestart/blob/master/needrestart),
[systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).
Die tatsächliche installierte systemd-/APTversion und konkrete Einheitenprüfung
bleiben Teil der Hostabnahme; neueste Onlinedokumentation ersetzt sie nicht.
