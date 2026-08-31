# Hybrid Validation and Local Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the inverted benchmark exhaustively in GitHub cloud and reduce the local real-model run to only non-redundant, correctly paired evidence collection with progress/checkpoint/resume.

**Architecture:** Add an explicit execution-plan layer between `ExperimentConfig` and `run_arm`, so redundant conditions are removed before inference and non-AI candidate seeds are model-independent. Add append-only checkpoints/progress to the existing runner and deterministic validation scenarios to CI. Local execution remains entirely within Inverted.

**Tech Stack:** Python 3.11+, pytest, GitHub Actions, PowerShell 7/Windows PowerShell-compatible scripts, Ollama HTTP API, existing CSV/JSONL artifact writer.

**Spec:** `docs/superpowers/specs/2026-08-31-hybrid-validation-and-local-handoff-design.md`

## Global Constraints

- Synthetic/mock results validate the instrument only; never label them architecture evidence.
- Primary statistics continue to cluster by independent `task_id`.
- `A_DIRECT`/`B_DIRECT_CHECKED` run once per model/task, not once per executor quality.
- `C_SYSTEM`/`E_RANDOM_AUDITOR`/`F_ORACLE_AUDITOR` run once per task/quality independent of model.
- `D_INVERTED` runs for every model/task/quality combination.
- Non-AI candidate generation is invariant to auditor model identity.
- Final benchmark artifact contract remains ten files.
- Local automation fails closed when Inverted prerequisites are missing.

---

### Task 1: Execution plan and candidate-pairing invariance

**Files:**
- Modify: `src/inverted/runner.py`
- Modify: `src/inverted/arms.py`
- Modify: `tests/test_runner.py`
- Modify: `tests/test_arms.py`

**Interfaces:**
- Produces: `TrialPlan` dataclass, `build_trial_plan(config, models) -> list[TrialPlan]`, `candidate_seed(task_id, quality, seed, epoch, attempt) -> int`.
- `run_experiment` consumes the plan instead of a rectangular `itertools.product` loop.

- [ ] Write failing tests proving A/B are quality-deduplicated, C/E/F are model-deduplicated, D spans all model x quality cells, and two model identities receive identical non-AI candidate sequences.
- [ ] Run targeted runner/arm tests and verify failures.
- [ ] Implement `TrialPlan`/`build_trial_plan` and remove model identity/trial ID from non-AI candidate RNG inputs.
- [ ] Run targeted tests and full existing suite.
- [ ] Commit `fix: pair candidates and remove redundant trial cells`.

### Task 2: Exact progress, checkpoints, and resume

**Files:**
- Modify: `src/inverted/runner.py`
- Modify: `src/inverted/cli.py`
- Create: `src/inverted/checkpoint.py`
- Modify: `tests/test_runner.py`
- Create: `tests/test_checkpoint.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces: `CheckpointStore(path)`, `completed_keys()`, `append_trial(trial)`, `load_trials()`; CLI flags `--checkpoint`, `--resume`, `--progress`.
- `run_experiment(..., checkpoint_store=None, progress_callback=None, resume=False)` skips completed plan keys and emits exact `(completed,total,plan_item)` progress.

- [ ] Write failing tests for append/load, interrupted-then-resumed equivalence, no duplicate trial execution on resume, and exact progress totals.
- [ ] Run targeted tests and verify failures.
- [ ] Implement append-only JSONL checkpoint and progress callback.
- [ ] Add CLI flags and a terminal progress renderer that prints completed/total/percent/model/arm/family/complexity/quality/seed/epoch.
- [ ] Run targeted tests and full suite.
- [ ] Commit `feat: add resumable checkpoints and exact progress`.

### Task 3: Deterministic known-answer validation campaigns

**Files:**
- Create: `src/inverted/validation.py`
- Create: `tests/test_validation.py`
- Create: `configs/validation-stress.yaml`
- Create: `scripts/run_validation.py`

**Interfaces:**
- Produces controlled mock scenarios `supported`, `refuted`, `inconclusive`, `non_decisive`, `null_effect`, and `positive_effect`; each returns expected/observed verdict plus summary metadata.

- [ ] Write failing tests for all four verdict classes and null/positive effect behavior.
- [ ] Run tests and verify failures.
- [ ] Implement deterministic scenario generation using existing MockModelAdapter/runner/statistics/verdict code.
- [ ] Add stress config spanning all families/complexities/qualities/seeds/epochs/arms with mock adapters and explicit `INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE` metadata.
- [ ] Add script writing `validation-manifest.json` and campaign outputs.
- [ ] Run validation tests and stress script locally/CI-compatible.
- [ ] Commit `test: add known-answer validation campaigns`.

### Task 4: Failure-injection and invariance regression expansion

**Files:**
- Modify: `tests/test_models.py`
- Modify: `tests/test_arms.py`
- Modify: `tests/test_statistics.py`
- Modify: `tests/test_artifacts.py`
- Modify: `tests/test_end_to_end.py`

**Interfaces:**
- Tests only; no new production API unless a failure case exposes a missing seam.

- [ ] Add tests for malformed executor/auditor JSON, parser/model errors, budget exhaustion, retry/rejection accounting, arm-order invariance, model-order invariance, repeated-measure bootstrap attack, deterministic replay, and ten-artifact row/schema consistency.
- [ ] Run targeted tests and verify any new failures are real defects.
- [ ] Apply minimal production fixes only where tests expose defects.
- [ ] Run full suite.
- [ ] Commit `test: harden benchmark invariants and failure handling`.

### Task 5: GitHub cloud validation and evidence upload

**Files:**
- Modify: `.github/workflows/test.yml`
- Create: `.github/workflows/validation.yml`

**Interfaces:**
- Core CI matrix: Ubuntu + Windows; Python 3.11/3.12 and 3.14 where setup-python supports it.
- Validation workflow uploads `inverted-validation-evidence` artifact.

- [ ] Extend core CI matrix and keep smoke verdict enforcement.
- [ ] Add validation workflow that installs package, runs full pytest, runs known-answer/stress validation, captures logs, and uploads evidence regardless of later inspection needs.
- [ ] Ensure validation workflow fails when expected and observed verdicts differ.
- [ ] Push branch and inspect every GitHub job/step result.
- [ ] Fetch uploaded artifact metadata and verify expected evidence files exist.
- [ ] Commit `ci: add exhaustive benchmark validation evidence`.

### Task 6: Final verification and integration

**Files:**
- No new production files unless verification exposes defects.

**Interfaces:**
- Release candidate is the head of `build/hybrid-validation`.

- [ ] Run full pytest on GitHub-supported Python matrix.
- [ ] Run deterministic smoke, checkpoint/resume smoke, known-answer campaigns, and validation stress campaign.
- [ ] Verify exact trial-plan counts and calculate real-model inference reduction versus the old 16,200-row rectangular schedule.
- [ ] Verify the ten final artifacts and validation evidence bundle.
- [ ] Inspect GitHub Actions status/logs for the branch.
- [ ] Compare branch to `main`, summarize changes, then fast-forward/merge only after green verification.
