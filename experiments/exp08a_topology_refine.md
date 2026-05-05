# Exp08a – Routing-based topology refinement

## Ziel
Ziel von Exp08a ist die Verbesserung strukturkomplexer urbaner Gebäude durch einen zweiten, topologiebewussten Durchgang auf Basis der in Phase A abgeleiteten Routing-Tabelle.

## Ausgangspunkt
Die Urban-Taxonomie und die Uncertainty-Analyse zeigten, dass nicht alle problematischen Gebäude gleich behandelt werden sollten. Für Fälle mit Innenhof- oder Mehrteiligkeitsproblemen wurde ein `topology_refine`-Pfad abgeleitet.

## Routing
In Exp08a werden nur die Fälle mit `routing_decision = topology_refine` aktiv verfeinert. Alle übrigen Fälle übernehmen ihren besten bisherigen Pass-1-Stand.

## Verfeinerungslogik
Für die verfeinerten Fälle wird:
- der beste bisherige Pass-1-Output als geometrischer Prior verwendet
- daraus ein neuer Box-Prompt abgeleitet
- mehrere positive Punkte im priorbasierten Polygon gesetzt
- negative Punkte aus konkaven Bereichen bzw. aus der Differenz zwischen konvexer Hülle und Priorgeometrie abgeleitet
- die resultierenden SAM-Masken geometrisch plausibilitätsbasiert re-ranked

## Erwartung
Der zweite topologische Durchgang soll insbesondere:
- Innenhof- und Mehrteiligkeitsfehler reduzieren
- grobe Übersegmentierung verringern
- und die Geometrie strukturkomplexer Gebäude näher an die kartographische Zielgeometrie bringen

## Output
- `outputs/urban_exp08a_topology_refine/berlin_predictions.gpkg`
- `outputs/urban_exp08a_topology_refine/berlin_update_proposals.gpkg`
- `outputs/urban_exp08a_topology_refine/external_eval_osm2025.csv`

## Ergebnisse
*(nach dem Run eintragen)*

## Interpretation
*(nach dem Run eintragen)*