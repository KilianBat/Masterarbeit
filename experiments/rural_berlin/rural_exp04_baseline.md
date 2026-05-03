# Rural Experiment 01 – Baseline (Exp04 logic)

## Ziel
Prüfen, wie gut die robuste Baseline aus dem urbanen Berlin-Block in einem ländlichen bzw. dörflichen Szenario funktioniert.

## Setup
- Gebiet: Lübars
- historischer OSM-Bestand: 2018
- Orthophoto: 2025
- kontrolliertes Evaluationssubset aus changed, removed und unchanged cases
- Prompting: Bounding Box + ein positiver Innenpunkt
- Chip-Strategie: enger gebäudenaher Ausschnitt analog zu Exp04

## Motivation
Die urbane Evaluation hat gezeigt, dass Exp04 die stabilste allgemeine Strategie ist. Im ländlichen Block dient dieses Setup daher als Ausgangspunkt und Vergleichsbasis.

## Erwartung
Im dörflichen Szenario wird eine robustere Segmentierung erwartet, da Gebäude typischerweise freistehend und geometrisch einfacher sind und weniger unter Schatteninteraktionen, Innenhöfen und komplexen Blockstrukturen leiden.


## Erste qualitative Beobachtungen
Im ländlichen Lübars-Szenario zeigte sich, dass freistehende und geometrisch einfache Gebäude von SAM2 grundsätzlich besser segmentiert werden als viele der zuvor untersuchten urbanen Berliner Gebäude. Insbesondere bei unveränderten Häusern waren die resultierenden Gebäudekonturen häufig plausibel.

Gleichzeitig blieb ein zentrales Problem sichtbar: Wenn Dachflächen teilweise im Schatten lagen, wurde der verschattete Teil des Gebäudes oft unvollständig oder ungenau segmentiert. Schatten stellen damit auch im ländlichen Szenario eine relevante Fehlerquelle dar.

Bei `changed_candidate`-Fällen zeigte sich zudem, dass die aktuelle Pipeline häufig weiterhin stark an der historischen 2018-Geometrie orientiert bleibt. Dies ist plausibel, da Chip-Erzeugung und Prompting direkt aus dem historischen OSM-Objekt abgeleitet werden. Der Workflow eignet sich damit besser für Verifikation und moderate Anpassungen bestehender Objekte als für deutlich veränderte Gebäudeformen.

Für `removed_candidate`-Fälle ergab sich im Baseline-Run noch kein überzeugendes Verhalten. Dies deutet darauf hin, dass vollständig entfernte Gebäude mit dem aktuellen objektzentrierten Prompting-Ansatz nicht zuverlässig erfasst werden können und als eigener Spezialfall behandelt werden müssen.

## Externe Evaluation nach Status
Die statusweise externe Evaluation gegen den aktuellen OSM-Stand 2025 zeigte ein differenziertes Bild.

Für `unchanged_candidate`-Gebäude war der historische OSM-Stand 2018 im ausgewerteten Subset bereits praktisch identisch zum OSM-Stand 2025. Der durch SAM2 erzeugte Update-Workflow verschlechterte diese Fälle im Mittel deutlich. Dies zeigt, dass die aktuelle Pipeline für unveränderte Gebäude zu update-freudig ist und vorhandene korrekte Geometrien unnötig verändert.

Für `changed_candidate`-Gebäude ergab sich ein gemischtes Bild. Im Mittel verbesserte sich die IoU gegenüber dem OSM-Stand 2025 nur minimal. Von zehn Fällen wurden fünf verbessert und fünf verschlechtert. Dies deutet darauf hin, dass der Workflow bei geänderten Rural-Gebäuden grundsätzlich Potenzial besitzt, im aktuellen Setup jedoch nicht stabil genug ist.

Für `removed_candidate`-Gebäude ergab sich dagegen ein überraschend klares Resultat. Alle sechs ausgewerteten Fälle blieben auch nach der Modellinferenz geometrisch praktisch ohne relevante Überlappung mit aktuellen OSM-2025-Gebäuden. Der Workflow „springt“ in diesen Fällen also nicht fälschlich auf heutige Nachbargebäude. Dies ist ein starkes Indiz dafür, dass entfernte Gebäude mit dem aktuellen Ansatz zumindest als Spezialfall gut erkennbar bleiben.