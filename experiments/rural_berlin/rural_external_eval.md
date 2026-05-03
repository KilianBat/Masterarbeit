# Rural External Evaluation – Lübars

## Ziel
Ziel dieses Schritts ist die externe Bewertung des ländlichen Baseline-Runs gegen den aktuellen OSM-Stand 2025, getrennt nach den Statusklassen `unchanged`, `changed` und `removed`.

## Motivation
Die interne Evaluation zeigt nur, wie stark die durch SAM2 erzeugte Geometrie vom historischen OSM-Objekt abweicht. Für die eigentliche Fragestellung der Arbeit ist jedoch entscheidend, ob das Update-Produkt dem späteren OSM-Stand 2025 näherkommt.

Im ländlichen Szenario ist zusätzlich wichtig, dass Änderungen häufiger als neue oder entfernte Gebäude auftreten. Deshalb wird die externe Bewertung statusweise durchgeführt.

## Bewertungslogik
- Für `unchanged` und `changed` wird die finale Geometrie gegen das im OSM 2025 zugeordnete Referenzobjekt verglichen.
- Für `removed` wird geprüft, ob die finale Vorhersage weiterhin nur geringe Überlappung mit aktuellen Gebäuden besitzt oder stattdessen fälschlich auf ein heutiges Gebäude „springt“.
- `new` wird in dieser Evaluationsstufe nicht direkt bewertet, da der aktuelle Workflow objektzentriert auf historischen Gebäuden basiert und daher keine eigenständige Neuerkennung durchführt.

## Ziel der Analyse
Die statusweise Analyse soll beantworten:
1. Funktioniert der Workflow bei `unchanged`-Gebäuden bereits sinnvoll?
2. Scheitert er bei `changed`-Gebäuden vor allem an der historischen Prompt-Verankerung?
3. Sind `removed`-Fälle mit dem aktuellen Ansatz grundsätzlich nicht gut modellierbar?