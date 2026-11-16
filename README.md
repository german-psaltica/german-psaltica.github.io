# German Psaltica

Statische Hugo-Website für die Notenbibliothek **German Psaltica**: 440 PDFs mit
byzantinischer Kirchenmusik in deutscher Sprache, durchsuchbar nach Titel, Fest,
Komponist, Bereich und Modus.

Die Website bietet:

- eine durchsuch- und filterbare Gesamtbibliothek,
- nach Ordnern gegliederte Bereichsseiten,
- eine Detailseite pro PDF mit Vorschau, Download und Metadaten,
- automatisch erzeugte Vorschaubilder der ersten Seite,
- ein standardmäßig ausgeblendetes Archiv,
- helles und dunkles Farbschema sowie eine mobile Ansicht.

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `GermanPsaltica/` | Unveränderte Quell-PDFs (256 MB) |
| `scripts/build_library.py` | Scannt die PDFs und erzeugt Daten, Seiten und Vorschauen |
| `data/library.json` | Generierter Katalog (Metadaten aller Noten) |
| `data/categories.json` | Redaktionelle Beschreibungen, Icons und Akzentfarben der Bereiche |
| `content/library/` | Generierte Bereichs- und Detailseiten |
| `static/thumbs/` | Generierte Vorschaubilder (JPEG) |
| `layouts/`, `assets/` | Templates, CSS und JavaScript |
| `public/` | Build-Ausgabe (nicht bearbeiten) |

Die PDFs werden über einen Hugo-Modul-Mount aus `GermanPsaltica/` unter
`/library/` ausgeliefert. Sie werden also nicht kopiert oder verändert.

## Voraussetzungen

- Hugo Extended **0.158 oder neuer**
- Python **3.10 oder neuer**
- `poppler-utils` mit `pdfinfo` und `pdftoppm`
- optional: `make`

Unter Debian/Ubuntu:

```sh
sudo apt install hugo poppler-utils python3
```

## Schnellstart

```sh
make build     # Daten erzeugen und Website nach public/ bauen
make serve     # Entwicklungsserver auf http://127.0.0.1:1414/
```

Ohne `make`:

```sh
python3 scripts/build_library.py --jobs 6
hugo server --bind 127.0.0.1 --port 1414
```

Für einen Produktionsbuild:

```sh
python3 scripts/build_library.py --jobs 6
hugo --minify --cleanDestinationDir
```

## Noten hinzufügen oder ändern

1. PDF unter `GermanPsaltica/` ablegen, umbenennen oder entfernen.
2. `python3 scripts/build_library.py --jobs 6` ausführen.
3. `hugo --minify` neu bauen.

Das Skript ist idempotent. Vorschaubilder werden nur neu erzeugt, wenn das
zugehörige PDF neuer ist als das Bild. Weitere Optionen:

```sh
python3 scripts/build_library.py --no-thumbs      # ohne Vorschauen (schnell)
python3 scripts/build_library.py --force-thumbs   # alle Vorschauen neu
python3 scripts/build_library.py --jobs 8         # mehr parallele Prozesse
```

Ordner mit den Namen `archiv`, `archive`, `alt`, `Vorübergehende Versionen`
sowie Ordner, die mit `99_` beginnen, gelten automatisch als Archiv. Ihre Noten
sind im Katalog standardmäßig ausgeblendet und lassen sich über
„Archiv einbeziehen“ einblenden.

Titel, Modus, Datum, Seitenzahl und Dateigröße werden aus Dateiname und
PDF-Metadaten abgeleitet. Bereichsbeschreibungen und Gestaltung der
Kategoriekacheln stehen in `data/categories.json`.

## Veröffentlichen

`public/` enthält eine vollständig statische Website und kann auf jedem
Webserver oder Static-Host ausgeliefert werden. Vor dem Veröffentlichen die
`baseURL` in `hugo.toml` auf die endgültige Adresse setzen.

Wichtig: Beim Build müssen sowohl `GermanPsaltica/` als auch die generierten
Dateien vorhanden sein, weil die PDFs per Modul-Mount eingebunden werden. Für
einen reinen Hugo-Build ohne Python muss `content/library/`, `data/library.json`
und `static/thumbs/` mit ausgeliefert bzw. versioniert werden.

## Rechte

Die Rechte an den Noten liegen bei den jeweiligen Urheberinnen und Urhebern.
Die Website stellt die PDFs ausschließlich zur Einsicht und zum Studium bereit.
Vor einer weiteren Veröffentlichung oder Aufführung sind die Rechteinhaber zu
kontaktieren. Weitere Hinweise stehen auf der Seite `/ueber/`.
