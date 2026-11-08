# Betriebsstand

Stand: 8. November 2026. Dieser Nachweis beschreibt geprüfte Infrastruktur und
den geprüften Graph-Anschluss. AP00-Grundbereitschaft und AP01a/b sind nach
unabhängiger Prüfung bestätigt. Die installierte Webvorschau ist synthetisch;
AD-Anmeldung und Administration werden in AP01c/d/e umgesetzt.

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
  HTTP202 um21:00 Uhr; tatsächlicher Empfang mit eindeutigem Testbetreff und
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

## Noch nicht nachgewiesen

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
