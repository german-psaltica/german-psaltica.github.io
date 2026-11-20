# German Psaltica

Statische Hugo-Website für die Notenbibliothek German Psaltica: byzantinische Kirchenmusik in deutscher Sprache.

Die PDFs liegen im Submodul `notations/` und werden unverändert unter `/library/` ausgeliefert. `scripts/build_library.py` erzeugt daraus Katalog, Seiten und Vorschaubilder. Bereichstexte und Kacheln stehen in `categories.json`. Generierte Dateien (`content/library/`, `data/library.json`, `static/thumbs/`, `public/`) werden nicht versioniert.

## Voraussetzungen

Hugo Extended 0.169 oder neuer, Python 3.10 oder neuer, `poppler-utils`.

```sh
sudo apt install hugo poppler-utils python3
git submodule update --init
```

## Lokal

```sh
make serve     # http://127.0.0.1:1414/
make build     # Produktionsbuild nach public/
```

Neue oder geänderte PDFs unter `notations/` ablegen und `make build` erneut ausführen. Ordner namens `archiv`, `archive`, `alt`, `Vorübergehende Versionen` und Ordner mit Präfix `99_` gelten als Archiv und sind standardmäßig ausgeblendet.

## Veröffentlichen

Jeder Push auf `master` baut die Website und veröffentlicht sie unter [https://german-psaltica.github.io/website/](https://german-psaltica.github.io/website/).

Einmalig:

1. **Settings → Pages → Source: GitHub Actions.**
2. Für eine öffentliche Website das Repository `website` öffentlich machen, oder GitHub Pro, Team bzw. Enterprise nutzen.
3. Fine-grained PAT mit **Contents: Read** auf `german-psaltica/notations` und `german-psaltica/website` als Secret `NOTATIONS_READ_TOKEN` hinterlegen.

## Rechte

Die Rechte an den Noten liegen bei den jeweiligen Urheberinnen und Urhebern. Die Website stellt die PDFs zur Einsicht und zum Studium bereit. Weitere Hinweise stehen auf `/ueber/`.
