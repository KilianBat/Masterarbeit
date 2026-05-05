# Phase B – Automatic feature extraction for routing

## Ziel
Ziel von Phase B ist die Ableitung automatisch berechenbarer Merkmale, die die in Phase A manuell validierten Fehlerklassen approximieren und damit eine spätere automatische Routing-Entscheidung vorbereiten.

## Ausgangspunkt
In Phase A wurden urbane Problemfälle zunächst manuell klassifiziert und anschließend in ein uncertainty-gestütztes Routing überführt. Diese manuelle Taxonomie diente bewusst als Entwicklungshilfe und soll nun in Richtung automatisierbarer Merkmale überführt werden.

## Grundidee
Für jedes urbane Objekt werden Merkmale aus Bild und Geometrie berechnet, darunter insbesondere:
- Helligkeits- und Schattenmerkmale
- Struktur- und Konkavitätsmerkmale
- Form- und Kompaktheitsmerkmale
- Unsicherheitsmerkmale aus bestehenden Experimentvarianten

## Ziel
Die automatische Merkmalsberechnung soll kein endgültiger Klassifikator sein, sondern ein erster nachvollziehbarer Schritt von manuell definierter Fehlerlogik zu automatisch ableitbarem Routing.

## Erwartung
Es wird erwartet, dass vor allem Schatten- und Strukturprobleme über einfache, regelbasierte Merkmale bereits sinnvoll separierbar sind.