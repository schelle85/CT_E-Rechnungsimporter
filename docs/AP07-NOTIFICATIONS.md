# AP07 – Benachrichtigungen, Teilstände A/B

Stand: 15. November 2026. AP07a–c ist freigegeben und in Arbeit. A enthält
Fach-/Datenbankbausteine; B ergänzt begrenzten Graphsender, Zertifikatsproof,
eigenen Schlüssel und CLI. Neue Webbedienung folgt in C. Kundenbetrieb bleibt
AP06 mit Schema006. Keine Kundenmigration, echte Testmail oder Zeitplanaktivierung
aus diesen Teilständen. Dauerhafte Jobs gehören AP08.

## Wiederverwendung und Umfang

Vorhandene SQLAlchemy-/Alembic-/Graph-/Azure-Identity-/HTTPX- und React-/Mantine-
Bausteine werden weiterverwendet. Kein weiterer Dienst oder SDK erforderlich.
Direkter [Graph-sendMail-Aufruf](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)
ist in B implementiert:202 bedeutet Annahme, keine Zustellung.
Keine SMTP-Ergänzung, keine zusätzlichen globalen Entra-Rechte und kein Mail-Editor.

Paket A ergänzt drei eingefrorene Tabellen über007: Notificationeinstellungen,
Outbox und Beobachtungsmetadaten. Migration benötigt keine Graph-/LDAP-/TLSdateien
oder Verschlüsselungsschlüssel. Sie beginnt ohne konfigurierte Empfänger;
reale Startwerte werden getrennt privat eingebracht. Bestehende Tabellen und
Migrationen001–006 bleiben unverändert. Destruktiver Downgrade ist gesperrt.

Die Store-Schnittstelle erwartet ausschließlich den separaten Notificationcipher.
Eigener Loader und explizite CLI-Bindungen sind in B implementiert. Echter
synthetischer Fernet-Negativdecrypt gegen einen unabhängigen LDAPkey bestanden;
konkrete native Image-/Mountprüfung folgt. [Betriebsvertrag](AP07-OPERATOR.md).

## Dauerhafte Versandabsicht

Slotidentität aus Instanz, serverseitigem Scope, Meldungsart und Zeitraum.
Vorlagen und Empfänger stehen vor der ersten Reservierung fest, als verschlüsselter
Gesamtpayload mit kanonischem Hash. Vordefinierte Klartextvorlagen enthalten nur
Zähler, neutrale Gründe und technische Statusangaben; keine Rechnungs-/Mailinhalte
oder Anhänge. Empfänger sind eine bis zehn geprüfte eindeutige SMTP-Adressen.

Vor Reservierung bleibt ein noch aktueller Pflichtslot bei Einstellungsänderung
unter gleichem Schlüssel mit erhöhter Planrevision neu planbar. Fehlende Empfänger,
Quote oder Retry-After schieben auf. Ab Reservierung bleibt der Payload unverändert.
Ein zusätzlicher dauerhafter POST-Startpunkt gibt auch demselben Owner höchstens
einmal den Payload zur externen Ausführung frei. Kein POST ohne bestätigten Commit.

Testrequests binden Actor, Scope, UUID und ursprüngliche erwartete Version.
Gleicher Request liefert seinen vorhandenen Beleg vor Prüfung der inzwischen
aktiven Version. Andere Payload-/Scopebindung ergibt Konflikt. Neue Sitzung
oder verlorene Antwort erzeugen keinen neuen Versand. Eine ungewisse Reservierung
wird weder nach Neustart noch Leaseablauf zurückgesetzt.

Zustände unterscheiden vorbereitet, sendend, angenommen, sicher abgewiesen,
ungewiss und überholt. Nur202 mit passender POST-Reservierung ist angenommen;
5xx oder fehlender Ausgang sind kein sicherer Ablehnungsbeleg. Verspätete Ergebnisse
überschreiben keinen bereits dauerhaften Abschluss. Abgleich und Historie lesen
nur den gespeicherten Beleg, ohne neuen Request anzulegen.

## Zeit- und Zählervertrag

Defaults: Zertifikatswarnung08:00, Tagesbericht08:15, Wochenbericht Montag08:30,
jeweils Europe/Berlin. Sommerzeitlücke: erster folgender gültiger Zeitpunkt;
doppelte Stunde: erste Ausprägung. Tages-/Wochenplanung wählt nur den jüngsten
fälligen Termin; Zertifikatswarnung nur den heutigen Slot. Keine historischen
Warnstapel nach Neustart.

Berichte verwenden `start <= created_at < end` für im Zeitraum erstmals
protokollierte Vorgänge. Zähler sind der gemeinsame konsistente Stand bei
Berichtserstellung, keine erfundene historische Abschlussstatistik aus updated_at.
Mail-/Anhangs-/Belegzähler verwenden ihre eindeutige Körnung; Quelljournal bleibt
unverändert. Snapshot und Erstellzeitpunkt werden vor Netzwerkzugriff eingefroren.

Warnfarben anhand exakter Restzeit: orange bei mehr als24h bis einschließlich
10×24h, rot bei höchstens24h einschließlich Ablauf/danach. Berliner Datum bestimmt
nur Tagesidentität/Terminierung. Zertifikatswarnung ist verpflichtend. Ende erst
nach frischer geprüfter Anmeldung mit genau dem gültigen Nachfolger. Lokales
PEM-/RSAlesen, gleicher-Bytes-/Scope-/Gültigkeitsproof und Revision gegen verspätete
Beobachter sind in B implementiert/synthetisch geprüft.0/negative Zeit bleibt
warnpflichtig und schaltet best-effortGraphversuche nicht ab; Authfehler neutral
gespeichert, keine ungültige Nachfolgerfreigabe. Keine echte Cloudprobe daraus.

Zertifikatspläne führen ihre ursprüngliche Warnserie mit eigener Serienidentität,
Scope, Fingerprint, Gültigkeits-/Beginnzeiten und festem Faktenzeitpunkt mit.
Erstanlage, Replay/Neuplanung, Reservierung und POST-Freigabe prüfen diese Bindung
unter derselben Sperre gegen die aktuell offene Serie. Ein verspäteter alter Plan
darf eine geschlossene Serie weder neu anlegen noch wieder öffnen oder umdeuten.
Nachfolgerproof macht vorbereitete Altzeilen überholt und weist reservierte,
noch nicht zum POST freigegebene Altzeilen ohne neue Reservierung ab.
Bereits konsumierte POST-Freigaben sowie accepted/unknown-Historie bleiben erhalten;
der Proof und die POST-Freigabe werden unter der gemeinsamen Sperre geordnet.
Dateitausch ohne gültigen frischen Proof lässt die ursprüngliche Pflichtserie offen.
Die Serienbindung nutzt das vorhandene JSON-Feld; Schema007 bleibt unverändert.

Reine Störungsplanung unterstützt Bündelung, beobachtete Ausfalldauer, einmalige
Erholung und Wiederholungsabstand. Ausfallwiederholungen warten den konfigurierten
Abstand seit der tatsächlichen dauerhaften Reservierung derselben Episode ab,
auch nach verspätetem Nachholen und bei ungewissem Ausgang. Der Store prüft diese
Grenze erneut unter der gemeinsamen Sperre; ein veralteter paralleler Plan wird
unreserviert aufgeschoben. Ausfall und Erholung führen den unveränderlichen
ursprünglichen Beobachtungssnapshot im IncidentSlot mit: Token/Episode,
Fehlercode, Beginn, Beobachtungs-/Fehlerzeit und gegebenenfalls Erholung.
Vor Erstanlage, unverändertem Replay und Neuplanung prüft der Store unter der
Sperre Slotzeitraum/Tag, Fakten und genau passende Incidentmitgliedschaft gegen
diesen Snapshot und den aktuellen Monitor. Veraltete Episoden werden abgewiesen,
statt einen alten Payload mit der inzwischen neuen Episode zu verknüpfen.
Die Bindung liegt im vorhandenen JSON-Feld, auch vor Erstkonfiguration; bei
Reservierung wird sie erneut geprüft. Keine Schemaänderung dafür.
Meldungsmitgliedschaft und Reservierung werden atomar verknüpft.
Fehlerbündel führen ihre ursprünglich ausgewählten Ursachen als eingefrorene
ErrorObservations mit; Fakten, Perioden und Mitgliedschaft werden vor Erstanlage,
Replay und Neuplanung gegen den aktuellen Monitor geprüft. Reservierung prüft
alle Mitglieder erneut, bevor eines markiert wird. Ab tatsächlicher letzter
Bündelreservierung gilt pro Scope mindestens1h; je unveränderter Ursache gilt
zusätzlich der konfigurierte Abstand (standardmäßig24h), auch beiunknown.
Stundenfenster oder alte Auswahlsnapshots umgehen diese Sperren nicht.
Ein zu frühes Bündel bleibt unreserviert aufgeschoben. Ein veraltetes Mitglied
wird nicht umgedeutet oder beim Reservieren still entfernt. Nur ein vollständig
konsistenter neuer Plan darf vor Reservierung Payload und Mitgliedschaft gemeinsam
mit höherer Planrevision ersetzen; abgewiesene Pläne verändern keinen Monitor.
Ein alter gespeicherter Fehler ist keine neue Verfügbarkeitsmessung.
Der begrenzte Sender ist in B implementiert. Weitere API-/Processingbeobachter
und Webverdrahtung folgen; kein unabhängiger VM-/SMB-/Offsiteüberwachungsdienst.

Der gemeinsame80s-Budgetweg für CLI/späteren Webaufruf ist in B implementiert:
Vorprüfung zählt mit, Kindphase höchstens60s/Restbudgetminus10s, Cleanup/Readback
begrenzt. Reale synthetische Kindprozesse lokal geprüft, tatsächliche native
CLI-/DB-/Signalgrenzen und ASGI-/Proxyintegration noch getrennt nachzuweisen.

## Lokaler Prüfstand

Erster A-Lieferstand:19 gezielte Gruppen bestanden; idempotente additive006→007-Übernahme und
unveränderte Altwerte, Einmalreservierung/Parallelität, Planrevision und Pflichtslot,
Request-/Scope-/Actorbindung, Abbruch und verspätete Resultate, Quote/Backoff,
verschlüsselte Ablagegrenze, Kalender/DST, exakte Warnschwellen, Berichtskörnung
und gemeinsamer Snapshot trotz paralleler Änderung sowie atomare Fehlerbündel.

Ein erster Migrationstest scheiterte nur beim Windows-Aufräumen des noch
gepoolten SQLitehandles. Testfixture auf NullPool korrigiert und gezielt bestanden;
anschließend erforderlicher Gesamtlauf des vervollständigten A-Stands:19/19PASS.
Keine nativen MariaDB-/Graph-/Kryptografie-/Browserergebnisse aus diesen lokalen
Prüfungen ableiten. Bestehende AP03–AP06-Ergebnisse behalten ihre Quellen/Zähler.

Erster Korrekturversuch AP07-A1: verspäteter Ausfallversuch eine Sekunde vor der
nächsten Periodengrenze, weiterhin gesperrt bei1s und24h−1s, freigegeben exakt24h
nach tatsächlicher Reservierung; unknown, Einstellungen, konkurrierende vorbereitete
Pläne, Episodenwechsel und separate Erholung geprüft. Erster Lauf21/22 bestanden;
ein zusätzlicher Test erwartete Neuplanung trotz noch aktivem Owner. Nur seine
Vorbedingung durch ausdrückliche Ownerfreigabe berichtigt, enge Nachprüfung1/1PASS.
Keine funktionale Produktänderung nach diesem ersten Lauf und kein vollständiges
22/22-Ergebnis behauptet. Unabhängiger Review dieses Versuchs fand noch die
Erstanlage-Race: alter Plan wurde mit der inzwischen neuen Episode verknüpft.

Korrekturversuch2 bindet deshalb den ursprünglichen Snapshot durchgängig wie oben
beschrieben. Erster lokaler Lauf25/25PASS, einschließlich Erstanlage-Race,
neuer Episode unter/exakt15Minuten, vermischter Fakten/Perioden/Mitgliedschaft,
unreserviertem Altplan/Erstkonfiguration/Replan, tatsächlicher24h-Grenze,
unknown und zwei konkurrierenden kohärenten Planern. Das unveränderte Setup
der unabhängigen Reproduktion wurde mit den geänderten Quellen nachgespielt:
alter Erstplan abgewiesen, keine zusätzliche Outboxzeile, neue Episode vollständig
unverändert und ohne Reservierung. A1 wurde danach unabhängig auf Quellenebene
mit lokaler Reproduktion nach Versuch2 geschlossen. Kein Gesamt-/Native-PASS für A.

Separater Restbefund A2 betraf dieselbe unveränderte Ursache im Fehlerbündelpfad:
ein gehaltener Snapshot konnte an der Stundengrenze nach1s erneut reservieren.
Korrekturversuch1 ergänzt die oben beschriebenen ursprünglichen Bündelsnapshots
und atomaren1h-/Ursachenabstände. Erster lokaler Lauf30/30PASS einschließlich
aller A1-Regressionsfälle. Unverändertes unabhängiges A2-Setup gegen die geänderten
Quellen nachgespielt: zweite Reservierung und POST-Berechtigung abgewiesen,
vollständiger Monitor unverändert. Exakte1h-/24h-Grenzen, unknown, Konkurrenz,
Episodenwechsel und konsistente Teil-Neuplanung geprüft. Unabhängiger Review und
native Prüfung dieses A2-Standes wurden separat fortgesetzt; A1 bleibt geschlossen.
A2 danach unabhängig nachVersuch1 geschlossen, gesamter A-Quellreview PASS.

PaketB:19Sender-/Zertifikats-/Runtimegruppen und9Prozess-/Bindungsgruppen lokal
bestanden. Initial versehentlich als Test gesammelten Fixturehelfer umbenannt;
keine Produktkorrektur daraus. Eigene gezielte B1-Fristkorrektur prüft Budget nach
POST-Gate-Commit und begrenzt Graphauth/-transport auf den Resttermin;19betroffene
Gruppen anschließend bestanden. Keine pauschale gemeinsame58er-/Nativeabnahme.
Einzelfall-/Runtimegrenzen im [Betreiberweg](AP07-OPERATOR.md).

Der unabhängige B-Quellenreview stoppte anschließend bei B2: verspätete erste
Warnplanung nach bereits bestätigtem Nachfolger konnte die Altwarnung freigeben.
Korrekturversuch1 ergänzt die Serienbindung und drei atomaren Prüfstellen oben.
Das ursprüngliche Review-Setup ist gegen die Korrektur nachgespielt: alte Erstanlage
abgewiesen, keine Outboxzeile/POST und Monitor nach Proof unverändert. Gezielte
Regressionsfälle prüfen auch beide Gates unabhängig von der Altzeilenbereinigung,
Konkurrenz, ursprüngliche Fakten, Dateitausch ohne gültigen Proof und unveränderte
Reservierungs-/Historienverträge. Unabhängiger B-Review/native B-Abnahme bleiben offen.
Abschließender betroffener Lauf:59/59 lokale Fälle bestanden (30A,19bisherige B,
10B2-Gruppen). Die9Prozess-/Bindungsgruppen wurden in diesem Korrekturschritt
nicht erneut ausgeführt; deren früherer Nachweis bleibt separat.

Nächster Prüfschritt: fester B-Review/native B-Nachweise. C ergänzt neue API-/
Web-/Loginbedienung und gezielte Browserprüfung einschließlich Administration→Berichte.
Realer Testversand erst nach konkretem Betreiberabgleich von Vorlage, Empfängern
und Anzahl. AP08/09/10 bleiben ohne Go, DMS und Erkennungsänderungen außerhalb AP07.
