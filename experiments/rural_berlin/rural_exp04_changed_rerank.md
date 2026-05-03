# Rural Experiment 04 – Changed-only with re-ranking

## Ziel
Prüfen, ob geänderte Gebäude im ländlichen Szenario besser segmentiert werden, wenn bei gleichem größeren Chip und gelockertem Prompt nicht einfach die SAM-Maske mit dem höchsten Score gewählt wird, sondern eine geometrisch plausiblere Maske bevorzugt wird.

## Ausgangsproblem
Das vorherige Changed-only-Experiment mit größerem Chip und gelockerter Bounding Box zeigte, dass das aktuelle Gebäude visuell häufiger korrekt gefunden wird, die resultierenden Segmentierungen jedoch teils zu groß oder zu grob ausfallen.

## Änderung gegenüber Rural Exp03
- gleicher changed-only Subset
- gleicher größerer Chip
- gleicher gelockerter Prompt
- neue Maskenauswahl:
  - nicht nur nach SAM score
  - zusätzlich nach geometrischer Plausibilität relativ zum historischen Objekt

## Hypothese
Eine maskenbasierte Re-Ranking-Strategie reduziert Übersegmentierung und verbessert dadurch die Annäherung an den OSM-Stand 2025 bei geänderten Gebäuden.

## Outputs
- `outputs/rural_exp04_changed_rerank/berlin_predictions.gpkg`
- `outputs/rural_exp04_changed_rerank/berlin_update_proposals.gpkg`
- `outputs/rural_exp04_changed_rerank/berlin_update_report.csv`
- `outputs/rural_exp04_changed_rerank/rural_external_eval_by_status.csv`

## Ergebnisse
Das Re-Ranking-Experiment führte im Rural-Changed-Block zur bisher deutlichsten Verbesserung.

Externe Evaluation gegen OSM 2025 für `changed_candidate`:
- Mean IoU historisches OSM 2018 vs. OSM 2025: 0.5893
- Mean IoU finales Ergebnis vs. OSM 2025: 0.6453

Damit übertrifft Exp04 alle vorherigen Rural-Changed-Experimente deutlich. Visuell zeigte sich zudem, dass das aktuelle Gebäude häufiger korrekt lokalisiert wird und die resultierenden Gebäudeumrisse seltener stark übersegmentiert sind.

## Interpretation
Die Ergebnisse deuten darauf hin, dass das Hauptproblem bei geänderten ländlichen Gebäuden zuletzt weniger in der reinen Objektfindung als in der Auswahl der finalen Maske lag. Größerer Chip und gelockerter Prompt verbesserten die Erfassung des aktuellen Gebäudes bereits, führten jedoch teils zu zu großen Segmentierungen. Erst durch eine geometrisch plausibilitätsbasierte Maskenauswahl konnte diese Tendenz spürbar reduziert werden. Damit stellt Exp04 den bisherigen Beststand für `changed_candidate`-Gebäude im Rural-Szenario dar.