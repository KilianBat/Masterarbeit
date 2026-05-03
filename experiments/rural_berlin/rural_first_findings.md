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

## Changed-only mit größerem Chip
Ein zusätzliches Changed-only-Experiment mit größerem Bildausschnitt zeigte, dass mehr Kontext die Qualität bei geänderten Gebäuden leicht verbessern kann. Der Effekt blieb jedoch klein und nicht stabil. Damit scheint der enge Chip zwar ein Teil des Problems zu sein, jedoch nicht die alleinige Ursache. Wahrscheinlich bleibt die Prompt-Strategie weiterhin zu stark auf das historische Gebäude ausgerichtet.

## Changed-only mit relaxed prompt
Ein zusätzliches Changed-only-Experiment mit größerem Chip und gelockerter Bounding Box zeigte visuell, dass das aktuelle Gebäude in mehreren Fällen besser gefunden wird. Gleichzeitig wurden die resultierenden Geometrien jedoch häufiger zu groß oder zu grob. Quantitativ ergab sich daher keine stabile Verbesserung gegenüber dem vorherigen Changed-only-Experiment. Dies spricht dafür, dass der nächste sinnvolle Schritt weniger in einer weiteren Prompt-Lockerung als vielmehr in einer verbesserten Maskenauswahl liegt.

## Changed-only mit Re-Ranking
Ein weiteres Changed-only-Experiment mit größerem Chip, gelockertem Prompt und geometriebasierter Maskenauswahl führte zur bisher klarsten Verbesserung im ländlichen Block. Im Unterschied zu den vorherigen Varianten wurden aktuelle Gebäudeformen häufiger korrekt erfasst, ohne gleichzeitig so stark zu groß zu werden. Dies deutet darauf hin, dass bei geänderten ländlichen Gebäuden die Maskenauswahl ein zentraler Erfolgsfaktor ist.

## Unchanged mit Keep-Bias
Ein konservativer, keep-orientierter Decision Layer verhinderte im ländlichen Unchanged-Subset unnötige Verschlechterungen. Dies zeigt, dass unveränderte Gebäude im finalen Workflow nicht primär durch bessere Segmentierung, sondern vor allem durch eine robuste Verifikationslogik stabil behandelt werden sollten.

## Neue Gebäude
Für neue Gebäude zeigte ein prototypischer kandidatenbasierter Ansatz, dass größere und gut sichtbare neue Häuser grundsätzlich segmentierbar sind. Kleine, verdeckte oder in Vegetation liegende Neubauten wurden dagegen häufig verfehlt. Damit hängt die Qualität bei `new` stark von der Sichtbarkeit des Gebäudes im Orthophoto ab.