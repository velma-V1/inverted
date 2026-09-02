# TEST 3 S2 Complete Forensics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make S2 retain every scientifically valuable observation durably, including raw provider payloads and the largest recoverable prefix after abnormal failure, while keeping the frozen 720-call experiment unchanged.

**Architecture:** Add an append-only hash-chained S2 forensic journal as the durable source of truth, extend model-call plumbing to retain raw provider transactions, preserve exact transformation failures, make CLI provenance/runtime/finalization failure-safe, and derive router-observability collision evidence post hoc. Existing in-memory structures remain the normal analysis surface but are no longer the sole copy of evidence.

**Tech Stack:** Python 3, pytest, JSONL/CSV/JSON artifacts, httpx/Ollama, existing S2 runtime and GitHub Actions validation.

**Spec:** `docs/superpowers/specs/2026-09-01-test3-s2-complete-forensics-design.md`

## Global Constraints

- Keep 72 Holdout-B cases, 5 arms, 2 calls per arm/task, 360 trials, and exactly 720 scheduled inference actions for a valid full run.
- Keep at most 12 provenance API actions and the 732 combined S2 external-action budget.
- Add zero inference calls and zero new external API endpoints.
- Keep zero transport retries and no outcome-dependent early stopping.
- Never expose hidden/private fixture truth to model prompts, `public_router_state`, or `select_action`.
- Any instrumentation/journal integrity failure blocks primary/architecture claims.

---

### Task 1: Forensic journal and integrity contract

**Files:**
- Create: `src/inverted/test3_s2_forensics.py`
- Create: `tests/test_test3_s2_forensics.py`

**Interfaces:**
- Produces: `S2ForensicJournal(run_dir, run_id)`, `append(event_type, payload, **identity)`, `snapshot_integrity()`, `read_records()`.

- [ ] Write failing tests proving each append is immediately visible on disk, sequence numbers are monotonic, and hash-chain verification detects tampering.
- [ ] Run the focused tests and verify RED because the journal does not exist.
- [ ] Implement canonical JSON serialization, SHA-256 chain, append+flush+fsync, read/verify helpers, and non-destructive close semantics.
- [ ] Run focused tests and verify GREEN.

### Task 2: Preserve complete raw model transactions and exact transformation failures

**Files:**
- Modify: `src/inverted/test2_local_hardened.py`
- Modify: `src/inverted/test2_local_impl.py`
- Modify: `src/inverted/test3_s2_runtime.py`
- Test: `tests/test_test3_s2_runtime.py`
- Test: `tests/test_test3_s2_forensics.py`

**Interfaces:**
- `BoundedCompletion.raw: dict[str, Any] | None`
- S2 call rows add `raw_provider_response`, `failure_stage`, `failure_detail` without changing prompts/router evidence.

- [ ] Write failing tests proving successful calls retain the complete `CompletionResult.raw` object.
- [ ] Write failing tests that independently distinguish JSON parse, action decode/application, repair-patch parse, and repair-composition failures while preserving response/raw provider evidence.
- [ ] Run focused tests and verify RED for missing raw/failure-stage fields.
- [ ] Extend `BoundedCompletion` and both normal/failed caller paths to retain raw provider payloads when available.
- [ ] Refactor S2 candidate/repair decoding into diagnostic helpers returning candidate plus explicit stage/error metadata; keep scoring semantics unchanged.
- [ ] Run focused tests and verify GREEN.

### Task 3: Journal every S2 runtime boundary and survive mid-run aborts

**Files:**
- Modify: `src/inverted/test3_s2_runtime.py`
- Modify: `src/inverted/test3_s2_forensics.py`
- Test: `tests/test_test3_s2_forensics.py`
- Test: `tests/test_test3_s2_runtime.py`

**Interfaces:**
- `run_s2_screen(..., journal: S2ForensicJournal | None = None, failure_injector: Callable[[str, dict], None] | None = None)`.

- [ ] Write failing tests injecting exceptions after a completed model call and between router decision/model completion; assert the durable journal contains the exact completed prefix and current identity.
- [ ] Run focused tests and verify RED.
- [ ] Instrument run initialization, budget reservations, trial starts, states, router views/decisions, model request/start/result, parse/composition, validators, transitions, trial completion, and runtime abort.
- [ ] Journal before subsequent mutations wherever losing the event would make reconstruction ambiguous.
- [ ] Run focused tests and verify GREEN.

### Task 4: Complete provenance/action ledger and failure-safe CLI finalization

**Files:**
- Modify: `src/inverted/test2_provenance.py`
- Modify: `src/inverted/test3_s2_cli.py`
- Modify: `src/inverted/test3_s2_artifacts.py`
- Test: `tests/test_test3_s2_cli.py`
- Test: `tests/test_test3_s2_artifacts.py`
- Test: `tests/test_test3_s2_forensics.py`

**Interfaces:**
- S2 provenance retains normalized fields plus raw `/api/version`, `/api/tags`, `/api/ps`, and per-model `/api/show` JSON.
- CLI always creates an output directory/journal before the first provenance request and writes partial/aborted evidence whenever cleanup is possible.

- [ ] Write failing tests for pre-run provenance failure, post-run provenance failure, and partial-packet claim suppression.
- [ ] Run focused tests and verify RED.
- [ ] Preserve full provenance payloads without changing endpoint count.
- [ ] Initialize journal/action ledger before preflight; wrap the entire real execution in one failure-safe evidence-finalization boundary.
- [ ] On abnormal failure, write `abort_state.json`, partial normalized evidence reconstructed from durable records where available, action-budget snapshot, and `PARTIAL/ABORTED EVIDENCE` completion marker; never authorize primary/architecture claims.
- [ ] Make artifact finalization errors journaled without deleting/truncating prior journal data.
- [ ] Run focused tests and verify GREEN.

### Task 5: Router-observability collision analysis

**Files:**
- Modify: `src/inverted/test3_s2_analysis.py`
- Modify: `src/inverted/test3_s2_artifacts.py`
- Test: `tests/test_test3_s2_analysis.py`
- Test: `tests/test_test3_s2_artifacts.py`

**Interfaces:**
- Produces `router_observability_collisions` rows and `router_observability_summary` with collision count/rate, ambiguous-case count/rate, largest group, B2-to-B3 resolved collisions, and B3 remaining collisions.

- [ ] Write failing analysis tests with intentionally aliased hidden fault labels that share the same B2 public observation and a case where B3 separates them.
- [ ] Assert runtime routing decisions/model prompts are byte-for-byte unchanged by adding the post-hoc analysis.
- [ ] Run focused tests and verify RED.
- [ ] Implement canonical observation fingerprints from stored router views and private post-hoc joins to holdout-manifest truth only after execution.
- [ ] Add collision CSV/JSON artifacts and master-index counts.
- [ ] Run focused tests and verify GREEN.

### Task 6: Complete evidence artifact contract and full regression gate

**Files:**
- Modify: `src/inverted/test3_s2_artifacts.py`
- Modify: `.github/workflows/test3-s2-validation.yml` if needed only to include new focused tests/artifact assertions.
- Test: all S2 tests plus repository suite.

**Interfaces:**
- Required artifacts include `forensic_journal.jsonl`, `raw_model_transactions.jsonl`, `parse_and_composition_failures.jsonl`, `external_action_ledger.jsonl`, `environment_provenance.json`, `abort_state.json`, `router_observability_collisions.csv`, `router_observability_summary.json`, and `journal_integrity.json`.

- [ ] Write/update failing artifact-contract tests asserting all new files exist, are included in `COMPLETE-EVIDENCE.txt`, and are hashed in `SHA256SUMS.csv`.
- [ ] Verify RED for missing files.
- [ ] Implement artifact emission for complete and partial modes; keep complete-mode legacy artifact names intact.
- [ ] Run all dedicated S2 tests.
- [ ] Run the full repository test suite/workflows and confirm zero regressions.
- [ ] Verify exact mock accounting remains 720 model-call slots, 360 trials, 144 calls/arm, zero cache hits, and no added external actions.
- [ ] Perform final spec-to-implementation audit and withhold Tier-A authorization if any acceptance criterion lacks direct test evidence.
