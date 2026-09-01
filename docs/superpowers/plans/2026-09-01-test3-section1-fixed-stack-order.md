# Test-3 Section 1 Fixed Stack/Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the bounded Tier-A Section-1 fixed-stack/order screen that consumes the frozen S0 handoff, runs on a dedicated Holdout A, enforces the 80-physical-call ceiling, and emits a self-contained forensic evidence packet.

**Architecture:** S1 loads the finalized S0 preregistration and the Test-2 Tier-A source referenced by the immutable S0 source manifest. It resolves the frozen best-single and repair-role models from Test-2 evidence, builds a fresh deterministic Holdout A, then executes the four frozen arms under independent per-arm physical-call caps. Primary inference uses only tasks completed by every arm; partial/budget-limited work remains evidence but cannot enter the matched causal comparison.

**Tech Stack:** Python 3.11+, stdlib, existing Ollama adapter, existing Test-2 domain/oracle/gold/budget primitives, PyYAML, pytest, GitHub Actions for mock/model-free validation only.

**Spec:** `docs/superpowers/specs/2026-09-01-adaptive-evidence-discovery-campaign-design.md`

## Global Constraints

- Section 1 answers only whether fixed component order has enough causal value to justify further fixed-topology optimization.
- Dedicated Holdout A only; no Test-2 holdout reuse.
- Tier-A architecture claims require real local model inference; GitHub validation uses mocks/dry-run only.
- Hard S1 ceiling: 80 new physical model calls total; frozen four-arm screen uses a 20-call ceiling per arm.
- No outcome-dependent early stopping. Budget/integrity/infrastructure guards are the only allowed early termination conditions.
- Model adapter retries remain disabled so physical-call accounting is exact.
- Hidden gold may score outcomes but must never enter model prompts, controller decisions, repair prompts, or verifier inputs.
- Raw prompts, raw responses, failures, cache/accounting, telemetry, edge cases, and instrumentation anomalies are retained.
- `oracle_auditor` and any other analysis-only component are forbidden from production S1 arms.
- S0 power evidence remains authoritative: the 80-call S1 screen is underpowered for the configured ~3pp target effect, so a null screen cannot rule out that small effect.

---

### Task 1: Frozen S1 input resolution and Holdout A

**Files:**
- Create: `src/inverted/test3_s1_inputs.py`
- Create: `src/inverted/test3_s1_cases.py`
- Test: `tests/test_test3_s1_inputs.py`
- Test: `tests/test_test3_s1_cases.py`

**Interfaces:**
- Consumes: `candidate_section1_preregistration.json`, S0 `source_manifest.json`, Test-2 `models/router-policy.json`, Test-2 `models/role-champions.json`.
- Produces: `S1ResolvedInputs`, `load_s1_inputs(...)`, `build_holdout_a()`.

- [ ] Write failing tests that reject an unfrozen S1 packet, reject oracle-containing arms, resolve `best_single_model` and `repairer` from the manifest-selected Test-2 Tier-A bundle, and prove Holdout A is deterministic/disjoint from Test-2 holdout seeds.
- [ ] Run focused tests and verify RED.
- [ ] Implement minimal immutable input resolution and 12-case Holdout A (`state/policy/reconciliation × complexity 1..4`) using seeds beginning at `211000`.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 2: Budgeted fixed-order runtime

**Files:**
- Create: `src/inverted/test3_s1_runtime.py`
- Test: `tests/test_test3_s1_runtime.py`

**Interfaces:**
- Consumes: `S1ResolvedInputs`, Holdout A cases, model adapters.
- Produces: `run_s1_screen(...) -> dict[str, Any]` with trials, model calls, events, validator results, arm accounting, and incomplete-task evidence.

- [ ] Write failing tests for exact 20-call arm caps, 80-call global ceiling, no internal retries, no cross-arm cache reuse, same matched task prefix, hidden-gold prompt exclusion, `requirement_validator/retry/targeted_repair/final_validator` ordering semantics, and fail-closed unknown components.
- [ ] Run focused tests and verify RED.
- [ ] Implement one-shot best-single baseline plus fixed-order interpreter. `retry` creates a fresh executor output only when current state is unsuccessful; `targeted_repair` creates a fresh repairer output only when unsuccessful; validators are deterministic and consume zero model calls; `final_validator` is terminal on failure. Each arm starts with a fresh executor candidate.
- [ ] Before each task, reserve against the arm's worst-case calls-per-task so no task is cut in half by a budget boundary. Execute the same deterministic Holdout-A prefix for all arms based on the most expensive frozen arm.
- [ ] Preserve all raw calls, prompts/responses, validator states, transitions, budget guards, cache fields, failures, and model-call errors.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 3: Matched causal analysis and preregistered screen verdict

**Files:**
- Create: `src/inverted/test3_s1_analysis.py`
- Test: `tests/test_test3_s1_analysis.py`

**Interfaces:**
- Consumes: completed S1 trial rows.
- Produces: `summarize_s1(...)`, pairwise matched transitions/effects, efficiency rows, `derive_s1_verdict(...)`.

- [ ] Write failing tests proving primary analysis includes only task IDs completed by every arm, reports wins-created/wins-destroyed/net-wins, catastrophe deltas, call/token efficiency, and cannot upgrade an underpowered null result into proof of no fixed-order effect.
- [ ] Run focused tests and verify RED.
- [ ] Implement large-signal screen rule: a fixed order is a strong S1 signal only if it gains at least two matched net wins versus baseline, adds no catastrophes, and also gains at least one matched net win versus the random-order control. Otherwise return `S1_SCREEN_NON_DECISIVE` and explicitly preserve the S0 full-power requirement.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 4: Forensic packet, CLI, and local authorization gate

**Files:**
- Create: `src/inverted/test3_s1_artifacts.py`
- Create: `src/inverted/test3_s1_cli.py`
- Create: `configs/test3-s1.yaml`
- Test: `tests/test_test3_s1_artifacts.py`
- Test: `tests/test_test3_s1_cli.py`

**Interfaces:**
- Commands: `python -m inverted.test3_s1_cli dry-plan ...`, `python -m inverted.test3_s1_cli mock-smoke ...`, `python -m inverted.test3_s1_cli run ... --authorize-tier-a`.

- [ ] Write failing tests that `run` refuses inference without explicit `--authorize-tier-a`, validates frozen 80/20×4 budget contract, and emits a hash-sealed packet containing preregistration/config/provenance/model calls/events/trials/validators/arm summaries/pairwise effects/failures/wins/losses/edge cases/anomalies/verdict/report/complete evidence/SHA inventory.
- [ ] Run focused tests and verify RED.
- [ ] Implement config loading and Ollama adapters with `temperature=0`, `think=false`, `transport_retries=0`, exact configured context/token limits, and model identity provenance before/after inference where available.
- [ ] Implement artifact writer and human-readable report. Raw evidence remains authoritative.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 5: GitHub validation and completion verification

**Files:**
- Create: `.github/workflows/test3-s1-validation.yml`
- Test: `tests/test_test3_s1_workflow_contract.py`

**Interfaces:**
- GitHub performs full pytest plus `dry-plan`/`mock-smoke`; it must never call Ollama or authorize Tier-A inference.

- [ ] Write failing workflow-contract test proving GitHub has no local-model/Ollama inference step and never passes `--authorize-tier-a`.
- [ ] Verify RED.
- [ ] Add workflow that runs full pytest, S1 mock smoke, verifies the 80-call/zero-real-inference contract, and uploads mock forensic evidence.
- [ ] Verify GREEN in GitHub Actions.
- [ ] Run all existing Test/Test-2/Test-3-S0 workflows and confirm no regression.
- [ ] Confirm `main` is unchanged and S1 remains isolated on `build/test3-s1-fixed-stack-order`.
- [ ] Commit completion state.
