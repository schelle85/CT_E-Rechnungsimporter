# Betriebsstand

Stand: 7. November 2026. Dieser Nachweis beschreibt ausschließlich die erfolgte
SSH-Zugangseinrichtung, keine fertig installierte Anwendung.

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

## Noch nicht nachgewiesen

AD-, Graph-, Docker- und Anwendungsbereitschaft sind durch diese Infrastrukturtests
nicht bestätigt. Eine allgemeine Bereitmeldung der Entwicklung steht noch aus.
Wöchentliche Wartung ist geplant, noch kein Skript/Timer auf dem Server installiert.
