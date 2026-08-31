# Test 2 Compounding Causal Atlas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a parallel Test-2 harness that isolates component causality, compounding order, failure removal, model specialization, routing value, and next-stride bottlenecks while enforcing a hard 480-local-call ceiling and exporting complete forensic evidence.

**Architecture:** Keep Test-1 modules unchanged. Add focused Test-2 modules for experiment types, call budgeting/caching, task/representation probes, causal analysis, artifact export, and a separate CLI. GitHub Actions runs model-free validation; local Ollama runs the bounded five-model campaign.

**Tech Stack:** Python 3.11+, stdlib, existing `httpx`/`PyYAML`, pytest, existing `inverted` task/oracle/model primitives.

**Spec:** `docs/superpowers/specs/2026-08-31-test2-compounding-causal-atlas-design.md`

## Global Constraints

- Do not change Test-1 arm semantics.
- Local physical model-call hard ceiling is exactly 480.
- Five configured local models are fixed by the spec.
- Preserve exact prompts/responses in raw evidence.
- No early scientific stopping.
- Cached reuse only for byte-equivalent call identity inputs.
- GitHub/model-free runs require no Ollama or paid inference.

---

### Task 1: Core Test-2 data contracts, call budget, and deterministic call identity

**Files:**
- Create: `src/inverted/test2_types.py`
- Create: `tests/test_test2_budget.py`

**Interfaces:**
- Produces: `PhysicalCallBudget`, `CallIdentity`, `OutcomeTransition`, `ComponentObservation`, `Test2CallRecord`.

- [ ] Write tests proving the 481st physical call is refused, cache hits do not consume budget, and call identity changes if model/messages/role/settings change.
- [ ] Run focused pytest and verify RED because Test-2 types do not exist.
- [ ] Implement minimal deterministic dataclasses and SHA256 call identity.
- [ ] Run focused pytest and verify GREEN.

### Task 2: Test-2 task/probe construction and fixed candidate bank

**Files:**
- Create: `src/inverted/test2_cases.py`
- Create: `tests/test_test2_cases.py`

**Interfaces:**
- Consumes: `generate_task`, `generate_candidate`, `evaluate_task`.
- Produces: deterministic formalization cases, 12 execution cells, 20 fixed audit candidates, 10 repair candidates, untouched holdout cells.

- [ ] Write tests for exact cardinalities, deterministic IDs/seeds, family/complexity coverage, and valid/invalid audit balance.
- [ ] Verify RED.
- [ ] Implement case builders without changing existing task generation.
- [ ] Verify GREEN.

### Task 3: Causal outcome transitions and failure kill-chain analysis

**Files:**
- Create: `src/inverted/test2_analysis.py`
- Create: `tests/test_test2_analysis.py`

**Interfaces:**
- Produces: `classify_transition`, `component_effects`, `failure_kill_matrix`, `pairwise_synergy`, `minimum_sufficient_stack`, `pareto_frontier`, `router_regret`, `model_complementarity`, `residual_bottlenecks`.

- [ ] Write matched-case tests distinguishing recovery from blocking/displacement/regression.
- [ ] Write tests for conditional/progressive/ablation effects and minimum-sufficient-stack thresholds.
- [ ] Write tests for router regret and model unique-win/complementarity accounting.
- [ ] Verify RED.
- [ ] Implement pure analysis functions.
- [ ] Verify GREEN.

### Task 4: Deterministic progressive/ablation/order simulator

**Files:**
- Create: `src/inverted/test2_simulation.py`
- Create: `tests/test_test2_simulation.py`

**Interfaces:**
- Produces: deterministic component pipeline evaluation and model-free factorial/order atlas.

- [ ] Write tests proving standalone, progressive, ablation, order, and saturation outputs are paired on the same cases.
- [ ] Write a test that any replay order changing an upstream model prompt is marked `REQUIRES_NEW_INFERENCE`.
- [ ] Verify RED.
- [ ] Implement deterministic simulator over synthetic/fixed candidates.
- [ ] Verify GREEN.

### Task 5: Bounded local model phases with exact prompt/response capture

**Files:**
- Create: `src/inverted/test2_local.py`
- Create: `tests/test_test2_local.py`

**Interfaces:**
- Consumes: existing model adapters and Test-2 cases.
- Produces: formalizer, executor, auditor, atomic-audit, repair-factorial, progressive holdout, and stability records.

- [ ] Write tests using `MockModelAdapter` proving phase maximums sum to 480 and runner refuses over-budget physical calls.
- [ ] Write tests proving identical calls are cached and changed upstream context is not reused.
- [ ] Write tests proving exact request/response text is retained.
- [ ] Verify RED.
- [ ] Implement phases and runtime budget enforcement.
- [ ] Verify GREEN.

### Task 6: Model specialization and layered routing derivation

**Files:**
- Modify: `src/inverted/test2_analysis.py`
- Create: `tests/test_test2_routing.py`

**Interfaces:**
- Produces role champions, task/family/fault/complexity/representation matrices, best-single/static-role/task-router/oracle ceilings, routing regret, stability labels.

- [ ] Write tests on synthetic model outcomes where the globally best model is not the best specialized router.
- [ ] Verify RED.
- [ ] Implement router derivation and model-pair complementarity.
- [ ] Verify GREEN.

### Task 7: Complete forensic artifact writer and master evidence stream

**Files:**
- Create: `src/inverted/test2_artifacts.py`
- Create: `tests/test_test2_artifacts.py`

**Interfaces:**
- Produces the exact directory contract in the spec plus deterministic `TEST2-COMPLETE-EVIDENCE.txt`, `TEST2-NEXT-STRIDE-REPORT.txt`, and `SHA256SUMS.csv`.

- [ ] Write tests for required file set and master evidence inclusion of every text/CSV/JSON/JSONL artifact.
- [ ] Write test for deterministic ordering and hashes.
- [ ] Verify RED.
- [ ] Implement writer and next-stride report generation.
- [ ] Verify GREEN.

### Task 8: Separate Test-2 CLI and local/GitHub configs

**Files:**
- Create: `src/inverted/test2_cli.py`
- Create: `configs/test2-model-free.yaml`
- Create: `configs/test2-local.yaml`
- Create: `tests/test_test2_cli.py`

**Interfaces:**
- Commands: `python -m inverted.test2_cli model-free ...` and `python -m inverted.test2_cli local ...`.

- [ ] Write CLI tests for model-free smoke, local dry-plan, exact model list, and 480-call hard ceiling.
- [ ] Verify RED.
- [ ] Implement minimal CLI/config loading.
- [ ] Verify GREEN.

### Task 9: GitHub Actions Test-2 validation

**Files:**
- Create: `.github/workflows/test2-validation.yml`
- Create: `tests/test_test2_workflow_contract.py`

**Interfaces:**
- Produces a GitHub artifact containing model-free Test-2 validation evidence.

- [ ] Write workflow-contract test asserting no Ollama/local-model dependency and required model-free commands/artifact upload.
- [ ] Verify RED.
- [ ] Add workflow that runs pytest, Test-2 model-free validation, evidence completeness checks, and uploads artifacts.
- [ ] Verify GREEN via GitHub Actions.

### Task 10: Regression and completion verification

**Files:**
- No production changes unless verification reveals defects.

- [ ] Run full pytest matrix through GitHub Actions.
- [ ] Run Test-2 model-free workflow and inspect artifact/report completeness.
- [ ] Compare Test-1 source modules against `main` and verify no semantic changes.
- [ ] Confirm local dry-plan reports ≤480 physical calls and exact five models.
- [ ] Open a PR from `build/test2-compounding-causal-atlas` to `main` with evidence and run instructions.
