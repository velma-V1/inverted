# Assistant Value & Trust Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three isolated, hard-budget assistant experiments that measure long-horizon reliability, evidence trust, and safe authority while preserving every generated datum.

**Architecture:** A new `inverted.assistant_value` package reuses the existing model adapter interface but owns its own generators, deterministic oracles, arm runners, budget, evidence store, analyzer, and CLI. No existing file is modified. GitHub/mock validation proves the instrument; real local models provide architecture evidence.

**Tech Stack:** Python 3.11+, existing `httpx`/`PyYAML` model stack, `pytest`, JSONL/CSV/SHA-256 evidence artifacts.

**Spec:** `docs/superpowers/specs/2026-09-01-assistant-value-trust-tests-design.md`

## Global Constraints

- Existing repository files are immutable for this work; branch diff must contain additions only.
- Long-horizon physical model-call ceiling: 1,152.
- Evidence-trust physical model-call ceiling: 1,080.
- Authority physical model-call ceiling: 1,152.
- A failed/timeout/censored invocation consumes one physical call.
- Deterministic/programmatic ground truth is final authority.
- Full prompts/responses and every serializable generated datum are retained.
- Missing provider fields remain null.
- Mock/GitHub runs are instrument validation, never architecture evidence.

---

### Task 1: Freeze contracts with failing tests

**Files:**
- Create: `tests/test_assistant_value_budget.py`
- Create: `tests/test_assistant_value_evidence.py`
- Create: `tests/test_assistant_value_long_horizon.py`
- Create: `tests/test_assistant_value_evidence_trust.py`
- Create: `tests/test_assistant_value_authority.py`
- Create: `tests/test_assistant_value_runner.py`

**Interfaces:**
- Produces the expected APIs consumed by later tasks.

- [ ] Write tests importing `PhysicalCallBudget`, `EvidenceStore`, the three generators/runners, `planned_calls`, and `run_assistant_value_test`.
- [ ] Assert exact hard ceilings, default three-model planned calls (972/1080/1080), deterministic generation, oracle labels, budget refusal, complete evidence artifact set, exact prompt/response preservation, and smoke execution.
- [ ] Push tests without production modules and verify CI fails because `inverted.assistant_value` does not exist.

### Task 2: Shared types and hard physical-call budget

**Files:**
- Create: `src/inverted/assistant_value/__init__.py`
- Create: `src/inverted/assistant_value/types.py`
- Create: `src/inverted/assistant_value/budget.py`

**Interfaces:**
- `PhysicalCallBudget(name: str, cap: int)` with `reserve(...)`, `used`, `remaining`, `to_dict()`.
- `CallBudgetExceeded` exception.
- Common serializable trial/decision dataclasses and stable hashing helpers.

- [ ] Run budget/types tests RED.
- [ ] Implement minimal budget and types.
- [ ] Run budget/types tests GREEN.

### Task 3: Lossless evidence store and model-call capture

**Files:**
- Create: `src/inverted/assistant_value/evidence.py`
- Create: `src/inverted/assistant_value/model_io.py`

**Interfaces:**
- `EvidenceStore(root, test_name, run_id)` append/write/finalize API.
- `invoke_json(...)` reserves budget before invocation, persists prompt, call record/error, response, parse status, and chronological event.

- [ ] Run evidence tests RED.
- [ ] Implement append-only JSONL ledgers, CSV/JSON writers, provenance, integrity audit, complete evidence text, and SHA-256 manifest.
- [ ] Implement model invocation wrapper using the existing adapter `.complete(...)` interface and `MockModelAdapter` context-driven mock payloads.
- [ ] Run evidence tests GREEN.

### Task 4: Long-horizon reliability experiment

**Files:**
- Create: `src/inverted/assistant_value/long_horizon.py`

**Interfaces:**
- `generate_long_horizon_cases(seed, per_horizon, horizons)`.
- `planned_long_horizon_calls(model_count, per_horizon=2, horizons=(8,16,30), arm_count=3) -> int`.
- `run_long_horizon(...)` returning serializable trials/metrics.

- [ ] Run long-horizon tests RED.
- [ ] Implement seeded step graphs, failure injections, direct/checked/inverted arms, deterministic state transitions/oracle, and requested metrics.
- [ ] Verify the default three-model plan equals 972 and cannot exceed 1,152.
- [ ] Run tests GREEN.

### Task 5: Evidence trust / injection / abstention experiment

**Files:**
- Create: `src/inverted/assistant_value/evidence_trust.py`

**Interfaces:**
- `generate_evidence_cases(seed, cases_per_regime)`.
- `planned_evidence_calls(model_count, cases_per_regime=20, regime_count=6, arm_count=3) -> int`.
- `run_evidence_trust(...)`.

- [ ] Run evidence-trust tests RED.
- [ ] Implement six evidence regimes, provenance/freshness metadata, adversarial embedded instructions, deterministic sufficiency resolver/oracle, three arms, calibration and injection metrics.
- [ ] Verify the default three-model plan equals the 1,080 hard ceiling exactly.
- [ ] Run tests GREEN.

### Task 6: Authority / side effects / trustworthy autonomy experiment

**Files:**
- Create: `src/inverted/assistant_value/authority.py`

**Interfaces:**
- `generate_authority_cases(seed, cases_per_class)`.
- `planned_authority_calls(model_count, cases_per_class=15, class_count=8, arm_count=3) -> int`.
- `run_authority(...)`.

- [ ] Run authority tests RED.
- [ ] Implement eight simulated tool classes, deterministic permissions/approval/reversibility policy, three arms, least-privilege and safe-autonomy metrics.
- [ ] Verify the default three-model plan equals 1,080 and remains below 1,152.
- [ ] Run tests GREEN.

### Task 7: Unified runner, CLI, and configs

**Files:**
- Create: `src/inverted/assistant_value/runner.py`
- Create: `src/inverted/assistant_value/cli.py`
- Create: `configs/assistant-value-smoke.yaml`
- Create: `configs/assistant-value-local.yaml`

**Interfaces:**
- `run_assistant_value_test(test_name, config, models, output_dir, run_id, progress_callback=None)`.
- CLI: `python -m inverted.assistant_value.cli --config <path> --test long_horizon|evidence_trust|authority|all --output-dir <path> --run-id <id>`.

- [ ] Run runner tests RED.
- [ ] Implement YAML/env configuration, pre-run worst-case plan rejection, per-test budget creation, evidence finalization, exact progress, and model unload between campaigns where supported.
- [ ] Smoke-run all three experiments with the deterministic mock model.
- [ ] Verify every smoke evidence directory passes its own integrity report.
- [ ] Run runner tests GREEN.

### Task 8: Dedicated GitHub instrument validation

**Files:**
- Create: `.github/workflows/assistant-value-validation.yml`

**Interfaces:**
- No runtime API; validates package on Linux and checks generated artifacts.

- [ ] Add a workflow that installs `.[test]`, runs all pytest tests, executes the three-test smoke campaign, and programmatically asserts `integrity.json` is clean for all three packets.
- [ ] Push and verify both the existing repository test workflow and the new assistant-value workflow are green.

### Task 9: Final integrity and branch review

**Files:** none.

- [ ] Run full `pytest -q` through GitHub Actions on the final feature-branch SHA.
- [ ] Run the all-tests mock smoke on the final feature-branch SHA.
- [ ] Compare `main...build/assistant-value-trust-tests` and verify every changed path has status `added`; any modified/removed baseline path is a release blocker.
- [ ] Verify the three configured hard ceilings and default physical-call plans from generated `budget.json`.
- [ ] Inspect the feature diff for hidden-gold leakage, silent data dropping, unsafe real side effects, and fabricated telemetry.
- [ ] Only after all checks are green, present branch integration options.