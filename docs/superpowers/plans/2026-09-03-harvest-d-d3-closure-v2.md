# Harvest D D3-Closure v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the D3 measurement architecture without altering D3-v1 historical evidence, add a D4 Qwen call-policy gate, and build a model-free-green D3-Closure v2 harness ready for fresh local inference.

**Architecture:** Preserve D3-v1 modules and outputs as historical behavior. Add versioned closure-specific scoring, information delivery, assistance, recovery, scheduling, analysis, cases, campaign, CLI, config, and launcher code; make only narrowly compatible shared-adapter changes where necessary. The closure controller consumes observed outcomes, separates model-visible assistance from deterministic system control, and emits a fresh evidence lineage.

**Tech Stack:** Python 3.11+, pytest, stdlib dataclasses/json/pathlib/urllib, Ollama local chat API, PowerShell launcher, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-03-harvest-d-d3-closure-v2-design.md`

## Global Constraints

- D3-v1 evidence and protocol remain immutable historical evidence.
- No new physical model calls are required to prove the build green.
- New protocol identity is `D3-CLOSURE-v2`.
- Maximum D4 physical calls: 48.
- Maximum D3-Closure physical calls: 200; 48 confirmation calls protected.
- Model failure, context exhaustion, specification failure, oracle failure, instrumentation failure, and architecture failure remain separate classes.
- Semantic correctness must not depend on strict formatting success.
- Model-visible assistance must occur before inference.
- System-owned assistance must be evaluated by decision/outcome semantics.
- Adaptive scheduling must consume observed results.
- Same-terminal progress remains mandatory.
- Call budgets are ceilings, not quotas.

---

### Task 1: Post-D3 zero-call salvage outputs

**Files:**
- Create: `src/inverted/harvest_d/post_d3_analysis.py`
- Create: `tests/test_harvest_d_post_d3_analysis.py`

**Interfaces:**
- Produces: `analyze_d3_v1(root: Path, output: Path) -> dict[str, object]`
- Produces the seven required `post_d3_*` artifacts without mutating `root`.

- [ ] **Step 1: Write failing tests** proving the analyzer refuses identical input/output roots, reads normalized/runtime evidence, identifies zero disposition success/context exhaustion/empty required artifacts where present, and writes all seven required artifacts to a separate output path.
- [ ] **Step 2: Run the focused test and verify RED.**
- [ ] **Step 3: Implement the minimal read-only analyzer and deterministic artifact writers.**
- [ ] **Step 4: Run focused tests and verify GREEN.**
- [ ] **Step 5: Commit.**

### Task 2: Corrected closure scoring and deterministic disposition

**Files:**
- Create: `src/inverted/harvest_d/d3_closure_scoring.py`
- Create: `tests/test_harvest_d_d3_closure_scoring.py`

**Interfaces:**
- Produces: `ClosureScore`
- Produces: `score_semantic_action(...)`
- Produces: `compile_system_disposition(...)`

- [ ] **Step 1: Write failing tests** showing semantic action correctness survives fenced/format-invalid JSON, hidden disposition guessing is absent, deterministic disposition maps missing evidence/unknown effect/invariant failure/normal execution correctly, and context exhaustion is independently classified.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement minimal scoring/compiler code.**
- [ ] **Step 4: Verify GREEN and run legacy D3 scoring tests.**
- [ ] **Step 5: Commit.**

### Task 3: Real amount and ordering controls

**Files:**
- Create: `src/inverted/harvest_d/d3_closure_information.py`
- Create: `tests/test_harvest_d_d3_closure_information.py`

**Interfaces:**
- Produces: `ClosureInformationPlan`
- Produces: `render_closure_packet(case, plan)`

- [ ] **Step 1: Write failing tests** for distinct amount hashes/burdens, semantic-preserving order controls, deterministic seeded shuffle, and no-op detection.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement amount semantics: minimum subset, compressed all-essential summary, moderate essential+context, full all fields, overloaded full+non-authoritative burden.**
- [ ] **Step 4: Implement objective/state/evidence/safety-first and seeded shuffle orderings.**
- [ ] **Step 5: Verify GREEN.**
- [ ] **Step 6: Commit.**

### Task 4: Assistance split and causal application

**Files:**
- Create: `src/inverted/harvest_d/d3_closure_assistance.py`
- Create: `tests/test_harvest_d_d3_closure_assistance.py`

**Interfaces:**
- Produces: `apply_predecision_assistance(mechanism_id, context)` for A1-A4.
- Produces: `evaluate_system_assistance(mechanism_id, proposal, context)` for A5-A11.

- [ ] **Step 1: Write failing tests** proving A1-A4 change model-visible context before call construction, OFF/SHAM do not inject target semantics, and A5-A11 are scored by system decision/outcome fields rather than structural dictionary difference.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement minimal pre-decision and deterministic assistance paths.**
- [ ] **Step 4: Verify GREEN.**
- [ ] **Step 5: Commit.**

### Task 5: Recovery trajectory model

**Files:**
- Create: `src/inverted/harvest_d/d3_closure_recovery.py`
- Create: `tests/test_harvest_d_d3_closure_recovery.py`

**Interfaces:**
- Produces: `RecoveryTrajectory`
- Produces: `classify_recovery_outcome(...)`
- Produces: `validate_recovery_trajectory(...)`

- [ ] **Step 1: Write failing tests** requiring every mandated trajectory stage, rejecting blind retry under unknown external effect, and distinguishing recovered/migrated/worsened/escalated/safe-stopped.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement minimal trajectory and validation logic.**
- [ ] **Step 4: Verify GREEN.**
- [ ] **Step 5: Commit.**

### Task 6: Outcome-fed adaptive scheduler and protected budget

**Files:**
- Create: `src/inverted/harvest_d/d3_closure_scheduler.py`
- Create: `tests/test_harvest_d_d3_closure_scheduler.py`

**Interfaces:**
- Produces: `ClosureScheduler.observe(block_result)`
- Produces: `ClosureBudget.reallocate(...)`
- Produces: `next_action(...)`

- [ ] **Step 1: Write failing tests** proving SUPERIOR deepens/ablates rather than repeats, HARMFUL permits only contradiction check, FUTILE stops, UNRESOLVED chooses discrimination, resolved unsealed budget reallocates, and 48 sealed calls cannot be borrowed.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement minimal stateful scheduler/budget.**
- [ ] **Step 4: Verify GREEN.**
- [ ] **Step 5: Commit.**

### Task 7: D4 Qwen policy support

**Files:**
- Modify: `src/inverted/harvest_d/models.py`
- Create: `src/inverted/harvest_d/d4_qwen_policy.py`
- Create: `tests/test_harvest_d_d4_qwen_policy.py`

**Interfaces:**
- Extend `OllamaChatAdapter` with an optional top-level chat request field for supported thinking control without changing default behavior.
- Produces: `QwenPolicy`, `classify_qwen_completion(...)`, and a 48-call max policy budget.

- [ ] **Step 1: Write failing tests** against captured request bodies proving default adapter behavior is unchanged, explicit thinking control is top-level rather than an Ollama generation option, and completion classification distinguishes STOP/CONTEXT_EXHAUSTED/EMPTY_FINAL/SEMANTIC_RESULT.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement minimal backward-compatible adapter extension and policy types.**
- [ ] **Step 4: Verify GREEN plus existing model adapter tests.**
- [ ] **Step 5: Commit.**

### Task 8: Closure cases, campaign, analysis, CLI, launcher and config

**Files:**
- Create: `src/inverted/harvest_d/d3_closure_cases.py`
- Create: `src/inverted/harvest_d/d3_closure_campaign.py`
- Create: `src/inverted/harvest_d/d3_closure_analysis.py`
- Create: `src/inverted/harvest_d/d3_closure_cli.py`
- Create: `configs/harvest-d-d3-closure-v2.json`
- Create: `scripts/run-harvest-d-d3-closure-v2.ps1`
- Create: `tests/test_harvest_d_d3_closure_campaign.py`
- Create: `tests/test_harvest_d_d3_closure_cli.py`
- Create: `tests/test_harvest_d_d3_closure_launcher_windows.py`

**Interfaces:**
- Model-free preflight generates fresh development/fresh/sealed hashes and a committed-work schedule without calling Ollama.
- Physical mode uses only preregistered candidates, 200-call ceiling, 48-call protected confirmation reserve, append-only evidence, no retries, crash/resume protection, and same-terminal progress.

- [ ] **Step 1: Write failing model-free tests** for fresh partition identity, protected sealed bank, 200-call ceiling, no retry, scheduler observation, required output skeleton, and progress contract.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement the minimal model-free-green campaign/CLI/launcher.**
- [ ] **Step 4: Verify GREEN.**
- [ ] **Step 5: Commit.**

### Task 9: CI integration and complete regression

**Files:**
- Modify: `.github/workflows/harvest-d-validation.yml`

**Interfaces:**
- CI validates legacy D3 unchanged plus all new post-D3/D4/closure model-free tests and a zero-call closure package.

- [ ] **Step 1: Add a failing CI expectation through tests/workflow path coverage for the new launcher/config/modules.**
- [ ] **Step 2: Update workflow paths and add focused closure model-free commands.**
- [ ] **Step 3: Run/check focused closure suite.**
- [ ] **Step 4: Run/check all Harvest D regressions.**
- [ ] **Step 5: Run/check full repository regression.**
- [ ] **Step 6: Verify zero physical inference/API/model actions were used by CI.**
- [ ] **Step 7: Commit.**

## Verification Gate

Before declaring implementation complete:

1. All new focused tests pass.
2. Legacy D3 focused tests pass unchanged.
3. All Harvest D tests pass.
4. Full repository tests pass.
5. Model-free D3-Closure end-to-end package succeeds.
6. CI shows green on the implementation branch/PR.
7. The diff contains no mutation of frozen D3-v1 evidence artifacts.
8. The branch contains the design/spec and implementation plan that explain every architecture-changing change.
