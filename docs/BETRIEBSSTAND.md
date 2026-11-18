# Betriebsstand

## Aktueller Stand: 18. November 2026, AP12 / AP10-Quelllieferung

Produktlaufzeit `d9f32a5a9c9fb642f59a13ed2550f74532fc3ebe`, Schema008.
Echter zweiter Graphwechsel committed/new mit drei Verbrauchern, eigenem
Abschlussproof und SQL overlap unabhängig nativ bestätigt. Erster Versuch
kontrolliert zum Originalmaterial zurückgekehrt, Ursache weiterhin offen.
Genau ein kontrollierter AP12-Kundenboot mit erhaltenen API-/DB-/Nginxdiensten
und Images, neuem Graphmaterial sowie gesunden sieben Timern/CIFS/HTTPS bestätigt.
Lesende Aufnahme am 17.11.2026 bestätigt diesen Betrieb und Gate allowed.
Produktive Altkeybereinigung und zukünftiger automatischer Auslöser bleiben offen.
Qualifizierte Wiederaufnahmegrenzen einschließlich des ursprünglichen fehlgeschlagenen
Restorehelper-Aufrufs stehen in der [AP12-Übergabe](AP12-UEBERGABE.md). Kein
vollständiger VM-/Offsite-Restore daraus.

AP09 ist freigegeben; [Technikunterlage](TECHNISCHE-DOKUMENTATION.md), PDF und
KI-Wiedereinstieg sind abschließend geprüft. [Übergabe](AP09-UEBERGABE.md).
AP11 seit17.11.2026 freigegeben: Nutzerhandbuch mit Bildern und PDF eigengeprüft
vorhanden und am festen Stand b565465 genau einmal unabhängig mit PASS geprüft.
AP09a übernimmt diese eine Anleitung; Kundenrückmeldung bleibt offen. Ein
vertrauliches Betriebsblatt wird separat übergeben. Mailgestaltung nur geplant.

AP10 ist seit 18.11.2026 freigegeben. [Wartungshülle](AP10-WARTUNG.md) und
[Einrichtungs-/Rückwegplan](AP10-EINRICHTUNG.md) sind lokal geliefert; 22 gezielte
Tests bestanden. Quellenreview, native Linuxprüfung, heutiger frischer Hostbestand,
Installation und erster echter Sonntagslauf bleiben offen. Kein APT-/Rebootlauf
aus dieser Lieferung. API-/Workerimages bleiben d9/008; die geplante Änderung der
Host-Stopfunktion ist separat ausgewiesen. AP09-/AP11-Abgaben unverändert.

Die folgenden früheren Abschlüsse bleiben datierte historische Nachweise.
Aussagen zu damaligen Quellen, fünf Timern, Schema007 oder späteren AP ohne Go
sind keine aktuelle AP12-Betriebsbeschreibung.

## Historischer AP08-Abschluss

Historischer Stand: 16. November 2026. AP08 ist aus
`413095f823702d39b02bc8b3c989b526fdf808d0` bereitgestellt. Neue API/Web und
Processing-/Notificationquelle sind gebunden; getrennte Base-Readbacks bestätigen
erhaltene DB-ID/Startzeit, DBzeilen und Konfiguration sowie Schema 007/Instanz.
HTTPS ist ready/journal mit derselben Instanz. Bestehende PDF-Vorschau verwendet
lesenden Graphabruf und ein privates Tmpfs mit 128 MiB; dessen tatsächlicher Mount ist bestätigt.

Echte externe HTTPSübernahme mit changed=true und anschließender No-op mit
changed=false sind getrennt bestätigt. Vertrauenswürdiger öffentlicher Peer bis
12.02.2027 gültig; Schema, Instanz und Konfiguration bleiben erhalten.
Reiner Notificationvorlauf und separater Readback bestätigen Version 1, drei
privat verwaltete Empfänger und Tages-/Wochenvorschauen mit 0 Zählwerten.
Ursprünglicher Testslot accepted/Reservierung 1/HTTP 202 erhalten; keine neue Testmail.

Startdienst und fünf Timer sind seit 16.11.2026 19:44:23 Europe/Berlin
enabled/active. Inbox alle 5 min, Korrekturen alle 15 min, Notifications jede Minute, TLS stündlich und
Status jede Minute; Kalender Europe/Berlin. Frische gebundene Statusprojektion active
separat bestätigt; Status wird jede Minute publiziert.

Erste geplante Korrekturen um 19:45 erfolgreich mit 0 Quanten / 0 remaining. Eingang um 19:45
wegen gemeinsamer Sperre deferred, nächste tatsächliche Gelegenheit um 19:50
ebenfalls erfolgreich mit 0 Quanten / 0 remaining. Normale Queuefairness beobachtet;
diese Leerlaufläufe sind kein belegter Rechnungsimport. Die Notificationjobs
19:45/19:46 haben den vorbereiteten Tages-/Wochenbericht je einmal mit HTTP 202
angenommen; weitere normale Läufe ohne zusätzliche Sendung. Der ursprüngliche
Testslot bleibt accepted/eine Reservierung/202. Keine unbekannten oder offenen
Postwirkungen; Graphannahme ist keine Zustellbestätigung.

Preboot-Gate um 19:50:28 Europe/Berlin bestätigt alle Worker inaktiv, keine
Operationscontainer und drei eindeutig angenommene Slots. Der erste geplante
TLS-Stundenlauf um 20:00 ist mit changed=false, gleichem Peer und status_recorded=true
bestätigt; die vorherige reale TLSübernahme bleibt ein eigener Nachweis.

Kontrollierter Reboot erfolgt: neue Boot-ID, gleiche API-/Web-/DBcontainer-IDs
und Images, gesundes HTTPS mit übernommenem Peer, beide CIFSmounts,
Schema/Instanz/Konfiguration und ursprünglicher Testslot erhalten. Weitere
Nachboot-Inboxläufe: 0 Quanten / 0 remaining; alle drei Mailbelege accepted/ein Versuch/202.
Der frische Nachbootstatus kann beim laufenden Notificationjob konservativ
degraded/unknown melden. Status- und Notificationtimer liefen bislang gleichphasig.
Nach dem Reboot wurde am 16.11.2026 um 20:15:08 Europe/Berlin separat der persistente
Statusphasen-Drop-in `10-phase.conf` gesetzt: genau ein effektiver Kalender
`*-*-* *:*:20 Europe/Berlin`, Ziel invoice-status.service, Timer active/enabled.
Anwendung, Hostskripte und Images bleiben unverändert auf 413095f. Drei
aufeinanderfolgende automatische Kontrollzyklen am 16.11.2026 um 20:16:21,
20:17:21 und 20:18:21 Europe/Berlin bestätigen jeweils active, den seit 15 Sekunden
abgeschlossenen Notificationlauf und running=false. Boot-/Quellbindung, Drop-in,
Dienstziel und übrige Wiederanlaufprüfungen sind bestätigt; kein manueller
Collector wurde gestartet. Die technische Serverabnahme und AP08 im vereinbarten
Umfang sind abgeschlossen. Der Versatz wurde nach dem belegten Reboot gesetzt;
ein zweiter Reboot oder vollständiger VMrestore ist damit nicht nachgewiesen.
Siehe [AP08-Betrieb](AP08-BETRIEB.md).

Die isolierte C-GUIprüfung umfasst drei Desktopgruppen und Mobile 390 × 844 mit
tatsächlichen C-Webassets/eigener HTTPSbindung und synthetischen APIantworten.
Sie ersetzt keine neue tatsächliche Kunden-/AD-Anmeldung. Frühere isolierte
A-/TLS-/Status-/Wiederanlaufnachweise bleiben nach ihrem konkreten Umfang getrennt.

## Historischer AP07-Abschluss vom 15. November 2026

Stand: 15. November 2026. AP07 ist technisch abgeschlossen und bereitgestellt aus
Codepin `5ecfd59270b63947d3f92af98a1b9f8e5a267aeb`. Kundenschema007 sowie API und
Web aus derselben festen Quelle wurden getrennt erfolgreich zurückgelesen.
Bestehende Instanzkennung, LDAP-Konfiguration und Datenbankdienst sind erhalten.

Administration → Berichte mit echten Journal-/Tages-/Wochenübersichten und
Zeitraumwahl, Benachrichtigungseinstellungen, feste Vorschau/Testaktion und
Versandhistorie sind geliefert. Die exakten Graph-Zertifikatsschwellen 10d/1d/0/
negativ einschließlich zusätzlichem Loginhinweis gelten für beide Rollen.

A/B sind vollständig geprüft, C-Quellenreview und 21 C-Fälle auf MariaDB bestanden.
Acht isolierte HTTPS-Browsergruppen belegen unter anderem den vollständigen
Fristfall mit 80,006 s, Antwortverlust, neue Sitzung und Konfigurationsversion ohne
Doppel-POST. Ein zusätzlicher synthetischer manueller CLIplan ist geprüft.
Diese isolierten Rollenprüfungen sind keine neue tatsächliche Kundenanmeldung
nach AP07; die echte AD-Abnahme aus AP01 bleibt der historische Nachweis.

Ein eigenständiger Notificationkey, eine getrennte minimale manuelle CLI und
drei privat initialisierte Empfänger sind eingerichtet. Echte Graph-
Zertifikatsanmeldung war erfolgreich. Genau eine feste Testmail wurde mit
HTTP 202 angenommen; Reservierung 1 und Status wurden getrennt bestätigt.
Der Empfang ist im eigenen Abnahmepostfach nachgewiesen. Für die beiden anderen
Empfänger liegt damit kein Empfangsnachweis vor.

Zum AP07-Abschluss waren Import-, Korrektur- und Benachrichtigungsautomatik inaktiv.
Gespeicherte Zeiten allein aktivierten keine dauerhaften Jobs. Die spätere
Aktivierung ist im aktuellen AP08-Block oben beschrieben.
AP09/10/11 bleiben ohne Umsetzungs-Go. AP11 bleibt geplant. Stichtag
1. Dezember 2026, eingefrorene AP03-Erkennung und DMS-Abgrenzung sind unverändert.
Interne Laufzeitnachweise, Verbindungswerte, Empfänger und geschützte Hostpfade
bleiben in den separaten Betreiberunterlagen.

Die folgenden datierten Infrastruktur- und Einrichtungsergebnisse dokumentieren
historische Teilstände, insbesondere AP00/AP01a/b vom 8. November mit Nachträgen.
Sie ersetzen nicht den aktuellen [Arbeitsplan](ARBEITSPLAN.md),
[AP05-Vertrag](AP05-PROCESSING.md), [manuellen Runtime-Stand](AP05-RUNTIME.md)
und die Verträge für [AP06](AP06-WEB.md) und [AP07](AP07-NOTIFICATIONS.md).

## AP00: SSH-Zugang

- Der Betreiber hat den ED25519-Hostfingerprint über die VM-Konsole bestätigt.
- Anmeldung mit dem vorgesehenen öffentlichen Schlüssel erfolgreich getestet.
- Administrative Ausführung für die beauftragte SSH-Umstellung geprüft.
- SSH-Konfiguration gesichert, Drop-in für ausschließliche Schlüsselanmeldung gesetzt.
- `PasswordAuthentication no`, `KbdInteractiveAuthentication no`,
  `PubkeyAuthentication yes`, `AuthenticationMethods publickey` sind wirksam.
- Konfiguration vor Neuladen mit `sshd -t` und effektiver Auswertung geprüft.
- Dienst neu geladen; eine danach neu aufgebaute Schlüsselverbindung war erfolgreich.
- Ein Versuch ohne Schlüssel wurde abgewiesen; der Server bot nur `publickey` an.
- SSH-Dienst anschließend aktiv; keine VM neu gestartet.

Interne Adressen, Benutzerwerte, Hostschlüssel, Sicherungspfad und
Zugangskonfiguration bleiben in den separat verwalteten Betreiberunterlagen.

## AP00: SMB-Einbindung und Rechte

- SSL- und Importfreigabe über Host-`fstab` mit SMB 3.1.1 eingebunden.
- SSL nur lesend; Linux-Verzeichnisse 0550, Dateizuordnung 0440, Zugriff über
  vorgesehene Administratorgruppe. Importablage für den vorgesehenen Benutzer
  und seine Gruppe schreibbar: Verzeichnisse 0770, Dateizuordnung 0660.
- Beide serverseitigen Credential-Dateien root-eigen und 0600; Inhalte nicht offengelegt.
- Kategorieordner `E-Rechnung`, `PDF`, `Zahlungsavis` angelegt.
- Eindeutige leere Testdateien im Importer und allen drei Kategorieordnern angelegt
  und wieder entfernt. Keine echten Dokumente verändert.
- SSL-Lesezugriff und fehlender Schreibzugriff als vorgesehener Benutzer geprüft.
- `fstab` ohne Parse-/Mountkonfigurationsfehler geprüft, erzeugte Mountunits aktiv.
- Kein VM-Neustart; tatsächlicher Wiederanlauf nach Reboot noch nicht nachgewiesen.

Quellen, Credentialpfade und konkrete Benutzer-/UID-Zuordnung sind ausschließlich
in den separaten Betreiberunterlagen dokumentiert. Containeranbindung und
Startabhängigkeiten der Anwendung folgen erst im jeweiligen DEV-Paket.

## AP00: Graph-Grundanbindung geprüft

- AP00 ist abgeschlossen; AP01 ist inzwischen ausdrücklich freigegeben.
- Dedizierte Single-Tenant-App registriert, ohne Redirect-URI oder Client-Secret.
- App- und Service-Principal-Identitäten intern getrennt dokumentiert.
- Bisher erteilte Administratorzustimmung umfasst nur delegiertes `User.Read`;
  damit ist kein unbeaufsichtigter Mailzugriff nachgewiesen.
- Postfachrechte über Exchange Application RBAC durch DEV vorbereitet und
  Einrichtungsschritte von REVIEW unabhängig geprüft.
  Eingerichtet sind `Application Mail.ReadWrite` und `Application Mail.Send` mit
  einem auf das Zielpostfach begrenzten Resource Scope. Zusätzliche tenantweite
  Entra-Mailrechte würden die Einschränkung umgehen und sind nicht vorgesehen.
- Dediziertes RSA-3072/SHA256-Anmeldezertifikat auf der Ziel-VM erzeugt;
  Schlüsselzuordnung geprüft, lokales Credential-Verzeichnis root-eigen 0700,
  private Dateien 0600. Nur öffentliches Zertifikat zum Portal übertragen.
- Öffentliches Zertifikat durch Betreiber registriert; Fingerabdruck und Laufzeit
  im Portal mit der lokalen Kopie abgeglichen. Privater Schlüssel bleibt auf der VM.
- Exchange-Service-Principal-Zeiger angelegt. Einmalige Organisationsanpassung
  nach Microsoft-Voraussetzung aktiviert; `IsDehydrated=False` nachgelesen.
- Resource Scope anhand stabiler Postfach-Objekt-ID angelegt; gespeicherten Filter
  erneut ausgewertet und genau ein vorgesehenes Postfach bestätigt.
- Nach drei administrativen Delegierungsfehlern gelang am 08.11.2026 um
  19:39 Uhr Europe/Berlin eine einzelne erneute ReadWrite-Zuweisung in frischer
  Sitzung. Reguläre Verwaltungsrechte und delegierende Application-Rechte waren
  bereits vorhanden; keine zusätzliche Administratorrolle wurde vergeben.
- Rücklesen bestätigt beide aktivierten Rollen am selben Service Principal und
  unveränderten Ein-Postfach-Scope. Exchange-RBAC-Prüfung: beide Rollen für das
  vorgesehene Postfach erlaubt, separat bestätigtes Kontrollpostfach ausgeschlossen.
- Tatsächliche Zertifikatsanmeldung von der Ziel-VM erfolgreich. Begrenzter
  Inbox-Metadatenzugriff liefert beim Ziel HTTP200 und beim Kontrollpostfach403;
  keine Rechnungs- oder Anhanginhalte abgerufen.
- Der Betreiber korrigierte die Primäradresse des synchronisierten Postfachs in
  der lokalen Verwaltungsquelle. Cloudübernahme vor Versand bestätigt; kein
  globaler Aliasversand aktiviert und keine Postfachumwandlung vorgenommen.
- Erster synthetischer Versandversuch um20:29 Uhr mit403 abgewiesen. Nach über
  30 Minuten vollständiger App-API-Ruhe genau ein abgestimmter neuer Versuch:
  HTTP 202 um21:00 Uhr; tatsächlicher Empfang mit eindeutigem Testbetreff und
  vorgesehenem Geschäftsabsender separat im Empfängerpostfach nachgewiesen.
  Einmalmarker und historische Ergebnisse erhalten, kein weiterer Versand.
- Berechtigungscache ist eine plausible Erklärung des vorübergehenden403;
  aus dem späteren Erfolg lässt sich die genaue Ursache nicht beweisen.

## AP00: VM, LDAP- und HTTPS-Voraussetzungen

- Linux-Version und Ressourcen der bereitgestellten VM erfasst, internes DNS
  und Schlüsselzugang erneut geprüft. Zugriff weiterhin nur im Kundennetz.
- LDAP-Dienstkonto und direkte Berechtigungsgruppen laut Betreiber vorhanden.
- Bestehende öffentliche interne CA aus einem bereits vertrauenswürdigen
  Windows-Zertifikatsspeicher exportiert und anwendungsspezifisch auf der VM
  abgelegt. Keine neue CA und kein privater CA-Schlüssel erzeugt/übertragen.
- Alle drei vorgesehenen LDAPS-Endpunkte mit CA-, Ketten- und Hostnamenprüfung
  erfolgreich geprüft; keine unsichere TLS-Ausnahme. LDAP-Bind und Benutzer-/
  Gruppenrechte werden erst im vorgesehenen AP01-Paket implementiert und getestet.
- Vorhandenes Wildcard-PFX passt zum internen Webhost und ist gültig.
  HTTPS-Webbetrieb und geschützte Schlüssel-/Kettenübernahme sind inzwischen
  im unten beschriebenen AP01a/b-Umfang geprüft.
- Isolierte Python-Testumgebung für die Graph-Abnahme mit dokumentierter
  Paketliste eingerichtet. Die spätere AP01-Webvorschau läuft separat in Docker.
- Tägliche VM-/Offsite-Sicherung einschließlich SMB-Server vom Betreiber
  bestätigt. Ein Wiederherstellungstest ist damit nicht nachgewiesen.

## AP00: Microsoft-Supportklärung

Am 08.11.2026 wurde der reproduzierbare Exchange-Delegierungsfehler über den
delegierten Partnerzugang als Microsoft-Serviceanfrage eröffnet. Status bei
Anlage: offen, Schweregrad C (Inbetriebnahme blockiert, kein Produktionsausfall).
Die geprüften Berechtigungsbefunde und der Reproduktionsbefehl wurden übergeben.
Fallnummer, Kontaktdaten und technische Identitäten bleiben in den internen
Betreiberunterlagen. Der spätere ReadWrite-Erfolg wurde Microsoft gemeldet.
Für den behobenen Rollenanlagefehler wurde die Schließung der Serviceanfrage
erbeten; eine Schließungsbestätigung steht noch aus.
Verzögerte Provisionierung bleibt eine mögliche, nicht bestätigte Erklärung.
Die frühere Rollenanlageblockade ist behoben; Graph-Lesezugriff und Versand
sind inzwischen tatsächlich nachgewiesen. Die automatische Support-Mailprüfung
wurde auf Betreiberwunsch vollständig abgeschaltet.

## AP01a/b: Design und HTTPS-Grundbetrieb

AP01 ist inzwischen freigegeben. Die Containerlaufzeit aus den offiziellen
Ubuntu-Paketquellen ist installiert und zurückgelesen: Docker29.1.3,
Compose2.40.3 und Buildx0.30.1. Die Dienste laufen, bestehende Mount- und
Credentialrechte sind erhalten; keine zusätzliche Docker-Gruppenmitgliedschaft.
Quellarbeit und Datenbank liegen auf lokalem VM-Speicher getrennt von der
SMB-Dokumentablage. Der feste Quellstand `13bc3047` wurde unabhängig mit Astra
geprüft und anhand der Betriebsbelege im vereinbarten A/B-Umfang abgenommen.

- React-/TypeScript-Vorschau mit synthetischen Vorgängen, Filtern, Details und
  deaktivierter Administration auf Desktop und Mobilgerät bedient und gesichtet.
- FastAPI, MariaDB und Nginx laufen als getrennte Container. Nur Nginx veröffentlicht
  HTTP/HTTPS an der vorgesehenen privaten Schnittstelle; API/DB ohne Hostports,
  Datenbanknetz intern. HTTP leitet mit308 auf HTTPS um.
- Tatsächlicher Zugriff aus dem Kundennetz/VPN mit gültiger Zertifikatskette und
  Hostnamenprüfung erfolgreich; API-Readiness200. TLS-Schlüssel nur für Nginx lesend.
- Drei Startprobleme behoben: Alembic-Importpfad, MariaDB-Singleton-DDL und
  Docker-Portveröffentlichung am Webnetz. Feste Korrekturen vor erneuten
  Kundentests unabhängig geprüft; reale MariaDB-/CLI-/HTTP-Proben erfolgreich.
- Alle drei Anwendungscontainer neu angelegt: neue Container-IDs bei unveränderten
  Images, Mounts und persistentem Metadatenbezeichner. Kein Datenverzeichnis gelöscht.
- Kontrollierte TLS-Releaseübernahme mit geprüftem vorhandenem Material,
  atomarem Linkwechsel, erfolgreichem Konfigurationstest und Reload geprüft.
  Neue Nginx-Worker und weiterhin gültiges Live-HTTPS nachgewiesen.
- Bestehende CIFS- und Credentialrechte nachgelesen. Vorschau ohne Graph-,
  LDAP- oder Rechnungszugriff; Administrations-GET/POST liefern403.

## Damalige offene Punkte des AP00/AP01a/b-Stands

Die Infrastrukturtests und Graph-Einzelproben ersetzen keine Anwendungsabnahme.
Echte LDAP-Benutzeranmeldung, wirksame Gruppenrechte, sichere Sitzungen und
geschützte Administration folgen innerhalb des laufenden AP01c/d/e. Der lesende
LDAP-Dienstbind und die Suche der vorgesehenen direkten Gruppen wurden vorgeprüft;
dies ersetzt keine Benutzer-/Rollenabnahme. Mailordner/Fahnen/Verschieben und
Rechnungsverarbeitung folgen erst in späteren freizugebenden AP.
Die TLS-Probe mit identischem Material belegt keinen externen 60-Tage-Erneuerungslauf
oder tatsächlichen Zertifikatsfehler-Rollback.
Nach Neustart durchgängiger Wiederanlauf und vollständiger Restore sind offen.
Wöchentliche Wartung ist geplant, noch kein Skript/Timer auf dem Server installiert.

Aktueller Abgleich: Anmeldung, Gruppenrechte und Administration sind inzwischen
in AP01 abgenommen; Graphaktionen in AP02 und der gemeinsame manuelle Pfad in AP05
geprüft. Die historischen Aussagen „folgen erst“ sind dadurch überholt. Durchgängiger
Wiederanlauf, vollständiger Restore und dauerhafte Automatik bleiben den späteren
freizugebenden Paketen zugeordnet; AP05 aktiviert keine Wartung oder Timer.
