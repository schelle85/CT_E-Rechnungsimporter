# AP07 – begrenzte Betreiberbefehle, Paket B

Paket B ergänzt den vorhandenen Graphadapter um einen begrenzten Notificationweg.
Quell-/Lokalprüfung, native Laufzeitprüfung und Kundeneinrichtung sind getrennte
Schritte. Diese Anleitung erteilt keine Kundenmigration, echte SendMail oder
Timeraktivierung. Bestehenden geprüften Compose-/Image-/DBstand verwenden;
historische Beispielimages sind kein aktueller Kundenstartweg.

## Eigener Schlüssel und minimale Bindungen

Der Betreiber provisioniert einen eigenen zufälligen Fernetkey für Notifications,
unabhängig vom allgemeinen LDAP-Konfigurationskey. Dauerhaft privat speichern,
root-owned, nur für die benötigte Gruppe lesbar, beispielsweise0440/root:10001.
Keine Schlüsselbytes in Git, Image, Kommandoausgabe oder Log.

`NOTIFICATION_KEY_FILE` bezeichnet die RO-Datei im Container. Die CLI lädt keine
LDAPkonfiguration und verwendet weder `Runtime.cipher` noch den allgemeinen
`CONFIG_KEY_FILE`-Loader. Vorhandene LDAPchiffren bleiben unverändert. Fehlender
Notificationkey ergibt einen nicht verfügbaren Notificationdienst.

Das eigene Profil [compose.notification.yaml](../deploy/compose.notification.yaml)
erbt keine APIkonfiguration. Erlaubte Bindungen: DBkennwort, Notificationkey,
bestehende Graphconfig und Graphcredential; nicht geheime DB-/Pfad-/Originwerte.
Kein allgemeiner Konfigurationskey, LDAPbootstrap/-kennwort, HTTPSprivatkey,
SMBroot oder DockerSocket. Kein Neustartmodus/Timer. Image über
`NOTIFICATION_IMAGE` auf den tatsächlich geprüften unveränderlichen Pin setzen.
Effektive Composekonfiguration vor Ausführung gegen diese Liste prüfen.

Ein späterer Senderkindprozess **im APIcontainer** bleibt Teil derselben bereits
genehmigten API-Vertrauensgrenze und teilt deren Dateisystem. Seine Envallowlist
und eigener Notificationkey sind implementiert; daraus keine Dateisystemisolation
vom APIprozess ableiten. Notificationcode liest auch dort keine LDAPdateien.
Zusätzliche API-Keybindung und neue Webpfade werden getrennt in C integriert.

## Einmalige private Erstkonfiguration

Nach geprüftem Schema007 beginnt der Notificationkopf mit version0 und ohne
Empfänger. Private JSON nach dem [synthetischen Beispiel](../deploy/notification-init.example.json)
erstellen; echte Adressen ausschließlich privat eintragen. Der Betreiberbefehl
akzeptiert nur `expected_version:0` und geprüfte Einstellungen, Actor`operator`.
Er legt keine ADidentität oder Kundensitzung an. Wiederholung überschreibt keine
bereits konfigurierte Version.

Für diesen einen Befehl die Datei zusätzlich gezieltRO einbinden, ohne automatische
Hostpfadanlage: [compose.notification-init.yaml](../deploy/compose.notification-init.yaml).
Danach den zusätzlichen Override wieder weglassen. Die folgenden Shellvariablen
stehen für bereits geprüfte private Pfade; keine geheimen Dateiinhalte einsetzen:

```sh
docker compose -f "$REVIEWED_COMPOSE_FILE" -f deploy/compose.notification.yaml \
  -f deploy/compose.notification-init.yaml --profile notification-operator \
  run --rm --no-deps notification configure-init
```

`NOTIFICATION_INITIAL_HOST_FILE` wird nur von diesem Override benötigt. Im
Container ist ausschließlich `/run/importer/notification-init.json` als Initpfad
zulässig. `--no-deps` startet keine Migration oder andere Dienste. Ergebnis enthält
Version, Empfängeranzahl und Settingshash; keine ADanmeldung oder SendMail.

## Fester Testauftrag, Vorschau und getrenntes Senden

Zuerst mit `configuration` die aktuelle Version prüfen. Eine UUID **einmal**
erzeugen und zusammen mit ihrer ursprünglichen Konfigurationsversion privat
festhalten. Dieselben Werte bei Antwortverlust und nach Neuanmeldung beibehalten.
`request-test` erzeugt nur die feste verschlüsselte Testabsicht; kein Mailaufruf.

```sh
docker compose -f "$REVIEWED_COMPOSE_FILE" -f deploy/compose.notification.yaml \
  --profile notification-operator run --rm --no-deps notification configuration
docker compose -f "$REVIEWED_COMPOSE_FILE" -f deploy/compose.notification.yaml \
  --profile notification-operator run --rm --no-deps notification request-test \
  --request-id "$SAVED_REQUEST_UUID" --expected-version "$ORIGINAL_CONFIG_VERSION"
```

Den gespeicherten Slotkey privat sichern. `preview --slot-key "$SLOT_KEY"` gibt
den exakt gespeicherten festen Payload einschließlich Empfängern zur privaten
Betreiberprüfung aus; diese Ausgabe nicht öffentlich protokollieren. Kein Editor,
keine Anhänge, kein freier Text oder Empfängerwechsel im Testrequest.

Erst nach konkretem Betreiberabgleich von Vorlage, Empfängern und Anzahl darf
`send --slot-key "$SLOT_KEY"` den benannten Auftrag ausführen. Für die später
autorisierte Initialprobe genau ein Testauftrag an die drei privat bestätigten
Ziele; diese Liste steht nicht im Produktrepository. Bei ungewissem Ausgang keinen
neuen Auftrag zum Wiederholen erzeugen. Statuslookup ohne neuen Request:

```sh
docker compose -f "$REVIEWED_COMPOSE_FILE" -f deploy/compose.notification.yaml \
  --profile notification-operator run --rm --no-deps notification status \
  --request-id "$SAVED_REQUEST_UUID" --expected-version "$ORIGINAL_CONFIG_VERSION"
```

Alternativ `status --slot-key "$SLOT_KEY"`. Lookup liest vorhandene scopegebundene
Belege ohne Graphauth, Notificationdecrypt oder neue Sitzung. Gleicher exakter
Request bleibt anActoroperator/UUID/Scope/ursprünglicheVersion gebunden; andere
Bindung ergibt Konflikt. Veralteter unreservierter Test wird nicht neu adressiert.

## Begrenzte Beobachtung, Planung und Versand

- `observe`: lokale Metadaten des Graph-Anmeldezertifikats speichern; keine
  Graphauth. `observe --probe`: zusätzlich frische Anmelde-/Postfachprobe, solange
  keine persistente Graphsperrfrist gilt. Keine Schreibprobe oder neue Entra-Rechte.
- `plan`: heutige Pflichtwarnung und jüngsten fälligen Tages-/Wochenbericht aus
  dem echten Journal vorbereiten. Bei0Vorgängen korrekte0Zähler; kein Importscan.
- `dispatch`: bereits vorbereitete Meldungen begrenzt senden, standardmäßig1,
  ausdrücklich maximal5, Zertifikatsvorrang und bestehende Stundenquote.
  `send` arbeitet ausschließlich auf einem konkret benannten gespeicherten Slot.

Reine Fehler-/Ausfallverträge aus A bleiben erhalten. Die tatsächliche weitere
API-/Processing-Beobachterverdrahtung und Webkonfiguration sind noch Integration;
diese CLI implementiert keinen unabhängigen VM-/SMBüberwachungsdienst. Kein
dauerhafter Planer oder Zeitplan wird durch die Befehle gestartet.

## Zertifikats- und Unsicherheitsvertrag

Geschützte PEM einmal lesen; zum RSAprivatkey passende erste öffentliche
Zertifikatsidentität eindeutig prüfen. SHA256, notBefore/notAfter und exakte
Restzeit werden lokal bestimmt. Aktuell gelesene Datei, offene alte Warnserie und
letzter erfolgreicher Proof sind getrennte Metadaten. Ein historischer Proof ist
keine neue Anmeldung mit einer inzwischen anderen Datei.

Dateitausch/Registrierung/Cachetoken beenden die alte Serie nicht. Ende erst durch
neue CertificateCredential ohne persistente Tokenübernahme mit **denselben gelesenen
PEMbytes**, lokal gültigem Nachfolger desselben Scopes und erfolgreichem minimalem
GraphGET. Die vor PEMlesen erfasste Monitorrevision schützt gegen verspätete alte
Beobachter/Proofs. Ungültiger Nachfolger schließt keine Serie. Ein selbst bald
ablaufender gültiger Nachfolger erhält seine eigene Warnserie.

**Ablauf0/negative Restzeit schaltet die Pflichtwarnung nicht ab.** Planung und
best-effortAuth/Versuch bleiben möglich; tatsächliche Graphantwort entscheidet.
Wenn Anmeldung scheitert, bleibt der neutrale Fehler im gespeicherten Beleg und
die Warnserie offen/rot. Es gibt keine Zustellgarantie nach Zertifikatsablauf.

Kein POST vor bestätigt zurückgekehrtem Reservierungs- und POST-Gate-Commit.
Payload ist ab Reservierung unveränderlich.202 heißt vom Maildienst angenommen,
keine Zustellung. Sichere4xx-Ablehnung,5xx/Transport/Abbruch/unklarer Commit und
dauerhaft akzeptierter Abschluss werden getrennt behandelt. Unknown wird nie
erneut gesendet.429 setzt eine persistente Scopefrist auch für andere neue Proben;
ungültige Retry-After-Werte15Minuten, übergroße Werte bleiben gesperrt.

Ein absolutes monotones80s-Gesamtbudget ab CLIeintritt gilt auch für den gemeinsamen
späteren Webserviceaufruf: Vorprüfung verbraucht dasselbe Budget. Kindphase maximal60s,
Restbudget minus10s; darin eigene Cleanupreserve, danach maximal5s endgültiger
Readback und3s Antwortreserve. DB-/Spawn-/Auth-/Transportzeiten zählen mit.
Graphanfrage wird zusätzlich auf verbleibende Zeit begrenzt; nach verspätetem
POST-Gate-Commit kein Transportstart nach Frist. Kein Graphaufruf im APIthreadpool.
Fehlender Kindausgang ist kein neuer Versandauftrag: nach beendetem Kind entscheidet
dauerhafter Readback. Nicht beendetes Kind oder nicht erreichbare DB ergibt
`persisted:false`/nicht prüfbar, keinen erfundenen gespeichertenunknown-Status.

## Prüfstand und noch nötiger nativer Nachweis

Lokal: echte Fernet-/generierte RSA-/X509prüfungen, Graphtransportdoubles und reale
synthetische Kindprozesse mit EOF/Kill, DBsperre, Envstrip und begrenzter Ausgabe.
Prozessfristen mit verkürzten Budgets geprüft; kein vollständiger80s-Wartelauf oder
ASGI-/90s-Proxynachweis daraus. Neue Webpfade folgen in C. Keine echte Cloudanmeldung,
SendMail oder Empfängerzustellung aus lokalen Tests behaupten.

Auf dem festen B-Pin benötigt der Betreiber noch: API-/Testimageherkunft,
gezielte Linuxhauptthread-/Signal-/CLI-/Prozessprüfung, native MariaDB-/DBsocket-/
Pool-/Sperrgrenzen und effektive Compose-/Mount-/Envallowlist einschließlich
eigenemNotifkey. A-Schema-/Alt-API-Nachweis bleibt ein eigener Beleg. Keine breite
AP06-Wiederholung; reale Initialprobe erst nach konkretem Rootabgleich.
