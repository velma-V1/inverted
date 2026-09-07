# Universal System Test Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, validated template and comparison planner for RAW, Brain, INVERTED System, and Brain+INVERTED system testing.

**Architecture:** Keep the new layer isolated under `src/inverted/system_testing/`. JSON manifests define systems and mechanisms; Python validates immutable causal contracts and expands only decision-relevant comparisons. No inference is performed by this layer.

**Tech Stack:** Python 3.11+, standard library JSON/dataclasses/enums, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-universal-system-test-templates-design.md`

## Global Constraints

- Preserve historical evidence and existing benchmark behavior.
- No model call may occur during template loading or planning.
- Every comparison must name the decision it can change.
- Do not enumerate the full mechanism power set.
- Model authority boundaries remain explicit and system-owned where required.
### Task 1: Template contract and validation

**Files:**
- Create: `src/inverted/system_testing/types.py`
- Create: `src/inverted/system_testing/templates.py`
- Create: `src/inverted/system_testing/__init__.py`
- Test: `tests/test_system_testing_templates.py`

- [ ] Write failing tests for valid loading, RAW invariants, duplicate/unknown references, responsibility ownership, and authority-boundary rejection.
- [ ] Run focused tests and confirm RED for missing module/API.
- [ ] Implement the minimum immutable dataclasses/enums and JSON loader/validator.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Decision-relevant comparison planner

**Files:**
- Create: `src/inverted/system_testing/planner.py`
- Test: `tests/test_system_testing_planner.py`

- [ ] Write failing tests for full-vs-raw, isolation, leave-one-out, declared interactions, deterministic ordering, exact counts, and no power-set expansion.
- [ ] Run focused tests and confirm RED.
- [ ] Implement deterministic comparison expansion with explicit decision IDs/reasons.
- [ ] Run focused tests and confirm GREEN.
### Task 3: Initial system manifests

**Files:**
- Create: `configs/system-tests/raw.json`
- Create: `configs/system-tests/brain.json`
- Create: `configs/system-tests/inverted-system.json`
- Create: `configs/system-tests/brain-inverted.json`
- Test: `tests/test_system_testing_profiles.py`

- [ ] Write failing tests asserting all four manifests satisfy one contract and form the exact Brain×INVERTED 2×2 core.
- [ ] Run focused tests and confirm RED because manifests are absent.
- [ ] Add minimal manifests with explicit mechanism ownership, causal requirements, and the mandatory compound interaction.
- [ ] Run focused tests and confirm GREEN.

### Task 4: Regression and decision-ready handoff

**Files:**
- Modify only if necessary: package exports/docs referenced by tests.

- [ ] Run the three new focused test modules together.
- [ ] Run full `pytest -q`.
- [ ] Inspect `git diff --check` and `git status --short`.
- [ ] Record exact files, test counts, and remaining boundary: templates/planner complete; real campaign execution not started.