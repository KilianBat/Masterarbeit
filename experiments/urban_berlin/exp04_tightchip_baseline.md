# Experiment 04 – Tighter chips with baseline prompting

## Ziel
Prüfen, ob ein engerer, gebäudenaher Bildausschnitt die Segmentierungsqualität verbessert.

## Ausgangsproblem
Die bisherigen Experimente zeigten wiederkehrende Probleme durch starke Schatten, dunkle Innenhöfe, komplexe Dachstrukturen und nahe Nachbargebäude. Eine mögliche Ursache ist, dass die bisherigen Chips zu viel störenden Kontext enthalten.

## Änderung gegenüber Exp01
- gleiche OSM-Objekte
- gleiches Modell
- gleiche Prompt-Logik wie in der Baseline
- aber engerer Chip um das jeweilige Gebäude

## Hypothese
Ein engerer Chip reduziert störenden Kontext und verbessert dadurch die Segmentierungsstabilität.

## Relevante Dateien
- Config: `configs/exp04_tightchip_baseline.json`
- Chip-Script: `scripts/geo_make_tightchips_experiment.py`
- Run-Script: `scripts/geo_run_sam2_experiment.py`
- Eval-Script: `scripts/geo_eval_update_experiment.py`
- Vergleich: `scripts/compare_experiments.py`

## Outputs
- `outputs/exp04_tightchip_baseline/berlin_predictions.gpkg`
- `outputs/exp04_tightchip_baseline/berlin_update_proposals.gpkg`
- `outputs/exp04_tightchip_baseline/berlin_update_report.csv`

## Ergebnisse
Exp04 führte im Vergleich zur Baseline zu einer leichten Verbesserung.

Vergleich Exp01 vs. Exp04:
- Mean IoU:
  - Exp01: 0.7229
  - Exp04: 0.7434
- Mean SAM score:
  - Exp01: 0.9019
  - Exp04: 0.9214
- Median IoU:
  - Exp01: 0.7644
  - Exp04: 0.7727
- Mean centroid shift:
  - Exp01: 1.94 m
  - Exp04: 1.33 m
- Min IoU:
  - Exp01: 0.2126
  - Exp04: 0.4167

Decision counts:
- Exp01: keep=3, update=4, flag_review=1
- Exp04: keep=3, update=5

Besonders auffällig ist die Reduktion extremer Fehlfälle. Der minimale IoU-Wert und die mittlere Schwerpunktverschiebung verbesserten sich deutlich.

## Interpretation
Die Hypothese von Exp04 wird teilweise bestätigt. Ein engerer Chip reduziert störenden Kontext wie Schatten, Straßenraum und benachbarte Gebäudestrukturen und führt dadurch zu etwas stabileren Vorhersagen. Der Effekt ist jedoch begrenzt: Die Verbesserung fällt insgesamt nur moderat aus, und die zentralen Fehlerbilder bleiben bestehen.

Insbesondere bei großen, komplexen und visuell zusammenhängenden Gebäudekomplexen scheint das Problem nicht primär die Chipgröße zu sein, sondern die Diskrepanz zwischen kartographisch getrennten OSM-Objekten und im Orthophoto visuell zusammenhängenden Dachstrukturen. Exp04 verbessert daher die Robustheit des Workflows, löst aber nicht das Grundproblem der Objektabgrenzung in komplexen urbanen Szenen.

## Qualitative Beobachtungen
Auch mit engeren Chips bleiben mehrere typische Fehlerquellen sichtbar:
- starke Schlagschatten
- dunkle Innenhöfe
- mehrteilige Dachstrukturen mit Aufbauten und Terrassen
- enge Nachbarschaft zu anderen Gebäuden
- kartographische OSM-Teilobjekte innerhalb visuell zusammenhängender Dachkomplexe

Die Ergebnisse deuten darauf hin, dass engeres Cropping vor allem extremen Störkontext reduziert, aber die semantische Trennung einzelner Teilgebäude innerhalb komplexer Strukturen nicht zuverlässig löst.