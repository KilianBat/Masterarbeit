# Experiment 07 – Topology-aware prompting

## Ziel
Prüfen, ob eine topologiebewusste Prompt-Platzierung auf Basis der OSM-Geometrie die Segmentierung komplexer Gebäude verbessert.

## Ausgangsproblem
Die bisherigen Experimente zeigten, dass die zentralen Fehlerquellen nicht nur im allgemeinen Kontext liegen, sondern vor allem bei:
- Innenhöfen
- komplexen und konkaven Gebäudeformen
- mehreren Dachniveaus
- visuell heterogenen Dachsegmenten

## Änderung gegenüber Exp04
- gleicher enger Chip wie in Exp04
- Bounding Box weiterhin aktiv
- statt einer rein generischen Promptstrategie wird die OSM-Topologie verwendet:
  - 1 stabiler Innenpunkt immer
  - zusätzliche positive Punkte nur bei komplexeren Formen
  - negative Punkte in Innenhöfen / Polygonlöchern

## Hypothese
Wenn die Prompt-Platzierung stärker an der tatsächlichen Objektstruktur orientiert wird, kann SAM2 komplexe Gebäudegeometrien besser erfassen als mit rein generischen Punktstrategien.

## Relevante Dateien
- Config: `configs/exp07_topology_aware.json`
- Run-Script: `scripts/geo_run_sam2_topology_aware.py`
- Eval-Script: `scripts/geo_eval_update_experiment.py`
- Vergleich: `scripts/compare_experiments.py`

## Outputs
- `outputs/exp07_topology_aware/berlin_predictions.gpkg`
- `outputs/exp07_topology_aware/berlin_update_proposals.gpkg`
- `outputs/exp07_topology_aware/berlin_update_report.csv`

## Ergebnisse
Exp07 zeigte gegenüber Exp04 keine generelle quantitative Verbesserung, aber klare qualitative Vorteile bei komplexeren Gebäudeformen.

Vergleich Exp04 vs. Exp07:
- Mean IoU:
  - Exp04: 0.7434
  - Exp07: 0.7392
- Median IoU:
  - Exp04: 0.7727
  - Exp07: 0.7658
- Mean SAM score:
  - Exp04: 0.9214
  - Exp07: 0.8525

Decision counts:
- Exp04: keep=3, update=5
- Exp07: keep=3, update=5

Die globalen Kennzahlen blieben damit sehr ähnlich bzw. leicht schwächer als in Exp04. Gleichzeitig zeigten qualitative Vergleiche, dass Exp07 Innenhof- und Strukturmerkmale komplexer Gebäude besser erfasste. Besonders relevant war, dass Innenhofstrukturen erstmals teilweise auf beiden Höfen sichtbar wurden und einzelne komplexe Gebäude differenzierter segmentiert wurden.

## Interpretation
Die Hypothese von Exp07 wird nur teilweise bestätigt. Topologiebewusstes Prompting verbessert die Segmentierung komplexer Gebäudeformen sichtbar, insbesondere bei Innenhöfen und heterogenen Dachstrukturen. Eine generelle Verbesserung über alle Objekte hinweg konnte jedoch nicht beobachtet werden.

Dies deutet darauf hin, dass die zusätzliche Strukturinformation aus dem OSM-Polygon tatsächlich hilfreich sein kann, jedoch vor allem für spezielle schwierige Fälle. Als allgemeines Standardverfahren bleibt Exp04 insgesamt robuster. Exp07 eignet sich daher eher als spezialisierte Strategie für topologisch komplexe Gebäude als als global beste Einstellung.

## Qualitative Beobachtungen
Visuell zeigte Exp07 erstmals eine teilweise Erkennung beider Innenhöfe eines komplexen Gebäudes. Auch bei Gebäuden mit mehreren Dachniveaus und heterogenen Dachsegmenten wirkte die Segmentierung plausibler als in den vorherigen Experimenten. Gleichzeitig blieben jedoch Probleme bei klaren Dachkanten, Schattenbereichen und der exakten Innenhofabgrenzung bestehen. Exp07 verbessert daher die strukturelle Plausibilität, ohne die geometrische Präzision insgesamt ausreichend zu stabilisieren.

## Externe Bewertung gegen OSM 2025
Exp07 war das beste der getesteten Experimente in der externen Evaluation gegen OSM 2025.

- Mean IoU orig2018 vs OSM2025: 0.7047
- Mean IoU Exp07 final vs OSM2025: 0.6630
- Mean delta IoU: -0.0416
- Verbesserte Objekte gegenüber OSM 2018: 1 / 8

Obwohl Exp07 die globale Ausgangsqualität des 2018er OSM nicht übertrifft, war es das einzige Experiment, das in der externen Bewertung überhaupt ein Objekt tatsächlich verbesserte. Dies stützt die Annahme, dass topologiebewusstes Prompting vor allem für schwierigere Gebäudeformen hilfreich sein kann, ohne jedoch bereits als allgemeine Lösung zu funktionieren.