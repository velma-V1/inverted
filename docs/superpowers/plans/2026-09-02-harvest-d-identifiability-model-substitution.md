# Harvest D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the model-free Harvest D experiment harness that freezes evidence provenance, measures model/system capability boundaries, enforces causal controls, validates deterministic kernel failure handling, supports Qwen routing and capability-ratchet promotion, and emits reproducible artifacts ready for later real local-model runs.

**Architecture:** Add an isolated `src/inverted/harvest_d/` package that does not modify frozen Test 2/Test 3 experiment code. The package uses immutable dataclasses/enums, JSON/JSONL/CSV artifacts, deterministic hashing, a state/authority/transaction kernel, causal intervention records, a versioned capability envelope, promotion gates, failure injection contracts, routing analysis, and a model-free CLI. Real Ollama inference is deliberately outside normal CI and enters later through a small adapter seam.

**Tech Stack:** Python 3 standard library, pytest, existing INVERTED repository conventions.

**Spec:** `docs/superpowers/specs/2026-09-02-harvest-d-identifiability-model-substitution-design.md`

## Global Constraints

- Base lineage is `0d67ba4e5578b4c14225eb83b726fd137dfffecd`; frozen evidence is never rewritten.
- Normal CI is model-free and requires no network or cloud credentials.
- No production code is written before a failing test demonstrates the desired behavior.
- Physical model-call identity is globally unique; duplicate identities invalidate evidence.
- A model cannot authorize, commit, self-certify, or promote its own knowledge.
- Unknown external effect state triggers reconciliation, never blind retry.
- Hard-invariant violation suspends candidate/promoted knowledge immediately.
- Harvest D scope is frozen to D0/D1/D2/D3/D4/D5/D6/D6B/D7.

---

### Task 1: Core schemas, enums, deterministic identity, and telemetry

**Files:**
- Create: `src/inverted/harvest_d/__init__.py`
- Create: `src/inverted/harvest_d/types.py`
- Create: `src/inverted/harvest_d/telemetry.py`
- Test: `tests/test_harvest_d_types.py`
- Test: `tests/test_harvest_d_telemetry.py`

**Interfaces:**
- Produces `ClaimState`, `Disposition`, `RouteMode`, `CapabilityState`, `MechanismClass`, `PromotionState`, `ClosureState`, `SequentialDecision`, `SystemInvolvement`, `StepRecord`, `stable_hash()`, and `IdentityRegistry`.

- [ ] Write failing tests proving stable hashing is order-independent for mappings, physical call IDs cannot be registered twice, and all ten system-involvement channels remain independently observable.
- [ ] Run focused tests and verify RED because `inverted.harvest_d` does not exist.
- [ ] Implement immutable enums/dataclasses and deterministic canonical JSON hashing.
- [ ] Run focused tests and verify GREEN.
- [ ] Refactor only duplication; rerun focused tests.
- [ ] Commit.

### Task 2: D0 evidence ledger and claim classification

**Files:**
- Create: `src/inverted/harvest_d/evidence.py`
- Test: `tests/test_harvest_d_evidence.py`

**Interfaces:**
- Consumes `ClaimState`, `stable_hash`, `IdentityRegistry`.
- Produces `EvidenceSource`, `EvidenceClaim`, `ReadinessQuestion`, `EvidenceLedger`, `EvidenceIntegrityError`.

- [ ] Write failing tests that diagnostic/contaminated evidence cannot be promoted beyond OBSERVED, duplicate physical call identity raises a blocker, and readiness questions preserve contradictions instead of averaging them away.
- [ ] Verify RED.
- [ ] Implement evidence ledger and explicit source-quality/contamination gates.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 3: D1 deterministic kernel, authority consumption, transaction/replay safety

**Files:**
- Create: `src/inverted/harvest_d/kernel.py`
- Create: `src/inverted/harvest_d/faults.py`
- Test: `tests/test_harvest_d_kernel.py`
- Test: `tests/test_harvest_d_faults.py`

**Interfaces:**
- Produces `CanonicalState`, `AuthorityLease`, `ProofCarryingAction`, `EffectReceipt`, `TransactionRecord`, `TrustedKernel`, `KernelViolation`, `FaultInjection`, `FaultLayer`, `EffectStatus`.

- [ ] Write failing tests for stale-state rejection, mutated-action proof invalidation, one-time authority consumption, rollback not resurrecting authority, duplicate-effect prevention, unknown-effect reconciliation, system-owned DONE, and invalid fault definitions.
- [ ] Verify RED.
- [ ] Implement minimal deterministic kernel and fault-contract validator.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 4: Capability envelope, system-involvement metrics, and frontier analysis

**Files:**
- Create: `src/inverted/harvest_d/frontier.py`
- Test: `tests/test_harvest_d_frontier.py`

**Interfaces:**
- Produces `CapabilityKey`, `CapabilityObservation`, `CapabilityEnvelope`, `FrontierMetrics`, `architecture_intervention_ratio()`, `intervention_value()`, `size_dependence_index()`, `synergy()`, `minimum_required_scaffolding()`.

- [ ] Write failing tests for per-capability state separation, safe division/undefined metrics, lexicographic selection of the least-involved noninferior configuration, and immutable/versioned envelope updates.
- [ ] Verify RED.
- [ ] Implement frontier/envelope metrics without a blended master score.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 5: Promotion state machine and capability ratchet

**Files:**
- Create: `src/inverted/harvest_d/knowledge.py`
- Test: `tests/test_harvest_d_knowledge.py`

**Interfaces:**
- Produces `KnowledgeObject`, `PromotionEvidence`, `KnowledgeRegistry`, `PromotionError`, `RatchetMetrics`.

- [ ] Write failing tests proving a single success cannot exceed OBSERVED, a model explanation cannot exceed HYPOTHESIZED, CAUSALLY_VERIFIED requires targeted+sham same-state evidence, promotion requires neighbor/fresh/regression gates, hard-invariant violation suspends knowledge, rollback restores previous envelope version, and authority expansion is forbidden.
- [ ] Verify RED.
- [ ] Implement promotion/rollback state machine and ratchet metrics.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 6: Routing controls and causal intervention analysis

**Files:**
- Create: `src/inverted/harvest_d/routing.py`
- Create: `src/inverted/harvest_d/causal.py`
- Test: `tests/test_harvest_d_routing.py`
- Test: `tests/test_harvest_d_causal.py`

**Interfaces:**
- Produces `RouteDecision`, `RoutingMetrics`, `compute_routing_metrics()`, `CausalPair`, `CausalResult`, `classify_mechanism()`.

- [ ] Write failing tests for missed/false escalation, call-rate-matched sham router validation, premature/late escalation, exact-state intervention/sham matching, and REQUIRED/CONDITIONAL/REDUNDANT/HARMFUL/UNRESOLVED classification.
- [ ] Verify RED.
- [ ] Implement deterministic routing/causal analysis helpers.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 7: Artifact writer, campaign manifest, deterministic CLI, and D0/D1 dry run

**Files:**
- Create: `src/inverted/harvest_d/artifacts.py`
- Create: `src/inverted/harvest_d/campaign.py`
- Create: `src/inverted/harvest_d/cli.py`
- Create: `configs/harvest-d.json`
- Test: `tests/test_harvest_d_artifacts.py`
- Test: `tests/test_harvest_d_campaign.py`
- Test: `tests/test_harvest_d_cli.py`

**Interfaces:**
- Produces `HarvestDConfig`, `HarvestDCampaign`, `ArtifactWriter`, `main()`.

- [ ] Write failing tests that the dry run emits the required master/provenance/readiness/kernel/transaction/capability/promotion artifacts, creates SHA-256 checksums, requires no model/network, and refuses a config that exceeds stage/call or scope constraints.
- [ ] Verify RED.
- [ ] Implement config loader, deterministic D0/D1 model-free campaign, artifact finalization, and CLI.
- [ ] Verify GREEN.
- [ ] Commit.

### Task 8: CI wiring and complete model-free regression

**Files:**
- Create: `.github/workflows/harvest-d-validation.yml`
- Test: all Harvest D tests plus existing repository suite.

**Interfaces:**
- CI runs `python -m pytest -q` and a Harvest D dry-run command with no model credentials/network requirements.

- [ ] Add model-free workflow only after the CLI/tests are green locally.
- [ ] Run all Harvest D tests.
- [ ] Run the full repository suite.
- [ ] Run `python -m inverted.harvest_d.cli --config configs/harvest-d.json --output <tempdir> --dry-run` and verify required artifacts/checksums.
- [ ] Confirm no normal workflow invokes Ollama or cloud inference.
- [ ] Commit.

### Task 9: Verification and Test 5 handoff skeleton

**Files:**
- Create: `docs/harvest-d-local-run.md`
- Create: `docs/harvest-d-test5-handoff-schema.md`

**Interfaces:**
- Documents exact local commands, model-artifact freeze requirements, call ceilings, stop rules, and D7 handoff fields.

- [ ] Document only commands/interfaces proven by tests.
- [ ] Run final full suite and dry run again after docs/config changes.
- [ ] Verify branch contains no modification to frozen evidence paths.
- [ ] Verify commit history and GitHub Actions are green before claiming completion.
- [ ] Commit.