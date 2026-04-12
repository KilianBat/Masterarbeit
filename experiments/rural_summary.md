# Rural Summary – Lübars

## Ziel
Ziel des Rural-Blocks war die Untersuchung, ob der entwickelte Workflow in dörflichen und geometrisch einfacheren Siedlungsstrukturen robuster funktioniert als im urbanen Berliner Szenario.

## Gebiet
Als Testgebiet wurde Lübars gewählt. Das Gebiet ist durch freistehende Häuser, einfachere Dachformen, größere Grundstücke und geringere Gebäudedichte geprägt und bildet damit einen klaren Kontrast zur zuvor untersuchten dichten Innenstadtbebauung.

## OSM-Differenzanalyse
Der Vergleich von OSM 2018 und OSM 2025 ergab:
- 378 unchanged candidates
- 10 changed candidates
- 6 removed candidates
- 19 new candidates

Dies bestätigt die Erwartung, dass in ländlicheren Gebieten Änderungen häufig in Form neuer oder entfernter Gebäude auftreten.

## Wichtigste Ergebnisse
### Unchanged
Ein konservativer, keep-orientierter Decision Layer verhinderte unnötige Verschlechterungen unveränderter Gebäude. Damit zeigte sich, dass `unchanged` im finalen Workflow primär als Verifikationsfall behandelt werden sollten.

### Changed
Der wichtigste Fortschritt wurde bei geänderten Gebäuden erzielt. Größerer Chip, gelockerter Prompt und geometriebasiertes Re-Ranking verbesserten die Übereinstimmung mit OSM 2025 deutlich. Das deutet darauf hin, dass bei `changed`-Gebäuden insbesondere die Maskenauswahl ein zentraler Erfolgsfaktor ist.

### Removed
Entfernte Gebäude blieben auch nach der Modellinferenz klar ohne relevante Überlappung mit aktuellen Gebäuden. Der Workflow springt in diesen Fällen also nicht fälschlich auf heutige Nachbargebäude.

### New
Für neue Gebäude zeigte ein prototypischer kandidatenbasierter Ansatz, dass größere und gut sichtbare Neubauten grundsätzlich segmentierbar sind. Kleine, verdeckte oder in Vegetation liegende Gebäude wurden dagegen häufig verfehlt.

## Gesamteinschätzung
Der Workflow funktioniert im ländlichen Szenario insgesamt differenzierter und robuster als im urbanen Block. Besonders bei `changed` und `unchanged` konnten sinnvolle Strategien identifiziert werden. Gleichzeitig zeigen `new`-Gebäude, dass Sichtbarkeit und Kandidatenqualität eine zentrale Rolle spielen. Der Rural-Block liefert damit eine wichtige Ergänzung zum urbanen Szenario und erlaubt eine deutlich differenziertere Gesamtbewertung des Ansatzes.