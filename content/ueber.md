---
title: "Über die Bibliothek"
description: "Hintergrund, Nutzung und Rechtehinweise zur German-Psaltica-Notenbibliothek."
eyebrow: "German Psaltica"
---

## Was ist German Psaltica?

German Psaltica ist eine Notenbibliothek für byzantinische Kirchenmusik in deutscher Sprache. Die hier veröffentlichten PDFs sind nach Gottesdiensten, Gattungen und Modi geordnet und lassen sich nach Titel, Fest, Komponist oder Modus durchsuchen.

Die Sammlung wächst aus der praktischen Arbeit eines Chores. Sie enthält vollständige Liturgien, einzelne Gesänge, Sammlungen, Übertragungen, Entwürfe und ältere Fassungen.

## Die Bibliothek benutzen

- **Bereiche:** Die Startseite führt zu Liturgie, Troparien, Kondakien, Morgenlob, Vesper, Psalmen, weiteren Gottesdiensten und Pas'cha.
- **Suche und Filter:** In der [Notenbibliothek]({{< relref "/library" >}}) können alle 440 PDFs nach Titel, Fest, Komponist und Modus durchsucht werden. Das Archiv ist standardmäßig ausgeblendet.
- **PDF-Vorschau:** Jede Notenseite enthält eine Vorschau im Browser sowie Schaltflächen zum Öffnen und Herunterladen.
- **Direkte Links:** Jede Notenseite und jede gefilterte Ansicht kann direkt geteilt werden.

## Aufbau

Die Website wird direkt aus dem Ordner `notations` erzeugt. Die Ordnerstruktur der Sammlung bildet die Kategorien und Bereiche der Website ab. Wird eine PDF hinzugefügt, verschoben oder umbenannt, kann die Bibliothek mit einem Befehl neu aufgebaut werden:

```bash
python3 scripts/build_library.py
```

## Rechte und Nutzung

Die Rechte an den Kompositionen, Übertragungen, Sätzen und Notensätzen liegen bei den jeweiligen Urheberinnen und Urhebern. Die Veröffentlichung auf dieser Website ersetzt keine Nutzungs- oder Aufführungsgenehmigung.

Viele Noten enthalten eigene Copyright- und Herkunftsangaben. Diese Angaben sind maßgeblich. Bei Fragen zur Verwendung einer konkreten Note wende dich bitte an die genannten Rechteinhaber.

## Hinweise zur Sammlung

Einzelne Bereiche enthalten ausdrücklich Entwürfe, vorläufige Fassungen oder Projekte, die nicht dem offiziellen Text entsprechen. Solche Hinweise werden auf den jeweiligen Bereichsseiten angezeigt. Für den gottesdienstlichen Gebrauch sollten die freigegebenen Fassungen verwendet werden.
