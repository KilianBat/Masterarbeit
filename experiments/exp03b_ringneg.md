# Experiment 03b – Stable interior points + ring negatives

## Ziel
Prüfen, ob eine gezieltere Prompt-Strategie mit wenigen stabilen Innenpunkten und systematisch verteilten negativen Außenpunkten die Gebäudesegmentierung verbessert.

## Ausgangsproblem
Exp02 zeigte keine Verbesserung durch mehrere positive Innenpunkte. Eine mögliche Ursache ist, dass zusätzliche positive Punkte auch visuell problematische Bereiche wie Schatten, Innenhöfe oder komplexe Dachstrukturen verstärken.

## Änderung gegenüber Exp02
- Bounding Box weiterhin aktiv
- Bounding Box leicht erweitert
- nur wenige positive Punkte
- positive Punkte werden gezielt tief im Gebäude gewählt
- negative Punkte werden ringförmig und gleichmäßig außerhalb des Polygons gesetzt

## Hypothese
Eine kleinere Zahl stabiler Innenpunkte vermeidet mehrdeutige positive Signale. Ringförmig verteilte negative Punkte helfen zusätzlich, angrenzende Dächer, Höfe und Schattenbereiche besser auszuschließen.

## Relevante Dateien
- Config: `configs/exp03b_ringneg.json`
- Run-Script: `scripts/geo_run_sam2_experiment.py`
- Eval-Script: `scripts/geo_eval_update_experiment.py`
- Vergleich: `scripts/compare_experiments.py`

## Outputs
- `outputs/exp03b_ringneg/berlin_predictions.gpkg`
- `outputs/exp03b_ringneg/berlin_update_proposals.gpkg`
- `outputs/exp03b_ringneg/berlin_update_report.csv`

## Ergebnisse
Im Vergleich zu Exp02 und auch zur Baseline zeigte Exp03b keine generelle Verbesserung.

Vergleich Exp02 vs. Exp03b:
- Mean IoU:
  - Exp02: 0.7223
  - Exp03b: 0.6499
- Mean SAM score:
  - Exp02: 0.8750
  - Exp03b: 0.8281

Decision counts:
- Exp02: keep=2, update=5, flag_review=1
- Exp03b: keep=2, update=6

Vergleich Exp01 vs. Exp03b:
- Mean IoU:
  - Exp01: 0.7229
  - Exp03b: 0.6499
- Mean SAM score:
  - Exp01: 0.9019
  - Exp03b: 0.8281

Die mittlere IoU und der mittlere Modellscore sanken gegenüber beiden Vergleichsexperimenten. Gleichzeitig verschlechterten sich mehrere Einzelobjekte deutlich, insbesondere Objekt 27 und Objekt 2.

## Interpretation
Die Hypothese, dass wenige stabile Innenpunkte in Kombination mit ringförmig verteilten negativen Außenpunkten die Segmentierung verbessern, konnte insgesamt nicht bestätigt werden. Zwar zeigten einzelne Objekte leichte Verbesserungen, der Gesamteffekt war jedoch negativ.

Eine plausible Erklärung ist, dass die negativen Punkte in komplexen urbanen Szenen zu nahe an visuell relevanten Dachrändern, Schattenkanten oder angrenzenden Gebäudestrukturen liegen und dadurch die Vorhersage zu stark einschränken. Gleichzeitig bleiben zentrale Problemquellen wie Schlagschatten, dunkle Innenhöfe und komplexe Dachaufbauten weiterhin bestehen. Das Experiment deutet daher darauf hin, dass die aktuelle Schwäche weniger in der bloßen Anzahl der Punkte liegt, sondern stärker in der Bildcharakteristik und in der Art der Promptplatzierung relativ zu schwierigen Strukturen.

## Qualitative Beobachtungen
Die Analyse der Berliner Chips und des Orthophotos zeigt mehrere wiederkehrende Fehlerquellen:
- starke Schlagschatten
- dunkle Innenhöfe in größeren Gebäudekomplexen
- komplexe Dachstrukturen mit Terrassen und Aufbauten
- enge Nachbarschaft zu anderen Gebäuden und Straßenräumen
- Unterschiede zwischen sichtbarer Dachkontur und kartographischem OSM-Polygon

Diese Faktoren erschweren eine stabile Segmentierung durch SAM2 und erklären plausibel, warum weder zusätzliche positive Punkte noch ringförmige negative Punkte zu einer generellen Verbesserung führten.