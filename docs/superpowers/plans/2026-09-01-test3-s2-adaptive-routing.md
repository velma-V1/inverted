# Test-3 S2 Adaptive Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fresh 72-case, five-arm, exact-720-call adaptive-routing experiment that tests whether verified evidence-state routing beats fixed and random routing while preserving complete forensic evidence.

**Architecture:** Reuse S1-R3's public prompt boundary, deterministic verification, targeted patch composition, model adapters, and telemetry primitives. Add S2-specific holdout/fault fixtures, routing policy layer, two-step runtime, analysis/verdict, artifact writer, CLI/config, progress adapter, and CI validation. The analysis-only oracle is derived only from observed S2 trajectories and consumes no inference.

**Tech Stack:** Python 3.11–3.14, pytest, PyYAML, existing Ollama/Mock adapters, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-01-test3-s2-adaptive-routing-design.md`

## Global Constraints

- Branch: `build/test3-s2-adaptive-routing`; do not modify `main`.
- Fresh Holdout B: exactly 72 cases = 6 families × 4 complexity levels × 3 perturbations.
- Five real arms: S2-B0..S2-B4; analysis-only S2-ORACLE.
- Exactly 2 physical model calls per real arm-task; exact planned calls = 720.
- Combined external/AI action budget is 720 for S2 and must never exceed repository ceiling 1000.
- Model adapters use zero retries and no cache.
- Hidden-gold/target/fault-construction metadata is forbidden from production routers and prompts.
- All mutations are revalidated.
- Progress display follows `TESTING.md`, including split-screen auto-fit, percent, calls, elapsed, left, ETA, arm/phase.
- No Tier-A inference during development or CI.

---

### Task 1: Freeze S2 holdout, perturbations, policy contracts, and budget

**Files:**
- Create: `src/inverted/test3_s2_cases.py`
- Create: `src/inverted/test3_s2_policy.py`
- Create: `src/inverted/test3_s2_budget.py`
- Test: `tests/test_test3_s2_contract.py`
- Test: `tests/test_test3_s2_cases.py`
- Test: `tests/test_test3_s2_policy.py`

**Interfaces:**
- `build_holdout_b() -> list[ExecutionCase]`
- `build_seed_failure_s2(case: ExecutionCase) -> Candidate`
- `failure_state(task, candidate, deterministic_result, ...) -> dict[str, Any]`
- `select_action(arm_id, evidence_state, step_index, random_seed) -> str`
- `CombinedActionBudget(limit: int)` with `reserve(kind: str, count: int = 1)` and `snapshot()`.

- [ ] Write failing tests proving 72 fresh cases, exact 6×4×3 balance, causal-twin grouping, all seed candidates fail, forbidden construction labels are absent from public evidence, B1/B2/B3 feature boundaries differ, B4 is deterministic seeded random, and budget 721st reservation fails closed.
- [ ] Run the new tests and confirm RED.
- [ ] Implement the minimum holdout/fault/policy/budget code to satisfy the contract.
- [ ] Run the new tests and confirm GREEN.
- [ ] Commit.

### Task 2: Implement exact-720 two-step runtime with shadow calls and stochastic-divergence capture

**Files:**
- Create: `src/inverted/test3_s2_runtime.py`
- Test: `tests/test_test3_s2_runtime.py`
- Test: `tests/test_test3_s2_stochastic_divergence.py`

**Interfaces:**
- `run_s2_screen(cases, arms, model_by_name, run_id, exact_budget=720) -> dict[str, Any]`
- `prompt_fingerprint(...) -> str`
- `detect_stochastic_divergence(model_calls) -> list[dict[str, Any]]`

- [ ] Write failing tests for exactly 720 mock calls, 144 calls/arm, 72 trials/arm, two calls/trial, active→shadow terminal behavior, B3 second decision after revalidation, identical intervention library for all arms, no cache/retry leakage, public prompt fail-closed scanning, call fingerprints, and same-fingerprint/different-response divergence detection.
- [ ] Confirm RED.
- [ ] Implement runtime by reusing S1-R3 executor, repair composition, deterministic validator, and call-row primitives; add llama model-switch path and policy selection.
- [ ] Confirm targeted tests GREEN.
- [ ] Commit.

### Task 3: Implement S2 analysis, observed oracle, attribution, and frozen verdict

**Files:**
- Create: `src/inverted/test3_s2_analysis.py`
- Test: `tests/test_test3_s2_analysis.py`

**Interfaces:**
- `summarize_s2(runtime: dict[str, Any]) -> dict[str, Any]`
- `derive_s2_verdict(summary: dict[str, Any]) -> dict[str, Any]`

- [ ] Write failing tests for paired effects, family/perturbation/complexity strata, transition matrix, observed oracle using only observed outcomes, regret, B2-vs-B1 incremental signal, stochastic-divergence exclusion sensitivity, protocol precedence, signal/harmful/non-decisive thresholds.
- [ ] Confirm RED.
- [ ] Implement analysis and frozen verdict contract exactly as specified.
- [ ] Confirm GREEN.
- [ ] Commit.

### Task 4: Build complete S2 forensic artifact packet

**Files:**
- Create: `src/inverted/test3_s2_artifacts.py`
- Test: `tests/test_test3_s2_artifacts.py`

**Interfaces:**
- `Test3S2ArtifactWriter(run_dir).write_all(evidence) -> dict[str, str]`

- [ ] Write failing test requiring every standard and S2-specific artifact, master-index counts, complete-evidence concatenation, and SHA256 inventory verification.
- [ ] Confirm RED.
- [ ] Implement writer with required JSON/JSONL/CSV outputs, derived telemetry tables, routing state, budget tables, stochastic divergence, oracle regret, and hashes.
- [ ] Confirm GREEN.
- [ ] Commit.

### Task 5: Add S2 CLI/config/progress and dry-plan

**Files:**
- Create: `configs/test3-s2.yaml`
- Create: `src/inverted/test3_s2_progress.py`
- Create: `src/inverted/test3_s2_cli.py`
- Test: `tests/test_test3_s2_cli.py`
- Test: `tests/test_test3_s2_progress.py`

**Interfaces:**
- `python -m inverted.test3_s2_cli dry-plan --config configs/test3-s2.yaml`
- `python -m inverted.test3_s2_cli mock-run --config configs/test3-s2.yaml --output-dir ...`
- `python -m inverted.test3_s2_cli run --config configs/test3-s2.yaml --output-dir ... --run-id ... --authorize-tier-a`

- [ ] Write failing CLI tests asserting protocol `S2-R1`, holdout `B-R1`, exact 720 budget, 72 cases, 5 arms, 2 calls/trial, three frozen models, combined action budget 720, no Tier-A without explicit flag, and complete mock evidence.
- [ ] Write failing progress tests at 72-column split-screen width requiring bar, percent, done/total, calls/720, arm/phase, elapsed, left, ETA, in-place update, one final newline.
- [ ] Confirm RED.
- [ ] Implement config validation, adapters/provenance, dry-plan, mock-run, Tier-A run gate, evidence assembly, and split-screen progress wrapper.
- [ ] Confirm GREEN.
- [ ] Commit.

### Task 6: Add CI contract and verify repository-wide GREEN

**Files:**
- Create: `.github/workflows/test3-s2-validation.yml`
- Create: `tests/test_test3_s2_workflow_contract.py`
- Modify only if required: `TESTING.md` (no semantic weakening permitted).

- [ ] Write failing workflow-contract test requiring Python 3.14, full pytest, S2 mock exact-720 run, artifact contract verification, and upload.
- [ ] Confirm RED.
- [ ] Add workflow.
- [ ] Run/observe S2 validation and general repository workflows on the same final SHA.
- [ ] Verify branch head did not move during final checks.
- [ ] Do not authorize or trigger Tier-A inference.
- [ ] Commit final verification-only changes if needed.
