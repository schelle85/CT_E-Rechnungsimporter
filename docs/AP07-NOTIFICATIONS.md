# AP07 – Berichte und Benachrichtigungen

Stand: 15. November 2026. AP07a–c ist technisch abgeschlossen, geprüft und
bereitgestellt auf Schema 007. A enthält Fach-/Datenbankbausteine, B den begrenzten
Graphsender mit Zertifikatsproof/eigenem Key/CLI, C die AD-gesicherte Webbedienung
und tatsächlichen Beobachter. Import-, Korrektur- und Notificationautomatik
bleiben inaktiv; die dauerhafte Aktivierung gehört in AP08.

## Wiederverwendung und Umfang

Vorhandene SQLAlchemy-/Alembic-/Graph-/Azure-Identity-/HTTPX- und React-/Mantine-
Bausteine werden weiterverwendet. Kein weiterer Dienst oder SDK erforderlich.
Direkter [Graph-sendMail-Aufruf](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)
ist in B implementiert:202 bedeutet Annahme, keine Zustellung.
Keine SMTP-Ergänzung, keine zusätzlichen globalen Entra-Rechte und kein Mail-Editor.

Paket A ergänzt drei eingefrorene Tabellen über007: Notificationeinstellungen,
Outbox und Beobachtungsmetadaten. Migration benötigt keine Graph-/LDAP-/TLSdateien
oder Verschlüsselungsschlüssel. Sie beginnt ohne konfigurierte Empfänger;
drei reale Startempfänger wurden getrennt privat initialisiert. Bestehende Tabellen und
Migrationen001–006 bleiben unverändert. Destruktiver Downgrade ist gesperrt.

Die Store-Schnittstelle erwartet ausschließlich den separaten Notificationcipher.
Eigener Loader und explizite CLI-Bindungen sind in B implementiert. Echter
synthetischer Fernet-Negativdecrypt gegen einen unabhängigen LDAPkey bestanden;
native Image-/Mountprüfung bestanden. [Betriebsvertrag](AP07-OPERATOR.md).

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
Beobachter sind implementiert und geprüft.0/negative Zeit bleibt
warnpflichtig und schaltet best-effortGraphversuche nicht ab; Authfehler neutral
gespeichert, keine ungültige Nachfolgerfreigabe. Echte Zertifikatsanmeldung ist
separat im bestätigten Betriebsstand nachgewiesen.

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
Die Serienbindung nutzt das vorhandene JSON-Feld; Schema 007 bleibt unverändert.

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
Der begrenzte Sender ist in B implementiert. C verbindet die reine Planung mit
tatsächlichen Journalfehlern sowie begrenzten API-/Graphproben im manuellen CLIplan.
Kein unabhängiger VM-/SMB-/Offsiteüberwachungsdienst.

Der gemeinsame 80-s-Budgetweg für CLI und Web ist implementiert und nativ geprüft:
Vorprüfung zählt mit, Kindphase höchstens60s/Restbudgetminus10s, Cleanup/Readback
begrenzt. Der vollständige HTTPS-Fristfall lief mit 80,006 s; Antwortverlust, neue
Sitzung und Konfigversion führten zu keinem Doppel-POST.

## Geprüfter Liefer- und Betriebsstand

AP07 aus `5ecfd59270b63947d3f92af98a1b9f8e5a267aeb` ist technisch abgeschlossen
und bereitgestellt. Schema 007, API/Web aus derselben festen Quelle und erhaltene
Instanz/LDAP-Konfiguration/DBdienst sind getrennt bestätigt. A/B vollständig,
C-Quellenreview und 21 C-Fälle auf MariaDB bestanden. Acht isolierte HTTPS-
Browsergruppen einschließlich 80,006 s-Fristfall, Antwortverlust, neuer Sitzung,
Konfigversion und Schutz vor Doppel-POST bestanden. Ein zusätzlicher
synthetischer CLIplan ist geprüft.

Eigenständiger Notificationkey, minimale manuelle CLI und drei Empfänger privat
initialisiert. Echte Graph-Zertifikatsanmeldung erfolgreich; genau eine feste
Testmail mit HTTP 202 angenommen, Reservierung 1 und Status getrennt bestätigt.
Empfang ausschließlich im eigenen Abnahmepostfach belegt. Keine neue tatsächliche
Kundenanmeldung nach AP07; die echte AD-Abnahme aus AP01 bleibt historisch.

Import-/Korrektur-/Notificationautomatik bleibt inaktiv. Gespeicherte Zeiten
starten keine Jobs; dauerhafte Aktivierung benötigt AP08-Go. AP08/09/10/11 nicht
freigegeben, AP11-Planung erhalten. [Aktueller Betriebsstand](BETRIEBSSTAND.md).

Administration bereitgestellt: Administration→Berichte mit echten Tages-/Wochen-/
frei gewählten Journalzeiträumen, gemeinsamem Snapshot und korrektem Leerzustand.
Beide AD-Rollen dürfen lesen; Berichtsansicht erzeugt keinen Outboxauftrag.
Lokale Graphzertifikatsmetadaten, offene Pflichtserie und gespeicherter Nachfolgerproof
werden getrennt gelesen; Portal- und gesonderter Loginwarnhinweis für beide Rollen.
Versionierte Einstellungen, lesender Verlauf und feste Testmail sind in C implementiert.
Aktuelle AD-/Admin-/Origin-/CSRF-Prüfung geht dem Requestlookup voraus; Actor aus
geprüfter AD-GUID. Originale UUID/Version bleiben im Browser bei Antwortverlust,
Reload und neuer Sitzung erhalten. Vorschau und ausdrücklicher Versand verwenden
denselben gespeicherten Slot. Statusabgleich erzeugt keinen neuen Auftrag.
Das Webbudget beginnt als äußere ASGI-Grenze vor AD/DB/Bodyvorprüfung und reicht
denselben absoluten Termin an den vorhandenen begrenzten Kindprozess weiter.
Der API-Kindprozess teilt die API-Dateisystemgrenze; Graph-JSON, Graph-PEM und
der zusätzliche Notificationkey sind im separaten Weboverlay einzeln RO gebunden.
Der externe Operator
behält seine eigene minimale Allowlist. Die weitere Beobachterintegration ist
implementiert; Quellen-, native und isolierte Browserprüfungen sind bestanden.

Der manuelle CLIplan liest maximal100 aktuelle Mailfehler und100 Anhangsfehler
im aktiven Postfachscope. Ursachen binden Tabellenart, neutralen Code, Vorgang/
Anhang, Verarbeitungs- und Befundrevision. Die Meldung enthält nur neutrale Codes
und Zähler. Unbekannte Dokumentart und inaktive Jobs erzeugen keinen Ausfall.
Bis100 ältere aktive Ursachen werden anhand ihrer ursprünglichen Referenz erneut
geprüft; ein Abfragelimit darf keine Erholung vortäuschen. Bereinigte/ersetzte Ursachen
schließen ihren Monitor. Alte unreservierte Ausfall-/Bündelabsichten werden unter
dem gemeinsamen Lock überholt, ohne reservierte Historie oder Journal zu verändern.
Fehlerbündel wählen höchstens100 aktuell fällige Ursachen; die bestehenden atomaren
1h-/Ursachenabstände ab tatsächlicher Reservierung bleiben maßgeblich.
APIbereitschaft wird durch genau einen begrenzten GET gegen `api:8000` einschließlich
Instanzvergleich geprüft; Graph über die vorhandene frische Postfachprobe.
Gespeicherte Graphsperrfristen sind keine neue Verfügbarkeitsmessung. Ausfall/
Erholung nutzen ursprüngliche A-Snapshots und frische beobachtete Dauer. Bei Ausfall
der eigenen VM/DB besteht keine zuverlässige Selbstalarmierung.
Die einmalige feste Mailprobe und ihr separater Status-/Empfangsabgleich sind
bestätigt. Daraus folgt kein weiterer Versandauftrag. AP08/09/10/11 bleiben ohne
Go; DMS und Erkennungsänderungen liegen außerhalb AP07.
