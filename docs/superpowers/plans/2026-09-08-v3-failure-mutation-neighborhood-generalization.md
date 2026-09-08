# V3 Failure Mutation and Neighborhood Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a locally repaired V3 failure into deterministic nearby replay fixtures, measure whether the same causal repair survives those neighbors, and promote only genuinely generalized mechanisms from `MOVEMENT` to `TIER_CANDIDATE` while preserving exact replay lineage and zero-call development validation.

**Architecture:** Extend the existing replay kernel rather than adding a second execution path. Stage 6 introduces a canonical `MUTATION_FIXTURE` record inside `TEST_REPLAY.jsonl`, deterministic mutation templates/operators that may change only preregistered structural leaves, append-only Stage-6 scientific metadata, an adaptive mutation planner, and a generalization analyzer. Every executable mutation compiles to the existing `ReplayRequest`/`ReplayExecutor` path with the already-proven mechanism/intervention unchanged; generated neighbors are explicitly labeled synthetic and remain linked to the original root failure and immutable source state.

**Tech Stack:** Python 3.14, frozen dataclasses/enums, canonical JSON/SHA-256, existing `ReplayStore`, `CausalEvidenceStore`, `SurfaceEvidenceStore`, `OperatingSurfaceProfile`, `InterventionDefinition`, `ReplayRequest`, `ReplayExecutor`, deterministic fake adapters, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-07-universal-capability-ratchet-v3-design.md`

## Global Constraints

- No real model/network/Ollama call may run during Stage 6 implementation, regression, preflight, or historical planning.
- A mutation is forbidden unless its transformation is deterministic, preregistered, replayable, and capable of changing D12 (or another explicitly named live decision).
- No free-form LLM-generated task mutation is permitted in Stage 6.
- Mutation must preserve the intended causal structure. If answer semantics change, the operator must deterministically update the oracle/contract; otherwise the mutation is invalid.
- Existing same-state and Stage-5 evidence is checked before scheduling a new mutation replay.
- `TEST_REPLAY.jsonl` remains the only canonical replay lineage. Stage-6 metadata may reference replay records but may not duplicate or replace them.
- Generated mutation fixtures must be distinguishable from naturally observed failures and retain lineage to the original root failure.
- `FRESH` and `SEALED` fixtures may be inspected but may not be mutated or consumed for development tuning/generalization.
- Stage 6 may emit `TIER_CANDIDATE` only after preregistered neighborhood evidence. It may never emit `CERTIFIED`.
- Failed mutation replays remain evidence and create child failure snapshots through the existing replay executor; no blind retry path is added.
- Protected challenge mutations survive pruning when scientifically admissible.
- No Cartesian product across mutation axes. The planner selects the smallest decision-changing neighborhood and stops when more points cannot change the generalization class or promotion decision.
- Historical/synthetic evidence cannot be relabeled as fresh or sealed evidence.
- Model cognition and system-owned state/authority/invariants remain separate.

---

### Task 1: Add canonical mutation-fixture replay contracts

**Files:**
- Create: `src/inverted/capability_ratchet/mutation_core.py`
- Modify: `src/inverted/capability_ratchet/core.py`
- Modify: `src/inverted/capability_ratchet/replay_store.py`
- Test: `tests/test_capability_ratchet_mutation_core.py`
- Test: `tests/test_capability_ratchet_replay_store.py`

**Interfaces:**
- Produces `MutationAxis`, `MutationOrigin`, `GeneralizationClass`, `MutationDirection`, `MutationSpec`, `MutationPolicy`, `GeneralizationProfile`.
- Adds canonical replay record `MutationFixture` to `core.py` and `ReplayRecord`.
- `MutationFixture` fields: `mutation_fixture_id`, `failure_snapshot_id`, `source_failure_snapshot_id`, `source_state_hash`, `mechanism_id`, `mutation_axis`, `mutation_direction`, `mutation_value`, `structural_region_id`, `model_visible_asset_sha256`, `oracle_asset_sha256`, `semantic_contract_hash`, `partition`, `origin`, `metadata`, `record_id`.
- `failure_snapshot_id` always names the immutable root failure family; `source_failure_snapshot_id` identifies the repaired source fixture/state from which the neighbor was generated.

- [ ] **1.1 Write failing frozen-contract tests.** Require all 13 Stage-6 axes from the spec: `NUMBERS_ENTITIES`, `DEPENDENCY_DEPTH`, `REQUIREMENT_COUNT`, `ACTION_SPACE_SIZE`, `CRITICAL_INFORMATION_POSITION`, `DISTRACTORS`, `EVIDENCE_STATE`, `AUTHORITY_STATE`, `REVERSIBILITY_CONSEQUENCE`, `TOOL_AVAILABILITY`, `CONTEXT_PRESSURE`, `ORDER`, `RECOVERY_OPPORTUNITY`. Require deterministic IDs, explicit `EASIER`/`LATERAL`/`HARDER` direction, `SYNTHETIC_NEIGHBORHOOD` versus `NATURAL_OBSERVATION` origin, immutable SHA references, and the five exact classes `INSTANCE_PATCH`, `LOCAL_MECHANISM`, `REGION_MECHANISM`, `CROSS_REGION_MECHANISM`, `PROMOTION_CANDIDATE`.

```python
def test_mutation_fixture_requires_root_and_source_lineage():
    fixture = MutationFixture.create(
        failure_snapshot_id="failure-root",
        source_failure_snapshot_id="failure-root",
        source_state_hash="a" * 64,
        mechanism_id="mechanism-1",
        mutation_axis=MutationAxis.DEPENDENCY_DEPTH,
        mutation_direction=MutationDirection.HARDER,
        mutation_value={"depth": 4},
        structural_region_id="planning/dependency",
        model_visible_asset_sha256="b" * 64,
        oracle_asset_sha256="c" * 64,
        semantic_contract_hash="d" * 64,
        partition=Partition.DEVELOPMENT,
        origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD,
    )
    assert fixture.record_type is ReplayRecordType.MUTATION_FIXTURE
```

- [ ] **1.2 Run red tests.**

```bash
pytest tests/test_capability_ratchet_mutation_core.py tests/test_capability_ratchet_replay_store.py -q
```

Expected: import/record parsing failures because `MutationFixture` and Stage-6 contracts do not exist.

- [ ] **1.3 Implement frozen Stage-6 contracts.** `MutationPolicy` must be explicit and serializable rather than hiding thresholds in analyzer code. Default policy:

```python
MutationPolicy(
    min_local_successes=2,
    min_region_successes=4,
    min_region_axes=3,
    min_cross_region_successes=6,
    min_cross_regions=2,
    min_promotion_successes=6,
    min_promotion_axes=4,
    min_harder_successes=2,
    min_success_rate=0.80,
    max_protected_failures=0,
)
```

`GeneralizationProfile` records exact mutation result IDs, axis/region coverage, harder-neighbor coverage, success rate, failures, protected failures, classification, unresolved boundaries, and `promotion_ceiling=PromotionState.TIER_CANDIDATE`.

- [ ] **1.4 Extend canonical replay serialization/parsing.** Add `MutationFixture` to `ReplayRecord`, `to_payload`, `from_payload`, logical identity/supersession validation, asset validation, and lineage validation. The store must reject mutation fixtures whose root family/source fixture/state hash is missing or inconsistent and reject `FRESH`/`SEALED` synthetic mutations.

- [ ] **1.5 Run green contract/store regressions.**

```bash
pytest tests/test_capability_ratchet_mutation_core.py tests/test_capability_ratchet_replay_store.py tests/test_capability_ratchet_core.py -q
```

- [ ] **1.6 Commit.**

```bash
git add src/inverted/capability_ratchet/mutation_core.py src/inverted/capability_ratchet/core.py src/inverted/capability_ratchet/replay_store.py tests/test_capability_ratchet_mutation_core.py tests/test_capability_ratchet_replay_store.py
git commit -m "feat: define V3 mutation replay contracts"
```

---

### Task 2: Generate deterministic causal-preserving mutation fixtures

**Files:**
- Create: `src/inverted/capability_ratchet/mutation_generator.py`
- Test: `tests/test_capability_ratchet_mutation_generator.py`

**Interfaces:**
- `MutationTemplate(source_failure_snapshot_id, structural_region_id, semantic_contract, model_visible_template, oracle_template, allowed_axes, operator_state)`
- `MutationGenerator(replay_store)`
- `generate(template, spec) -> MutationFixture`
- `generate_many(template, specs) -> tuple[MutationFixture, ...]`
- `semantic_contract_hash(contract) -> str`

- [ ] **2.1 Write failing operator-safety tests.** A generator must reject an axis not listed by the template, an operator that changes the semantic contract without an oracle transform, mutation of `FRESH`/`SEALED`, nondeterministic values, duplicate logical mutations, and attempts to change model/runtime provenance.

- [ ] **2.2 Write deterministic planted operators.** Tests must cover at least:
  - numeric/entity substitution with deterministic oracle remap;
  - dependency-depth increase/decrease;
  - requirement-count increase;
  - distractor insertion;
  - critical-information relocation;
  - authority-state change;
  - tool-availability flag;
  - context-pressure padding;
  - order permutation;
  - recovery-opportunity flag.

Each operator writes canonical model-visible/oracle assets with `ReplayStore.put_asset()` and derives `MutationFixture` IDs solely from source lineage + canonical spec + resulting asset hashes.

- [ ] **2.3 Run red tests.**

```bash
pytest tests/test_capability_ratchet_mutation_generator.py -v
```

- [ ] **2.4 Implement template-bound operators.** Do not parse arbitrary prose to guess mutable slots. A source without an explicit deterministic `MutationTemplate` is `NOT_MUTATABLE`, not an invitation to fabricate a neighbor.

- [ ] **2.5 Prove byte-identical regeneration/idempotent append.** Generating the same mutation twice must produce the same assets, fixture ID, record ID, and no additional logical replay row.

```bash
pytest tests/test_capability_ratchet_mutation_generator.py tests/test_capability_ratchet_replay_store.py -q
```

- [ ] **2.6 Commit.**

```bash
git add src/inverted/capability_ratchet/mutation_generator.py tests/test_capability_ratchet_mutation_generator.py
git commit -m "feat: generate deterministic failure neighborhoods"
```

---

### Task 3: Persist Stage-6 studies, outcomes, and profiles append-only

**Files:**
- Create: `src/inverted/capability_ratchet/mutation_store.py`
- Test: `tests/test_capability_ratchet_mutation_store.py`

**Interfaces:**
- `MutationStudy(study_id, failure_snapshot_id, mechanism_id, source_failure_snapshot_id, source_state_hash, operating_surface_profile_id, policy, decision_id, candidate_specs, protected_spec_ids)`
- `MutationOutcome(outcome_id, study_id, mutation_fixture_id, replay_result_id, axis, direction, structural_region_id, protected, semantic_pass, contract_pass, metadata)`
- `MutationEvidenceStore(root, replay_store, surface_store)`
- `append_study`, `append_outcome`, `append_profile`, `studies`, `outcomes`, `profiles`, `validate`
- Files: `mutation-studies.jsonl`, `mutation-outcomes.jsonl`, `generalization-profiles.jsonl` plus SHA-256 manifests.

- [ ] **3.1 Write red durability/lineage tests.** Require idempotent append, no logical-ID rewrite, manifest tamper detection, study references a real `MOVEMENT` mechanism/Stage-5 profile or an explicit decision-critical reason, outcome references a stored `MutationFixture` and matching `ReplayResult`, and profile evidence resolves to stored outcomes.

- [ ] **3.2 Require partition and contamination invariants.** No synthetic study may consume a `FRESH`/`SEALED` mutation fixture; historical/development/training lineage remains explicit and immutable.

- [ ] **3.3 Implement canonical append-only metadata store.** Stage-6 metadata never stores raw model responses or creates an alternate replay identity.

- [ ] **3.4 Run green + Stage-5/store regressions.**

```bash
pytest tests/test_capability_ratchet_mutation_store.py tests/test_capability_ratchet_surface_store.py tests/test_capability_ratchet_replay_store.py -q
```

- [ ] **3.5 Commit.**

```bash
git add src/inverted/capability_ratchet/mutation_store.py tests/test_capability_ratchet_mutation_store.py
git commit -m "feat: persist mutation generalization evidence"
```

---

### Task 4: Plan the smallest decision-changing mutation neighborhood

**Files:**
- Create: `src/inverted/capability_ratchet/mutation_planner.py`
- Test: `tests/test_capability_ratchet_mutation_planner.py`

**Interfaces:**
- `MutationPlanner(mutation_store)`
- `plan_next(study, *, max_new_mutations=3) -> MutationPlan`
- `MutationPlan(specs, reused_fixture_ids, decision_reason, minimum_physical_calls, expected_physical_calls, worst_case_physical_calls, protected_challenge_calls, stop_reason)`

- [ ] **4.1 Write red adaptive-selection tests.** The first neighborhood must sample different causal dimensions before spending calls densely on one axis; at least one `HARDER` mutation must be retained where admissible. Existing answered mutation fixtures/results are reused with zero calls.

- [ ] **4.2 Write protected-challenge tests.** Pruning cannot erase the only admissible high-difficulty/extreme mutation. Protected challenge failures block promotion rather than being averaged away.

- [ ] **4.3 Write no-Cartesian-product tests.** For 13 axes × multiple values, the initial plan must remain bounded by `max_new_mutations`, and every chosen spec must identify how its possible outcomes can change classification, a neighborhood boundary, or D12.

- [ ] **4.4 Write stopping tests.** Stop when remaining admissible mutations cannot move the current `INSTANCE_PATCH`/`LOCAL_MECHANISM`/`REGION_MECHANISM`/`CROSS_REGION_MECHANISM`/promotion decision under the registered policy.

- [ ] **4.5 Implement deterministic planner/call geometry.** No model adapter may be constructed by `plan_next()`.

- [ ] **4.6 Run green tests.**

```bash
pytest tests/test_capability_ratchet_mutation_planner.py tests/test_capability_ratchet_surface_planner.py -q
```

- [ ] **4.7 Commit.**

```bash
git add src/inverted/capability_ratchet/mutation_planner.py tests/test_capability_ratchet_mutation_planner.py
git commit -m "feat: adaptively plan mutation neighborhoods"
```

---

### Task 5: Compile mutation probes through the existing causal repair/replay path

**Files:**
- Create: `src/inverted/capability_ratchet/mutation_replay.py`
- Modify: `src/inverted/capability_ratchet/replay.py`
- Test: `tests/test_capability_ratchet_mutation_replay.py`

**Interfaces:**
- `MutationReplayCompiler(replay_store, causal_store)`
- `compile(mutation_fixture, mechanism_label, intervention_ids, *, request_id, decision_id="D12") -> ReplayRequest`
- Existing `ReplayExecutor` remains the only executor.

- [ ] **5.1 Write red leaf-fidelity tests.** A mutation replay must combine exactly two preregistered facts: the mutated model-visible fixture and the already-proven repair mechanism. It may not silently change inference budget, temperature, tool set, prompt/context ingredient, or another repair dimension unless that dimension is itself part of the registered mechanism.

- [ ] **5.2 Require mechanism identity preservation.** The source mechanism/intervention IDs must be unchanged from the evidence that earned `MOVEMENT`; Stage 6 tests transfer of the repair, not a newly tuned repair per mutation.

- [ ] **5.3 Require explicit mutation provenance in request metadata.** Include `mutation_fixture_id`, `mutation_axis`, `mutation_direction`, `structural_region_id`, `synthetic_neighborhood=True`, and source operating-surface profile ID.

- [ ] **5.4 Implement compilation through `ReplayRequest(mode=COUNTERFACTUAL)` and existing replay assets.** Extend `ReplayExecutor` only as necessary to select the mutation fixture's model-visible asset; do not add transport/adaptor duplication.

- [ ] **5.5 Prove failed mutation replay creates a child failure snapshot.** The mutation fixture remains immutable and the child is linked to the same root failure family.

```bash
pytest tests/test_capability_ratchet_mutation_replay.py tests/test_capability_ratchet_replay.py tests/test_capability_ratchet_qwen_replay.py -q
```

- [ ] **5.6 Commit.**

```bash
git add src/inverted/capability_ratchet/mutation_replay.py src/inverted/capability_ratchet/replay.py tests/test_capability_ratchet_mutation_replay.py
git commit -m "feat: replay proven repairs across mutations"
```

---

### Task 6: Classify generalization and gate `TIER_CANDIDATE`

**Files:**
- Create: `src/inverted/capability_ratchet/mutation_analysis.py`
- Modify: `src/inverted/capability_ratchet/query.py`
- Test: `tests/test_capability_ratchet_mutation_analysis.py`

**Interfaces:**
- `MutationAnalyzer(replay_store, mutation_store)`
- `analyze(study_id) -> GeneralizationProfile`
- `maybe_promote(profile) -> PromotionEvent | None`

- [ ] **6.1 Write planted classification tests.** Require:
  - source-only/local single success → `INSTANCE_PATCH`;
  - at least two same-axis nearby successes → `LOCAL_MECHANISM`;
  - default-policy breadth across ≥3 axes and ≥4 successes → `REGION_MECHANISM`;
  - ≥2 structural regions and ≥6 successes → `CROSS_REGION_MECHANISM`;
  - promotion thresholds met, including ≥4 axes, ≥2 harder successes, ≥80% success, and zero protected failures → `PROMOTION_CANDIDATE`.

- [ ] **6.2 Write negative-transfer/boundary tests.** Any protected mutation failure blocks `TIER_CANDIDATE`. Ordinary failures remain in the profile and create explicit unresolved/negative-transfer boundaries instead of being discarded.

- [ ] **6.3 Write promotion-chain tests.** `maybe_promote()` may append `MOVEMENT -> TIER_CANDIDATE` only. `CERTIFIED` is forbidden. Evidence replay-result IDs must all resolve to the same root mechanism family, and the source fixture's static `promotion_state` must remain unchanged.

- [ ] **6.4 Implement deterministic classification from registered `MutationPolicy`.** Do not hide threshold changes in code. Query selection must derive current promotion state from append-only events as in Plan 2.

- [ ] **6.5 Run green mechanism/query regressions.**

```bash
pytest tests/test_capability_ratchet_mutation_analysis.py tests/test_capability_ratchet_mechanisms.py tests/test_capability_ratchet_query_cli.py -q
```

- [ ] **6.6 Commit.**

```bash
git add src/inverted/capability_ratchet/mutation_analysis.py src/inverted/capability_ratchet/query.py tests/test_capability_ratchet_mutation_analysis.py
git commit -m "feat: classify mechanism neighborhood generalization"
```

---

### Task 7: Orchestrate Stage 6 and add safe CLI surfaces

**Files:**
- Create: `src/inverted/capability_ratchet/mutation_lab.py`
- Modify: `src/inverted/capability_ratchet/cli.py`
- Test: `tests/test_capability_ratchet_mutation_lab.py`
- Test: `tests/test_capability_ratchet_query_cli.py`

**Interfaces:**
- `MutationLab.prepare(study_id) -> MutationPlan`
- `MutationLab.execute(plan, adapters) -> MutationStepResult`
- CLI:
  - `plan-mutations --replay-root ... --causal-root ... --surface-root ... --mutation-root ... --study-id ...`
  - `show-mutations ...`
  - `run-mutations ... --allow-model-calls`

- [ ] **7.1 Write fake-adapter lab tests.** `prepare()` generates/persists only deterministic fixtures required by the current plan, reuses answered neighbors, and performs zero model calls. `execute()` compiles requests through `MutationReplayCompiler`, executes only through `ReplayExecutor`, appends outcomes, analyzes the profile, and returns the next adaptive decision.

- [ ] **7.2 Write child-failure continuation test.** A failed harder mutation creates a child failure snapshot that remains queryable in the originating failure family and can seed a later Stage-7 autopsy without mutating the Stage-6 source.

- [ ] **7.3 Write CLI hard-gate tests.** `plan-mutations` and `show-mutations` report `MODEL_CALLS=0`; `run-mutations` must reject before Qwen/Ollama/network adapter construction without explicit `--allow-model-calls`.

- [ ] **7.4 Implement orchestration.** No automatic retry after a failed mutation. The result either narrows the generalization boundary, changes classification, or becomes a new failure asset.

- [ ] **7.5 Run green lab/CLI regressions.**

```bash
pytest tests/test_capability_ratchet_mutation_lab.py tests/test_capability_ratchet_query_cli.py tests/test_capability_ratchet_surface_lab.py tests/test_capability_ratchet_lab.py -q
```

- [ ] **7.6 Commit.**

```bash
git add src/inverted/capability_ratchet/mutation_lab.py src/inverted/capability_ratchet/cli.py tests/test_capability_ratchet_mutation_lab.py tests/test_capability_ratchet_query_cli.py
git commit -m "feat: orchestrate mutation generalization studies"
```

---

### Task 8: Prove Stage 6 end to end with zero inference

**Files:**
- Create: `tests/test_capability_ratchet_mutation_preflight.py`
- Modify: `src/inverted/capability_ratchet/__init__.py`
- Modify: `scripts/audit-v3-replay-foundation.py`
- Create: `.github/workflows/v3-stage6-completion.yml`

- [ ] **8.1 Build planted synthetic mechanism cases.** Include:
  - an instance-only repair that fails its first lateral mutation;
  - a local mechanism surviving two same-axis variants but failing another axis;
  - a region mechanism surviving multiple axes;
  - a cross-region mechanism;
  - a promotion candidate surviving ≥6 neighbors, ≥4 axes, ≥2 harder mutations, ≥80% success, and zero protected failures;
  - a protected negative-transfer case that must block promotion;
  - a mutation whose result already exists and must be reused without invoking the fake adapter.

- [ ] **8.2 Booby-trap real transports.** Monkeypatch Qwen/Ollama/network constructors to raise. All Stage-6 preflight and audit commands must complete without constructing them.

- [ ] **8.3 Prove canonical replay integrity.** Mutation fixtures appear as `MUTATION_FIXTURE` rows in `TEST_REPLAY.jsonl`; replay requests/results and failed descendants resolve to one root family; `forgotten_count=0`; no orphan assets; synthetic origin cannot be confused with natural failure evidence.

- [ ] **8.4 Prove promotion ceiling.** Clean neighborhood evidence may emit `TIER_CANDIDATE`; any Stage-6 attempt to emit `CERTIFIED` must fail because Stage 11 fresh/sealed confirmation has not occurred.

- [ ] **8.5 Extend permanent audit.** Add Stage-6 counts/invariants without weakening Plan-1/2/3 checks: mutation-axis count = 13, `MUTATION_FIXTURE` parser/serializer coverage, no FRESH/SEALED synthetic mutation, no Stage-6 `CERTIFIED` event, and zero-call historical eligibility planning.

- [ ] **8.6 Add dedicated zero-call completion workflow.** It must run:

```bash
python -m pytest tests/test_capability_ratchet_mutation_*.py -q
python -m pytest tests/test_capability_ratchet_*.py -q
python -m pytest tests/test_universal_tuning_end_to_end.py tests/test_universal_tuning_qwen_cli.py tests/test_universal_tuning_runner.py tests/test_universal_tuning_scheduler.py tests/test_universal_tuning_scoring.py tests/test_universal_tuning_statistics.py tests/test_universal_tuning_tasks.py tests/test_universal_tuning_v1_audit.py tests/test_qwen_thinking_tuning.py -q -k "not test_powershell_launcher_dry_run_executes_repo_local_module and not test_powershell_launcher_uses_v2_default_dry_run"
python -m pytest -q -k "not test_powershell_launcher_dry_run_executes_repo_local_module and not test_powershell_launcher_uses_v2_default_dry_run"
python -m inverted.evidence_privacy check --root evidence --scan-out /tmp/stage6-privacy.json
python scripts/audit-v3-replay-foundation.py --source live-evidence/qwen-thinking-tuning-v2-real-20260907 --replay-root /tmp/stage6-replay
```

The historical Stage-6 planning result must explicitly emit `NO_ELIGIBLE_MECHANISMS` or `NO_MUTATION_TEMPLATE` when durable prerequisites do not exist; it may never manufacture eligibility.

- [ ] **8.7 Run full exact-head matrix.** Linux 3.11/3.12/3.14, Windows 3.14, capability-ratchet model-free, Test-2 model-free, and Test-3 S0 repository replay must all remain green.

- [ ] **8.8 Commit Stage-6 completion.**

```bash
git add src/inverted/capability_ratchet scripts/audit-v3-replay-foundation.py tests/test_capability_ratchet_mutation_*.py .github/workflows/v3-stage6-completion.yml
git commit -m "test: validate V3 neighborhood generalization"
```

---

## Stage 6 Completion Gate

Stage 6 is complete only when all are true:

1. All synthetic neighbors are deterministic, template-bound, and linked to the original root failure and repaired source state.
2. Every generated neighbor is a canonical `MUTATION_FIXTURE` in `TEST_REPLAY.jsonl`; no competing replay registry exists.
3. Mutation fixtures are explicitly distinguishable from naturally observed failures.
4. All 13 Stage-6 mutation axes are represented by frozen contracts, while only template-authorized axes can be generated for a given source.
5. Semantic-contract preservation is enforced; semantic changes require deterministic oracle/contract transformation.
6. FRESH/SEALED evidence cannot be mutated or consumed for development generalization.
7. Existing answered mutation evidence is reused before any physical call is proposed.
8. The planner samples causal breadth adaptively, avoids Cartesian enumeration, retains protected challenge mutations, and stops when more mutations cannot change D12/generalization class.
9. The already-proven repair mechanism is held fixed across neighbors; Stage 6 does not retune a new repair per mutation.
10. Every executable mutation uses existing `ReplayRequest` + `ReplayExecutor`; no second execution engine exists.
11. Failed mutation replays create child failure snapshots and become new evidence rather than blind retries.
12. Generalization is classified only as `INSTANCE_PATCH`, `LOCAL_MECHANISM`, `REGION_MECHANISM`, `CROSS_REGION_MECHANISM`, or `PROMOTION_CANDIDATE` under an explicit stored policy.
13. Protected negative transfer blocks promotion and remains visible as a boundary.
14. `MOVEMENT -> TIER_CANDIDATE` requires preregistered neighborhood breadth/reliability; source fixture immutability is preserved.
15. Stage 6 cannot emit `CERTIFIED`.
16. Synthetic preflight distinguishes all five generalization classes and rejects sham/negative-transfer promotion.
17. Historical zero-call planning never manufactures a mutation template or eligible mechanism.
18. Plan-1/2/3/Stage-6, V2, full-repository, replay-integrity, privacy, Test-2, Test-3 S0, Linux, and Windows gates remain green.
19. `MODEL_CALLS=0` for every implementation/preflight/completion workflow command.

## Deliberate Scope Boundary

Stage 6 ends after causal-preserving neighborhood generalization and optional promotion to `TIER_CANDIDATE`. It does **not** perform Stage-7 tool/skill/verifier/recovery tomography, Stage-8 capability ownership compilation, Stage-9 fine-tuning qualification/training, Stage-10 controller extraction, or Stage-11 fresh/sealed certification. Stage 7 receives generalized mechanisms plus failed mutation descendants as its input.
