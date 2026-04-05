# Experiment 06b – Gamma brightening

## Ziel
Prüfen, ob eine leichte Aufhellung dunkler Bildbereiche die Gebäudesegmentierung verbessert.

## Ausgangsproblem
Schatten und dunkle Dachsegmente bleiben eine zentrale Fehlerquelle.

## Änderung gegenüber Exp04
- gleiche Chips wie Exp04
- gleiches Prompting wie Exp04
- zusätzlich Gamma-Aufhellung vor der Inferenz

## Hypothese
Die Aufhellung dunkler Bildbereiche reduziert den Einfluss von Schatten und verbessert dadurch die Objektkontur.

## Ergebnisse
Exp06b (Gamma-Aufhellung) führte im Vergleich zu Exp04 zu praktisch unveränderten Resultaten.

Vergleich Exp04 vs. Exp06b:
- Mean IoU:
  - Exp04: 0.7434
  - Exp06b: 0.7421
- Median IoU:
  - Exp04: 0.7727
  - Exp06b: 0.7681
- Mean SAM score:
  - Exp04: 0.9214
  - Exp06b: 0.9214

Decision counts:
- Exp04: keep=3, update=5
- Exp06b: keep=3, update=5

Die Unterschiede liegen im Bereich sehr kleiner Schwankungen. Eine belastbare Verbesserung gegenüber Exp04 konnte nicht festgestellt werden.

## Interpretation
Die Hypothese, dass eine leichte Gamma-Aufhellung dunkler Bildbereiche die Segmentierung verbessert, konnte im aktuellen Setup nicht bestätigt werden. Im Unterschied zu CLAHE verschlechtert Gamma die Resultate auch nicht deutlich, erzeugt jedoch ebenfalls keine relevante Verbesserung. Dies deutet darauf hin, dass Schatten und dunkle Innenbereiche nicht allein durch eine einfache globale Aufhellung gelöst werden können.

## Qualitative Beobachtung
Visuell wirken einzelne Konturen unter Gamma-Aufhellung teilweise etwas stabiler oder klarer. Dieser Eindruck schlägt sich jedoch nicht in einer relevanten quantitativen Verbesserung nieder. Der Effekt ist daher eher kosmetisch als methodisch wirksam.