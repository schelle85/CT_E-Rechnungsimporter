# AP08 – Betriebsübergang

Stand: 16. November 2026. AP08 ist zur Umsetzung freigegeben. Paket A liefert
die Laufzeitbasis; Paket B ergänzt Start-/Timervorlagen und HTTPSübernahme zur
Quellprüfung. Es ist noch keine Hostbereitstellung oder
Aktivierungsabnahme. Der Kundenbetrieb bleibt beim abgenommenen AP07-Stand,
Schema 007 und inaktiver Import-/Korrektur-/Benachrichtigungsautomatik.

## Bestehende Bausteine und Umfang

Die vorhandenen Docker-Operatoren, Notification-CLI, MariaDB-Journale und
systemd werden weiterverwendet. Keine neue Bibliothek, Jobplattform oder
Migration. Der zusätzliche Code begrenzt die bestehenden Abläufe und schließt
die belegten Auswahl-/Fairnesslücken. Classifier, OCR, Paketlocks und Stichtag
01.12.2026 00:00 Europe/Berlin bleiben unverändert. DMS, Linuxupdates und
AP12-Graphrotation gehören nicht zu diesem Paket.

## Fester Hosteinstieg

`deploy/run-automation.py` kennt ausschließlich `inbox`, `corrections` und
`notifications` mit einem geschützten Profil. `automation-host.example.json`
enthält absichtlich ungültige Imageplatzhalter. Vor einer nativen Probe müssen
geprüfte unveränderliche Image-IDs und private Pfade eingesetzt werden.
Beide Hostskripte, Profile und sämtliche Elternverzeichnisse müssen Root gehören,
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
Consumer-Guard benötigt noch den schmalen nativen positiven/negativen Nachweis.
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

Die Beispiele installieren oder aktivieren nichts. Root übernimmt die drei
geschützten Nachbarskripte `run-automation.py`, `run-processing.py` und
`host-runtime.py`, bindet die tatsächlichen lokalen Image-IDs/Instanz/Origin und
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
bereitgestellt. Sie erzeugt die beiden geschützten Hostverzeichnisse; kein
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

## Nachweis und nächste Lieferteile

Paket A ist lokal mit synthetischer SQLite, echten Notificationverschlüsselungs-
und Zertifikatsbausteinen sowie Transport-/Hostdoubles gezielt geprüft. Die
Nachweise umfassen Auswahl vor Limits 1/5, erneute Testabwehr, expliziten
Einzeltest, gemeinsame Frist, verlorene Antworten, mehr als 50 fällige Mails,
Modewechsel, Abbruchfortsetzung und bekannte 429-Leseablehnung. Keine Aussage
über native Linuxfristen, tatsächliches flock, Docker oder CIFS daraus ableiten.

Nach festem Quellreview folgen gezielte native Rootprüfungen. Neues Backend
muss in API/Notification und dem separaten Processingconsumer ankommen;
Processing wird mit dem eingefrorenen Classifier und neuem Backend gebaut.
Alte Pins und Schema 007 für den Rückweg erhalten. Paket B liefert lokale
Fehler-/Ablaufprüfungen mit ausdrücklichen OpenSSL-/Docker-/Hostdoubles, keine
native Krypto-, Mount-, Frist- oder systemd-Abnahme. Root prüft die tatsächlichen
Kalender/Units, Starts, Mounts, neuen Leaf und Rückweg separat. Zugehörige
Wiederanlaufnachweise führt Root getrennt. Frischer lesender Betriebsstatus samt
Oberfläche folgt C; kontrollierte Aktivierung/Readbacks bleiben ausstehend.
Alle Unitbeispiele bleiben bis zur passenden Prüfung ohne Installationsauftrag.
