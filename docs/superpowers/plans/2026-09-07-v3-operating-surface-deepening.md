# V3 Adaptive Operating-Surface Deepening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Characterize only causal mechanisms that earned `MOVEMENT` (or remain explicitly decision-critical) deeply enough to learn the smallest robust operating region—especially Qwen reasoning amount/limits, saturation and harm boundaries, temperature only where cognition is causal, and representation/order/timing/context-delivery effects—without spending calls on exhaustive grids or promoting single-instance evidence beyond `MOVEMENT`.

**Architecture:** Extend the proven Plan 1 replay kernel and Plan 2 causal laboratory. Surface characterization is scientific metadata over immutable `FailureFixture`/`MechanismLabel` lineage; every executable point compiles to an existing registered `InterventionDefinition` and `COUNTERFACTUAL` `ReplayRequest`, so `TEST_REPLAY.jsonl` remains the only replay source of truth. A deterministic evidence compiler reuses same-state replay evidence and V2 historical budget/temperature evidence before scheduling; an adaptive planner brackets useful/harmful regions one axis at a time, preserves protected exploration, and stops when another point cannot change the operating/routing decision.

**Tech Stack:** Python 3.14, frozen dataclasses/enums, canonical JSON/SHA-256, existing `ReplayStore`, `CausalEvidenceStore`, `InterventionDefinition`, `ReplayExecutor`, V2 paired clustered bootstrap/statistics, pytest, existing Qwen/Ollama replay adapter behind explicit live-call gates only.

**Spec:** `docs/superpowers/specs/2026-09-07-universal-capability-ratchet-v3-design.md`

## Global Constraints

- No real model/network/Ollama call may run during Plan 3 implementation, regression, or preflight.
- Existing evidence is checked before any proposed surface point; a call is invalid if valid stored evidence already settles the same decision.
- Only mechanisms at `MOVEMENT`, or an explicitly recorded decision-critical mechanism with a reason, may enter Stage 5.
- Plan 3 may not emit `TIER_CANDIDATE` or `CERTIFIED`; Stage 6 neighborhood generalization is required before either.
- Same-state causal evidence is distinguished from historical/observational priors. A prior may change point ordering but cannot masquerade as a same-parent intervention result.
- No Cartesian product over budget × temperature × representation × delivery. Characterize one causal axis at a time unless a preregistered interaction is already supported by Plan 2 evidence.
- Temperature characterization is forbidden until reasoning/cognition has demonstrated causal relevance for that mechanism/state.
- Representation-only comparisons must preserve a deterministic semantic-contract hash; changing meaning invalidates the representation-only claim.
- Timing/latency noise cannot select a cognitive optimum. Semantic/contract/completion evidence and preregistered efficiency thresholds drive decisions.
- Negative transfer is first-class evidence. A surface that helps locally and harms elsewhere becomes conditional; it is never promoted into a global always-think/always-context policy.
- Fresh and sealed partitions remain immutable and unavailable to development characterization.
- Failed surface replays remain replay evidence and become child failure fixtures through the existing replay executor; no blind retry path is added.
- Protected exploration must retain at least one scientifically admissible unusual/extreme point when pruning would otherwise erase it.
- Every planned physical call has a named decision reason and must be capable of changing a lower/upper useful bound, harm boundary, robust band, ownership, or routing decision.
- Call geometry is computed before execution: minimum, expected adaptive, worst case, and protected-exploration reserve.

## File Structure

- Create `src/inverted/capability_ratchet/surface_core.py` — frozen Stage-5 contracts: axes, point/study identities, evidence provenance, operating bands/profiles, call geometry.
- Create `src/inverted/capability_ratchet/surface_store.py` — append-only/hash-validated Stage-5 scientific metadata; references canonical replay records rather than duplicating them.
- Create `src/inverted/capability_ratchet/surface_evidence.py` — same-state replay reuse plus V2 historical budget/temperature prior compiler.
- Create `src/inverted/capability_ratchet/surface_planner.py` — adaptive axis eligibility, bracketing, pruning, protected exploration, stopping, and call accounting.
- Create `src/inverted/capability_ratchet/surface_interventions.py` — compile one surface point into registered `InterventionDefinition` + existing `ReplayRequest` dimensions.
- Create `src/inverted/capability_ratchet/surface_analysis.py` — infer robust band, lower useful bound, plateau/saturation, harm onset, negative-transfer boundary, and unresolved edges using paired evidence.
- Create `src/inverted/capability_ratchet/surface_lab.py` — prepare/execute one adaptive characterization step using existing replay infrastructure.
- Modify `src/inverted/capability_ratchet/cli.py` — add inspection-only `plan-surface`/`show-surface` and explicit-gated `run-surface`.
- Modify `src/inverted/capability_ratchet/query.py` and `__init__.py` only where stable surface selection/exports are needed.
- Create tests `tests/test_capability_ratchet_surface_core.py`, `..._surface_store.py`, `..._surface_evidence.py`, `..._surface_planner.py`, `..._surface_interventions.py`, `..._surface_analysis.py`, `..._surface_lab.py`, `..._surface_preflight.py`.

---

### Task 1: Freeze operating-surface scientific contracts and Stage-5 eligibility

**Files:**
- Create: `src/inverted/capability_ratchet/surface_core.py`
- Test: `tests/test_capability_ratchet_surface_core.py`

**Interfaces:**
- Produces `SurfaceAxis`, `SurfaceEvidenceKind`, `SurfaceDisposition`, `SurfacePoint`, `SurfaceStudy`, `SurfaceObservation`, `SurfaceBand`, `SurfaceCallGeometry`, `OperatingSurfaceProfile`.
- Consumes existing `PromotionState`, `Partition`, `MechanismLabel`, `MechanismRole` only by ID/state; it does not mutate canonical replay records.

- [ ] **1.1 Write failing frozen-contract tests.** Require deterministic IDs, JSON-safe frozen fields, unique point values, exact source `failure_snapshot_id`/`mechanism_id`/`parent_state_hash`, immutable partition, decision IDs, protected-exploration flag, and explicit evidence kind (`SAME_STATE_CAUSAL` vs `HISTORICAL_PRIOR`). Require Stage-5 eligibility to reject `UNASSESSED`, `REJECTED`, `FRESH`, and `SEALED` inputs unless no execution is requested.

```python
def test_surface_study_requires_movement_or_decision_critical_reason():
    with pytest.raises(ValueError, match="MOVEMENT"):
        SurfaceStudy.create(
            failure_snapshot_id="failure-1",
            mechanism_id="mechanism-1",
            parent_state_hash="a" * 64,
            partition=Partition.HISTORICAL,
            promotion_state=PromotionState.UNASSESSED,
            decision_id="D3",
            axes=(SurfaceAxis.REASONING_BUDGET,),
            axis_values={"REASONING_BUDGET": (0, 512, 1024, 2048)},
        )
```

- [ ] **1.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_surface_core.py -v
```

Expected: import failure because `surface_core` does not exist.

- [ ] **1.3 Implement minimal frozen contracts.** Use deterministic SHA-256 IDs over canonical payloads. `SurfacePoint` identifies one axis/value on one immutable parent state; `SurfaceStudy` carries allowed values but no results; `SurfaceObservation` references canonical replay result IDs or immutable V2 evidence refs; `OperatingSurfaceProfile` records evidence-derived bounds only.

Required enums:

```python
class SurfaceAxis(str, Enum):
    REASONING_BUDGET = "REASONING_BUDGET"
    TEMPERATURE = "TEMPERATURE"
    CONTEXT_DOSE = "CONTEXT_DOSE"
    REPRESENTATION = "REPRESENTATION"
    ORDER = "ORDER"
    RECURRENCE = "RECURRENCE"
    TIMING = "TIMING"
    PLACEMENT = "PLACEMENT"
    CONTEXT_POSITION = "CONTEXT_POSITION"
    DELIVERY_MODE = "DELIVERY_MODE"
    TRIGGER_MODE = "TRIGGER_MODE"

class SurfaceDisposition(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    USEFUL_BAND = "USEFUL_BAND"
    PLATEAU = "PLATEAU"
    SATURATED = "SATURATED"
    HARM_BOUNDARY = "HARM_BOUNDARY"
    NEGATIVE_TRANSFER = "NEGATIVE_TRANSFER"
    NO_USEFUL_REGION = "NO_USEFUL_REGION"
```

`OperatingSurfaceProfile` must include `lower_useful`, `upper_useful`, `recommended_region`, `harm_onset`, `evidence_refs`, `unresolved_edges`, and `promotion_ceiling=PromotionState.MOVEMENT`.

- [ ] **1.4 Run green tests.**

```bash
pytest tests/test_capability_ratchet_surface_core.py -q
```

- [ ] **1.5 Commit.**

```bash
git add src/inverted/capability_ratchet/surface_core.py tests/test_capability_ratchet_surface_core.py
git commit -m "feat: define V3 operating surface contracts"
```

---

### Task 2: Add append-only operating-surface metadata storage

**Files:**
- Create: `src/inverted/capability_ratchet/surface_store.py`
- Test: `tests/test_capability_ratchet_surface_store.py`

**Interfaces:**
- `SurfaceEvidenceStore(root: Path, replay_store: ReplayStore, causal_store: CausalEvidenceStore)`
- `append_study(study) -> str`
- `append_observation(observation) -> str`
- `append_profile(profile) -> str`
- `studies(mechanism_id=None)`, `observations(study_id=None)`, `profiles(mechanism_id=None)`
- `validate() -> SurfaceStoreValidation`
- Canonical metadata files: `surface-studies.jsonl`, `surface-observations.jsonl`, `operating-surface-profiles.jsonl`, each with SHA manifest.

- [ ] **2.1 Write failing durability/lineage tests.** Prove idempotent identical append, no logical-ID rewrite, manifest tamper detection, no observation referencing an unknown study, no same-state causal observation referencing a missing `ReplayResult`, historical-prior rows require immutable source refs instead of fake replay IDs, and profile evidence refs must resolve to stored observations.

- [ ] **2.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_surface_store.py -v
```

- [ ] **2.3 Implement canonical append-only stores and cross-store validation.** `TEST_REPLAY.jsonl` remains canonical for executable replay lineage; this store contains only Stage-5 scientific metadata and may be rebuilt/validated from its own manifests plus referenced canonical IDs.

- [ ] **2.4 Run green + replay/causal store regressions.**

```bash
pytest tests/test_capability_ratchet_surface_store.py tests/test_capability_ratchet_replay_store.py tests/test_capability_ratchet_causal_store.py -q
```

- [ ] **2.5 Commit.**

```bash
git add src/inverted/capability_ratchet/surface_store.py tests/test_capability_ratchet_surface_store.py
git commit -m "feat: persist operating surface evidence"
```

---

### Task 3: Compile existing evidence before authorizing new surface points

**Files:**
- Create: `src/inverted/capability_ratchet/surface_evidence.py`
- Test: `tests/test_capability_ratchet_surface_evidence.py`

**Interfaces:**
- `SurfaceEvidenceCompiler(replay_store, causal_store, surface_store)`
- `same_state_observations(study) -> tuple[SurfaceObservation, ...]`
- `compile_v2_priors(source: V2EvidenceSource, study) -> tuple[SurfaceObservation, ...]`
- `answered_points(study) -> frozenset[str]`

- [ ] **3.1 Write red evidence-reuse tests.** A completed replay point on the same `parent_state_hash`, mechanism lineage, axis and value must be reused with zero calls. Evidence from another parent state may be imported only as `HISTORICAL_PRIOR`. V2 reasoning-budget and temperature evidence may order Stage-5 candidates but may not mark a same-state point answered unless provenance/state identity actually matches.

```python
def test_historical_prior_cannot_satisfy_same_state_point(tmp_path):
    compiler, study = planted_prior_case(tmp_path)
    priors = compiler.compile_v2_priors(study.source, study)
    assert priors
    assert all(row.evidence_kind is SurfaceEvidenceKind.HISTORICAL_PRIOR for row in priors)
    assert compiler.answered_points(study) == frozenset()
```

- [ ] **3.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_surface_evidence.py -v
```

- [ ] **3.3 Implement deterministic evidence matching.** Reuse V2 `Profile`/raw observation fields and immutable evidence refs. Record semantic, contract, completion, reasoning-cap/natural-stop, thinking/output tokens, and physical-call cost where available. Never infer hidden reasoning quality from inaccessible chain-of-thought.

- [ ] **3.4 Prove duplicate evidence compilation is idempotent and zero-call.**

```bash
pytest tests/test_capability_ratchet_surface_evidence.py tests/test_capability_ratchet_historical.py -q
```

- [ ] **3.5 Commit.**

```bash
git add src/inverted/capability_ratchet/surface_evidence.py tests/test_capability_ratchet_surface_evidence.py
git commit -m "feat: reuse historical evidence for surface studies"
```

---

### Task 4: Build adaptive one-axis characterization and stopping logic

**Files:**
- Create: `src/inverted/capability_ratchet/surface_planner.py`
- Test: `tests/test_capability_ratchet_surface_planner.py`

**Interfaces:**
- `SurfacePlanner(surface_store, evidence_compiler)`
- `eligible_axes(study, mechanism, hypothesis, intervention) -> tuple[SurfaceAxis, ...]`
- `plan_next(study, *, max_new_points=2) -> SurfacePlan`
- `SurfacePlan(points, decision_reason, minimum_physical_calls, expected_physical_calls, worst_case_physical_calls, protected_exploration_calls, stop_reason)`

- [ ] **4.1 Write failing axis-gating tests.** Cognition mechanisms can expose `REASONING_BUDGET`; `TEMPERATURE` remains blocked until same-lineage evidence establishes cognition relevance. Context mechanisms expose dose/position/delivery axes; representation mechanisms expose representation/order/placement; delivery mechanisms expose timing/recurrence/trigger axes. Unrelated axes are rejected.

- [ ] **4.2 Write failing adaptive bracketing tests.** For ordered numeric values, prioritize the smallest unresolved point capable of moving the lower useful bound, then an upper probe capable of detecting saturation/harm. Reuse answered points, do not emit the full set, and preserve one protected extreme/unusual point when scientifically admissible.

Example planted budget values:

```python
study = surface_study(axis_values={
    "REASONING_BUDGET": (0, 256, 512, 1024, 2048, 4096, 8192)
})
plan = planner.plan_next(study, max_new_points=2)
assert len(plan.points) <= 2
assert plan.worst_case_physical_calls < 7 * calls_per_point
```

- [ ] **4.3 Write decision-value stopping tests.** Stop when all admissible remaining points cannot change the robust band, harm boundary, mechanism ownership, or routing decision. Do not schedule additional points merely to increase N. A flat plateau must stop without inventing a single optimum.

- [ ] **4.4 Implement planner using V2 statistical constants, not V2 campaign scheduling.** Reuse `SUPERIORITY_MARGIN=0.05`, `NONINFERIORITY_MARGIN=-0.02`, paired evidence concepts, and checkpoints where applicable. Do not modify V2 `AdaptiveScheduler` behavior.

- [ ] **4.5 Run green tests plus V2 scheduler/statistics regressions.**

```bash
pytest tests/test_capability_ratchet_surface_planner.py tests/test_universal_tuning_scheduler.py tests/test_universal_tuning_statistics.py -q
```

- [ ] **4.6 Commit.**

```bash
git add src/inverted/capability_ratchet/surface_planner.py tests/test_capability_ratchet_surface_planner.py
git commit -m "feat: adaptively plan operating surface probes"
```

---

### Task 5: Compile surface points into registered causal replay interventions

**Files:**
- Create: `src/inverted/capability_ratchet/surface_interventions.py`
- Test: `tests/test_capability_ratchet_surface_interventions.py`

**Interfaces:**
- `SurfaceInterventionCompiler(replay_store, causal_store)`
- `compile_point(study, point, *, request_id, decision_id) -> tuple[InterventionDefinition, ReplayRequest]`
- `semantic_contract_hash(payload) -> str`

- [ ] **5.1 Write red leaf-fidelity tests.** Reasoning budget changes only the registered thinking request `options.num_predict` leaf; temperature changes only `options.temperature`; direct/thinking transition changes only preregistered `think` plus its compatibility-required option leaves and is labeled as such. All non-target request bytes remain equal.

- [ ] **5.2 Write representation/delivery integrity tests.** A representation-only point must carry the same semantic-contract hash as baseline. Order/timing/placement/recurrence points must declare exact changed message/context leaves. If meaning changes, compilation must reject the `REPRESENTATION` claim.

- [ ] **5.3 Implement compilation through existing `InterventionDefinition` and `ReplayRequest`.** Never create a second execution schema. Register intervention metadata in `CausalEvidenceStore`, then compile `COUNTERFACTUAL` requests with exact declared dimensions. Existing `ReplayExecutor` remains the enforcement layer.

- [ ] **5.4 Run green + replay/intervention fidelity regressions.**

```bash
pytest tests/test_capability_ratchet_surface_interventions.py tests/test_capability_ratchet_interventions.py tests/test_capability_ratchet_replay.py tests/test_capability_ratchet_qwen_replay.py -q
```

- [ ] **5.5 Commit.**

```bash
git add src/inverted/capability_ratchet/surface_interventions.py tests/test_capability_ratchet_surface_interventions.py
git commit -m "feat: compile surface points into causal replays"
```

---

### Task 6: Infer robust bands, saturation, and negative-transfer boundaries

**Files:**
- Create: `src/inverted/capability_ratchet/surface_analysis.py`
- Test: `tests/test_capability_ratchet_surface_analysis.py`

**Interfaces:**
- `SurfaceAnalyzer(surface_store)`
- `analyze(study_id) -> OperatingSurfaceProfile`
- Uses paired same-parent evidence where available; priors may be reported separately but cannot create a causal bound.

- [ ] **6.1 Write planted threshold-band tests.** Example: 0/256 fail, 512/1024/2048 succeed, 4096 plateaus, 8192 degrades. Require lower useful bound near 512, robust region containing 512–2048/4096 according to paired margins, and explicit harm onset at 8192 rather than “more thinking is better.”

- [ ] **6.2 Write plateau/no-false-precision tests.** Equal outcomes across temperatures produce `PLATEAU` with a recommended region, not a fake optimum chosen from latency jitter. Timing may break ties only when a preregistered material efficiency threshold is met while capability is statistically noninferior.

- [ ] **6.3 Write negative-transfer tests.** A mechanism that helps its source state but harms a protected control region yields `NEGATIVE_TRANSFER` and a conditional boundary. The profile must prohibit global routing metadata.

- [ ] **6.4 Implement paired analysis by reusing V2 clustered bootstrap utilities.** Keep semantic, contract, completion, reasoning-cap exhaustion, token and physical-call outcomes distinct. Persist the profile append-only through `SurfaceEvidenceStore`.

- [ ] **6.5 Run green + statistics regression.**

```bash
pytest tests/test_capability_ratchet_surface_analysis.py tests/test_universal_tuning_statistics.py -q
```

- [ ] **6.6 Commit.**

```bash
git add src/inverted/capability_ratchet/surface_analysis.py tests/test_capability_ratchet_surface_analysis.py
git commit -m "feat: characterize robust mechanism operating bands"
```

---

### Task 7: Orchestrate adaptive characterization and add safe CLI surfaces

**Files:**
- Create: `src/inverted/capability_ratchet/surface_lab.py`
- Modify: `src/inverted/capability_ratchet/cli.py`
- Modify: `src/inverted/capability_ratchet/query.py`
- Test: `tests/test_capability_ratchet_surface_lab.py`
- Test: `tests/test_capability_ratchet_query_cli.py`

**Interfaces:**
- `OperatingSurfaceLab.prepare(study_id) -> SurfacePlan`
- `OperatingSurfaceLab.execute(plan, adapters) -> SurfaceStepResult`
- CLI `plan-surface --replay-root ... --causal-root ... --surface-root ... --mechanism-id ...`
- CLI `show-surface ...`
- CLI `run-surface ... --allow-model-calls` hard gate.

- [ ] **7.1 Write red lab tests with `FakeReplayAdapter`.** Prepare must reuse stored points, compile only new decision-changing points, append requests/results through the existing replay executor, capture failed point descendants, append surface observations, analyze the updated profile, and return the next adaptive decision without automatic retry.

- [ ] **7.2 Write CLI zero-call/gating tests.** `plan-surface` and `show-surface` must report `MODEL_CALLS=0`. `run-surface` must reject before model-adapter construction unless `--allow-model-calls` is explicit. Cross-check that plan output includes min/expected/worst/protected-exploration call geometry.

- [ ] **7.3 Implement orchestration with no new transport path.** Live execution may construct `QwenReplayAdapter` only after the explicit gate. Synthetic/preflight tests monkeypatch real Qwen/Ollama/network constructors to raise.

- [ ] **7.4 Run green capability-ratchet CLI/lab regressions.**

```bash
pytest tests/test_capability_ratchet_surface_lab.py tests/test_capability_ratchet_query_cli.py tests/test_capability_ratchet_lab.py -q
```

- [ ] **7.5 Commit.**

```bash
git add src/inverted/capability_ratchet/surface_lab.py src/inverted/capability_ratchet/cli.py src/inverted/capability_ratchet/query.py tests/test_capability_ratchet_surface_lab.py tests/test_capability_ratchet_query_cli.py
git commit -m "feat: orchestrate adaptive surface characterization"
```

---

### Task 8: Prove Stage-5 characterization end to end with zero inference

**Files:**
- Create: `tests/test_capability_ratchet_surface_preflight.py`
- Modify: `src/inverted/capability_ratchet/__init__.py` only for final stable Plan-3 exports.
- Modify: `scripts/audit-v3-replay-foundation.py` only to add Stage-5 surface integrity checks; Plan-1/2 checks may not be weakened.

- [ ] **8.1 Build planted synthetic mechanisms.** Include: (a) reasoning threshold + useful band + high-budget harm; (b) flat temperature plateau; (c) representation-only effect whose semantic-contract hash is preserved; (d) local benefit with protected-region negative transfer; (e) an already-answered replay point that must be reused with no fake adapter invocation.

- [ ] **8.2 Prove adaptive economics.** Assert the planner resolves planted surfaces with fewer points than exhaustive enumeration, retains protected exploration, computes minimum/expected/worst physical calls, and never schedules a branch whose possible outcomes cannot change a named decision.

- [ ] **8.3 Prove promotion boundary.** Even a clean robust Stage-5 profile remains capped at `MOVEMENT`; any attempt to emit `TIER_CANDIDATE` or `CERTIFIED` fails because Stage 6 neighborhood evidence does not exist.

- [ ] **8.4 Run all Stage-5 focused tests.**

```bash
pytest tests/test_capability_ratchet_surface_*.py -q
```

- [ ] **8.5 Run all Plan 1 + Plan 2 + Plan 3 capability-ratchet tests and explicit V2 regressions.**

```bash
pytest tests/test_capability_ratchet_*.py -q
pytest tests/test_universal_tuning_end_to_end.py tests/test_universal_tuning_qwen_cli.py tests/test_universal_tuning_runner.py tests/test_universal_tuning_scheduler.py tests/test_universal_tuning_scoring.py tests/test_universal_tuning_statistics.py tests/test_universal_tuning_tasks.py tests/test_universal_tuning_v1_audit.py tests/test_qwen_thinking_tuning.py -q
```

- [ ] **8.6 Run repository/integrity/privacy gates.**

```bash
pytest -q
git diff --check
python -m inverted.evidence_privacy check --root evidence --scan-out runs/v3-plan3-privacy.json
python scripts/audit-v3-replay-foundation.py --source live-evidence/qwen-thinking-tuning-v2-real-20260907 --replay-root runs/v3-plan3-replay-check
git status --short
```

Expected: all existing Plan-1/2/V2/full-repo baselines remain green; privacy matches 0; replay audit `forgotten_count=0`; generated `runs/` remain unstaged; all implementation/preflight commands report/perform `MODEL_CALLS=0`.

- [ ] **8.7 Zero-call plan real historical Stage-5 candidates.** Rebuild/validate the historical replay corpus, select mechanisms with `MOVEMENT` evidence when present, compile V2 budget/temperature priors, and run `plan-surface` only. Output must show which points were reused, which remain unresolved, why each proposed point can change D3/D4/D5/D9, projected physical-call geometry, and `MODEL_CALLS=0`. If no durable real `MOVEMENT` mechanism exists in the rebuilt zero-call corpus, emit an explicit `NO_ELIGIBLE_MECHANISMS` result rather than manufacturing eligibility.

- [ ] **8.8 Commit Plan 3 completion.**

```bash
git add src/inverted/capability_ratchet scripts/audit-v3-replay-foundation.py tests/test_capability_ratchet_*.py
git commit -m "test: validate V3 operating surface characterization"
```

---

## Plan 3 Completion Gate

Plan 3 is complete only when all are true:

1. Stage-5 eligibility is limited to `MOVEMENT` or explicitly decision-critical mechanisms and cannot consume FRESH/SEALED evidence for tuning.
2. Existing same-state replay evidence is reused before any new point is proposed; V2 historical evidence is retained as a prior without being mislabeled causal.
3. Reasoning-budget characterization identifies useful lower bounds, saturation/plateau, and harmful overthinking regions rather than assuming more reasoning is better.
4. Temperature is characterized only where cognition is already causally relevant.
5. Representation-only evidence preserves semantic meaning by deterministic contract hash.
6. Order, recurrence, timing, placement, context position, progressive delivery, and trigger mode are available only when supported by the originating mechanism/hypothesis.
7. The planner does not execute a Cartesian grid and stops when additional points cannot change a named decision.
8. Protected exploration survives pruning.
9. Every executable surface point is an existing-style registered `InterventionDefinition` + `COUNTERFACTUAL` `ReplayRequest`; no competing replay schema exists.
10. Failed surface points become child failure fixtures rather than blind retries.
11. Paired analysis distinguishes semantic, contract, completion, reasoning-cap, token/call, and negative-transfer effects.
12. Plateaus remain plateaus; timing noise cannot manufacture an optimum.
13. Negative-transfer evidence produces a conditional boundary and blocks global always-think/always-context routing.
14. Every profile records exact source mechanism/failure/state lineage, evidence refs, robust region, harm onset, unresolved edges, and cost geometry.
15. Plan 3 cannot emit `TIER_CANDIDATE` or `CERTIFIED`; Stage 6 generalization remains mandatory.
16. Synthetic preflight recovers a planted Qwen-like reasoning band and high-budget harm while using fewer probes than exhaustive enumeration.
17. Real historical characterization planning is possible with zero model calls and never manufactures eligible mechanisms.
18. All Plan 1, Plan 2, Plan 3, V2, full-repository, replay-integrity, and privacy gates remain green.

## Deliberate Scope Boundary

Plan 3 ends after Stage 5 operating-surface characterization. It does **not** generate neighborhood mutations, promote mechanisms to `TIER_CANDIDATE`, perform tool/skill/recovery tomography, compile production capability ownership, build a controller, or qualify fine-tuning. Stage 6 receives `OperatingSurfaceProfile` as its input and tests whether the discovered local operating region survives deterministic causal-preserving mutations before any broader promotion.