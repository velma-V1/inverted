# Inverted Brain Frontier Mechanism Harvest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained, forensic experiment on the `inverted-brain` branch that discovers Qwen3.5-9B + Brain frontier failures, harvests successful Claude/Codex trajectories, localizes and causally tests candidate mechanisms, and validates one-mechanism-at-a-time transfer on fresh sealed tasks.

**Architecture:** Add a separate `src/inverted_brain/` package and `tests/inverted_brain/` suite without modifying `src/inverted/`. The package owns task generation, adaptive frontier selection, normalized trajectories, critical-divergence localization, intervention/replay records, mechanism extraction, teacher/Qwen adapters, blind verification, forensic evidence, and the campaign CLI. Existing Inverted benchmark code remains an untouched sibling package.

**Tech Stack:** Python 3.11+, pytest, Docker Desktop, Ollama HTTP API, Claude Code CLI, Codex CLI, SHA-256 manifests, standard-library concurrency/subprocess/json/dataclasses.

**Spec:** `docs/inverted-brain/2026-09-06-frontier-mechanism-harvest-design.md`

## Global Constraints
- Existing `src/inverted/`, original benchmark configs, and historical evidence are immutable.
- Brain work exists only on branch `inverted-brain` and under `src/inverted_brain/`, `tests/inverted_brain/`, `configs/inverted_brain/`, `scripts/inverted_brain/`, and `docs/inverted-brain/`.
- Qwen model is fixed to `qwen3.5:9b-q8_0` for this test.
- Qwen non-thinking sampling defaults: temperature 0.7, top_p 0.8, top_k 20, min_p 0.0, presence_penalty 1.5, repeat_penalty 1.0; seed is recorded per trial.
- Claude/Codex RAW receive neutral task/tool plumbing only; no Inverted laws, Context7, hidden verifier information, or task-specific hints.
- Full teacher trajectories are never copied into the Brain. Candidate mechanisms are minimal contrastive records.
- Verifier files and gold state remain outside writable agent workspaces.
- No failed/interrupted evidence is deleted or silently retried.
- Campaign ceiling is ~200 agent runs and unused calls are not spent merely to hit budget.

---

### Task 1: Brain Package Contracts and Frozen Configuration

**Files:**
- Create: `src/inverted_brain/__init__.py`
- Create: `src/inverted_brain/contracts.py`
- Create: `src/inverted_brain/config.py`
- Create: `configs/inverted_brain/frontier_harvest.yaml`
- Test: `tests/inverted_brain/test_contracts.py`

**Interfaces:**
- Produces dataclasses `DifficultyVector`, `TaskSpec`, `AgentEvent`, `TrialResult`, `CriticalDivergence`, `InterventionSpec`, `MechanismCandidate`, `RetentionDecision`.
- Produces immutable Qwen runtime constants and campaign budget defaults.

- [ ] Write failing tests asserting exact Qwen model/sampling constants, status enums, serialization round-trips, and that no contract imports `inverted.*`.
- [ ] Run `pytest tests/inverted_brain/test_contracts.py -q` and require RED for missing package.
- [ ] Implement the minimal dataclasses/config loader and exact defaults from the spec.
- [ ] Re-run and require GREEN.
- [ ] Commit `feat(brain): add isolated experiment contracts`.

### Task 2: Sealed Multi-Grammar Task Generator

**Files:**
- Create: `src/inverted_brain/taskgen.py`
- Create: `src/inverted_brain/task_manifest.py`
- Create: `tests/inverted_brain/test_taskgen.py`

**Interfaces:**
- `generate_task(grammar: str, difficulty: DifficultyVector, seed: int, root: Path) -> TaskSpec`
- `freeze_task(task_dir: Path) -> dict[str, str]`
- `verify_task(task_dir: Path) -> list[str]`
- Grammars: `dependency_repair`, `stale_state`, `constraint_interaction`, `evidence_selection`, `reconciliation`, `interface_novelty`.

- [ ] Write failing tests for deterministic generation, independent difficulty dimensions, hidden verifier separation, exact manifests, six grammars, and no answer literals in visible prompt files.
- [ ] Require RED.
- [ ] Implement deterministic generators with small local repositories/files and programmatic hidden verifiers.
- [ ] Add a contamination scanner that rejects exact task/prompt overlap against supplied prior-task hashes/text fingerprints.
- [ ] Require GREEN and freeze generator version/hash.
- [ ] Commit `feat(brain): add sealed frontier task generator`.

### Task 3: Isolated Three-Agent Execution Layer

**Files:**
- Create: `src/inverted_brain/docker_workspace.py`
- Create: `src/inverted_brain/mcp_bridge.py`
- Create: `src/inverted_brain/adapters.py`
- Create: `tests/inverted_brain/test_execution.py`

**Interfaces:**
- `DockerWorkspace` mounts only one trial workspace and never Docker socket/home directories.
- `QwenBrainAdapter.run(...)`, `ClaudeRawAdapter.run(...)`, `CodexRawAdapter.run(...) -> TrialResult`.
- Claude/Codex use a single fixed MCP shell inside the arm container; Qwen uses the same container boundary through host Ollama.

- [ ] Write failing tests for sibling isolation, no Docker socket, prompt neutrality, Codex stdin delivery, no automatic retry, and Qwen exact options in raw call evidence.
- [ ] Require RED.
- [ ] Port the already-proven arena boundary into the branch without importing the standalone Desktop arena at runtime.
- [ ] Require GREEN using mock processes, then one non-scientific connectivity probe per adapter.
- [ ] Commit `feat(brain): add isolated qwen claude codex runners`.

### Task 4: Observable Trajectory Normalization

**Files:**
- Create: `src/inverted_brain/trajectory.py`
- Create: `tests/inverted_brain/test_trajectory.py`

**Interfaces:**
- `normalize_qwen(...)`, `normalize_claude(...)`, `normalize_codex(...) -> list[AgentEvent]`.
- Canonical event kinds: observation, tool_call, tool_result, assertion, mutation, state_reread, dependency_inspection, repair, rollback, verification, failure, final.

- [ ] Write failing fixtures representing equivalent Qwen/Claude/Codex actions and assert they normalize to the same semantic event types.
- [ ] Add tests that raw events remain linked by source IDs/timestamps and are never discarded.
- [ ] Implement normalization heuristics based only on observable tool/event data, never private chain-of-thought.
- [ ] Require GREEN.
- [ ] Commit `feat(brain): normalize cross-agent trajectories`.

### Task 5: Adaptive Frontier Sampler

**Files:**
- Create: `src/inverted_brain/frontier.py`
- Create: `tests/inverted_brain/test_frontier.py`

**Interfaces:**
- `FrontierSampler.observe(difficulty, passed) -> None`
- `FrontierSampler.next_batch(pool, n) -> list[TaskSpec]`
- Prioritizes strata with mixed Qwen outcomes and diversity across grammar/difficulty dimensions.

- [ ] Write failing tests proving all-pass and all-fail strata receive lower future allocation than mixed strata, while calibration samples are still retained.
- [ ] Add deterministic seed/replay tests.
- [ ] Implement an uncertainty/mixed-outcome score plus grammar-diversity constraint; no ML dependency required.
- [ ] Require GREEN.
- [ ] Commit `feat(brain): add adaptive frontier selection`.

### Task 6: Process/Outcome Verifier and Constraint Ledger

**Files:**
- Create: `src/inverted_brain/verifier.py`
- Create: `src/inverted_brain/constraint_ledger.py`
- Create: `tests/inverted_brain/test_verifier.py`

**Interfaces:**
- `verify_outcome(task, workspace) -> OutcomeScore`
- `evaluate_process(task, events) -> ProcessScore`
- `build_constraint_ledger(task, events) -> list[ConstraintEvaluation]`.

- [ ] Write failing tests separating terminal correctness from prohibited-process violations and controllable from infrastructure failures.
- [ ] Write a case where output passes but process violates a rule and assert it is not counted as clean success.
- [ ] Implement non-overlapping rubric criteria and guarded step-by-step constraint evaluation.
- [ ] Require GREEN.
- [ ] Commit `feat(brain): separate process and outcome verification`.

### Task 7: Critical Divergence Localization

**Files:**
- Create: `src/inverted_brain/divergence.py`
- Create: `tests/inverted_brain/test_divergence.py`

**Interfaces:**
- `localize_critical_divergence(qwen_events, teacher_events, ledger, task) -> CriticalDivergence`.
- Returns earliest evidence-supported divergence plus candidate failure class and confidence/evidence links.

- [ ] Write failing synthetic trajectories where the visible final error occurs after an earlier causal commitment and assert the earlier step is selected.
- [ ] Add interaction and recovery cases so a recoverable error is not mislabeled critical.
- [ ] Implement earliest-unrecoverable localization from event/state deltas plus constraint ledger; do not use terminal error position as a shortcut.
- [ ] Require GREEN.
- [ ] Commit `feat(brain): localize critical trajectory divergence`.

### Task 8: Counterfactual Intervention and Causal Replay

**Files:**
- Create: `src/inverted_brain/interventions.py`
- Create: `src/inverted_brain/replay.py`
- Create: `tests/inverted_brain/test_replay.py`

**Interfaces:**
- `plan_interventions(divergence, teacher_events) -> list[InterventionSpec]`
- `replay_from_snapshot(task, snapshot, intervention, adapter, repetitions) -> ReplayResult`.
- Supported interventions: remove, replace, delay, force, and paired interaction bundle.

- [ ] Write failing deterministic branchable-task tests where only one planted intervention changes outcome.
- [ ] Add leave-one-out and two-step interaction fixtures.
- [ ] Implement replay with identical task snapshot/seed controls and confidence interval/count reporting; preserve every replay as evidence.
- [ ] Require GREEN.
- [ ] Commit `feat(brain): add causal replay and ablation`.

### Task 9: Minimal Mechanism Extraction and Registry

**Files:**
- Create: `src/inverted_brain/mechanisms.py`
- Create: `src/inverted_brain/registry.py`
- Create: `tests/inverted_brain/test_mechanisms.py`

**Interfaces:**
- `extract_candidate(divergence, replay_results) -> MechanismCandidate`
- `validate_candidate(candidate) -> list[str]`
- Registry statuses: proposed, causally_supported, dev_passed, retained, rejected, bounded.

- [ ] Write failing tests that reject task IDs, exact hidden answers, unnecessary generator literals, and full teacher trajectory text.
- [ ] Test that a candidate stores trigger/guard, baseline behavior, minimal replacement, evidence, scope, cost, counterevidence.
- [ ] Implement deterministic validation plus concise mechanism serialization.
- [ ] Require GREEN.
- [ ] Commit `feat(brain): extract minimal causal mechanisms`.

### Task 10: Fresh Transfer and Retention Gates

**Files:**
- Create: `src/inverted_brain/retention.py`
- Create: `tests/inverted_brain/test_retention.py`

**Interfaces:**
- `decide_retention(candidate, baseline_trials, candidate_trials) -> RetentionDecision`.
- Enforces causal support, >=3/24 fresh lift by default, <=1 regression, no catastrophic new failure, cross-grammar or bounded-scope rule, mechanism-match evidence, complexity rent, and no benchmark encoding.

- [ ] Write failing edge-case tests for each retention gate independently and in combination.
- [ ] Implement exact preregistered gates with explicit failure reasons; never coerce borderline results into retained.
- [ ] Require GREEN.
- [ ] Commit `feat(brain): enforce fresh transfer retention gates`.

### Task 11: Campaign Orchestrator and Forensic Evidence

**Files:**
- Create: `src/inverted_brain/campaign.py`
- Create: `src/inverted_brain/evidence.py`
- Create: `src/inverted_brain/audit.py`
- Create: `tests/inverted_brain/test_campaign.py`

**Interfaces:**
- Phase-aware resumable state machine: preflight -> frontier -> harvest -> localize -> ablate -> candidate_dev -> holdout -> complete.
- `run_campaign(config, output_dir, resume=True)`.
- SHA-256 manifest plus independent audit of task hashes, model fingerprints, evidence identity, denominator exclusions, and call budget.

- [ ] Write failing tests for crash/resume, append-only failed evidence, 200-run ceiling, invalid-infrastructure exclusion, no silent retry, and fresh-holdout freeze ordering.
- [ ] Implement minimal deterministic phase controller and evidence manifest.
- [ ] Require GREEN.
- [ ] Commit `feat(brain): orchestrate forensic mechanism harvest campaign`.

### Task 12: CLI, Preflight, and Non-Scientific Instrument Validation

**Files:**
- Create: `src/inverted_brain/cli.py`
- Create: `scripts/inverted_brain/run-frontier-harvest.ps1`
- Create: `tests/inverted_brain/test_cli.py`
- Create: `docs/inverted-brain/README.md`

**Interfaces:**
- `python -m inverted_brain.cli --config configs/inverted_brain/frontier_harvest.yaml --output-dir <path> --preflight`
- `--instrument-smoke` runs only synthetic/mock adapters and must label output `INSTRUMENT VALIDATION — NOT BRAIN EVIDENCE`.
- Live campaign requires explicit `--live`.

- [ ] Write failing CLI tests for preflight model/tool checks, safe defaults, and refusal to run live campaign without `--live`.
- [ ] Implement PowerShell wrapper with exact progress, checkpoint/resume, AC-sleep handling only while running, and final audit.
- [ ] Run all `tests/inverted_brain/` plus existing repository tests; require zero regressions in `src/inverted/` tests.
- [ ] Run instrument validation only; do not spend the scientific campaign budget during build.
- [ ] Independently verify manifest and branch diff contains no modifications under `src/inverted/`.
- [ ] Commit `feat(brain): finish frontier mechanism harvest instrument`.

## Final Build Acceptance
- All existing Inverted tests remain green.
- All new Inverted-Brain tests are green.
- Git diff from `main` contains no modifications/deletions under `src/inverted/`, existing benchmark configs, or historical evidence.
- Dedicated `inverted-brain` branch contains frozen spec, plan, instrument, configs, tests, and operator docs.
- Instrument smoke passes with mock/synthetic adapters and produces a valid manifest.
- Live campaign has not been silently started during instrument construction.
- The next live run can produce a new Brain mechanism only after causal replay and fresh-transfer retention gates.
