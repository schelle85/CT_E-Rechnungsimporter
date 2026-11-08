# Betriebsstand

Stand: 8. November 2026. Dieser Nachweis beschreibt geprüfte Infrastruktur und
den begonnenen Graph-Anschluss, keine fertig installierte Anwendung.

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

## AP00: Graph-Grundanbindung begonnen

- AP00 ist ausdrücklich freigegeben; nachfolgende AP noch nicht.
- Dedizierte Single-Tenant-App registriert, ohne Redirect-URI oder Client-Secret.
- App- und Service-Principal-Identitäten intern getrennt dokumentiert.
- Bisher erteilte Administratorzustimmung umfasst nur delegiertes `User.Read`;
  damit ist kein unbeaufsichtigter Mailzugriff nachgewiesen.
- Postfachrechte über Exchange Application RBAC durch DEV vorbereitet und
  Einrichtungsschritte von REVIEW unabhängig geprüft.
  Geplant sind `Application Mail.ReadWrite` und `Application Mail.Send` mit
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
- Die Anlage der App-Rollenzuweisung wird von Exchange mit einem administrativen
  Delegierungsfehler abgewiesen, obwohl aktive Delegierung und effektive
  Administratorzuordnung lesend angezeigt werden. Auch nach gezielter erneuter
  Anmeldung noch offen. Keine zusätzliche Administratorrolle als Versuch vergeben.
- Effektive Rollenzuweisungen und echte positive/negative Graph-Zugriffstests
  stehen noch aus. Keine Testmail gesendet.

## AP00: Microsoft-Supportklärung

Am 08.11.2026 wurde der reproduzierbare Exchange-Delegierungsfehler über den
delegierten Partnerzugang als Microsoft-Serviceanfrage eröffnet. Status bei
Anlage: offen, Schweregrad C (Inbetriebnahme blockiert, kein Produktionsausfall).
Die geprüften Berechtigungsbefunde und der Reproduktionsbefehl wurden übergeben.
Fallnummer, Kontaktdaten und technische Identitäten bleiben in den internen
Betreiberunterlagen. AP00 bleibt bis zur Klärung und den noch ausstehenden
Berechtigungs-/Graph-Nachweisen offen.

## Noch nicht nachgewiesen

AD-, Graph-, Docker- und Anwendungsbereitschaft sind durch diese Infrastrukturtests
nicht bestätigt. Die AP00-Freigabe ersetzt keine technische Gesamtabnahme.
Wöchentliche Wartung ist geplant, noch kein Skript/Timer auf dem Server installiert.
