# Rural Subset Selection – Lübars

## Ziel
Ziel dieses Schritts ist die Erzeugung eines kontrollierten Evaluations-Subsets für den ländlichen Experimentblock. Das Subset soll nicht zufällig aus allen historischen Gebäuden gezogen werden, sondern gezielt relevante Änderungstypen enthalten.

## Motivation
Die OSM-Vergleichsanalyse für Lübars zeigte eine starke Dominanz unveränderter Gebäude. Ein rein zufälliger Rural-Run würde daher überwiegend `unchanged`-Fälle enthalten und nur begrenzt Erkenntnisse über tatsächlich relevante Änderungsfälle liefern.

## Vorgehen
Aus dem historischen OSM-Bestand 2018 und dem aktuellen OSM-Bestand 2025 werden drei Gruppen abgeleitet:
- `unchanged_candidate`
- `changed_candidate`
- `removed_candidate`

Für das Evaluationssubset werden:
- alle `changed_candidate`
- alle `removed_candidate`
- sowie eine feste Kontrollgruppe aus `unchanged_candidate`
verwendet.

## Ziel des Subsets
Das Subset soll den Rural-Baseline-Run auf die tatsächlich interessanten Fälle fokussieren und gleichzeitig eine kleine stabile Referenzgruppe unveränderter Gebäude enthalten.

## Erwartung
Im ländlichen Szenario wird erwartet, dass Änderungen häufiger als neue oder entfernte Häuser auftreten als als komplexe geometrische Umbauten. Das Subset soll diese Struktur gezielt abbilden.