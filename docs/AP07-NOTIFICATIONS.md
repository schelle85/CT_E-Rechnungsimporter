# AP07 – Benachrichtigungen, Paket A

Stand: 14. November 2026. AP07a–c ist freigegeben und in Arbeit. Dieser erste
Teilstand enthält reine Fach-/Datenbankbausteine, noch keinen Graphsender und keine
neue Webbedienung. Kundenbetrieb bleibt AP06 mit Schema006. Keine Kundenmigration,
echte Testmail oder Zeitplanaktivierung aus Paket A. Dauerhafte Jobs gehören AP08.

## Wiederverwendung und Umfang

Vorhandene SQLAlchemy-/Alembic-/Graph-/Azure-Identity-/HTTPX- und React-/Mantine-
Bausteine werden weiterverwendet. Kein weiterer Dienst oder SDK erforderlich.
Direkter [Graph-sendMail-Aufruf](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)
ist für die folgende Integration vorgesehen:202 bedeutet Annahme, keine Zustellung.
Keine SMTP-Ergänzung, keine zusätzlichen globalen Entra-Rechte und kein Mail-Editor.

Paket A ergänzt drei eingefrorene Tabellen über007: Notificationeinstellungen,
Outbox und Beobachtungsmetadaten. Migration benötigt keine Graph-/LDAP-/TLSdateien
oder Verschlüsselungsschlüssel. Sie beginnt ohne konfigurierte Empfänger;
reale Startwerte werden getrennt privat eingebracht. Bestehende Tabellen und
Migrationen001–006 bleiben unverändert. Destruktiver Downgrade ist gesperrt.

Die Store-Schnittstelle erwartet ausschließlich den separaten Notificationcipher.
Eigener Schlüssel, konkrete Bindungen und synthetischer Negativdecrypt gegen den
allgemeinen LDAP-Konfigurationsschlüssel werden in Paket B geprüft; Paket A
behauptet diese Runtimeprüfung noch nicht.

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
nach frischer geprüfter Anmeldung mit genau dem gültigen Nachfolger; tatsächliches
Zertifikatslesen und dieser Nachweis folgen in B.

Reine Störungsplanung unterstützt Bündelung, beobachtete Ausfalldauer, einmalige
Erholung und Wiederholungsabstand. Ausfallwiederholungen warten den konfigurierten
Abstand seit der tatsächlichen dauerhaften Reservierung derselben Episode ab,
auch nach verspätetem Nachholen und bei ungewissem Ausgang. Der Store prüft diese
Grenze erneut unter der gemeinsamen Sperre; ein veralteter paralleler Plan wird
unreserviert aufgeschoben. Ausfallmitgliedschaft bindet genau eine Incidentepisode
im vorhandenen JSON-Feld, auch vor Erstkonfiguration. Keine Schemaänderung dafür.
Meldungsmitgliedschaft und Reservierung werden atomar verknüpft.
Ein alter gespeicherter Fehler ist keine neue Verfügbarkeitsmessung.
Der tatsächliche API-/Graph-Beobachter und Versand folgen; kein unabhängiger
VM-/SMB-/Offsiteüberwachungsdienst wird behauptet.

Das gemeinsame80s-Budget und ein daraus abgeleitetes Kindbudget von höchstens60s
mit10s Abschlussreserve sind als reine Berechnung vorhanden. Tatsächliche Web-/
CLI-Abbruchfristen und Bindungen stehen noch zur nativen Prüfung an.

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

Gezielte Korrektur AP07-A1: verspäteter Ausfallversuch eine Sekunde vor der
nächsten Periodengrenze, weiterhin gesperrt bei1s und24h−1s, freigegeben exakt24h
nach tatsächlicher Reservierung; unknown, Einstellungen, konkurrierende vorbereitete
Pläne, Episodenwechsel und separate Erholung geprüft. Erster Lauf21/22 bestanden;
ein zusätzlicher Test erwartete Neuplanung trotz noch aktivem Owner. Nur seine
Vorbedingung durch ausdrückliche Ownerfreigabe berichtigt, enge Nachprüfung1/1PASS.
Keine funktionale Produktänderung nach diesem ersten Lauf und kein vollständiges
22/22-Ergebnis behauptet. Native Nachprüfung auf festem Korrekturpin steht aus.

Nächste Pakete: B für begrenzten Graphsender, Zertifikat/Wechselproof, eigenen
Schlüssel und CLI; C für neue API-/Web-/Loginbedienung und gezielte Browserprüfung.
Realer Testversand erst nach konkretem Betreiberabgleich von Vorlage, Empfängern
und Anzahl. AP08/09/10 bleiben ohne Go, DMS und Erkennungsänderungen außerhalb AP07.
