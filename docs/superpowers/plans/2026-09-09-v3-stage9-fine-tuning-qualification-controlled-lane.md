# V3 Stage 9 Implementation Plan — Fine-Tuning Qualification and Optional Controlled Lane

> Execute without an approval pause. TDD is mandatory. Development/historical verification stays `MODEL_CALLS=0`.

**Goal:** implement a deterministic D11 qualification layer that can prove when fine-tuning has been earned, construct a leakage-safe referenced dataset package, and emit a bounded but unauthorized controlled-lane plan without constructing or invoking a trainer/model transport.

**Architecture:** dedicated Stage-9 scientific layer over Stage-7/8 evidence. Reuse the canonical replay, mutation, tomography, and compilation stores; do not add a second executor or transport. Stage-9 metadata is append-only and content-addressed.

## Task 1 — Freeze Stage-9 scientific contracts

**Tests first**
- Create `tests/test_capability_ratchet_fine_tuning_core.py`.
- Assert dispositions are disjoint from promotion vocabulary.
- Assert policy defaults: D11, minimum recurrence 2, zero development calls, no certification/deployment/training authorization.
- Assert content-addressed/immutable candidate/example/dataset/qualification/plan objects.
- Assert FRESH/SEALED, one-off, unresolved cheaper owner, missing generalization, hidden-oracle/raw-thinking metadata, non-finite values, and live authorization are rejected.
- Assert qualification cannot claim trained/certified/deployed.

**Implementation**
- Add `src/inverted/capability_ratchet/fine_tuning_core.py`.
- Use stable canonical SHA-256 identities and frozen nested values.

**Verification**
- `python -m pytest tests/test_capability_ratchet_fine_tuning_core.py -q`

## Task 2 — Append-only Stage-9 evidence store

**Tests first**
- Create `tests/test_capability_ratchet_fine_tuning_store.py`.
- Prove canonical JSONL, immutable logical IDs, manifest integrity, idempotent append, protected partition veto, source-link validation, and raw/oracle leakage rejection.

**Implementation**
- Add `src/inverted/capability_ratchet/fine_tuning_store.py` with:
  - `fine-tuning-candidates.jsonl`
  - `fine-tuning-datasets.jsonl`
  - `fine-tuning-qualifications.jsonl`
  - `controlled-tuning-plans.jsonl`
  - `SHA256SUMS.csv`
- Reuse Stage-8 append-only storage patterns.

**Verification**
- `python -m pytest tests/test_capability_ratchet_fine_tuning_store.py -q`

## Task 3 — Deterministic Stage-9 eligibility

**Tests first**
- Create `tests/test_capability_ratchet_fine_tuning_eligibility.py`.
- Prove only Stage-8 `FINE_TUNE_CANDIDATE` + model-internal residual can enter.
- Prove cheaper unresolved owners veto.
- Prove Stage-4→5→6 generalization is mandatory via Stage-8 admission.
- Prove recurrence across independent canonical failures is required.
- Prove FRESH/SEALED, instance-patch, insufficient ownership, leakage-risk, and unsupported-source states are explicit.
- Prove historical empty corpus returns `NO_ELIGIBLE_FINE_TUNING_CANDIDATES`, not fabricated work.
- Booby-trap HTTP/Ollama/socket/model-client constructors to prove scan is zero-call.

**Implementation**
- Add `src/inverted/capability_ratchet/fine_tuning_eligibility.py`.
- Consume `CompilationEligibilityScanner`; do not reimplement Stage-8 source qualification.
- Group only independently qualified model-owned candidates into D11 recurrence patterns.

**Verification**
- `python -m pytest tests/test_capability_ratchet_fine_tuning_eligibility.py -q`

## Task 4 — Leakage-safe dataset compiler

**Tests first**
- Create `tests/test_capability_ratchet_fine_tuning_dataset.py`.
- Prove train/eval sets are disjoint by example ID, failure lineage, and source content hash.
- Prove FRESH/SEALED rows rejected.
- Prove only canonical references/hashes enter metadata.
- Prove raw response, raw thinking/CoT, hidden oracle, prompt/message payload duplication is rejected.
- Prove dataset hash stable under equivalent ordering.
- Prove regression and negative-transfer refs mandatory.

**Implementation**
- Add `src/inverted/capability_ratchet/fine_tuning_dataset.py`.
- No synthetic examples and no model calls.

**Verification**
- `python -m pytest tests/test_capability_ratchet_fine_tuning_dataset.py -q`

## Task 5 — Qualification planner and analyzer

**Tests first**
- Create `tests/test_capability_ratchet_fine_tuning_planner.py` and `tests/test_capability_ratchet_fine_tuning_analysis.py`.
- Prove planner emits zero-call `NOT_AUTHORIZED` controlled-lane geometry only after every gate.
- Prove base model/profile frozen, physical training budget bounded, eval/regression preregistered, stop/abort and rollback required.
- Prove no trainer/provider/http/socket construction.
- Prove analyzer distinguishes `QUALIFY_CONTROLLED_LANE`, `NOT_JUSTIFIED`, `REQUIRES_MORE_EVIDENCE`, escalation, and safe stop.
- Prove qualification never changes trained/certified/deployment flags.

**Implementation**
- Add `fine_tuning_planner.py` and `fine_tuning_analysis.py`.

**Verification**
- `python -m pytest tests/test_capability_ratchet_fine_tuning_planner.py tests/test_capability_ratchet_fine_tuning_analysis.py -q`

## Task 6 — Thin lab orchestration

**Tests first**
- Create `tests/test_capability_ratchet_fine_tuning_lab.py`.
- Prove lab validates source stores, runs scan→dataset→qualification→plan without live clients, and writes only Stage-9 metadata.
- Prove no execution method silently invokes training.

**Implementation**
- Add `fine_tuning_lab.py` with injected stores/compiler/planner/analyzer only.

**Verification**
- `python -m pytest tests/test_capability_ratchet_fine_tuning_lab.py -q`

## Task 7 — Public API + CLI

**Tests first**
- Create `tests/test_capability_ratchet_fine_tuning_cli.py`.
- Assert public exports.
- Assert zero-call commands:
  - `scan-fine-tuning-eligibility`
  - `plan-fine-tuning --auto-eligible`
  - `show-fine-tuning-candidate --candidate-id`
  - `show-fine-tuning-qualification --qualification-id`
  - `export-fine-tuning-dataset --candidate-id --output`
- Assert there is no Stage-9 train/execute command.

**Implementation**
- Update `src/inverted/capability_ratchet/__init__.py`.
- Update `src/inverted/capability_ratchet/cli.py`.

**Verification**
- `python -m pytest tests/test_capability_ratchet_fine_tuning_cli.py -q`

## Task 8 — Permanent audit and planted preflight

**Tests first**
- Create `tests/test_capability_ratchet_fine_tuning_audit_closure.py`.
- Extend `scripts/audit-v3-replay-foundation.py`.
- Permanent audit must assert:
  - contracts/public API/CLI cannot disappear;
  - zero-call planning;
  - no independent executor/trainer transport;
  - model-internal-only ownership;
  - cheaper-owner veto;
  - recurrence gate;
  - Stage-8 generalization gate;
  - FRESH/SEALED veto;
  - train/eval disjointness;
  - hidden reasoning/oracle leakage veto;
  - observable-target requirement;
  - regression/negative-transfer requirement;
  - qualification != training/certification/deployment;
  - `NOT_AUTHORIZED` default;
  - Stage-11 confirmation requirement;
  - zero Stage-9 certification events.

**Verification**
- `python -m pytest tests/test_capability_ratchet_fine_tuning_*.py -q`
- `python scripts/audit-v3-replay-foundation.py ...`

## Task 9 — Dedicated Stage-9 completion workflow

**Implementation**
- Add `.github/workflows/v3-stage9-completion.yml`.
- Matrix: Ubuntu Python 3.11/3.12/3.14 + Windows 3.14.
- Matrix jobs run dedicated Stage-9 suite + full capability-ratchet.
- Zero-call completion job runs:
  1. privacy check;
  2. dedicated Stage-9 suite;
  3. full capability-ratchet;
  4. explicit V2 regression;
  5. full Linux repo regression;
  6. canonical historical replay seed;
  7. permanent Stage-5/6/7/8/9 audit;
  8. historical Stage-9 eligibility scan;
  9. historical Stage-9 auto-plan;
  10. deterministic empty/qualified dataset summary as applicable;
  11. completion invariants;
  12. clean tree;
  13. artifact upload.

Completion artifact must report at least:
- `STAGE9_COMPLETION`
- `MODEL_CALLS`
- historical Stage-9 status
- eligible candidate count
- qualified lane count
- dataset count/hash summary
- cheaper-owner veto contract
- recurrence contract
- leakage contract
- train/eval disjoint contract
- authorization veto
- Stage-11 handoff contract
- certification-event count
- forgotten count
- orphan assets
- privacy matches

## Task 10 — Exact-head closure

Run/inspect GitHub Actions on the exact Stage-9 head:
- dedicated Stage-9 completion workflow;
- repository general CI;
- any existing permanent V3 workflows triggered by the commit.

Before any completion claim:
1. reread `verification-before-completion` skill;
2. verify branch ref equals the tested SHA;
3. verify workflow conclusions are success;
4. inspect full zero-call completion log and counts;
5. verify artifact upload/digest;
6. verify clean-tree result;
7. report the historical scientific boundary without manufacturing fine-tuning candidates.

## Commit sequence

1. `docs: define V3 Stage-9 fine-tuning qualification`
2. `test: specify Stage-9 fine-tuning qualification contracts` — expected red CI before implementation.
3. `feat: implement Stage-9 fine-tuning qualification`
4. `test: close Stage-9 audit and completion workflow`
5. Any platform-only correction must preserve canonical scientific behavior and get its own exact-head rerun.
