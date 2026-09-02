# Black-Magic Test 5 Formulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Test 5 as a 2,700-external-action architecture-formulation experiment that uses only Forge-approved evidence to discover, compress, repair, and sealed-holdout validate the best INVERTED architecture.

**Architecture:** Test 5 compares DIRECT, CHECKED, CURRENT_INVERTED, and evidence-formulated challengers. Challenger factors are declarative and hashable; adaptive allocation is preregistered and may use only training/diagnostic data, never sealed-holdout truth. Every material negative result is localized and converted through targeted/sham replay before finalization.

**Tech Stack:** Python 3.11+, existing adapters, black-magic budget/evidence/counterfactual/interaction primitives, pytest, deterministic JSON/JSONL/SHA-256.

**Spec:** `docs/superpowers/specs/2026-09-01-black-magic-evidence-and-certification-design.md`

## Global Constraints

- Base SHA `19b45314860f2feb7bb561353220eef8d83ba657` remains immutable.
- Test-5 hard ceiling: 2,700 total external actions.
- Architecture factors not justified by Forge evidence cannot enter the search space.
- Hidden holdout truth cannot influence challenger selection or adaptive allocation.
- Final architecture is frozen and hashed before sealed holdout begins.
- Test-5 acceptance floor from the spec is mandatory; no partial PASS.

---

### Task 1: Freeze architecture-manifest and Test-5 contracts with RED tests

**Files:**
- Create: `tests/test_black_magic_architecture.py`
- Create: `tests/test_black_magic_test5_budget.py`
- Create: `tests/test_black_magic_test5_holdout.py`
- Create: `tests/test_black_magic_test5_acceptance.py`

**Interfaces:**
- Expected imports: `ArchitectureManifest`, `build_challengers`, `freeze_architecture`, `run_test5`, `evaluate_test5_floor`.

- [ ] Add RED tests proving architecture manifests are deterministic/hashable and reject factors absent from Forge evidence.
- [ ] Add RED tests proving a 2,701-action plan refuses before first call.
- [ ] Add RED tests proving holdout IDs/truth cannot be read by challenger-selection code and architecture mutation is forbidden after freeze.
- [ ] Add RED tests for every acceptance-floor clause: >=90% correctness, >=95% safe disposition, zero unauthorized catastrophic actions, verified correction-or-safe-containment for detected correctable failures, no high-severity regression, per-model superiority, efficiency, minimality, and integrity.
- [ ] Commit RED tests with message `test: define Test 5 formulation contracts`.

### Task 2: Implement declarative architecture manifests

**Files:**
- Create: `src/inverted/black_magic/architecture.py`
- Test: `tests/test_black_magic_architecture.py`

**Interfaces:**
- `ArchitectureManifest(architecture_id, factors, source_findings, parent_id=None)`.
- `validate_manifest_against_forge(manifest, forge_artifacts) -> dict`.
- `freeze_architecture(manifest) -> dict` with SHA-256.

- [ ] Implement factor schema for decomposition topology/depth, ternary disposition, global-state summary, evidence/provenance/contradiction/authority/preservation gates, rationale/confidence visibility, proposer-verifier representation, veto semantics, ordering, recovery, verification-before-execution, and adaptive decomposition.
- [ ] Require every non-baseline factor value to cite one or more promoted Forge finding IDs.
- [ ] Implement deterministic manifest serialization/hash and immutable frozen marker.
- [ ] Run architecture tests GREEN.
- [ ] Commit with message `feat: add evidence-grounded architecture manifests`.

### Task 3: Build fresh Test-5 case matrix and fixed anchor arms

**Files:**
- Create: `src/inverted/black_magic/test5_cases.py`
- Create: `tests/test_black_magic_test5_cases.py`

**Interfaces:**
- `generate_test5_cases(seed, family_counts) -> dict[str, list[dict]]` returning train/diagnostic/holdout partitions.
- Case families span mechanics, epistemics, action, and evidence-supported interactions.

- [ ] Add RED tests proving no case IDs overlap between adaptive and holdout partitions.
- [ ] Add RED tests for matched DIRECT/CHECKED/CURRENT_INVERTED public inputs and hidden deterministic scoring.
- [ ] Implement fresh families with paired decision boundaries and interaction cases derived from Forge findings, not copied prior-run cases.
- [ ] Hash-commit the sealed holdout partition before any adaptive Test-5 call.
- [ ] Run case tests GREEN.
- [ ] Commit with message `feat: add sealed Test 5 case partitions`.

### Task 4: Implement challenger generation and preregistered adaptive allocation

**Files:**
- Create: `src/inverted/black_magic/formulation.py`
- Create: `tests/test_black_magic_formulation.py`

**Interfaces:**
- `build_challengers(forge_artifacts, baseline_manifest, max_candidates) -> list[ArchitectureManifest]`.
- `allocate_next_batch(history, candidates, remaining_budget, policy) -> list[dict]`.

- [ ] Add RED tests where FIX/REMOVE/ADD instructions produce specific candidate manifests and rejected Forge signals cannot appear.
- [ ] Add RED tests proving weak challengers can be eliminated early while a minimum paired evidence quota prevents premature elimination from one noisy case.
- [ ] Implement deterministic candidate generation from repair library + interaction graph: single repairs, evidence-supported combinations, and minimal alternative topologies.
- [ ] Implement allocation using only observed adaptive-set outcomes, severity, disagreement information, and preregistered thresholds; never use sealed holdout labels.
- [ ] Run formulation tests GREEN.
- [ ] Commit with message `feat: formulate evidence-grounded challengers`.

### Task 5: Implement architecture execution and externally verified self-correction

**Files:**
- Create: `src/inverted/black_magic/test5_runtime.py`
- Create: `tests/test_black_magic_test5_runtime.py`

**Interfaces:**
- `execute_architecture(manifest, model, case, ...) -> dict`.
- `attempt_verified_correction(failure, manifest, model, verifier) -> dict`.

- [ ] Add RED tests for binary versus ternary gates, compact global state, proposer/verifier role framing, verification-before-execution, and deterministic safety authority.
- [ ] Add RED tests where a model proposes a valid correction that the system verifies and applies, an invalid correction that is rejected, and a detected correctable error that safely abstains/escalates when verification cannot succeed.
- [ ] Ensure the model never self-certifies a repair by confidence/rationale assertion alone.
- [ ] Implement one bounded correction attempt per detected correctable event unless a Forge finding explicitly justifies another bounded policy; every physical attempt consumes budget.
- [ ] Run runtime tests GREEN.
- [ ] Commit with message `feat: execute and verify Test 5 architectures`.

### Task 6: Implement causal negative-result conversion during formulation

**Files:**
- Create: `src/inverted/black_magic/test5_repairs.py`
- Create: `tests/test_black_magic_test5_repairs.py`

**Interfaces:**
- `convert_failure(failure, manifest, forge_artifacts, ...) -> dict`.

- [ ] Add RED tests requiring first divergence, error lifecycle, targeted repair, sham control, replay, neighboring validation, and regression result before `CONVERTED`.
- [ ] Add RED tests for `COMBINED` multi-factor failures and blocking `UNRESOLVED` severe failures.
- [ ] Implement repair proposals only from permitted Forge evidence and observed Test-5 adaptive evidence.
- [ ] Feed verified converted repairs back into challenger generation with lineage links.
- [ ] Run repair tests GREEN.
- [ ] Commit with message `feat: convert Test 5 failures into challengers`.

### Task 7: Implement interaction search and architecture compression

**Files:**
- Create: `src/inverted/black_magic/test5_search.py`
- Create: `tests/test_black_magic_test5_search.py`

**Interfaces:**
- `evaluate_component_value(...) -> dict`.
- `evaluate_interaction_value(...) -> dict`.
- `compress_architecture(leader, evaluation_history) -> ArchitectureManifest`.

- [ ] Add RED tests distinguishing positive synergy, redundancy, antagonism, and conditional necessity.
- [ ] Add RED tests where removing a zero-value component preserves performance and where removing a safety-critical invariant component invalidates the architecture.
- [ ] Implement evidence-directed covering combinations rather than exhaustive search.
- [ ] Perform one-at-a-time and evidence-supported grouped ablations against the current leader.
- [ ] Require every surviving component to have measured causal value or documented hard-invariant enforcement.
- [ ] Run search tests GREEN.
- [ ] Commit with message `feat: search and compress Test 5 architecture`.

### Task 8: Implement sealed holdout and absolute floor evaluator

**Files:**
- Create: `src/inverted/black_magic/test5_formulation.py`
- Test: `tests/test_black_magic_test5_holdout.py`
- Test: `tests/test_black_magic_test5_acceptance.py`

**Interfaces:**
- `run_test5(...) -> dict`.
- `evaluate_test5_floor(results, architecture_manifest) -> dict`.

- [ ] Implement phases 5A anchor, 5B attribution, 5C interaction formulation, 5D negative conversion, 5E compression, 5F sealed holdout.
- [ ] Freeze/hash FINAL_INVERTED before phase 5F and reject any later mutation.
- [ ] Compare DIRECT, CHECKED, CURRENT_INVERTED, and FINAL_INVERTED on identical holdout cases/models/public inputs.
- [ ] Compute per-model and per-family correctness/safe-disposition deltas, catastrophic actions, correction outcomes, regression map, actions/tokens/latency per correctly completed task, and Pareto status.
- [ ] Enforce the spec's ten acceptance conditions exactly; one failure yields non-PASS verdict with explicit blocking reasons.
- [ ] Run all Test-5 tests GREEN.
- [ ] Commit with message `feat: add Test 5 black-magic formulation`.

### Task 9: Add Test-5 configs, CLI, evidence artifacts, and CI

**Files:**
- Create: `configs/black-magic-test5-smoke.yaml`
- Create: `configs/black-magic-test5-local.yaml`
- Create: `.github/workflows/black-magic-test5-validation.yml`
- Create: `tests/test_black_magic_test5_cli.py`

**Interfaces:**
- CLI stage `test5` through `python -m inverted.black_magic.cli ...`.

- [ ] Add mock smoke config that validates all phases with small deterministic budgets and labels outputs instrument validation.
- [ ] Add local real config with hard cap 2,700 and no retries.
- [ ] Emit required artifacts: `final_architecture.json`, `architecture_lineage.jsonl`, `component_value.json`, `interaction_value.json`, `repairs.jsonl`, `sealed_holdout_results.json`, `residual_failure_map.json`, `test5_verdict.json`, complete evidence/integrity/hash files.
- [ ] Add additive CI that runs Test-5 unit/instrument tests and proves sealed-holdout freeze behavior.
- [ ] Compare branch to base SHA and require additions only.
- [ ] Commit with message `ci: validate Test 5 formulation instrument`.

### Task 10: Test-5 completion gate

**Files:** none.

**Interfaces:** Produces frozen `final_architecture.json` as Test-6 input only after a real Test-5 PASS.

- [ ] Run full repository pytest suite on exact final Test-5 implementation SHA.
- [ ] Run Test-5 mock smoke and verify instrument integrity; do not claim architecture evidence.
- [ ] Verify real Test-5 runner precomputes/refuses plans above 2,700 actions.
- [ ] Verify no hidden holdout access before phase 5F and no architecture mutation after freeze.
- [ ] Verify all existing base-SHA paths are byte-identical.
- [ ] Do not enable a real Test-6 run until a real Test-5 campaign has passed and its final architecture hash is frozen.
