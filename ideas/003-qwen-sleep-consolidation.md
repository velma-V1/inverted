# Idea 003 — Qwen Sleep / Dream / Consolidation Loop

**Status:** Seed

## Core hypothesis

Qwen works normally while raw successes and failures accumulate. During an offline "sleep" phase, Codex clusters recurring failures, proposes competing explanations/fixes, generates related dream cases, and tests whether a correction generalizes before anything is consolidated back into Qwen.

## Candidate cycle

1. **Wake:** Qwen performs real tasks.
2. **Episode capture:** preserve raw successful and failed trajectories plus metadata.
3. **Sleep:** Codex clusters recurring failure mechanisms.
4. **Dream:** generate unseen, adversarial, easier, harder, and counterfactual variants.
5. **Verification:** test candidate corrections on held-out cases and unrelated controls.
6. **Consolidation:** keep only corrections that improve the target failure class without unacceptable regression.

## Important constraint

Raw episodes remain immutable evidence. Compressed memories are hypotheses and must never replace the raw data.

## Candidate consolidation methods

- Retrieved memory/capsule
- Test-time adaptation
- Activation steering
- Small adapter/LoRA
- Structural/weight modification only after simpler methods fail

## Primary question

Can a small local model accumulate verified experience and convert recurring failure classes into durable improvements without catastrophic forgetting?
