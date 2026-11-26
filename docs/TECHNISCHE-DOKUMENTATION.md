# Technische Dokumentation

CT E-Rechnungsimporter

Dokumentversion: RC05-Vorbereitung, 26. November 2026. Technische Betriebs- und Übergabeunterlage.
Programmstand: `2ee04d0bb4ef72d64fcf94cb9e0f8d283acc5e41`, Datenbankschema `008`.
Die Dokumentversion bezeichnet diese Unterlage; sie ist keine neue Programmversion.

## 1. Geltung und Übergabestatus

Diese Unterlage richtet sich an technische Betreiber und die kundenseitige Betreuung.
Sie beschreibt den bereitgestellten Importer, seine Abhängigkeiten, Betriebsabläufe,
Schutzgrenzen und nachgewiesenen Ergebnisse. Sie enthält ausschließlich generische
Pfade und Rollen. Tatsächliche Anschlussdaten, Dienstkonten, Instanzkennungen,
Schlüssel, Empfänger und Sicherungsorte werden getrennt vertraulich verwaltet.

Diese RC05-Fortschreibung ergänzt die zuvor geprüfte AP09-Ausgabe. Das vollständige
[Nutzerhandbuch](HANDBUCH-ZUM-PRODUKT.md) und die wöchentliche Linuxwartung sind
vorhanden. Der Betrieb wurde am 26.11.2026 lesend bestätigt; eine endgültige
Releasefreigabe oder neue Kundenabnahme folgt daraus nicht. ORGA übernimmt die
Dokumentprüfung; REVIEW prüft ausschließlich Code. Aktuelle Freigabepunkte stehen
in der [Releasevorbereitung](RELEASE-VORBEREITUNG.md).

Führend für den aktuellen AP12-Nachweis ist die [AP12-Übergabe](AP12-UEBERGABE.md).
Ältere Paketdokumente beschreiben ihren damaligen Teilstand; Aussagen wie
"Timer inaktiv" oder "noch keine Bereitstellung" sind dort historisch zu lesen.
Bei Unterschieden gelten der datierte aktuelle Lieferstand und seine qualifizierten
Nachweise. Eine zukünftige Wirkung wird nicht aus einer erfolgreichen Einzelprobe abgeleitet.

## 2. Architektur und Vertrauensgrenzen

Der Importer verbindet vorhandene Dienste und Bibliotheken. Auf der Linux-VM laufen
Docker Compose, eine lokale persistente MariaDB, eine Python-API und ein Nginx-Webdienst.
React/TypeScript bildet das Portal. Zeitgesteuerte Hostprozesse starten begrenzte
Processing- und Notificationläufe. Eine zusätzliche Queue, ein IAM-Dienst oder ein
separates Orchestrierungssystem ist nicht erforderlich.

| Verbindung | Aufgabe und Grenze |
| --- | --- |
| Browser - HTTPS - Nginx - API | Portal, Journal, Administration und berechtigte Originalvorschau; Schreibrechte prüft die API. |
| API - MariaDB | Sitzungen, Einstellungen, Journale, Freigaben und Wirkungsbelege; DB nicht öffentlich freigeben. |
| API - AD über LDAPS | Bestehende Firmenkonten, aktueller Kontostatus und direkte Gruppen; CA- und Hostnamenprüfung. |
| Host - Processing - Graph/SMB | Begrenzter Postfachabruf, persistente Verarbeitung und kontrollierte Dokumentablage. |
| Processing - Classifier | Eingefrorene PDF/XML/OCR-Erkennung; Klassifikation ohne Netzwerk, DB, Graphsecret oder SMBzugang. |
| Host - Notifications - Graph | Berichte und Warnungen mit eigenem Schlüssel und gespeichertem Versandjournal. |
| Root - Graphrotation - Verbraucher | Privates Wirkungsjournal, kontrollierter Zertifikatswechsel und Freigabe erst nach tatsächlichen Verbrauchernachweisen. |
| SMB-TLSquelle - Host - Nginx | Lesende Zertifikatsübernahme in eine lokale TLSfreigabe; getrennt vom Graph-Zertifikat. |

API und Nginx laufen ohne Root als `10001:10001` beziehungsweise `10002:10002`, mit
schreibgeschütztem Rootdateisystem, reduzierten Rechten und privaten Tmpfsbereichen.
Die API hat genau einen Worker. Sie erhält weder Docker-Socket noch SMBmount.
Der Hostkoordinator benötigt Root für geschützte Dateien, Sperren, Mountprüfung und
gezielte Containerwechsel. Seine Verantwortung wird nicht an Webanfragen delegiert.
Die Datenbank schreibt ausschließlich in ihr lokales persistentes Datenverzeichnis.

## 3. Versionen, Abhängigkeiten und Lizenzen

Die folgende Aufnahme ist vom 17.11.2026, 16:07 Europe/Berlin. Sie nennt installierte
Versionen der bereitgestellten Umgebung, keine pauschalen Mindestversionen und keine
Freigabe für deren selbstständiges Upgrade. Imageidentitäten und Deploymentbindungen
werden im geschützten Betriebsnachweis geführt. Die Vorlagen enthalten gepinnte
Basisimages; ein Tag allein ersetzt den geprüften Imagepin nicht.

| Komponente | Datierte installierte Version |
| --- | --- |
| Ubuntu / Kernel | 26.04.1 LTS / 7.0.0-1020-azure |
| Docker / Compose | 29.1.3 / 2.40.3+ds1-0ubuntu1 |
| API-Python | 3.13.18 |
| FastAPI / Uvicorn | 0.162.2 / 0.54.0 |
| SQLAlchemy / PyMySQL | 2.1.8 / 1.2.3 |
| ldap3 / MSAL | 2.9.1 / 1.39.0 |
| cryptography / requests | 50.0.2 / 2.34.2 |
| MariaDB / Nginx | 12.3.3 / 1.28.2 |

Exakte Pythonpakete stehen in [requirements.lock](../backend/requirements.lock),
Classifierpakete getrennt in [requirements-classifier.lock](../backend/requirements-classifier.lock)
und [requirements-classifier-native.lock](../backend/requirements-classifier-native.lock).
Das Web wird aus [package-lock.json](../frontend/package-lock.json) gebaut
(React/React-DOM 19.3.1, Mantine 9.7.5, TypeScript 5.9.3, Vite 7.3.7 im Lockfile;
Buildabhängigkeiten, keine separate installierte Hostaufnahme); die
direkten Abhängigkeiten und Buildwerkzeuge stehen in [package.json](../frontend/package.json).
Die Paketdateien sind die vollständige Versionsreferenz; die obige Auswahl ist kein SBOM.
Die Erkennung bleibt auf dem separat eingefrorenen AP03-/AP05-Image.

Lizenzorientierung für wesentliche Bausteine: Python verwendet die PSF-Lizenz mit
zusätzlichen Hinweisen, FastAPI und SQLAlchemy MIT, Uvicorn BSD-3-Clause und Nginx
eine BSD-Lizenz mit zwei Bedingungen. ldap3 ist LGPLv3; dies wurde bereits im
AP01-Bibliotheksentscheid berücksichtigt. MariaDB Server ist GPLv2. Maßgeblich bleiben
die Lizenztexte der tatsächlich bezogenen Versionen einschließlich transitiver Pakete,
Basisimages und OCRwerkzeuge. Diese Orientierung ist keine vollständige Lizenzprüfung.
Vor Weiterverteilung sind Lizenzhinweise und gegebenenfalls Quellbereitstellung
anhand der jeweiligen Distribution zu prüfen.

Primärquellen: [Python-Lizenz](https://docs.python.org/3.13/license.html),
[FastAPI-Lizenz](https://github.com/fastapi/fastapi/blob/master/LICENSE),
[SQLAlchemy-Lizenz](https://github.com/sqlalchemy/sqlalchemy/blob/main/LICENSE),
[Uvicorn-Lizenz](https://github.com/Kludex/uvicorn/blob/main/LICENSE.md),
[Nginx-Lizenz](https://nginx.org/LICENSE),
[ldap3-Projekt](https://github.com/cannatag/ldap3),
[MariaDB-Lizenz](https://github.com/MariaDB/server/blob/12.3/COPYING).
Die Anwendung benötigt daneben die vorhandenen Microsoft-365-, AD-, SMB- und
Hostingdienste. Deren Verträge und laufende Betriebskosten sind kein Bestandteil
dieser öffentlichen technischen Unterlage.

## 4. Voraussetzungen, Netze und Speicher

Erforderlich sind ein verwalteter Linuxhost mit Docker Compose und systemd,
zuverlässige Namensauflösung, Zeitsynchronisation sowie ausreichender lokaler
Speicher für Datenbank, Containerimages und geschützte Betriebsjournale. Die
vorhandene Dimensionierung ist kein allgemein geprüfter Lastgrenzwert. Freier
Speicher, Inodes, DBwachstum und Laufzeiten sind im Betrieb zu überwachen.

Benötigte Wege sind Browserzugriff über HTTPS, ausgehendes HTTPS zu den vereinbarten
Microsoft-Anmelde-/Graphdiensten, LDAPS zu den freigegebenen Verzeichnisservern
und SMB zur Dokumentablage sowie zur TLSquelle. Die Datenbank bleibt im internen
Containernetz. Nur die vorgesehenen Webports werden veröffentlicht; HTTP leitet
auf HTTPS um. Tatsächliche Firewallziele und Proxyvorgaben gehören ins private Betriebsblatt.

| Speicherbereich | Behandlung |
| --- | --- |
| Lokales DBverzeichnis | Dauerhaft, gesichert, ausschließlich MariaDB zugeordnet. |
| Geschützte Konfiguration | Generisch `/etc/invoice-importer`; Rootverwaltung, keine Geheimnisse im Git oder Image. |
| Dauerhafte Hostdaten | `/var/lib/invoice-importer`; Ergebnisbelege, Rotationsjournal, Inventar und Status. |
| Flüchtige Sperren | `/run/invoice-importer`; kontrolliert neu nach Boot, nicht während laufender Arbeit entfernen. |
| SMB-Dokumentablage | Geprüfter Hostmount; ausschließlich gebundener Processingverbraucher schreibt. |
| TLSquelle und lokale Releases | Quelle lesend; validierter lokaler Release für Nginx, getrennte Schlüsselrechte. |
| API-Vorschauspeicher | Privates Tmpfs 128 MiB; `/tmp` separat 32 MiB; keine dauerhafte Rechnungsablage. |

Vor jedem Processingbind prüft der Host den tatsächlichen CIFSmount einschließlich
Quelle, Mountidentität und Dateisystembezug. Er hält eine passende Bindung bis zum
Verbraucher und prüft dessen tatsächliches Gerät. Ein bloß vorhandener lokaler
Ordner bei ausgefallenem Mount reicht nicht. Dann wird vor dem Graphabruf abgebrochen;
es wird kein Ersatzimportverzeichnis angelegt. Symlinkkomponenten werden abgewiesen.

## 5. Konfiguration und Geheimnisse

Die Dateien in `deploy` sind Vorlagen. Beispielwerte dürfen nicht als fertige
Kundenkonfiguration übernommen werden. Für eine neue Umgebung sind Dateiinhalt,
Besitz, Zugriffsrechte, Mounts und sämtliche Quell-/Instanzbindungen vor Start zu prüfen.
Geschützte Hostprofile und ihre Eltern müssen Root gehören, reguläre Dateien ohne
Symlinks sein und dürfen nicht gruppen- oder fremdschreibbar sein. Profilgrößen sind begrenzt.

| Referenz | Inhalt und Schutz |
| --- | --- |
| `compose.yaml` und freigegebene Overlays | Dienstaufteilung, Netz, feste Image-/Pfadbindungen; privates Envblatt separat. |
| `runtime-host.example.json` | Erwartete DB-/API-/Nginxidentitäten, Images, Instanz, TLSwurzel und Prüfgegenstelle. |
| `processing-host.example.json` | Graph-/Processingdateien, DBbindung, Netze, Speicherwurzel und Speichergruppe. |
| `automation-host.example.json` | Processing-/Notificationimage, Profile, Zustände, öffentlicher Origin, Runtime-/TLSprofil. |
| `status-host.example.json` | Quell- und Deploymentbindung, Ergebnis-/Statusverzeichnis und Automationsprofil. |
| `rotation-host.example.json` | Fester Quellpin, APIimage, Rootjournal und geprüfte Compose-Dateien. |
| `graph-access-host.example.json` | Rootverwaltung der Graphbindung und getrennte lesbare Verbrauchersicht. |
| `graph.example.json` | Tenant, App und genau das freigegebene Postfach; keine Passwörter im JSON. |
| `processing.example.json` | Scope, Speicherwurzel, erwartete SMBquelle und ausgeschlossener Stagingbereich. |
| `ldap-bootstrap.example.json` | LDAPSserver, Gruppen und Dienstbindung; Bindpasswort separat. |
| `notification-init.example.json` | Initiale versionierte Empfänger-/Berichtseinstellungen; Beispieladressen ersetzen. |

Die API liest DBpasswort, LDAP-Bindpasswort und einen stabilen Konfigurationsschlüssel
über Secretdateien. Der Konfigurationsschlüssel schützt gespeicherte Bindgeheimnisse;
sein Verlust verhindert deren Entschlüsselung. Für Benachrichtigungen existiert ein
eigener unabhängiger Schlüssel. Graph verwendet Zertifikatsanmeldung mit privatem
Schlüssel; Bindungs- und Gateinformationen werden dem Verbraucher nur lesbar gegeben.
Die API liest keinen privaten Rootwirkungsjournalinhalt.

Geheimnisse nicht als Kommandozeilenargument, Logausgabe, Screenshot, Mail oder
Repositorydatei weitergeben. Sicherung und Wiederherstellung müssen diese Dateien
einschließlich Dateirechten abdecken. Ein reiner DBdump enthält die nötigen externen
Schlüssel nicht. Vertrauliche Übergaben benötigen einen gesonderten geschützten Weg.

## 6. Anmeldung, Rechte und Graphzugang

Die Anmeldung verwendet vorhandene ADkonten. Es gibt keinen lokalen Produktpasswort-
oder Demologin. LDAPS prüft CA und Hostnamen; Klartext, Referrals und beliebige
Serverdiscovery sind ausgeschlossen. Bis zu drei konfigurierte Server erlauben
begrenztes Failover bei Verbindungsfehlern. Falsche Benutzerkennwörter werden nicht
auf jedem Server erneut probiert. Es zählen direkte `memberOf`-Mitgliedschaften.

Die konfigurierte Lesergruppe `GR_CEO` liest; `GR_Rechnung` verwaltet. Kontostatus,
Ablauf und aktuelle Gruppen werden bei geschützten Requests erneut geprüft. Ein
Verzeichnisausfall öffnet keine Rechte, sondern führt zu einem nicht verfügbaren Zugriff.
Verwaltungsaktionen benötigen aktuellen Gruppennachweis, exakten HTTPS-Origin,
CSRFnachweis und passende Versions-/Auftragsbindung. Auch ein Wiederholungsrequest
umgeht diese Prüfung nicht. Erfolgreiche Konfigurationsänderung widerruft Sitzungen.

Der Cookie `__Host-importer_session` ist Secure, HttpOnly, SameSite=strict und auf
`/` begrenzt. MariaDB hält nur den Hash des zufälligen Sitzungstokens. Voranmeldung
gilt zehn Minuten, angemeldete Sitzung höchstens acht Stunden und 30 Minuten ohne
Aktivität. Logout widerruft serverseitig auch bei LDAPausfall. Persistente
Ratenbegrenzung und neutrale Validierungsfehler schützen den Anmeldeweg.

Graphanmeldung verwendet die freigegebene Entra-App und deren Zertifikat. Mailrechte
sind auf das vorgesehene Postfach begrenzt; positive und negative Leseprobe sowie
Testversand wurden in der Grundeinrichtung nachgewiesen. Die tatsächliche
App-/Exchange-Rollenzuordnung wird privat geführt. Rotation arbeitet ausschließlich
an der gebundenen eigenen App und erweitert keine Berechtigungen. Die Originalvorschau
erlaubt nur GET. Benachrichtigungen nutzen denselben kontrollierten Graphzugang;
ein alternativer Mailtransport ist nicht eingerichtet.

## 7. Datenbank, Journale und Migrationen

MariaDB speichert die feste Instanzidentität, versionierte Konfiguration, Sitzungen,
Audit, Graphaktionen, Mail-/Anhangsjournale, Ablagebelege, Befund-/Freigaberevisionen,
Benachrichtigungseinstellungen und Versandabsichten. Schema008 ergänzt den
Rotationskopf und gebundene Rotationsaufträge. Die Migrationen sind im
[Alembic-Verzeichnis](../backend/migrations) nachvollziehbar.

| Schemaschritt | Zweck |
| --- | --- |
| 001 / 002 | Grundmetadaten sowie AD-/Konfigurations- und Sitzungsschutz. |
| 003 | Persistente Graphaktionen und Postfachgrundlage. |
| 004 / 005 | Ablage- und gemeinsames Verarbeitungsjournal mit stabilen Wirkungsbelegen. |
| 006 | Aktuelle Befunde, Korrekturen, technische Wiederholungen und Webjournal. |
| 007 | Benachrichtigungspläne, Versandzustände und Nachweise. |
| 008 | Additive Rotationsaufträge und Rotationskopf. |

Migrationen werden nur für einen geprüften, gesicherten Lieferstand mit dem
zugehörigen Migrator durchgeführt. Sie gehören nicht zum normalen Boot. Vorher/nachher
sind Schema, Instanz, Konfigurationskopf und relevante Datenbestände getrennt
zurückzulesen. Keinen Bootstrap über eine vorhandene aktive Konfiguration erzwingen.
Ein Image-Rollback ist kein Schema-Downgrade. Eine Kompatibilität früherer Images
darf nur aus dem konkret geprüften Übergang abgeleitet werden.

Stabile Quellen-, Revisions- und Wirkungsidentitäten verhindern blindes erneutes
Publizieren. Ein Datenbankeintrag allein kann jedoch eine externe Mail-/Graph-/
Dateiwirkung nicht rückgängig machen. Bei unklarem Ausgang sind Journale und reale
Wirkung zuerst abzugleichen. Tabellen löschen, Status zurücksetzen oder eine neue
UUID erzeugen ist kein allgemeiner Reparaturweg.

## 8. Verarbeitung, Ablage und Mailabschluss

Neue Quellen kommen ausschließlich aus der direkten Inbox des vorgesehenen
Postfachs ab **23. November 2026, 00:00 Europe/Berlin**. Gelesene und ungelesene
Nachrichten werden berücksichtigt. Ältere Mails bleiben
unangetastet. Paging und Quellmanifest werden vor äußeren Wirkungen vollständig
gebunden. Die Originalbytes, tatsächliche Bytezahl und SHA256 sind maßgeblich.
Ein Empfangs- oder Dateiname allein ersetzt keine Quellenprüfung.

Die Erkennung unterscheidet E-Rechnungen, Rechnungs-PDFs,
Zahlungsavise, Mahnungen/Zahlungserinnerungen, unbekannte Dokumente, ignorierte
Anhänge und technische/strukturelle Fehler. Sie ist Formaterkennung, keine
vollständige fachliche Rechnungsvalidierung. ZUGFeRD bleibt als Original-PDF erhalten.
Erkannte relevante Anhänge werden unabhängig vom Gesamtergebnis der Mail passend
abgelegt. Unklarheiten können ausdrücklich je zulässigem Anhang zugeordnet werden;
strukturelle Widersprüche und technische Sperren lassen sich damit nicht umgehen.
Es gibt kein automatisches Lernen aus einzelnen Benutzerentscheidungen.

Ablage und Dublettenerkennung verwenden das vorhandene AP04register. Name und
Bytegröße bestimmen Dubletten innerhalb der aktuellen Kalenderwoche. Andere
Namenskonflikte erhalten einen Zusatz; vorhandene Dateien werden nicht überschrieben.
Wirkungsbelege bleiben erhalten, auch wenn ein nachgelagertes System die abgelegte
Datei entnimmt. Dessen Import, Konfiguration und Prüfung liegen außerhalb des Auftrags.

| Zustand | Technische Bedeutung und Folge |
| --- | --- |
| Pending / busy | Arbeit oder reservierter Besitzer; noch kein erfolgreicher Abschluss. |
| Unbekannt | Lesbarer, gewöhnlich nicht eindeutig zugeordneter Anhang; ausdrückliche zulässige Zuordnung möglich. |
| Failed | Technischer/struktureller Fehler; Ursache klären und gegebenenfalls gezielte technische Wiederholung freigeben. |
| Dublette | Regelgebundener vorhandener Ablagefall; kein pauschaler erneuter Schreibauftrag. |
| Ungewisse Wirkung | Erst reale Wirkung und bestehenden Beleg abgleichen; kein blindes Wiederholen. |
| Erfolg | Erforderliche Ablage, Mailziel und gegebenenfalls Fahne sind bestätigt. |

Für gemischte Anhänge gilt die Mailzielpriorität:
`Failed > unzugeordnet (Unbekannt/Dublette) > Mahnung > Nachfragen (PDF) > Zahlungsavis > Success`.
Ohne Relevantes wird unzugeordnet gewählt. Mehrere relevante Anhänge setzen die
vorgesehene Fahne. Eine enge Signaturbild-Zählausnahme benötigt file+inline,
normalisierten image-MIME und ein vollständig hashgebundenes ignoriertes AP03finding;
andere Anhänge werden dadurch nicht ausgeblendet. Nach Move werden Ziel und Fahne
gemeinsam nachgeprüft. Bereits wirksame Geschwister bleiben bei Teilfehlern erhalten.

Webfreigaben erzeugen dauerhafte gebundene Absichten. Die gemeinsame Verarbeitung
übernimmt sie später mit bestehenden Wirkungskeys und Belegen. Vorschau oder
HTTPklick verarbeiten keine Mail unmittelbar. Der Originalabruf prüft Graphquelle,
Manifest und Bytes, ist lesend, erlaubt zwei parallele Originalantworten bis je
25 MiB und verwendet endliche Fristen. Das Webarchiv nach zwei Kalenderjahren
ändert nur die Ansicht; es löscht keine Daten und bewegt keine Mails.

## 9. Zeitpläne, Sperren und Ressourcen

Am datierten Betriebsstand sind sieben systemd-Timer aktiv und enabled. Kalender
verwenden `Europe/Berlin`, persistente Fälligkeiten, eine Sekunde Genauigkeit und
keine zufällige Verzögerung. Gespeicherte GUIzeiten sind allein kein Nachweis eines
laufenden Hosttimers. Maßgeblich sind tatsächliche Units und frischer gebundener Status.

| Timer | Fälligkeit |
| --- | --- |
| `invoice-processing-inbox.timer` | Alle fünf Minuten. |
| `invoice-processing-corrections.timer` | Alle 15 Minuten. |
| `invoice-notifications.timer` | Jede Minute, Sekunde 00. |
| `invoice-tls.timer` | Stündlich. |
| `invoice-status.timer` | Jede Minute, Sekunde 20. |
| `invoice-rotation-daily.timer` | Täglich 03:35. |
| `invoice-rotation-opportunity.timer` | Jede Minute, Sekunde 40. |
| `invoice-maintenance.timer` | Sonntag, 03:00 Uhr Europe/Berlin; bedarfsabhängiger Neustart. |

Manuelle und automatische Verarbeitung teilen dieselbe Hostsperre. Ein belegter
Job wird zurückgestellt; gemeinsame Fälligkeiten werden begrenzt und fair nachgeholt.
Ein Lauf wählt höchstens 50 Kandidaten und verarbeitet höchstens 20 Quanten bei
780 Sekunden Gesamtbudget. Ein neues Quantum benötigt mindestens 540 Sekunden
Restbudget, seine Frist ist höchstens 500 Sekunden; Kindbereinigung ist berücksichtigt.
Ältere AP05grenzen beschreiben den historischen manuellen Vertrag.

Graph429 lässt unmutierte Journalabsichten bestehen. Retry-After wird nicht
verkürzt; die Automatik teilt eine Processingrückstellung mit konservativem
Fallback. Keine unbeschränkte interne Retrystorm. Notification plant und beobachtet,
wählt höchstens eine Sendung und gleicht deren Status getrennt innerhalb eines
80-Sekunden-Budgets ab; der Host begrenzt den Lauf auf 95 Sekunden. Testmails werden
von der Automatik ausgeschlossen.

Die globale Reihenfolge der Sperren ist Rotationswriter, Lifecycle, Processing,
Notifications, Graph. Ein tatsächliches Prozess-/cgroupende zählt; ein abgelaufener
Zeitstempel allein beweist keine Ruhe. Unbekannte Prozesse oder Wirkungen sperren
den Abschluss. Flüchtige Sperrverzeichnisse nicht von Hand leeren.

## 10. Start, Drain, Stopp und Neustart

Die Hostentrypoints und Profile werden als geprüfte feste Dateien installiert.
Der gemeinsame stdlib-Einstieg `run-automation.py` bietet die Modi `start`, `drain`,
`inbox`, `corrections`, `notifications`, `tls` und `status`. Root startet Python
isoliert mit absoluten Pfaden und den geschützten Profilen. Die konkreten Aufrufe
stehen im [AP08-Betriebsvertrag](AP08-BETRIEB.md) und in den gelieferten Units.
Die nachfolgende Folge ist ein Betreiberverfahren für einen freigegebenen Eingriff.

1. Vor Start Images, Konfiguration, Instanzbindung, DBdaten und echte Mounts prüfen.
2. Start erhält die bestehende DB und wartet auf deren Gesundheit, danach API,
   Nginx, TLS/HTTPS und Bereitschaft mit derselben Instanz. Kein Build, Pull oder
   automatischer Schemawechsel beim Boot.
3. AP12startup liest gebundene Rootjournale, tatsächliches Graphmaterial und den
   Gatezustand. Wiederaufnahme darf eine vorhandene Pause oder einen fremden
   Drain nicht aufheben. Unklare Registrierung erzeugt kein neues addKey.
4. Vor Wartung den kontrollierten Drain verwenden. Er schreibt zuerst die eigene
   Pause und wartet dann auf Lifecycle-, Processing- und Notificationruhe.
5. Timerstopp allein reicht nicht: zugehörige Services, Kindprozesse und unklare
   Wirkungen prüfen. Drain lässt das Portal erreichbar. Ein zusätzlicher
   API-/Nginx-/DBstopp braucht eine passende gesonderte Eingriffsfolge.
6. Nach Wiederanlauf HTTPS/Instanz/Schema, Mounts, Timer, Gate, letzten Jobausgang
   und unklare Aufträge zurücklesen. Pause nur durch ihren zugeordneten Ablauf
   und nach bestätigtem Zustand lösen.

Die belegten kontrollierten Boots sind keine generelle Freigabe zum Neustart
während einer offenen Zertifikatsoperation. Bei unbekanntem Prozess, nicht
auflösbarer Wirkung oder widersprüchlichem Journal zuerst Betreuung hinzuziehen.

## 11. HTTPS-Zertifikate und Graphrotation

HTTPS und Graph verwenden getrennte Zertifikate und Lebenszyklen. Das stündliche
TLSverfahren liest die freigegebene SMBquelle, prüft begrenzt Material, Kette,
Schlüsselzuordnung, Gültigkeit und vertrauenswürdigen Peer und übernimmt einen
lokalen Release kontrolliert. Anschließend erfolgen Nginxreload und HTTPS-/
Bereitschaftsprüfung. Fehler und unklarer Reload werden mit reserviertem Rückweg
behandelt. Der Altstand wird nicht vor bestätigtem Abschluss entfernt. Ein
PKCS12-Legacyweg gilt nur für das bestätigte Quellformat; keine globale Änderung
der OpenSSL-Sicherheit. Dieser Weg erneuert kein Graph-Zertifikat.

Graphrotation startet als SQLauftrag mit ursprünglicher UUID, Akteur, Scope,
Instanz, erwartetem Stand und altem Fingerprint. Der Adminklick speichert diesen
Auftrag; Root führt die Wirkung später aus. Bei verlorener Antwort bleibt dieselbe
Auftragsidentität erhalten. Zuerst lesen, ob der Auftrag angenommen wurde; keine
neue UUID als vermeintlicher Retry. Rechte und CSRF werden trotzdem aktuell geprüft.

Der Rootablauf erzeugt einen RSA3072-Nachfolger mit 180 Tagen Gültigkeit und
registriert ihn über die gebundene eigene App. Eine dauerhafte Wirkungsabsicht
geht dem einmaligen addKey voraus. Bei unklarem Registrierungsausgang wird nur
gezielt lesend abgeglichen, nicht nochmals registriert. Kandidatenprobe und
produktiver Verbrauchernachweis sind getrennt.

Die Übernahme benötigt tatsächliche API-, Processing-/CIFS- und Notificationbelege
mit passendem Material und Image sowie einen gesonderten frischen Abschlussproof.
Erst der versiegelte Hostabschluss erlaubt das Gate dauerhaft. Ein nötiger
APIwechsel erhält DB und Nginx; anschließend werden Nginxauflösung und externes
HTTPS geprüft. Der Altweg benötigt gültige private Altbytes und erneut alle alten
Verbraucher plus Proof. Eine unklare Beweislage bleibt geschlossen oder pausiert.

Automatische Erneuerung ist aktuell erlaubt; die Tagesprüfung um 03:35 und die
minütliche Gelegenheit sind aktiv. Das vorgesehene Erneuerungsfenster liegt
zwischen einer Stunde und 30 Tagen Restgültigkeit. Der erfolgreiche manuelle
Wechsel belegt noch keinen späteren automatischen 30-Tage-Auslöser.

Nach erfolgreichem Wechsel bleibt der Altkey höchstens sieben Tage und nur innerhalb
seiner Restgültigkeit in Überlappung. Bereinigung darf ausschließlich eindeutig
zugeordnetes eigenes Altmaterial entfernen. Bereits vorhandenes Material benötigt
explizite Rootzuordnung; ein Hash allein beweist keinen Besitz. Aktive Operation,
Pause, unbestätigter Job oder unklare Entfernung sperren weitere Wirkung.
Ein unbekanntes removeKey wird nicht blind wiederholt. Boot setzt die Frist nicht
neu. Versiegelte Historie und öffentliche Retirementbelege bleiben nach der
zulässigen Löschung privater Altbytes erhalten. Spätere produktive Bereinigung
ist zum Dokumentstand noch nicht nachgewiesen.

Sind alle nutzbaren Appzertifikate abgelaufen oder fehlen die passenden privaten
Bytes, kann die normale Selbstrotation nicht helfen. Dann ist ein eigener
Wiederherstellungsauftrag mit berechtigtem Entraadministrator nötig: Betrieb
pausieren, ursprüngliche Bindungen und unbekannte Wirkungen erhalten, einen
konkreten Material-/Journalübernahmeplan prüfen und neue Anmeldung, drei
Verbraucher, Abschlussproof und HTTPS vor Freigabe nachweisen. Ein manueller
Dateitausch oder erneuter Bootstrap ist kein Resetweg. Dieser Ausnahmeablauf ist
nicht als automatisches Werkzeug geliefert oder nativ abgenommen.

## 12. Überwachung, Meldungen und Fehlersuche

`/api/health/ready` prüft DB, Schema und aktiven Konfigurationskopf. Es ist kein
dauerhafter Nachweis von AD, Graph, SMB oder einer komplett funktionierenden
Verarbeitung. Diese Abhängigkeiten benötigen eigene frische Zustandsbelege.
Der Hoststatus bindet Quelle, Deployment, Instanz, Boot und Erzeugungszeit. Fehlende,
ungültige oder fremd gebundene Daten sowie Alter über 180 Sekunden oder mehr als
30 Sekunden Zukunft werden als unbekannt behandelt. Unbekannt bedeutet keine
bestätigte Aktivität und nicht automatisch Inaktivität.

Systemdjournal und begrenzte Hostresultate zeigen Jobstart, Ergebnis, Sperrdeferred,
Zeitbudget und Mount-/Start-/TLSfehler. Portaljournale zeigen gespeicherte
Mail-/Anhangszustände, Befunde, Freigaben und Belege. Audit und Versandhistorie sind
von einem bloßen aktuellen Bildschirminhalt zu unterscheiden. Keine geheimen
Requestinhalte oder privaten Schlüssel zur Fehlersuche in Protokolle aufnehmen.

Benachrichtigungen umfassen Zertifikate, Tages-/Wochenberichte, Fehlerbündel,
Ausfälle und Wiederherstellung gemäß versionierter Einstellungen. Lesen eines
Berichts verschickt keine Mail. Ein akzeptiertes HTTP202 belegt Graphannahme,
keinen Empfang beim Empfänger. Bei unbekanntem Sendeausgang vorhandenen Slot und
Status abgleichen; kein erneuter Testversand als Diagnoseersatz. Bei Graphausfall
kann der gleiche Graphweg keine Ausfallmail garantieren; Portal und Hostkontrolle
bleiben erforderlich. Tages- und Wochenberichte werden seit der Bereitstellung
vom 24.11.2026 als HTML im Portalstil erzeugt. Die fachliche und visuelle Abnahme
der ersten regulär neu erzeugten Berichte in Outlook bleibt gesondert offen.

| Beobachtung | Nächster technischer Schritt |
| --- | --- |
| Portal/HTTPS nicht bereit | DNS, Peer/TLS, Nginx und APIhealth mit fester Instanz prüfen, dann DB-/Startresultat. |
| Anmeldung scheitert | LDAPSreichweite, CA, Hostname, Dienstbindung und direkte Gruppen prüfen; keine Rechte lokal umgehen. |
| Kein Import | Stichtag/Inboxquelle, Timer/letzten Job, Pause/Gate, Sperren und echten CIFSmount prüfen. Ein Leerabruf kann korrekt sein. |
| Unknown / Failed | Quellen-/Anhangsbefund und bestehenden Beleg lesen; nur zulässige Zuordnung oder gezielte technische Freigabe. |
| Alte Betriebsanzeige | Statuscollector, Zeitbasis und Bindungen prüfen; keine Aktivität aus altem grünen Status ableiten. |
| Unklarer Mail-/Datei-/Graphausgang | Ursprüngliche Identität und Journal sichern, reale Wirkung lesen und abgleichen; keine UUID-/Statusrücksetzung. |
| Rotation blockiert | Rootjournal, Pause, Material, Verbraucher und Proof prüfen; Gate nicht von Hand auf allowed setzen. |
| Bereinigung fällig, aber blockiert | Eigentum, Altgültigkeit und unbekannte Operation klären; fremde Appkeys erhalten. |

Der Adminstatus wird regelmäßig aktualisiert. Eine überfällige Tagesprüfung wird
nach zwei Stunden sichtbar. Bei höchstens 24 Stunden Zertifikatsrestlaufzeit ist
Betreiberhilfe innerhalb einer Stunde erforderlich, unter einer Stunde sofort.
Eine solche Warnung ist keine Aufforderung zu einer weiteren automatischen
Registrierung neben einem bestehenden Auftrag.

## 13. Sicherung und Wiederherstellung

Tägliche VM-/Offsite-Sicherung einschließlich SMBserver ist vom Betreiber bestätigt.
Ein vollständiger VM-/Offsite-Restore mit anschließendem Gesamtfunktionsnachweis
ist nicht belegt. Vor dem AP12deployment wurden logischer DBdump, relevante
Konfiguration/Dateien und Rechte gesichert sowie Manifest, Instanz und Schema
zurückgelesen. Das ist keine tatsächlich ausgeführte DBwiederherstellung.

| Bestandteil | Warum erforderlich |
| --- | --- |
| Konsistente MariaDBsicherung | Instanz, Einstellungen, Journale, Wirkungen, Sitzungen und Aufträge. |
| Konfigurations- und Notificationkey | Entschlüsselung der dazugehörigen gespeicherten Geheimnisse. |
| Graphmaterial alt/neu und Rootjournal | Gebundene Wiederaufnahme, Eigentum, Gate, Inventar und versiegelte Historie. |
| Hostprofile, Units, Bindungen und Pins | Derselbe geprüfte Start-, Mount- und Verbraucherpfad. |
| LDAP-/TLSdateien und Zugangsmaterial | Vertrauensketten und tatsächlicher Betriebszugang; Schlüssel besonders schützen. |
| SMB-Dokumentdaten und Ablageregister | Konsistenz externer Dateien mit persistenten Ablagebelegen. |

Sicherungen verschlüsselt und zugriffsbeschränkt lagern; Schlüssel und
Wiederherstellungszugänge getrennt verfügbar halten. Ein erfolgreicher Sicherungsjob
ersetzt keinen Rücklese- und Restoretest. Dateirechte, Eigentümer und private
Materialgeneration gehören zur Wiederherstellung, nicht nur die sichtbaren JSONwerte.

Vor einem geplanten konsistenten Sicherungs-/Restoreeingriff neue Arbeit per Drain
sperren und tatsächliche Ruhe einschließlich unbekannter Wirkungen klären. Aus einem
Snapshot kann nicht auf den damaligen Zustand externer Graphkeys, versandter Mails
oder bereits entnommener SMBdateien zurückgesprungen werden. Deshalb nach Restore
zuerst reale externe Wirkung, Originalaufträge und Schlüsselbestand abgleichen,
Gate/Pause konservativ halten und erst dann kontrolliert freigeben. Keine pauschale
Neuinitialisierung, Tabellenleerung oder Neuregistrierung.

Isoliert geprüft sind bestimmte Hostwiederaufnahmezustände, einschließlich Verlust
flüchtiger `/run`-Sperren. Ein ursprünglicher Restorehelper-Aufruf blieb mit
AssertionError fehlgeschlagen; seine Ursache ist unbewiesen. Ein anschließender
rein lesender Zustandsabgleich qualifiziert den erreichten Zustand, ohne den
Fehlversuch umzudeuten. Das ersetzt weder vollständigen VMrestore noch einen
erneuten Boot oder eine bewiesene erfolgreiche native Fehlerfallserie.

## 14. Update, Rückweg und Zuständigkeiten

Ein Update ist ein gesondert freigegebener Eingriff. Vorher festen Quellstand,
geprüfte Images, Schemaübergang, Sicherung, Mounts, externe Wirkungen und
konkreten Rückweg festlegen. Keine ungeprüften Pulls, Rebuilds oder allgemeines
`compose down -v`. DB-/Instanzidentität und vorhandene Konfiguration erhalten.
Neue Images nur gezielt übernehmen und anschließend DBzustand, Schema, Instanz,
HTTPS, ADzugang soweit beauftragt, Status und betroffene Verbraucher separat prüfen.

Ein Rückweg verwendet die zuvor gesicherten und tatsächlich kompatiblen Images
und Dateien. Rücksetzen des Codes macht eine Migration oder Graphregistrierung
nicht rückgängig. Zertifikatsrückweg folgt ausschließlich dem gebundenen
AP12verfahren und gültigem Altmaterial. Unklare Wirkung oder fehlender Proof
braucht eine gezielte technische Entscheidung, keinen unkontrollierten Komplettreset.

| Zuständigkeit | Aufgabe |
| --- | --- |
| Technischer Betreiber | Host, Sicherung/Restore, Systemzeit, Netze, Mounts, TLSquelle, Secrets, Drain und freigegebene Eingriffe. |
| AD-/Microsoft-365-Verantwortliche | Konten, Gruppen, Vertrauensketten, freigegebene App-/Postfachrechte und externe Änderungen. |
| Kundenseitige Verwaltung | Zulässige fachliche Zuordnungen, freigegebene Einstellungen und sichtbare Warnungen an Betreuung melden. |
| Entwicklung / unabhängige Prüfung | Feste Lieferstände, nachvollziehbare Änderungen und abgegrenzte Nachweise vor Übernahme. |

Die konkreten Ansprechpartner und Eskalationskontakte werden vertraulich übergeben.
AP10 ist installiert: Linuxwartung sonntags um 03:00 Uhr Europe/Berlin,
mit bedarfsabhängigem Neustart und lesender Nachkontrolle um 03:30 Uhr.
Der verspätete Start am 22.11. endete vor der Paketinstallation; der reguläre
vollständige Sonntagslauf bleibt nachzuweisen. Wartungsneustarts sind mit
laufenden Rotationen zu koordinieren. Einzelheiten und Zeitgrenzen enthält der
[Wartungsnachtrag](WARTUNGSNACHTRAG.md). Datenbankschema- oder Anwendungsupgrades
werden dadurch nicht automatisch freigegeben.

## 15. Abnahmebelege und offene Grenzen

| Bereich | Tatsächlicher Nachweis und Grenze |
| --- | --- |
| AD / AP01 | Echte Anmeldung, Rechte und Gesamtumfang durch Kunden abgenommen. Keine neue echte Kundenanmeldung aus späteren isolierten Browserfixtures ableiten. |
| Erkennung / AP03 | Eingefrorener Quell-/Runtime-/Dateiprüfstand, ergänzte Titelvarianten separat bestätigt; fachliche Restfälle und Gesamtfreigabe offen. |
| Ablage / AP04-05 und RC03 | Native Grundlagenprüfungen; zusätzlich am 24.11. echte Erstcharge mit 13 abgeschlossenen Mails und 14 anhand Größe, Hash und Zielpfad bestätigten Originaldateien. |
| Journal / AP06 | Native Sicherheits-/Konkurrenz-/Vorschauprüfungen und fünf isolierte Browsergruppen; Kundenmigration und separate Betriebsreadbacks. |
| Meldungen / AP07 | Quellen, MariaDB und isolierter Browser geprüft; feste Testmail mit genau einer Reservierung/202, Empfang nur im eigenen Abnahmepostfach. |
| Betrieb / AP08 | Aktive Zeitpläne, Leerlaufläufe, Tages-/Wochenbericht je einmal 202, TLSübernahme und No-op, kontrollierter Boot und spätere Statusphasenprüfung. |
| Rotation / AP12 und RC01 | Echter zweiter Wechsel mit drei Verbrauchern und Abschlussproof bestätigt; verwalteter alter Schlüssel am 24.11. bereinigt. Erste regulär fällige automatische Erneuerung bleibt ein zukünftiger Betriebsnachweis. |
| Erster Rotationsversuch | Kontrollierter Rückweg committed/old; ursprüngliche Ursache offen, Kandidat und terminaler Fehlauftrag erhalten. Erfolg des zweiten erklärt den ersten nicht. |
| AP12-Boot / Wiederaufnahme | Genau ein kontrollierter Kundenboot; API/DB/Nginx und Images erhalten, neues Graphmaterial, sieben Timer, CIFS und HTTPS gesund. Isolierte Altmaterial- und vorbereitete Neumaterialzustände gesondert qualifiziert. |
| AP12-Browser | Sieben isolierte Funktionsgruppen und Sichtprüfung. Ursprüngliches natives false wegen genau eines Reload-GETabbruchs bleibt erhalten; nur der konkret abgegrenzte Offlinefall ist akzeptiert. |

Der zweite reale Wechsel setzte nach unklarer Registrierung denselben Auftrag
nach rein lesendem Abgleich fort; es erfolgte keine zweite Registrierung dieses
Kandidaten. Die isolierte Altmaterialwiederaufnahme war erfolgreich. Der Fall mit
verlorenem flüchtigem Laufzustand erreichte vorbereitete neue Übernahme mit
erhaltener Pause; dort wurde die API gezielt neu erzeugt, DB/Nginx blieben erhalten.
Dies wird nicht als vollständig abgeschlossener neuer Wechsel umgedeutet.

Offen bleiben der zukünftige reguläre Erneuerungsauslöser, vollständiger
VM-/Offsite-Restore, der vollständige Sonntagswartungslauf, erste reguläre Berichte
in Outlook und die fachliche Abnahme am aktuellen Stand mit beiden AD-Rollen.
Die Betriebsanzeige kann bei gemeinsam fälligen Inbox-/Korrekturtriggern zeitweise
einen fehlenden neuen Ergebnisbeleg anzeigen; die Zuordnung zum tatsächlich
ausgeführten Modus ist als RC03-Restkorrektur offen. Die PDF/XRechnung-Mischfälle
und verständlichen Hinweise wurden im gelieferten Stand gezielt verbessert.
Historische Fehlversuche bleiben unverändert als solche dokumentiert.
Die DMS-Anbindung bleibt außerhalb des Auftrags.

## 16. Führende Quellen und PDF-Erzeugung

Für vertiefte technische Verträge gelten die vorhandenen Quellen im selben Repository:

- [Anforderungen](ANFORDERUNGEN.md), [Arbeitsplan](ARBEITSPLAN.md) und [Betriebsstand](BETRIEBSSTAND.md).
- [AD und Sitzungen](AP01-SECURITY.md), [Graphgrundlage](AP02-GRAPH.md) und [Erkennung](AP03-RECOGNITION.md).
- [Ablage](AP04-ABLAGE.md), [Processing](AP05-PROCESSING.md) und [Runtime](AP05-RUNTIME.md).
- [Web und Vorschau](AP06-WEB.md), [Benachrichtigungen](AP07-NOTIFICATIONS.md) und [Betreiberweg](AP07-OPERATOR.md).
- [Betriebsautomatik](AP08-BETRIEB.md) sowie [AP12-Übergabe](AP12-UEBERGABE.md).
- [Rotationsvertrag](AP12-GRAPH-ZERTIFIKATSROTATION.md), [Hostablauf](AP12-HOSTABLAUF.md), [Automatik](AP12-AUTOMATIK.md), [Admin-API](AP12-ADMIN-API.md), [Eigentum](AP12-OWNERSHIP.md) und [Bereinigung](AP12-CLEANUP.md).
- [KI-Wiedereinstieg](KI-DOKUMENTATION.md), [Dokumentationsplan](DOKUMENTATIONSPLAN.md) und [PDF-Buildhinweise](handbuecher/README.md).

Die Markdownquelle ist führend. Der schmale dokumentbezogene Renderer verwendet
ReportLab und dessen eingebettete Vera-Schriften, erzeugt Inhaltsverzeichnis,
Lesezeichen und Seitenzahlen ohne Netzwerkzugriff. Aufruf im Repository:

```text
python -I -B tools/build_technical_pdf.py --document-label "RC05 | Dokumentstand 26.11.2026"
```

Die Ausgabe liegt unter `docs/handbuecher/Technische-Dokumentation.pdf`. Für
bytegleiche Reproduktion sind identische Quelle, Renderer-, Python- und
ReportLabversion sowie dieselben mitgelieferten Schriftdateien nötig. Der Build
verwendet konstante PDFmetadaten; ein Dokumentcommit wird nicht in seine eigene
Ausgabe eingebettet. Nach jeder Änderung PDF neu erzeugen, Text vollständig
extrahieren, alle Seiten rendern und sichtbar prüfen. Eine aktuelle PDF ohne
passende Quelle ist keine abgeschlossene Dokumentlieferung.
