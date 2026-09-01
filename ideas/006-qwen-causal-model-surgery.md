# Idea 006 — Causal Model Surgery on Qwen

**Status:** Seed

## Core hypothesis

If recurring failures can be localized to reproducible internal mechanisms, a minimal causal intervention may eliminate the failure class while preserving unrelated capabilities.

## Escalation order

Do not begin with random weight edits. Progress from least invasive to most invasive:

1. Runtime activation/state intervention
2. Learned steering or gating
3. Small adapter/LoRA
4. Targeted permanent parameter change
5. Structural/topology experiment

## Experimental pattern

1. Reproduce one failure reliably.
2. Capture internal telemetry for failing and successful controls.
3. Localize candidate divergence points.
4. Intervene at exactly one location/variable.
5. Re-run the same case.
6. Run held-out related cases.
7. Run broad unrelated regression tests.
8. Keep only interventions with reproducible causal benefit and acceptable collateral cost.

## Primary question

Can a stronger external agent discover and validate small internal interventions that remove a reproducible failure mechanism from a smaller model?

## Important constraint

Use an instrumentable higher-precision model/checkpoint for surgery where practical, then quantize the validated result for comparison against the original deployment quantization. Avoid treating quantization artifacts as architectural effects.
