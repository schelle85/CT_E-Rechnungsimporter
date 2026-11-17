# AP12 – ausführbarer Hostablauf C3b

Quellstand, noch nicht bereitgestellt oder vollständig nativ abgenommen.
Kundenbetrieb bleibt AP08 auf Schema007. C2a-UID10001-Integration und C2B-R1-
POSIXfrist sind separat unabhängig nativ abgeschlossen.

`deploy/run-rotation.py` bietet ausschließlich bootstrap/run/resume/rollback
als Root über geschützte feste Profile. `app.rotation_worker` verarbeitet
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

bootstrap stattet bestehende Verbraucher bei unverändertem aktuellen Key aus und
registriert keinen Schlüssel. resume öffnet keine unerklärte Sperre. Unklarer
Proof wird zuerst sperrend aus der DB gegen ursprüngliche Revision/Fingerprint/
Scope/Zeit gelesen. Vor neuer Prüfung wird der ursprüngliche vollständige
Checkpoint einschließlich Seal/Absicht archiviert. Bei Fehlern nur über gültiges
gesichertes Altmaterial, erneut erstellte API und bestätigte alte Verbraucher/Proofs
zurückkehren; unbestätigter Rückweg bleibt geschlossen.

Alte/neue bewusste Pause bleibt erhalten. Nur eigener Drain wird per Identität
gelöst. Start bewahrt vorhandene Drainmarker und führt anschließend den begrenzten
Wiederabgleich aus. Der Rotationscontroller aktiviert keine Timer/Hauptdienste.

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
