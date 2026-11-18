# AP06 – Webansichten und berechtigte Originalanzeige

Stand: 14.11.2026. AP06a–d samt PDF-Vorschau ist freigegeben, implementiert und
technisch isoliert geprüft. Produktlaufzeit aus `3fd5fef`; spätere Änderungen des
AP06-Abschlusses betrafen ausschließlich Browser-/Testserverwerkzeuge und Dokumentation.
AP07 hat inzwischen ein eigenes Go und einen getrennten [Teilstand](AP07-NOTIFICATIONS.md).
Kundenmigration und Umschaltung sind abgeschlossen und getrennt zurückgelesen.
Quellprüfung, isolierter Runtime-/Browsernachweis,
Kundenbereitstellung und Kundenabnahme werden getrennt geführt.

Zum AP06-Abschluss galten die eingefrorene AP03-Erkennung und der damalige
Eingangsstichtag 1. Dezember 2026, Berlin. Der spätere Kandidatenstand steht in den
[Anforderungen](ANFORDERUNGEN.md#betrieb-und-eingang).
AP06 hat keine Timer oder Benachrichtigungen aktiviert; AP08 bleibt ohne Go. DMS-Anbindung,
-Konfiguration und -Prüfung liegen vollständig außerhalb des Auftrags und
sind keine Abnahmebedingung.

## Verfügbarer Funktionsumfang

- Echte Journalübersicht mit Suche, Filtern, Seitenwahl und Status-/Fehler-/
  Dublettenzählern. Keine Demo-API und keine Ersatzbeispiele bei leerem Journal.
- Details je Vorgang/Anhang mit unveränderlichem Erstbefund, aktuellem Befund,
  Befundgeneration, Freigabe-/Retryverlauf und tatsächlichen Ablagebelegen.
- Ausdrückliche Zuordnung einzelner zulässiger unbekannter Anhänge zu PDF,
  Zahlungsavis, Mahnung oder Ignorieren. Strukturelle Sperren und technische
  Fehler lassen sich damit nicht umgehen. Neue Absichten nur mit Verwaltungsrecht,
  aktueller AD-Prüfung, Origin/CSRF und passender Quellen-/Befund-/Revisionsbindung.
- Dauerhafte technische Retryabsichten. Der manuelle Korrekturmodus übernimmt
  sie mit vorhandenen Wirkungskeys/Receipts; keine blinde Neuveröffentlichung und
  kein Verlust bereits wirksamer Kundenzuordnungen. Keine HTTP-Verarbeitung von Mails.
- Offene Browserabsichten bleiben je Benutzer/Vorgang über Dialog-/Seitenreload
  und neue Anmeldung erhalten. Ursprünglicher Body/Request-ID bleiben gleich;
  aktueller CSRF-Nachweis wird separat verwendet. Defekte Erfolgsantworten oder
  verlorene Antworten gelten erst nach passendem Serverbeleg als bestätigt.
- Zwei Kalenderjahre aktive Protokolle, danach schreibgeschützte Archivauswahl.
  Keine Datenlöschung oder Mailbewegung durch das Webarchiv.
- Versionierte Einstellungen für neue Originalvorschauen und technische
  Retryfreigaben. Bestehende dauerhafte Aufträge bleiben erhalten.

## Originalanzeige und Ressourcen

Großer nativer PDFdialog mit neuem Tab und unverändertem Download als weitere
Bedienwege; andere Formate werden als Download angeboten. Der journalgebundene
Abruf prüft tatsächliche Graphquelle, Parent/Empfangszeit, Manifest, Bytezahl und
SHA256 sowie den aktuellen Journalschnappschuss. Er verändert keine Journale oder
Mails. Bereits reservierte Abschlussziele bleiben nur mit gültigem bestehendem
AP05-Abschlussbeleg zulässig. Dessen historische Hashreihenfolge bleibt erhalten.

Genau ein API-Worker und zwei Plätze über Kindprozess, private Dateien und gesamte
HTTP-Auslieferung. Je Original maximal 25 MiB, inneres Limit 180 s, Gesamtfrist 300 s.
Ein eigenes 128 MiB großes tmpfs enthält beide Graph- und Ausgabekopien; /tmp mit 32 MiB bleibt
getrennt. Bei Abbruch werden Kinder beendet und Dateien/Platz freigegeben.
Einzel-Range, ETag/If-Range, HEAD und sicherer Dateiname sind implementiert;
HEAD ignoriert Range, unpassendes If-Range liefert das vollständige Original.

Nur die exakte Originalroute erlaubt SAMEORIGIN und frame-ancestors self.
Das übrige Portal bleibt DENY/frame-ancestors none. Nginx puffert Originale nicht
in Proxydateien; Proxy-/Sendefristen sind endlich. Der API-Service erhält dafür
zwei zusätzliche RO-Einzeldateien für Graph-Konfiguration und Zertifikat.
Der Vorschauadapter erlaubt nur GET. Migration erhält keine Graphdateien;
API/Migration erhalten weder CIFS noch Docker-Socket.

## Prüfstand und Bereitstellungsgrenze

Additives Schema 006 und frische Migration 001→006 wiederholt mit gleicher Instanzkennung
geprüft. Der tatsächliche alte Pfad 005→006 erhält Altspalten/-werte und ergänzt aktuelle
Befunde/Historie einmal. Die tatsächliche vorherige API ist mit006 und erhaltener
Konfiguration/Sitzung geprüft; kein alter Migrator oder Schema-Downgrade.
Gezielte native Sicherheits-, HTTP-, Konkurrenz-, Freigabe-/Retry- und
Vorschau-Lebensdauerprüfungen sowie unabhängige Korrekturreviews bestanden.
Historische Teilergebnisse bleiben unten ihren Quellen zugeordnet.

Fünf vollständige Browsergruppen auf festen nativen API-/Web-/Processingimages
bestanden: Rollen/Original/PDF/Download/Mobil, Freigabe mit abgeschnittener HTTP-200-
Antwort und neuer Anmeldung, Retry nach HTTP 409 und anschließender Annahme mit
Antwortverlust/neuer Revision, Teilvorgänge/Archiv/Quellfehler sowie zwei langsame
25-MiB-Streams über Nginx. Rund 100 MiB Spitze bei 128 MiB Kapazität, dritter Abruf mit HTTP 503,
nach verkürzter Testfrist von 12 s beide Plätze frei und keine privaten Verzeichnisse/Proxydateien.
Die tatsächliche Dokumentseite wurde im Dialog und neuen Tab einzeln visuell geprüft.

Testjournale/Directory/Graph waren isoliert. Eine freigegebene private Test-PDF
wurde nur lesend verwendet; Original und bestehende Kundencontainer blieben
unverändert. Private PDF-/Bild-/Betriebsnachweise liegen außerhalb dieses Repositories.
Keine alten Kundenmails registriert oder verschoben und keine erneute breite
Klassifikation.

Die anschließende Kundenbereitstellung ist separat bestätigt: geschütztes Backup,
Schema 005→006 mit erhaltenen Altwerten/Instanz/Konfiguration, neue API/Web mit
festen geprüften Imagepins und unveränderter Datenbank. Manuelles Processingprofil
aktualisiert; keine Processing-Timer gestartet. HTTPS meldet den echten Journalmodus,
HTTP leitet um und geschützte Liste/Originalroute bleiben unangemeldet gesperrt.
Das echte Journal ist leer; vollständiger Graph-GET-Scan bestätigt 0 passende
Mails/Anhänge ab dem unveränderten Stichtag. UID/RO-Bindungen und leeres
Vorschautmpfs sind zurückgelesen. Eine neue tatsächliche Kundenanmeldung für AP06
wurde nicht durchgeführt; vollständige Rollen-/Browserprüfungen erfolgten isoliert.

## Historische Teilstände

Die folgenden Nachträge dokumentieren frühere Entwicklungsstände. Aussagen wie
„geplant“, „noch offen“ oder „noch nicht implementiert“ gelten ausschließlich für
den jeweils beschriebenen Teilstand, nicht für den führenden Stand oben.

Erster Teilstand: `ProcessQueries` liest die vorhandenen AP05-Journale und
verknüpft Anhangs-, Freigabe- und Storagebelege. Keine Claims, Klassifikation,
Registrierung oder Graph-/Dateiaktionen aus diesen Leseoperationen.
Serverseitige Suche/Filter, stabile Pagination bis50Vorgänge, Details,
offene Unknown-Anhänge und Status-/Dubletten-/Fehlerzähler sind implementiert.
Anhangsfilter verwenden Exists statt vervielfachender Joins. Abfragen laufen
in einem konsistenten Snapshot, damit alte Mailrevision und neue Anhangswirkung
nicht fälschlich zu einem fertigen Vorgang kombiniert werden.

Archiv ist eine reine Leseauswahl nach der ersten Journalanlage: zwei
Kalenderjahre in Europe/Berlin, exakte Grenzsekunde gehört zur aktiven Ansicht.
29.Februar wird beim Rückgang in ein Nichtschaltjahr auf28.Februar begrenzt.
Daten bleiben vollständig erhalten; keine Löschung oder Mailarchivierung.

Sieben lokale SQLite-Gruppen bestanden: leere echte DB, Zählung mehrerer Anlagen,
Freigabezustände/strukturelle Sperre, erforderliche Mail- und Dateibelege,
begrenzte Filter/Pagination, Archiv/Schaltjahr, unveränderte Journale und echte
Snapshotkonsistenz bei paralleler Revisionsänderung. Kein nativer MariaDB-,
API-/Browser- oder Gesamt-PASS aus diesem Teilstand.

Geplant im laufenden AP06: bestehende AD-/CSRF-Grenzen an echte APIansichten
anbinden; zulässige Unknown-Entscheidungen ausdrücklich freigeben; technischen
Retry nur mit denselben Quellen-/Wirkungskeys und ohne Blindwiederholung;
großer PDFdialog über geschützte Originalroute und vorhandenen Browserviewer.
Keine zusätzliche Viewerbibliothek, kein neues ML und keine neue Plattform.

Nächster Teilstand: GET /api/processes, /api/processes/stats, /api/processes/{key}
und /api/unknown verwenden diese echten Journalprojektionen unter der bestehenden
AD-/Sitzungsgrenze. Die frühere Demo-API entfällt. Bestehende Sicherheitstests
adressieren jetzt /api/processes; drei neue HTTP-Gruppen prüfen echte leere und
gefüllte Journale, beide Rollen, Gruppenentzug und neutrale Eingabefehler.
Syntaxprüfung erfolgt; native HTTP-Ausführung ist für diesen Commit noch offen.

AP06-L1/L2, jeweils gezielter Korrekturversuch1: Der blockierte Mailzustand
operator_required hat jetzt Vorrang vor einer lediglich begonnenen Korrektur.
Der Korrekturbeleg bleibt unverändert. Auswahl, Archivkennzeichen, Leaseanzeige
und Freigabemöglichkeit verwenden pro Abfrage denselben Zeit-Snapshot.
Neun lokale SQLite-Gruppen bestanden, darunter beide gezielten Reproduktionen.
Am vorausgehenden API-Stand17ce54c bestanden native Linux-HTTP-/Sicherheitsprüfungen:
26 unterschiedliche Tests, durch importierte Testklassen49 Ausführungen. Die
Testimports sind bereinigt; kein MariaDB-/Browser-/Deployment-PASS daraus.

AP06-M1: Migration005 verwendet nun ausdrücklich ihre eingefrorenen ursprünglichen
Tabellendefinitionen (processing_schema005). Dadurch fügt ausschließlich006 neue
AP06-Strukturen hinzu. Der vorhandene005-Migrationskettennachweis und weitere
12ProcessingState-Gruppen bestanden lokal; nativer006-Nachweis folgt separat.

Freigabe-/Retryteilstand006: aktuelle Findingkopie und Generation getrennt vom
unveränderlichen Erstbefund; additive Findinghistorie, Retrybelege und versionierte
Websteuerung. Approval und Übernahme prüfen denselben aktuellen Befund samt Hash
und Generation. Webanfragen werden je Request-ID idempotent belegt, auch nach
Übernahme. Freigeber/Zeit stammen vom Server; Absicht, Übernahme und Ergebnis
werden atomar im bestehenden Audit verknüpft. Archiv bleibt schreibgeschützt.

Technischer Retry erzeugt ausschließlich eine Absicht im bestehenden manuellen
Korrekturmodus. Neue Befundgeneration nur nach abgeschlossenem Vorgänger.
Bestehende unklare Wirkungen werden in derselben Revision mit unveränderten Keys,
Receipts und Publikationszählern abgeglichen. Eine vor Publikation gescheiterte
Ablage darf nur mit belegtem Zähler0 und ohne aktiven Storageowner zurück auf
pending; erfolgreiche oder reservierte Veröffentlichungen werden nicht genullt.
Bereits wirksame Kundenzuordnungen bleiben erhalten. Kein Scheduler/Job aktiviert.

GET/PUT /api/admin/processing steuert ausschließlich neue technische Retryfreigaben
und neue Vorschauabrufe. Ein bereits freigegebener Retry bleibt ein dauerhafter
Auftrag. POST-Freigaben/Retry und PUT nutzen vorhandene admin-/Origin-/CSRF-Grenze.
Die Vorschauoption wird mit dem folgenden Originalabrufteil wirksam verdrahtet;
aktuell gibt es daraus noch keine Originaldateiroute oder fertige Oberfläche.

Lokale Nachweise:10 neue Decision-/Migration-/Konkurrenzgruppen,13 bestehende
ProcessingState-Gruppen und9 Projektionsgruppen bestanden. Native006-/MariaDB-
und neue HTTP-Schreibtests stehen am festen Commit noch aus. Kundenschema bleibt005.

NativeLinux/MariaDB zum festen006-Standf3d6e6c: neue Processing-/Testimages offline
gebaut, eingefrorene Classifierlayer unverändert. Frische echte CLI001→006 zweimal
mit gleicher Instanzkennung bestanden.53 gezielte Tests ausgeführt:52PASS,
ein HTTP-Testfehler durch uneinheitliche Testuhren (API real, Consumer eingefroren).
AP06-T1 Versuch1 vereinheitlicht beide Uhren ausschließlich im HTTP-Testfixture;
gezielter nativer Nachweis folgt. Tatsächlicher alter005→006-Pfad noch offen.

Nativer Deltaabschluss zu77e963c: fünf betroffene HTTP-GruppenPASS, AP06-T1 nach
Versuch1 geschlossen (eigenständige Testuhrursache, kein Importaliasfehler).
Die vorherigen52PASS bleibenf3d6e6c zugeordnet; kein wiederholter53/53-Gesamtlauf.
Zusätzlich tatsächlicher005→006-Pfad mit altem AP05-ProcessingimageCF93… und
Altzeilen:1Mail/2Anhänge/1Storagebeleg/1Graphabsicht. Alle ursprünglichen Spalten
und Werte unverändert, UUID erhalten, aktuelle Findings/Historie genau einmal
ergänzt. Frischer CLI001→006 zweimal ebenfallsPASS. Eigene Ressourcen bereinigt.

Originalabrufteil jetzt implementiert, noch nativ ungeprüft: ManagedOriginal hält
zwei Plätze über Childabruf, vollständigen Hash-/Größen-/Revisionsnachcheck und
komplette ASGI-Auslieferung. Inneres Limit180s, HTTP-Gesamtfrist300s, kein pathsend.
GET-only-Kindprozess nutzt bestehendes JournalMailbox und legt beide Dateikopien
im privaten Vorschautmpfs ab. Einzel-Range/HEAD/Download, Nicht-PDF nurattachment.
ExpliziterAPIworker1, eigenes128MiBtmpfs und nur zwei zusätzliche RO-Graphdateien
am API-Service. Ausschließlich exakte Originalroute SAMEORIGIN/frame-ancestorsself,
keine Proxydateipufferung, endliche Proxyzeiten; übriges Portal bleibt DENY.
Sieben neue native Prüfgruppen vorbereitet; SyntaxPASS, Ausführung noch offen.
Frontend und tatsächlicher großer PDF-Browserdialog folgen. Kein Deployment-PASS.

AP06-R1/R2 jeweils Korrekturversuch1: Bei übernommenen Entscheidungen setzt ein
technischer Retry die bestehende Zuordnung fort, statt erneut zu klassifizieren.
Freigeber/Zeit/Erstbefund bleiben erhalten; der vorhandene Korrekturbeleg wird an
die ausdrücklich freigegebene Folgegeneration gebunden. Offene Retrybelege der
Revision0 bleiben im Korrekturmodus auch nach Unterbrechung/Verzögerung auswählbar.
Zwei gezielte Reproduktionen und insgesamt12Decisiongruppen lokalPASS; nativer
Delta- und unabhängiger Nachreview folgen. Keine neue Mail-/Ablagewirkung ausgelöst.

AP06-R3 Quellkorrekturversuch1: unveränderlicher Attachment→Mail-Verweis wird
außerhalb der Entscheidungstransaktion gelesen. Innerhalb steht zuerst die
exklusive Mailsperre; anschließende mutable Beleg-/Anhangsabfragen lesen aktuell
mit FOR UPDATE. Retry beginnt direkt mit der gesperrten Mailabfrage. Derselbe
Vertrag gilt für die interne bereits-freigegeben-Grenze und Retryübernahme.
Keine globale Änderung des Isolationsgrads.12Decisiongruppen lokalPASS; die
gezielt angehaltene native MariaDB-Gegenprobe des Reviews steht noch aus.

Vorschaukorrekturen jeVersuch1: AP06-P1 ergänzt ausschließlich die vorhandene
URL-/Pagingvalidierung im GET-only-Adapter; keine generische Methodendelegation.
AP06-P2 betrifft separat den Testablauf mit dem good_worker-Spawnstub (dieser
benutzt den Graphadapter nicht): ausreichende Anlaufzeit vor dem Transferlimit,
HTTP200 muss vor blockierter Auslieferung erreicht sein und der Test sammelt
seine Antworttask auch im Fehlerfall vor Fixturecleanup ein. Die ursprüngliche
zweite Fehlermeldung war ein Timeout, kein zweiter Adapteraufruf. Die beiden
fehlgeschlagenen Gruppen werden gezielt nativ nachgeprüft; die5PASS bleiben7ab7214.

Gezielte nativeKorrekturen auf65fbd4e: R1/R2beidePASS. DeterministischeR3-Probe
unter unverändertemMariaDB REPEATABLE READ: alterProduktstand77e963c zeigt beide
Verstöße; korrigierterStand liefert409bei konkurrierenderRetryabsicht und denselben
Beleg beiidentischerApprovalrequest. ZweiVorschau-DeltagruppenP1/P2PASS;5positive
Vorschaugruppenbleiben7ab7214zugeordnet. KeinneuerbreiterGesamtlaufbehauptet.

Frontend jetzt an echte APIgebunden: aktiveVorgänge/Suche/Filter/Pagination,
Unknown-Anhangsliste, lesbaresArchiv und großerDialog mitnativerPDFiframe sowie
NeuerTab/Download. KeinefiktivenAbsender/Betreffwerte oderDemos imNormalportal.
Kategorie ohne Vorauswahl, ausdrücklicheEinzelanhangfreigabe, persistenterStatus,
Original-/aktuellerBefund/Feedback, Dubletten-/Datei-/Fehler-/Retrybelege getrennt.
Readerliest; Mutationen nurAdminbei serverseitigangezeigterZulässigkeit. Vorhandene
LDAPverwaltungbleibt; neueSchaltersteuern tatsächlicheWebfunktionen. Fehlerkachel
undneuererrors-Filter nutzen dieselbenbeidenMailzustände;10lokaleProjektionsgruppen
PASS. NochkeinFrontend-Build-/Browser-PASS. FürgezieltenOffline-APIbau kann
Dockerfile.runtime vorhandenegeprüfteAbhängigkeiten mitunverändertemLock übernehmen;
aufgelösteBasis-ID undLayerabstammungvorBauprüfen. Kundendiensteunverändert.

AP06-P3/P4 bestätigt durch unveränderte vollständige-App-Gegenprobe auf65fbd4e:
Exit0 war keinPASS; äußereBodyweiterleitung blieb nach8s bei6sBudget blockiert,
Platz/Dateien waren bereits freigegeben. HEAD/If-Range-Mismatch wurden fälschlich
als ungültigeRange416 behandelt. JeKorrekturversuch1: bestehendeAuth-/CSRF-/Rollen-
grenze alsdirekteASGIweiterleitung ohne Bodypuffer; Vorschaufristen und Platzleben
wirken so bis zum tatsächlichen send. Bereichsvalidierung erst bei relevanter
Range, HEAD und nichtpassender starkerETagbedingung erhaltenvolle200Antwort.
Permanente gezielteRegressionen ergänzt. SyntaxPASS; passende nativeAuth-/API-
und ursprüngliche unveränderte Gegenprobe folgenamfestenPin. KeinBetriebsPASS.

FrontendBuild3bd9a24 nach kontrolliertemAbrufderfestenöffentlichenLockpaketePASS;
API/Processing/Web/Testgebaut, Worker1/ComposeAPI-onlyGraphbindungen/tmpfs und
Nginxsyntaxisoliertbelegt. DiesePins enthalten nochdieP3/P4-Vorgängerversion und
sind keinefinaleDeploymentfreigabe. NeuerBau nachKorrekturprüfung nötig.

P3/P4 amfesten5255359 nativPASS:25gezielteAuth/API-/Originalgruppen und die
unverändertevolleApp-Gegenprobe bestehen. ÄußereAnfrage beendet sichinnerhalb
derFrist,Dateien/Kinderweg,beidePlätzefrei; HEAD/IfRange-Mismatch200. Astrahat
beideUrsachen nachjeVersuch1unabhängiggeschlossen. TatsächlicherOldAPIeef…-
Rückwegaufneuer006DBmitverschlüsselterKonfiguration/erhaltenerUUID/SitzungPASS,
kein alterMigrator; Kundendienste/DBunverändert. NochkeineGUI-/Deploymentfreigabe.

G1/G2 jeVersuch1: vollständigePendingabsicht ausZiel/Payload/Request-ID wird
benutzer- undvorgangsgebunden tablokal gespeichert und bis zur passendenQuittung
unverändert wiederverwendet. Detail-/Seitenneuladen und neueSitzung schreiben
keine neueRevision/Zuordnung hinein; aktuellerCSRFHeader wird separat genommen.
NeueAktionen derselbenMail bleiben bis Auflösunggesperrt. Serverbeleg wird an
dieursprünglicheRequest-/Zielbindung geprüft. UnlesbaresErfolgsJSON/fehlenderBeleg
sind Protokollfehler; Pendingbleibtbestehen. FehlerhafteGETantwort gilt nicht als
leereListe.401invalidiertdieSitzung auchbei defektemBody. Logintextbereinigt.
12NodegruppenPASS(8neuegezielteplus4bestehendeLoginabläufe), keinBrowserPASS.
DerNode-Lauf brauchtfür diebestehendeApiError-Parameterproperty TypeScript-
Transformation; ein ersterstrip-only-Testimport erreichte diesePrüfungen nicht.

G1/G2-Stand6761e05 vollständiggebaut: API/Web/Processing/Testimages mit allen
bisherigenFixes, genau1APIworker und unveränderterClassifierlayerbindung belegt.
Browsernachweisvorbereitet imTestimage: explizitmarkierter Testserver mit eigener
SQLite, synthetischerDirectory/Graph undnurlesendemInputbind einer vorhandenen
privatenPDF. KeineTestmodi/TestendpunkteimnormalenAPIimage. GeplanteGegenfälle:
nativePDFanzeige/NeuerTab/Download,Reader/Admin,AntwortverlustundneueRevision,
abgeschnittenes200JSON/neueSitzung,Einzelanhänge/Belege/Archiv/Quellfehler und zwei
25MiB-Ströme übertatsächlichesNginx mitkontrolliertlangsamenLesern. PrivateDatei
undScreenshotsbleibenintern;keine44erNeuklassifikationoderMatrixänderung.
EinunverändertesbereitsalsPDFbelegtesOriginal behält bei reintechnischemFolgefehler
seinenPDFtyp,sofernderaktuelleBefundkeineabweichendeFormatangabeenthält undMagic/
Hash/Größevollständigpassen. GezielterReadernachtest erweitert;Native-/Browser-
ausführungam folgenden festenPinnoch offen. DeutscherDialog-Schließenname ergänzt.

G1Versuch2: unmittelbarvorjedem(auch erneutem)Sendwird diegleichegespeicherte
Absicht dauerhaftaufunbestätigtgesetzt;FehlerbeimSpeichernverhindertVersand.
Payload/Request-IDbleibenunverändert. Ablehnungsabschlussprüft erneutdengesicherten
Zustand,so dass aucheineveralteteUIaktionkeinunbestätigtesErgebnisverwerfenkann.
SechsgezieltePending-NodegruppenPASS, darinsowohlApprovalalsauchRetry:
409→erneutaktiv→Send/Annahme/Antwortverlust→Storageerneuteinlesen→keinSchließen;
Speicherverweigerungsendetnichts. G2/P3/P4bleibengeschlossen;Browsernachweisfolgt.
SeparaterFormatrandfall istin65a6ca3:fehlendeaktuelleFormatangabenach reintechnischem
FolgefehlernutztdenunveränderlichenPDF-Erstbefund;vollständigeBytes/Hash/Magic
bleibenPflicht. NurdieserReadernachtestwirdgezieltnativausgeführt,keinTesthookimProdukt.
