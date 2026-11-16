# AP08 – Betriebsübergang

Stand: 16. November 2026. AP08 ist zur Umsetzung freigegeben. Paket A liefert
die Laufzeitbasis zur Quellprüfung; es ist noch keine Hostbereitstellung oder
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
höchstens ein Quantum. Nach Fortschritt sortiert das Journal die Mail hinter
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
Schreibbarkeit und strikten/ungepufferten Cache. Docker erhält den gehaltenen
Hostdeskriptorpfad `/proc/<Hostpid>/fd/<fd>`. Vor Create und vor Start werden
aktueller Pfad und gehaltener Deskriptor erneut verglichen. Der Deskriptor bleibt
bis nach dem Containercleanup offen. Die vorhandene CIFSprüfung im Consumer
bleibt zusätzlich bestehen. Ein lokales Ersatzverzeichnis erfüllt diese Prüfung
nicht. Die tatsächliche Bindwirkung und Austausch-/Unmountfälle benötigen den
nativen Rootnachweis; Windows-Doubles belegen sie nicht.

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
Alte Pins und Schema 007 für den Rückweg erhalten. Noch ausstehend sind die
Units/Timer samt Berlin-Kalender, Startbereitschaft, externe HTTPSübernahme,
frischer lesender Betriebsstatus einschließlich Oberfläche, isolierter
Wiederanlauf und kontrollierte Aktivierung mit getrenntem Rücklesen.
Die bisherigen Processing-Unitbeispiele sind kein AP08-Installationsauftrag.
