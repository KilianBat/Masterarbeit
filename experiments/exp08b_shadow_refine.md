# Exp08b – Shadow-specific refinement

## Ziel
Ziel von Exp08b ist die Verbesserung schattenbeeinflusster urbaner Gebäude durch einen spezialisierten zweiten Durchgang, der nur für Fälle mit `shadow_refine` aktiviert wird.

## Ausgangspunkt
Der routing-basierte Urban-Workflow mit selektiver Akzeptanz zeigte, dass strukturkomplexe Fälle durch einen spezialisierten Topologie-Zweitlauf verbessert werden können. Gleichzeitig blieben Schattenfälle weiterhin ein zentraler Restfehler.

## Grundidee
Für schattenbeeinflusste Gebäude wird auf Basis des aktuellen besten Workflows ein zusätzlicher Shadow-Refinement-Pass durchgeführt:
- auf einem aufgehellten Bildchip
- mit priorgeführtem Prompt
- und mit selektiver Akzeptanz gegenüber dem bisherigen besten Ergebnis

## Erwartung
Der zweite Durchgang soll insbesondere untersegmentierte oder durch dunkle Dachhälften verkürzte Gebäudegeometrien verbessern, ohne gleichzeitig starke Übersegmentierung zu erzeugen.

## Output
- `outputs/urban_exp08b_shadow_refine/berlin_predictions.gpkg`
- `outputs/urban_exp08b_shadow_refine/berlin_update_proposals.gpkg`
- `outputs/urban_exp08b_shadow_refine/external_eval_osm2025.csv`

## Ergebnisse
*(nach dem Run eintragen)*

## Interpretation
*(nach dem Run eintragen)*