# AP07 – begrenzte Betreiberbefehle

Stand: 15. November 2026. AP07 ist geprüft und bereitgestellt aus
`5ecfd59270b63947d3f92af98a1b9f8e5a267aeb`, Kundenschema007. API/Web aus gleicher
Quelle, bestehende Instanz/LDAP-Konfiguration und DBdienst sind getrennt bestätigt.
Eigener Notificationkey und drei Empfänger sind privat eingerichtet. Die einmalige
feste Testmail mit HTTP 202/Reservierung 1 und separatem Statusabgleich ist bestätigt;
Empfang im eigenen Abnahmepostfach belegt. Diese Anleitung erteilt keinen weiteren
Versandauftrag oder eine Timeraktivierung. Geprüfte unveränderliche Imagepins
verwenden; die tatsächlichen Laufzeitwerte bleiben in den Betreiberunterlagen.

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

Der CLI-Service gehört zum Profil `notification-operator`. Das Profil sowohl bei
Ausführungsbefehlen als auch beim Rendern mit `config` beziehungsweise
`config --services` ausdrücklich aktivieren, damit derselbe aktive Dienstumfang
geprüft wird:

```sh
docker compose -f "$REVIEWED_COMPOSE_FILE" -f deploy/compose.notification.yaml \
  --profile notification-operator config
docker compose -f "$REVIEWED_COMPOSE_FILE" -f deploy/compose.notification.yaml \
  --profile notification-operator config --services
```

Die gerenderte Konfiguration kann private Pfade und Verbindungswerte enthalten;
ihre Ausgabe gehört ausschließlich in die privaten Betreiberunterlagen.

Der Senderkindprozess **im APIcontainer** bleibt Teil derselben bereits
genehmigten API-Vertrauensgrenze und teilt deren Dateisystem. Seine Envallowlist
und eigener Notificationkey sind implementiert; daraus keine Dateisystemisolation
vom APIprozess ableiten. Notificationcode liest auch dort keine LDAPdateien.
Eigene API-Keybindung und AD-gesicherte Webpfade sind mit AP07 bereitgestellt.

## Einmalige private Erstkonfiguration

Nach geprüftem Schema 007 beginnt der Notificationkopf mit version0 und ohne
Empfänger. Dies ist der Ablauf für eine neue Instanz; die bereitgestellte Instanz
ist bereits privat initialisiert. Private JSON nach dem [synthetischen Beispiel](../deploy/notification-init.example.json)
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
  dem echten Journal vorbereiten. Zusätzlich tatsächliche Verarbeitungsfehler
  sowie APIbereitschaft und frischen Graphzugriff begrenzt beobachten; fällige
  Fehler-/Ausfall-/Erholungsabsichten vorbereiten. Bei0Vorgängen korrekte0Zähler;
  kein Importscan und kein Mail-POST. Dieser Befehl führt jetzt lesende Netzproben aus.
- `dispatch`: bereits vorbereitete Meldungen begrenzt senden, standardmäßig1,
  ausdrücklich maximal5, Zertifikatsvorrang und bestehende Stundenquote.
  `send` arbeitet ausschließlich auf einem konkret benannten gespeicherten Slot.

Reine Fehler-/Ausfallverträge aus A bleiben erhalten. C verbindet sie mit tatsächlichen
Journalzuständen und Proben. Der API-GET nutzt fest `http://api:8000/api/health/ready`
mit höchstens5s, maximal4KiB und erwartet die gleiche Instanz; CLI und API müssen
im vorgesehenen Compose-Netz erreichbar sein. Leeres Journal/inaktive Importjobs
sind kein Ausfall. Die eigene VM/DB kann nicht zuverlässig selbst alarmieren.
Diese CLI implementiert keinen unabhängigen VM-/SMBüberwachungsdienst. Kein
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

Jeder Warnplan ist an seine ursprüngliche offene Serie im selben Scope gebunden.
Planung, Reservierung und POST-Freigabe prüfen diese Bindung atomar. Nach gültigem
Nachfolgerproof sind auch verspätete erste Altplanungen gesperrt. Vorbereitete
Altzeilen werden überholt; reservierte Altzeilen ohne konsumierte POST-Freigabe
werden abgewiesen, ohne Reservierung oder Payload zurückzusetzen. Ein vor dem Proof
bereits freigegebener POST kann nicht zurückgerufen werden; accepted/unknown und
der Einmalvertrag bleiben erhalten. Bloßer Dateitausch beendet keine Pflichtserie.

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

Ein absolutes monotones 80-s-Gesamtbudget ab CLIeintritt gilt auch für den gemeinsamen
Webserviceaufruf: Vorprüfung verbraucht dasselbe Budget. Kindphase maximal60s,
Restbudget minus10s; darin eigene Cleanupreserve, danach maximal5s endgültiger
Readback und3s Antwortreserve. DB-/Spawn-/Auth-/Transportzeiten zählen mit.
Graphanfrage wird zusätzlich auf verbleibende Zeit begrenzt; nach verspätetem
POST-Gate-Commit kein Transportstart nach Frist. Kein Graphaufruf im APIthreadpool.
Fehlender Kindausgang ist kein neuer Versandauftrag: nach beendetem Kind entscheidet
dauerhafter Readback. Nicht beendetes Kind oder nicht erreichbare DB ergibt
`persisted:false`/nicht prüfbar, keinen erfundenen gespeichertenunknown-Status.

## Bestätigter Prüf- und Betriebsstand

Für die AP07-Webintegration benennt `compose.notification-web.yaml` an der API
Graph-JSON, Graph-PEM und den zusätzlichen unabhängigen Notificationkey als einzelne
RO-Dateien. Die API behält ihre bisherigen AD-/DB-/Vorschauaufgaben; ihr Kind
teilt dieselbe Dateisystemgrenze. Die Envallowlist ist keine physische Isolation.
Der eigenständige CLI-Container verwendet weiter ausschließlich seine expliziten
minimalen Bindungen aus `compose.notification.yaml`. Das Weboverlay aktiviert
keinen Worker oder Zeitplan. Die bereitgestellten API-/Webimages stammen aus
demselben festen Codepin; ihre Herkunft wurde getrennt bestätigt. Bei späteren
Aktualisierungen beide Herkunftsnachweise erneut dem geprüften Stand zuordnen.

A/B vollständig geprüft, C-Quellenreview und 21 C-Fälle auf MariaDB bestanden.
Acht isolierte HTTPS-Browsergruppen belegen unter anderem den vollständigen
Fristfall mit 80,006 s sowie Antwortverlust/neue Sitzung/Konfigversion ohne
Doppel-POST. Exakte Zertifikatsschwellen 10d/1d/0/negativ und Loginhinweis für
beide Rollen geprüft; zusätzlicher synthetischer CLIplan bestanden.

Die echte Graph-Zertifikatsanmeldung und einmalige Mailprobe sind separat von
diesen synthetischen Prüfungen bestätigt. Ein Empfangsnachweis liegt ausschließlich
für das eigene Abnahmepostfach vor. Keine neue tatsächliche Kundenanmeldung nach
AP07; die echte AD-Abnahme aus AP01 bleibt historisch.

Import-, Korrektur- und Notificationautomatik bleiben inaktiv. Gespeicherte
Zeitangaben starten keine Jobs. Dauerhafte Aktivierung erst nach AP08-Go;
AP08/09/10/11 sind nicht freigegeben. Aktueller [Betriebsstand](BETRIEBSSTAND.md).
