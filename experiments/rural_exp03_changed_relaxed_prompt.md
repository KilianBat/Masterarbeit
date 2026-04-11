# Rural Experiment 03 – Changed-only with looser chips and relaxed prompt

## Ziel
Prüfen, ob geänderte Gebäude im ländlichen Szenario besser segmentiert werden, wenn nicht nur der Bildausschnitt größer ist, sondern auch die Bounding Box des historischen Objekts bewusst erweitert wird.

## Ausgangsproblem
Das vorherige Changed-only-Experiment mit größerem Chip zeigte nur eine geringe Verbesserung. Dies deutet darauf hin, dass der enge historische Prompt weiterhin eine starke Verankerung am alten Gebäude erzeugt.

## Änderung gegenüber Rural Exp02
- gleicher changed-only Subset
- gleicher größerer Chip
- gleicher positiver Innenpunkt
- Bounding Box wird zusätzlich erweitert

## Hypothese
Eine erweiterte Bounding Box reduziert die historische Verankerung des Prompts und erlaubt es SAM2, aktuelle Gebäudeerweiterungen, Verschiebungen oder geänderte Umrisse besser zu erfassen.

## Outputs
- `outputs/rural_exp03_changed_relaxed_prompt/berlin_predictions.gpkg`
- `outputs/rural_exp03_changed_relaxed_prompt/berlin_update_proposals.gpkg`
- `outputs/rural_exp03_changed_relaxed_prompt/berlin_update_report.csv`
- `outputs/rural_exp03_changed_relaxed_prompt/rural_external_eval_by_status.csv`

## Ergebnisse
Im Vergleich zum Changed-only-Experiment mit größerem Chip, aber ohne zusätzliche Prompt-Lockerung, ergab sich keine stabile Verbesserung.

Externe Evaluation gegen OSM 2025 für `changed_candidate`:
- Mean IoU historisches OSM 2018 vs. OSM 2025: 0.5893
- Mean IoU finales Ergebnis vs. OSM 2025: 0.5966

Damit liegt Exp03 praktisch auf dem Niveau von Exp02 mit größerem Chip. Von zehn ausgewerteten `changed`-Fällen wurden erneut fünf verbessert und fünf verschlechtert.

## Interpretation
Die gelockerte Bounding Box verbessert in einzelnen Fällen offenbar die Erfassung des aktuellen Gebäudes, führt jedoch gleichzeitig häufiger zu zu großen oder zu groben Segmentierungen. Dies deutet darauf hin, dass das Hauptproblem bei geänderten Rural-Gebäuden nicht mehr allein in einer zu starken historischen Verankerung des Prompts liegt, sondern zunehmend in der Auswahl und Begrenzung der finalen Maske.