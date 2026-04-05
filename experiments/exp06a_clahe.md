# Experiment 06a – CLAHE preprocessing

## Ziel
Prüfen, ob lokale Kontrastnormalisierung (CLAHE) die Segmentierung in Schatten- und Innenhofsituationen verbessert.

## Ausgangsproblem
Die bisherigen Experimente zeigen weiterhin Schwierigkeiten bei starken Schlagschatten, dunklen Innenhöfen und starken Helligkeitsunterschieden innerhalb desselben Gebäudes.

## Änderung gegenüber Exp04
- gleiche Chips wie Exp04
- gleiches Prompting wie Exp04
- zusätzlich CLAHE auf dem L-Kanal im LAB-Farbraum

## Hypothese
Eine lokale Kontrastnormalisierung macht dunkle Dach- und Schattenbereiche für SAM2 besser interpretierbar und verbessert dadurch die Segmentierung.

## Outputs
- `outputs/exp06a_clahe/berlin_predictions.gpkg`
- `outputs/exp06a_clahe/berlin_update_proposals.gpkg`
- `outputs/exp06a_clahe/berlin_update_report.csv`

## Ergebnisse
Exp06a (CLAHE) führte im Vergleich zu Exp04 nicht zu einer Verbesserung.

Vergleich Exp04 vs. Exp06a:
- Mean IoU:
  - Exp04: 0.7434
  - Exp06a: 0.7343
- Median IoU:
  - Exp04: 0.7727
  - Exp06a: 0.7586
- Mean SAM score:
  - Exp04: 0.9214
  - Exp06a: 0.9258

Decision counts:
- Exp04: keep=3, update=5
- Exp06a: keep=3, update=5

Alle acht Testobjekte zeigten eine leicht negative IoU-Veränderung gegenüber Exp04. Eine generelle Verbesserung konnte daher nicht beobachtet werden.

## Interpretation
Die Hypothese, dass lokale Kontrastnormalisierung durch CLAHE die Segmentierung in Schatten- und Innenhofsituationen verbessert, konnte nicht bestätigt werden. Eine plausible Erklärung ist, dass CLAHE nicht nur dunkle Dachbereiche besser sichtbar macht, sondern gleichzeitig auch Schattenkanten, Dachtexturen und lokale Kontrastunterschiede verstärkt. Dadurch wird das Bild für SAM2 nicht einfacher, sondern visuell komplexer. In diesem Setup erwies sich CLAHE daher nicht als geeignete Vorverarbeitungsstrategie.