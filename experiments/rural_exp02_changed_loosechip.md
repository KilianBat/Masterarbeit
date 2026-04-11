# Rural Experiment 02 – Changed-only with looser chips

## Ziel
Prüfen, ob geänderte Gebäude im ländlichen Szenario besser segmentiert werden, wenn der Bildausschnitt größer gewählt wird und dadurch mehr aktueller Kontext sichtbar ist.

## Ausgangsproblem
Die statusweise externe Evaluation des Rural-Baseline-Runs zeigte:
- `unchanged`-Gebäude werden häufig unnötig verschlechtert,
- `removed`-Gebäude bleiben überraschend gut als „removed-like“ erkennbar,
- `changed`-Gebäude bilden den eigentlichen offenen Problemfall.

Bei `changed`-Gebäuden scheint der aktuelle Workflow zu stark an der historischen 2018-Geometrie verankert zu sein. Der enge Chip und die aus dem historischen Objekt abgeleiteten Prompts fokussieren das Modell zu stark auf die alte Lage und Form.

## Änderung gegenüber Rural Baseline
- nur `changed_candidate`-Gebäude
- größerer / lockererer Chip
- Baseline-Prompting bleibt unverändert:
  - Bounding Box
  - ein positiver Innenpunkt

## Hypothese
Ein größerer Chip reduziert die historische Verankerung und erlaubt es SAM2, den aktuellen Gebäudekontext besser zu erfassen. Dadurch sollten geänderte Gebäude näher an den OSM-Stand 2025 heranrücken.

## Outputs
- `outputs/rural_exp02_changed_loosechip/berlin_predictions.gpkg`
- `outputs/rural_exp02_changed_loosechip/berlin_update_proposals.gpkg`
- `outputs/rural_exp02_changed_loosechip/berlin_update_report.csv`
- `outputs/rural_exp02_changed_loosechip/rural_external_eval_by_status.csv`

## Ergebnisse
Im Vergleich zum ersten Rural-Baseline-Run für gemischte Statusklassen zeigte der größere Chip bei `changed_candidate`-Gebäuden eine leichte Verbesserung.

Externe Evaluation gegen OSM 2025 für `changed_candidate`:
- Mean IoU historisches OSM 2018 vs. OSM 2025: 0.5893
- Mean IoU finales Ergebnis vs. OSM 2025: 0.5977

Von zehn ausgewerteten `changed`-Fällen wurden fünf verbessert und fünf verschlechtert.

## Interpretation
Der größere Chip verbessert `changed`-Fälle leicht, aber nicht stabil genug. Dies deutet darauf hin, dass der bisherige enge Chip tatsächlich zu einer zu starken Fokussierung auf das historische Objekt beiträgt. Gleichzeitig zeigt die nur geringe Verbesserung, dass zusätzlicher Kontext allein nicht ausreicht. Wahrscheinlich bleibt der Prompt weiterhin zu stark an der historischen OSM-Geometrie verankert.
