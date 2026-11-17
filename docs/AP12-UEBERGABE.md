# AP12 – Lieferstand und Übergabe an Betrieb und Dokumentation

Stand: 17. November 2026. AP12 ist aus `d9f32a5a9c9fb642f59a13ed2550f74532fc3ebe`
bereitgestellt, Schema008. Der echte Zertifikatswechsel ist unabhängig nativ bestätigt:
`committed/new`, SQL-Zustand `overlap`, alle drei Verbraucher und eigener
Abschlussproof. Genau ein kontrollierter AP12-Kundenboot ist erfolgt. Danach sind
Kunden-API, Datenbank und Nginx unverändert erhalten; neues Graph-Zertifikat,
sieben Timer, CIFS und HTTPS sind bestätigt. Die qualifizierten
Wiederaufnahmebelege und ihre Grenzen stehen weiter unten.
Produktive Altkeybereinigung nach Ablauf der Überlappung bleibt gesondert offen.

Der erste echte Wechselversuch endete kontrolliert auf dem alten Zertifikat; seine
ursprüngliche Fehlerursache bleibt unbelegt. Ein ausdrücklich getrennter zweiter Auftrag
wurde nach lesendem Abgleich seiner unklaren Registrierung unter derselben
ursprünglichen Auftragsidentität erfolgreich fortgesetzt. Der erste Fehlversuch und sein
registrierter Kandidat bleiben getrennt erhalten; der Erfolg des zweiten belegt keine
nachträgliche Erklärung oder Behebung der ersten Ursache.

## Führende Teilverträge

| Bereich | Gelieferter Ablauf | Maßgeblicher Vertrag |
| --- | --- | --- |
| Graphgrenze und Übernahme | Gebundene Freigabe, drei Verbraucher, eigener Abschlussproof, Rückweg und ursprünglicher Auftrag | [Hostablauf](AP12-HOSTABLAUF.md) |
| Bereinigung | Begrenzte Überlappung, nur eigene Altkeys, unklarer POST nur lesend abgleichen, alte Dateien gezielt entfernen | [Cleanup](AP12-CLEANUP.md) |
| Bedienung | Administration → Graph-Zertifikat, Rollen, Status, Historie, dauerhaft gebundene Erneuerungsabsicht | [Admin/API](AP12-ADMIN-API.md) |
| Automatik | 03:35 Europe/Berlin, Minutenlauf Sekunde40, ein Tagesplatz, ursprüngliche Automatikabsicht, Statusdatei | [Zeitplanung](AP12-AUTOMATIK.md) |
| Vorhandenes Zertifikat | Ausdrückliche Rootentscheidung mit geprüftem Eigentumsnachweis und lesendem Appabgleich | [Zuordnung](AP12-OWNERSHIP.md) |

Vorhandene Kryptografie-/Azure-Identity-/HTTPX- und AP07/AP08-Bausteine bleiben die
Grundlage. Es wird kein zusätzlicher Dienst oder kostenpflichtiger
Zertifikatsmanager eingeführt. Neue Logik betrifft ausschließlich den gebundenen
Auftrag, die kontrollierte Verbraucherübernahme und deren Bedien-/Betriebsnachweise.

## Nachweisstand

Kern B und C1 sind im beschriebenen isolierten Umfang unabhängig nativ bestätigt.
C2a-UID10001-Integration und C2B-R1-Frist sind separat nativ abgeschlossen. Auf
Pin `24bb7568d92d384319d7ed42c5f2947829b9ddc6` sind Vorbereitung, Bootstrap,
Normalwechsel und ausdrücklicher Rückweg nach bestätigter neuer Übernahme nativ
unabhängig bestätigt: Linux/Docker/MariaDB/Dateien/HTTPS tatsächlich, Entra und SDK
synthetisch. Genau ein addKey, kein removeKey; drei Verbraucher und jeweils
getrennter Abschlussproof. Das ist keine vollständige C3-Fehler-/Bootabnahme.

C4, C5 einschließlich Abwesenheitskorrektur der GETquittung und C6 haben einen
unabhängigen Quellen-/lokalen Nachweisreview bestanden. Der damalige C7-Lieferstand ist mit zwölf neuen
und sechs betroffenen lokalen Fällen dokumentiert. Die inzwischen tatsächliche
Rootzuordnung und der echte Wechsel sind davon getrennte Betriebsnachweise. Zähler und feste Belege werden intern geführt, ohne
private Betriebsdaten oder Abrechnungsangaben in dieses Repository zu übernehmen.

Die Bereitstellung aus d9 erhält die ursprüngliche Instanz, Konfiguration und
Datenbank sowie die alten Datentabellen bei additivem Schema008. Geschützte
Dateirechte, verschachtelte RO-Bindungen, HTTPS, ausdrückliche Rootzuordnung und
die drei tatsächlichen Graphverbraucher sind getrennt nachgelesen. Die isolierten
Browsergruppen einschließlich fachlicher Sichtung sind abgeschlossen; sie sind
keine neue tatsächliche Kunden-/AD-Anmeldung.

### Kontrollierter Boot und qualifizierte Wiederaufnahme

Es erfolgte genau ein AP12-Kundenboot. Danach sind dieselben Kunden-API-,
Datenbank- und Nginxcontainer mit unveränderten Images erhalten; das neue
Graph-Zertifikat ist aktiv, alle sieben Timer sowie CIFS und HTTPS sind gesund.
Siegel und sämtliche Verbraucher-/Abschlussquittungen wurden getrennt gelesen.

In der isolierten Rückwegprüfung bestand der Generalstart mit dem ursprünglichen,
bereits zurückgerollten alten Material. In der isolierten Pauseprüfung ging die
temporäre Lockablage durch den echten Boot verloren; der Generalstart bei
vorbereiteter neuer Übernahme und erhaltener Pause bestand. Deren Datenbank und
Nginx blieben erhalten, die API wurde dabei wie vorgesehen neu erstellt.
Beide Prüfaufträge behalten jeweils genau eine Registrierung und keine Entfernung.

Der erste Restore-Aufruf bleibt als fehlgeschlagen mit `AssertionError` erhalten;
seine Ursache ist nicht belegt. Der anschließend ausschließlich lesend
bestätigte Restorezustand qualifiziert den Zustandsnachweis, macht aber den
ersten Aufruf nicht erfolgreich. Weder Start noch Boot wurden dafür wiederholt.
Daraus folgt keine pauschale Abnahme sämtlicher historischer Fehler-/Pausefenster.

Die spätere tatsächliche produktive Bereinigung nach Ablauf der Überlappung
sowie nicht separat abgeschlossene historische Einzelprüfungen bleiben offen.

## Übergabefakten für AP11

GR_CEO liest den Reiter, GR_Rechnung darf mit aktueller ADprüfung verwalten.
„Jetzt erneuern“ speichert zunächst einen Auftrag. Erst bestätigte Verbraucher
und Abschlussproof belegen die Übernahme. Unklarer HTTPausgang wird anhand
derselben ursprünglichen UUID abgeglichen; eine leere Abfrage allein gestattet
keinen neuen Auftrag. Bei fremder aktiver Anforderung wird kein zweiter gestartet.

Die Oberfläche trennt letzten Erneuerungsversuch, erfolgreiche Tagesprüfung,
zusätzlichen aktuellen AP07-Anmeldenachweis und erfolgreiche Erneuerung. Sie
zeigt alte/neue Zertifikate, Überlappung, ausstehende Bereinigung und unverwaltetes
Altmaterial. Private Schlüssel und interne Rootbelege bleiben außerhalb des Browsers.

Die gespeicherte Automatikeinstellung ist von tatsächlich aktiven Hosttimern
getrennt. Ausschalten verhindert neue automatische Anforderungen, verwirft aber
keinen bereits angenommenen Auftrag. Manuelle Aufträge werden auch bei
ausgeschalteter automatischer Erneuerung bearbeitet. Ein alter oder unpassender
Hoststatus wird unbestätigt; der nächste Prüftermin benötigt tatsächliche
systemd-Daten. AP11 übernimmt diese inzwischen bereitgestellten und isoliert
geprüften Bedienfakten mit den genannten Grenzen.

## Betriebsgrenzen und Wiederherstellung für AP09

Bei fehlgeschlagenem oder unklarem Wechsel zuerst die ursprüngliche UUID,
SQLquittung, Gatebindung und privaten Hostbelege sichern und abgleichen.
`resume`/`rollback` sind feste Betreiberwege für genau diese nachgewiesene Bindung.
Ein unbekannter addKey-/removeKey-Ausgang erlaubt keinen erneuten POST. Keine
Journale löschen, keinen Nachfolger neu erzeugen und keine Freigabedatei von Hand
öffnen, um einen blockierten Zustand zu übergehen.

Ein Rückweg benötigt die ursprünglichen gültigen privaten Altbytes und erneut
bestätigte Verbraucher sowie einen eigenen Abschlussproof. Nach tatsächlicher
Altkey-/Altdateientfernung stehen diese Bytes nicht für einen Rückweg zur Verfügung.
Die öffentliche Materialattestierung hält historische Belege lesbar und ersetzt
keinen privaten Schlüssel. Bewusste Graphpause und fremder Drain bleiben erhalten.

Die tägliche Prüfung ist ab Solltermin+2h ohne Versuch überfällig. Bei höchstens
24h Restgültigkeit muss innerhalb einer Stunde eskaliert werden; unter einer
Stunde ist unmittelbare Betreiberhilfe nötig. Automatik beginnt dann keinen neuen
Wechsel. Ein bereits aktiver Vorgang wird anhand seines tatsächlichen Stadiums
abgeglichen. AP07-Warnung ab zehn Tagen und rote Resttages-/Ablaufhinweise bleiben.

Sind alle nutzbaren Appzertifikate abgelaufen oder fehlen passende private Bytes,
ist der normale Selbstrotations-/Rückweg nicht ausführbar. Der administrative
Wiederherstellungsauftrag hat folgende getrennt zu prüfende Schritte:

1. Betroffenen Betrieb pausieren und ursprüngliche Gate-/SQL-/Journal-/Material-
   Bindungen privat dokumentieren. Den noch unbekannten Vorgang erhalten.
2. Berechtigten Entraadministrator und Betreiber anhand der bestehenden eigenen
   App-/Instanzbindung zusammenführen. Ein neues Zertifikat wird auf dem Host
   erzeugt; nur sein öffentlicher Teil darf zusätzlich registriert werden.
3. Vor einem Materialtausch den konkreten geschützten Wiederherstellungsablauf
   festlegen und prüfen: vorhandene unbekannte Wirkungen, tatsächliche Verbraucher,
   Dateibindungen, erhaltene Journale und neue Freigabe müssen zusammenpassen.
   Der normale Bootstrap lehnt ein gegenüber seinem Beleg ausgetauschtes Material
   ab; er ist kein pauschaler Resetweg nach manueller Dateiersetzung.
4. Neue Anmeldung, alle drei tatsächlichen Verbraucher, getrennten Abschlussproof,
   HTTPS und dauerhafte Bindungen nachweisen, bevor der Betrieb wieder freigegeben
   wird. Die manuelle Zuordnung erteilt diese Freigabe nicht.

Dieser administrative Ausnahmeablauf ist nicht als ausführbares automatisches
Resetwerkzeug geliefert oder nativ abgenommen. Sein konkreter Material-/Journal-
Übernahmeplan bleibt Teil des jeweiligen Wiederherstellungsauftrags. Eine
Warnmail über dieselbe ausgefallene Anmeldung ist keine Zustellgarantie;
unabhängige Betriebsüberwachung muss einen Ausfall außerhalb dieses Kanals melden.

## Bereitstellungsgrenze

Die durchgeführte Bereitstellung verwendet einen gemeinsamen festen
Quellstand für API/Web/Worker/Hostpeers, additive008 mit Bestanderhaltung,
geschützte Profile/RO-Bindungen und einen bestätigten Bootstrap. Die neuen
Unitdateien werden im Repository als deaktivierte Vorlagen geliefert. Im Betrieb
sind die beiden Rotationtimer separat aktiviert und nach dem Wechsel bestätigt. Runtimeprofile bleiben name/image; tatsächliche
Container-IDs gehören ausschließlich in private Hostbelege. AP08-Status und
HTTPS-Zertifikatsbetrieb bleiben eigenständige Verträge.

Der AP08-Statussammler akzeptiert im öffentlichen Statusverzeichnis zusätzlich
genau den vorgesehenen Unterordner `graph-access`: Rootbesitz, Gruppe10001,
Modus0750, geschützte Eltern und kein Symlink. Fremde Namen oder abweichende
Metadaten werden weiterhin abgewiesen. Der Sammler liest oder verändert den
AP12-Inhalt nicht; sein Statusschema mit vier Jobs bleibt unverändert. Die lokale
Profilprüfung verwendet ausdrücklich simulierte POSIX-Metadaten. Die tatsächliche
Bereitstellung hat Verzeichnisrechte, verschachtelte RO-Mounts und den gemeinsamen
Betrieb von Statussammler und Gate zusätzlich auf Linux bestätigt.
