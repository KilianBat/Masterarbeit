# Rural First Findings – Lübars

## Gebietseindruck
Das Gebiet Lübars eignet sich gut als ländlicher Kontrast zum urbanen Berliner Block. Das Orthophoto zeigt vorwiegend freistehende Häuser, einfachere Dachformen und deutlich weniger komplexe Blockstrukturen.

## Erste OSM-Differenzanalyse
Der Vergleich von OSM 2018 und OSM 2025 ergab:
- 378 unchanged candidates
- 10 changed candidates
- 6 removed candidates
- 19 new candidates

Damit bestätigt sich die Erwartung, dass in ländlicheren Gebieten Änderungen häufig in Form neuer oder verschwundener Gebäude auftreten und nicht primär als komplexe Umbauten dichter Gebäudeblöcke.

## Erste Beobachtungen aus dem Baseline-Run
- Unveränderte Häuser werden grundsätzlich besser erkannt als im urbanen Berlin-Szenario.
- Schatten auf Dächern bleiben eine zentrale Fehlerquelle.
- Bei changed-Fällen bleibt die Vorhersage häufig zu stark an der historischen 2018-Geometrie orientiert.
- Removed-Fälle werden mit dem aktuellen Workflow noch nicht überzeugend modelliert.

## Erste Schlussfolgerung
Der ländliche Block zeigt, dass der Workflow bei einfacheren Gebäudetypen grundsätzlich robuster wirkt als im urbanen Szenario. Gleichzeitig werden die Grenzen des objektzentrierten Ansatzes bei stark veränderten oder nicht mehr vorhandenen Gebäuden besonders deutlich.

## Externe Statusbewertung
Die externe Evaluation nach Status zeigte:

- `unchanged`: historischer OSM-Stand bereits sehr gut, Update-Workflow verschlechtert diese Fälle deutlich
- `changed`: gemischtes Bild mit ungefähr hälftigen Verbesserungen und Verschlechterungen
- `removed`: alle ausgewerteten Fälle blieben auch nach der Inferenz klar „removed-like“

Damit zeigt der ländliche Block, dass der Workflow nicht pauschal bewertet werden darf. Je nach Änderungstyp ergeben sich sehr unterschiedliche Stärken und Schwächen.