# AP12 – Lieferstand und Übergabe an Betrieb und Dokumentation

Stand17.11.2026: AP12 ist zur Umsetzung freigegeben und als Quellstand bis zur
ausdrücklichen Rootzuordnung geliefert. Kundenbetrieb bleibt AP08/Schema007.
Diese Übersicht ist eine technische Übergabe, keine Meldung einer produktiven
AP12-Aktivierung und kein vorgezogenes Nutzerhandbuch.

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
unabhängigen Quellen-/lokalen Nachweisreview bestanden. C7 ist mit zwölf neuen
und sechs betroffenen bestehenden lokalen Fällen geliefert; sein unabhängiger
Review bleibt gesondert. Zähler und feste Belege werden intern geführt, ohne
private Betriebsdaten oder Abrechnungsangaben in dieses Repository zu übernehmen.

Offen bleiben weitere C3-Abbruch-/Boot-/Pausefenster sowie native Bereinigung,
Admin/API-/Browserrollen, Timer/Persistenz/Writerkonkurrenz, öffentliche
Dateirechte/Frische und Rootzuordnung. Reale Entra-/Kundenübernahme und
Produktivaktivierung sind getrennte Schritte. Ein Quellen-PASS oder lokales
Prüfergebnis ersetzt keinen dieser Nachweise.

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
systemd-Daten. AP11 übernimmt diese Bedienfakten erst nach entsprechender
Bereitstellung und Browserabnahme.

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

Für die spätere Bereitstellung braucht der Betreiber einen gemeinsamen festen
Quellstand für API/Web/Worker/Hostpeers, additive008 mit Bestanderhaltung,
geschützte Profile/RO-Bindungen und einen bestätigten Bootstrap. Die neuen
Unitdateien sind deaktivierte Vorlagen. Erst ihr tatsächlicher Rücklesebeleg
bestätigt Aktivität und Termine. Runtimeprofile bleiben name/image; tatsächliche
Container-IDs gehören ausschließlich in private Hostbelege. AP08-Status und
HTTPS-Zertifikatsbetrieb bleiben eigenständige Verträge.
