# Phase A – Urban Error Taxonomy

## Ziel
Ziel von Phase A ist die systematische Analyse der Fehlerarten im urbanen Berliner Szenario. Die bisherigen Experimente haben gezeigt, dass die Segmentierungsqualität nicht nur global betrachtet werden sollte, sondern stark von der jeweiligen Problemstruktur des Gebäudes abhängt.

## Motivation
Im urbanen Block traten wiederholt ähnliche Fehler auf, insbesondere bei:
- Schatten auf Dächern
- Innenhöfen
- mehreren Dachniveaus
- heterogenen Dachsegmenten
- Verschmelzung mit Nachbarstrukturen
- unnatürlichen, zu runden oder geometrisch unplausiblen Polygonformen

Bevor neue Urban-Experimente entwickelt werden, soll daher systematisch erfasst werden, welche Fehlerarten bei welchen Gebäuden auftreten und welche bisherigen Varianten diese Fehler bereits teilweise verbessern konnten.

## Ziel der Taxonomie
Die Fehlerklassifikation dient drei Zwecken:
1. Bestimmung der primären Problemtypen im urbanen Szenario
2. Ableitung einer uncertainty-gesteuerten Verfeinerungslogik
3. Vorbereitung spezialisierter Reparaturdurchgänge in späteren Experimenten

## Verwendete Referenzexperimente
Die Fehleranalyse basiert auf:
- Exp04 – robusteste allgemeine Urban-Baseline
- Exp05 – OSM-referenzgeführte iterative Variante
- Exp07 – topologiebewusste Prompt-Variante

## Grundidee
Jeder urbane Testfall erhält:
- eine primäre Fehlerklasse
- optional eine sekundäre Fehlerklasse
- eine Einschätzung, welches bisherige Experiment das Objekt am besten behandelt
- eine Einschätzung, ob das Hauptproblem eher in Objektfindung, Maskenauswahl oder Polygonform liegt