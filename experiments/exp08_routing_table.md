# Exp08 – Urban routing table

## Ziel
Ziel dieses Schritts ist die Ableitung einer konkreten Routing-Logik für urbane Gebäudefälle auf Basis von Fehlerklassifikation und Unsicherheitsanalyse.

## Ausgangspunkt
Die reine Unsicherheitsanalyse zeigte, dass instabile Fälle teilweise korrekt erkannt werden, systematische Fehler jedoch nicht immer als unsicher erscheinen. Insbesondere Schatten- und Strukturprobleme können auch dann konsistent auftreten, wenn die geometrische Variation zwischen bestehenden Experimenten gering bleibt.

## Schlussfolgerung
Ein uncertainty-only Routing ist daher nicht ausreichend. Stattdessen wird ein kombiniertes Routing verwendet, das:
- Unsicherheit als Instabilitätsindikator nutzt
- Fehlerklassen als inhaltlichen Prior berücksichtigt

## Routing-Kategorien
- `no_refine`
- `review_keep`
- `shadow_refine`
- `topology_refine`
- `context_refine`
- `geometry_refine`

## Ziel von Exp08
Die Routing-Tabelle dient als Grundlage für die ersten spezialisierten Urban-Refinement-Durchgänge.