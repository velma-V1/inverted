# V3 Stage-8 Capability Compilation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic Stage-8 compiler that admits only generalized canonical mechanisms, selects the cheapest evidence-supported durable owner, emits immutable versioned capability artifacts/catalogs, and closes historical compilation with zero model calls when no candidate exists.

**Architecture:** Add a compact Stage-8 layer beside the existing Stage-6/7 scientific stores. The layer has frozen contracts, an append-only metadata store, deterministic eligibility/planning/compilation, a zero-call CLI, and permanent audit/completion gates. It never creates an executor or transport and never changes canonical replay evidence.

**Tech Stack:** Python 3.11–3.14, dataclasses/enums, JSON/JSONL, SHA-256 manifests, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-09-v3-stage8-capability-compilation-design.md`

## Global Constraints

- `MODEL_CALLS=0` for all Stage-8 scan/plan/compile/export/development verification.
- No model, replay, tool, HTTP, socket, MCP, or provider executor in Stage 8.
- `INSTANCE_PATCH` cannot compile.
- Stage-7-only evidence cannot bypass Stage 4→5→6.
- FRESH/SEALED evidence is rejected from development compilation.
- Owner precedence is exactly: deterministic rule → state representation → formatter/parser/validator → tool → skill → reasoning → verifier/recovery → fine-tune → escalation → safe-stop.
- Trigger, tested region, negative-transfer boundary, evidence lineage, version, and rollback are mandatory for compiled artifacts.
- Stage 8 cannot certify or deploy; `deployment_allowed=False` always.
- Historical empty eligibility is a valid boundary; never manufacture a candidate.

---

### Task 1: Freeze Stage-8 contracts

**Files:**
- Create: `src/inverted/capability_ratchet/compilation_core.py`
- Create: `tests/test_capability_ratchet_compilation_core.py`

**Interfaces:**
- Produces: `CompilationKind`, `CompilationEligibilityStatus`, `CompilationDisposition`, `CompilationPolicy`, `CompilationCandidate`, `CompilationPlan`, `CompiledCapability`.

- [ ] **Step 1: Write failing contract tests** covering exact owner order, content-addressed IDs, unsupported/non-finite metadata rejection, hidden-oracle trigger rejection, mandatory trigger/tested-region/negative-transfer/rollback, `INSTANCE_PATCH` representation, immutable version linkage, and `deployment_allowed=False`.
- [ ] **Step 2: Run** `python -m pytest tests/test_capability_ratchet_compilation_core.py -q`; expect import failure.
- [ ] **Step 3: Implement minimal frozen contracts** with canonical JSON hashing and immutable mappings/tuples.
- [ ] **Step 4: Re-run focused test**; expect PASS.
- [ ] **Step 5: Commit** `feat: add Stage-8 compilation contracts`.

### Task 2: Add append-only compilation evidence store

**Files:**
- Create: `src/inverted/capability_ratchet/compilation_store.py`
- Create: `tests/test_capability_ratchet_compilation_store.py`

**Interfaces:**
- Consumes: Task-1 contracts; canonical `ReplayStore`; optional mutation/causal store interfaces through injected `validate()`/profile lookups.
- Produces: `CompilationEvidenceStore`, `CompilationStoreValidation`.

- [ ] **Step 1: Write failing tests** for candidate/decision/capability append, SHA-256 manifest validation, duplicate-identical idempotence, duplicate-changed rejection, source lineage checks, protected partition veto, version chain integrity, raw payload key rejection, and deterministic catalog export.
- [ ] **Step 2: Run focused store tests** and verify RED.
- [ ] **Step 3: Implement append-only files** `compilation-candidates.jsonl`, `compilation-decisions.jsonl`, `compiled-capabilities.jsonl`, `SHA256SUMS.csv` with cross-platform file locking and atomic append/manifests following mutation/tomography store patterns.
- [ ] **Step 4: Implement `export_catalog(path)`** producing deterministic `compiled-capabilities.json` with `MODEL_CALLS=0` and catalog hash.
- [ ] **Step 5: Run store tests**; expect PASS.
- [ ] **Step 6: Commit** `feat: add Stage-8 compilation evidence store`.

### Task 3: Implement deterministic eligibility scanner

**Files:**
- Create: `src/inverted/capability_ratchet/compilation_eligibility.py`
- Create: `tests/test_capability_ratchet_compilation_eligibility.py`

**Interfaces:**
- Consumes: `GeneralizationProfile`, replay mechanism labels, optional explicit prior-generalized evidence records.
- Produces: `CompilationEligibilityScanner`, `CompilationEligibilityResult`, `plan_eligible_compilation` bootstrap entrypoint.

- [ ] **Step 1: Write RED tests** proving `INSTANCE_PATCH` rejected; LOCAL/REGION/CROSS/PROMOTION accepted when contracts complete; missing profile rejected; Stage-7-only result returns `REQUIRES_STAGE456_FEEDBACK`; FRESH/SEALED rejected; missing trigger/boundary rejected; already-compiled recognized; empty historical stores yield zero candidates without model construction.
- [ ] **Step 2: Run focused test**; verify RED.
- [ ] **Step 3: Implement scanner** using only canonical stores and explicit evidence fields, never free-form model inference.
- [ ] **Step 4: Run focused test**; expect PASS.
- [ ] **Step 5: Commit** `feat: add Stage-8 compilation eligibility`.

### Task 4: Implement cheapest-owner planning

**Files:**
- Create: `src/inverted/capability_ratchet/compilation_planner.py`
- Create: `tests/test_capability_ratchet_compilation_planner.py`

**Interfaces:**
- Consumes: eligible `CompilationCandidate`.
- Produces: `CompilationPlanner.plan(candidate) -> CompilationPlan`.

- [ ] **Step 1: Write RED tests** for deterministic over tool, representation over skill, tool only when cheaper kinds unsupported/excluded, explicit cheaper exclusion reasons, reasoning-policy surface-ref requirement, fine-tune residual requirements, escalation/safe-stop handoff semantics, and `projected_model_calls=0`.
- [ ] **Step 2: Run focused planner tests**; verify RED.
- [ ] **Step 3: Implement exact precedence planner**; reject a selected expensive kind when an evidence-supported cheaper kind lacks an explicit exclusion reason.
- [ ] **Step 4: Run focused tests**; expect PASS.
- [ ] **Step 5: Commit** `feat: plan Stage-8 capability ownership`.

### Task 5: Compile immutable capability versions

**Files:**
- Create: `src/inverted/capability_ratchet/compilation_compiler.py`
- Create: `tests/test_capability_ratchet_compilation_compiler.py`

**Interfaces:**
- Consumes: `CompilationCandidate`, `CompilationPlan`, `CompilationEvidenceStore`.
- Produces: `CapabilityCompiler.compile(...) -> CompiledCapability`.

- [ ] **Step 1: Write RED tests** for version-1 compile, version-2 previous-ID linkage, stable capability key, immutable previous rows, owner-specific handoff disposition, source-evidence preservation, hidden-oracle/raw payload rejection, no deployment activation, and no executor/network import construction.
- [ ] **Step 2: Run focused compiler tests**; verify RED.
- [ ] **Step 3: Implement compiler** as pure data transformation + store append. No execution methods.
- [ ] **Step 4: Run focused tests**; expect PASS.
- [ ] **Step 5: Commit** `feat: compile durable Stage-8 capabilities`.

### Task 6: Public API and zero-call CLI

**Files:**
- Create: `src/inverted/capability_ratchet/compilation_cli.py`
- Modify: `src/inverted/capability_ratchet/cli.py`
- Modify: `src/inverted/capability_ratchet/__init__.py`
- Create: `tests/test_capability_ratchet_compilation_cli.py`

**Interfaces:**
- Produces commands: `scan-compilation-eligibility`, `plan-compilation`, `show-compiled-capability`, `export-compiled-capabilities`.

- [ ] **Step 1: Write RED CLI/API tests** for exact public exports, exact Stage-8 commands, `--candidate-id`/`--auto-eligible`, deterministic JSON output, empty historical boundary, catalog export, no execute flag, no allow-model-calls flag, and monkeypatched model/network constructor traps.
- [ ] **Step 2: Run focused tests**; verify RED.
- [ ] **Step 3: Implement isolated Stage-8 CLI adapter and route hooks** while preserving legacy/Stage-7 router semantics.
- [ ] **Step 4: Run Stage-8 CLI tests plus existing CLI suites**; expect PASS.
- [ ] **Step 5: Commit** `feat: expose Stage-8 zero-call compilation CLI`.

### Task 7: Permanent Stage-8 omission audit

**Files:**
- Modify: `scripts/audit-v3-replay-foundation.py`
- Create: `tests/test_capability_ratchet_compilation_audit_closure.py`

**Interfaces:**
- Extends current Stage-5/6/7 permanent audit without weakening inherited checks.

- [ ] **Step 1: Write RED audit tests** requiring Stage-8 files/exports, exact owner order, instance-patch veto, Stage456 feedback gate, partition protection, zero-call syntax-aware transport scan, cheapest-owner rule, trigger/boundary/rollback/version contracts, no CERTIFIED/deployment, and source/test/workflow omission detection.
- [ ] **Step 2: Run focused capability-ratchet suite**; confirm failures are audit omissions only.
- [ ] **Step 3: Extend the permanent audit** with runtime/source-derived Stage-8 checks; keep AST-based executable transport detection.
- [ ] **Step 4: Run focused suite**; expect PASS.
- [ ] **Step 5: Commit** `test: make Stage-8 compilation permanently auditable`.

### Task 8: Stage-8 completion workflow

**Files:**
- Create: `.github/workflows/v3-stage8-completion.yml`
- Extend: `tests/test_capability_ratchet_compilation_audit_closure.py`

**Interfaces:**
- Produces artifact `v3-stage8-completion-evidence` and `STAGE8-COMPLETION.json`.

- [ ] **Step 1: Add RED workflow-presence/completion-contract tests** requiring Linux 3.11/3.12/3.14 + Windows 3.14, dedicated/full/V2/full-repo regressions, privacy, zero-call historical seed, permanent audit, Stage-8 scan/auto-plan, catalog export validation, clean tree, and evidence upload.
- [ ] **Step 2: Implement workflow** with no real inference and no hardcoded historical candidate count.
- [ ] **Step 3: Run focused suite**; expect PASS locally/CI.
- [ ] **Step 4: Commit** `ci: add Stage-8 zero-call completion gate`.

### Task 9: Exact-head closure

**Files:** none unless a concrete gate defect is found.

- [ ] **Step 1: Run dedicated Stage-8 suite**.
- [ ] **Step 2: Run full capability-ratchet suite**.
- [ ] **Step 3: Run explicit V2 regression**.
- [ ] **Step 4: Run full Linux repository regression**.
- [ ] **Step 5: Confirm Linux 3.11/3.12/3.14 and Windows 3.14 matrix**.
- [ ] **Step 6: Confirm privacy 0, permanent audit forgotten/orphan 0, zero-call historical status, deterministic catalog, no CERTIFIED/deployment, clean tree, and `MODEL_CALLS=0`**.
- [ ] **Step 7: Fetch and inspect completion artifact and exact job logs**.
- [ ] **Step 8: Verify branch head equals tested head**.
- [ ] **Step 9: Lock Stage 8 and advance to Stage 9 only after fresh exact-head evidence is green**.
