# Exp08 – Uncertainty-aware Urban Refinement (Design)

## Ziel
Entwicklung einer uncertainty-gesteuerten Urban-Logik, bei der unsichere Fälle automatisch einen zweiten, spezialisierteren Durchgang erhalten.

## Ausgangspunkt
Die bisherigen Urban-Experimente zeigen, dass Fehler nicht einheitlich auftreten, sondern stark von der Gebäude- und Szenenstruktur abhängen. Gleichzeitig ergeben sich bei einigen Fällen deutliche Unterschiede zwischen verschiedenen Prompt-Varianten. Dies legt nahe, Unsicherheit explizit zu modellieren.

## Grundidee
Ein erster Durchgang erzeugt ein initiales Ergebnis. Anschließend wird geprüft, ob der Fall stabil oder unsicher ist.

### Stabil
Das Ergebnis wird übernommen.

### Unsicher
Ein zweiter Durchgang wird ausgelöst, der gezielt auf den vermuteten Problemtyp reagiert.

## Geplante Unsicherheitsindikatoren
1. Prompt-Instabilität
2. Geometrische Instabilität
3. Entscheidungsinstabilität

## Ziel von Phase A
In Phase A wird noch kein vollständiger Unsicherheits-Workflow implementiert. Zunächst werden:
- Fehlerarten systematisch erfasst
- Unsicherheitskriterien definiert
- und die Logik für spätere Urban-Refinement-Experimente vorbereitet