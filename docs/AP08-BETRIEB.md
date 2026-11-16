# AP08 – Betriebsübergang

Stand: 16. November 2026. AP08 ist im vereinbarten Umfang technisch abgeschlossen
und aus
`413095f823702d39b02bc8b3c989b526fdf808d0` bereitgestellt: A-Laufzeitbasis,
B-Start/Drain/Timer/HTTPSübernahme und C-Betriebsstatus für API/GUI.
Base-Apply und getrennte Readbacks erhalten Schema 007, Instanz, Konfiguration
und DBzustand. Echte externe HTTPSübernahme und anschließender No-op sowie
reiner Notificationvorlauf/Nullvorschauen sind bestätigt. Startdienst und fünf
Timer seit 16.11.2026 19:44:23 Europe/Berlin enabled/active; frischer Status active.
Geplante Leerlaufläufe und je ein Tages-/Wochenbericht mit HTTP 202 angenommen
sind bestätigt. Kontrollierter Wiederanlauf und geplanter TLS-Stundenlauf um
20:00 sind belegt. Der danach separat gesetzte Statusphasenversatz auf Sekunde 20
ist durch drei automatische Kontrollzyklen um 20:16:21, 20:17:21 und 20:18:21
Europe/Berlin bestätigt. Anwendung, Hostskripte und Images bleiben auf 413095f.
Ein zweiter Reboot oder vollständiger VMrestore ist damit nicht nachgewiesen.

## Bestehende Bausteine und Umfang

Die vorhandenen Docker-Operatoren, Notification-CLI, MariaDB-Journale und
systemd werden weiterverwendet. Keine neue Bibliothek, Jobplattform oder
Migration. Der zusätzliche Code begrenzt die bestehenden Abläufe und schließt
die belegten Auswahl-/Fairnesslücken. Classifier, OCR, Paketlocks und Stichtag
01.12.2026 00:00 Europe/Berlin bleiben unverändert. DMS, Linuxupdates und
AP12-Graphrotation gehören nicht zu diesem Paket.

## Fester Hosteinstieg

`deploy/run-automation.py` kennt ausschließlich `inbox`, `corrections`,
`notifications`, `start`, `drain`, `tls` und den lesenden `status`-Weg.
`automation-host.example.json`
enthält absichtlich ungültige Imageplatzhalter. Vor einer nativen Probe müssen
geprüfte unveränderliche Image-IDs und private Pfade eingesetzt werden.
Alle Hostskripte, Profile und sämtliche Elternverzeichnisse müssen Root gehören,
dürfen keine Symlinks und für Gruppe/andere nicht schreibbar sein. Skripte/Profile
sind höchstens 64 KiB groß; Geheimnisdateien können für die bestehende
Containergruppe lesbar sein. Ausführung ausschließlich als Root mit
`python3 -I -B` und absolutem Skriptpfad.

Der Betreiber provisioniert `/run/invoice-importer` und
`/var/lib/invoice-importer` geschützt, üblicherweise 0700. Das flüchtige
Sperrverzeichnis darf während eines laufenden manuellen oder automatischen
Operators nicht entfernt/neu erzeugt werden. Es ist daher kein kurzlebiges
`RuntimeDirectory` eines einzelnen Dienstes. Der persistente Schedulepfad ist
ein eigenes, nur vom Operator verwaltetes JSON mit atomarem Ersatz und fsync.
Keine Weiterverwendung einer kopierten Scheduledatei aus einer anderen Instanz.

Processing verwendet dasselbe geschützte Profil und denselben Hostlock auch im
manuellen `run-processing.py`. Gleichzeitige Starts arbeiten nicht parallel:
ein belegter Lock liefert `deferred`. Automatische Anforderungen werden davor
als höchstens eine Fälligkeit je festem Mode gespeichert. Sind beide fällig,
wechselt die Auswahl den Mode; ein unterbrochener aktiver Mode wird nach
Sperrerwerb wieder fällig. Vorher müssen verwaiste Container mit dem vorhandenen
Processinglabel geklärt sein. Fremde/alte Vorgänge werden nicht automatisch gelöscht.

Eine automatische Ausführung wählt höchstens 50 Kandidaten und bearbeitet
einen endlichen Batch von höchstens 20 Quanten, soweit das gemeinsame Zeitbudget
ausreicht. Beide Hosteinstiege verwenden dieselbe feste Grenze, ohne zusätzliches
Profilfeld. Die normale Einzelanhangmail benötigt ein Quantum für Erkennung/
Ablage und ein weiteres für den Mailabschluss; mehrere schnelle Quanten dürfen
daher im selben Lauf erfolgen. Nach Fortschritt sortiert das Journal die Mail hinter
bisher unbearbeitete Kandidaten. Mode-, Lease-, Freigabe- und Retryregeln bleiben
wirksam. Inbox-/Korrekturfälligkeiten sind Gelegenheiten und keine Zusage, dass
eine große Mail innerhalb des Timerintervalls vollständig abgeschlossen wird.

Die gemeinsame monotone Hostfrist beträgt 780 s, einschließlich Auswahl und
Cleanupreserve. Ein neues Quantum beginnt nur mit mindestens 540 s Restzeit;
seine Frist beträgt höchstens 500 s. Jeder Kindaufruf reserviert darin 35 s für
seinen exakten Containercleanup; der begrenzte Clientprozess-Reap ist Teil des
jeweils übergebenen Zeitbudgets. Der manuelle Operator unterliegt ebenfalls der
780-s-Gesamtfrist. Ein Timeout liefert keine erneute Wirkungsfreigabe. Journale,
Eigentümer und ungewisse Wirkungen bleiben maßgeblich. Fehlgeschlagener Cleanup
oder ein alter Container blockiert weitere Arbeit bis zur Betreiberklärung.

Bei einer sicher abgelehnten Graphlese mit 429 bleibt das unberührte Journal
offen. Retry-After wird nicht verkürzt; ohne verwertbare Grenze gelten 900 s,
mindestens 300 s. Die Hostqueue übernimmt die Rückmeldung als gemeinsame
Sperrzeit beider automatischer Processingmodes. Ein ausbleibender Folgetick
startet keine Hintergrundwiederholung im beendeten Operator.

## CIFS vor Bind und Start

Vor jedem Processingkind öffnet der Host den Importpfad komponentenweise ohne
Symlinkverfolgung und prüft seine Mount-ID, Geräte-/Inodeidentität, CIFSquelle,
Schreibbarkeit und strikten/ungepufferten Cache. Docker bindet den regulären
geprüften Fstab-Pfad; ein Host-proc-FD als Bindquelle wird auf der Ziel-VM von
runc abgelehnt und wird nicht mehr verwendet. Vor Create und vor Start werden
aktueller Pfad und gehaltener Deskriptor erneut verglichen. Der Deskriptor bleibt
bis nach dem Containercleanup offen. Sein Geräte-/Inodepaar wird als zwei feste
Pflichtargumente an jeden Worker übergeben, ohne neues Profilfeld. Der Consumer
öffnet sein tatsächliches `CifsFiles`, prüft unmittelbar nochmals dessen Guard
und vergleicht Geräte-/Inodewerte vor `operator_client` und Servicearbeit.
Fehlende, unvollständige, ungültige oder abweichende Werte erlauben keinen
Kompatibilitäts-Bypass. Die vorhandenen CIFS-/Quellen-/Options-, FD-/Root- und
Publikationsprüfungen bleiben unverändert. Ein lokales Ersatzverzeichnis
scheitert vor Graph und Publikation; es wird kein Importroot erzeugt.

Der normale Bind und die Vergleichbarkeit von Host-/Consumergerät und Inode
sind auf der Ziel-VM als reine Metadatenprobe belegt. Der feste neue
Consumer-Guard ist separat in sechs nativen positiven/negativen Fällen geprüft.
Kein neuer Schreib-/Durchsatznachweis aus diesem Transportfix; die bereits
bestandenen SQLprüfungen werden dafür nicht pauschal wiederholt.

## Begrenzte automatische Notifications

Der CLIbefehl `automatic` umfasst Plan/Beobachtung, Auswahl, höchstens einen
Versand und getrennten dauerhaften Statusabgleich innerhalb desselben beim
CLIeintritt erzeugten 80-s-Budgets. Das Budget wird zwischen Phasen nicht
erneuert. Die Hosthülle begrenzt Vorprüfung, CLI und exakten Cleanup zusammen
auf 95 s; sie kann einen langsamen CLIlauf früher beenden. Ein früher Abbruch
erteilt keine Versandwiederholung.

Vor LIMIT ausgeschlossen sind Testmails aller Akteure, alte Konfigversionen,
fehlende Payloads, nicht fällige/veraltete Slots, `not_before` und lebende Owner.
Zulässig sind nur certificate/daily/weekly/errors/outage/recovery. Dieselbe
Meldungsartenprüfung erfolgt vor dem Versand erneut für alle ausgewählten Keys.
Auch das bestehende `dispatch --limit 1..5` ist damit auf automatische Arten
begrenzt. Ein ausdrücklich benannter `send --slot-key` bleibt der manuelle
Einzelweg für einen Test. Keine zusätzliche echte Testmail ist hiermit beauftragt.
Reservierung, gemeinsame Quote, 429 und `unknown` behalten die bestehenden Regeln.

Die Hosthülle bindet ausschließlich Graphkonfiguration/-credential, DBpasswort
und unabhängigen Notificationkey schreibgeschützt. Kein API-Konfigkey, LDAP,
SMB-, TLSschlüssel oder APIservice-Vererbung. `PUBLIC_ORIGIN` stammt aus dem
geschützten Hostprofil. Die Meldung benötigt keinen erreichbaren Importmount.
Ein eigener Hostlock und die Prüfung älterer Notificationcontainer verhindern
überlappende automatische Hüllen. Der ausdrückliche AP07-Einzelweg nutzt weiter
die gemeinsamen DBreservierungen/Quoten. Es gibt keine neue HTTPsteuerroute.

## Start, Zeitplanung und Drain – Paket B

Die Beispiele installieren oder aktivieren nichts. Root übernimmt die fünf
geschützten Nachbarskripte `run-automation.py`, `run-processing.py`,
`host-runtime.py`, `operations-host.py` sowie die unveränderte Datei
`backend/app/operations_status.py` unter dem Hostnamen `operations-status.py`,
bindet die tatsächlichen lokalen Image-IDs/Instanz/Origin und
passt die Mountpfade in den Vorlagen an. `runtime-host.example.json` benennt
bereits vorhandene DB/API/Nginx-Container; Boot erstellt keine neuen Container
und führt weder Composebuild/Pull noch Migration aus. Eine kanonische, geprüfte
Composebereitstellung mit passenden Images bleibt der getrennte Rootschritt.

`invoice-importer.service` startet ausschließlich diese vorhandenen gepinnten
Container-IDs: DB healthy → API healthy → Nginx running → vertrauenswürdiges
HTTPS mit lokalem Leaf-Fingerprint und `/api/health/ready`, journal/Instanzgleich.
240s Gesamtfrist. Die Portalprüfung liest den lokalen TLSbaum, keinen SSLquell-
oder Importmount. Innerhalb der ursprünglichen Frist werden vorübergehende
Verbindungs-/Bereitschaftsfehler nur lesend erneut geprüft; die erste HTTPSantwort
ist kein Endentscheid. Notifications benötigen anschließend DBbereitschaft und
können einen späteren APIausfall weiter beobachten. Processing verlangt zusätzlich
Portal-/Instanzbereitschaft und seinen eigenen geprüften Importmount; TLS hat
eine getrennte RO-Quellmountbedingung. `RequiresMountsFor` ersetzt nie die
zusätzliche CIFSidentitätsprüfung. Kein DMSgate.

`invoice-importer.tmpfiles.example` wird von Root als passende tmpfiles-Konfiguration
bereitgestellt. Sie erzeugt die geschützten Host-, Ergebnis- und Statusverzeichnisse; kein
kurzlebiges RuntimeDirectory. Die Timer bieten Inbox5min, Korrekturen15min,
Notifications1min und HTTPSprüfung1h, jeweils ausdrücklich Europe/Berlin auf
unverändertem UTC-Host. `Persistent=true` bietet eine Nachholmöglichkeit statt
einer Wiederholung aller verpassten Perioden. Die vorhandene Processingqueue
fasst weitere Fälligkeiten weiterhin je Mode zusammen. Selbstüberlappung wird
von systemd, modesübergreifende/manuelle Überlappung von Hostflock verhindert.

Die Worker hängen von der Startunit ab und werden mit ihr gestoppt. Processing
hat780s Start-/45s Stopfrist, Notifications95s/15s, TLS180s/45s. Die Hosthülle
reicht die ursprüngliche Frist einschließlich Vorprüfungen weiter; keine neue
Frist nach der Bereitschaftsprüfung. Stop/Cleanup entfernt nur eigene Helfer.

Deaktivierung bedeutet Timer und aktive Worker stoppen, Drain und getrenntes
Rücklesen. Der Drainweg benötigt keine intakten Runtime-/TLS-/Secretprofile.
Er setzt zuerst eine geschützte Sperrdatei und wartet begrenzt auf Lifecycle-,
Processing- und Notificationsperre. Aktive manuelle Vorgänge oder alte
markierte Container verhindern einen bestätigten Drain; die Sperrdatei bleibt.
Keine automatische Fremdbereinigung. Ein erfolgreicher Start öffnet die Sperre
erst nach Bereitschaft und überschreibt keinen währenddessen neu eingegangenen
Drainauftrag. Die Portalcontainer bleiben beim Drain erreichbar; eine Abschaltung
der DB/API/Webcontainer wäre ein eigener Betreiberauftrag. Root ersetzt/stoppt
auch den bestehenden manuellen Operator passend, damit derselbe Sperrweg gilt.

## Externe HTTPSübernahme – Paket B

`tls-source.example.json` benennt die eigene RO-CIFSquelle und eine geschützte
Passwortdatei. Der Betreiber bestätigt das Quellformat/Passwort; kein Erraten.
Für das vorgefundene RC2-PFX-Format wird `-legacy` ausschließlich beim PKCS12lesen
verwendet, keine globale Provider-/Cipheränderung. Eine bestätigte leere
Passwortdatei wird nur in privatem Staging als leere Passwortzeile normalisiert;
der Prozess erhält den Dateipfad, keinen Passwortwert. Vorhandenes OpenSSL statt
neuer Kryptobibliothek: [PKCS12](https://docs.openssl.org/3.5/man1/openssl-pkcs12/),
[Server-/Hostnameprüfung](https://docs.openssl.org/3.0/man1/openssl-verification-options/).

Höchstens32 reguläre geschützte PFXdateien mit je höchstens1MiB, keine Symlinks.
Mountquelle/-ID/Gerät/Inode, RO und sichere Cacheoptionen werden am gehaltenen
Directory-FD geprüft. Zwei identische Inhaltslesungen und unveränderte
Dateiidentität bilden den privaten Snapshot; vor Übernahme wird er erneut mit
der Quelle verglichen. Auswahl nach validiertem Zertifikatinhalt, nicht Dateiname:
genau ein privater Schlüssel, passender öffentlicher Schlüssel des Leafs,
geordnete vollständige Kette mit2–8 Zertifikaten, Systemtrust/sslserver/Hostname,
aktuelle Gültigkeit und mehr als1h Restgültigkeit. Keine Rückstufung auf älteres
Material. Gleicher Leaf ist No-op mit tatsächlichem Peer-/Bereitschaftsrücklesen.

Neuer privater Release, abschließend root:10002/0750 und vier Dateien0440:
cert/chain/fullchain/privkey.pem. Kein API-/Graphkeywechsel. Der gesamte TLSbaum
bleibt Nginx RO gebunden. Vor Wechsel werden tatsächliches Nginximage, UID10002,
RO-Wurzel und exakter TLSmount sowie Container-ID geprüft. Relativer current-Link
wird atomar gewechselt; nginx-test vor gezieltem Reload genau dieser ID.
Erfolg erst nach vertrauenswürdigem HTTPS, exaktem Peerfingerprint und identischer
bereiter Instanz. Ergebnis enthält den bestätigten Quellsnapshot-Hash.
Vorwärts- und Rückweg warten innerhalb ihrer bereits übergebenen monotonen
Fristen auf diese Bestätigung. Ein noch alter Peer nach Reload ist kein sofortiger
Endfehler. Wiederholt werden ausschließlich neue HTTPSlesungen, kein Linkwechsel,
Reload oder Graphaufruf. Fristablauf bleibt Fehler beziehungsweise Pendingbeleg.

Ein rootprivater `.tls-pending.json`-Beleg entsteht vor dem Linkwechsel. Bei
Testfehler wird der alte Link ohne Reload wiederhergestellt; bei Reload-/Livefehler
folgen alter Link, Test, Reload und alter Peerreadback. Die45s Rückwegreserve
ist von der135s Vorwärtsphase ausgenommen. Alter Release/Quelle bleiben erhalten.
Nur bestätigter Erfolg/Rückweg entfernt den Vorgangsbeleg. Unterbrechung oder
unbestätigter Rückweg blockieren den nächsten TLSwechsel bis Root Link, Release,
genannte Container-ID und tatsächlichen Peer abgeglichen hat. Keine automatische
Löschung dieses Belegs und keine pauschale Release-/Quellenbereinigung.

## Frischer lesender Betriebsstatus – Paket C

Bestehendes systemd, Dockerinspect und die bereits geprüften Mount-/HTTPS-
Lesebausteine bleiben die Quellen. Kein neuer Dienstanbieter, Scheduler,
Socketzugang der API oder zusätzliches Paket. Der Rootcollector
`run-automation.py status --profile /etc/invoice-importer/status-host.json`
hat eine ursprüngliche 15s-Frist. Das feste Profil benennt Quellcommit,
Deployment-UUID, vorhandenes Automationprofil und zwei getrennte Verzeichnisse.
Die Beispielwerte sind absichtlich ungültig. Quellcommit und neue Deployment-
UUID müssen exakt mit der APIkonfiguration derselben Bereitstellung stimmen;
Instanz kommt aus dem bestehenden Runtimeprofil, Boot-ID aus dem laufenden Kernel.

`invoice-status.service/timer.example` bietet eine lesende Gelegenheit pro
Berlinminute auf Sekunde 20. Der Collector ist unabhängig von Hauptdienst/Workertimern und
läuft deshalb auch bei pausierten Jobs oder fehlgeschlagenem Start. Er ruft
keinen Start, Enable, Reload, Graphabruf oder Versand auf. Er liest ausschließlich
die neun festen Start-/Timer-/Workerunits, validierte Containerrollen, tatsächliche
HTTPSbereitschaft, Mountmetadaten, Drainsperre, bestehendes flock und Queue-/TLS-
Sperrmetadaten. Die echten Timerkalender und Trigger müssen zum vorgesehenen
5-/15-/1-Minuten-/Stundenplan passen; bloße Konfiguration ist keine Aktivität.

Die bestehenden Operatoren hinterlegen nach ihrem Ergebnis nur eine erlaubte
kleine Ergebnisquittung pro festem Mode. Quelle/Deployment/Instanz/Boot, Anfang/
Ende und ok/deferred/failed/unknown werden übernommen; keine freien Ergebnis-
texte, Mail-/Empfänger-/Dateidaten oder Geheimnisse. Das Hostmodul wird im
dynamischen Importweg ausdrücklich übergeben. Ein fehlgeschlagener Statusbeleg
ändert kein bereits festgestelltes Verarbeitungsergebnis und erlaubt keinen
erneuten Wirkungsversuch. Fehlende oder nicht zum jüngeren Unitlauf passende
Quittung wird unbekannt; ohne passende Quittung bleibt ein bekannt
fehlgeschlagener Unitlauf Fehler.

Quittungen liegen nur unter root:root/0700
`/var/lib/invoice-importer/results`. Ausschließlich die erlaubte Statusprojektion
liegt unter root:10001/0750 `/var/lib/invoice-importer/status`, Datei
`status.json` root:10001/0440. Vollständige temporäre Datei, Rechte, Datei-fsync,
atomarer Ersatz und Verzeichnis-fsync; kein nachträgliches Beschreiben der
bereits veröffentlichten Datei. Der Collector hat eine eigene Sperre und
bereinigt ausschließlich seine eigene temporäre Datei. Kein Journal-/Schemawechsel.

`compose.operations.yaml` ergänzt nur API mit diesem eigenen Verzeichnis als
RO-Bind nach `/run/importer/operations`, `create_host_path=false` sowie
`OPERATIONS_SOURCE_COMMIT` und `OPERATIONS_DEPLOYMENT_ID`. Keine Rootprofile,
Quittungsablage, Docker-/systemd-Sockets oder neuen Secrets in der API.
Root prüft die tatsächliche Dateigrenze und alle fünf installierten Peers vor
Bereitstellung. API-/Webimage müssen denselben geprüften C-Stand enthalten;
die minimale externe Notification-CLI erhält keinen Statusmount.

`GET /api/operations/status` verwendet die bestehende AD-/Sitzungsgrenze für
beide Rollen und `Cache-Control: no-store`. Keine Steuerroute. Der Leser öffnet
ohne Symlinkfolge/nichtblockierend, verlangt reguläre Datei, Root/GID10001,
0440, genau einen Link und höchstens32KiB. Striktes Schema1, nur feste Felder,
keine doppelten JSONkeys. Quelle, Deployment, DBinstanz und aktueller Boot
müssen passen. Mehr als180s alt oder mehr als30s zukünftig ist unbekannt;
fehlend, unlesbar, ungültig und ungebunden ebenfalls. Fremde Rohdaten werden
dann nicht als aktuelle Metadaten zurückgegeben.

Die Projektion trennt eingerichtet, Timer aktiv, läuft, zurückgestellt, letzte
Quittung, nächste Startgelegenheit, Start-/DB-/Portalbereitschaft und Mounts.
`active` bedeutet belegter aktiver Zeitplan mit passenden Voraussetzungen;
`paused` belegter inaktiver Timer; `degraded` aktiver Timer mit Einschränkung;
`unknown` fehlender belastbarer Aktivitätsnachweis. Aktive Notifications
benötigen DBbereitschaft, keinen verfügbaren Importmount oder Portalpeer.
Die bestehende Notificationkonfiguration liefert aus derselben Quelle
`automatic_schedule_active: boolean|null` und `automatic_schedule_state`.
Die externe CLI ohne Statusbindung meldet null/unknown.

Übersicht, Sidebar, Footer und Benachrichtigungsanzeige teilen dieselbe geprüfte
Projektion. Der Login behauptet keinen Betriebszustand. Poll alle30s, begrenzte
Anfrage und monotone Ablaufzeit einschließlich Anfragezeit; Fetchfehler,
Ablauf oder Rückkehr zu einer abgelaufenen Ansicht entfernen alte Aktivität.
Die Oberfläche bietet keinen Jobsteuerknopf. Zeitpläne bleiben ausdrücklich
Startgelegenheiten; Stichtag01.12.2026 00:00 Europe/Berlin unverändert.

## Tatsächlicher Bereitstellungs- und Aktivierungsstand

Die bereitgestellte C-Quelle ist getrennt gegen API/Web/Processing/Notification
gebunden. Base-Apply ersetzt API/Web, erhält DBcontainer-ID/Startzeit, DBzeilen,
Konfigurationshashes, Schema 007 und Instanz. HTTPS ready/journal bestätigt.
Die bestehende PDF-Vorschau verwendet lesende Graphabrufe und privates Tmpfs mit 128 MiB.
Native Statusdateigrenze und isolierte C-GUIprüfung sind bestanden; die drei
Desktopgruppen/Mobile 390 × 844 verwenden tatsächliche Webassets und synthetische
API-/Rollenfixtures. Daraus keine neue tatsächliche Kunden-/AD-Anmeldung ableiten.

Die reale HTTPSübernahme changed=true ist mit öffentlichem Peerreadback bestätigt,
anschließende Prüfung changed=false bestätigt den No-op. Peer gültig bis 12.02.2027.
Instanz, Schema und Konfiguration sind erhalten. Die Notificationvorprüfung
bestätigt gespeicherte Version 1/drei privat verwaltete Empfänger, Tages-/
Wochenvorschauen mit 0 Zählwerten und den unveränderten ursprünglichen Testslot
accepted/Reservierung 1/HTTP 202; keine neue Testmail aus dem Vorlauf.

Der minimale Dienst `notification` auf dem aktuellen C-Compose verwendet drei
nur lesbare Volumes für Graphkonfiguration, Graphcredential und Notificationkey sowie das
Datenbank-Secret: vier benötigte Dateibindungen. Profil `notification-operator` aktivieren;
beispielsweise mit dem bereits geprüften aktuellen C-Compose:

```sh
docker compose -p invoice-importer -f "$REVIEWED_C_COMPOSE" --profile notification-operator \
  run --rm --no-deps notification plan
docker compose -p invoice-importer -f "$REVIEWED_C_COMPOSE" --profile notification-operator \
  run --rm --no-deps notification preview --slot-key "$EXISTING_SLOT_KEY"
```

`plan` beobachtet und persistiert ggf. Absichten, `preview` zeigt den gespeicherten
Payload eines vorhandenen Slots. Beide erzeugen keinen Mail-POST. Der Hostmodus
`notifications` und CLI `automatic` können dagegen einen fälligen Versand ausführen.
Die externe minimale CLI hat keine Hoststatusbindung und meldet null/unknown;
den laufenden Zeitplan aus der gebundenen Host-/APIprojektion lesen.

Aktivierung am 16.11.2026 19:44:23 Europe/Berlin: `invoice-importer.service`
und die fünf Timer `invoice-processing-inbox.timer`,
`invoice-processing-corrections.timer`, `invoice-notifications.timer`,
`invoice-tls.timer`, `invoice-status.timer` enabled/active. Frische Statusprojektion
active separat bestätigt, Statuspublikation jede Minute. Geplante Korrekturen um 19:45
erfolgreich mit 0 Quanten / 0 remaining; Eingang um 19:45 wegen gemeinsamer Sperre deferred,
nächste Gelegenheit um 19:50 erfolgreich mit 0 Quanten / 0 remaining. Queuefairness damit
im normalen Betrieb beobachtet; kein Rechnungsimport aus dem Leerlauf abgeleitet.
Notificationjobs um 19:45/19:46 bestätigen je einmal Tages-/Wochenbericht mit HTTP 202;
weitere Läufe ohne zusätzliche Sendung, ursprünglicher Testslot accepted/1/202
erhalten, keine unbekannten/offenen Postwirkungen. Graphannahme ist keine
Zustellbestätigung. Preboot-Gate um 19:50:28: alle Worker inaktiv, keine
Operationscontainer, drei eindeutig angenommene Slots. TLSstundentimer ist
enabled/active; erster geplanter Stundenlauf um 20:00 bestätigt changed=false,
gleicher Peer und status_recorded=true. Die davor erfolgreich ausgeführte
reale TLSunit/No-op bleibt ein eigener Nachweis.

Kontrollierter Reboot mit neuer Boot-ID, gleichen API-/Web-/DBcontainer-IDs und
Images, gesundem HTTPS, beiden CIFSmounts und erhaltenen Schema-/Instanz-/
Konfigurations-/Testslotbindungen erfolgt. Weitere Nachboot-Inboxläufe
0 Quanten / 0 remaining und drei eindeutige Mailbelege accepted/ein Versuch/202 bestätigt.
Eine Aufnahme während eines neuen Notificationlaufs verwirft konservativ den
vorigen Abschluss als Ergebnis des neuen Laufs und zeigt unknown/degraded.
Der gemeinsame Minutentakt konnte wiederholt genau diese laufende Phase erfassen.
Nach dem Reboot wurde deshalb am 16.11.2026 um 20:15:08 Europe/Berlin separat der
persistente Drop-in `10-phase.conf` angewandt. Effektiv genau ein Kalender
`*-*-* *:*:20 Europe/Berlin`, Ziel invoice-status.service, Timer active/enabled.
Die öffentliche Timerbeispielzeile verwendet ebenfalls Sekunde 20. Der Minutenabstand,
Frische-/Ergebnisguards und alle Anwendungs-/Hostskript-/Imagepins bleiben erhalten.
Längere oder ungewisse Jobs bleiben entsprechend eingeschränkt. Drei
aufeinanderfolgende automatische Kontrollzyklen am 16.11.2026 um 20:16:21,
20:17:21 und 20:18:21 Europe/Berlin bestätigen jeweils active, den seit 15 Sekunden
abgeschlossenen Notificationlauf und running=false. Kein manueller Collector
wurde gestartet. Boot-/Quellbindung, der einzige Drop-in, Dienstziel und übrige
Wiederanlaufprüfungen sind bestätigt. Dieser Nachweis gilt für den nach dem
belegten Reboot separat gesetzten Versatz; er enthält keinen zweiten Reboot.

## Technischer Abschluss und Nachweisgrenzen

Paket A ist lokal mit synthetischer SQLite, echten Notificationverschlüsselungs-
und Zertifikatsbausteinen sowie Transport-/Hostdoubles gezielt geprüft. Die
Nachweise umfassen Auswahl vor Limits 1/5, erneute Testabwehr, expliziten
Einzeltest, gemeinsame Frist, verlorene Antworten, mehr als 50 fällige Mails,
Modewechsel, Abbruchfortsetzung und bekannte 429-Leseablehnung. Keine Aussage
über native Linuxfristen, tatsächliches flock, Docker oder CIFS daraus ableiten.

Der feste Quellreview, gezielte native Rootprüfungen und die Bereitstellung
sind getrennt belegt. Processing verwendet den eingefrorenen Classifier und
dieselbe C-Backendquelle wie API/Notification. Alte Pins und Schema 007 für
den Rückweg bleiben erhalten. Paket B liefert außerdem lokale
Fehler-/Ablaufprüfungen mit ausdrücklichen OpenSSL-/Docker-/Hostdoubles.
Die separat gemeldeten nativen A-/Consumer-/TLSprüfungen ersetzen keine C-
Abnahme. C hat gezielte lokale Schema-/Frische-/Import-/Host-/ADrollen- und
Frontendprüfungen sowie Typprüfung/Webbuild. Native Dateigrenzen, Hostintegration,
C-GUI und Bereitstellung sind separat geprüft. Wiederanlaufnachweise behalten
ihren konkret belegten Umfang. Mit den drei bestandenen automatischen
Statuskontrollzyklen sind die technische Serverabnahme und AP08 im vereinbarten
Umfang abgeschlossen. Ein vollständiger VMrestore ist nicht nachgewiesen;
DMS sowie AP09/10/11 und die AP12-Umsetzung gehören nicht zu diesem Abschluss.
AP03 bleibt eingefroren, seine fachlichen Restfälle bleiben offen. Unitbeispiele
bleiben Vorlagen für geprüfte Betreiberinstallationen.
