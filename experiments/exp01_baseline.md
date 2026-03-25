# Experiment 01 – Baseline (BBox + 1 positiver Innenpunkt)

## Ziel
Prüfen, wie gut SAM2 Gebäude mit automatisch aus OSM abgeleiteten Standard-Prompts segmentiert.

## Ausgangsbeobachtung
Im bisherigen Berliner Beispiel zeigen sich häufig Abweichungen zwischen OSM und SAM2, insbesondere bei komplexen Dachformen, dunklen Innenhöfen und Schlagschatten.

## Änderung / Methode
- Prompt: Bounding Box aus OSM-Polygon
- zusätzlicher positiver Punkt: Polygon-Centroid
- Modell: SAM2.1 hiera large
- Datengrundlage: Berliner MVP-Ausschnitt, Orthophoto 2025, OSM als t1

## Erwartung / Hypothese
Die Bounding Box begrenzt den Suchraum. Der Innenpunkt soll SAM2 stärker auf das eigentliche Gebäude fokussieren.

## Dateien
- Script: `scripts/geo_run_sam2.py`
- Config: `configs/berlin_mvp.json`
- Outputs: `outputs/exp01_baseline/`
Stand: 18.03.2026
Commit: 

## Ergebnisse
- n = 8
- keep = 3
- update = 4
- flag_review = 1
- Mittelwert IoU = 0,722908
- Median IoU = 0,764431

## Qualitative Beobachtung
- gute Ergebnisse bei einfachen, klar isolierten Gebäuden
- Probleme bei Schatten, Innenhöfen, dichten Blockstrukturen

## Interpretation
Die Baseline funktioniert technisch stabil, liefert aber geometrisch oft ungenaue Vorschläge.