# SYSTEM_HARVEST_11 Production Execution Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hardened live-capable execution backend beneath the existing harvest orchestrator, proven entirely with synthetic local stand-ins and mechanically disarmed from real inference.

**Architecture:** `ProductionExecutionBackend` composes immutable launch envelopes, workspace leases, a single direct-argv `ProcessEngine`, and 11 thin driver descriptors. The orchestrator remains semantic authority; adapters remain capture/launch-description authority; the backend only executes and transports observable evidence.

**Tech Stack:** Python 3.14, stdlib `subprocess`, `threading`, `hashlib`, `json`, `pathlib`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-system-harvest-11-production-execution-backend-design.md`

## Global Constraints

- No real Codex/Claude/Prime/Pi/oh-my-cli/SWE-agent/mini-SWE-agent/Aider/AegisEvo/OpenHands/Kimi task execution.
- BUILD and DRY_RUN must make target process spawn impossible.
- PREFLIGHT_PROBE may run allowlisted identity/help/version probes only.
- Process creation uses argv with `shell=False`; no shell-string fallback.
- Exact raw capture precedes parsing/classification, except mandatory secret/privacy redaction before persistence.
- `CONTINUE_FROM_FAILURE_BOUNDARY` is preserved for escalation.
- Ambiguous crash state must become reconciliation uncertainty, never blind resend.
- Full repository verification is required before `PRODUCTION_BACKEND_READY`.

---
### Task 1: Arming and immutable launch envelopes

**Files:**
- Create: `src/inverted/system_harvest/arming.py`
- Create: `src/inverted/system_harvest/launch.py`
- Test: `tests/test_system_harvest_production_launch.py`

**Interfaces:**
- Produces `ArmState`, `LaunchEnvelope`, `LaunchEnvelopeError`, `build_launch_envelope()` and `validate_launch_envelope()`.
- Consumes existing `ExecutionCell`, adapter descriptors, and `LaunchSpec`.

- [ ] Write failing tests proving BUILD/DRY_RUN reject task-bearing launch, PREFLIGHT_PROBE accepts only allowlisted non-inference argv, unresolved placeholders fail, and the same logical launch inputs produce the same idempotency key/hash.
- [ ] Run `pytest -q tests/test_system_harvest_production_launch.py` and verify RED on missing modules/types.
- [ ] Implement frozen enums/dataclasses and canonical hashing. Expand adapter argv positionally; reject shell strings and unresolved `{...}` tokens.
- [ ] Run the focused test file and verify GREEN.

```python
assert validate_launch_envelope(build_launch_envelope(...)).valid
with pytest.raises(LaunchEnvelopeError):
    build_launch_envelope(..., arm_state=ArmState.DRY_RUN, task_bearing=True)
```

### Task 2: Workspace leases and secret-safe environment policy

**Files:**
- Create: `src/inverted/system_harvest/workspace.py`
- Create: `src/inverted/system_harvest/environment.py`
- Test: `tests/test_system_harvest_production_workspace.py`
**Interfaces:**
- Produces `WorkspaceLease`, `WorkspaceLeaseManager`, `EnvironmentPolicy`, `EnvironmentSnapshot`, and deterministic redaction/fingerprint helpers.
- Consumes fixture path/hash, cell/execution IDs, run root, and declared secret-variable names.

- [ ] Write failing tests proving fixtures are copied rather than mutated, leases cannot be shared, baseline/final hashes are recorded, interrupted leases remain preserved, and secret values never appear in persisted snapshots or redacted output.
- [ ] Run focused tests and verify RED.
- [ ] Implement content hashing/copy materialization, lease ownership checks, final tree inventory, salted fingerprints, and deterministic redaction tokens.
- [ ] Run focused tests and verify GREEN.

```python
lease = manager.acquire(cell_id="c1", execution_id="e1", fixture=fixture, expected_sha256=digest)
assert lease.workspace_path != fixture
assert secret not in policy.snapshot(env).persistent_json
```

### Task 3: Direct-argv process engine and raw-firehose transport

**Files:**
- Create: `src/inverted/system_harvest/process_engine.py`
- Create: `tests/fixtures/system_harvest_synthetic_target.py`
- Test: `tests/test_system_harvest_process_engine.py`

**Interfaces:**
- Produces `ProcessEngine`, `ProcessObservation`, `ProcessResult`, `ProcessTermination`, and `ProcessSessionHandle`.
- Consumes only a validated `LaunchEnvelope`, environment injection, stdin bytes, and capture/redaction policy.

- [ ] Write failing tests for stdout/stderr interleaving, capture-before-stdin, malformed JSON bytes, partial output, nonzero exit, timeout/no-progress, resource/liveness records, and echoed-secret redaction.
- [ ] Run focused tests and verify RED.
- [ ] Implement `subprocess.Popen(..., shell=False)` with concurrent stdout/stderr drainers, binary capture sinks opened before stdin, monotonic source ordinals, explicit termination classification, and no semantic verdict logic.
- [ ] Run focused tests and verify GREEN.

```python
result = engine.run(envelope, stdin_bytes=b"task\n")
assert result.termination is ProcessTermination.EXITED
assert all(secret not in obs.persisted_text for obs in result.observations)
```

### Task 4: Production execution drivers and frozen registry

**Files:**
- Create: `src/inverted/system_harvest/drivers/base.py`
- Create: `src/inverted/system_harvest/drivers/registry.py`
- Create: `src/inverted/system_harvest/drivers/systems.py`
- Test: `tests/test_system_harvest_production_drivers.py`

**Interfaces:**
- Produces `ResumeCapability`, `ExecutionDriverDescriptor`, `ExecutionDriver`, `all_drivers()`, `driver_by_adapter_id()`, and `validate_driver_registry()`.
- Consumes the existing 11 adapter descriptors and their launch specs.

- [ ] Write failing tests requiring exactly the frozen 11 adapter IDs, a valid adapter launch mode for each driver, explicit resume capability, artifact-watch declarations, family assignment, and the AegisEvo deterministic/live distinction.
- [ ] Run focused tests and verify RED.
- [ ] Implement the six driver families and 11 thin descriptors without adding any alternate generic-shell fallback.
- [ ] Add synthetic launch translation tests for every registered driver and verify GREEN.

```python
report = validate_driver_registry(all_adapters(), all_drivers())
assert report.valid and report.blockers == ()
assert len(all_drivers()) == 11
```
### Task 5: Production backend protocol integration

**Files:**
- Create: `src/inverted/system_harvest/production_backend.py`
- Modify: `src/inverted/system_harvest/backend.py`
- Test: `tests/test_system_harvest_production_backend.py`

**Interfaces:**
- Produces `ProductionExecutionBackend` implementing existing `ExecutionBackend.execute/resume/continue_from_escalation`.
- Consumes schedule/cell lookup, adapters, driver registry, `ProcessEngine`, workspace manager, environment policy, and arm state.

- [ ] Write failing tests proving execute maps process observations to `BackendObservation`, resume preserves execution ID/level, duplicate idempotency keys cannot spawn twice, ambiguous resume returns infrastructure interruption with no blind resend, and escalation continuation requires capsule/model identity.
- [ ] Run focused tests and verify RED.
- [ ] Implement backend composition without provider SDK imports and without semantic correctness logic.
- [ ] Run focused tests and verify GREEN.

```python
backend.execute(cell.cell_id, execution_id, 0)
with pytest.raises(DuplicateLaunchError):
    backend.execute(cell.cell_id, execution_id, 0)
```

### Task 6: Synthetic all-driver acceptance and orchestrator integration

**Files:**
- Test: `tests/test_system_harvest_production_contract.py`
- Modify only if required: `src/inverted/system_harvest/orchestrator.py`

**Interfaces:**
- Exercises every registered production driver through synthetic local executables while preserving existing orchestrator semantics.

- [ ] Write contract tests for all 11 drivers using synthetic launch overrides, asserting zero external-agent executable names are spawned.
- [ ] Add escalation, infrastructure interruption, resume, malformed-output, artifact discovery, and secret-redaction end-to-end cases.
- [ ] Run new production tests plus every `test_system_harvest*.py` test and verify GREEN.
### Task 7: Public exports, live-readiness boundary, and final verification

**Files:**
- Modify: `src/inverted/system_harvest/__init__.py`
- Modify: `docs/superpowers/specs/2026-09-07-system-harvest-11-production-execution-backend-design.md` only for implementation-alignment notes if needed.
- Test: `tests/test_system_harvest_production_readiness.py`

**Interfaces:**
- Produces `ProductionReadinessReport`/`evaluate_production_backend_readiness()` that can report `PRODUCTION_BACKEND_READY` but never `LIVE_HARVEST_READY`.

- [ ] Write readiness tests requiring arm-gate tests, driver registry validation, synthetic acceptance, no real-agent invocation evidence, and explicit separation from live campaign readiness.
- [ ] Export stable production-backend interfaces from `system_harvest.__init__`.
- [ ] Run `python -m compileall -q src/inverted/system_harvest` and static scans for shell execution/provider SDK imports/real-agent invocation in tests.
- [ ] Run every harvest test by explicit path enumeration; require 0 failures.
- [ ] Run `PYTHONPATH=src pytest -q`; recover the actual process result if the desktop tool window expires; require 0 failures before claiming ready.
- [ ] Run `git diff --check` and confirm preserved `runs/` evidence was not modified.

```python
report = evaluate_production_backend_readiness(...)
assert report.production_backend_ready
assert not hasattr(report, "live_harvest_ready") or report.live_harvest_ready is False
```

## Completion rule

The implementation phase is complete only when Tasks 1–7 are GREEN from the final code state. This authorizes a later live-readiness audit; it does not arm or begin the 11-system harvest.
