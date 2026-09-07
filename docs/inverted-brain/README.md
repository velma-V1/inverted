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

These documents are the authoritative design basis for the next test-template build. **They are frozen design only; implementation requires explicit operator approval.**

- `2026-09-07-universal-harvest-frozen-contract.md` — shared laws, fairness contract, mandatory container Harvest Lab, canonical forensic event schema, adaptive frontier, immutable/raw evidence rules, reasoning/memory capture, checkpoint/replay requirements, automatic autopsy package, concurrent scheduler, and mechanism promotion rules.
- `2026-09-07-local-continuation-harvest-frozen-spec.md` — locked 1–2B -> Qwen 9B -> Devstral 24B continuation ladder, one-retry law, freeze/handoff semantics, sampled fresh controls, compute-aware scheduling, and Claude/Codex frontier resolution.
- `2026-09-07-frontier-cloud-harvest-frozen-spec.md` — separate Claude/Codex/ChatGPT native harvest at the 11/10 evidence standard, passive-versus-instrumented reasoning separation, redundant observation, memory/thought/reasoning capture when exposed, decision checkpoints, counterfactual replay, automatic trajectory autopsy, first-divergence analysis, and seven adaptive frontier edge-case families.
- `2026-09-07-universal-harvest-audit-amendment-v2.md` — authoritative post-audit clarifications: current-tier frontier climbing, complete eleven-system/source inventory, teacher-trajectory preservation semantics, frozen Weinberg-derived hypothesis inventory, knowledge/claim provenance, current-state ownership, attention/resource-allocation proxy, optional deep local neural telemetry, redundancy/order ledgers, mandatory per-task comparison artifacts, and maximum frontier-data preservation.

The source inventory is maintained in `configs/inverted_brain/harvest_sources.yaml` and is authoritative for source admission/roles.

### Change Control

- Do not weaken or silently reinterpret these specifications during implementation.
- Any material change requires explicit operator approval and a versioned amendment.
- Where the audit amendment is more specific than earlier wording, the amendment controls.
- Do not rely on conversational memory as the sole source of requirements; read the frozen repository specifications and source conversation when clarification is necessary.
- Preserve historical evidence and the original Inverted experiment unchanged.

## Historical / Supporting Documents
- `2026-09-06-frontier-mechanism-harvest-design.md` — historical preregistration for the Claude/Codex frontier-mechanism experiment. Preserve unchanged.
- `2026-09-06-inverted-brain-vnext-harvest-compiler-design.md` — architecture direction preceding the frozen Universal Harvest specifications.
- `../superpowers/plans/2026-09-06-inverted-brain-frontier-mechanism-harvest.md` — historical build plan.
- `../superpowers/plans/2026-09-06-inverted-brain-vnext-harvest-compiler.md` — current update plan preceding the Universal Harvest template work.
