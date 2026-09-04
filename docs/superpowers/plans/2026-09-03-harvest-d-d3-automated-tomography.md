# Harvest D D3 Automated Tomography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable, automation-first Harvest D D3 campaign that can spend up to 1,000 admissible physical local-model calls to causally identify minimum useful information, deterministic assistance, recovery support, and model-size substitution while preserving every expensive observation for later deterministic re-analysis.

**Architecture:** Extend the existing isolated `src/inverted/harvest_d/` package with focused D3 modules rather than expanding `local_run.py` into a monolith. D3 uses an append-only event/journal store, typed experiment conditions, deterministic packet/assistance/recovery transforms, an adaptive scheduler with a protected randomized exploration stream, anytime-valid sequential inference, a single-call/no-blind-retry executor, crash-safe resume semantics, and derived analyzers that produce the normative D3 outputs. Normal CI remains fully model-free; real Ollama calls are only reachable through the explicit D3 launcher after preflight passes.

**Tech Stack:** Python 3.11+ standard library, existing `httpx`/PyYAML dependencies only where already present, pytest, PowerShell launcher, GitHub Actions. No new runtime dependency unless a later failing requirement cannot be met with the standard library.

**Spec:** `docs/superpowers/specs/2026-09-03-harvest-d-d3-automated-information-control-tomography.md`

**Normative addenda:**
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-data-capture-addendum.md`
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-independent-frontier-review-addendum.md`
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-research-delta-addendum.md`
- `docs/superpowers/specs/2026-09-02-harvest-d-cpu-sentinel-addendum.md`

## Global Constraints

- Frozen Harvest D base lineage remains `0d67ba4e5578b4c14225eb83b726fd137dfffecd`; prior evidence is never rewritten.
- D3 hard ceiling is **1,000 admissible physical model calls**; deterministic replay, scoring, analysis, and system-only events cost zero calls.
- D3 phase reservoirs are: D3.1=80, D3.2=150, D3.3=120, D3.4=150, D3.5=150, D3.6=160, D3.7=90, D3.8=100; D3.8 is protected from development reallocation.
- Phase numbers are adaptive reservoirs, not quotas. Unused unsealed calls may be reallocated only through a recorded scheduler decision.
- Automation is the default. Human/operator intervention is required only for hard-stop conditions, provenance-changing decisions, or actions that would alter experimental truth.
- Every model call has exactly one globally unique `physical_model_call_id`; blind retries are forbidden.
- Unknown external effect requires reconciliation before any retry that could duplicate an irreversible effect.
- Models never receive hidden oracle values, expected answers, sealed annotations, or future outcomes.
- Models may propose; deterministic/system-owned components own authority, admission, state transition, final verification, and promotion.
- Raw evidence is immutable and losslessly retained. Normalized and derived layers are append-only/recomputable and never overwrite raw evidence.
- A call is promotion-admissible only after required capture is durably committed and validated; `CAPTURE_INCOMPLETE` calls remain diagnostic evidence.
- Normal CI must require no Ollama daemon, GPU, cloud API, network credentials, or paid service.
- D3 must preserve opportunity sets/non-events, missingness reasons, runtime carryover/order metadata, structural case features, normalized behavior features, causal claim edges, coverage/saturation, protocol deviations, assumptions, and safe unknown fields.
- The controller may choose among preregistered moves but may not rewrite oracles, success criteria, sealed cases, authority, prior events, or retry until success.
- Pure context-length controls, a protected randomized exploration stream, and decomposed detection→diagnosis→recovery-selection→execution→verification telemetry are mandatory.
- CPU Sentinel remains a separate D3/D4 intervention seam; D3 may identify useful sentinel input fields but may not promote Sentinel without its S0/S1/S2+sham and verified CPU-residency gates.
- Promotion evidence depth targets remain approximately 12–16 broad screen, ~24 pursue, ~32–48 architecture candidate, ~48–64 promotion candidate, plus additional safety-critical adversarial exposure and zero hard-invariant violations.

---

### Task 1: Freeze D3 budget/configuration and protected reservoirs

**Files:**
- Modify: `src/inverted/harvest_d/campaign.py`
- Modify: `configs/harvest-d.json`
- Create: `src/inverted/harvest_d/d3_config.py`
- Create: `tests/test_harvest_d_d3_config.py`

**Interfaces:**
- Consumes: `HarvestDConfig`, existing Harvest D stage names.
- Produces: `D3Phase`, `D3_PHASE_RESERVOIRS`, `D3BudgetState`, `D3BudgetError`, `reserve_call(phase)`, `reallocate_calls(source, target, count, reason)`, `remaining_unsealed`, `sealed_remaining`.

- [ ] **Step 1: Write failing budget tests**

```python
from inverted.harvest_d.d3_config import D3BudgetError, D3BudgetState, D3Phase


def test_d3_budget_is_1000_with_protected_100_call_sealed_reserve():
    budget = D3BudgetState.default()
    assert budget.total_ceiling == 1000
    assert budget.phase_ceiling(D3Phase.SEALED_CONFIRMATION) == 100
    assert budget.sealed_remaining == 100


def test_discovery_cannot_borrow_from_sealed_reserve():
    budget = D3BudgetState.default()
    with pytest.raises(D3BudgetError):
        budget.reallocate_calls(D3Phase.SEALED_CONFIRMATION, D3Phase.INFORMATION, 1, reason="more power")


def test_reallocation_requires_reason_and_preserves_total_ceiling():
    budget = D3BudgetState.default()
    budget.reallocate_calls(D3Phase.REPRESENTATION, D3Phase.INFORMATION, 10, reason="representation futile")
    assert sum(budget.current_ceilings.values()) == 1000
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_harvest_d_d3_config.py`
Expected: FAIL because `d3_config` does not exist and current D3 ceiling is still 110.

- [ ] **Step 3: Implement immutable phase names and mutable campaign budget state**

```python
class D3Phase(str, Enum):
    BASELINE = "D3.1"
    INFORMATION = "D3.2"
    REPRESENTATION = "D3.3"
    ASSISTANCE = "D3.4"
    RECOVERY = "D3.5"
    COMBINED = "D3.6"
    NEGATIVE_TRANSFER = "D3.7"
    SEALED_CONFIRMATION = "D3.8"

D3_PHASE_RESERVOIRS = {
    D3Phase.BASELINE: 80,
    D3Phase.INFORMATION: 150,
    D3Phase.REPRESENTATION: 120,
    D3Phase.ASSISTANCE: 150,
    D3Phase.RECOVERY: 150,
    D3Phase.COMBINED: 160,
    D3Phase.NEGATIVE_TRANSFER: 90,
    D3Phase.SEALED_CONFIRMATION: 100,
}
```

Update `_DEFAULT_CEILINGS["D3"]` to `1000` and `primary_call_ceiling` to the Harvest D aggregate implied by the frozen stage ceilings after the D3 revision. Validation must reject any D3 config above 1,000 and any attempt to reduce the protected D3.8 reserve after campaign start.

- [ ] **Step 4: Run GREEN plus existing campaign tests**

Run: `python -m pytest -q tests/test_harvest_d_d3_config.py tests/test_harvest_d_campaign.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/harvest_d/campaign.py src/inverted/harvest_d/d3_config.py configs/harvest-d.json tests/test_harvest_d_d3_config.py
git commit -m "feat: freeze D3 adaptive 1000 call budget"
```

---

### Task 2: Define the D3 experiment, event, missingness, and trajectory schemas

**Files:**
- Create: `src/inverted/harvest_d/d3_types.py`
- Modify: `src/inverted/harvest_d/faults.py`
- Create: `tests/test_harvest_d_d3_types.py`

**Interfaces:**
- Consumes: `Disposition`, `RouteMode`, `FaultLayer`, `stable_hash`.
- Produces: `D3Condition`, `InformationField`, `InformationPacket`, `AssistanceCondition`, `RecoveryChoice`, `RecoveryStage`, `MissingnessReason`, `EvidenceAdmissibility`, `D3Event`, `SchedulerDecision`, `CallCaptureStatus`, `RecoveryTrajectory`, `CaseStructuralFeatures`, `ModelBehaviorFeatures`, `ProtocolViolation`, `AssumptionRecord`.

- [ ] **Step 1: Write failing schema tests**

```python
from inverted.harvest_d.d3_types import MissingnessReason, RecoveryStage, D3Event


def test_missingness_is_reason_coded_not_ambiguous_null():
    assert MissingnessReason.NOT_APPLICABLE.value == "NOT_APPLICABLE"
    assert MissingnessReason.NOT_EXPOSED_BY_RUNTIME.value == "NOT_EXPOSED_BY_RUNTIME"
    assert MissingnessReason.CAPTURE_INCOMPLETE.value == "CAPTURE_INCOMPLETE"


def test_recovery_stages_are_independently_observable():
    assert [x.value for x in RecoveryStage] == [
        "DETECTION", "DIAGNOSIS", "SELECTION", "ADMISSION", "EXECUTION", "VERIFICATION"
    ]


def test_event_hashes_model_visible_and_system_known_information_separately():
    event = D3Event.for_test(model_visible={"state": 1}, system_known={"state": 1, "secret_oracle": 9})
    assert event.model_visible_information_hash != event.system_known_information_hash
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_harvest_d_d3_types.py`
Expected: FAIL because the D3 schemas do not exist.

- [ ] **Step 3: Implement frozen enums/dataclasses**

`D3Event` must contain the normative identity/lineage, sequence/time, component/event type, pre/post state hashes, model-visible/system-known hashes, authority/evidence hashes, proposal/admission/recovery/verifier/effect fields, call ID, token/latency/runtime provenance, invariant/oracle status, and artifact references. Optional values must carry a `MissingnessReason` whenever absence is scientifically meaningful.

Extend `FaultLayer` with `GLOBAL_INTERACTION` and `NOVELTY` without removing existing values.

- [ ] **Step 4: Run GREEN plus fault regression**

Run: `python -m pytest -q tests/test_harvest_d_d3_types.py tests/test_harvest_d_core.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/harvest_d/d3_types.py src/inverted/harvest_d/faults.py tests/test_harvest_d_d3_types.py
git commit -m "feat: add D3 causal observability schemas"
```

---

### Task 3: Build the append-only evidence store and capture-completeness gate

**Files:**
- Create: `src/inverted/harvest_d/d3_store.py`
- Modify: `src/inverted/harvest_d/artifacts.py`
- Create: `tests/test_harvest_d_d3_store.py`

**Interfaces:**
- Consumes: D3 schemas, `IdentityRegistry`, `stable_hash`.
- Produces: `D3EvidenceStore`, `append_event()`, `append_call_bundle()`, `commit_checkpoint()`, `verify_integrity()`, `capture_status(call_id)`, `mark_capture_incomplete()`, `finalize_manifest()`.

- [ ] **Step 1: Write failing append/integrity tests**

```python

def test_store_never_overwrites_raw_evidence(tmp_path):
    store = D3EvidenceStore(tmp_path)
    store.append_event(event("e1", sequence=1))
    with pytest.raises(D3IntegrityError):
        store.append_event(event("e1", sequence=2))


def test_call_is_not_admissible_until_required_capture_commits(tmp_path):
    store = D3EvidenceStore(tmp_path)
    store.append_call_bundle(minimal_bundle("call-1", omit={"raw_response"}))
    assert store.capture_status("call-1").admissibility is EvidenceAdmissibility.DIAGNOSTIC_ONLY


def test_integrity_verification_detects_manual_mutation(tmp_path):
    store = D3EvidenceStore(tmp_path)
    store.append_event(event("e1", sequence=1)); store.commit_checkpoint()
    (tmp_path / "d3_system_events.jsonl").write_text("corrupt\n")
    with pytest.raises(D3IntegrityError):
        store.verify_integrity()
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_harvest_d_d3_store.py`
Expected: FAIL.

- [ ] **Step 3: Implement durable append-only files**

Write every record as one canonical JSON line, flush and `os.fsync()` before advancing the journal checkpoint. Maintain an append-only call ledger and checkpoint manifest with SHA-256/byte size. Required per-call families include raw request/response, normalized call, information packet, score rows, runtime telemetry, scheduler linkage, capture-field matrix, and system events. Unknown safe fields go into `extras` and are never discarded.

- [ ] **Step 4: Implement all mandatory empty-but-present output families in model-free mode**

At minimum create the data-capture addendum files plus the independent-review files: opportunity sets, decision opportunity sets, reproducibility calibration, structural features, behavior features, decision-boundary telemetry, missingness summary, causal claim graph/edges, coverage/uncovered/saturation, protocol violations, and assumption ledger.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest -q tests/test_harvest_d_d3_store.py tests/test_harvest_d_campaign.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/inverted/harvest_d/d3_store.py src/inverted/harvest_d/artifacts.py tests/test_harvest_d_d3_store.py
git commit -m "feat: add append-only D3 evidence store"
```

---

### Task 4: Implement information tomography and pure context-length controls

**Files:**
- Create: `src/inverted/harvest_d/d3_information.py`
- Create: `tests/test_harvest_d_d3_information.py`

**Interfaces:**
- Consumes: `HarvestCase`, `InformationField`, `InformationPacket`, `stable_hash`.
- Produces: `InformationContent`, `InformationQuality`, `InformationTrust`, `InformationRepresentation`, `InformationTiming`, `InformationAmount`, `PacketPlan`, `render_information_packet()`, `build_context_length_control()`, `field_lineage()`.

- [ ] **Step 1: Write failing packet tests**

```python

def test_model_packet_never_contains_hidden_oracle():
    packet = render_information_packet(case_with_hidden_oracle(), PacketPlan.minimum())
    assert "expected" not in packet.rendered.lower()
    assert "oracle" not in packet.rendered.lower()


def test_pure_context_length_control_changes_length_not_useful_information():
    short, long = build_context_length_control(base_fields(), target_extra_tokens=512)
    assert short.semantic_field_hash == long.semantic_field_hash
    assert long.approx_token_count > short.approx_token_count
    assert long.control_kind == "PURE_CONTEXT_LENGTH"


def test_field_lineage_records_include_omit_reason_and_transformation_chain():
    rows = field_lineage(packet_with_omission())
    omitted = next(x for x in rows if x["field_id"] == "I4")
    assert omitted["model_visible"] is False
    assert omitted["reason"]
    assert omitted["transform_chain"]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q tests/test_harvest_d_d3_information.py`
Expected: FAIL.

- [ ] **Step 3: Implement I1–I10 content, quality/source, amount, representation, ordering, placement/timing**

Represent packet plans as data, not prompt-specific conditionals. Renderers must support raw prose, typed fields, strict JSON/schema, decision table, priority block, explicit alternatives, decomposition, minimal ledger, compressed summary, and admissible-action matrix. Ordering and timing must be recorded separately from semantic content.

- [ ] **Step 4: Implement negative information controls**

Provide deterministic builders for token-matched irrelevant material, stale plausible state, conflicting evidence, untrusted metadata, redundant history, overload, unnecessary decomposition, wrong recovery suggestion, misleading route hint, and correct-information/poor-representation conditions. None may alter hidden truth.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest -q tests/test_harvest_d_d3_information.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/inverted/harvest_d/d3_information.py tests/test_harvest_d_d3_information.py
git commit -m "feat: add D3 information tomography"
```

---

### Task 5: Implement deterministic assistance, disposition compilation, and recovery decomposition

**Files:**
- Create: `src/inverted/harvest_d/d3_assistance.py`
- Create: `src/inverted/harvest_d/d3_recovery.py`
- Modify: `src/inverted/harvest_d/kernel.py`
- Create: `tests/test_harvest_d_d3_assistance.py`
- Create: `tests/test_harvest_d_d3_recovery.py`

**Interfaces:**
- Produces assistance A1–A11 target/off/sham evaluators, `DispositionCompiler`, `AssistanceOpportunity`, `RecoveryPolicy`, `RecoveryDecision`, `classify_recovery_trajectory()`, `failure_migrated()`.

- [ ] **Step 1: Write failing disposition/compiler tests**

```python

def test_disposition_compiler_uses_system_semantics_not_case_ids():
    result = DispositionCompiler().compile(system_state(missing_required_evidence=True))
    assert result.disposition is Disposition.ACQUIRE_EVIDENCE
    assert "case_id" not in result.inputs_used


def test_unknown_external_effect_never_compiles_to_retry():
    result = DispositionCompiler().compile(system_state(effect_status="UNKNOWN"))
    assert result.recovery in {"RECONCILE", "ESCALATE", "SAFE_STOP"}
```

- [ ] **Step 2: Write failing recovery-stage tests**

```python

def test_recovery_records_detection_diagnosis_selection_execution_verification_separately():
    t = simulate_recovery(fault="STALE_STATE")
    assert t.stage("DETECTION").timestamp <= t.stage("DIAGNOSIS").timestamp
    assert t.stage("SELECTION").choice
    assert t.stage("VERIFICATION").outcome


def test_local_fix_that_breaks_global_invariant_is_failure_migration():
    t = trajectory(local_recovered=True, global_invariant_ok=False)
    assert failure_migrated(t) is True
```

- [ ] **Step 3: Run RED**

Run: `python -m pytest -q tests/test_harvest_d_d3_assistance.py tests/test_harvest_d_d3_recovery.py`
Expected: FAIL.

- [ ] **Step 4: Implement A1–A11 as explicit deterministic mechanisms**

Every mechanism returns `OFF`, `TARGET`, and a matched `SHAM` result where scientifically valid. The mechanism receives only model-visible/system-owned observables allowed by the spec. Opportunity records must include eligible, ineligible reason, eligible-not-triggered, triggered-rejected, and triggered-admitted states.

- [ ] **Step 5: Implement recovery policy and migration detection**

Recovery choices are `RETRY`, `ALTERNATE_ACTION`, `RECONCILE`, `ROLLBACK`, `COMPENSATE`, `REPLAN`, `DECOMPOSE`, `ACQUIRE_EVIDENCE`, `ESCALATE`, `SAFE_STOP`. Enforce reconciliation before duplicate-risk retry and authority-consumption invariants through `TrustedKernel`.

- [ ] **Step 6: Run GREEN plus kernel regressions**

Run: `python -m pytest -q tests/test_harvest_d_d3_assistance.py tests/test_harvest_d_d3_recovery.py tests/test_harvest_d_core.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/inverted/harvest_d/d3_assistance.py src/inverted/harvest_d/d3_recovery.py src/inverted/harvest_d/kernel.py tests/test_harvest_d_d3_assistance.py tests/test_harvest_d_d3_recovery.py
git commit -m "feat: add D3 assistance and recovery controls"
```

---

### Task 6: Replace interval-only stopping with an anytime-valid sequential engine and adaptive scheduler

**Files:**
- Modify: `src/inverted/harvest_d/statistics.py`
- Create: `src/inverted/harvest_d/d3_scheduler.py`
- Create: `tests/test_harvest_d_d3_statistics.py`
- Create: `tests/test_harvest_d_d3_scheduler.py`

**Interfaces:**
- Produces: `anytime_hoeffding_cs(values, alpha)`, `SequentialEvidence`, `D3Scheduler`, `ExperimentCandidate`, `SchedulerPolicy`, `select_next()`, `record_decision()`, `protected_random_stream_fraction`.

- [ ] **Step 1: Write failing anytime-valid statistics tests**

```python

def test_anytime_sequence_contains_observed_mean_and_shrinks_with_n():
    a = anytime_hoeffding_cs([1, 0, 1, 1], alpha=.01)
    b = anytime_hoeffding_cs(([1, 0, 1, 1] * 16), alpha=.01)
    assert a.lower <= .75 <= a.upper
    assert (b.upper - b.lower) < (a.upper - a.lower)


def test_hard_violation_overrides_positive_effect():
    evidence = sequential_evidence([1] * 64, margin=.02, hard_violation=True)
    assert evidence.decision is SequentialDecision.HARMFUL
```

- [ ] **Step 2: Implement a standard-library anytime-valid confidence sequence**

For bounded values in `[0,1]`, use a time-uniform Hoeffding union bound with `alpha_n = alpha * 6 / (pi^2 * n^2)` and half-width `sqrt(log(2/alpha_n)/(2*n))`. For matched deltas in `[-1,1]`, map `x -> (x+1)/2`, compute the sequence, then map bounds back. Store method/version, alpha, look index, effective n, margin, bounds, and decision on every look. Retain `classify_sequential_interval()` for backward compatibility but do not use it as the D3 interval generator.

- [ ] **Step 3: Write failing scheduler tests**

```python

def test_scheduler_prioritizes_safety_then_semantics_then_silent_wrong_action():
    chosen = D3Scheduler.default().select_next(candidate_set())
    assert chosen.priority_reason == "HARD_INVARIANT_UNCERTAINTY"


def test_harmful_candidate_stops_receiving_calls_except_contradiction_check():
    sched = D3Scheduler.default()
    sched.observe("m1", SequentialDecision.HARMFUL)
    assert all(x.kind == "CONTRADICTION_CHECK" for x in sched.remaining_for("m1"))


def test_scheduler_preserves_randomized_exploration_stream():
    sched = D3Scheduler.default(random_stream_fraction=.10, seed=20260903)
    picks = [sched.select_next(many_equal_candidates()) for _ in range(100)]
    assert any(p.selection_mode == "PROTECTED_RANDOM" for p in picks)
```

- [ ] **Step 4: Implement adaptive information-gain ranking and protected random stream**

Rank lexicographically by hard-invariant uncertainty, semantic uncertainty, silent wrong action, recovery, information×assistance, model substitution, information marginal, assistance marginal, MSIP/MRS, then efficiency. Candidate metadata must record every alternative and its score so scheduling is reconstructable. The random stream draws only from preregistered admissible candidates and can never touch sealed cases early.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest -q tests/test_harvest_d_d3_statistics.py tests/test_harvest_d_d3_scheduler.py tests/test_harvest_d_analysis.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/inverted/harvest_d/statistics.py src/inverted/harvest_d/d3_scheduler.py tests/test_harvest_d_d3_statistics.py tests/test_harvest_d_d3_scheduler.py
git commit -m "feat: add anytime-valid D3 scheduler"
```

---

### Task 7: Build the single-call D3 executor with maximum-value capture and reproducibility calibration

**Files:**
- Create: `src/inverted/harvest_d/d3_executor.py`
- Modify: `src/inverted/harvest_d/models.py`
- Modify: `src/inverted/harvest_d/runner.py`
- Create: `tests/test_harvest_d_d3_executor.py`

**Interfaces:**
- Consumes: `ModelAdapter`, `D3EvidenceStore`, packet plan, assistance plan, scheduler decision.
- Produces: `D3CallExecutor.execute_once()`, `RuntimeNeighborState`, `ReproducibilityCalibration`, `run_reproducibility_block()`.

- [ ] **Step 1: Write failing one-call/no-retry test**

```python

def test_executor_calls_adapter_once_even_when_response_is_malformed(tmp_path):
    adapter = CountingAdapter("not json")
    result = D3CallExecutor(store=D3EvidenceStore(tmp_path)).execute_once(call_plan(), adapter)
    assert adapter.calls == 1
    assert result.failure_class == "FORMAT_OR_SCHEMA"
```

- [ ] **Step 2: Write failing raw/neighbor capture test**

```python

def test_executor_preserves_exact_request_response_and_previous_call_link(tmp_path):
    store = D3EvidenceStore(tmp_path)
    ex = D3CallExecutor(store=store)
    first = ex.execute_once(call_plan(case_id="a"), FixedAdapter("ok"))
    second = ex.execute_once(call_plan(case_id="b"), FixedAdapter("ok"))
    row = store.normalized_call(second.physical_model_call_id)
    assert row["previous_physical_model_call_id"] == first.physical_model_call_id
    assert store.raw_request(second.physical_model_call_id)["messages"]
    assert store.raw_response(second.physical_model_call_id)["payload"]
```

- [ ] **Step 3: Extend Ollama response capture without changing generation freeze**

Preserve exact outbound message array/options and the complete safe raw Ollama payload. Record model/runtime-visible metadata such as load duration, done reason, prompt/eval counts, total duration, and safe unknown fields under `extras`. Do not capture credentials or broad environment dumps.

- [ ] **Step 4: Implement the preregistered reproducibility block**

Default calibration is 4 structurally distinct cases × SMALL_A/QWEN × 3 exact physical repetitions = 24 calls, interleaved. Record byte identity, semantic identity, disposition/answer stability, latency/token variance, prior-call linkage, warm/cold/load status, restart epoch, and hardware allocation if exposed. Permit sequential early stopping only under a preregistered calibration rule; never silently assume temperature 0 is deterministic.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest -q tests/test_harvest_d_d3_executor.py tests/test_harvest_d_execution.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/inverted/harvest_d/d3_executor.py src/inverted/harvest_d/models.py src/inverted/harvest_d/runner.py tests/test_harvest_d_d3_executor.py
git commit -m "feat: add lossless D3 call executor"
```

---

### Task 8: Implement crash-safe journal/resume and provenance segmentation

**Files:**
- Create: `src/inverted/harvest_d/d3_resume.py`
- Create: `tests/test_harvest_d_d3_resume.py`

**Interfaces:**
- Produces: `D3ResumeState`, `D3Journal`, `resume_campaign()`, `ProvenanceMismatch`, `ResumeIntegrityError`.

- [ ] **Step 1: Write failing committed-call replay test**

```python

def test_resume_never_repeats_committed_physical_call(tmp_path):
    journal = seeded_journal(tmp_path, committed_call="call-7", next_action="action-8")
    state = resume_campaign(journal.root, current_provenance=journal.provenance)
    assert state.next_action_id == "action-8"
    assert "call-7" in state.completed_call_ids
```

- [ ] **Step 2: Write failing provenance-change test**

```python

def test_model_digest_change_requires_segmentation_or_halt(tmp_path):
    journal = seeded_journal(tmp_path)
    with pytest.raises(ProvenanceMismatch):
        resume_campaign(journal.root, current_provenance={**journal.provenance, "model_digest": "changed"})
```

- [ ] **Step 3: Implement atomic journal order**

Use schedule intent → physical call → raw capture → normalized capture → event/call ledger → completeness validation → committed action marker. On restart, verify manifest hashes and identity uniqueness, then resume from the first uncommitted action. Never auto-repeat a physical call whose response was received but capture became incomplete; retain it as diagnostic and schedule a new preregistered observation only if scientifically justified under a new call ID.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest -q tests/test_harvest_d_d3_resume.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/harvest_d/d3_resume.py tests/test_harvest_d_d3_resume.py
git commit -m "feat: add crash safe D3 resume semantics"
```

---

### Task 9: Implement deterministic post-call analysis, coverage, MSIP/MRS, and causal claim graph

**Files:**
- Create: `src/inverted/harvest_d/d3_analysis.py`
- Modify: `src/inverted/harvest_d/causal.py`
- Modify: `src/inverted/harvest_d/frontier.py`
- Modify: `src/inverted/harvest_d/knowledge.py`
- Create: `tests/test_harvest_d_d3_analysis.py`

**Interfaces:**
- Produces `classify_failure()`, `derive_structural_features()`, `derive_behavior_features()`, `build_information_value_map()`, `build_assistance_value_map()`, `build_recovery_maps()`, `find_msip()`, `find_mrs()`, `build_model_substitution_frontier()`, `build_coverage_matrix()`, `build_claim_graph()`.

- [ ] **Step 1: Write failing failure-classification tests**

```python

def test_answer_correct_disposition_wrong_is_its_own_failure_class():
    assert classify_failure(score(answer=True, disposition=False)) == "ANSWER_RIGHT_DISPOSITION_WRONG"


def test_recovery_migration_is_not_counted_as_recovery_success():
    summary = build_recovery_maps([trajectory(recovered_local=True, migrated=True)])
    assert summary["recovered_without_migration"] == 0
```

- [ ] **Step 2: Write failing minimum-support tests**

```python

def test_msip_removes_fields_that_do_not_pay_complexity_rent():
    result = find_msip(packet="I1+I2+I3", ablations={"I3": noninferior(), "I2": harmful_drop()})
    assert result.required_fields == ("I1", "I2")


def test_mrs_prefers_least_involved_safe_noninferior_configuration():
    result = find_mrs(points())
    assert result.name == "light"
```

- [ ] **Step 3: Implement deterministic derived datasets and claim graph**

Claims must link supporting/contradictory raw call IDs, replay IDs, sham controls, neighbor/fresh/sealed evidence, effect state, applicability/exclusions, promotion/suspension/revalidation history, component version, and superseded claims. Do not promote from development evidence alone.

- [ ] **Step 4: Implement coverage/saturation/uncovered-space telemetry**

Track information × quality/source/representation/timing, assistance × failure family, recovery × failure family, model × capability region, TARGET/OFF/SHAM, development/neighbor/fresh/sealed, structural feature ranges, hard-invariant attacks. Every uncovered cell receives an explicit reason such as `LOW_VALUE`, `INAPPLICABLE`, `KILLED_BY_EVIDENCE`, `BUDGET_DEFERRED`, or `IMPORTANT_UNRESOLVED`.

- [ ] **Step 5: Run GREEN**

Run: `python -m pytest -q tests/test_harvest_d_d3_analysis.py tests/test_harvest_d_analysis.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/inverted/harvest_d/d3_analysis.py src/inverted/harvest_d/causal.py src/inverted/harvest_d/frontier.py src/inverted/harvest_d/knowledge.py tests/test_harvest_d_d3_analysis.py
git commit -m "feat: add D3 causal analysis and minimum support search"
```

---

### Task 10: Build the autonomous D3 campaign controller

**Files:**
- Create: `src/inverted/harvest_d/d3_campaign.py`
- Create: `tests/test_harvest_d_d3_campaign.py`

**Interfaces:**
- Consumes: budget, scheduler, executor, store, information/assistance/recovery modules, analysis, resume.
- Produces: `D3Campaign`, `preflight()`, `run()`, `run_model_free_simulation()`, `HardStop`, `CampaignResult`.

- [ ] **Step 1: Write failing autonomous-loop test**

```python

def test_campaign_runs_unattended_until_scheduler_stop(tmp_path):
    campaign = D3Campaign.testing(tmp_path, adapter=DeterministicFakeAdapter(), max_calls=12)
    result = campaign.run()
    assert result.calls_used <= 12
    assert result.operator_actions_required == []
    assert result.final_state in {"COMPLETE", "EVIDENCE_CEILING_REACHED"}
```

- [ ] **Step 2: Write failing hard-stop test**

```python

def test_hard_invariant_violation_halts_before_another_model_call(tmp_path):
    adapter = CountingAdapter(sequence=[safe_response(), invariant_breaking_response(), safe_response()])
    result = D3Campaign.testing(tmp_path, adapter=adapter, max_calls=10).run()
    assert result.final_state == "HARD_STOP"
    assert adapter.calls == 2
```

- [ ] **Step 3: Implement automated campaign state machine**

```text
PREFLIGHT -> REPRO_CALIBRATION -> DISCOVERY -> DEEPEN -> INTERACTIONS -> MSIP_MRS -> FRESH_GENERALIZATION -> NEGATIVE_TRANSFER -> SEALED_CONFIRMATION -> FINALIZE
```

The controller automatically schedules, calls, captures, scores, replays OFF/TARGET/SHAM where zero-call-valid, classifies failures/recovery, updates sequential evidence, reallocates unsealed reservoirs, mines failures, and selects the next preregistered experiment. Ordinary malformed/low-scoring/failed-recovery responses remain evidence and do not stop the campaign.

- [ ] **Step 4: Implement hard-stop enforcement**

Hard-stop before another physical call on unauthorized irreversible action/simulation, duplicate irreversible effect, resurrected authority, oracle leak, ambiguous call identity, sealed contamination, corrupted evidence/journal, invalid provenance comparability, promoted authority bypass, or exhausted preregistered moves with a high-value unresolved causal question.

- [ ] **Step 5: Implement evidence-depth/promotion gates**

A candidate cannot enter the proposed core build until the applicable evidence-depth target, target>sham requirement, invariants, semantic regression, neighbor/fresh generalization, negative transfer, MSIP/MRS, migration, sealed, and integrity gates are satisfied. Otherwise classify it `CONDITIONAL` or `UNRESOLVED`.

- [ ] **Step 6: Run GREEN**

Run: `python -m pytest -q tests/test_harvest_d_d3_campaign.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/inverted/harvest_d/d3_campaign.py tests/test_harvest_d_d3_campaign.py
git commit -m "feat: automate Harvest D D3 campaign"
```

---

### Task 11: Add preflight, CLI, PowerShell launcher, final artifact package, and data-value audit

**Files:**
- Create: `src/inverted/harvest_d/d3_cli.py`
- Create: `scripts/run-harvest-d-d3.ps1`
- Create: `configs/harvest-d-d3.json`
- Create: `tests/test_harvest_d_d3_cli.py`
- Create: `tests/test_harvest_d_d3_outputs.py`

**Interfaces:**
- `python -m inverted.harvest_d.d3_cli --config configs/harvest-d-d3.json --output <dir> --model-free`
- Real local run through `scripts/run-harvest-d-d3.ps1` after preflight.

- [ ] **Step 1: Write failing preflight tests**

```python

def test_model_free_preflight_spends_zero_calls_and_checks_leakage(tmp_path):
    result = D3Campaign.testing(tmp_path, adapter=ForbiddenAdapter()).preflight(model_free=True)
    assert result.calls_used == 0
    assert result.oracle_leakage_check is True


def test_preflight_rejects_changed_sealed_hash_before_calls(tmp_path):
    campaign = campaign_with_changed_sealed_bank(tmp_path)
    with pytest.raises(HardStop):
        campaign.preflight()
```

- [ ] **Step 2: Implement preflight**

Record repo branch/commit, case-bank hashes, prompt/packet hashes, local endpoint availability for real mode, exact model IDs/digests where exposed, runtime version, generation options/context, measurement version, budget/journal state, identity registry, sealed integrity, oracle-leak checks, output integrity/writeability, component/dependency manifest, and safe environment provenance. Any failure occurs before inference.

- [ ] **Step 3: Implement one-command launcher**

`run-harvest-d-d3.ps1` must run model-free validation/preflight first, then invoke the real D3 CLI only after all gates pass. It must not contain hidden retries. Default real models are SMALL_A `qwen2.5:1.5b-instruct-q8_0` and QWEN `qwen3.5:9b-q8_0`; transition/stronger models are optional scheduler-controlled probes, not dependencies.

- [ ] **Step 4: Emit every normative output**

Include the original D3 maps/reports plus all data-capture/independent-review files. Finalization must emit `d3_data_dictionary.json`, checksums, master index, completeness audit, causal claim graph, coverage matrix, and `d4_handoff.json`.

- [ ] **Step 5: Implement the final 15-question data-value audit**

The model-free audit must prove the stored dataset can reconstruct why each call was scheduled, alternatives available, model-visible vs system-known information, transformations, opportunity sets, deterministic decisions, counterfactual replays, runtime-order confounds, missingness, structural predictors, contradictory claims, uncovered regions, final-build provenance, excluded-component provenance, and new deterministic scorer replayability. If cheap required evidence is unavailable, finalization fails.

- [ ] **Step 6: Run GREEN**

Run: `python -m pytest -q tests/test_harvest_d_d3_cli.py tests/test_harvest_d_d3_outputs.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/inverted/harvest_d/d3_cli.py scripts/run-harvest-d-d3.ps1 configs/harvest-d-d3.json tests/test_harvest_d_d3_cli.py tests/test_harvest_d_d3_outputs.py
git commit -m "feat: add one command D3 launcher and evidence audit"
```

---

### Task 12: Wire CI and drive the complete repository to model-free green

**Files:**
- Modify: `.github/workflows/harvest-d-validation.yml`
- Test: all `tests/test_harvest_d_d3_*.py`, all existing Harvest D tests, full repository suite.

**Interfaces:**
- GitHub Actions remains model-free and validates D3 simulation/dry-run only.

- [ ] **Step 1: Extend workflow path filters and focused D3 test step**

Add `src/inverted/harvest_d/d3_*.py`, `tests/test_harvest_d_d3_*.py`, `configs/harvest-d-d3.json`, `scripts/run-harvest-d-d3.ps1`, and all four normative D3 spec/addendum paths.

- [ ] **Step 2: Add a model-free D3 end-to-end CI command**

Run:

```bash
python -m inverted.harvest_d.d3_cli --config configs/harvest-d-d3.json --output /tmp/harvest-d-d3-model-free --model-free
```

Verify master index, `d3_system_events.jsonl`, `d3_campaign_journal.jsonl`, `d3_call_ledger.jsonl`, `d3_capture_completeness.json`, `d3_data_dictionary.json`, `d3_causal_claim_graph.jsonl`, `d3_coverage_matrix.json`, and `SHA256SUMS.csv` exist and the run reports zero physical model calls.

- [ ] **Step 3: Run the entire focused D3 suite locally/in CI**

Run: `python -m pytest -q tests/test_harvest_d_d3_*.py`
Expected: PASS.

- [ ] **Step 4: Run all Harvest D regressions**

Run: `python -m pytest -q tests/test_harvest_d_core.py tests/test_harvest_d_analysis.py tests/test_harvest_d_execution.py tests/test_harvest_d_campaign.py tests/test_harvest_d_d3_*.py`
Expected: PASS.

- [ ] **Step 5: Run full repository regression**

Run: `python -m pytest -q`
Expected: PASS with no normal test requiring Ollama/cloud/network.

- [ ] **Step 6: Run model-free D3 end-to-end twice and compare deterministic artifacts**

The two runs must produce identical deterministic config/schema/plan/case metadata and logically equivalent event structure; run IDs/timestamps may differ and must be explicitly excluded from byte-identity expectations. Both runs must use zero physical model calls.

- [ ] **Step 7: Verify frozen evidence paths are untouched**

Use Git diff/commit comparison to confirm no file under frozen Test2/Test3 evidence trees was modified.

- [ ] **Step 8: Verify GitHub Actions green before claiming the harness is green**

Required green workflows include `harvest-d-validation` and any full repository validation workflow triggered by the branch changes. Do not claim a real D3 campaign is green until local Ollama preflight and the real launcher are subsequently run by the operator; CI only proves the automated harness/model-free control plane.

- [ ] **Step 9: Commit**

```bash
git add .github/workflows/harvest-d-validation.yml
git commit -m "ci: validate automated Harvest D D3 harness"
```

---

## Self-Review Against the Normative D3 Spec

- Budget/phase reservoirs/protected sealed reserve: Task 1.
- Typed conditions, missingness, fault-family expansion, event schemas: Task 2.
- Three-layer lossless evidence, append-only integrity, completeness gate, unknown-field preservation: Task 3.
- I1–I10, quality/source/amount/representation/order/timing, negative information, pure context-length control: Task 4.
- A1–A11, disposition compiler, OFF/TARGET/SHAM, opportunity sets, recovery decomposition and migration: Task 5.
- Sequentially valid inference, adaptive information-gain scheduling, protected randomized stream: Task 6.
- One-call/no-retry physical execution, raw capture, order/cache/carryover telemetry, reproducibility calibration: Task 7.
- Crash/resume, atomic journaling, provenance mismatch/segmentation: Task 8.
- Failure mining, structural/behavior features, MSIP/MRS, coverage/saturation, causal claim graph: Task 9.
- Fully automated unattended campaign, hard stops, promotion/evidence-depth gates, sealed confirmation: Task 10.
- Preflight, operator provenance, one-command launcher, mandatory outputs, data-value audit: Task 11.
- Model-free full-green CI, deterministic dry runs, frozen-evidence verification: Task 12.
- CPU Sentinel: preserved as an explicit later intervention seam; D3 may learn its best input contract but does not bypass its approved validation gates.

No task authorizes oracle rewriting, authority expansion, sealed-case tuning, hidden retries, private chain-of-thought capture, or evidence deletion. The implementation deliberately prefers deterministic replay and post-hoc analysis over additional inference whenever causally valid.