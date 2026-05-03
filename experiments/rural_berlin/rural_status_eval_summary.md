# Rural Status Evaluation Summary

## Ziel
Ziel dieser Auswertung war die getrennte externe Bewertung des Rural-Baseline-Runs für `unchanged`, `changed` und `removed`.

## Wichtigste Ergebnisse
### Unchanged
Für die ausgewerteten unveränderten Gebäude war der historische OSM-Stand 2018 bereits praktisch identisch zum OSM-Stand 2025. Der Workflow verschlechterte diese Fälle deutlich. Daraus folgt, dass der aktuelle Ansatz für unveränderte Gebäude zu aggressive Update-Entscheidungen erzeugt.

### Changed
Für geänderte Gebäude zeigte sich ein gemischtes Bild. Die endgültigen Geometrien lagen im Mittel nur minimal näher am OSM-Stand 2025 als die historischen Ausgangsobjekte. Fünf Fälle wurden verbessert, fünf Fälle verschlechtert. Dies spricht dafür, dass der Workflow bei geänderten Gebäuden grundsätzlich Potenzial besitzt, aber im aktuellen Setup noch zu instabil ist.

### Removed
Für entfernte Gebäude ergab sich ein klares Resultat. Alle sechs ausgewerteten Fälle blieben auch nach der Inferenz praktisch ohne relevante Überlappung mit aktuellen Gebäuden. Das deutet darauf hin, dass `removed`-Fälle mit dem aktuellen objektzentrierten Workflow überraschend gut als eigener Spezialfall behandelbar sind.

## Schlussfolgerung
Der Rural-Baseline-Run zeigt, dass der Workflow in ländlichen Gebieten differenziert betrachtet werden muss. Für unveränderte Gebäude ist vor allem eine konservativere Entscheidungslogik erforderlich. Für geänderte Gebäude sollte die Bild- und Prompt-Strategie weiter verbessert werden. Für entfernte Gebäude zeichnet sich bereits eine robuste Spezialfallbehandlung ab.