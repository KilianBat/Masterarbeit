# Externe Evaluation gegen OSM 2025

## Ziel
Prüfen, ob die aus OSM 2018 und Orthophoto 2025 erzeugten Update-Produkte dem späteren OSM-Stand 2025 näherkommen als der ursprüngliche OSM-Stand 2018.

## Motivation
Die bisherigen Experimente wurden zunächst intern bewertet, also anhand der Ähnlichkeit zwischen dem ursprünglichen OSM-Objekt und der durch SAM2 erzeugten Geometrie. Diese interne Bewertung ist jedoch nicht ausreichend, um zu beurteilen, ob der Workflow tatsächlich eine sinnvolle Aktualisierung erzeugt. Daher wurde zusätzlich eine externe Referenzbewertung gegen den späteren OSM-Stand 2025 durchgeführt.

## Datengrundlage
- Ausgangsdaten: `berlin_buildings_20180101.gpkg`
- Referenz: `data/raw/berlin_buildings.gpkg` (OSM 2025)
- verglichene Experimente:
  - Exp04: `exp04_tightchip_baseline`
  - Exp05: `exp05_osmref_iterative`
  - Exp07: `exp07_topology_aware`

## Ergebnisse
Mittelwerte der IoU gegen OSM 2025:

- OSM 2018 → OSM 2025: 0.7047
- Exp04 final → OSM 2025: 0.6340
- Exp05 final → OSM 2025: 0.6255
- Exp07 final → OSM 2025: 0.6630

Verbesserte Objekte gegenüber OSM 2018:
- Exp04: 0 / 8
- Exp05: 0 / 8
- Exp07: 1 / 8

## Interpretation
Keines der getesteten Experimente verbessert den Datensatz im Mittel gegenüber dem ursprünglichen OSM-Stand 2018. Das beste Ergebnis erzielt Exp07, bleibt jedoch ebenfalls unterhalb der Ausgangsqualität des 2018er OSM im Vergleich zu OSM 2025.

Dies deutet darauf hin, dass der Workflow zwar visuell plausible und teilweise strukturtreuere Gebäudekonturen erzeugen kann, diese aber nicht automatisch besser mit der späteren kartographischen Repräsentation übereinstimmen. Eine zentrale Ursache scheint die Diskrepanz zwischen sichtbarer Dachkontur im Orthophoto und der kartographischen Gebäudegeometrie in OSM zu sein. Zusätzlich wirken sich Schatten, Innenhöfe und heterogene Dachstrukturen negativ auf die Segmentierungsqualität aus.

## Schlussfolgerung
Der bisherige Workflow eignet sich in der getesteten Form nicht für eine direkte automatische Aktualisierung urbaner OSM-Gebäudegeometrien. Gleichzeitig zeigen einzelne Ergebnisse, insbesondere aus Exp07, dass topologiebewusste Strategien bei komplexeren Gebäuden hilfreich sein können. Für die weitere Arbeit ist daher eine stärkere Fokussierung auf:
1. schwierigkeitsabhängige Strategien,
2. andere Siedlungsstrukturen,
3. sowie die Trennung von Verifikation bestehender Objekte und Neuentdeckung
sinnvoll.