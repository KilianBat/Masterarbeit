# Experiment 03 – Multipoint + Negative Points

## Ziel
Prüfen, ob zusätzliche negative Außenpunkte helfen, angrenzende Dächer, Schattenflächen oder Innenhofstrukturen besser auszuschließen.

## Ausgangsproblem
In den bisherigen Experimenten zeigte SAM2 teils Übersegmentierungen über die Zielgeometrie hinaus.

## Änderung gegenüber Exp02
- Bounding Box aus OSM-Polygon
- mehrere positive Innenpunkte
- mehrere negative Punkte in einem Ring knapp außerhalb der Polygon-Bounding-Box

## Hypothese
Negative Punkte reduzieren Fehlsegmentierung in angrenzende Strukturen und verbessern die geometrische Abgrenzung.

## Relevante Dateien
- Config: `configs/exp03_multipoint_neg.json`
- Run-Script: `scripts/geo_run_sam2_experiment.py`
- Eval-Script: `scripts/geo_eval_update_experiment.py`
- Vergleich: `scripts/compare_experiments.py`

## Outputs
- `outputs/exp03_multipoint_neg/berlin_predictions.gpkg`
- `outputs/exp03_multipoint_neg/berlin_update_proposals.gpkg`
- `outputs/exp03_multipoint_neg/berlin_update_report.csv`

## Ergebnisse
*(nach dem Run ausfüllen)*

## Interpretation
*(nach dem Vergleich mit Exp02/Exp01 ausfüllen)*