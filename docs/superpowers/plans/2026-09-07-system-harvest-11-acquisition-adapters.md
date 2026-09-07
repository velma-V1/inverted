# SYSTEM_HARVEST_11 Acquisition Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Implement all eleven declarative acquisition adapters, a shared passive sidecar contract, registry validation and fixture-only capture tests.

**Architecture:** Adapters preserve each target's native evidence surfaces and compose them with shared sidecar capture. They generate acquisition plans and parse synthetic/native fixtures but never execute the real agents during this implementation phase.

**Tech Stack:** Python 3, dataclasses/enums, pathlib, JSON/JSONL, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-system-harvest-11-acquisition-adapters-design.md`

## Global Constraints

- Exactly 11 adapters matching the frozen campaign order.
- Native artifacts remain raw and lossless; normalization adds lineage only.
- Every surface declares `NATIVE`, `SIDECAR`, `DERIVED`, `INSTRUMENTED`, `INACCESSIBLE` or `NOT_APPLICABLE`.
- Adapter construction/validation launches zero live inference, shell commands or network calls.
- Shared sidecar covers environment/git/filesystem/process/runtime evidence without replacing native telemetry.
- Failure-boundary escalation remains owned by the existing common harvest layer.
- TDD: every production behavior is preceded by a failing focused test.
### Task 1: Common adapter contract

**Files:** `adapters/base.py`, `tests/test_system_harvest_adapter_base.py`

- [ ] RED: test evidence origins, immutable descriptors, lossless native artifact declarations and declarative acquisition plans.
- [ ] GREEN: implement the minimum typed contract and validation.

### Task 2: Shared passive sidecar

**Files:** `adapters/sidecar.py`, `tests/test_system_harvest_adapter_sidecar.py`

- [ ] RED: require git/filesystem/process/environment/runtime/state capture surfaces and secret-redaction metadata.
- [ ] GREEN: implement sidecar surface/plan declarations with zero execution.

### Task 3: Frozen registry

**Files:** `adapters/registry.py`, `tests/test_system_harvest_adapter_registry.py`

- [ ] RED: require exactly eleven adapters in campaign order, unique canonical IDs, complete required-channel declarations and no extras.
- [ ] GREEN: implement registry and coverage validation.
### Task 4: Structured stream/session adapters

**Files:** `codex.py`, `prime_agent.py`, `pi.py`, `oh_my_cli.py`, `kimi_cli.py`, `tests/test_system_harvest_adapters_structured.py`

- [ ] RED: prove each adapter declares its native JSON/JSONL/RPC/hook/session artifacts and preserves arbitrary native records unchanged.
- [ ] GREEN: implement five system-specific descriptors/parsers/plans.

### Task 5: Trajectory/history adapters

**Files:** `swe_agent.py`, `mini_swe_agent.py`, `aider.py`, `tests/test_system_harvest_adapters_trajectory.py`

- [ ] RED: prove trajectory/history/repo-map/config/model-stat artifacts retain raw structure and source path lineage.
- [ ] GREEN: implement three adapters.

### Task 6: Hook/EventStream and discovery-first adapters

**Files:** `claude_code.py`, `openhands.py`, `aegisevo.py`, `tests/test_system_harvest_adapters_event.py`

- [ ] RED: prove hook/EventStream surfaces are declared and AegisEvo unknown native surfaces remain explicit discovery requirements rather than guessed fields.
- [ ] GREEN: implement three adapters.
### Task 7: Cross-adapter contract and fixture ingestion

**Files:** `adapters/__init__.py`, `tests/test_system_harvest_adapters_contract.py`

- [ ] RED: instantiate all eleven adapters, build acquisition plans, ingest representative fixture records, preserve raw payload identity and verify required evidence-channel coverage.
- [ ] GREEN: expose public registry helpers and close contract gaps.

### Task 8: Verification

- [ ] Run all adapter and existing `system_harvest` tests.
- [ ] Run complete repository regression with `PYTHONPATH=src`.
- [ ] Compile new package, scan for subprocess/network/provider imports, inspect git status/diff and leave existing `runs/` untouched.

## Self-review

The plan covers native evidence preservation, sidecar evidence, all eleven frozen systems, lossless fixture ingestion, explicit unknown/inaccessible surfaces, declarative launch planning, registry completeness and zero-live-inference validation. No placeholder adapter may satisfy registry tests.
## Execution-review amendments

The implementation review promoted several implied requirements into executable gates:

- `adapters/preflight.py`: inference cannot begin until version/source identity, supported execution mode, required artifact classes and required surfaces are observed on the installed target version.
- `adapters/manifest.py`: exact byte hash/size/source/preserved path are recorded; required missing artifacts block closure; multiple files per artifact class are valid; unexpected artifacts are retained as discoveries.
- `acquisition.py`: exact native stream bytes are append-persisted with flush/fsync and journal hashes; malformed JSONL is retained verbatim with parse failure metadata rather than repaired or discarded.
- `registry.observability_matrix(...)`: preserves per-system/per-channel evidence origin for later 6–12 month analysis.
- Current launch syntax is test-locked for mini-SWE-agent, SWE-agent and oh-my-cli rather than relying on earlier guessed flags.
- OpenHands now has a verified `openhands --headless --json -t {task}` acquisition mode.
- AegisEvo now has the verified deterministic `cargo run -p aegisevo-cli -- demo --seed 17 --output ...` mode plus a required `INSTRUMENTED` live-model-gateway capture surface. No unverified live-harness CLI is fabricated.
- Construction and validation remain fixture-only; no real model or target agent is launched by these tests.
