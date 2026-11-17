# AP12 – ausdrückliche Zuordnung eines bestehenden Zertifikats

Dieser Rootbedienweg liegt als lokal geprüfter Quellstand vor. Er wird weder durch
Bootstrap noch durch die Weboberfläche automatisch ausgeführt. Vorhandene Keys
bleiben ohne ausdrückliche Zuordnung unverwaltet und werden nicht bereinigt.

## Voraussetzungen und Eingaben

Der Betreiber prüft außerhalb der Anwendung, dass das aktuell geladene Zertifikat
ausschließlich zur fest gebundenen Importerinstanz gehört und später durch deren
bereits festgelegten Cleanupweg entfernt werden darf. Der private Nachweis hält
App-/Instanzzuordnung, Key-ID, tatsächlichen Zertifikatfingerprint, Prüfer und
Zeitpunkt fest. Sein SHA256 wird übergeben; das Programm prüft seine Form, nicht
den Inhalt des außerhalb gespeicherten Nachweises. Der Hash allein beweist keine
Eigentümerschaft. Ein passender Graphbestand ersetzt diese Betreiberentscheidung
ebenfalls nicht.

Der feste Aufruf ist `run-rotation.py attest-current --key-id <UUID>
--fingerprint <SHA256> --evidence <SHA256>` über das geschützte Hostprofil. Alle drei
Eingaben sind erforderlich. Es gibt keinen frei übergebenen Credentialpfad und
keine zu erzeugende Wechsel-ID. UUID und Hashes werden kanonisch geprüft.

Vorausgesetzt werden bestätigte Verbraucher des aktuellen Boots, erlaubte
Graphfreigabe, tatsächliche unveränderte gültige PEMbytes und kein aktiver
Rotationsauftrag. Ein Bootstrap muss seinen vollständigen versiegelten Abschluss
haben. Nach einer Rotation muss die aktuelle versiegelte Übernahme mit SQL
übereinstimmen; bei neuem Material gehört dazu abgeschlossener Cleanup. Ein
bestätigter Rückweg verlangt den abgeschlossenen failed/old-Auftrag. Pausen,
fremder Drain, unklarer Abschluss und laufende Überlappung sperren die Zuordnung.

## Begrenzter Abgleich

Der Host hält Writer → Lifecycle → Processing → Notification und bestätigt API
und HTTPSbereitschaft. Der Rootworker verwendet das bestehende private Journal
und die normale geteilte Graphfreigabe. Ein selektiver GET der eigenen App muss
genau einen passenden Key mit Fingerprint, Key-ID, Zertifikattyp, Nutzung und
exakter Gültigkeit des geladenen Zertifikats liefern. Er führt keinen addKey-,
removeKey- oder PATCH-Aufruf aus und wechselt keine Credentialdatei.

Vor dem Inventareintrag werden Freigabe und Material erneut geprüft. Der SQLhead
wird gesperrt und muss unverändert sein: Ein während des GET eingetroffener
Erneuerungsauftrag verhindert die Zuordnung. Der lokale Inventareintrag wird
atomar und dauerhaft gespeichert. Ein späterer APIauftrag wartet auf diese
kurze Sperre und kann anschließend normal angelegt werden.

Ein neuer Eintrag bekommt Herkunft adopted, die bestehende Freigabe-ID und den
übergebenen Nachweishash. Bereits vorhandene gültige Einträge bleiben vollständig
erhalten, einschließlich ursprünglicher Herkunft created/adopted und ursprünglichem
Nachweis. Auch eine verlorene Antwort wird so lesend abgeglichen. Widersprüchliche
Key-/Fingerprintzuordnungen werden abgewiesen. Eine Zuordnung startet weder
Erneuerung noch Bereinigung; dafür gelten die jeweiligen gebundenen Aufträge.

Zwölf neue lokale Fälle und sechs unmittelbar betroffene bestehende Fälle sind
bestanden. Sie verwenden reale Dateien, Kryptografie und SQLite sowie ausdrücklich
synthetische Graph-, Docker-, POSIX-, Uhr- und Freigabegrenzen. Tatsächliche
Linuxrechte, Sperren, Prozesse und Graphbestand sind gesondert nativ zu prüfen.
