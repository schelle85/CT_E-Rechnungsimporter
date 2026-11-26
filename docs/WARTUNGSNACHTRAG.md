# Wartungsnachtrag

Für Nutzer und Betreiber des E-Rechnungsimporters. Stand: 26. November 2026.
Ergänzung zum gelieferten Nutzerhandbuch und zur technischen Dokumentation.
Die Wartung ist installiert, qualifiziert geprüft und seit **18.11.2026,
11:24:12 Uhr Europe/Berlin** regelmäßig eingeplant. Am 22.11. wurde die
Wartung wegen des gespeicherten VM-Zustands verspätet ausgelöst und vor der
Paketinstallation beendet. Ein vollständiger regulärer Sonntagslauf steht noch aus.

## Termin, Umfang und Portalunterbrechung

Die Betriebssystemwartung ist für Sonntag um **03:00 Uhr Europe/Berlin**
vorgesehen. Während der kontrollierten Unterbrechung kann das Portal zeitweise
nicht erreichbar sein und die automatische Verarbeitung pausieren. Neue
Paketläufe beginnen nur bis vor 03:15 Uhr. Ein erforderlicher Neustart wird nur
nach erfolgreichen Prüfungen und vor 04:30 Uhr angefordert.

Bereits laufende Paketarbeit wird auch nach 04:30 Uhr regulär abgewartet.
Deshalb ist 04:30 Uhr keine zugesagte Endzeit der Unterbrechung. Ein ausgefallener
Termin wird beim späteren Einschalten nicht nachgeholt. Anschließend müssen
Dienste, Dateiablagen, HTTPS und die vorgesehenen Zeitpläne wieder bestätigt sein.

Bei anhaltender Nichterreichbarkeit an die technische Betreuung wenden und
Zeitpunkt sowie angezeigte Meldung nennen. Eine bestehende manuelle Pause oder
ein ungeklärter Vorgang wird durch die Wartung nicht eigenmächtig aufgehoben.
Aus einer Nichterreichbarkeit allein lässt sich kein erfolgreicher Neustart ableiten.

## Nachkontrolle und Störungen

Die bestehende rein lesende Nachkontrolle ist für **Sonntag um 03:30 Uhr
Europe/Berlin** aktiviert und vom Wartungschat übernommen. Eine belegte
laufende Wartung wird als laufend erfasst; fehlende
Abschlussbelege bleiben offen. Der beauftragte Wartungschat beobachtet nötigenfalls
höchstens alle fünf Minuten lesend weiter, längstens bis 05:30 Uhr. Beim
tatsächlichen Ende wird das Ergebnis gegen den ursprünglichen Vorzustand geprüft.

Fehler werden dem technischen Betreiber gemeldet. Bei fehlendem Abschluss oder
Zugang übernimmt dieser die weitere Klärung und den späteren Abschlussauftrag.
Laufende Paketarbeit wird nicht zum Ende der Beobachtung abgebrochen. Details
einschließlich Zugangsversuchen und Archivwarnung stehen im
[Einrichtungs- und Nachkontrollplan](AP10-EINRICHTUNG.md).

Bei fehlendem VPN oder Serverzugang ist das Ergebnis **nicht prüfbar**. Nach
höchstens zwei weiteren lesenden Zugangsversuchen um 03:35 und 03:40 Uhr wird
dies an den Betreiber übergeben. Ein bekannter Fehler bleibt auch bei fehlenden
Zusatzbelegen ein Fehler. Fehlender Abschluss wird nicht als Erfolg gewertet.

Bei Fehlern können Dienste und Verarbeitung bewusst pausiert bleiben. Die
technische Betreuung gleicht zuerst Originalbelege, laufende Arbeit und den
Besitzer einer Pause ab. Sperren oder Protokolle werden nicht zur Freigabe
gelöscht; ein unklarer Versand oder Dateivorgang wird nicht blind wiederholt.
Ein kontrollierter manueller Wiederanlauf ist ein gesonderter Betreiberauftrag.

Ist um 05:30 Uhr noch kein Abschluss belegt, übernimmt der technische Betreiber
die weitere Klärung und veranlasst die abschließende Rücklese nach tatsächlichem
Ende. Spätestens am nächsten Arbeitstag um 08:00 Uhr ist ein erneuter manueller
Statusauftrag vorgesehen. Das ist keine Zusage, dass Paketarbeit dann beendet ist.

## Geprüfter Stand, Sicherung und offene Nachweise

Am 18.11.2026 sind die 16 Wartungsziele aus Quellstand `10cea808` installiert.
Guard und automatische Bootprüfung, der reine Check und die Probe außerhalb des
Wartungsfensters sind bestanden. Die getrennte Rücklese um 11:20 Uhr bestätigt
die bisherigen Dienst-, Paket-, Dateiablage-, HTTPS- und Zeitplanbindungen.
Bei dieser Einrichtung wurden keine Betriebssystemupdates und kein Reboot ausgeführt.

Die konkrete Bereitstellung ist unabhängig mit PASS geprüft. Der Wartungstimer
ist seit 11:24:12 Uhr enabled/active/waiting; nächster Termin ist **22.11.2026,
03:00 Uhr Europe/Berlin (02:00 UTC)**. Der bisherige tägliche Upgrade-Timer ist
deaktiviert und inaktiv. Der neue Zeitplan holt verpasste Läufe nicht nach.

Der Wartungsumfang umfasst freigegebene Betriebssystempakete aus den bestätigten
Quellen. Anwendungs- und Datenbankschemaänderungen benötigen einen eigenen
Lieferauftrag. Der technische Betreiber verantwortet Sicherung, Zugang,
Wiederherstellung und die Prüfung des tatsächlichen Wartungsergebnisses.

Die bestehende Sicherungsvereinbarung bleibt bestehen: tägliche Sicherung mit
HornetVMbackup einschließlich Offsite. Der technische Betreiber kontrolliert vor
dem Wartungslauf den letzten erfolgreichen Sicherungsstand; eine automatische
Hornet-Prüfung ist nicht Bestandteil des Importers oder der lesenden Nachkontrolle.
Der letzte Sicherungsjob ist durch diesen Dokumentabschluss nicht live nachgewiesen.
Ein vollständiger VM-/Offsite-Restore ist
weiterhin **nicht nachgewiesen**. Eine vorhandene Sicherung oder ein bestandener
Installationscheck ersetzt diesen Wiederherstellungsnachweis nicht.

Anwendung und Datenbankschema wurden am 26.11. lesend auf dem gelieferten Stand
2ee04d0/008 bestätigt. Der nächste reguläre Termin ist am 29.11. um 03:00 Uhr
Europe/Berlin; die VM muss dafür laufen. Die ursprünglichen AP09-/AP11-Ausgaben
bleiben in Git erhalten. Dieser Nachtrag ergänzt die aktuellen Unterlagen um
den Wartungsablauf. Der **erste vollständige reguläre Sonntagslauf**
und ein dabei gegebenenfalls erforderlicher **Neustart mit Wiederanlaufprüfung**
sind noch nicht nachgewiesen.

Technischer Ablauf: [AP10-Wartungsvertrag](AP10-WARTUNG.md).
