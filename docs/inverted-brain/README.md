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

## Documents
- `2026-09-06-frontier-mechanism-harvest-design.md` — historical preregistration for the Claude/Codex frontier-mechanism experiment. Preserve unchanged.
- `2026-09-06-inverted-brain-vnext-harvest-compiler-design.md` — current architecture direction.
- `../superpowers/plans/2026-09-06-inverted-brain-frontier-mechanism-harvest.md` — historical build plan.
- `../superpowers/plans/2026-09-06-inverted-brain-vnext-harvest-compiler.md` — current update plan.
