# SYSTEM_HARVEST_11 One-Pass Evidence / Escalation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reusable, validation-first template and execution-control substrate for an evidence-maximal harvest of eleven systems with failure-boundary escalation, recursive continuation, crash-safe resume, gap closure, and impossible-to-fake completion.

**Architecture:** A frozen JSON campaign manifest is loaded into typed Python contracts. An append-only event/journal model separates raw evidence capture from normalized/derived views. Wrong/stalled executions create complete reconstructable escalation capsules and continue through stronger models from the captured failure boundary; infrastructure interruptions resume the same execution identity. This stage launches no real inference; adapters for individual harvested systems plug into the contract later.

**Tech Stack:** Python 3, dataclasses/enums, JSON, hashlib, pathlib, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-system-harvest-11-one-pass-evidence-design.md`

## Global Constraints

- Keep `docs/superpowers/specs/2026-09-07-universal-system-test-templates-design.md` and `src/inverted/system_testing/` semantically separate and unchanged.
- Frozen system count is exactly 11.
- "Never rerun" is an evidence-severity assumption, not a prohibition on future replay or testing.
- Each incorrect/stalled model execution freezes a complete failure-boundary capsule before recovery mutation.
- Escalation continues from the captured boundary; recursive failures create child capsules linked to the prior chain.
- Infrastructure interruption resumes the same execution identity and does not create a semantic escalation by itself.
- `COMPLETED` is impossible until all required coverage and evidence gates close.
- Preserve raw payload lineage; never summarize away raw evidence first.
- Template validation and unit tests must launch zero real inference.

---
### Task 1: Frozen campaign manifest and validator

**Files:**
- Create: `configs/system-harvest-11/campaign.json`
- Create: `src/inverted/system_harvest/types.py`
- Create: `src/inverted/system_harvest/template.py`
- Create: `src/inverted/system_harvest/__init__.py`
- Test: `tests/test_system_harvest_template.py`

**Interfaces:**
- Produces: `HarvestTemplate`, `CoverageDomain`, `EscalationPolicy`, `load_harvest_template(path)`.
- Consumes: JSON campaign manifest only.

- [ ] Write failing tests proving exact eleven-system identity/order, mandatory coverage domains, future-query gate, raw evidence layers, and failure-boundary escalation policy.
- [ ] Run `python -m pytest -q tests/test_system_harvest_template.py` and confirm RED because the package/config do not exist.
- [ ] Implement typed enums/dataclasses plus strict JSON validation.
- [ ] Reject missing systems, duplicates, restart-style escalation policies, absent required snapshot sections/evidence layers, blank domains, and completion policies that permit partial coverage.
- [ ] Re-run the focused test and require GREEN.

### Task 2: Exhaustive event envelope and raw evidence integrity

**Files:**
- Create: `src/inverted/system_harvest/evidence.py`
- Test: `tests/test_system_harvest_evidence.py`

**Interfaces:**
- Produces: `RawEvent`, `EventLineage`, `content_hash(payload)`, `verify_event(event)`.
- Consumes: arbitrary JSON-safe observable payloads from future adapters.

- [ ] Write failing tests for exact raw payload retention, stable IDs, parent/event lineage, content hashes, source/version metadata, attempt identity, and redacted-secret metadata.
- [ ] Verify RED.
- [ ] Implement immutable event records without lossy normalization.
- [ ] Ensure derived/normalized references point to raw event IDs rather than replace raw content.
- [ ] Verify GREEN.
### Task 3: Failure-boundary escalation and crash-resume state machine

**Files:**
- Create: `src/inverted/system_harvest/execution.py`
- Create: `src/inverted/system_harvest/escalation.py`
- Test: `tests/test_system_harvest_execution.py`
- Test: `tests/test_system_harvest_escalation.py`

**Interfaces:**
- Produces: `AttemptOutcome`, `ExecutionDecision`, `EscalationCapsule`, `SnapshotSection`, `build_escalation_capsule(...)`, `verify_escalation_capsule(...)`.
- Consumes: template escalation policy plus raw event/journal state.

- [ ] Write failing tests proving `INCORRECT` or `STALL` produces `CAPTURE_AND_ESCALATE`, never terminal fail-after-retry.
- [ ] Require complete task/instruction/ingredient/context/environment/state/tool/trajectory/failure/pending-work sections in every capsule.
- [ ] Require content-derived capsule identity, raw evidence lineage, and explicit handling for inaccessible/not-applicable sections.
- [ ] Prove recursive escalation requires parent-capsule linkage and preserves the full chain.
- [ ] Prove continuation mode is `CONTINUE_FROM_FAILURE_BOUNDARY`; restart is not the default recovery action.
- [ ] Prove infrastructure interruption resumes the same execution/campaign/escalation identity.
- [ ] Verify RED, implement minimal deterministic state/capsule machinery, then verify GREEN.

### Task 4: Coverage ledger, adaptive gap closure, and future-query survivability

**Files:**
- Create: `src/inverted/system_harvest/coverage.py`
- Test: `tests/test_system_harvest_coverage.py`

**Interfaces:**
- Produces: `CoverageItem`, `CoverageStatus`, `CoverageLedger`, `FutureQueryProbe`.
- Consumes: frozen domains plus newly discovered coverage items.

- [ ] Write failing tests proving blank/skipped items are impossible and new discoveries append without mutating prior entries.
- [ ] Prove `CAPTURED_PARTIAL`, `PENDING`, and all `NEEDS_*` states keep a system open.
- [ ] Prove `INACCESSIBLE` requires an evidence-backed reason and provenance IDs.
- [ ] Prove at least one future-query probe outside the predefined battery is required before freeze.
- [ ] Verify RED, implement ledger/gap APIs, then verify GREEN.

### Task 5: Completion gate and manifest verification

**Files:**
- Create: `src/inverted/system_harvest/completion.py`
- Test: `tests/test_system_harvest_completion.py`

**Interfaces:**
- Produces: `SystemCompletionReport`, `CampaignCompletionReport`, `evaluate_system_completion(...)`, `evaluate_campaign_completion(...)`.
- Consumes: coverage ledger, example outcomes, evidence-channel records, integrity verification, mechanism extraction records and future-query probes.

- [ ] Write failing tests proving one missing channel/item/example blocks `HARVEST_COMPLETE`.
- [ ] Prove unresolved escalation prevents completion while `RECOVERED_BY_ESCALATION` is a valid completed example outcome.
- [ ] Prove the campaign cannot reach `COMPLETED` until exactly all eleven systems independently pass the system gate.
- [ ] Prove raw/normalized/relationship manifest verification is mandatory.
- [ ] Verify RED, implement gate, then verify GREEN.
### Task 6: Cross-system harvest contract regression

**Files:**
- Create: `tests/test_system_harvest_contract.py`
- Modify only if needed: `src/inverted/system_harvest/__init__.py`

**Interfaces:**
- Consumes every public interface from Tasks 1–5.
- Produces no new production API; this is the integrated contract gate.

- [ ] Write integrated tests constructing all eleven system ledgers and examples from the frozen manifest.
- [ ] Prove a semantic failure becomes an escalation boundary rather than a terminal example outcome.
- [ ] Prove resume maintains campaign/example/execution/escalation identity.
- [ ] Prove recursive escalation lineage remains connected across multiple model handoffs.
- [ ] Prove a newly appended discovery reopens completion until resolved.
- [ ] Prove complete evidence with recovered escalation outcomes can close the campaign.
- [ ] Run all `tests/test_system_harvest_*.py` and require GREEN.
- [ ] Run `python -m pytest -q` with the repository-required `PYTHONPATH=src` environment and record unrelated/pre-existing failures separately.
- [ ] Run `git diff --check` and inspect `git status --short` without deleting or modifying pre-existing `runs/` evidence.

## Self-review

- Spec coverage: manifest, exhaustive raw capture, lineage, failure-boundary escalation, recursive capsule linkage, infrastructure resume, coverage ledger, adaptive discoveries, future-query gate, integrity verification and completion gate are each mapped to a task.
- Placeholder scan: no implementation task depends on TBD/TODO behavior.
- Type consistency: template -> execution/coverage -> completion boundaries are explicit; raw evidence is independent from derived interpretation.
- Scope: this builds the reusable harvest contract/control substrate only; it does not run any of the eleven systems or modify the INVERTED causal-test template.

## Execution rule

Implement inline in this existing isolated worktree using TDD. Do not launch real inference. Stop only for a genuine repository blocker; otherwise complete all six tasks and verify before claiming readiness.

## Execution-review amendments

Two requirements were promoted from implied architecture to explicit implementation during review:

### Amendment A: Freeze executable batteries in the manifest

`HarvestTemplate` and `campaign.json` now carry a 32-item common behavioral battery and a 12-item perturbation battery. The validator exposes these as typed immutable tuples, and tests require high-value ambiguity, failure, interruption, context-pressure, recovery, and irreversibility cases to remain present.

This makes “all examples/tests/requirements completed” machine-enumerable rather than dependent on prose.

### Amendment B: Durable same-campaign journal

**Files:**
- Create: `src/inverted/system_harvest/journal.py`
- Test: `tests/test_system_harvest_journal.py`

The journal is append-only JSONL with monotonically increasing sequence IDs, campaign identity on every record, SHA-256 integrity per record, flush + `fsync` on append, reopen verification, campaign-mismatch rejection and tamper detection.

Infrastructure restart therefore resumes the same campaign evidence stream rather than silently creating a replacement run. This durable substrate protects the one-pass evidence posture and exact continuation state; it is not a prohibition on future scientifically justified reruns or replays.

### Amendment C: Failure-boundary capsule semantics

The earlier same-model retry/terminal-failure design was superseded by owner clarification. The old retry policy and retry-terminal coverage states are removed. The manifest now carries `one_pass_evidence_standard=true` plus a recursive `escalation_policy`. Every wrong/stalled model execution freezes a typed, content-addressed escalation capsule before recovery mutation; stronger models inherit the exact reconstructable boundary and continue the same task trajectory.
