# Exp08a – Selective acceptance of topology refinement

## Ziel
Ziel dieses Schritts ist es, den zweiten topologischen Durchgang nicht mehr automatisch zu übernehmen, sondern nur dann zu akzeptieren, wenn er gegenüber dem bisherigen Pass-1-Ergebnis intern plausibel bleibt.

## Ausgangsproblem
Das rohe Exp08a-Experiment zeigte, dass der topologische Zweitdurchgang einzelne komplexe Gebäude deutlich verbessern kann, andere Fälle jedoch verschlechtert. Besonders wichtig war die Beobachtung, dass der zweite Durchgang als Kandidatengenerator wertvoll ist, jedoch nicht automatisch das beste Endergebnis liefert.

## Grundidee
Für Fälle mit `topology_refine` werden Pass 1 und Pass 2 gegeneinander gestellt. Pass 2 wird nur übernommen, wenn:
- kein `flag_review` entsteht
- der SAM-Score ausreichend hoch bleibt
- die interne geometrische Abweichung gegenüber Pass 1 nicht zu stark anwächst
- die Flächenabweichung nicht deutlich schlechter wird

## Erwartung
Die selektive Akzeptanzlogik soll lokale Verbesserungen wie bei ID32 erhalten, während problematische Zweitdurchläufe wie bei ID21 oder ID27 automatisch verworfen werden.

## Output
- `outputs/urban_exp08a_selective_acceptance/berlin_predictions.gpkg`
- `outputs/urban_exp08a_selective_acceptance/berlin_update_proposals.gpkg`
- `outputs/urban_exp08a_selective_acceptance/external_eval_osm2025.csv`

## Ergebnisse
*(nach dem Run eintragen)*

## Interpretation
*(nach dem Run eintragen)*