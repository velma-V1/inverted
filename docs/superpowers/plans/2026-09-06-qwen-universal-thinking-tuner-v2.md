# Qwen Universal Thinking Tuner V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing Qwen thinking tuner into a universal paired adaptive operating-surface test that collects enough evidence to separate semantic capability, contract compliance, reasoning-budget effects, temperature plateaus, interaction effects, and holdout confidence without wasting calls.

**Architecture:** Keep `inverted.qwen_thinking_tuning` and the PowerShell launcher as the stable entry point, but move V2 concerns into focused `inverted.universal_tuning` modules. Preserve V1 functions/artifacts for audit compatibility. V2 freezes deterministic task pools, executes paired profiles, records append-only atomic evidence, applies deterministic paired statistics, schedules only unresolved decisions, and emits versioned machine/human reports.

**Tech Stack:** Python 3 stdlib, pytest, Ollama HTTP API, JSON/JSONL, PowerShell launcher. No SciPy/pandas dependency.

**Spec:** `docs/superpowers/specs/2026-09-06-qwen-universal-thinking-tuner-v2-design.md`

## Global Constraints
- Existing 192-call V1 evidence is immutable and may only be rescored into derived artifacts.
- V2 remains outside frozen Test-1 source-binding directories.
- Certification requires at least 40 fresh atomic holdout tasks per family.
- Close contests expand through 60, 80, and 120 atomic-task checkpoints.
- Superiority threshold: +5 percentage points semantic accuracy.
- Non-inferiority margin: -2 percentage points semantic accuracy.
- Temperature point optima are forbidden unless paired semantic evidence resolves them; otherwise report a plateau.
- Every scheduled model call must carry a decision reason and hard call ceilings remain enforced.

---
### Task 1: Universal Evidence and Scoring Core

**Files:**
- Create: `src/inverted/universal_tuning/__init__.py`
- Create: `src/inverted/universal_tuning/core.py`
- Create: `src/inverted/universal_tuning/scoring.py`
- Create: `tests/test_universal_tuning_scoring.py`

**Interfaces:**
- Produces `AtomicTask`, `Profile`, `AtomicScore`, `Observation`, `FailureClass`, `score_atomic_task()`.
- Later tasks consume these immutable dataclasses and scorer registry.

- [ ] Write failing tests proving semantic correctness can pass while contract correctness fails, including routing/list-vs-object, logic, tool selection, governance, synthesis number-word normalization, and coding-expression semantics.
- [ ] Run `python -m pytest tests/test_universal_tuning_scoring.py -q` and confirm RED because V2 modules do not exist.
- [ ] Implement immutable core dataclasses plus deterministic semantic canonicalizers and strict contract validators; coding tasks use AST/executable-safe expression checks rather than exact-string equality.
- [ ] Run the scoring tests and confirm GREEN.
- [ ] Commit with `git commit -m "feat: add universal tuning evidence and scoring core"`.

### Task 2: Deterministic Task Generators and Frozen Pools

**Files:**
- Create: `src/inverted/universal_tuning/tasks.py`
- Create: `tests/test_universal_tuning_tasks.py`

**Interfaces:**
- Consumes `AtomicTask`.
- Produces `TaskFamilySpec`, `TaskPool`, `build_qwen_task_pool(seed, per_family)`, `freeze_task_pool(path, pool)`.

- [ ] Write failing tests for all 12 families, >=120 unique atomic tasks/family, deterministic generation, difficulty strata, stable task IDs, answer determinism, and SHA-256 manifest stability.
- [ ] Run the task tests and confirm RED.
- [ ] Implement seeded generators with no model calls and a canonical JSON manifest whose hash changes on any task/scorer mutation.
- [ ] Run the task tests and confirm GREEN.
- [ ] Commit with `git commit -m "feat: add frozen universal tuning task pools"`.
### Task 3: Paired Statistics and Decision Gates

**Files:**
- Create: `src/inverted/universal_tuning/statistics.py`
- Create: `tests/test_universal_tuning_statistics.py`

**Interfaces:**
- Consumes paired atomic semantic outcomes grouped by micro-batch.
- Produces `PairedComparison`, `paired_bootstrap_ci()`, `classify_comparison()`, `required_checkpoint()`.

- [ ] Write failing tests for deterministic bootstrap reproducibility, +5 pp superiority, -2 pp non-inferiority, CLOSE interval logic, checkpoint expansion 40->60->80->120, plateau/tie classification, and refusal to certify below 40 tasks.
- [ ] Run the statistics tests and confirm RED.
- [ ] Implement a pure-stdlib deterministic clustered bootstrap over matched micro-batches with fixed bootstrap seed and explicit CI fields; do not rank profiles by latency until semantics are statistically equivalent.
- [ ] Run the statistics tests and confirm GREEN.
- [ ] Commit with `git commit -m "feat: add paired tuning decision statistics"`.

### Task 4: V1 Immutable Rescoring Audit

**Files:**
- Create: `src/inverted/universal_tuning/v1_audit.py`
- Create: `tests/test_universal_tuning_v1_audit.py`

**Interfaces:**
- Consumes a V1 `observations.jsonl`, its source hash, and V1 case definitions.
- Produces a separate `v1-derived-audit.jsonl` plus `v1-derived-summary.json`; never mutates V1 files.

- [ ] Write failing tests using fixtures that reproduce the observed semantic-pass/contract-fail patterns from the completed run and assert original bytes remain unchanged.
- [ ] Run the audit tests and confirm RED.
- [ ] Implement deterministic V1 response parsing, semantic rescoring, contract rescoring, failure classification, and source/evaluator hashes.
- [ ] Run the audit tests and confirm GREEN.
- [ ] Commit with `git commit -m "feat: add immutable v1 tuning rescore audit"`.

### Task 5: Adaptive Operating-Surface Scheduler

**Files:**
- Create: `src/inverted/universal_tuning/scheduler.py`
- Create: `tests/test_universal_tuning_scheduler.py`

**Interfaces:**
- Consumes task pool, observations, model metadata, decision thresholds.
- Produces deterministic `ScheduledTrial` objects with `decision_reason`, stage, profile, task IDs, and inference seed.

- [ ] Write failing synthetic-surface tests for direct-sufficient, budget boundary, broad temperature plateau, narrow temperature optimum, noisy tie, contract-only failure, capability limit, and budget x temperature interaction.
- [ ] Assert no winner is certified before 40 fresh holdout tasks and dominated candidates stop consuming calls once they cannot change a decision.
- [ ] Implement stages: direct-vs-thinking gate; adaptive budget bracketing; temperature surface with edge expansion and 0.10/0.05/0.02/0.01/0.001 refinement only while informative; bounded interaction; 40/60/80/120 holdout certification.
- [ ] Run scheduler tests and confirm GREEN.
- [ ] Commit with `git commit -m "feat: add adaptive universal tuning scheduler"`.
### Task 6: Universal Runner, Evidence Store, Resume, and Progress

**Files:**
- Create: `src/inverted/universal_tuning/runner.py`
- Create: `src/inverted/universal_tuning/evidence.py`
- Create: `tests/test_universal_tuning_runner.py`

**Interfaces:**
- Consumes `ScheduledTrial`, a model adapter exposing `complete(task, profile, seed)`, and frozen protocol/task manifests.
- Produces append-only `atomic_observations.jsonl`, `raw_calls.jsonl`, scheduler state reconstructed from evidence, and responsive progress.

- [ ] Write failing tests for paired same-task execution, distinct batch seeds, no duplicate calls on resume, hash mismatch rejection, hard-call ceilings, append-only evidence, decision-reason persistence, and terminal-width responsive progress.
- [ ] Run runner tests and confirm RED.
- [ ] Implement evidence commit ordering so raw call envelope and scored atomic observations are durable before scheduler advancement; infrastructure/provenance failures abort rather than count as model failures.
- [ ] Implement projected-call progress from unresolved scheduler decisions instead of the hard ceiling.
- [ ] Run runner tests and confirm GREEN.
- [ ] Commit with `git commit -m "feat: add resumable universal tuning runner"`.

### Task 7: Qwen/Ollama Adapter and Stable CLI Migration

**Files:**
- Create: `src/inverted/universal_tuning/qwen_ollama.py`
- Modify: `src/inverted/qwen_thinking_tuning.py`
- Modify: `scripts/run-qwen-thinking-tuning.ps1`
- Create: `tests/test_universal_tuning_qwen_cli.py`

**Interfaces:**
- `QwenOllamaAdapter.complete(task, profile, seed)` preserves bounded two-stage thinking semantics and runtime provenance.
- Existing launcher and module remain the user entry point. Default real protocol becomes V2; `--protocol v1` remains available for compatibility/dry diagnostics.

- [ ] Write failing tests for exact Ollama request options, direct and bounded-thinking calls, natural-thinking token capture, V2 default dry-run geometry, V1 compatibility, and PowerShell execution with repo-local PYTHONPATH.
- [ ] Run CLI/adapter tests and confirm RED.
- [ ] Implement adapter metadata for general/coding temperature anchors, profile serialization, provenance digest checks, and CLI routing without weakening Test-1 source binding.
- [ ] Run CLI/adapter tests and confirm GREEN.
- [ ] Commit with `git commit -m "feat: route qwen tuner through universal v2 protocol"`.

### Task 8: Reports, Synthetic End-to-End Proof, and Regression Gate

**Files:**
- Create: `src/inverted/universal_tuning/report.py`
- Create: `tests/test_universal_tuning_end_to_end.py`
- Modify only if required: `tests/test_qwen_thinking_tuning.py`

**Interfaces:**
- Produces `protocol-v2-manifest.json`, `operating-surface.json`, `report.md`, and final summary with evidence hashes and decision statuses.

- [ ] Write failing end-to-end synthetic tests proving: broad plateau cannot yield fake 0.001 optimum; narrow optimum is resolved only when semantics support it; minimum useful budget chooses the smallest non-inferior cap; contract-only failure is reported separately; interaction changes policy when warranted.
- [ ] Implement report generation and synthetic adapter fixtures until all V2 acceptance criteria are machine-tested.
- [ ] Run all V2 tests, then existing tuner tests, then `python -m pytest -q`.
- [ ] Run `scripts/run-qwen-thinking-tuning.ps1 --dry-run` through ExecutionPolicy Bypass and verify no real model calls occur.
- [ ] Commit with `git commit -m "test: validate universal qwen tuner v2 end to end"`.
- [ ] Do not launch a real V2 Qwen campaign; report the exact tested command and call geometry for separate authorization.
