# AP12 – Graph-Zertifikatsrotation und Administration

Stand: 17. November 2026. AP12 ist aus `d9f32a5a9c9fb642f59a13ed2550f74532fc3ebe`
bereitgestellt, Schema008. Der echte Zertifikatswechsel ist unabhängig nativ bestätigt:
`committed/new`, SQL-Zustand `overlap`, alle drei Verbraucher und eigener
Abschlussproof. Genau ein kontrollierter AP12-Kundenboot ist erfolgt. Danach sind
Kunden-API, Datenbank und Nginx unverändert erhalten; neues Graph-Zertifikat,
sieben Timer, CIFS und HTTPS sind bestätigt. Die qualifizierten
Wiederaufnahmebelege und ihre Grenzen stehen in der [Übergabe](AP12-UEBERGABE.md).
Produktive Altkeybereinigung nach Ablauf der Überlappung bleibt gesondert offen.

Der erste echte Wechselversuch endete kontrolliert auf dem alten Zertifikat; seine
ursprüngliche Fehlerursache bleibt unbelegt. Ein ausdrücklich getrennter zweiter Auftrag
wurde nach lesendem Abgleich seiner unklaren Registrierung unter derselben
ursprünglichen Auftragsidentität erfolgreich fortgesetzt. Der erste Fehlversuch und sein
registrierter Kandidat bleiben getrennt erhalten; der Erfolg des zweiten belegt keine
nachträgliche Erklärung oder Behebung der ersten Ursache.

Die [Übergabe](AP12-UEBERGABE.md) trennt den aktuellen Betriebsnachweis von
historischen Einzelprüfungen und den verbleibenden Nachweisgrenzen.
Teilabläufe: [Host](AP12-HOSTABLAUF.md), [Cleanup](AP12-CLEANUP.md),
[Admin/API](AP12-ADMIN-API.md), [Automatik](AP12-AUTOMATIK.md),
[Rootzuordnung](AP12-OWNERSHIP.md). Die folgenden B-/C-Abschnitte dokumentieren
ihre damaligen Lieferstände; offene Einzelprüfungen werden nicht pauschal geschlossen.

## Gelieferter Kern B und seine Grenze

`rotation_model.py` und `rotation_graph.py` begrenzen den Adapter auf die eigene
fest gebundene App. Vorhandene Kryptografie/Azure Identity/httpx bleiben erhalten:
RSA 3072, tatsächlich 180 Tage einschließlich Vordatierung, gesonderter PoP mit
App-Objekt-ID, selektiver Bestands-GET, genau ein addKey-POST je dauerhaftem Auftrag.
Es wird keine zusätzliche Graphberechtigung oder Laufzeit installiert.

Die additive Migration 008 legt ausschließlich zwei neue Auftragstabellen an;
Automatik ist zunächst aus. Ursprüngliche Instanz/Scope/Akteur/Request-ID bleiben
gebunden. Leases oder ein späterer Tageslauf erzeugen nach unklarer/abgelehnter
Registrierung keinen Ersatzauftrag. Eine ausdrücklich neue berechtigte manuelle
Anforderung bleibt von der alten Quittung getrennt. Alte Tabellen/Migrationen bleiben.

`rotation_journal.py` speichert den einen Kandidaten und das Sendestadium vor dem
POST rootprivat mit Dateiflush/atomarem Ersatz/Verzeichnis-fsync. Wiederaufnahme
verwendet dieselben Bytes und liest ausschließlich den gebundenen Bestand.
Genau eine passende neue Key-ID mit unverändertem Altbestand ist erforderlich;
Null-/Mehrfachtreffer, andere App oder widersprüchliche Antwort bleiben unknown.
Das Inventar übernimmt neue eigene Keys nach bestätigter Registrierung; bestehende
Keys werden nur nach gesonderter Rootattestierung als verwaltet gekennzeichnet.
Der Entfernen-Adapter und lesende Inventarabgleich sind noch kein Cleanupauftrag.

Die frische Kandidatenprobe verwendet exakt das gespeicherte PEM und schreibt
keinen produktiven AP07-Monitor-/Nachfolgerproof. Aktivierung, Rückweg,
dauerhafte Graphfreigabe, Timer und Webrouten werden von diesem Kern nicht ausgeführt.
Bestehende API-/Hostpfade sind in Paket B unverändert; keine produktive Mutation
oder neue Bedienaktion daraus ableiten.

28 gezielte lokale Fälle mit realer Kryptografie, synthetischem HTTP und SQLite
sind bestanden, einschließlich echter synthetischer 007→008-Bestandserhaltung
und ausgewählter unveränderter API-/Notification-/Processing-/Vorschauleser.
POSIX-Dateirechte/flock/Verzeichnis-fsync und Linuxfristen haben in den lokalen
Windowsprüfungen ausdrückliche Doubles. Die anschließenden nativen B2-Belege
bestätigen auf isolierter MariaDB 007→008 mit unverändertem Bestand und zwei
identischen Anforderungen unter REPEATABLE READ/snapshot ON: gleiche Quittung,
genau eine Auftrags-/Auditwirkung. Separat sind echte Linux-Rootrechte, flock,
Prozessende und Wiederaufnahme ohne zweiten POST sowie Rechte-/Symlinkablehnung
bestanden und unabhängig geprüft. Kein Kundenbestand, Mail- oder Graphzugriff
dieser Tests; keine produktive Migration oder Zertifikatsrotation daraus.

SQL-Nachtrag B-R1: Head wird vor der ersten konsistenten Lesung gesperrt und die
ursprüngliche Quittung danach ebenfalls sperrend gelesen. Das erhält identische
parallele Anforderungen unter der vorgesehenen Serialisierung. Der gezielte
SQLite-Nachlauf ersetzt keinen MariaDB-Nachweis mit tatsächlicher Isolation.
Der oben genannte separate native B2-Nachweis schließt diesen Befund im
geprüften Kernumfang. AP12 insgesamt bleibt in Arbeit.

## C1 – lokale Freigabe als Bibliotheksstand

`app/graph_access.py` und `deploy/graph-access-host.py` sind feste stdlib-Bausteine,
noch ohne Verdrahtung in API, Kinder oder Hosteinstieg. Sie installieren/öffnen
keine Freigabe und ersetzen keinen Bereitstellungsauftrag. Die vollständige
Host-/API-Übernahme bleibt das anschließende Paket.

Die Freigabe ist an Quelle/Deployment/Instanz/Scope, Kernelboot, Generation und
tatsächliche PEMbytes gebunden. Fehlende/ungültige Daten sperren. Shared-flock
trägt die zugelassene Aktion; ein explizit übertragener Kinddeskriptor hält diese
Bindung auch nach Elternende. Schließen erfolgt ohne LOCK_UN, das sonst auch
einen geerbten Deskriptor vorzeitig entsperren könnte. Root schreibt zuerst blocked,
wartet exklusiv und öffnet ausschließlich ausdrücklich nach Abschlussbeleg.

Gesonderte Hostproben sind an ein 256-bit-Geheimnis, Auftrag/Generation/Boot,
Verbraucher, Material und höchstens 60 Sekunden gebunden. Im lesbaren Beleg steht
nur der Hash. Leseprobe erlaubt ausschließlich GET und keinen produktiven
Nachfolgerproof; dafür ist ein eigener finalize-proof-Zweck erforderlich.
Pause, Epochkonflikt, falscher Boot/Deskriptor/Verbraucher und abgelaufener oder
widerrufener Grant bleiben gesperrt. Das ändert das Runtimeprofil name/image nicht.

14 gezielte lokale C1-Fälle bestanden; POSIXrechte, flock und Verzeichnis-fsync
sind dabei ausdrücklich ersetzt. Echte Dateideskriptor-Duplikation und
Fehlerpfad-Schließen wurden lokal geprüft. Anschließend wurden alle sieben
isolierten Linux-Komponentenchecks samt separatem Rücklesen unabhängig bestätigt:
Writerinitialisierung, echter flock nach SIGKILL des eigenen Elternprozesses,
gesondertes Kindende vor EX, Sperre neuer Zulassungen, alte Generation, falscher
Boot und enges Host-Lesepermit. Dieser Lauf war UID0:GID10001, ohne Graph/Mail;
er belegt keine tatsächliche UID10001-API-/Verbrauchereinbindung.

## C2a – Freigabe in bestehenden Graphwegen

`graph_access_runtime.py` liest eine zusätzliche rootgeschützte Bindung unter
`/run/importer/graph-access-binding.json`. Sie enthält ausschließlich Schema,
Quelle, Deployment, Instanz, eigene App-Objekt-ID und den daraus mit tenant/client/
mailbox berechneten Rotationsscope. Das bestehende Graph-JSON bleibt unverändert.
Die API vergleicht zusätzlich die tatsächliche DBinstanz. Fehlend, ungültig oder
abweichend bedeutet gesperrt; kein Legacy-Fallback und keine Browseroption.

Beide vorhandenen Graphfabriken verlangen die Freigabe vor Credentialerzeugung.
Der unterste Graphtransport prüft sie vor jeder Tokenanforderung/HTTPaktion;
ein direkter Client ohne Permit bleibt geschlossen. Der lesende Testquellclient
übernimmt die vorhandene Bindung. Der AP07-Proof benötigt denselben Kontext;
Kandidaten-/Verbraucherlesegrants dürfen keine Warnserie schließen oder senden.

Nach der unveränderten AD-/Origin-/CSRF-Grenze sperrt eine fehlende APIfreigabe
Originalvorschau/Download/Original-HEAD und Testsendung mit 503, bevor ein Kind
oder neuer Versandtestslot angelegt wird. Notificationkinder erhalten nur den
serverseitig erzeugten Deskriptor mit Snapshot über feste IPC, keine HTTPfelder.
Vorschaukinder erhalten ein Duplikat über multiprocessing.spawn und prüfen es
vor Quellabruf. Eltern halten bis Kindende/Reap und beim Versand bis zum
dauerhaften Readback; anschließend kann eine lokale geprüfte PDFantwort ohne
Graphlock streamen. Fristen, Request-ID und einmalige POSTreservierung bleiben.
Anmeldung, Health, gespeicherte Berichte/Historie und lokale Zertifikatsdaten
bleiben Graph-unabhängig.

Gezielte lokale Prüfung: Runde mit 46 Fällen, davon 45 bestanden und ein echter
POSIX-Rechtetest unter Windows ausgelassen; vier zusätzliche Lebenszeit-/Budget-/
Replayfälle und eine Vorschau-Lebenszeitprüfung bestanden. Rechte/flock/
Verzeichnis-fsync sowie Linux-Spawning sind dabei ausdrücklich ersetzt; echte
Dateideskriptorduplikation und API-/AD-/CSRF-/SQLiteabläufe wurden lokal geprüft.
Synthetische Transportfixtures benennen ihre Testfreigabe ausdrücklich und
werden vom APIimage nicht übernommen.

Dieser feste Quellstand ist noch kein Bereitstellungspaket. RO-Bindungen aller
Verbraucher, tatsächliche UID10001-API-/Kind-/Verbraucherprüfung, fester Host-
Probeaufruf, privilegierte Übernahme/Rückweg und Öffnen zuletzt folgen separat.
Ohne diese Bindungen bleibt der neue Quellstand absichtlich gesperrt. Das
Runtimeprofil bleibt name/image; API-ID gehört nur in den privaten Abschlussbeleg.
Kundenruntime, produktive Graphpfade, Schema 007 und AP08-Timer bleiben erhalten.

## C2b – feste Hostprobe und Verbraucherbindungen

`python -B -m app.graph_access_probe` ist ein fester interner Aufruf als
UID10001:GID10001, ohne HTTProute, Workerflag oder Pfadargument. Root übergibt
genau ein begrenztes JSONpaket über anschließend geschlossenes stdin: Schema1,
operation_id,epoch,purpose,consumer_role,consumer_id und ein 256-bit-Geheimnis
als64 Hexzeichen. Keine Geheimnisse in Argumenten, Umgebung oder Ergebnis.
Der vorhandene Gatebeleg muss den passenden höchstens60s-Grant enthalten.
Config/PEM/Bindung haben feste Containerpfade; Probe ist auf40s begrenzt.

Fristkorrektur C2B-R1: Der vorhandene begrenzte Kindprozess umfasst den gesamten
Probeablauf; zwei Sekunden des ursprünglichen40s-Budgets bleiben für dessen
bestätigtes Reap reserviert. Das Kind erhält dieselbe absolute Arbeitsfrist,
einschließlich bereits verbrauchter Spawn-/Preflightzeit. Es gibt keinen äußeren
ITIMER_REAL um GraphClient: Dessen unveränderte eigene POSIX-Transportfrist bleibt
aktiv und mit der übrigen Ablaufzeit kompatibel. Auch blockierendes Credential-
Schließen/DB-/Proofarbeit fällt unter die Elternfrist. Probegeheimnis bleibt in
stdin und privater fester Eltern-Kind-IPC, nicht in Argumenten/Umgebung.
Sechs synthetische lokale Funktionsfälle bestanden; drei zusätzliche echte
POSIX-Frist-/Spawnfälle werden unter Windows ausdrücklich übersprungen und sind
für die separate native Prüfung vorgesehen. Noch kein nativer R1-PASS.

candidate-read/consumer-read verwenden eine frische Credentialinstanz und einen
minimalen Inbox-GET, ohne DBzugriff oder AP07-Proof. Nur finalize-proof darf nach
dem GET den aktuellen Monitorrevision-/DBinstanz-gebundenen AP07-Proof schreiben.
Der Grant wird anschließend nochmals geprüft. Rückgabe enthält nur öffentliche
Bindungen, Materialhash, Fingerprint, Proofrevision/-zeit und BelegSHA256. Root
muss das Ergebnis der tatsächlich ausgewählten Consumer-ID zuordnen; stdin ist
keine Browser-/API-Schnittstelle. Ein Grant allein bestätigt keine Übernahme.

Composevorlagen für API, Graphoperator, Notification und lesende Testquelle
erhalten ausschließlich RO-Bindungen für das zusätzliche Bindingfile und den
Gateunterordner. Die neuen Hostvariablen GRAPH_ACCESS_BINDING_HOST_FILE und
GRAPH_ACCESS_GATE_HOST_DIR sind ausdrücklich erforderlich; keine Pfaderzeugung.
Bestehende Secret-/Netz-/User-/Capabilitygrenzen bleiben. Graphmigration und
Klassifikation benötigen keine neue Graphbindung.

Processing-/Notification-Hoststarts lesen ein getrenntes rootgeschütztes Profil
`/etc/invoice-importer/graph-access-host.json` mit ausschließlich binding_file
und directory. Sie geben zwei feste RO-Ziele weiter. Kein APIcontainer-ID-Feld
im Runtimeprofil name/image und kein allgemeines Hoststatus-/Rootjournalmount.
Die Pfade müssen mit den tatsächlich installierten Composebindungen übereinstimmen;
Hostübernahme prüft dies separat. Acht gezielte lokale synthetische Prüfungen
bestanden; tatsächliche native Verbraucher-/ProbeCLIprüfung bleibt offen.

Die Hoststeuerung muss Verbraucherbelege vor finalize-proof und diesen Proof
vor dem dauerhaften Abschluss bestätigen. Erst danach darf sie die normale
Freigabe öffnen. APIneuerstellung, Rückweg, Quittungen und Cleanup sind durch
diesen Probe-/Mountstand weiterhin nicht implementiert oder bereitgestellt.

## C3a – privater dauerhafter Übernahmebeleg

`rotation_adoption.py` ergänzt das vorhandene Rootjournal um eine getrennte
auftraggebundene host.json-Datei und eine unveränderliche alte PEMsicherung.
Der B-Registrierungsbeleg behält sein Format. Aktivierungsabsicht wird vor dem
Dateiersatz gespeichert; Verbraucher-/Proofstadien und abschließender BelegSHA256
bleiben getrennt. Tatsächliche Container-IDs stehen ausschließlich im privaten
Beleg, gebunden an Rolle/Image/Probezweck/Quittungshash/Material/Quelle/Instanz.
Ein unklarer Proof behält seine ursprüngliche Revision-/Verbraucher-/Epochbindung;
die Schreibabsicht kann nicht einfach erneut begonnen werden.

Commit des Belegs setzt drei passende Verbraucherquittungen, den getrennten
passenden höchstens60s alten Proof, weiterhin gültiges Zielmaterial und denselben
Pausen-/Drainzustand voraus. Rückweg verlangt die nach Hash/Kryptografie geprüfte
gültige Originalsicherung und erneut sämtliche alten Verbraucher/Proofs. Boot-
wechsel blockiert Wirkungen, erhält aber den alten Beleg lesbar. Sieben gezielte
lokale Datei-/Kryptografiefälle bestanden, POSIX-/Hostgrenzen ausdrücklich ersetzt.
Dieser Baustein öffnet kein Gate und führt keine Docker-/Dateiaktivierungsaktion
aus. Tatsächlicher Hostcontroller, Boot-/Unknown-Reconciliation und native
Übernahme-/Rückwegprüfung bleiben getrennte Folgearbeit.

Übergangskorrektur C3A-R1: rollback_unknown ist ausschließlich in noch nicht
versiegelten Rückwegphasen zulässig. Nach committed wird der Aufruf vor jeder
Änderung abgelehnt; Revision/Seal und gesamte Datei bleiben unverändert lesbar.
Gezielt abgeschlossenen und weiterhin zulässigen offenen Rückweg lokal geprüft.

Geplant nach AP08 und vor AP11/der finalen AP09-Übergabe. Technische Grundlage ist
AP07. Vorhandene Betriebsbausteine aus AP08/AP10 nutzen, soweit vorhanden; keine
anderen AP-Freigaben aus diesem Plan ableiten.

## Zusätzlicher Reiter in der Administration

Name: **Administration → Graph-Zertifikat**. Er ergänzt Berichte,
Benachrichtigungen sowie Verbindungen/Verarbeitung und verwendet die vorhandene
Zertifikatsanzeige/-prüfung aus AP07.

- Aktives Graph-Anmeldezertifikat, öffentlicher Fingerprint und Ablauf.
- Letzter Versuch, letzte erfolgreiche Prüfung und letzte erfolgreiche Erneuerung
  getrennt anzeigen; nächster geplanter Prüflauf mit Solltermin.
- Laufender Wechsel, Ergebnis und verständlicher Fehler-/Handlungsstatus.
- Bisheriges und neues Zertifikat während der Übergangsfrist, Rückweg und
  ausstehende Bereinigung.
- Aktion „Jetzt erneuern“ über denselben begrenzten Ablauf wie die Automatik.

Bestehende AD-Gruppen gelten: GR_CEO liest; GR_Rechnung darf verwalten und den
festen Erneuerungsauftrag auslösen. Aktuelle AD-Prüfung, Origin/CSRF und
serverseitige Aktionsbindung vor Auftragszugriff verwenden. Ein Klick darf bei
Wiederholung oder Antwortverlust keinen zweiten Wechsel erzeugen.

Der Browser erhält keine privaten Schlüssel, PFX-Kennwörter oder Schlüsseldateien.
Ein PFX-Upload, ein Download privater Schlüssel und eine SMB-Abholautomatik gehören
nicht zum Standardumfang. Das vorhandene HTTPS-/Wildcardzertifikat bleibt ein
separater Betriebsweg.

## Ein gemeinsamer kontrollierter Wechsel

1. Vorhandene Konfiguration, Zertifikatsgültigkeit und ausstehende Aktionen prüfen.
   Einen dauerhaften Wechselauftrag mit Identität/Zustand und Sperre anlegen.
2. Neues Schlüsselpaar und passendes Zertifikat lokal auf Linux erzeugen.
   Laufzeit und Gültigkeit müssen die geltenden Entra-Richtlinien berücksichtigen.
3. Nur den öffentlichen Teil zusätzlich an derselben konfigurierten Entra-App
   registrieren. Vorhandene funktionierende Registrierung zunächst erhalten.
4. Mit dem neuen Zertifikat ausdrücklich einen frischen Token und einen minimalen
   Graph-GET prüfen. Ein alter Cachetoken ist kein Nachweis des neuen Zertifikats.
5. Zertifikatsdatei kontrolliert aktivieren. Laufende Aktionen berücksichtigen und
   alle betroffenen Verbraucher auf das neue Material umstellen; bei einzelnen
   Docker-Dateibindungen erforderliche gezielte Neuerstellung vorsehen.
   Anschließend die tatsächlich betriebene Laufzeit erneut prüfen.
6. Erfolgreichen Wechsel und den vorhandenen AP07-Nachfolgernachweis speichern.
   Bei Fehlern bleibt der alte funktionierende Stand verfügbar beziehungsweise
   wird über den festgelegten Rückweg wiederhergestellt.
7. Nach bestätigtem Betrieb und definierter Überlappung ausschließlich die selbst
   verwaltete alte Registrierung/Datei gezielt bereinigen. Keine fremden
   App-Zertifikate oder übrigen Zugangsdaten entfernen.

Ziel ist ein begrenzter Betreiberauftrag auf dem Host. Der API-Container bekommt
dafür keinen allgemeinen Root-/Shellzugriff, keinen Dockersocket und kein
Schreibrecht auf die private Zertifikatsablage. Schnittstelle und Berechtigungen
vor Implementierung konkret entwerfen und unabhängig prüfen.

Wechsel-ID, auslösender berechtigter Benutzer beziehungsweise Automatik,
öffentlicher Fingerprint, registrierte Schlüssel-ID und Fortschritt dauerhaft
erfassen. Die aktive Vorgangsbindung über Doppelklick, Antwortverlust, Neustart
und gleichzeitigen Zeitplanaufruf erhalten. Nach Abbruch oder verlorener Graph-Antwort zuerst den
bekannten Vorgang abgleichen; Registrierung, Aktivierung oder Entfernung nicht
blind wiederholen. Parallele manuelle und automatische Wechsel verhindern.

## Automatik und Wiederherstellung

Vorgesehene Standardwerte: tägliche Prüfung, Beginn der Erneuerung 30 Tage vor
Ablauf, sieben Tage Überlappung bei ausreichender Restgültigkeit. Zeitsteuerung
und gültige Einstellgrenzen werden im AP12-Entwurf festgelegt und geprüft.
Fehlgeschlagene Erneuerung sowie ausgebliebene Prüfläufe müssen sichtbar sein.
Ein abgelaufenes Altzertifikat bietet keinen Rückweg; sieben Tage sind ein Zielwert
innerhalb der tatsächlichen Gültigkeit. Notfall-/Eskalationsfrist im Entwurf
festlegen. Ein Ausfall der gesamten VM oder Datenbank kann nicht zuverlässig durch
dieselbe Anwendung alarmiert werden; dafür ist eine unabhängige Betriebsüberwachung
erforderlich, ohne sie aus diesem AP als bereits vorhanden abzuleiten.

Die AP07-Pflichtwarnung ab zehn Tagen und die roten Hinweise ab einem Resttag,
bei null und danach bleiben erhalten. Eine Warnserie wird weiterhin erst nach
dem bestätigten gültigen Nachfolger beendet.

Für die Selbstrotation verlangt Microsoft einen Besitznachweis mit einem
bestehenden gültigen Zertifikat; für das Rollen eigener Schlüssel dokumentiert
Microsoft keine zusätzliche spezielle Appberechtigung. Diesen Weg im Zielmandanten
gezielt prüfen, ohne pauschale tenantweite App-Verwaltungsrechte vorauszusetzen.
Sind alle Zertifikate abgelaufen, ist ein dokumentierter administrativer
Wiederherstellungsweg erforderlich. Warnmails über dieselbe ausgefallene
Graph-Anmeldung bieten dann keine Zustellgarantie.

Vorhandene Python-/Zertifikats- und Graph-Bausteine nutzen. Keine zusätzliche
gekaufte Zertifikatsverwaltung voraussetzen.

## Prüfung und Unterlagen

AP12 umfasst den Entwurf, das manuell geprüfte Betreiberskript, den Adminreiter,
die gezielte Aktivierung der Automatik und deren Abnahme. Gezielt prüfen:
Rollen/CSRF, Wiederholung/Konkurrenz, neue Anmeldung und tatsächliche Übernahme,
unterbrochene/unklare Schritte, Rückweg, Bereinigung, abgelaufene Ausgangslage
und fehlender Prüflauf. Kundendaten durch synthetische, isolierte Fälle ersetzen,
soweit möglich; tatsächliche Entra-Änderungen erst auf geprüftem konkretem Ablauf.

AP11 beschreibt den ausgelieferten Reiter und die erlaubten Bedienwege.
AP09 ergänzt technische Durchführung, Rückweg und administrative Wiederherstellung.
Keine Geheimnisse oder privaten Betriebswerte in die öffentlichen Unterlagen.

## C4 – Rootbereinigung nach bestätigter Übernahme

Der Quellstand verbindet den dauerhaften sieben Tage begrenzten Überlappungsplan,
eine einmalige eigene removeKey-Freigabe, lesenden Unknown-Abgleich und begrenzte
Altdateibereinigung mit dem festen Hostcontroller. Vor Wirkungen prüft der
Rootworker die normale Graphfreigabe und selbst eine frische Nachfolgeranmeldung.
Öffentliche Materialattestierungen erhalten historische Hostbelege ohne alte
private Schlüssel. Abschluss und Wiederanlauf behalten die ursprüngliche
Request-ID; nicht verwaltetes Altmaterial bleibt ausdrücklich erhalten.

Einzelheiten, lokale Belege und offene native Grenzen stehen im
[Cleanupvertrag](AP12-CLEANUP.md). Dieser historische Quellnachtrag war noch kein
Produktivabschluss. Der aktuelle d9-Betriebsnachweis und seine offenen Grenzen
stehen in der [Übergabe](AP12-UEBERGABE.md).

Primärquellen:
[Microsoft addKey](https://learn.microsoft.com/en-us/graph/api/application-addkey?view=graph-rest-1.0),
[Microsoft removeKey](https://learn.microsoft.com/en-us/graph/api/application-removekey?view=graph-rest-1.0),
[Graph PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.applications/add-mgapplicationkey?view=graph-powershell-1.0).
