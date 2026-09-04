# Black-Magic Harvest Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the additive black-magic runtime foundation plus three high-information harvest experiments that convert decision, evidence, and action failures into causal repair data without modifying the completed assistant-value suite.

**Architecture:** All runtime code lives in a new `src/inverted/black_magic/` package. The package may import frozen public helpers from `inverted.assistant_value` but never edits or monkey-patches them. Each harvest owns fresh deterministic cases, hidden deterministic scoring, fork/replay, sham controls, metamorphic probes where relevant, and a strict 1,200 external-action ceiling.

**Tech Stack:** Python 3.11+, existing model adapter interface, pytest, JSON/JSONL/CSV, SHA-256, deterministic random seeds.

**Spec:** `docs/superpowers/specs/2026-09-01-black-magic-evidence-and-certification-design.md`

## Global Constraints

- Base SHA `035c2190403c506330b6b54fa244ce35a62f26bf` is immutable.
- Every path existing at the base SHA is read-only; implementation is additive only.
- Hidden oracle data may score only after a public decision artifact exists.
- No adapter-internal retries.
- One external-action reservation equals one physical model/API/tool attempt.
- Harvest ceilings: 1,200 external actions each.
- Mock runs validate instrumentation only, never architecture claims.
- High-severity `UNRESOLVED` findings block later Test-5 formulation.

---

### Task 1: Freeze additive contracts with RED tests

**Files:**
- Create: `tests/test_black_magic_budget.py`
- Create: `tests/test_black_magic_evidence.py`
- Create: `tests/test_black_magic_counterfactual.py`
- Create: `tests/test_black_magic_metamorphic.py`
- Create: `tests/test_black_magic_interactions.py`

**Interfaces:**
- Produces expected imports for `ExternalActionBudget`, `BlackMagicEvidenceStore`, `fork_and_replay`, `evaluate_metamorphic_pair`, and coverage helpers.

- [ ] Write failing tests asserting: exact 1,200 harvest caps; cap+1 refusal before invocation; one reservation per physical attempt; additive evidence packet creation; deterministic stable IDs; targeted replay versus sham replay separation; invariant/boundary metamorphic scoring; and 2-way/3-way/ordered coverage verification.
- [ ] Push the RED tests and verify failure is due to missing `inverted.black_magic` modules, not syntax or fixture errors.
- [ ] Commit with message `test: define black-magic harvest contracts`.

### Task 2: Add shared types and unified external-action budget

**Files:**
- Create: `src/inverted/black_magic/__init__.py`
- Create: `src/inverted/black_magic/types.py`
- Create: `src/inverted/black_magic/budget.py`

**Interfaces:**
- `ExternalActionBudget(name: str, cap: int)` with `reserve(kind: str, metadata: dict | None = None)`, `used`, `remaining`, `to_dict()`.
- `ExternalActionBudgetExceeded` exception.
- Stable dataclasses/dicts for `Finding`, `InterventionRecord`, `ErrorLifecycleRecord`, `ArchitectureInstruction`.

- [ ] Run `pytest tests/test_black_magic_budget.py -q` and confirm RED.
- [ ] Implement immutable caps/constants, stable hash/ID helpers, and fail-closed `reserve` semantics.
- [ ] Re-run the budget tests and confirm GREEN.
- [ ] Commit with message `feat: add black-magic budget and types`.

### Task 3: Add lossless evidence packet store and model I/O wrapper

**Files:**
- Create: `src/inverted/black_magic/evidence.py`
- Create: `src/inverted/black_magic/model_io.py`
- Create: `tests/test_black_magic_model_io.py`

**Interfaces:**
- `BlackMagicEvidenceStore(root, experiment_name, run_id)` append/finalize API.
- `invoke_json_external(...)` reserves exactly once, captures prompt/response/error/latency/token telemetry when exposed, and writes chronological events.

- [ ] Write RED tests for required ledgers: tasks, states, calls, prompts, responses, decisions, actions, tool results, oracle results, transitions, interventions, shams, error lifecycle, metamorphic pairs, coverage, anomalies.
- [ ] Write RED tests proving failed/timeout responses still consume one external action and create call/prompt/response rows.
- [ ] Implement append-only JSONL, deterministic JSON/CSV finalization, integrity checks, `COMPLETE-EVIDENCE.txt`, and `SHA256SUMS.csv` without recursive stale hashes.
- [ ] Run `pytest tests/test_black_magic_evidence.py tests/test_black_magic_model_io.py -q` and confirm GREEN.
- [ ] Commit with message `feat: add black-magic evidence capture`.

### Task 4: Implement causal fork/replay and sham controls

**Files:**
- Create: `src/inverted/black_magic/counterfactual.py`
- Test: `tests/test_black_magic_counterfactual.py`

**Interfaces:**
- `capture_fork_state(case, state, decision_index) -> dict`.
- `apply_intervention(fork_state, intervention) -> dict`.
- `fork_and_replay(..., targeted_intervention, sham_intervention, scorer) -> dict`.
- Output includes original, targeted, sham outcomes and `causal_lift`.

- [ ] Add RED tests where a targeted intervention flips failure to success while an irrelevant sham does not.
- [ ] Add RED tests where both targeted and sham flip, forcing the result to be marked `AMBIGUOUS` rather than causal.
- [ ] Implement deterministic deep-copy fork state, intervention manifests, replay lineage, and causal classification.
- [ ] Run the counterfactual tests GREEN.
- [ ] Commit with message `feat: add verified counterfactual replay`.

### Task 5: Implement metamorphic and interaction coverage primitives

**Files:**
- Create: `src/inverted/black_magic/metamorphic.py`
- Create: `src/inverted/black_magic/interactions.py`
- Test: `tests/test_black_magic_metamorphic.py`
- Test: `tests/test_black_magic_interactions.py`

**Interfaces:**
- `evaluate_metamorphic_pair(base_result, transformed_result, relation) -> dict`.
- `generate_pairwise_covering_rows(factors: dict[str, list]) -> list[dict]`.
- `verify_t_way_coverage(rows, factors, strength) -> dict`.
- `verify_ordered_sequence_coverage(sequences, required_relations) -> dict`.

- [ ] Add RED tests for evidence-order permutation, identifier renaming, irrelevant-note insertion, and one decisive-fact boundary flip.
- [ ] Add RED tests proving pairwise coverage is complete and ordered precedence requirements are verified before execution.
- [ ] Implement deterministic transformations and coverage verification; keep 4–6-way generation targeted to explicitly supplied factor subsets rather than brute force.
- [ ] Run metamorphic/interaction tests GREEN.
- [ ] Commit with message `feat: add metamorphic and interaction probes`.

### Task 6: Build Decision Mechanics Harvest

**Files:**
- Create: `src/inverted/black_magic/decision_harvest.py`
- Create: `tests/test_black_magic_decision_harvest.py`

**Interfaces:**
- `generate_decision_harvest_cases(seed: int, case_count: int) -> list[dict]`.
- `planned_decision_harvest_actions(model_count: int, case_count: int, arm_count: int, replay_budget: int) -> int`.
- `run_decision_harvest(...) -> (trials, metrics, findings)`.

- [ ] Add RED tests for fresh dependency graphs, locally-correct/globally-wrong traps, over/under-decomposition, stale state, requirement change, checkpoint recovery, and auditor false-accept/false-reject.
- [ ] Add RED tests for first meaningful divergence, first unrecovered divergence, propagation depth, recovery opportunity, correction-role effect, targeted/sham repair lift, and generalization/regression fields.
- [ ] Implement fresh case generation and paired DIRECT/CHECKED/INVERTED-style decision roles without importing hidden oracle labels into prompts or deterministic candidate construction.
- [ ] Add externalized-correction probes using byte-identical error payloads wrapped as own prior output, external candidate, tool/state report, and memory-style record.
- [ ] Reserve replay calls adaptively only for disagreements/failures under a preregistered rule and prove worst-case actions stay <=1,200.
- [ ] Run `pytest tests/test_black_magic_decision_harvest.py -q` GREEN.
- [ ] Commit with message `feat: add decision mechanics harvest`.

### Task 7: Build Epistemic Mechanics Harvest

**Files:**
- Create: `src/inverted/black_magic/epistemic_harvest.py`
- Create: `tests/test_black_magic_epistemic_harvest.py`

**Interfaces:**
- `generate_epistemic_harvest_cases(seed: int, case_count: int) -> list[dict]`.
- `planned_epistemic_harvest_actions(...) -> int`.
- `run_epistemic_harvest(...) -> (trials, metrics, findings)`.

- [ ] Add RED tests for complete/partial/irrelevant/stale/contradictory/adversarial evidence, forged authority, source ambiguity, majority-wrong evidence, no-valid-action, and required `INSUFFICIENT` cases.
- [ ] Add RED tests for evidence surgery: remove/restore one item, freshness-only, provenance-only, reordering, ID renaming, distractor insertion, rationale removal, confidence removal, contradiction resolve/create.
- [ ] Implement invariant and boundary metamorphic pairs and record minimal sufficient evidence, unnecessary load, marginal signal value, contradiction value, provenance/freshness interaction, abstention boundary accuracy, and exploitability.
- [ ] Add targeted/sham replay for high-information wrong judgments and verify the 1,200-action ceiling before first call.
- [ ] Run `pytest tests/test_black_magic_epistemic_harvest.py -q` GREEN.
- [ ] Commit with message `feat: add epistemic mechanics harvest`.

### Task 8: Build Action Mechanics Harvest

**Files:**
- Create: `src/inverted/black_magic/action_harvest.py`
- Create: `tests/test_black_magic_action_harvest.py`

**Interfaces:**
- `generate_action_harvest_cases(seed: int, case_count: int) -> list[dict]`.
- `planned_action_harvest_actions(...) -> int`.
- `run_action_harvest(...) -> (trials, metrics, findings)`.

- [ ] Add RED tests for simulated read/write/delete/send/publish/purchase/configure/credential effects with explicit/ambiguous/revoked authority, scope mismatch, least privilege, irreversible actions, chained risk, delayed effects, false success, overblocking, and mid-sequence permission changes.
- [ ] Add RED tests separating `understanding_correct` from `action_correct`, plus authority error, scope error, escalation, least privilege, action-order dependence, preventable damage, and repair lift.
- [ ] Implement action surgery on authority, scope, reversibility, approval tier, ordering, prerequisites, alternatives, consequence estimate, and verification-before-execution state.
- [ ] Require sham controls for promoted causal repair findings and reject plans above 1,200 actions.
- [ ] Run `pytest tests/test_black_magic_action_harvest.py -q` GREEN.
- [ ] Commit with message `feat: add action mechanics harvest`.

### Task 9: Add harvest runner, configs, CLI, and additive CI

**Files:**
- Create: `src/inverted/black_magic/runner.py`
- Create: `src/inverted/black_magic/cli.py`
- Create: `configs/black-magic-smoke.yaml`
- Create: `configs/black-magic-harvest-local.yaml`
- Create: `.github/workflows/black-magic-validation.yml`
- Create: `tests/test_black_magic_runner.py`

**Interfaces:**
- CLI: `python -m inverted.black_magic.cli --config <path> --stage decision_harvest|epistemic_harvest|action_harvest|harvest_all --output-dir <dir> --run-id <id>`.

- [ ] Add RED tests for config parsing, exact stage dispatch, full content capture, retry rejection, pre-run ceiling refusal, and three complete smoke evidence packets.
- [ ] Implement mock-only smoke configs and local real-model config with environment model names; mock provenance must say instrument validation.
- [ ] Add a new workflow that runs the full repository pytest suite plus black-magic smoke validation and artifact integrity checks without modifying existing workflows.
- [ ] Verify all new tests GREEN and the additive workflow succeeds.
- [ ] Compare base SHA to branch and require all changed paths status `added`.
- [ ] Commit with message `ci: validate black-magic harvest instruments`.

### Task 10: Harvest completion gate

**Files:** none.

**Interfaces:** Produces validated inputs for the Evidence Forge plan.

- [ ] Run all pytest tests on the final harvest SHA.
- [ ] Run all three mock harvests and verify complete evidence integrity, targeted/sham discrimination, metamorphic manifests, and coverage manifests.
- [ ] Verify no existing base-SHA path changed.
- [ ] Verify each real harvest config refuses >1,200 planned external actions.
- [ ] Verify hidden-gold tests prove public decision construction cannot access oracle labels.
- [ ] Record the exact final SHA before beginning the Evidence Forge implementation.
