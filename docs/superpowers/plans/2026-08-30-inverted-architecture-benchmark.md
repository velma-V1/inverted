# Inverted Architecture Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained, falsifiable benchmark that compares direct AI execution against a non-AI executor plus AI auditor, captures exhaustive telemetry, and emits a preregistered `SUPPORTED`, `REFUTED`, or `INCONCLUSIVE` verdict only for adequately powered decisive runs.

**Architecture:** A deterministic synthetic-world core generates seeded tasks with hidden oracle truth. Six architecture arms consume identical tasks through pluggable model adapters. Every transition emits normalized telemetry into append-only artifacts; the statistics/reporting layer reconstructs metrics from those artifacts and applies preregistered verdict gates.

**Tech Stack:** Python 3.11+, standard library, httpx, PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-08-30-inverted-architecture-benchmark-design.md`

## Global Constraints

- Python 3.11+.
- No agent framework, database, vector store, MCP layer, or external evaluation framework.
- CI runs offline using deterministic mock models.
- Ground truth is deterministic code and never an LLM judge.
- Same model configuration is used for executor/auditor comparisons.
- All randomized behavior is reproducible from recorded seeds.
- Real model failures never silently fall back to mocks.
- Every model call and trial is persisted with stable IDs and all provider telemetry available.
- Smoke runs are `NON-DECISIVE`; only adequately powered decisive runs may return `SUPPORTED`, `REFUTED`, or `INCONCLUSIVE`.

---

### Task 1: Core domain types, synthetic state, and hidden oracle

**Files:**
- Create: `pyproject.toml`
- Create: `src/inverted/__init__.py`
- Create: `src/inverted/domain.py`
- Create: `src/inverted/oracle.py`
- Test: `tests/test_oracle.py`

**Interfaces:**
- Produces `WorldState`, `Requirement`, `TaskCase`, `Action`, `OracleResult`, `evaluate_task(task, state, actions)`.
- Later tasks rely on JSON-serializable dataclasses and stable requirement IDs.

- [ ] Write failing tests proving the oracle detects correct states, omitted requirements, preservation violations, procedure violations, and catastrophic violations.
- [ ] Run `pytest tests/test_oracle.py -q` and verify failures are due to missing implementation.
- [ ] Implement immutable-ish JSON-serializable domain dataclasses and exact requirement evaluators; do not use model output in oracle decisions.
- [ ] Run `pytest tests/test_oracle.py -q`; all tests pass.
- [ ] Refactor only after green.

### Task 2: Seeded task families, complexity scaling, and controlled fault injection

**Files:**
- Create: `src/inverted/tasks.py`
- Create: `src/inverted/system_executor.py`
- Test: `tests/test_tasks.py`
- Test: `tests/test_system_executor.py`

**Interfaces:**
- Produces `generate_task(family, complexity, seed) -> TaskCase`.
- Produces `generate_candidate(task, target_quality, seed) -> Candidate` with recorded injected fault categories.

- [ ] Write failing tests for deterministic generation: identical seed/config gives byte-equivalent task; different seeds vary task content.
- [ ] Write failing tests that L1/L2/L3/L4 requirement-count ranges are 1–2, 3–5, 6–9, and 10–15.
- [ ] Write failing tests for all three families: `state`, `policy`, `reconciliation`.
- [ ] Write failing tests showing target-quality extremes change realized candidate correctness while keeping candidates structurally legal.
- [ ] Run the focused tests and verify RED.
- [ ] Implement seeded generators and fault injection with explicit fault IDs/categories.
- [ ] Run focused tests and full suite; verify GREEN.

### Task 3: Model adapters and exhaustive per-call telemetry

**Files:**
- Create: `src/inverted/models.py`
- Create: `src/inverted/telemetry.py`
- Test: `tests/test_models.py`
- Test: `tests/test_telemetry.py`

**Interfaces:**
- `ModelAdapter.complete(messages, *, role, context) -> ModelResponse`.
- Implement `MockModelAdapter`, `OllamaAdapter`, `OpenAICompatibleAdapter`.
- `ModelCallRecord` normalizes timing, usage, throughput, errors, retries, inference parameters, raw provider usage, and optional content.

- [ ] Write failing tests proving mock responses are deterministic and no real adapter silently falls back to mock behavior.
- [ ] Write failing telemetry tests for input/output/total tokens, latency, generated tokens/sec, end-to-end tokens/sec, retry/error fields, TTFT nullable behavior, and provider metadata preservation.
- [ ] Verify tests fail before production code.
- [ ] Implement adapters with httpx and provider-specific usage normalization. When a metric is unavailable, persist `null`; never synthesize it.
- [ ] Implement optional prompt/response capture controlled by `capture_content`.
- [ ] Verify focused and full tests pass.

### Task 4: Six architecture arms and matched-budget experiment runner

**Files:**
- Create: `src/inverted/arms.py`
- Create: `src/inverted/runner.py`
- Test: `tests/test_arms.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- `run_arm(arm, task, model, executor_quality, seed, budget) -> TrialRecord`.
- Arms: `A_DIRECT`, `B_DIRECT_CHECKED`, `C_SYSTEM`, `D_INVERTED`, `E_RANDOM_AUDITOR`, `F_ORACLE_AUDITOR`.
- Runner emits stable run/trial/candidate/call IDs and event records.

- [ ] Write failing tests that all six arms execute the same task identity and record architecture arm explicitly.
- [ ] Write failing tests showing E uses seeded random decisions and F uses hidden oracle decisions.
- [ ] Write failing tests that D rejects an auditor-failed candidate and may attempt the next candidate within budget.
- [ ] Write failing tests that parser failures/timeouts/retries are retained as observed failures.
- [ ] Write failing tests for equal-token budget termination.
- [ ] Implement minimal arm logic and runner orchestration.
- [ ] Verify focused and full suites pass.

### Task 5: Statistics, bootstrap uncertainty, crossover analysis, and preregistered verdict

**Files:**
- Create: `src/inverted/statistics.py`
- Create: `src/inverted/verdict.py`
- Test: `tests/test_statistics.py`
- Test: `tests/test_verdict.py`

**Interfaces:**
- `aggregate_trials(trials) -> Summary`.
- `bootstrap_rate_difference(..., seed) -> ConfidenceInterval`.
- `estimate_crossover(...) -> CrossoverResult`.
- `decide_verdict(summary, config) -> VerdictResult`.

- [ ] Write failing tests for success/requirement/catastrophic rates, auditor confusion matrix, latency percentiles, token efficiency, and failure taxonomy counts.
- [ ] Write failing deterministic bootstrap tests using fixed seeds.
- [ ] Write failing verdict tests for every `SUPPORTED` gate, each `REFUTED` condition, `INCONCLUSIVE`, and `NON-DECISIVE` insufficient-power behavior.
- [ ] Verify RED.
- [ ] Implement calculations using standard library statistics/random only.
- [ ] Verify GREEN and no division-by-zero/sparse-slice crashes.

### Task 6: Artifact persistence and exhaustive final report

**Files:**
- Create: `src/inverted/artifacts.py`
- Create: `src/inverted/report.py`
- Test: `tests/test_artifacts.py`
- Test: `tests/test_report.py`

**Interfaces:**
- `ArtifactWriter` writes append-only `events.jsonl` and `model_calls.jsonl`, trial CSV/JSONL, failure CSV, summary JSON/CSV, config, provenance, and report text.
- `render_report(summary, provenance) -> str` prints verdict first, followed by all metric families required by the spec.

- [ ] Write failing tests for all required filenames and round-trip JSON/CSV readability.
- [ ] Write failing report tests asserting presence of: verdict, observation counts, A/B/D comparisons, confidence intervals, crossover, per-model/family/complexity/quality slices, auditor TP/TN/FP/FN, tokens, tokens/sec, latency p50/p90/p95/p99, TTFT availability, call/retry/timeout/parser errors, known cost, failure taxonomy, environment provenance, and raw artifact paths.
- [ ] Verify RED.
- [ ] Implement persistence and deterministic text rendering.
- [ ] Verify GREEN and full suite.

### Task 7: CLI, smoke/decisive configurations, documentation, and offline CI

**Files:**
- Create: `src/inverted/cli.py`
- Create: `configs/smoke.yaml`
- Create: `configs/decisive.yaml`
- Create: `README.md`
- Create: `.github/workflows/test.yml`
- Test: `tests/test_cli.py`

**Interfaces:**
- CLI: `python -m inverted.cli --config configs/smoke.yaml`.
- Supports environment-substituted API keys; secrets are never written to artifacts.

- [ ] Write failing CLI test executing an offline mock smoke run in a temporary directory and asserting exit code 0 plus all artifacts.
- [ ] Write failing test proving smoke config cannot emit a scientific `SUPPORTED`/`REFUTED` verdict.
- [ ] Implement CLI/config parsing, config validation, provider selection, provenance, and report printing.
- [ ] Document exact Ollama and OpenAI-compatible invocation examples, telemetry caveats, and interpretation of verdicts.
- [ ] Add GitHub Actions workflow for Python 3.11 and 3.12 running `pytest -q` plus mock smoke benchmark.
- [ ] Run full suite and smoke benchmark locally.

### Task 8: End-to-end benchmark integrity and adversarial regression tests

**Files:**
- Create: `tests/test_end_to_end.py`
- Modify as required only files already introduced above.

**Interfaces:**
- Entire repository is the interface: task generation -> six arms -> oracle -> telemetry -> statistics -> verdict -> artifacts/report.

- [ ] Write an end-to-end test with deterministic mock behavior in which the inversion clearly wins; assert `SUPPORTED` only when the decisive minimum sample requirement is deliberately reduced in the test config.
- [ ] Write an end-to-end case where the inversion loses and assert `REFUTED`.
- [ ] Write an end-to-end ambiguous case and assert `INCONCLUSIVE`.
- [ ] Write adversarial tests for plausible-but-wrong candidates, malformed auditor JSON, missing provider usage fields, interrupted/incomplete runs, and zero-success token-efficiency slices.
- [ ] Run `pytest -q` and require zero failures.
- [ ] Run `python -m inverted.cli --config configs/smoke.yaml` and inspect the generated `report.txt` and `summary.json` for consistency.
- [ ] Verify repository contains no API keys, no hidden oracle leakage in prompts, no placeholder/TODO benchmark logic, and no silent mock fallback.
