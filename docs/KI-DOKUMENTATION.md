# KI-Dokumentation

Stand: 26. November 2026. RC04/RC05-Vorbereitung; noch keine Releasefreigabe.
Historische Detailverläufe bleiben in den Paketverträgen und der Git-Historie.
Keine privaten Chatprotokolle und kein pauschaler Gesamtabschlussbericht.

## Wiedereinstieg

1. [Arbeitsregeln](../AGENTS.md), konkreten Auftrag, Git-Stand und Arbeitsbaum prüfen.
   Dokument-HEAD und festen Produktpin unterscheiden.
2. [Anforderungen](ANFORDERUNGEN.md) und [Arbeitsplan](ARBEITSPLAN.md) abgleichen.
3. [Technische Dokumentation](TECHNISCHE-DOKUMENTATION.md) für den Betriebsüberblick,
   [AP12-Übergabe](AP12-UEBERGABE.md) für aktuelle Nachweisgrenzen lesen.
4. Den betroffenen Originalvertrag lesen. Alten Paketstatus nicht als aktuellen
   Gesamtstand behandeln. Nur den konkret freigegebenen Umfang bearbeiten.
5. Quellprüfung, tatsächlich ausgeführte Prüfung, Bereitstellung und Kundenabnahme
   getrennt dokumentieren. Unbekannte Wirkung zuerst lesen und abgleichen.

## Aktueller fester Stand

Produktlaufzeit: `5ad0a2c01490eaaafc65e4229298d8e074710bef`, Schema `008`.
Am 26.11. lesend bestätigt: HTTPS, API/DB, zwei CIFS-Mounts, acht Timer und
freigegebener Graphzugang mit erfolgreicher täglicher Prüfung. Reine
Dokumentcommits ändern diese Laufzeit nicht. Bestehende Instanz, Konfiguration
und Datenbank wurden erhalten. RC03 bestätigt 13 abgeschlossene Erstchargenmails
und 14 hashgeprüfte Originaldateien. XRechnung-Extension-Profil, PDF-Titelkontext
und verständliche Hinweise wurden im aktuellen Stand gezielt ergänzt.

Der echte zweite Wechsel ist unabhängig nativ bestätigt: `committed/new`, SQL
`overlap`, drei tatsächliche Verbraucher und eigener Abschlussproof. Eine unklare
Registrierung wurde unter demselben ursprünglichen Auftrag rein lesend abgeglichen
und fortgesetzt; keine zweite Registrierung dieses Kandidaten. Neues Graphmaterial
aktiv, automatische Erneuerung erlaubt und Rotationtimer aktiviert. Ein zukünftiger
automatischer Auslöser bleibt unbewiesen. Die produktive verwaltete Altkeybereinigung
wurde am 24.11.2026 in RC01 bestätigt.

Der erste Versuch kehrte kontrolliert zum Originalzertifikat zurück. Ursache
unbelegt; terminaler Fehlauftrag und registrierter Kandidat bleiben erhalten.
Der Erfolg des zweiten erklärt oder heilt den ersten nicht rückwirkend.

Genau ein kontrollierter AP12-Kundenboot ist erfolgt. Kunden-API, DB und Nginx samt
Images blieben erhalten; neues Graphmaterial, sieben Timer, CIFS und HTTPS gesund
bestätigt. Die lesende Aufnahme vom 17.11.2026 bestätigt diesen Betrieb. Der frühere
AP08-Boot bleibt ein eigener historischer Nachweis.

Isolierte Altmaterialwiederaufnahme erfolgreich. Nach Verlust flüchtiger Sperren
wurde vorbereitete neue Übernahme mit erhaltener Pause erreicht; dort API gezielt
ersetzt, DB/Nginx erhalten. Kein vollständig abgeschlossener neuer Wechsel daraus.
Erster Restorehelper-Aufruf mit AssertionError fehlgeschlagen, Ursache offen.
Späterer lesender Zustandsnachweis qualifiziert das Ergebnis, ersetzt den Fehlversuch
nicht. Kein vollständiger VM-/Offsite-Restore und keine pauschal bestandene native
Fehlerfallserie. Führend: [AP12-Übergabe](AP12-UEBERGABE.md).

## Auftragsstand - historische Paketabschlüsse bis 18.11.

AP09 ist seit 17.11.2026 zur Abschlussdokumentation freigegeben. Technikquelle/PDF,
dieser Wiedereinstieg und konsistente Übergabedateien bilden das vollständige Paket
der einmaligen unabhängigen Abschlussprüfung am festen Stand `330c749`, Ergebnis PASS.
Keine notwendigen Korrekturbefunde und keine Kapitelreviews.
Ein vertrauliches Betriebsblatt wird separat übergeben. Erstellung ist keine
neue Betriebs- oder Kundenabnahme.

AP11 hat seit17.11.2026 Go. Eine führende [Nutzer-/Administrationsanleitung](HANDBUCH-ZUM-PRODUKT.md)
mit zwölf neutralen Aufnahmen und [PDF](handbuecher/Handbuch-zum-Produkt.pdf) liegt
eigengeprüft vor. Genau eine unabhängige Prüfung am fertigen festen Paket b565465
ist mit PASS ohne notwendige Korrekturbefunde bestanden. AP09a übernimmt dieses
eine Handbuch; Kundenrückmeldung bleibt offen, keine konkurrierende Anleitung.
AP09-Technikquelle/PDF bleibt als geprüfte datierte Ausgabe unverändert. AP10 zur wöchentlichen
Linuxwartung ist seit 18.11.2026 freigegeben und aus 10cea808 installiert. Quellen-/
Planreview, 22+4, Kalender und isolierte native Leser-/MariaDB-/systemd-Prüfungen
bestanden. Guard/Bootprüfung active/exited; Check, Offslot und getrennte Rücklese
der 16 Ziele um 11:20 Europe/Berlin bestanden, systemd verify Exit0. Bisherige
Betriebsbindungen erhalten. Bereitstellungsprüfung PASS. Sonntagstimer seit
11:24:12 Europe/Berlin enabled/active/waiting, erster Termin 22.11.2026 um 03:00
Berlin/02:00 UTC. Alter Upgrade-Timer disabled/inactive; kein heutiger Paket-/Bootlauf.
Lesende Nachkontrolle Sonntag 03:30 Europe/Berlin übernommen und bestätigt aktiv;
erster echter Sonntag-/Bedarfsbootlauf offen.
API-/Workerimages waren zu diesem Paketabschluss d9/008; die aktuelle Bindung
steht oben. Der am 18.11.2026 freigegebene AP07-Nachtrag ist seit 24.11. bereitgestellt. Der gemeinsame
Versandrenderer erzeugt Tages- und Wochenberichte als HTML im Portalstil.
Berichtsdaten und Slotregeln bleiben erhalten. Erste neue reguläre Berichte in
Outlook bleiben abzunehmen. Der verspätete Wartungslauf vom 22.11. endete vor APT;
ein vollständiger Sonntagslauf ist weiter offen.

## Führende Quellen

| Thema | Quelle und Einordnung |
| --- | --- |
| Betriebsüberblick, Versionen, Restore | [Technische Dokumentation](TECHNISCHE-DOKUMENTATION.md); datierte installierte Versionen, keine Mindestvorgaben. |
| Umfang und Freigaben | [Anforderungen](ANFORDERUNGEN.md), [Arbeitsplan](ARBEITSPLAN.md), [Dokumentationsplan](DOKUMENTATIONSPLAN.md). |
| Betriebsabschlüsse | [Betriebsstand](BETRIEBSSTAND.md); aktueller AP12-Kopf vor historischen AP08-/AP07-Blöcken. |
| AD und Sitzungen | [AP01](AP01-SECURITY.md); aktuelle Rechte serverseitig prüfen. |
| Graph, Quellen und Aktionen | [AP02](AP02-GRAPH.md); enger Adapter, persistente Wirkungen. |
| Eingefrorene Erkennung | [AP03](AP03-RECOGNITION.md); fachliche Restfälle offen. |
| Dateiablage und Dubletten | [AP04](AP04-ABLAGE.md); Belege auch nach Entnahme erhalten. |
| Verarbeitung | [AP05](AP05-PROCESSING.md), [Runtime](AP05-RUNTIME.md); aktuelle automatische Budgets aus AP08. |
| Portal, Freigaben, Originale | [AP06](AP06-WEB.md); spätere Timeraktivierung getrennt. |
| Meldungen, Slots und Proof | [AP07](AP07-NOTIFICATIONS.md), [Betreiberweg](AP07-OPERATOR.md). |
| Start, Drain, Timer, TLS, Status | [AP08](AP08-BETRIEB.md); heute sieben Timer mit AP12-Ergänzung. |
| OS-Wartung | [AP10-Vertrag](AP10-WARTUNG.md), [Einrichtung/Rückweg/Abnahme](AP10-EINRICHTUNG.md), [Nachtrag](WARTUNGSNACHTRAG.md) mit [PDF](handbuecher/Wartungsnachtrag.pdf); installiert, qualifiziert geprüft und eingeplant. |
| Aktuelle Rotationsabnahme | [AP12-Übergabe](AP12-UEBERGABE.md); führend vor historischen C-Teilständen. |
| Rotationsdetails | [Hostablauf](AP12-HOSTABLAUF.md), [Automatik](AP12-AUTOMATIK.md), [Admin-API](AP12-ADMIN-API.md), [Ownership](AP12-OWNERSHIP.md), [Cleanup](AP12-CLEANUP.md). |
| Browsergrenzen | [AP12-Browserprüfung](AP12-BROWSERPRUEFUNG.md); isolierte Fixtures sind kein echter ADlogin. |
| Nutzerhandbuch | [AP11-Handbuch](HANDBUCH-ZUM-PRODUKT.md), [PDF](handbuecher/Handbuch-zum-Produkt.pdf); alle Bedienbereiche, neutrale Bilder, keine neue Kundenabnahme. |
| Dokumenterzeugung | [PDF-Buildhinweise](handbuecher/README.md); Quelle bleibt führend. |

## Architekturentscheidungen

Vorhandene FastAPI-/SQLAlchemy-/MariaDB-, Azure-Identity-/HTTPX-, React-/Mantine-,
Docker-/systemd- und Standardbibliotheksbausteine weiterverwenden. Keine zusätzliche
Queue, IAM- oder Orchestrierungsplattform. Eigene Logik beschränkt sich auf den
vereinbarten Postfach-, Wirkungs-, Ablage-, Portal- und Betriebsvertrag. Neue Vorhaben
zunächst gegen bestehende Lösungen prüfen. KoSIT/Mustang sind wegen des auf
Erkennung begrenzten Umfangs keine zwingende Vollvalidierung; invoice2data ist
nicht integriert. Kein automatisches Lernen aus Benutzerentscheidungen.

API und Nginx ohne Root. API: ein Worker, privates Vorschau-Tmpfs, kein CIFS oder
Docker-Socket. Classifier ohne Netzwerk/Secrets. Root schützt Profile, Mounts,
Sperren und Wirkungsjournal. Verbraucher lesen die Gatebindung nur. Eine Kandidatenprobe
ersetzt keinen Produktionsproof. Freigabe erst nach drei Verbrauchern und Abschlussproof.

## Fachliche Invarianten

- Nur vorgesehenes Postfach und direkte Inbox. Der bereitgestellte Stand verwendet den bestätigten
  regulären Eingang ab 23.11.2026, 00:00 Uhr Europe/Berlin (22.11.2026, 23:00 UTC).
  Gelesene und ungelesene Mails einbeziehen; ältere Mails bleiben unangetastet.
  Erkennung nur bei tatsächlich belegten Restfällen gezielt ändern.
- Formaterkennung genügt; ZUGFeRD als Original-PDF. DMS-Anbindung, Konfiguration
  und Prüfung vollständig außerhalb Auftrag und Abnahme.
- Relevante Anhänge unabhängig ablegen. Technische/strukturelle Sperren nicht
  durch manuelle Zuordnung umgehen. Keine automatische Verallgemeinerung von Klicks.
- Dubletten nach Name/Bytegröße nur innerhalb aktueller KW. Andere Konflikte mit
  Zusatz lösen, nie überschreiben. Entnahme hebt Ablagebelege nicht auf.
- Mailpriorität: Failed, unzugeordnet (Unbekannt/Dublette), Mahnung, Nachfragen,
  Zahlungsavis, Success. Erst bestätigte Ablage-/Mailwirkung ergibt Erfolg.
- Mehrfachanhänge markieren; enge hashgebundene Inlinebild-Zählausnahme aus AP05
  erhalten. Keine manuelle Signaturhashliste.
- Webfreigaben erzeugen dauerhafte gebundene Absichten. Antwortverlust,
  Neuanmeldung und Reload erhalten ursprünglichen Body und UUID.
- Zwei Kalenderjahre aktive Protokollansicht, danach Webarchiv; keine Löschung
  oder zusätzliche Mailpflege. Graphannahme 202 ist keine Zustellbestätigung.
- Neustart/Rückweg darf keine unbemerkte Doppelwirkung erzeugen. Unklaren
  POST, addKey/removeKey oder Versand nie blind wiederholen.

## Betriebs- und Nachweisinvarianten

Sieben Timer in Europe/Berlin. Gemeinsame Processinghostsperre, Pause/Drain,
Budgets und frische CIFSbindung auch bei manuellen Läufen. Ein Timerstopp beweist
keinen stillen Service. Flüchtige Sperren nicht bei laufender Arbeit entfernen.
Start macht keinen Build/Pull/Migration. Status älter als180s oder mehr als30s
zukünftig ist unbekannt. Vier AP08-Statusjobs und eigene AP12-Rotationsanzeige
nicht zu einem neuen Statusschema umdeuten. HTTPS und Graph bleiben getrennt.

Historische AP08-Abnahme: Quelle413095f, fünf Timer, Leerlaufläufe, je ein Tages-/
Wochenbericht mit202, TLSübernahme/No-op und Boot. Statusphasenversatz auf Sekunde20
danach separat gesetzt und in drei automatischen Zyklen geprüft. AP12-Lieferung
und ihr Boot sind davon getrennt.

AP12-Browser: sieben isolierte Funktionsgruppen und Sichtprüfung abgeschlossen.
Ursprünglicher nativer Lauf false durch Reload-GETabbruch bleibt erhalten.
Nur der konkret abgegrenzte endliche Offlinefall ist akzeptiert; kein allgemeiner
Networkerrorverzicht und kein neuer echter Kunden-/ADlogin daraus. Historische
AP01-Kundenabnahme bleibt der tatsächliche ADnachweis.

## Historischer Dokumentabschluss bis 18.11.

Die einmalige finale AP09-Prüfung ist bestanden. Geprüfte Technikquelle, PDF und
vertrauliches Betriebsblatt bleiben bei der anschließenden Statusfortschreibung unverändert.
AP11-Gesamtpaket genau einmal unabhängig mit PASS geprüft und in AP09a übernommen.
Handbuchquelle, PDF und Bilder bleiben bei der anschließenden Statuspflege unverändert.
Kundenrückmeldung zum Handbuch ist offen; Dokumentvollständigkeit ist keine neue Betriebsabnahme.
AP10 ist qualifiziert bereitgestellt und der Sonntagstimer bestätigt aktiviert.
Die Betriebsübergabe ist angenommen; die vorhandene lesende Nachkontrolle für
Sonntag 03:30 Europe/Berlin ist bestätigt aktiv. Gesonderter MD-/PDFnachtrag
liegt eigengeprüft für genau einen finalen Dokumentreview vor; noch kein Commit
dieses Dokumentabschlusses. Datierte AP09-/AP11-Abgaben bleiben erhalten.
Erster tatsächlicher Sonntaglauf und bedingter Boot bleiben gesondert offen.
Öffentliche Dokumente und vertrauliche Zuordnungen
werden getrennt übergeben; keine neue Produktbereitstellung daraus ableiten.

Weitere Grenzen: spätere produktive Altkeybereinigung, zukünftiger automatischer
Erneuerungsauslöser, vollständiger VM-/Offsite-Restore, fachliche Erkennungsrestfälle,
neue echte Kundenanmeldung nach späteren Deployments und ursprüngliche Ursachen
des ersten Rotations-/Restorefehlversuchs. Keine neuen Serien daraus starten.

## Aktuelle Restaufgaben und Zuständigkeit

RC03-Statuskorrektur ist nach Quell-/Operationscodeprüfung und 28 gezielten
Linux-Tests bereitgestellt. Collector und Webanzeige erklären eine vorgemerkte
gemeinsame Aufgabe als deferred; fehlende oder fremde Belege werden nicht als
Erfolg maskiert. Datenbank/Einstellungen erhalten, acht Timer und drei Graph-
Verbraucher getrennt bestätigt. PDF/XML-Mischfall ebenfalls technisch abgeschlossen.
Neue Tagesberichte vom 25./26.11. sind empfangen, das Outlook-Layout vom 26.11.
ist visuell geprüft. Fachlicher Kennzahlen-/Wochenberichtabgleich sowie aktuelle
Kundenabläufe mit beiden AD-Rollen bleiben abzunehmen.
RC04: tatsächliche Sonntagswartung, Sicherungsdatum und Wiederanlauf belegen;
Schelle übernimmt den isolierten VM-/Offsite-Restore-Nachweis zum Vor-Ort-Termin
am 07.12. Die erste spätere reguläre Graph-Erneuerung mit Fälligkeit an den Betrieb
übergeben. RC05: Dokumente und endgültigen Lieferstand abgleichen, Freigabe,
Versions-/Tag-/Releaseerstellung und Kundenübergabe abschließen. Ziel ist 1.0.0,
bis zur tatsächlichen Freigabe keine Veröffentlichung behaupten.

Führend für diese Fortschreibung ist die [Releasevorbereitung](RELEASE-VORBEREITUNG.md).
Historische Prüfgrenzen bleiben erhalten, erledigte Altkeybereinigung ist oben
fortgeschrieben. Kein neuer Kundenlogin aus einer technischen Momentaufnahme.

ORGA koordiniert und prüft Dokumente, DEV liefert, REVIEW prüft ausschließlich
Code. Für neue Entwicklungsaufträge GPT-6.1 Sol, für Code-REVIEW GPT-6 Astra;
keine Modelle der 6.2-Familie. Keine Zusatzchats oder Agenten ohne
Auftrag. Pro Ursache höchstens fünf gezielte DEV-Korrekturversuche; Modellwechsel
oder Umbenennung setzt Zähler nicht zurück. Interne Zeit-, Token-, Kosten-,
Zugangs- und Prüfzuordnungen bleiben außerhalb des öffentlichen Git.
