# Test-3 S1-R2 Expanded Category Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement S1-R2 as a fresh, exact-200-call, six-family fixed-order causal screen while preserving S1-R1 behavior and evidence.

**Architecture:** Extend the benchmark with three isolated task-family generators, build a deterministic A-R2 holdout and category-specific seed failures, generalize the S1 runtime/analysis to support protocol-specific contracts, then wire CLI/config/artifacts/CI to enforce exact 200-call execution. R1 remains reproducible and immutable; R2 uses the same four arms and two-call active/shadow intervention semantics.

**Tech Stack:** Python 3.11–3.14, pytest, PyYAML, existing Ollama/Mock adapters, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-01-test3-s1-r2-expanded-category-screen-design.md`

## Global Constraints

- Protocol: `S1-R2`; holdout: `A-R2`.
- Exactly 25 matched tasks, 4 arms, 2 physical calls per arm-task, 50 calls per arm, 200 total calls.
- Families: `state`, `policy`, `reconciliation`, `preservation`, `dependency_order`, `repair_containment`.
- Exact seeds/order from the spec; no outcome-dependent selection or stopping.
- Preserve S1-R1 code path and historical evidence semantics.
- No hidden target state, `critical`, hidden-gold, injected-fault metadata, or oracle-only metadata in model prompts.
- Zero cache hits and zero hidden/transport retries.
- Deterministic balanced arm execution order by task as preregistered.
- Any schedule/exposure/leakage violation invalidates the primary R2 verdict.

---

### Task 1: Add the three R2 task families

**Files:**
- Modify: `src/inverted/tasks.py`
- Test: `tests/test_tasks.py`

**Interfaces:**
- Produces: `generate_task(family: str, complexity: int, seed: int) -> TaskCase` support for `preservation`, `dependency_order`, and `repair_containment`.
- Consumes: existing `Requirement`, `Action`, `WorldState`, `apply_actions` semantics.

- [ ] **Step 1: Write failing tests** asserting each new family is deterministic for a seed, exposes only supported requirement/action semantics, generates a valid target state, and spans L1–L4.
- [ ] **Step 2: Run `python -m pytest tests/test_tasks.py -q`** and verify RED because the families are currently rejected.
- [ ] **Step 3: Implement minimal family generators** using existing `preserve`, `action_present`, `action_before`, `equal`, `action_absent`, `grant`, `start`, and `set` semantics; add public requirements without exposing `critical`.
- [ ] **Step 4: Run `python -m pytest tests/test_tasks.py -q`** and verify GREEN.
- [ ] **Step 5: Commit** `feat: add S1-R2 task families`.

### Task 2: Freeze A-R2 holdout, seed failures, and arm schedule

**Files:**
- Modify: `src/inverted/test3_s1_cases.py`
- Test: `tests/test_test3_s1_cases.py`

**Interfaces:**
- Produces: `build_holdout_a_r2() -> list[ExecutionCase]`, `build_seed_failure_r2(case: ExecutionCase) -> Candidate`, and `r2_arm_order(task_index: int) -> tuple[str, ...]`.
- Consumes: new task families and existing deterministic oracle evaluation.

- [ ] **Step 1: Write failing tests** for exact 25-case family/complexity/seed order, seed disjointness from Test-2/A/A-R1, exact category-specific fault behavior, identical seed candidate across arms, and preregistered balanced arm order.
- [ ] **Step 2: Run `python -m pytest tests/test_test3_s1_cases.py -q`** and verify RED.
- [ ] **Step 3: Implement A-R2 and category-specific seed failures** exactly from the spec; verify every seed candidate fails before inference and containment seeds preserve the initially-correct requirement set.
- [ ] **Step 4: Implement deterministic `r2_arm_order`** for indices 0–24.
- [ ] **Step 5: Run `python -m pytest tests/test_test3_s1_cases.py -q`** and verify GREEN.
- [ ] **Step 6: Commit** `feat: freeze S1-R2 holdout and seed failures`.

### Task 3: Generalize runtime to exact-200 R2 without breaking R1

**Files:**
- Modify: `src/inverted/test3_s1_runtime.py`
- Test: `tests/test_test3_s1_runtime.py`

**Interfaces:**
- Produces protocol-aware `run_s1_screen(...)` that can execute R1 and R2 contracts, preserving two-call active/shadow semantics.
- Consumes: `build_seed_failure_r2`, `r2_arm_order`, protocol config values.

- [ ] **Step 1: Write failing R2 runtime tests** asserting exactly 100 arm-task trials, 200 physical calls, 50 per arm, 2 per arm-task, no cache, at least one active intervention per arm-task, balanced task-blocked arm execution order, and fail-closed behavior on any count/order mismatch.
- [ ] **Step 2: Add regression tests** proving existing R1 exact-80 mock behavior still passes unchanged.
- [ ] **Step 3: Run `python -m pytest tests/test_test3_s1_runtime.py -q`** and verify RED only on missing R2 support.
- [ ] **Step 4: Refactor constants into protocol contract data** rather than replacing R1 constants; route seed builder and execution ordering by protocol.
- [ ] **Step 5: Preserve public-safe repair feedback** and add explicit assertion that model-call prompts contain no forbidden metadata.
- [ ] **Step 6: Run `python -m pytest tests/test_test3_s1_runtime.py -q`** and verify GREEN for R1 and R2.
- [ ] **Step 7: Commit** `feat: add exact-200 S1-R2 runtime`.

### Task 4: Add category-level analysis and preregistered R2 verdicts

**Files:**
- Modify: `src/inverted/test3_s1_analysis.py`
- Test: `tests/test_test3_s1_analysis.py`

**Interfaces:**
- Produces protocol-aware summary plus family summaries and R2 verdicts: `S1_R2_FIXED_ORDER_LARGE_SIGNAL`, `S1_R2_FIXED_ORDER_CATEGORY_CONDITIONAL_SIGNAL`, `S1_R2_FIXED_ORDER_NEGATIVE_OR_HARMFUL`, `S1_R2_SCREEN_NON_DECISIVE`, and invalid-protocol verdict.

- [ ] **Step 1: Write failing tests** for exact R2 protocol gate, aggregate thresholds, family-level thresholds, harmful threshold, tie-breaking, and non-decisive behavior.
- [ ] **Step 2: Write family-metric tests** for preservation violations, dependency/order failures, containment repairs, regressions, and new failures.
- [ ] **Step 3: Run `python -m pytest tests/test_test3_s1_analysis.py -q`** and verify RED.
- [ ] **Step 4: Implement R2 analysis while preserving R1 verdict logic**.
- [ ] **Step 5: Run `python -m pytest tests/test_test3_s1_analysis.py -q`** and verify GREEN.
- [ ] **Step 6: Commit** `feat: add S1-R2 category analysis`.

### Task 5: Wire config, CLI, evidence packet, and short progress display

**Files:**
- Modify: `configs/test3-s1.yaml`
- Modify: `src/inverted/test3_s1_cli.py`
- Modify: `src/inverted/test3_s1_artifacts.py` if needed for new category tables/fields
- Modify: `src/inverted/test3_s1_progress.py` only if required for 200-call display
- Test: `tests/test_test3_s1_cli.py`
- Test: `tests/test_test3_s1_artifacts.py`
- Test: `tests/test_test3_s1_progress.py`

**Interfaces:**
- `dry-plan` must print `PROTOCOL=S1-R2`, `HOLDOUT=A-R2`, `MATCHED_TASKS=25`, `PER_ARM_CALL_CAP=50`, `PLANNED_PHYSICAL_CALLS=200`.
- Real execution remains gated by `--authorize-tier-a`.

- [ ] **Step 1: Write failing tests** for exact R2 config, dry-plan, real preflight, mock evidence packet, category evidence, progress length ≤63 characters, and refusal to run on stale R1 config/schedule.
- [ ] **Step 2: Run focused CLI/artifact/progress tests** and verify RED.
- [ ] **Step 3: Update config and CLI** to use R2 protocol, A-R2 cases, exact-200 schedule, and evidence-resolved model identities.
- [ ] **Step 4: Extend evidence output** with family summaries, containment regression data, balanced execution-order metadata, and explicit protocol-validity fields.
- [ ] **Step 5: Run focused tests** and verify GREEN.
- [ ] **Step 6: Commit** `feat: wire S1-R2 execution and evidence`.

### Task 6: Harden CI to reject anything except the frozen R2 instrument

**Files:**
- Modify: `.github/workflows/test3-s1-validation.yml`
- Test: `tests/test_test3_s1_workflow_contract.py` if present; otherwise extend the existing workflow-contract test file.

**Interfaces:**
- GitHub mock validation must assert exactly 200 calls, 25 matched tasks, 50 calls/arm, 2 calls/arm-task, six families, zero cache, valid intervention exposure, deterministic arm ordering, and R2 evidence fields.

- [ ] **Step 1: Write/update failing workflow-contract tests** for the new R2 gate.
- [ ] **Step 2: Run the contract test and verify RED against the stale R1 workflow**.
- [ ] **Step 3: Update `test3-s1-validation.yml`** to run and verify R2 mock evidence.
- [ ] **Step 4: Run full local pytest in CI via push** and verify S1 mock validation GREEN.
- [ ] **Step 5: Commit** `ci: validate exact-200 S1-R2 instrument`.

### Task 7: Full regression and scientific readiness verification

**Files:**
- No new production files unless a discovered bug requires a TDD fix.

**Interfaces:**
- Final head SHA must pass all relevant workflows before local Tier-A execution is authorized.

- [ ] **Step 1: Run/observe full repository test matrix** on Linux Python 3.11/3.12/3.14 and Windows Python 3.14.
- [ ] **Step 2: Verify Test-2 validation** remains GREEN.
- [ ] **Step 3: Verify Test-3 S0 clean-clone scientific replay** remains GREEN.
- [ ] **Step 4: Verify S1-R2 mock validation** produces exactly 200 calls and valid evidence.
- [ ] **Step 5: Adversarially inspect prompts/evidence** for hidden metadata, schedule drift, cache use, arm-order confounding, and category metric omissions.
- [ ] **Step 6: If any defect appears, add a RED regression test first, fix minimally, and rerun every gate on the new final SHA.**
- [ ] **Step 7: Do not authorize the local Tier-A run until all gates are GREEN on one final commit.**
