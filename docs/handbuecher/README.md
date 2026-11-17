# PDF-Unterlagen

Stand: 17. November 2026. AP09-Dokumentpaket zur gemeinsamen Abschlussprüfung.

- Führende Quelle: [Technische Dokumentation](../TECHNISCHE-DOKUMENTATION.md).
- Ausgabe: [Technische Dokumentation als PDF](Technische-Dokumentation.pdf).
- Das Nutzerhandbuch aus AP11 fehlt noch; AP09a bleibt offen. Kein AP11-Go.
- Ein vertrauliches Betriebsblatt wird separat übergeben und gehört nicht ins Repository.

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

Querverweise innerhalb des Repositorys bleiben relative Verweise. Für deren Nutzung
die Markdownquelle beziehungsweise PDF mit zugehörigem Repository bereitstellen.
Die einzelne PDF enthält den vollständigen technischen Haupttext; vertiefende
Paketverträge werden nicht mit eingebettet.

## Freigabeprüfung

Nach jeder Quellenänderung neu bauen, Text extrahieren und gegen Quelle abgleichen,
alle Seiten mit Poppler rendern und visuell auf Vollständigkeit, Tabellenumbrüche,
Schriften, Lesbarkeit und Seitenzahlen prüfen. Eigenprüfung und unabhängige
Abschlussprüfung sind getrennte Schritte. Keine PDF allein aufgrund eines
erfolgreichen Builds als geprüft oder als Kundenabnahme bezeichnen.
