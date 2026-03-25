# Experiment 02 – Multipoint Prompting

## Ziel
Prüfen, ob mehrere positive Innenpunkte die Gebäudesegmentierung gegenüber der Baseline stabilisieren.

## Ausgangsproblem
In der Baseline zeigten sich geometrische Abweichungen zwischen OSM und SAM2, insbesondere bei komplexen Dachformen, Schatten, dunklen Innenhöfen und dichten Blockstrukturen.

## Änderung gegenüber Exp01
- weiterhin Bounding Box aus OSM-Polygon
- statt nur eines positiven Innenpunkts werden mehrere positive Innenpunkte innerhalb des OSM-Polygons erzeugt
- keine negativen Punkte

## Hypothese
Mehrere positive Punkte fokussieren SAM2 stärker auf das Zielgebäude und reduzieren Fehlsegmentierungen in benachbarte Dach- oder Schattenbereiche.

## Relevante Dateien
- Config: `configs/exp02_multipoint.json`
- Run-Script: `scripts/geo_run_sam2_experiment.py`
- Eval-Script: `scripts/geo_eval_update_experiment.py`
- Vergleich: `scripts/compare_experiments.py`

## Outputs
- `outputs/exp02_multipoint/berlin_predictions.gpkg`
- `outputs/exp02_multipoint/berlin_update_proposals.gpkg`
- `outputs/exp02_multipoint/berlin_update_report.csv`

## Ergebnisse
Verglichen mit der Baseline ergab sich keine Verbesserung.

- Mean IoU:
  - Exp01 Baseline: 0.7229
  - Exp02 Multipoint: 0.7223
- Mean SAM score:
  - Exp01 Baseline: 0.9019
  - Exp02 Multipoint: 0.8750

Decision counts:
- Exp01: keep=3, update=4, flag_review=1
- Exp02: keep=2, update=5, flag_review=1

Die mittlere IoU blieb praktisch unverändert, während der mittlere SAM-Score sank. Außerdem wurde mindestens ein zuvor stabiler Fall (ID 12) von `keep` zu `update` verschlechtert.

## Interpretation
Die Hypothese, dass mehrere positive Innenpunkte die Segmentierung stabilisieren, konnte nicht bestätigt werden. Eine plausible Erklärung ist, dass bei komplexen Gebäuden mehrere positive Punkte auch visuell problematische Bereiche wie dunkle Innenhöfe, Dachaufbauten oder schattige Teilflächen verstärken. Dadurch erhält SAM2 nicht zwingend ein klareres, sondern teils ein uneindeutigeres Signal. In diesem Setup erwies sich Multipoint-Prompting daher nicht als Verbesserung gegenüber der Baseline.