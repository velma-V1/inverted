# SYSTEM_HARVEST_11 Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, event-sourced fake-backed campaign orchestrator that can schedule, execute, verify, resume, escalate, gap-close, and complete the 11-system harvest without losing observable evidence.

**Architecture:** `CampaignSchedule` freezes baseline/applicability coverage; `ExecutionBackend` emits observable execution events but owns no scheduler state; `CampaignOrchestrator` journals every transition and delegates raw persistence to `AcquisitionRecorder`, failure continuation to the existing escalation layer, and closure to explicit manifest/coverage gates. Initial execution is deterministic and sequential with `FakeExecutionBackend` only.

**Tech Stack:** Python 3.14, dataclasses/enums/protocols, pathlib, JSON/JSONL, SHA-256, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-system-harvest-11-orchestrator-design.md`

## Global Constraints

- No live target-agent, model-provider, network, or production subprocess execution in this phase.
- Preserve every observable backend/native record before parsing or interpretation.
- Baseline schedule is immutable after freeze; discoveries append supplemental cells.
- Every 11×32 behavioral applicability pair is explicit; every required perturbation coverage obligation is explicit.
- `CONTINUE_FROM_FAILURE_BOUNDARY` is the normal escalation resume contract.
- Infrastructure interruption keeps the same logical execution identity and escalation level.
- Cell/campaign completion is impossible with unresolved evidence, manifests, escalation, or supplemental work.
- Existing `runs/` evidence is untouched.
### Task 1: Frozen schedule and applicability compiler

**Files:**
- Create: `src/inverted/system_harvest/schedule.py`
- Create: `tests/test_system_harvest_schedule.py`

**Interfaces:**
- Consumes: `HarvestTemplate`, frozen adapter registry system IDs.
- Produces: `VerificationContract`, `ExecutionCell`, `ApplicabilityRecord`, `CampaignSchedule`, `compile_schedule(...)`, `append_supplemental_cell(...)`.

- [ ] Write RED tests proving stable content-derived cell IDs, duplicate rejection, unknown scenario/perturbation rejection, fixture hash requirement, verifier requirement, full 11×32 applicability accounting, perturbation accounting, immutable baseline hash, and append-only supplemental provenance.
- [ ] Run `python -m pytest -q tests/test_system_harvest_schedule.py` and verify RED on missing module/functions.
- [ ] Implement immutable schedule dataclasses and deterministic canonical hashing.
- [ ] Implement compiler coverage validation: each system/behavior pair is exactly one executable cell or evidence-backed applicability record; each perturbation obligation is explicit.
- [ ] Implement supplemental append returning a new schedule while preserving the original baseline hash and existing cell IDs.
- [ ] Run focused tests to GREEN.

### Task 2: Backend protocol and deterministic fake backend

**Files:**
- Create: `src/inverted/system_harvest/backend.py`
- Create: `tests/test_system_harvest_backend.py`

**Interfaces:**
- Consumes: `ExecutionCell`, stable `execution_id`, optional escalation continuation package.
- Produces: `BackendObservation`, `BackendResult`, `ExecutionBackend` protocol, `FakeExecutionBackend`.

- [ ] Write RED tests for ordered raw observations, success/incorrect/stall/infra-interruption scripts, exact resume handle reuse, malformed text preservation, and deterministic recursive escalation scripts.
- [ ] Run focused test and verify RED.
- [ ] Implement backend event/result types with no scheduler-completion authority.
- [ ] Implement fake backend as a script queue keyed by cell and escalation level; record launch/resume calls for idempotency assertions.
- [ ] Ensure backend module imports no subprocess/socket/http/provider libraries.
- [ ] Run focused tests to GREEN.
### Task 3: Event-sourced cell state machine

**Files:**
- Create: `src/inverted/system_harvest/orchestrator.py`
- Create: `tests/test_system_harvest_orchestrator_core.py`

**Interfaces:**
- Consumes: `CampaignSchedule`, `ExecutionBackend`, adapter registry, `AcquisitionRecorder`, `HarvestJournal`.
- Produces: `CellState`, `CellRuntimeState`, `CampaignRuntimeState`, `CampaignOrchestrator.start_cell(...)`, `resume_from_journal(...)`, `run_next_eligible(...)`.

- [ ] Write RED tests proving no launch before global/cell preflight, legal transition ordering, raw observation journal/persistence precedes verifier state, post-snapshot precedes completion, and blocked cells do not abort unrelated eligible cells.
- [ ] Verify RED.
- [ ] Implement explicit durable cell states from `PLANNED` through `COMPLETE`, plus `INFRA_INTERRUPTED`, failure/stall boundary states, `ESCALATION_PENDING`, and `RECOVERY_UNCERTAIN`.
- [ ] Journal every transition before mutating in-memory scheduler state; rebuild runtime state only by replaying valid journal records.
- [ ] Add idempotency keys for launch, resume, artifact finalization, capsule persistence, and advancement.
- [ ] Run focused tests to GREEN.

### Task 4: Verification, stall detection, and escalation ordering

**Files:**
- Modify: `src/inverted/system_harvest/orchestrator.py`
- Create: `tests/test_system_harvest_orchestrator_escalation.py`

**Interfaces:**
- Consumes: existing `advance_example(...)`, `build_escalation_capsule(...)`, `verify_escalation_capsule(...)`.
- Produces: `VerifierResult`, `StallPolicy`, `EscalationRoute`, `EscalationRouter` protocol, deterministic fake router.

- [ ] Write RED tests for deterministic verifier authority, indeterminate verification blocking completion, stall evidence capture, capsule-before-router ordering, recursive parent-linked capsules, and continuation at the exact failure boundary.
- [ ] Verify RED.
- [ ] Implement verifier/stall records as journaled evidence-bearing events.
- [ ] Build required 25-section capsules from supplied snapshot evidence; refuse escalation if any required section is unresolved.
- [ ] Persist and verify capsule before recording/using the router decision.
- [ ] Preserve escalation level and parent capsule lineage across recursive failures.
- [ ] Run focused tests to GREEN.
### Task 5: Crash recovery, reconciliation, and supplemental gap closure

**Files:**
- Modify: `src/inverted/system_harvest/orchestrator.py`
- Create: `tests/test_system_harvest_orchestrator_recovery.py`

**Interfaces:**
- Consumes: durable journal records, backend session handles, `append_supplemental_cell(...)`.
- Produces: `ReconciliationResult`, `GapDiscovery`, `admit_supplemental(...)`, crash-safe resume behavior.

- [ ] Write RED tests for same-execution resume after infra interruption, journal replay after process restart, no duplicate launch/capsule/finalization/advance, `RECOVERY_UNCERTAIN` when external completion cannot be proven, and supplemental admission with origin evidence/decision value/closure condition.
- [ ] Verify RED.
- [ ] Implement reconciliation state and idempotency recovery from journal-derived facts.
- [ ] Ensure infrastructure interruption never increments semantic escalation level.
- [ ] Implement append-only supplemental queue; baseline hash and existing baseline cell ordering must remain unchanged.
- [ ] Make admitted supplemental work mandatory for campaign closure.
- [ ] Run focused tests to GREEN.

### Task 6: Campaign completion authority and 11-adapter synthetic contract

**Files:**
- Modify: `src/inverted/system_harvest/orchestrator.py`
- Create: `tests/test_system_harvest_orchestrator_completion.py`
- Create: `tests/test_system_harvest_orchestrator_contract.py`

**Interfaces:**
- Consumes: cell runtime states, artifact manifest reports, evidence-channel coverage, escalation verification, existing completion contracts.
- Produces: `OrchestratorCompletionReport`, `evaluate_orchestrator_completion(...)`.

- [ ] Write RED tests proving scheduler exhaustion/open blockers cannot equal completion, missing artifact/evidence/escalation verification blocks closure, supplemental work blocks closure, and all 11 adapters can execute synthetic matched cells under identical scheduler semantics.
- [ ] Verify RED.
- [ ] Implement explicit completion report with machine-readable blockers.
- [ ] Run a synthetic campaign across all 11 adapters using only fake backend events and fixture evidence.
- [ ] Verify no construction/test path imports or invokes live agent/provider/network/subprocess execution.
- [ ] Run focused tests to GREEN.

### Task 7: Final verification and documentation alignment

**Files:**
- Modify only if needed: orchestrator spec/plan and `src/inverted/system_harvest/__init__.py`.

- [ ] Run all `tests/test_system_harvest*.py` with `PYTHONPATH=src`.
- [ ] Compile `src/inverted/system_harvest`.
- [ ] Validate 11-adapter registry and 13 evidence-channel coverage from the current campaign manifest.
- [ ] Scan orchestrator/backend production files for live execution/provider/network imports.
- [ ] Run the full repository test suite; separately report unrelated concurrent failures rather than modifying unrelated subsystems.
- [ ] Inspect `git status --short`, `git diff --check`, and leave existing `runs/` untouched.
