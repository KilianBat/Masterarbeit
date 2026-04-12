# Rural Experiment 06 – New building prototype

## Ziel
Prüfen, ob neue Gebäude im ländlichen Szenario grundsätzlich mit SAM2 segmentierbar sind, auch wenn kein historisches OSM-Polygon als Prompt-Anker vorhanden ist.

## Ausgangsproblem
Für `new`-Gebäude existiert im historischen OSM-Bestand kein Ausgangsobjekt. Der bisherige objektzentrierte Workflow kann daher nicht direkt angewendet werden. Bevor ein vollständiger New-Building-Workflow entwickelt wird, soll zunächst in einem kontrollierten Prototyp getestet werden, ob neue Gebäude in einem kandidatengestützten Chip überhaupt zuverlässig segmentiert werden können.

## Setup
- Gebiet: Lübars
- Datengrundlage: `new_current_candidates.gpkg`
- Chips werden um aktuelle 2025-only-Gebäude erzeugt
- Prompting:
  - kein historisches Polygon
  - nur zentrierter Punkt
  - optional lockere zentrale Box
- Maskenauswahl:
  - building-like Re-Ranking
  - keine Nutzung der 2025-Geometrie zur Laufzeit

## Wichtige Einschränkung
Dieses Experiment ist kein vollständiger New-Building-Detector. Es testet nur, ob ein neues Gebäude segmentierbar ist, **wenn ein sinnvoller Kandidatenchip bereits vorliegt**.

## Hypothese
Freistehende neue Gebäude im ländlichen Szenario sind mit einem einfachen zentrierten Prompt und building-like Maskenauswahl grundsätzlich segmentierbar.

## Outputs
- `outputs/rural_exp06_new_centerprompt/new_predictions.gpkg`
- `outputs/rural_exp06_new_centerprompt/new_eval_report.csv`
- `outputs/rural_exp06_new_centerprompt/new_eval_layers.gpkg`

## Ergebnisse
Der Prototyp für neue Gebäude zeigte ein gemischtes Bild.

Auswertung:
- detected_good: 4
- detected_partial: 1
- missed: 7
- Mean IoU: 0.3335

Qualitativ zeigte sich, dass größere und freistehende neue Einfamilienhäuser häufig sinnvoll segmentiert werden konnten. Dagegen wurden kleine, teilweise verdeckte oder in Vegetation eingebettete neue Gebäude oft verfehlt oder deutlich zu groß segmentiert.

## Interpretation
Die Ergebnisse deuten darauf hin, dass neue Gebäude im ländlichen Szenario grundsätzlich segmentierbar sind, wenn sie im Orthophoto gut sichtbar und geometrisch relativ klar ausgeprägt sind. Der Prototyp ist jedoch deutlich weniger robust bei kleinen oder visuell schwer erkennbaren Neubauten. Das Problem liegt damit nicht nur in der Segmentierungslogik selbst, sondern stark in der Sichtbarkeit und Kandidatenqualität.

## Methodische Einordnung
Dieses Experiment stellt keinen vollständigen New-Building-Detector dar. Es testet lediglich, ob ein neues Gebäude segmentierbar ist, wenn bereits ein sinnvoller Kandidatenchip vorliegt. Die vorgelagerte Generierung solcher Kandidaten bleibt eine eigene offene Aufgabe.