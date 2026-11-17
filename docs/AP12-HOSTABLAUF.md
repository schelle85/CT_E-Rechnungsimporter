# AP12 – ausführbarer Hostablauf C3b

Quellstand, noch nicht bereitgestellt oder vollständig nativ abgenommen.
Kundenbetrieb bleibt AP08 auf Schema007. C2a-UID10001-Integration und C2B-R1-
POSIXfrist sind separat unabhängig nativ abgeschlossen.

`deploy/run-rotation.py` bietet bootstrap/run/resume/rollback sowie die festen
[Tages-/Gelegenheitsläufe](AP12-AUTOMATIK.md) und die ausdrückliche
[Zertifikatszuordnung](AP12-OWNERSHIP.md) als Root über geschützte feste Profile.
`app.rotation_worker` verarbeitet
begrenztes privates stdin, eigene DBanforderungen und die bestehenden Rootjournale.
Die API erhält weder Root-/Dockerzugang noch private Journal-/Credentialschreibrechte.

Der Ablauf hält die Rotationssperre, schreibt zuerst blocked und setzt den kurzen
Drain. Danach Lifecycle → Processing → Notification → Graph-EX. Vor Materialwechsel
werden tatsächlicher Containerzustand, cgroup.procs und cgroup.events/populated
geprüft; freier flock allein reicht nicht. Voraussetzung ist systemd/cgroupv2.
Unbekannte laufende Verbraucher derselben Credentialbindung blockieren.
Nur eigene vorab dauerhaft benannte Jobs werden gezielt abgeglichen/entfernt.

Registrierung nutzt unverändert den einmaligen B-Auftrag. Kandidatenprobe schreibt
keinen Produktionsproof. Nach dauerhafter Aktivierungsabsicht/Altsicherung werden
dieselben Kandidatenbytes atomar eingesetzt und ausschließlich API über geschützte
Composequellen mit explizitem Imagepin neu erstellt. DB/nginx/TLS bleiben erhalten.
API/Processing/Notification bestätigen Material und frischen GET, Processing auch
die vorhandene CIFSbindung. Danach eigener Abschlussgrant, passender AP07-Proof,
versiegeltes Rootjournal und Freigabe; EX bleibt bis zum Nachlauf gehalten.
Die neue API-ID steht ausschließlich im privaten Beleg; Runtimeprofil bleibt name/image.

Vor Compose wird eine dauerhafte Austauschabsicht mit ursprünglicher API-ID,
Zielimage, Quell-/Instanzbindung, API-Name, Materialhash, eigener Austauschkennung
und DB-/nginx-IDs geschrieben. Neue Container müssen diese Kennung und sämtliche
Verbraucherbindungen erfüllen. Eine fehlende API ist ausschließlich über diesen
Beleg und bestätigte Ruhe ihrer bekannten Cgroups zulässig. Eine bereits passend
erzeugte API wird nach Antwortverlust übernommen; das Runtimeprofil wird danach
vervollständigt. Ein Rückweg mit anderem Material erhält eine neue Austauschabsicht,
während der bisherige Beleg unverändert archiviert wird.

bootstrap stattet bestehende Verbraucher bei unverändertem aktuellen Key aus und
registriert keinen Schlüssel. resume öffnet keine unerklärte Sperre. Unklarer
Proof wird zuerst sperrend aus der DB gegen ursprüngliche Revision/Fingerprint/
Scope/Zeit gelesen. Vor neuer Prüfung wird der ursprüngliche vollständige
Checkpoint einschließlich Seal/Absicht archiviert. Bei Fehlern nur über gültiges
gesichertes Altmaterial, erneut erstellte API und bestätigte alte Verbraucher/Proofs
zurückkehren; unbestätigter Rückweg bleibt geschlossen.

Dies gilt auch für den ausdrücklichen Root-Rückweg. Unbekannte Proofwirkung muss
zur ursprünglichen Absicht passen; bestätigte Proofs bleiben mit vollständigem Seal
archiviert. Ein nach Archivierung verlorener Fortschritt verwendet dasselbe Archiv
erneut. Vorbereitete Aufträge wechseln erst nach Material-/Ruhebeleg in den aktuellen
Boot. Ein veröffentlichter Rückweg ohne aktiven SQLauftrag wird anhand des exakten
Gate-/SQL-/Journalabschlusses übernommen und mit neuen Verbraucher-/Proofbelegen
bestätigt. Dabei bleibt dieselbe ursprüngliche Anforderung erhalten.

Alte/neue bewusste Pause bleibt erhalten. Nur eigener Drain wird per Identität
gelöst. Start bewahrt vorhandene Drainmarker, startet zunächst die vorhandene
Datenbank und führt dann den begrenzten Wiederabgleich aus. Erst danach verlangt
er die vollständig bereite API. Beim API-Austausch wird der vorhandene nginx nach
Bestätigung seiner Identität gestartet oder neu geladen, damit seine bestehende
API-Namensauflösung aktuell ist; TLSdateien werden nicht ersetzt. Die abschließende
HTTPSprüfung bleibt verbindlich. Auch die Wiederaufnahme eines unklaren API-Execjobs
stoppt erst innerhalb Lifecycle → Processing → Notification; sein Abschlussbeleg
wird nach bestätigter Cgroupruhe unter Graph-EX entfernt. Bereits vollständig
gesperrte Rückwegaufrufer erwerben dieselben Sperren nicht erneut.
Der Rotationscontroller aktiviert keine Timer/Hauptdienste.

Betreiberinstallation aus festem Quellarchiv: bestehende geschützte AP08-Hostpeers
plus run-rotation.py/graph-access-host.py und eine geschützte Kopie von
backend/app/graph_access.py als graph-access-model.py im selben Hostordner.
Profile: rotation-host.example.json und graph-access-host.example.json.
Journalroot0700; Binding/Key/Gate root:10001 nur lesbar für Verbraucher.
Compose-/Runtime-/Automation-/Graphbindungen müssen dieselbe Quelle/Instanz und
gepinnten Images bezeichnen. Schema008 und Metadatendateien vor bootstrap
kontrolliert bereitstellen. Keine privaten Betriebswerte in öffentliche Beispiele.

Gezielte lokale Datei-/Kryptografie-/SQLitefälle mit ausdrücklichen Docker-/OS-/
SDK-/Probe-Doubles prüfen Wechsel, gültigen Rückweg, Resume nach Dateiersatz,
verlorene Proofantwort, Bootstrap ohne addKey und alte/neue Pause. Weitere Fälle
prüfen Originalauftrag, Commit vor Veröffentlichung, Sperrfolge und tatsächliche
Ruhekriterien anhand synthetischer OSdaten. Das ist kein nativer Hostnachweis.
Der konkrete isolierte Nativ-Einstieg folgt separat; sichere eigene Altkey-
Bereinigung, Reiter und feste Automatik/Frischeprojektion folgen im übrigen AP12.
