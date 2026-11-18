# KI-Dokumentation

Stand: 18. November 2026. Wiedereinstieg nach AP09/AP11 und zur AP10-Quelllieferung.
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

Produktlaufzeit: `d9f32a5a9c9fb642f59a13ed2550f74532fc3ebe`, Schema `008`.
Reine Dokumentcommits ändern diese Laufzeit nicht. API/Web/Worker/Hostpeers sind
bereitgestellt; Classifier bleibt separat eingefroren. Bestehende Instanz,
Konfiguration und Datenbank wurden erhalten.

Der echte zweite Wechsel ist unabhängig nativ bestätigt: `committed/new`, SQL
`overlap`, drei tatsächliche Verbraucher und eigener Abschlussproof. Eine unklare
Registrierung wurde unter demselben ursprünglichen Auftrag rein lesend abgeglichen
und fortgesetzt; keine zweite Registrierung dieses Kandidaten. Neues Graphmaterial
aktiv, automatische Erneuerung erlaubt und Rotationtimer aktiviert. Ein zukünftiger
automatischer Auslöser und produktive Altkeybereinigung bleiben unbewiesen.

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

## Auftragsstand

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
Linuxwartung ist seit 18.11.2026 freigegeben. Lokale Quelle und Einrichtungs-/Rückwegplan
sind eigengeprüft; 14 gezielte Tests bestanden. Quellenreview, native Linuxprüfung,
frischer Instanzabgleich, Installation und echter Sonntagslauf noch offen.
API-/Workerimages bleiben d9/008; geplante Host-Stopkorrektur separat abgleichen.
Gestaltung der Tages-/Wochenberichtsmails ist nur
als separater AP07-Nachtrag geplant. Kein Push oder Deployment aus einer lokalen
Dokumentlieferung ableiten.

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
| Geplante OS-Wartung | [AP10-Vertrag](AP10-WARTUNG.md), [Einrichtung/Rückweg/Abnahme](AP10-EINRICHTUNG.md); freigegebene lokale Quelllieferung, noch kein installierter Betrieb. |
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

- Nur vorgesehenes Postfach und direkte Inbox ab 01.12.2026, 00:00 Europe/Berlin.
  Altmails unangetastet; AP03 und Stichtag eingefroren.
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

## Offene Punkte und nächster Schritt

Die einmalige finale AP09-Prüfung ist bestanden. Geprüfte Technikquelle, PDF und
vertrauliches Betriebsblatt bleiben bei der anschließenden Statusfortschreibung unverändert.
AP11-Gesamtpaket genau einmal unabhängig mit PASS geprüft und in AP09a übernommen.
Handbuchquelle, PDF und Bilder bleiben bei der anschließenden Statuspflege unverändert.
Kundenrückmeldung zum Handbuch ist offen; Dokumentvollständigkeit ist keine neue Betriebsabnahme.
AP10 hat Go; vor Installation festen Quellstand und konkreten Plan prüfen sowie den
frischen Hostbestand nachholen. Heute nur Check/Simulation/Offslotprobe, kein echter
Mittwochsupdate oder Reboot. Nach tatsächlicher Einrichtung nötige neue PDFausgaben
ausdrücklich planen; datierte gelieferte Unterlagen erhalten.
Öffentliche Dokumente und vertrauliche Zuordnungen
werden getrennt übergeben; keine neue Produktbereitstellung daraus ableiten.

Weitere Grenzen: spätere produktive Altkeybereinigung, zukünftiger automatischer
Erneuerungsauslöser, vollständiger VM-/Offsite-Restore, fachliche Erkennungsrestfälle,
neue echte Kundenanmeldung nach späteren Deployments und ursprüngliche Ursachen
des ersten Rotations-/Restorefehlversuchs. Keine neuen Serien daraus starten.

ORGA koordiniert, DEV liefert, REVIEW prüft. Keine Zusatzchats oder Agenten ohne
Auftrag. Pro Ursache höchstens fünf gezielte DEV-Korrekturversuche; Modellwechsel
oder Umbenennung setzt Zähler nicht zurück. Interne Zeit-, Token-, Kosten-,
Zugangs- und Prüfzuordnungen bleiben außerhalb des öffentlichen Git.
