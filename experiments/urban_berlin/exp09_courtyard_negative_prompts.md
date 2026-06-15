# Exp09: Targeted Courtyard Negative Prompts

## Motivation

The earlier ring-negative experiment applied negative prompting as a general strategy. It did not improve the urban workflow overall and in several cases degraded the segmentation. Exp09 therefore tests a more targeted hypothesis: negative point prompts may be useful only for buildings where the error source is a clearly identifiable courtyard or non-building region inside the chip.

## Research question

Can a deliberately placed negative point inside a courtyard or non-building interior region improve SAM2 building proposals for difficult urban cases?

## Target cases

The first target set is deliberately small:

- ID 21: courtyard / multi-level roof case; previous topology pass unstable
- ID 32: courtyard / context ambiguity; previous topology refinement helped
- ID 27: multi-part roof / possible inner non-building region

This experiment should not be interpreted as a global replacement for the best urban workflow. It is a targeted ablation for one error type.

## Experimental protocol

1. Generate annotated prompt previews using `prepare_exp09_courtyard_negative_prompts.py`.
2. Manually check that red negative points lie inside the intended courtyard or non-building area.
3. Run SAM2 inference with the same positive prompt and bounding-box setup as the baseline, plus the additional negative point.
4. Vectorise and externally evaluate the result against OSM 2025 using the existing evaluation pipeline.
5. Compare Exp09 only on the targeted object IDs against:
   - Exp04 baseline
   - Exp08b current best workflow
   - Exp09 negative point prompt result

## Expected interpretation

A positive result would show that negative point prompts can help when applied selectively to courtyard-type failures. A negative or mixed result would still be informative because it would confirm that exclusion prompts are sensitive to placement and should not be applied automatically without reliable courtyard detection.

## Thesis relevance

Exp09 directly addresses the supervisor suggestion to test negative point prompts for courtyards. It also sharpens the methodological distinction between global prompting strategies and error-type-specific refinement modules.
