# Exp09 targeted courtyard negative prompts

This folder contains a prompt plan for the targeted negative point experiment.

Before running SAM2 inference, open the debug figures and check whether the red negative points lie inside the courtyard or non-building region that should be excluded. If not, edit `configs/urban_berlin/exp09_courtyard_negative_prompts.json` and run this preparation script again.

The experiment should be interpreted as a targeted follow-up to the earlier global ring-negative experiment. It tests whether negative prompts help when applied only to cases where a clear exclusion region exists.
