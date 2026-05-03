# Exp08 – Urban uncertainty analysis from existing experiments

## Ziel
Ziel dieses Schritts ist es, Unsicherheit im urbanen Szenario aus bereits vorhandenen Experimenten abzuleiten, ohne sofort einen neuen Modelllauf durchzuführen.

## Grundlage
Verwendet werden die drei bisherigen Urban-Referenzexperimente:
- Exp04 – robuste Baseline
- Exp05 – OSM-referenzgeführte Variante
- Exp07 – topologiebewusste Variante

## Grundidee
Wenn dieselben urbanen Gebäude unter mehreren plausiblen Experimentvarianten stark unterschiedliche Geometrien oder Entscheidungen erzeugen, deutet dies auf Unsicherheit hin.

## Verwendete Unsicherheitsindikatoren
1. Geometrische Übereinstimmung zwischen den Varianten
2. Flächenstreuung
3. Zentroid-Streuung
4. Entscheidungsstreuung (`keep`, `update`, `flag_review`)

## Ziel der Auswertung
Für jedes urbane Gebäude soll festgelegt werden:
- ob der Fall stabil oder unsicher ist
- wie hoch die Unsicherheit ist
- welche spätere Reparaturstrategie voraussichtlich am besten passt

## Erwarteter Nutzen
Diese Auswertung bildet die Grundlage für:
- uncertainty-gesteuerte Zweitläufe
- error-specific repair passes
- spätere geometrische Nachbearbeitung