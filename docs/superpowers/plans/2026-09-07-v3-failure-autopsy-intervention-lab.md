# V3 Failure Autopsy & Intervention Laboratory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn every canonical `FAILURE_FIXTURE` into a zero-rerun causal micro-experiment: identify the earliest supported divergence, generate falsifiable hypotheses, construct the smallest matched intervention/sham/ablation set, execute only registered counterfactual replay branches, and append durable mechanism/movement evidence without mutating the source failure.

**Architecture:** Extend the proven replay kernel rather than replacing it. A deterministic autopsy layer consumes only verified replay assets and safely observable forensic evidence; a causal evidence store persists hypotheses/interventions; a tournament planner compiles interventions into existing `ReplayRequest` objects; a laboratory orchestrator feeds failed replay children back into the same lineage; a mechanism localizer turns matched outcomes into explicit causal roles and MOVEMENT-only promotion events. Plan 2 remains inference-free in tests/preflight: all execution uses `FakeReplayAdapter` and real Qwen/Ollama construction remains forbidden.

**Tech Stack:** Python 3.14, frozen dataclasses/enums, canonical JSON/SHA-256, existing `ReplayStore`/`ReplayExecutor`, pytest, PowerShell wrapper conventions.

**Spec:** `docs/superpowers/specs/2026-09-07-universal-capability-ratchet-v3-design.md`

## Global Constraints

- The immutable source `FAILURE_FIXTURE`, original attempt, forensic evidence, and model-visible replay assets may never be rewritten by a repair.
- `TEST_REPLAY.jsonl` remains the only canonical replay lineage store. Hypothesis/intervention files are scientific metadata stores, not competing replay stores.
- Generic retry branches are forbidden. Every branch must carry a `hypothesis_id`, `intervention_id`, expected causal implication, and registered changed dimensions.
- Exact replay is analytically distinct from counterfactual intervention evidence and may not be scored as intervention gain.
- Historical fixtures remain historical. FRESH/SEALED labels are immutable and cannot be manufactured by replay.
- Autopsy/hypothesis generation may use model-visible state plus safely observable forensic evidence; hidden oracle answers/family labels may be used for scoring but never to construct a treatment presented to the model.
- Failed intervention replays remain evidence and, when material, become child `FAILURE_FIXTURE` rows that can be autopsied independently without deleting the parent branch.
- A successful mechanism must beat an appropriate matched sham/control whenever a sham can falsify the causal explanation.
- MOVEMENT is a discovery gate. Plan 2 must not emit `TIER_CANDIDATE` or `CERTIFIED`; those require neighborhood/fresh/sealed work from later plans.
- Protected exploration must preserve at least one admissible surprising/alternative hypothesis when the planner prunes a larger candidate set.
- No real model/network/Ollama call is permitted during Plan 2 implementation, regression, or synthetic preflight.
- A call branch is invalid if no possible result can change an active hypothesis, ownership decision, or mechanism classification.

---

## File Structure

- Create `src/inverted/capability_ratchet/causal_core.py` — frozen causal/autopsy/intervention/mechanism contracts and enums.
- Create `src/inverted/capability_ratchet/causal_store.py` — integrity-gated `causal-hypotheses.jsonl` and immutable intervention registry/assets.
- Create `src/inverted/capability_ratchet/autopsy.py` — deterministic first-divergence extraction and hypothesis generation.
- Create `src/inverted/capability_ratchet/interventions.py` — intervention recipes, matched sham/control construction, and `ReplayRequest` compilation.
- Create `src/inverted/capability_ratchet/tournament.py` — minimal hypothesis-separating tournament geometry, pruning, ablation generation, and call accounting.
- Create `src/inverted/capability_ratchet/mechanisms.py` — matched-outcome causal localization, MOVEMENT disposition, and hash-linked `mechanism-graph.json` derived view.
- Create `src/inverted/capability_ratchet/lab.py` — end-to-end failure micro-program orchestration and child-failure feedback.
- Modify `src/inverted/capability_ratchet/core.py` — add `MECHANISM_LABEL` and `PROMOTION_EVENT` canonical replay records only.
- Modify `src/inverted/capability_ratchet/replay_store.py` — validate/store the new canonical replay record types without changing prior rows.
- Modify `src/inverted/capability_ratchet/query.py` and `cli.py` — mechanism/hypothesis inspection and zero-call lab planning.
- Modify `src/inverted/capability_ratchet/__init__.py` — stable exports after behavior is proven.
- Create tests `tests/test_capability_ratchet_causal_core.py`, `..._causal_store.py`, `..._autopsy.py`, `..._interventions.py`, `..._tournament.py`, `..._mechanisms.py`, `..._lab.py`, and `..._causal_preflight.py`.

---

### Task 1: Freeze causal contracts and append-only mechanism/promotion lineage

**Files:**
- Create: `src/inverted/capability_ratchet/causal_core.py`
- Modify: `src/inverted/capability_ratchet/core.py`
- Modify: `src/inverted/capability_ratchet/replay_store.py`
- Test: `tests/test_capability_ratchet_causal_core.py`
- Test: `tests/test_capability_ratchet_replay_store.py`

**Interfaces:**
- Produces `DivergenceClass`, `ArchitectureOwner`, `HypothesisStatus`, `InterventionKind`, `MechanismRole`, `FirstDivergence`, `CausalHypothesis`, `InterventionDefinition`, `MechanismLabel`, `PromotionEvent`.
- `MechanismLabel` and `PromotionEvent` are canonical append-only `TEST_REPLAY` record types; hypotheses/interventions are separate scientific metadata objects.

- [ ] **1.1 Write failing contract tests.** Require frozen JSON-safe fields, stable IDs/hashes, evidence refs, falsifier/prediction fields, changed-dimension uniqueness, sham/ablation lineage, and owner/role enums. Add replay-store tests proving `MECHANISM_LABEL` and `PROMOTION_EVENT` serialize/round-trip/validate and prior rows remain byte-identical.

```python
def test_hypothesis_is_falsifiable_and_bound_to_failure():
    h = CausalHypothesis.create(
        failure_snapshot_id="failure-1",
        parent_state_hash="a" * 64,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.CONTRACT_INTERFACE,
            observable_path="focus_observation.contract_pass",
            event_index=0,
            evidence_refs=("forensic:focus_observation",),
            confidence=1.0,
        ),
        owner_candidate=ArchitectureOwner.SYSTEM,
        claim="schema failure is independent of semantic reasoning",
        expected_if_true="a deterministic formatter repairs contract without cognition change",
        falsifier="formatter treatment fails while a cognition treatment repairs the same state",
    )
    assert h.failure_snapshot_id == "failure-1"
    assert h.hypothesis_id.startswith("hyp-")
```

- [ ] **1.2 Run red tests.**

```bash
pytest tests/test_capability_ratchet_causal_core.py tests/test_capability_ratchet_replay_store.py -q
```

Expected: new causal types/record parsing are missing.

- [ ] **1.3 Implement minimal contracts and replay-record extensions.** Do not add orchestration or generators in this task. Preserve existing `FailureFixture`, `ReplayRequest`, and `ReplayResult` payloads byte-for-byte.

- [ ] **1.4 Run green tests plus existing core/store regressions.**

```bash
pytest tests/test_capability_ratchet_core.py tests/test_capability_ratchet_replay_store.py tests/test_capability_ratchet_causal_core.py -q
```

- [ ] **1.5 Commit.**

```bash
git add src/inverted/capability_ratchet/causal_core.py src/inverted/capability_ratchet/core.py src/inverted/capability_ratchet/replay_store.py tests/test_capability_ratchet_causal_core.py tests/test_capability_ratchet_replay_store.py
git commit -m "feat: define V3 causal laboratory contracts"
```

---

### Task 2: Add integrity-gated hypothesis and intervention evidence stores

**Files:**
- Create: `src/inverted/capability_ratchet/causal_store.py`
- Test: `tests/test_capability_ratchet_causal_store.py`

**Interfaces:**
- `CausalEvidenceStore(root)`
- `append_hypothesis(hypothesis) -> str`
- `hypotheses(failure_snapshot_id=None) -> tuple[CausalHypothesis, ...]`
- `register_intervention(intervention) -> str`
- `get_intervention(intervention_id) -> InterventionDefinition`
- `validate() -> CausalStoreValidation`
- Canonical files: `causal-hypotheses.jsonl`, `causal-hypotheses.sha256`, `intervention-registry.json`, `causal-assets/sha256/<digest>.json`.

- [ ] **2.1 Write failing durability tests.** Prove deterministic/idempotent append, content-addressed intervention payloads, duplicate logical IDs require exact bytes, manifest/hash tamper is detected, registry correction cannot overwrite an existing intervention ID, and hypothesis/intervention records always reference an existing canonical failure snapshot when a `ReplayStore` is supplied.

```python
def test_intervention_registry_is_content_addressed_and_immutable(tmp_path):
    replay = seeded_replay_store(tmp_path / "replay")
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    intervention = intervention_for(replay.records()[0])
    digest = causal.register_intervention(intervention)
    before = (causal.root / "intervention-registry.json").read_bytes()
    assert causal.register_intervention(intervention) == digest
    assert (causal.root / "intervention-registry.json").read_bytes() == before
    assert causal.validate().ok
```

- [ ] **2.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_causal_store.py -v
```

- [ ] **2.3 Implement canonical JSON/hash validation and cross-store lineage checks.** The intervention registry may add new IDs but must never alter the content hash already assigned to an existing ID.

- [ ] **2.4 Run green test and replay-store regression.**

```bash
pytest tests/test_capability_ratchet_causal_store.py tests/test_capability_ratchet_replay_store.py -q
```

- [ ] **2.5 Commit.**

```bash
git add src/inverted/capability_ratchet/causal_store.py tests/test_capability_ratchet_causal_store.py
git commit -m "feat: add causal hypothesis and intervention evidence store"
```

---

### Task 3: Autopsy the exact failed process and earliest supported divergence

**Files:**
- Create: `src/inverted/capability_ratchet/autopsy.py`
- Test: `tests/test_capability_ratchet_autopsy.py`

**Interfaces:**
- `FailureAutopsy(replay_store, causal_store)`
- `analyze(fixture: FailureFixture) -> AutopsyReport`
- `AutopsyReport(failure_snapshot_id, first_divergence, hypotheses, evidence_refs, unresolved_questions)`
- `HypothesisGenerator` protocol for future mentor/model-assisted generation; Plan 2 implements only `DeterministicHypothesisGenerator`.

- [ ] **3.1 Write red tests from planted failure evidence.** Cover semantic arithmetic failure, contract-only failure, completion/reasoning-cap failure, authority/scope metadata, and unknown failure. Require the autopsy to cite the exact observable field/event where divergence first appears and never read oracle task answers when generating claims/treatments.

```python
def test_contract_failure_localizes_before_semantic_cognition(tmp_path):
    fixture, replay, causal = planted_contract_failure(tmp_path)
    report = FailureAutopsy(replay, causal).analyze(fixture)
    assert report.first_divergence.divergence_class is DivergenceClass.CONTRACT_INTERFACE
    assert report.first_divergence.observable_path.endswith("contract_pass")
    assert ArchitectureOwner.SYSTEM in {h.owner_candidate for h in report.hypotheses}
    assert all("oracle" not in ref.lower() for h in report.hypotheses for ref in h.evidence_refs)
```

- [ ] **3.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_autopsy.py -v
```

- [ ] **3.3 Implement deterministic evidence extraction and bounded hypotheses.** Rules must be evidence-driven and deterministic: maximum four live hypotheses per parent, ordered by explanatory discrimination rather than generic breadth. Unknown cases emit `UNKNOWN_NOVEL` plus explicit unresolved evidence need; they do not invent a diagnosis.

- [ ] **3.4 Persist generated hypotheses and prove idempotence.** Re-autopsying the same immutable fixture must return the same hypothesis IDs and add no duplicate scientific rows.

- [ ] **3.5 Run green tests.**

```bash
pytest tests/test_capability_ratchet_autopsy.py tests/test_capability_ratchet_causal_store.py -q
```

- [ ] **3.6 Commit.**

```bash
git add src/inverted/capability_ratchet/autopsy.py tests/test_capability_ratchet_autopsy.py
git commit -m "feat: autopsy replay failures into falsifiable hypotheses"
```

---

### Task 4: Generate tailored interventions, controls, and registered replay dimensions

**Files:**
- Create: `src/inverted/capability_ratchet/interventions.py`
- Test: `tests/test_capability_ratchet_interventions.py`

**Interfaces:**
- `InterventionGenerator(replay_store, causal_store)`
- `generate(fixture, hypothesis) -> tuple[InterventionDefinition, ...]`
- `compile_request(fixture, intervention, request_id, decision_id) -> ReplayRequest`
- `make_matched_sham(target) -> InterventionDefinition | None`

- [ ] **4.1 Write failing tests for hypothesis-specific recipes.** At minimum:
  - contract/interface -> deterministic formatting/contract emphasis treatment;
  - reasoning-cap -> bounded cognition profile treatment, not global always-think;
  - missing state/dependency -> context/representation treatment;
  - deterministic-computation hypothesis -> system computation treatment marker;
  - unknown/novel -> protected exploration treatment only, never generic retry.

Require each treatment to declare exactly the registered `ReplayRequest.changed_dimensions`, `overrides`, hypothesis lineage, expected causal implication, projected physical-call count, and whether a matched sham is scientifically admissible.

```python
def test_prompt_treatment_and_sham_change_same_leaf(tmp_path):
    fixture, hypothesis, generator = prompt_case(tmp_path)
    target = generator.generate(fixture, hypothesis)[0]
    sham = generator.make_matched_sham(target)
    assert target.changed_dimensions == sham.changed_dimensions
    assert target.hypothesis_id == sham.hypothesis_id
    assert sham.kind is InterventionKind.SHAM
    assert sham.sham_for == target.intervention_id
```

- [ ] **4.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_interventions.py -v
```

- [ ] **4.3 Implement registered intervention recipes only.** Use existing replay dimension paths (`request_envelopes.<n>.messages`, `.options.<key>`, `.think`, `.tools`). For interventions that represent future system/tool ownership rather than a model-visible replay leaf, emit a zero-model-call `DETERMINISTIC` candidate with explicit evaluator metadata; do not fake a model request.

- [ ] **4.4 Compile model-visible interventions into valid `COUNTERFACTUAL` requests and prove undeclared dimensions are rejected by the existing `ReplayExecutor`.**

- [ ] **4.5 Run green tests plus replay tests.**

```bash
pytest tests/test_capability_ratchet_interventions.py tests/test_capability_ratchet_replay.py -q
```

- [ ] **4.6 Commit.**

```bash
git add src/inverted/capability_ratchet/interventions.py tests/test_capability_ratchet_interventions.py
git commit -m "feat: generate tailored V3 replay interventions"
```

---

### Task 5: Build the minimum hypothesis-separating tournament and ablation geometry

**Files:**
- Create: `src/inverted/capability_ratchet/tournament.py`
- Test: `tests/test_capability_ratchet_tournament.py`

**Interfaces:**
- `TournamentPlanner(causal_store)`
- `plan(fixture, hypotheses, interventions, *, reproducibility_known=True, max_branches=8) -> TournamentPlan`
- `TournamentBranch(branch_id, intervention_ids, mode, decision_reason, protected_exploration, projected_physical_calls)`
- `build_ablations(successful_compound, component_ids) -> tuple[InterventionDefinition, ...]`

- [ ] **5.1 Write failing geometry tests.** Prove:
  - no exact replay is added when historical reproducibility already settles the noise question;
  - one targeted branch per live hypothesis is preferred before redundant variants;
  - admissible matched shams accompany causal claims;
  - protected exploration survives pruning;
  - a branch is rejected if success and failure would lead to the same decision;
  - compound success generates leave-one-component-out ablations plus sham, not a full power-set explosion;
  - `A+B+A` recurrence is representable when the hypothesis explicitly requires re-anchoring/recurrence.

```python
def test_compound_success_generates_leave_one_out_and_sham_not_power_set():
    plan = build_ablations(successful_compound("A", "B", "C"), ("A", "B", "C"))
    assert {item.ablates for item in plan if item.ablates} == {("A",), ("B",), ("C",)}
    assert sum(item.kind is InterventionKind.SHAM for item in plan) == 1
    assert len(plan) == 4
```

- [ ] **5.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_tournament.py -v
```

- [ ] **5.3 Implement deterministic information-value pruning and call geometry.** `TournamentPlan` must report minimum/expected/worst-case physical calls and the unresolved decision each branch can change.

- [ ] **5.4 Run green tests.**

```bash
pytest tests/test_capability_ratchet_tournament.py tests/test_capability_ratchet_interventions.py -q
```

- [ ] **5.5 Commit.**

```bash
git add src/inverted/capability_ratchet/tournament.py tests/test_capability_ratchet_tournament.py
git commit -m "feat: plan causal intervention tournaments"
```

---

### Task 6: Localize causal mechanism roles and emit MOVEMENT without false certification

**Files:**
- Create: `src/inverted/capability_ratchet/mechanisms.py`
- Modify: `src/inverted/capability_ratchet/query.py`
- Test: `tests/test_capability_ratchet_mechanisms.py`

**Interfaces:**
- `MechanismLocalizer(replay_store, causal_store)`
- `evaluate(failure_snapshot_id, replay_results) -> MechanismAssessment`
- `MechanismAssessment(labels, supported_hypotheses, falsified_hypotheses, promotion_events, next_decisions)`

- [ ] **6.1 Write failing causal-classification tests.** Synthetic patterns must classify `REQUIRED`, `ENABLER`, `SYNERGIST`, `SUPPRESSOR`, `REDUNDANT`, `HARMFUL`, and `UNRESOLVED`. Target success with sham success must not establish causality. A single-instance targeted success beating sham may earn `MOVEMENT`, but must never emit `TIER_CANDIDATE`/`CERTIFIED`.

```python
def test_target_success_sham_failure_earns_movement_not_certification(tmp_path):
    assessment = planted_target_vs_sham(tmp_path, target_pass=True, sham_pass=False)
    assert any(event.to_state is PromotionState.MOVEMENT for event in assessment.promotion_events)
    assert not any(event.to_state in {PromotionState.TIER_CANDIDATE, PromotionState.CERTIFIED}
                   for event in assessment.promotion_events)
```

- [ ] **6.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_mechanisms.py -v
```

- [ ] **6.3 Implement outcome matching by parent state, hypothesis, intervention, and counterfactual group.** Never compare branches from different parent hashes as a causal pair.

- [ ] **6.4 Append `MechanismLabel` and `PromotionEvent` rows to `TEST_REPLAY.jsonl`; make queries filter by mechanism/promotion state without mutating `FailureFixture.promotion_state`.** Current state is derived from append-only events. Generate `mechanism-graph.json` as a rebuildable view whose header carries the source `TEST_REPLAY.sha256` and causal-store manifest hash; deleting the graph and rebuilding it must produce byte-identical output.

- [ ] **6.5 Run green tests and query regressions.**

```bash
pytest tests/test_capability_ratchet_mechanisms.py tests/test_capability_ratchet_query_cli.py tests/test_capability_ratchet_replay_store.py -q
```

- [ ] **6.6 Commit.**

```bash
git add src/inverted/capability_ratchet/mechanisms.py src/inverted/capability_ratchet/query.py tests/test_capability_ratchet_mechanisms.py tests/test_capability_ratchet_query_cli.py
git commit -m "feat: localize replay mechanisms and movement"
```

---

### Task 7: Orchestrate one failure as a reusable causal research program

**Files:**
- Create: `src/inverted/capability_ratchet/lab.py`
- Modify: `src/inverted/capability_ratchet/cli.py`
- Test: `tests/test_capability_ratchet_lab.py`

**Interfaces:**
- `FailureLab(replay_store, causal_store, autopsy, intervention_generator, tournament_planner, localizer)`
- `prepare(failure_snapshot_id) -> FailureResearchProgram`
- `execute(program, adapters) -> FailureResearchResult`
- `ingest_child_failure(child_failure_snapshot_id) -> FailureResearchProgram`
- CLI: `autopsy`, `plan-lab`, `show-lab`; `run-lab` must require `--allow-model-calls` and remain unused in Plan 2 validation.

- [ ] **7.1 Write failing orchestration tests.** Starting from one synthetic failure, require:
  1. autopsy exact failure point;
  2. persisted hypotheses;
  3. minimal target/sham plan;
  4. compiled counterfactual requests sharing the same parent state;
  5. failed treatment creates a child snapshot;
  6. child can be autopsied into a new program while parent evidence remains unchanged;
  7. successful treatment + failed sham localizes a mechanism and emits MOVEMENT;
  8. all records remain selectable as one originating failure family.

- [ ] **7.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_lab.py -v
```

- [ ] **7.3 Implement pure preparation first.** `prepare()` may not construct adapters, touch network APIs, or execute inference. It should be fast enough to plan selected historical fixtures directly from `TEST_REPLAY` + verified assets.

- [ ] **7.4 Implement fake-adapter execution and child feedback.** Reuse `ReplayExecutor`; do not add a second replay engine.

- [ ] **7.5 Add CLI inspection commands and hard execution gate.** `run-lab` imports/constructs model adapters only after explicit `--allow-model-calls`, mirroring `execute-replay`.

- [ ] **7.6 Run green tests and CLI inspection.**

```bash
pytest tests/test_capability_ratchet_lab.py tests/test_capability_ratchet_query_cli.py -q
python -m inverted.capability_ratchet.cli autopsy --replay-root runs/v3-v2-seed-check --causal-root runs/v3-causal-preflight --snapshot-id failure-v2-020e7c8f3691554298ec16cd
```

For automated tests, use a synthetic fixture ID. Do not run live model execution.

- [ ] **7.7 Commit.**

```bash
git add src/inverted/capability_ratchet/lab.py src/inverted/capability_ratchet/cli.py tests/test_capability_ratchet_lab.py tests/test_capability_ratchet_query_cli.py
git commit -m "feat: orchestrate failure causal research programs"
```

---

### Task 8: Prove the planted mechanism can be recovered while the sham is rejected

**Files:**
- Create: `tests/test_capability_ratchet_causal_preflight.py`
- Modify: `src/inverted/capability_ratchet/__init__.py` only for final stable Plan 2 exports.
- Modify: `scripts/audit-v3-replay-foundation.py` to add Plan 2 scientific-surface checks without weakening Plan 1 checks.

**Interfaces:**
- Synthetic preflight is the completion gate for Plan 2.

- [ ] **8.1 Build a planted causal failure.** Create a deterministic fake adapter whose failure is repaired only when a registered dependency representation is present. A byte/shape-matched sham must fail. A compound branch must be decomposable by leave-one-out ablation. No real transport object may be constructed.

```python
def test_planted_mechanism_is_recovered_and_sham_rejected(tmp_path, monkeypatch):
    forbid_real_qwen(monkeypatch)
    lab, root = planted_dependency_lab(tmp_path)
    program = lab.prepare(root.failure_snapshot_id)
    result = lab.execute(program, adapters={"fake-model": planted_adapter()})
    assert result.assessment.supported_hypotheses
    assert result.sham_results and not any(r.semantic_pass for r in result.sham_results)
    assert any(label.role in {MechanismRole.REQUIRED, MechanismRole.ENABLER}
               for label in result.assessment.labels)
    assert result.model_calls_are_fake_only
```

- [ ] **8.2 Add negative controls.** Prove:
  - target+sham both passing remains unresolved;
  - target failing does not earn MOVEMENT;
  - a failed child treatment becomes a new replay fixture rather than a retry overwrite;
  - one branch cannot compare against a different parent state;
  - protected exploration cannot be pruned away;
  - historical fixture cannot become FRESH/SEALED;
  - real Qwen/Ollama/network constructors are booby-trapped.

- [ ] **8.3 Run the complete Plan 2 focused suite.**

```bash
pytest tests/test_capability_ratchet_causal_core.py tests/test_capability_ratchet_causal_store.py tests/test_capability_ratchet_autopsy.py tests/test_capability_ratchet_interventions.py tests/test_capability_ratchet_tournament.py tests/test_capability_ratchet_mechanisms.py tests/test_capability_ratchet_lab.py tests/test_capability_ratchet_causal_preflight.py -q
```

- [ ] **8.4 Run all Plan 1 + Plan 2 capability-ratchet tests and explicit V2 regressions.**

```bash
pytest tests/test_capability_ratchet_*.py -q
pytest tests/test_universal_tuning_end_to_end.py tests/test_universal_tuning_qwen_cli.py tests/test_universal_tuning_runner.py tests/test_universal_tuning_scheduler.py tests/test_universal_tuning_scoring.py tests/test_universal_tuning_statistics.py tests/test_universal_tuning_tasks.py tests/test_universal_tuning_v1_audit.py tests/test_qwen_thinking_tuning.py -q
```

- [ ] **8.5 Run repository and evidence integrity gates.**

```bash
pytest -q
git diff --check
python scripts/audit-v3-replay-foundation.py --source live-evidence/qwen-thinking-tuning-v2-real-20260907 --replay-root runs/v3-task8-final-check-20260907
git status --short
```

Expected: all prior baselines remain green; Plan 1 audit remains `forgotten_count=0`; generated runs/caches remain unstaged; `MODEL_CALLS=0` for all preflight/audit commands.

- [ ] **8.6 Zero-call plan a small real historical cohort.** Seed/validate the already-proven replay corpus if needed, select 5 historical failures, and run `autopsy` + `plan-lab` only. Confirm the output includes exact divergence evidence, hypothesis IDs, intervention IDs, sham/control membership, projected physical-call geometry, and `MODEL_CALLS=0`.

- [ ] **8.7 Commit Plan 2 completion.**

```bash
git add src/inverted/capability_ratchet scripts/audit-v3-replay-foundation.py tests/test_capability_ratchet_*.py
git commit -m "test: validate V3 causal failure laboratory"
```

---

## Plan 2 Completion Gate

Plan 2 is complete only when all are true:

1. A canonical failure can be autopsied from replay assets without the original campaign directory.
2. The earliest supported divergence is recorded with exact observable evidence/path rather than an unsupported narrative diagnosis.
3. Each live hypothesis is falsifiable and bound to one immutable failure state.
4. Tailored interventions are hypothesis-specific and never generic retries.
5. Target and matched sham/control branches share the same parent state and registered changed-dimension geometry.
6. The tournament planner selects the smallest decision-changing set and preserves protected exploration.
7. Successful compounds generate leave-one-out ablations/sham geometry without full-power-set explosion.
8. Failed interventions remain child failure snapshots and can seed a new autopsy/research program.
9. Mechanism localization distinguishes required/enabling/synergistic/suppressive/redundant/harmful/unresolved evidence, and `mechanism-graph.json` is deterministically rebuildable from canonical append-only evidence.
10. A target that does not beat its sham cannot become a causal mechanism.
11. Single-instance causal movement can emit MOVEMENT but cannot emit TIER_CANDIDATE/CERTIFIED.
12. `TEST_REPLAY.jsonl` retains the immutable failure plus all replay requests/results/mechanism/promotion lineage.
13. `causal-hypotheses.jsonl` and `intervention-registry.json` are hash/integrity validated and cannot silently drift from replay lineage.
14. A planted causal mechanism is recovered while its matched sham is rejected.
15. A failed replay creates useful new evidence instead of triggering blind retry behavior.
16. Real Qwen/Ollama/network calls remain zero throughout Plan 2 preflight and repository validation.
17. All Plan 1, Plan 2, V2 regression, full repository, and integrity gates remain green.

## Deliberate Scope Boundary

Plan 2 does **not** implement Stage 5 operating-surface deepening, Stage 6 failure mutation/generalization, Stage 7 tool/skill/recovery tomography, Stage 8 capability compilation, production routing/controller training, or fine-tuning. Those become Plan 3+ only after the causal laboratory can recover a planted mechanism, reject its sham, preserve lineage, and convert failed treatments into new reusable research fixtures.
