# Inverted Brain

This directory contains research and operator documentation for the isolated `inverted-brain` branch. It is separate from the original Inverted executor/auditor experiment on `main`.

## Current Direction
The project is no longer trying to invent every agent primitive from scratch. Existing systems are harvested for mechanisms; only causally supported, bounded, transferable mechanisms are compiled into Inverted.

The target architecture has six learning destinations:
- `BRAIN` — cognitive policy and meta-reasoning;
- `SYSTEM` — governance, execution authority, verification, rollback;
- `SKILL` — repeatable procedural knowledge loaded on demand;
- `TOOL_HAND` — executable atomic tools or specialized multi-step hands;
- `MEMORY` — durable facts/state with provenance;
- `NEGATIVE_EVIDENCE` — failed/rejected mechanisms preserved for future decisions.

## Frozen Universal Harvest Specifications — 2026-09-07

These three documents are the authoritative design basis for the next test-template build. **They are frozen design only; implementation requires explicit operator approval.**

- `2026-09-07-universal-harvest-frozen-contract.md` — shared laws, adaptive frontier, immutable/raw evidence rules, complete forensic recorder, reasoning/memory capture, checkpoint/replay requirements, derivative-experiment policy, and mechanism promotion rules.
- `2026-09-07-local-continuation-harvest-frozen-spec.md` — locked 1–2B -> Qwen 9B -> Devstral 24B continuation ladder, one-retry law, freeze/handoff semantics, sampled fresh controls, compute-aware scheduling, and Claude/Codex frontier resolution.
- `2026-09-07-frontier-cloud-harvest-frozen-spec.md` — separate Claude/Codex/ChatGPT native harvest at the 11/10 evidence standard, redundant observation, memory/thought/reasoning capture when exposed, decision checkpoints, counterfactual replay, first-divergence analysis, and seven adaptive frontier edge-case families.

### Change Control

- Do not weaken or silently reinterpret these specifications during implementation.
- Any material change requires explicit operator approval and a versioned amendment.
- Do not rely on conversational memory as the sole source of requirements; read the frozen repository specifications and source conversation when clarification is necessary.
- Preserve historical evidence and the original Inverted experiment unchanged.

## Historical / Supporting Documents
- `2026-09-06-frontier-mechanism-harvest-design.md` — historical preregistration for the Claude/Codex frontier-mechanism experiment. Preserve unchanged.
- `2026-09-06-inverted-brain-vnext-harvest-compiler-design.md` — current architecture direction preceding the frozen Universal Harvest specifications.
- `../superpowers/plans/2026-09-06-inverted-brain-frontier-mechanism-harvest.md` — historical build plan.
- `../superpowers/plans/2026-09-06-inverted-brain-vnext-harvest-compiler.md` — current update plan preceding the Universal Harvest template work.
