# Urban Change-Type Classification Layer

## Ziel
Ziel dieses Schritts ist die Erweiterung des bisherigen urbanen Refinement-Workflows um eine explizite semantische Entscheidung darüber, welche Art von Veränderung für ein historisches OSM-Gebäude vorliegt. Die Segmentierung wird dadurch nicht mehr nur als Geometrieerzeugung verstanden, sondern als Grundlage einer anwendungsnahen Update-Entscheidung.

## Scope
Um den Urban-Block methodisch fokussiert und für die Masterarbeit beherrschbar zu halten, werden zunächst nur historische Bestandsobjekte klassifiziert. Neubauten werden in diesem Schritt noch nicht als Hauptklasse modelliert, da sie kein historisches OSM-Polygon als objektzentrierten Anker besitzen.

## Klassen
Für den aktuellen Urban-Block werden die folgenden Klassen verwendet:
- `unchanged`
- `modified`
- `review`
- optional `removed_candidate`

## Grundidee
Die Change-Type-Klassifikation baut auf dem aktuell besten Urban-Workflow (`urban_exp08b_shadow_refine`) auf. Sie verwendet keine spätere OSM-Referenz zur Laufzeit, sondern nur Informationen, die im realen Anwendungsszenario verfügbar wären:
- historisches OSM-Objekt
- aktuelles Orthophoto
- Segmentierungs- und Refinement-Ergebnisse
- interne Qualitäts- und Unsicherheitsmetriken

## Eingabesignale
Für die Klassifikation werden insbesondere herangezogen:
- finale `decision` aus dem Update-Workflow
- `final_source`
- `sam_score`
- `iou_map_vs_sam`
- `area_diff_frac`
- `centroid_shift_m`
- `routing_decision`
- `uncertainty_level`
- Information, ob ein spezialisierter Zweitdurchgang akzeptiert wurde

## Intuition der Klassen
### unchanged
Das historische Objekt wird als weiterhin plausibel angesehen. Es liegt keine ausreichend starke Evidenz für eine echte geometrische Änderung vor.

### modified
Das historische Objekt scheint im aktuellen Orthophoto verändert und die segmentierungsbasierte Evidenz für eine aktualisierte Geometrie ist stark genug.

### review
Der Fall ist gemischt, instabil oder nicht hinreichend eindeutig. Die Änderung soll nicht vollautomatisch klassifiziert werden, sondern als prüfungsbedürftig markiert werden.

### removed_candidate
Das historische Objekt wird im aktuellen Bild nicht mehr überzeugend bestätigt. Diese Klasse wird im aktuellen Urban-Block nur vorsichtig verwendet und ist methodisch als optionaler Spezialfall zu verstehen.

## Methodische Einordnung
Die spätere OSM-Referenz von 2025 dient ausschließlich der retrospektiven Evaluation der Klassifikation, nicht als Laufzeitwissen. Dadurch bleibt der Ansatz anwendungsnah, während die wissenschaftliche Bewertung weiterhin möglich ist.
