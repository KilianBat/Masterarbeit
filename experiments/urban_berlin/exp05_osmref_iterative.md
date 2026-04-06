# Experiment 05 – OSM-reference-guided iterative prompting

## Ziel
Prüfen, ob eine PerSAM-artige Referenzstrategie mit OSM als objektspezifischer Prior die Segmentierung komplexer Gebäude verbessert.

## Ausgangsproblem
Die bisherigen Experimente zeigten, dass reine Prompt-Variationen nur begrenzt helfen. Hauptprobleme bleiben Schlagschatten, dunkle Innenhöfe, komplexe Dachsegmente und Unterschiede zwischen OSM-Geometrie und visuell sichtbarer Dachstruktur.

## Änderung gegenüber Exp04
- gleicher enger Chip wie in Exp04
- erster Inferenzschritt mit Baseline-Prompt (Box + 1 positiver Punkt)
- OSM-Polygon wird als Referenzmaske im Chip genutzt
- aus dem Vergleich zwischen Vorhersage und OSM-Prior werden Korrekturpunkte erzeugt:
  - positive Punkte in fehlenden OSM-Bereichen
  - negative Punkte in übersegmentierten Bereichen
- zweiter Inferenzschritt mit den Korrekturpunkten

## Hypothese
Die objektspezifische Referenzinformation aus dem OSM-Polygon hilft SAM2, visuell schwierige Dachbereiche gezielter zu interpretieren und die Segmentierung am bekannten Objekt auszurichten.

## Relevante Dateien
- Config: `configs/exp05_osmref_iterative.json`
- Run-Script: `scripts/geo_run_sam2_osmref_iterative.py`
- Eval-Script: `scripts/geo_eval_update_experiment.py`
- Vergleich: `scripts/compare_experiments.py`

## Outputs
- `outputs/exp05_osmref_iterative/berlin_predictions.gpkg`
- `outputs/exp05_osmref_iterative/berlin_update_proposals.gpkg`
- `outputs/exp05_osmref_iterative/berlin_update_report.csv`

## Ergebnisse
Exp05 zeigte im Vergleich zu Exp04 keine generelle Verbesserung, aber qualitative Vorteile bei einzelnen schwierigen Gebäudetypen.

Vergleich Exp04 vs. Exp05:
- Mean IoU:
  - Exp04: 0.7434
  - Exp05: 0.7404
- Mean SAM score:
  - Exp04: 0.9214
  - Exp05: 0.7949
- Mean centroid shift:
  - Exp04: 1.33 m
  - Exp05: 1.90 m

Decision counts:
- Exp04: keep=3, update=5
- Exp05: keep=2, update=6

Die globalen Durchschnittswerte blieben ähnlich, verschlechterten sich jedoch leicht. Gleichzeitig zeigten einzelne Objekte deutliche Verbesserungen, insbesondere Objekt 21 sowie in geringerem Maß die Objekte 32, 4 und 16. Dagegen verschlechterten sich einzelne zuvor stabile Fälle, insbesondere Objekt 12.

## Interpretation
Die Hypothese von Exp05 wird nur teilweise bestätigt. Die OSM-referenzgeführte iterative Promptstrategie führt nicht zu einer generellen Verbesserung über alle Testobjekte hinweg. Die globalen Kennzahlen bleiben ähnlich oder verschlechtern sich leicht. Gleichzeitig zeigen qualitative Vergleiche, dass die Methode bei bestimmten schwierigeren Gebäudetypen hilfreich sein kann, insbesondere bei komplexen Dachstrukturen und Innenhofsituationen.

Dies deutet darauf hin, dass die objektspezifische Referenzinformation prinzipiell wertvoll ist, jedoch nicht für alle Fälle gleichermaßen geeignet ist. Exp05 scheint deshalb eher als spezialisierte Strategie für komplexe Objektformen geeignet zu sein als als neuer globaler Standardansatz.

## Qualitative Beobachtungen
Visuell zeigte Exp05 Vorteile bei Gebäuden mit:
- mehreren Dachniveaus
- heterogenen Dachsegmenten
- Innenhofstrukturen

In solchen Fällen konnte die OSM-Referenz das Modell offenbar stärker auf die gewünschte Objektstruktur fokussieren. Bei einfacheren oder bereits gut segmentierten Gebäuden brachte die Methode dagegen oft keinen Vorteil und verschlechterte einzelne Fälle sogar.