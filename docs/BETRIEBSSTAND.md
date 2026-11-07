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

## Noch nicht nachgewiesen

SMB-, AD-, Graph-, Docker- und Anwendungsbereitschaft sind durch diesen SSH-Test
nicht bestätigt. Die allgemeine Startbedingung der Entwicklung bleibt offen.
Wöchentliche Wartung ist geplant, noch kein Skript/Timer auf dem Server installiert.
