# Test-3 S1-R1 Protocol Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the invalid intervention-collapsing S1 runtime with a fresh, exact-80-call S1-R1 causal screen that guarantees meaningful fixed-order exposure and fails closed if exposure collapses.

**Architecture:** Preserve S0-frozen arm identities, orders, model identities, and the 80-call budget. Add a fresh 10-case Holdout A-R1 where every arm starts from the same deterministic verified failure; reserve exactly two model calls per arm-case, use shadow calls only to equalize compute after success/terminal state, and gate all primary verdicts on exact call accounting plus intervention-exposure evidence.

**Tech Stack:** Python 3.11+, stdlib, existing Ollama and mock adapters, existing deterministic task/oracle/gold primitives, PyYAML, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-01-test3-s1-r1-corrective-protocol.md`

## Global Constraints

- Preserve the original run `test3-s1-20260901-111233` as invalid measurement evidence.
- Preserve S0-selected arms and models; no oracle/analysis-only production component.
- Fresh Holdout A-R1 only.
- Exactly 10 matched cases, 2 calls per arm-case, 20 calls per arm, 80 total.
- No cache, no transport retries, no hidden-gold prompt leakage.
- Deterministic failed seed candidate is identical across arms for each case and consumes zero calls.
- Shadow calls are recorded but cannot mutate the candidate or outcome.
- Primary verdict fails closed unless the intervention-exposure contract is fully satisfied.
- GitHub remains mock/model-free only; real Ollama inference is local only.

---

### Task 1: Fresh corrective holdout and failed-state fixture

**Files:**
- Modify: `src/inverted/test3_s1_cases.py`
- Modify: `tests/test_test3_s1_cases.py`

**Interfaces:**
- Produces: `build_holdout_a_r1() -> list[ExecutionCase]`
- Produces: `build_seed_failure(case: ExecutionCase) -> Candidate`

- [ ] Write tests proving A-R1 contains exactly 10 deterministic disjoint cases and never overlaps original Holdout A/Test-2 holdout IDs.
- [ ] Write tests proving each seed fixture is deterministically unsuccessful and contains injected-fault metadata while the task remains unchanged.
- [ ] Run the focused tests and verify RED.
- [ ] Implement the new holdout and seed-failure helper using deterministic public benchmark primitives.
- [ ] Run focused tests and verify GREEN.
- [ ] Commit.

### Task 2: Exact two-call exposure runtime

**Files:**
- Modify: `src/inverted/test3_s1_runtime.py`
- Modify: `tests/test_test3_s1_runtime.py`

**Interfaces:**
- `matched_task_limit(...)` returns exactly 10 when four 20-call arms and A-R1 are supplied.
- `run_arm_task(...)` starts from a supplied deterministic failure fixture and consumes exactly two physical calls.
- `run_s1_screen(...)` returns exactly 80 physical calls and exposure accounting.

- [ ] Write failing tests that reject non-failing seed fixtures, require exactly two calls per arm-case, and prove shadow responses cannot alter final output.
- [ ] Write a failing full-screen test proving 10 × 4 × 2 = 80 calls, 20 per arm, zero cache hits, and at least one active intervention in every arm-case.
- [ ] Verify RED.
- [ ] Implement baseline two-attempt best-single semantics, fixed-order active/shadow semantics, and explicit call-row fields `active_intervention`, `shadow_only`, and `planned_component`.
- [ ] Record `first_active_component`, `active_inference_calls`, `shadow_inference_calls`, `seed_failure_verified`, and per-arm exposure accounting.
- [ ] Fail closed on any budget or exposure divergence.
- [ ] Verify focused GREEN.
- [ ] Commit.

### Task 3: Primary-claim protocol validity gate

**Files:**
- Modify: `src/inverted/test3_s1_analysis.py`
- Modify: `tests/test_test3_s1_analysis.py`

**Interfaces:**
- `summarize_s1(...)` adds intervention exposure coverage.
- `derive_s1_verdict(...)` accepts/derives protocol validity and returns `S1_INVALID_INTERVENTION_EXPOSURE` before any architecture claim when invalid.

- [ ] Write failing tests proving a 24-call/6-task legacy-shaped run is invalid regardless of outcome.
- [ ] Write failing tests proving exact 80-call R1 evidence with valid exposure can reach the existing strong-signal rule.
- [ ] Verify RED.
- [ ] Implement the validity gate and active/shadow summaries.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 4: R1 config, CLI, evidence, and short progress line

**Files:**
- Modify: `configs/test3-s1.yaml`
- Modify: `src/inverted/test3_s1_cli.py`
- Modify: `src/inverted/test3_s1_progress.py`
- Modify: `src/inverted/test3_s1_artifacts.py`
- Modify: `tests/test_test3_s1_cli.py`
- Modify: `tests/test_test3_s1_artifacts.py`

**Interfaces:**
- `dry-plan` reports `PROTOCOL=S1-R1`, `HOLDOUT=A-R1`, 10 matched cases, and planned exact 80 calls.
- `run` refuses any config that is not the corrective protocol.
- evidence includes protocol validity, predecessor invalid run, and intervention exposure.

- [ ] Write failing tests for the R1 config contract and concise progress renderer (<64 characters under normal counters).
- [ ] Write failing CLI tests proving mock R1 emits 80 calls and a valid protocol gate.
- [ ] Verify RED.
- [ ] Implement config/CLI/evidence wiring and short progress output.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 5: GitHub green-light gate

**Files:**
- Modify: `.github/workflows/test3-s1-validation.yml` only if needed for stronger assertions.
- Modify: `tests/test_test3_s1_workflow_contract.py`

**Interfaces:**
- GitHub mock S1-R1 must prove exact 80 calls and valid intervention exposure without Ollama/Tier-A authorization.

- [ ] Add/adjust workflow-contract regression tests.
- [ ] Verify RED if workflow changes are required.
- [ ] Update validation assertions to require protocol `S1-R1`, exact 80 calls, 10 matched tasks, and protocol-valid mock evidence.
- [ ] Run full GitHub matrix plus Test-2, S0 replay, and S1 validation.
- [ ] Confirm every relevant workflow is green on the same final commit.
- [ ] Only then provide the local dry-plan / Tier-A rerun command.
