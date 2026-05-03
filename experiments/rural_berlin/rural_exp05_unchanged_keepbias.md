# Rural Experiment 05 – Unchanged-only with conservative keep-bias

## Ziel
Prüfen, ob unveränderte Gebäude im ländlichen Szenario stabiler behandelt werden, wenn eine konservative Entscheidungslogik eingesetzt wird, die bestehende OSM-Geometrien standardmäßig bevorzugt.

## Ausgangsproblem
Die statusweise externe Evaluation des Rural-Baseline-Runs zeigte, dass `unchanged_candidate`-Gebäude trotz bereits korrekter historischer Geometrie häufig verschlechtert werden. Das deutet darauf hin, dass das Hauptproblem bei unveränderten Gebäuden weniger in der reinen Segmentierung als in einer zu aggressiven Update-Entscheidung liegt.

## Änderung gegenüber Rural Baseline
- nur `unchanged_candidate`-Gebäude
- gleicher enger Chip wie in der Rural-Baseline
- gleiches Baseline-Prompting:
  - Bounding Box
  - ein positiver Innenpunkt
- neue konservative Entscheidungslogik:
  - `keep` als Default
  - `update` nur bei starker Evidenz
  - `flag_review` für Grenzfälle

## Hypothese
Eine konservative, keep-orientierte Entscheidungslogik verhindert unnötige Verschlechterungen bereits korrekter Gebäude und verbessert dadurch die Übereinstimmung mit dem OSM-Stand 2025.

## Outputs
- `outputs/rural_exp05_unchanged_keepbias/berlin_predictions.gpkg`
- `outputs/rural_exp05_unchanged_keepbias/berlin_update_proposals.gpkg`
- `outputs/rural_exp05_unchanged_keepbias/berlin_update_report.csv`
- `outputs/rural_exp05_unchanged_keepbias/rural_external_eval_by_status.csv`

## Ergebnisse
Das Keep-Bias-Experiment stabilisierte den Umgang mit unveränderten Gebäuden deutlich. Im ausgewerteten Unchanged-Subset wurde die historische OSM-Geometrie in allen Fällen beibehalten oder zur manuellen Prüfung markiert. Dadurch blieb die externe Übereinstimmung mit dem OSM-Stand 2025 vollständig erhalten.

Externe Evaluation gegen OSM 2025:
- Mean IoU historisches OSM 2018 vs. OSM 2025: 1.000
- Mean IoU finales Ergebnis vs. OSM 2025: 1.000

## Interpretation
Das Ergebnis zeigt, dass bei unveränderten ländlichen Gebäuden nicht primär eine immer genauere Neu-Segmentierung erforderlich ist, sondern vor allem eine konservative Entscheidungslogik, die bereits korrekte Geometrien nicht unnötig ersetzt. Damit bestätigt sich, dass `unchanged` im finalen Workflow primär als Verifikations- und nicht als Update-Fall behandelt werden sollte.