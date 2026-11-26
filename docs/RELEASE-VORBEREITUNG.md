# Vorbereitung der ersten Produktversion

Stand: 26. November 2026. Ziel: Version 1.0.0, Übergabe am Montag 07.12.2026.
Dies ist der Entwurf der Übergabeunterlage, keine bereits erteilte Releasefreigabe.

## Gelieferter Umfang

- Interner HTTPS-Zugang mit AD-Anmeldung; Vollzugriff und Leserechte über Gruppen.
- Automatischer Abruf der direkten Inbox über Microsoft Graph, unabhängig vom
  Gelesenstatus; Eingang ab 23.11.2026, 00:00 Uhr Europe/Berlin.
- Erkennung von ZUGFeRD/XRechnung, Rechnungs-PDF, Zahlungsavis, Mahnung und
  Unbekannt; Originalablage nach Jahr, Monat und Kalenderwoche, Dublettenprüfung.
- Journal, Suche, Filter, Original-PDF-Vorschau, fachliche Zuordnung unbekannter
  Anhänge, kontrollierte technische Wiederholung und Webarchiv.
- Tages-/Wochenberichte im Portalstil, konfigurierbare Benachrichtigungen,
  Zertifikatswarnung und Administration der Graph-Zertifikatsrotation.
- Regelmäßiger Betrieb, TLS-Übernahme und sonntägliche Linuxwartung mit
  bedarfsabhängigem Neustart und getrennter Nachkontrolle.

## Aktueller belegter Lieferstand

Am 26.11. lesend bestätigt: Programmquelle
2ee04d0bb4ef72d64fcf94cb9e0f8d283acc5e41, Datenbankschema 008.
Die erste reguläre Charge mit 13 abgeschlossenen Mails und 14 unverändert
abgelegten Originaldateien ist am 24.11. nachgewiesen. Der PDF/XRechnung-Mischfall
und verständliche Hinweise je Anhang wurden gezielt verbessert.
Dokumentänderungen führen zu keiner neuen Programmbereitstellung.

## Vor der endgültigen Freigabe

1. RC03-Restkorrektur der Betriebsanzeige prüfen und bereitstellen: Bei gemeinsam
   fälligen Inbox-/Korrekturtriggern muss der Nachweis zum tatsächlich ausgeführten
   Modus passen. Ein fehlender neuer Beleg darf nicht als Erfolg ausgegeben werden.
2. Tatsächliche Kundenabläufe mit beiden AD-Rollen und die ersten neu erzeugten
   Tages-/Wochenberichte in Outlook abnehmen.
3. Die regulären Wartungsergebnisse auswerten; zukünftige Graph-Erneuerung und
   den isolierten VM-/Offsite-Restore mit Zuständigkeit und Termin übergeben.
4. Finalen Programm- und Dokumentstand sowie Image-Zuordnung festhalten;
   Releaseversion, Tag und Veröffentlichung erst nach Betreiberfreigabe erstellen.

## Betrieb und bekannte Grenzen

Unbekannt erfordert eine fachliche Entscheidung, ein technischer Fehler eine
gezielte Klärung. Einzelne Benutzerkorrekturen erzeugen kein automatisches Lernen.
Formaterkennung ersetzt keine vollständige fachliche Rechnungsprüfung.
Graph-Annahme einer Mail ist keine Empfangsbestätigung. Ein ausgefallener
Graph-Zugang kann nicht über denselben Zugang zuverlässig eine Warnmail senden.
Zukünftige Wartungs- und Rotationsläufe gelten erst nach tatsächlichem Ergebnis
als geprüft. Ein vorhandenes Backup ist kein bestandener Vollrestore.
Die technische DMS-Anbindung ist nicht Bestandteil des Importers.

Installation, Versionswechsel und Rückweg folgen den bestehenden
[Betriebsabläufen](AP08-BETRIEB.md) und der
[Technikdokumentation](TECHNISCHE-DOKUMENTATION.md). Ein früherer Code- oder
VM-Stand setzt externe Mail-, Datei- und Graph-Wirkungen nicht zurück.

## Übergabeunterlagen

- [Handbuch](HANDBUCH-ZUM-PRODUKT.md) und [PDF](handbuecher/Handbuch-zum-Produkt.pdf).
- [Technische Dokumentation](TECHNISCHE-DOKUMENTATION.md) und [PDF](handbuecher/Technische-Dokumentation.pdf).
- [Wartungsnachtrag](WARTUNGSNACHTRAG.md) und [PDF](handbuecher/Wartungsnachtrag.pdf).
- [KI-Wiedereinstieg](KI-DOKUMENTATION.md).

Anschlussdaten, Schlüssel, Betreiberkontakte, Prüfnachweise und das ausgefüllte
Abnahmeprotokoll werden getrennt vertraulich übergeben.
