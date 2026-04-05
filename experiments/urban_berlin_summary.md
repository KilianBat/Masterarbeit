# Urban Berlin Summary

## Ziel des urbanen Experimentblocks
Ziel des urbanen Berlin-Blocks war es, einen vollständigen prototypischen Workflow zur Verifikation und Aktualisierung bestehender Gebäudepolygone mit Hilfe aktueller Orthophotos und eines promptbasierten Segmentierungsmodells aufzubauen und in einem realen, komplexen Stadtszenario zu untersuchen.

Im Mittelpunkt stand dabei nicht die vollständige Detektion aller Gebäude in einem Luftbild, sondern die objektzentrierte Überprüfung bereits vorhandener OSM-Gebäude. Ausgangspunkt war ein historischer OSM-Gebäudebestand aus dem Jahr 2018, der mit einem Berliner Orthophoto von 2025 kombiniert wurde. Daraus sollte ein Update-Produkt erzeugt werden, das bestehende Geometrien entweder beibehält oder durch modellbasierte Vorschläge ersetzt.

## Datengrundlage
Verwendet wurden:
- historischer OSM-Gebäudebestand (2018)
- aktuelles Berliner Orthophoto (2025)
- späterer OSM-Gebäudebestand (2025) als externe Referenz

Das Testgebiet war ein kleiner dichter Innenstadt-Ausschnitt in Berlin. Die Wahl fiel bewusst auf ein schwieriges urbanes Szenario mit:
- Blockrandbebauung
- Innenhöfen
- heterogenen Dachstrukturen
- starken Schlagschatten
- enger Nachbarschaft zwischen Gebäuden und Straßenräumen

## Pipeline
Für jedes OSM-Gebäude wurde ein georeferenzierter Bildchip erzeugt. Anschließend wurden aus dem bestehenden Polygon Prompts für SAM2 abgeleitet. Die modellierte Gebäudemaske wurde in ein Polygon zurückgeführt, geographisch referenziert und mit dem ursprünglichen OSM-Objekt verglichen. Daraus wurde ein Update-Produkt mit Entscheidungslogik (`keep`, `update`, `flag_review`) erzeugt.

Zusätzlich wurde eine externe Bewertung gegen den späteren OSM-Stand 2025 durchgeführt.

## Wichtigste Experimente
### Exp01 – Baseline
Bounding Box + ein positiver Innenpunkt.  
Diente als Ausgangspunkt für alle weiteren Experimente.

### Exp02 – Multipoint
Mehrere positive Innenpunkte innerhalb des OSM-Polygons.  
Keine Verbesserung gegenüber der Baseline.

### Exp03b – Ring negatives
Wenige positive Innenpunkte plus ringförmig verteilte negative Außenpunkte.  
Global schlechter, lokal teilweise hilfreich.

### Exp04 – Tight chips
Engerer Bildausschnitt um das jeweilige Gebäude bei gleicher Baseline-Promptstrategie.  
Dies war das robusteste allgemeine Setup des urbanen Blocks.

### Exp05 – OSM-reference iterative
Iterative, OSM-referenzgeführte Promptstrategie.  
Keine generelle Verbesserung, aber qualitative Vorteile bei komplexeren Gebäuden.

### Exp06a / Exp06b – Bildvorverarbeitung
CLAHE und Gamma-Aufhellung.  
Kein relevanter positiver Effekt.

### Exp07 – Topology-aware prompting
Topologiebewusste Prompt-Platzierung mit stärkerer Berücksichtigung komplexer Formen und Innenhofstrukturen.  
Qualitativ hilfreich bei schwierigen Gebäuden, aber nicht global besser als Exp04.

## Zentrale Beobachtungen
Im urbanen Szenario traten wiederholt dieselben Fehlerquellen auf:
- starke Schlagschatten
- dunkle Innenhöfe
- mehrere Dachniveaus innerhalb desselben Gebäudes
- heterogene Dachmaterialien und Dachaufbauten
- enge räumliche Nachbarschaft zu anderen Gebäuden
- Unterschiede zwischen sichtbarer Dachkontur und kartographischer OSM-Geometrie

Diese Faktoren führten dazu, dass visuell plausible Segmentierungen nicht automatisch näher an der späteren OSM-Referenz lagen.

## Wichtigste Ergebnisse
Intern zeigte Exp04 die stabilsten Gesamtergebnisse. Exp07 zeigte visuelle Vorteile bei komplexeren und innenhofreichen Gebäuden, blieb jedoch global leicht hinter Exp04 zurück.

In der externen Bewertung gegen OSM 2025 ergab sich:
- OSM 2018 → OSM 2025: Mean IoU = 0.7047
- Exp04 final → OSM 2025: Mean IoU = 0.6340
- Exp05 final → OSM 2025: Mean IoU = 0.6255
- Exp07 final → OSM 2025: Mean IoU = 0.6630

Keines der Experimente verbesserte den historischen OSM-Stand im Mittel. Exp07 war das beste der getesteten Experimente und verbesserte als einziges Setup zumindest einen Einzelfall gegenüber dem historischen Ausgangsobjekt.

## Schlussfolgerung
Der entwickelte Workflow ist technisch funktionsfähig und erzeugt nachvollziehbare geometrische Vorschläge. Für eine direkte automatische Aktualisierung urbaner OSM-Gebäudegeometrien ist er im getesteten Berliner Szenario jedoch noch nicht ausreichend robust. Die größte Schwierigkeit liegt nicht nur in der Prompt-Strategie, sondern in der komplexen Bildcharakteristik urbaner Orthophotos und in der Diskrepanz zwischen sichtbarer Dachstruktur und kartographischer Gebäudegeometrie.

Der urbane Block liefert damit eine belastbare Grundlage für die weitere Arbeit. Insbesondere zeigt er, welche Strategien im allgemeinen Fall stabiler sind (Exp04) und welche Strategien bei komplexeren Spezialfällen Potenzial besitzen (Exp07). Dies bildet die Basis für den nächsten Untersuchungsschritt in ländlicheren und geometrisch einfacheren Siedlungsstrukturen.