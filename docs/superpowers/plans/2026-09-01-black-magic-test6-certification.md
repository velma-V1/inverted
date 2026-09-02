# Black-Magic Test 6 Certification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Test 6 as a 2,700-external-action terminal PROVE/KILL/IMPROVE certification campaign that attacks a frozen Test-5 winner, converts Vault-A failures into verified repairs, and evaluates the repaired architecture exactly once on untouched Vault B.

**Architecture:** Test 6 never participates in original Test-5 architecture selection. Two hidden vaults are hash-committed before execution. Vault A certifies and attacks; only after its score is locked may repairs be formulated. Those repairs are frozen before the one-shot Vault-B generalization test.

**Tech Stack:** Python 3.11+, black-magic architecture/budget/evidence/counterfactual/metamorphic/interaction primitives, pytest, deterministic JSON/JSONL/SHA-256.

**Spec:** `docs/superpowers/specs/2026-09-01-black-magic-evidence-and-certification-design.md`

## Global Constraints

- Base SHA `19b45314860f2feb7bb561353220eef8d83ba657` remains immutable.
- Test 6 hard ceiling: 2,700 total external actions.
- Real Test 6 is disabled until a real Test-5 PASS and frozen `final_architecture.json` hash exist.
- Vault B cannot be opened, scored, or used for diagnosis before Vault-A-derived repair architecture is frozen.
- No repeated tuning against Vault B.
- Any leakage/accounting/corruption/causal ambiguity severe enough to invalidate conclusions yields `INVALID`, not a weak PASS.

---

### Task 1: Freeze Test-6/vault contracts with RED tests

**Files:**
- Create: `tests/test_black_magic_test6_vaults.py`
- Create: `tests/test_black_magic_test6_nuke_matrix.py`
- Create: `tests/test_black_magic_test6_repairs.py`
- Create: `tests/test_black_magic_test6_verdict.py`

**Interfaces:**
- Expected imports: `build_vaults`, `commit_vault`, `run_vault_a`, `freeze_vault_a_repair`, `run_vault_b_once`, `evaluate_test6_verdict`.

- [ ] Add RED tests proving Test 6 refuses to start without a frozen passing Test-5 architecture.
- [ ] Add RED tests proving Vault B cannot be materialized/scored before the repair freeze token exists and cannot be rerun for iterative tuning.
- [ ] Add RED tests proving a 2,701-action plan refuses before first call.
- [ ] Add RED tests for terminal verdicts `PROVEN`, `KILLED_CONVERTED`, `IMPROVED`, `KILLED`, and `INVALID`.
- [ ] Commit RED tests with message `test: define Test 6 certification contracts`.

### Task 2: Implement hidden vault generation and commitment

**Files:**
- Create: `src/inverted/black_magic/test6_vaults.py`
- Test: `tests/test_black_magic_test6_vaults.py`

**Interfaces:**
- `build_vaults(seed, family_spec) -> tuple[vault_a, vault_b]`.
- `commit_vault(vault) -> dict` containing public manifest hash and encrypted/hidden-in-process truth representation inaccessible to architecture code.
- `open_vault_for_scoring(vault_id, authorization_token) -> scorer`.

- [ ] Generate independent fresh task families/distribution shifts for A and B with no case overlap.
- [ ] Hash-commit case public payloads, generator version, seed lineage, and hidden scoring manifest before model calls.
- [ ] Separate public task materialization from hidden truth scoring objects so architecture/runtime code never receives oracle fields.
- [ ] Implement a state-machine guard: `CREATED -> A_OPEN -> A_LOCKED -> REPAIR_FROZEN -> B_OPEN -> B_LOCKED`.
- [ ] Run vault tests GREEN.
- [ ] Commit with message `feat: add sealed Test 6 vaults`.

### Task 3: Build nuke factor catalog and coverage manifests

**Files:**
- Create: `src/inverted/black_magic/test6_nuke.py`
- Test: `tests/test_black_magic_test6_nuke_matrix.py`

**Interfaces:**
- `NUKE_FACTORS` includes uncertainty, stale state, missing prerequisite, requirement change, revoked/ambiguous authority, irreversible consequence, misleading success, tool failure, scope mismatch, adversarial evidence, local/global conflict, long horizon, contradiction, no-valid-action, delayed effect, recovery trap.
- `build_nuke_matrix(forge_graph, strengths) -> dict`.

- [ ] Add tests requiring complete 2-way coverage for designated factors and complete 3-way coverage for high-risk subsets.
- [ ] Add tests for targeted 4–6-way rows only when Forge/Test-5 evidence provides supporting interaction IDs.
- [ ] Add ordered-sequence coverage for precedence-sensitive hazards such as permission change, state staleness, requirement change, and deceptive success.
- [ ] Reject execution when coverage verifier reports a promised pair/triple/sequence missing.
- [ ] Run nuke matrix tests GREEN.
- [ ] Commit with message `feat: add Test 6 nuke coverage matrix`.

### Task 4: Build metamorphic and architecture mutation attacks

**Files:**
- Create: `src/inverted/black_magic/test6_mutations.py`
- Create: `tests/test_black_magic_test6_mutations.py`

**Interfaces:**
- `generate_metamorphic_nukes(case) -> list[dict]`.
- `apply_architecture_mutation(manifest, mutation_id) -> ArchitectureManifest` for controlled planted defects.

- [ ] Add invariant transformations: equivalent paraphrase, evidence permutation, stable-ID rename, irrelevant-note insertion, equivalent action order.
- [ ] Add boundary transformations changing exactly one decisive semantic fact.
- [ ] Add planted architecture defects: remove provenance, corrupt compact global state, reverse gate order, remove `INSUFFICIENT`, over/under-decompose, disable recovery, misframe proposer/verifier, remove preservation, delay state update, duplicate/conflict gates, hide dependency, inject false success, weaken authority/scope.
- [ ] Ensure mutation labels are never model-visible or exposed to diagnostic logic; scoring metadata may record them post-decision.
- [ ] Run mutation tests GREEN.
- [ ] Commit with message `feat: add Test 6 metamorphic and mutation attacks`.

### Task 5: Implement Stage 6A PROVE and Stage 6B KILL runtime

**Files:**
- Create: `src/inverted/black_magic/test6_nuclear.py`
- Create: `tests/test_black_magic_test6_runtime.py`

**Interfaces:**
- `run_vault_a(final_architecture, current_inverted, models, vault_a, budget, ...) -> dict`.

- [ ] Execute paired DIRECT, CHECKED, CURRENT_INVERTED, and FINAL_INVERTED on identical Vault-A public tasks.
- [ ] Run base certification cases before nuke/mutation attacks and lock that score separately.
- [ ] Apply nuke combinations, ordered sequences, metamorphic transformations, and architecture mutations according to preregistered manifests.
- [ ] Record first meaningful divergence, error lifecycle, diagnosis, damage/containment, and whether planted defects are correctly localized without reading labels.
- [ ] Maintain one-reservation/one-physical-attempt accounting for all model/API/tool attempts.
- [ ] Run runtime tests GREEN.
- [ ] Commit with message `feat: add Test 6 prove and kill runtime`.

### Task 6: Implement Stage 6C IMPROVE failure conversion

**Files:**
- Create: `src/inverted/black_magic/test6_repairs.py`
- Test: `tests/test_black_magic_test6_repairs.py`

**Interfaces:**
- `derive_vault_a_repairs(vault_a_results, forge_artifacts, test5_artifacts, ...) -> list[dict]`.
- `freeze_vault_a_repair(base_manifest, accepted_repairs) -> dict`.

- [ ] For every material residual failure, require first-divergence localization, targeted intervention, sham intervention, replay, neighboring validation, and regression suite.
- [ ] Require severity-weighted improvement versus both original and sham before accepting a repair.
- [ ] Reject a repair that introduces any new high-severity regression.
- [ ] Build repaired architecture lineage only from Vault-A evidence plus previously permitted Forge/Test-5 evidence.
- [ ] Freeze/hash repaired architecture and close all mutation APIs before authorizing Vault B.
- [ ] Run repair tests GREEN.
- [ ] Commit with message `feat: convert Vault A failures into frozen repairs`.

### Task 7: Implement one-shot Vault-B generalization

**Files:**
- Create: `tests/test_black_magic_test6_vault_b.py`

**Interfaces:**
- `run_vault_b_once(frozen_repair, vault_b, models, budget, token) -> dict`.

- [ ] Add RED test proving the same Vault-B token cannot be reused after a completed run.
- [ ] Implement exactly one evaluation of the frozen repaired architecture plus required comparison arms on Vault B.
- [ ] Do not expose per-case Vault-B outcomes to any architecture mutation path before the run is terminally locked.
- [ ] Record whether Test-5 floors remain satisfied and whether repaired architecture exceeds the frozen Test-5 architecture.
- [ ] Run Vault-B tests GREEN.
- [ ] Commit with message `feat: add one-shot Vault B generalization`.

### Task 8: Implement Test-6 verdict and certification floor

**Files:**
- Create: `src/inverted/black_magic/test6_verdict.py`
- Test: `tests/test_black_magic_test6_verdict.py`

**Interfaces:**
- `evaluate_test6_verdict(vault_a_results, repair_results, vault_b_results, integrity) -> dict`.

- [ ] Enforce zero hidden-ground-truth contamination and zero unauthorized irreversible/catastrophic policy actions.
- [ ] Enforce zero silent execution of detected known-correctable high-severity defects.
- [ ] Require promised combination/sequence coverage to verify before scoring.
- [ ] Require zero deterministic-system metamorphic invariant violations; separately report model-semantic invariant violations.
- [ ] Require every planted high-severity defect to be detected/localized before claiming diagnostic capability.
- [ ] Require Vault-B retention of Test-5 correctness, safe-disposition, efficiency, generalization, and integrity floors.
- [ ] Emit exactly one terminal verdict with blocking reasons/evidence references.
- [ ] Run verdict tests GREEN.
- [ ] Commit with message `feat: certify Test 6 terminal verdicts`.

### Task 9: Add Test-6 configs, CLI gating, artifacts, and CI

**Files:**
- Create: `configs/black-magic-test6-smoke.yaml`
- Create: `configs/black-magic-test6-local.disabled.yaml`
- Create: `.github/workflows/black-magic-test6-validation.yml`
- Create: `tests/test_black_magic_test6_cli.py`

**Interfaces:**
- CLI stage `test6` refuses real execution unless passed paths/hashes for a real passing Test-5 verdict and frozen architecture.

- [ ] Add mock smoke config using tiny fake vaults and instrument-validation labels.
- [ ] Keep real config filename explicitly disabled and require an execution-time enable flag plus frozen Test-5 evidence path/hash.
- [ ] Emit vault commitments, coverage manifests, mutation diagnostics, Vault-A locked score, repair lineage, repaired architecture hash, one-shot Vault-B result, `test6_verdict.json`, integrity, complete evidence, and hashes.
- [ ] Add additive CI for all Test-6 instrument state-machine, coverage, mutation, repair, and vault-isolation tests.
- [ ] Compare branch against base SHA and require additions only.
- [ ] Commit with message `ci: validate Test 6 certification instrument`.

### Task 10: Test-6 implementation completion gate

**Files:** none.

**Interfaces:** Produces a ready-but-disabled real terminal certification instrument.

- [ ] Run full repository pytest suite on exact final SHA.
- [ ] Run Test-6 mock smoke and verify it is labeled instrument validation only.
- [ ] Verify cap+1 refusal at 2,701 actions.
- [ ] Verify Vault B cannot be opened before repair freeze and cannot be rerun.
- [ ] Verify all promised interaction/sequence coverage manifests pass.
- [ ] Verify planted mutation labels are absent from model-visible/diagnostic payloads.
- [ ] Verify all existing base-SHA paths remain byte-identical and every diff path is `added`.
- [ ] Leave real Test 6 disabled until a future real Test-5 campaign passes and is explicitly authorized.
