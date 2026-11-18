# PDF-Unterlagen

Stand: 18. November 2026. AP09-Technikunterlagen geprüft; AP11-Nutzerhandbuch
eigengeprüft und am vollständigen festen Paket b565465 genau einmal unabhängig
mit PASS geprüft. Kundenrückmeldung zum Handbuch bleibt offen.

- Führende Quelle: [Technische Dokumentation](../TECHNISCHE-DOKUMENTATION.md).
- Ausgabe: [Technische Dokumentation als PDF](Technische-Dokumentation.pdf).
- Führendes [Nutzerhandbuch](../HANDBUCH-ZUM-PRODUKT.md) und [PDF](Handbuch-zum-Produkt.pdf):
  24 Kapitel, zwölf synthetische Bildschirmbilder, 26 Seiten. AP11-Go seit17.11.2026;
  AP09a hat diese Anleitung nach deren bestandener Abschlussprüfung übernommen.
- Ein vertrauliches Betriebsblatt wird separat übergeben und gehört nicht ins Repository.
- Gesonderter [Wartungsnachtrag als Markdown](../WARTUNGSNACHTRAG.md) und
  [dreiseitige PDF](Wartungsnachtrag.pdf), Stand 18.11.2026: qualifiziert
  bereitgestellte Wartung und bestätigter Sonntagstimer mit aktiver lesender
  Nachkontrolle um 03:30 Europe/Berlin, erster realer Lauf offen.
  Ergänzt die unveränderten datierten AP09-/AP11-Abgaben; finaler Dokumentreview offen.

## Reproduzierbarer Build

Der dokumentbezogene [Renderer](../../tools/build_technical_pdf.py) benötigt Python
und ReportLab mit dessen mitgelieferten Vera-Schriften. Keine neue Markdownbibliothek,
keine Netzabfrage und keine Anwendungslaufzeit nötig. Der AP09-Build verwendet
ReportLab 4.4.9. Die genaue lokale Werkzeugversion und SHA256werte stehen im
separaten festen Prüfbericht; diese Werkzeugversionen sind keine Produktabhängigkeiten.

Vom Repositoryverzeichnis aus:

```text
python -I -B tools/build_technical_pdf.py
```

Für das separat verwaltete Betriebsblatt sind Pfade ausdrücklich wählbar:

```text
python -I -B tools/build_technical_pdf.py --input <quelle.md> --output <ausgabe.pdf>
```

Unterstützt wird der hier verwendete begrenzte Markdownumfang: ein Titel, H2-/H3-
Überschriften, Absätze, flache Listen, Pipe-Tabellen, Textblöcke, Inlinecode,
Fettdruck und Links. Tabellenköpfe werden wiederholt, Schriftdateien eingebettet,
Inhaltsverzeichnis, Lesezeichen und Seitenzahlen erzeugt. Dokumentmetadaten sind
konstant. Gleiche Quelle, Renderer-, Python-/ReportLabversion und Schriftdateien
ergeben dieselben PDFbytes; eine abweichende Werkzeugversion ist neu zu prüfen.

Markdownverweise innerhalb des Repositorys bleiben relativ. Der Renderer löst sie
für die PDF vom Verzeichnis der Markdownquelle aus zu absoluten GitHub-Verweisen
auf `schelle85/CT_E-Rechnungsimporter`, Zweig `main`, auf. Dateiverweise verwenden
`blob`, Verzeichnisse `tree`; Fragmente bleiben erhalten. Ziele außerhalb des
Repositorys werden abgewiesen, externe URLs bleiben unverändert. Die verlinkten
Repositorydateien müssen im Veröffentlichungsablauf auf `main` bereitgestellt werden.
Die einzelne PDF enthält den vollständigen technischen Haupttext; vertiefende
Paketverträge werden nicht mit eingebettet.

## Nutzerhandbuch bauen

```text
python -I -B tools/build_technical_pdf.py --handbook --input docs/HANDBUCH-ZUM-PRODUKT.md --output docs/handbuecher/Handbuch-zum-Produkt.pdf
```

Der kleine Handbuchmodus ergänzt eingebettete PNGabbildungen mit Bildunterschriften,
kurze Kapitel auf eigener Seite und AP11-Metadaten. Das explizite Markdown-Inhaltsverzeichnis
zwischen den zwei TOC-Kommentarmarken bleibt in der Quelle anklickbar; die PDF erzeugt
ihr eigenes anklickbares Verzeichnis mit Seitenzahlen und Lesezeichen. Die unveränderte
AP09-Quelle erzeugt im bisherigen Standardmodus weiterhin bytegleich dieselbe Technik-PDF.
[Bildherkunft und Grenzen](../bilder/ap11/README.md).

## Freigabeprüfung

Der kleine [AP10-Builder](../../tools/build_maintenance_pdf.py) verwendet
Schriften, Stile, Markdownparser und Linkauflösung des vorhandenen Renderers.
Er ergänzt nur AP10-Metadaten/Fußzeile und drei kurze Themenblätter:

```text
python -I -B tools/build_maintenance_pdf.py
```

Ausgabe ausschließlich `Wartungsnachtrag.pdf`; AP09-/AP11-Ausgaben werden dabei
nicht neu erzeugt. Alle drei Seiten wurden gerendert und visuell geprüft.

Nach jeder Quellenänderung neu bauen, Text extrahieren und gegen Quelle abgleichen,
alle Seiten mit Poppler rendern und visuell auf Vollständigkeit, Tabellenumbrüche,
Schriften, Lesbarkeit und Seitenzahlen prüfen. Eigenprüfung und unabhängige
Abschlussprüfung sind getrennte Schritte. Keine PDF allein aufgrund eines
erfolgreichen Builds als geprüft oder als Kundenabnahme bezeichnen.
