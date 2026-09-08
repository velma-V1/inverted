# Stage 7 — Tool / Skill / Verification / Recovery Tomography Implementation Plan

**Date:** 2026-09-08
**Governing design:** `docs/superpowers/specs/2026-09-08-v3-stage7-tool-skill-verification-recovery-tomography-design.md`

## Goal

Implement Stage 7 as a zero-inference scientific layer over the canonical replay kernel. Preserve `TEST_REPLAY.jsonl` as the only replay/result/failure authority, add append-only tomography metadata, and distinguish operating-surface deficits from model-internal boundaries with bounded matched contrasts.

## Task 1 — Freeze contracts and permanent boundary tests

Create `tomography_core.py` plus permanent tests for all 12 axes, dispositions, stop reasons, profile invariants, `certification_allowed=False`, protected veto, and Stage-4 route-back for new movement.

## Task 2 — Implement bounded planner geometry

Create `tomography_planner.py`. Admit only explicit Stage-7 divergence classes, require deterministic scoring/baseline/parent evidence, use existing evidence first, enforce max three new probes by default, never schedule a standalone generic retry, and require external-support exhaustion before a model-internal boundary can be declared.

## Task 3 — Compile through canonical replay

Create `tomography_replay.py`. Compile `TomographyProbe` + canonical intervention into ordinary `ReplayRequest` objects. Do not create a second executor or transport. Keep the frozen parent state/model provenance intact and add only Stage-7 metadata references.

## Task 4 — Add append-only scientific store

Create `tomography_store.py` with `CAPABILITY_RATCHET_V3_TOMOGRAPHY.jsonl`. Persist studies, probes, outcomes, and profiles only. Reject raw/private payload-shaped fields and validate internal study/probe/result references.

## Task 5 — Implement deterministic analysis

Create `tomography_analysis.py` for tool availability/selection/arguments/interpretation, verifier feedback, targeted recovery versus generic control, skill qualification evidence, protected regression veto, nonspecific retry detection, and model-internal residual qualification. Stage 7 never certifies.

## Task 6 — Orchestrate without new transport

Create `tomography_lab.py`. Accept injected adapters, call the existing `ReplayExecutor`, append Stage-7 outcomes that reference canonical replay results, preserve child failure snapshot IDs, and expose whether all adapters are fake for preflight.

## Task 7 — Extend autopsy/interventions and public API

Add explicit-evidence-only Stage-7 divergence detection to `autopsy.py`; add TOOL/SKILL/VERIFICATION_RECOVERY/ESCALATION treatment recipes to `interventions.py`; export Stage-7 contracts from `__init__.py`. Generic semantic failures remain `UNKNOWN_NOVEL`.

## Task 8 — Add zero-call historical planning CLI

Add `plan-tomography --auto-eligible` to `cli.py`. It must never execute a model or external tool and must return machine-readable plans or a valid stopped status such as `NO_ELIGIBLE_RESIDUALS` / `DECISION_ALREADY_RESOLVED`.

## Task 9 — Completion gate

Add a Stage-7 completion workflow covering Stage-7 tests, the full capability-ratchet suite, V2/full regressions, privacy, replay audit, zero-call historical planning, no `CERTIFIED` Stage-7 evidence, clean tree, and `MODEL_CALLS=0`.

## Non-negotiable boundaries

- No new executor or model transport.
- No real Qwen/Ollama/network/tool calls during implementation or preflight.
- No third blind retry.
- Default maximum three new probes per failure snapshot.
- Failed probes remain canonical child failures in `TEST_REPLAY.jsonl`.
- Protected regression stops promotion immediately.
- New Stage-7 `MOVEMENT` routes back through Stages 4→5→6 before Stage 8.
- Stage 7 cannot issue `CERTIFIED`.
