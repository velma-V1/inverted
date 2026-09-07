# Universal Capability Ratchet V3 Replay Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Track every checkbox and do not skip red/green verification.

**Goal:** Build the zero-inference V3 replay foundation that converts every material model failure into an immutable, queryable `TEST_REPLAY.jsonl` fixture that can later be reconstructed, replayed on the source model, forked under controlled interventions, or replayed on another compatible model.

**Architecture:** Keep `src/inverted/universal_tuning/` as the stable V2 experimental chassis. Add a focused `src/inverted/capability_ratchet/` layer that consumes V2 tasks, profiles, observations, scoring, statistics, and Qwen/Ollama provenance while owning V3 failure snapshots, replay assets, replay lineage, compatibility adapters, historical seeding, and replay selection. `TEST_REPLAY.jsonl` is the single canonical replay source; large payloads are content-addressed assets and any secondary indexes are regenerable views.

**Tech Stack:** Python 3.14, stdlib dataclasses/enums/protocols/pathlib/hashlib/json, pytest, existing `inverted.universal_tuning` modules, PowerShell launcher wrappers.

**Spec:** `docs/superpowers/specs/2026-09-07-universal-capability-ratchet-v3-design.md`

## Global Constraints

- No real model inference may run while implementing or validating this plan.
- `TEST_REPLAY.jsonl` is the single canonical replay registry; snapshot/branch indexes are derived only.
- Failure fixtures are immutable after append. Corrections append superseding records; they never rewrite old rows.
- Successful replay may never overwrite, hide, or relabel the original failure.
- `EXACT`, `COUNTERFACTUAL`, and `CROSS_MODEL` replay remain analytically distinct.
- Historical replay can never be relabeled as fresh or sealed evidence.
- Fresh/sealed partition labels are immutable and cannot leak into development or training eligibility.
- Model-visible material required for reconstruction must be embedded or referenced through a verified content-addressed asset.
- Credentials, secrets, unrelated private machine data, and inaccessible private chain-of-thought are never persisted.
- V2 raw evidence and existing V2 behavior remain unchanged.
- Same-model exact replay requires provenance compatibility; cross-model replay records every adapter change explicitly.
- Every replay definition states `decision_id`, `hypothesis_id`, replay mode, and registered changed dimensions.
- All tests in this plan use fake/mocked adapters. Network/Ollama calls are forbidden.

## File Structure

### New package

- `src/inverted/capability_ratchet/__init__.py` — stable replay-kernel exports.
- `src/inverted/capability_ratchet/core.py` — immutable enums/dataclasses and serialization contracts.
- `src/inverted/capability_ratchet/replay_store.py` — append-only `TEST_REPLAY.jsonl`, content-addressed assets, integrity, supersession.
- `src/inverted/capability_ratchet/snapshot.py` — convert scored V2 trials/observations into replayable failure fixtures.
- `src/inverted/capability_ratchet/replay.py` — replay request validation, exact/counterfactual/cross-model orchestration, child-result lineage.
- `src/inverted/capability_ratchet/qwen_replay.py` — replay frozen Qwen/Ollama request envelopes.
- `src/inverted/capability_ratchet/historical.py` — zero-call V2 historical importer/seeder.
- `src/inverted/capability_ratchet/query.py` — deterministic replay selection/filtering.
- `src/inverted/capability_ratchet/cli.py` — safe replay inspection/planning/execution gate.
- `scripts/run-test-replay.ps1` — thin PowerShell entry point.

### Existing file modified

- `src/inverted/universal_tuning/qwen_ollama.py` — expose only the smallest reusable request-posting seam; preserve V2 `complete()` behavior exactly.

### New tests

- `tests/test_capability_ratchet_core.py`
- `tests/test_capability_ratchet_replay_store.py`
- `tests/test_capability_ratchet_snapshot.py`
- `tests/test_capability_ratchet_replay.py`
- `tests/test_capability_ratchet_qwen_replay.py`
- `tests/test_capability_ratchet_historical.py`
- `tests/test_capability_ratchet_query_cli.py`
- `tests/test_capability_ratchet_preflight.py`

---

## Task 1 — Freeze the V3 replay schema

**Files**
- Create: `src/inverted/capability_ratchet/__init__.py`
- Create: `src/inverted/capability_ratchet/core.py`
- Test: `tests/test_capability_ratchet_core.py`

**Interfaces**
- `ReplayRecordType`
- `ReplayMode`
- `PromotionState`
- `Partition`
- `FailureFixture`
- `ReplayRequest`
- `ReplayResult`
- `ReplayRecord`
- `to_payload(value) -> dict[str, Any]`
- `from_payload(payload) -> ReplayRecord`

- [ ] **1.1 Write failing schema tests.** Cover round-trip serialization, immutable `record_type`, invalid mode/dimension combinations, partition parsing, and required IDs.

Example core assertions:

```python
fixture = FailureFixture(
    failure_snapshot_id="fail-001",
    source_campaign_id="v2-real",
    source_trial_id="ARITHMETIC:gate:000:candidate",
    focus_observation_id="obs-001",
    focus_task_id="arith-001",
    batch_task_ids=("arith-001", "arith-002", "arith-003", "arith-004", "arith-005"),
    family="ARITHMETIC",
    failure_classes=("SEMANTIC_FAIL",),
    source_model_id="qwen3.5:9b-q8_0",
    source_model_digest="digest-1",
    source_runtime={"provider": "ollama", "version": "0.32.15"},
    inference_profile={"thinking_budget": 1024, "temperature": 1.0},
    inference_seed=42,
    partition=Partition.DEVELOPMENT,
    model_visible_asset_sha256="a" * 64,
    oracle_ref="task-pool-v2:arith-001",
    expected_contract="answer_object",
    source_evidence_refs=("raw_calls.jsonl:12", "atomic_observations.jsonl:25"),
    metadata={"stage": "gate"},
)
assert from_payload(to_payload(fixture)) == fixture
assert fixture.record_type is ReplayRecordType.FAILURE_FIXTURE
```

- [ ] **1.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_core.py -v
```

Expected: import failure because `inverted.capability_ratchet` does not exist.

- [ ] **1.3 Implement frozen enums/dataclasses and explicit serialization.** `FailureFixture.record_type` must be `init=False`. `EXACT` forbids changed dimensions. `CROSS_MODEL` requires `target_model` in changed dimensions. Do not use an untyped dictionary as the canonical record schema.

- [ ] **1.4 Run green test.**

```bash
pytest tests/test_capability_ratchet_core.py -v
```

- [ ] **1.5 Commit.**

```bash
git add src/inverted/capability_ratchet tests/test_capability_ratchet_core.py
git commit -m "feat: define capability ratchet replay schema"
```

---

## Task 2 — Implement canonical append-only replay storage

**Files**
- Create: `src/inverted/capability_ratchet/replay_store.py`
- Test: `tests/test_capability_ratchet_replay_store.py`

**Interfaces**
- `ReplayStore(root: Path)`
- `put_asset(payload) -> str`
- `read_asset(sha256) -> Any`
- `append(record) -> str`
- `records() -> tuple[ReplayRecord, ...]`
- `get_failure(id) -> FailureFixture`
- `validate() -> ReplayValidation`
- `supersede(old_record_id, replacement_record_id, reason) -> str`

Canonical paths:

```text
<root>/TEST_REPLAY.jsonl
<root>/TEST_REPLAY.sha256
<root>/replay-assets/sha256/<digest>.json
```

- [ ] **2.1 Write failing append-only and integrity tests.** Prove one canonical JSONL row per record, content-addressed asset reuse, idempotent identical append, append-only correction/supersession, tamper detection, missing-asset detection, and broken-lineage detection.

- [ ] **2.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_replay_store.py -v
```

- [ ] **2.3 Implement the store.** Use canonical JSON (`sort_keys=True`, compact separators, UTF-8) and `os.fsync()` after every append, following the durability pattern in V2 `EvidenceStore`. Compute `record_id` as SHA-256 of the canonical payload before adding `record_id`. Duplicate identical appends are idempotent.

Implement:

```python
@dataclass(frozen=True)
class ReplayValidation:
    ok: bool
    row_count: int
    unique_record_count: int
    missing_assets: tuple[str, ...]
    hash_mismatches: tuple[str, ...]
    broken_lineage: tuple[str, ...]
    duplicate_record_ids: tuple[str, ...]
```

`validate()` must verify every replay asset, failure parent, replay request/result link, supersession link, and the registry SHA manifest.

- [ ] **2.4 Run green test.**

```bash
pytest tests/test_capability_ratchet_replay_store.py -v
```

- [ ] **2.5 Commit.**

```bash
git add src/inverted/capability_ratchet/replay_store.py tests/test_capability_ratchet_replay_store.py
git commit -m "feat: add canonical TEST_REPLAY store"
```

---

## Task 3 — Build exact-replay failure fixtures from V2 evidence

**Files**
- Create: `src/inverted/capability_ratchet/snapshot.py`
- Test: `tests/test_capability_ratchet_snapshot.py`

**Interfaces**
- Consume `inverted.universal_tuning.core.AtomicTask`, `Observation`, V2 raw-trial rows, task-pool records, and `ReplayStore`.
- Produce `build_failure_fixture(...) -> FailureFixture`.
- The fixture represents the **whole original physical batch/model-visible envelope**. `focus_task_id` identifies the atomic failure being investigated. Never isolate one atomic item from its original five-task batch and call that an exact replay.

- [ ] **3.1 Write failing reconstruction/privacy tests.** Prove full batch task IDs and original raw request envelopes are retained; oracle data is not injected into model-visible assets; non-failure observations are rejected; plaintext secrets are rejected; `<REDACTED>` placeholders are allowed.

Critical assertion:

```python
visible = store.read_asset(fixture.model_visible_asset_sha256)
assert tuple(fixture.batch_task_ids) == tuple(task.task_id for task in atomic_tasks)
assert fixture.focus_task_id == failed_observation.task_id
assert visible["request_envelopes"] == [call["request"] for call in raw_trial["raw_calls"]]
```

- [ ] **3.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_snapshot.py -v
```

- [ ] **3.3 Implement deterministic snapshot extraction.** It must resolve the exact V2 `trial_id`, retain every request envelope needed for reconstruction, preserve batch/focus IDs, preserve partition/contamination lineage, store expected/oracle references separately, run a bounded secret scanner, create one content-addressed model-visible asset, and return the fixture without auto-appending it.

Sensitive-key rejection includes case-insensitive `authorization`, `api_key`, `token`, `password`, `secret`, and PEM private-key markers.

- [ ] **3.4 Run focused green + exact V2 runner regression.**

```bash
pytest tests/test_capability_ratchet_snapshot.py tests/test_universal_tuning_runner.py -v
```

- [ ] **3.5 Commit.**

```bash
git add src/inverted/capability_ratchet/snapshot.py tests/test_capability_ratchet_snapshot.py
git commit -m "feat: snapshot V2 failures for exact replay"
```

---

## Task 4 — Implement replay planning, controlled diffs, and child lineage

**Files**
- Create: `src/inverted/capability_ratchet/replay.py`
- Test: `tests/test_capability_ratchet_replay.py`

**Interfaces**
- `ReplayAdapter.runtime_provenance()`
- `ReplayAdapter.execute_fixture(fixture, visible_payload, request) -> ReplayCompletion`
- `ReplayExecutor(store, adapters)`
- `ReplayExecutor.plan(request) -> ReplayPlan`
- `ReplayExecutor.execute(request) -> ReplayResult`

Tests use `FakeReplayAdapter`; no Ollama/network call.

- [ ] **4.1 Write failing tests.** Cover exact replay source-digest mismatch, counterfactual declared-dimension enforcement, cross-model adapter diff, partition immutability, parent fixture/request lineage, raw-call asset hashes, and infrastructure exceptions remaining infrastructure failures.

Example:

```python
executor = ReplayExecutor(
    replay_store,
    {failure_fixture.source_model_id: FakeReplayAdapter(digest="wrong")},
)
with pytest.raises(ValueError, match="exact replay provenance mismatch"):
    executor.plan(ReplayRequest.for_exact(
        failure_fixture,
        decision_id="D1",
        hypothesis_id="H-reproducibility",
    ))
```

- [ ] **4.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_replay.py -v
```

- [ ] **4.3 Implement validation before adapter execution.**

`EXACT`:
- target model ID/digest must match source;
- `changed_dimensions == ()`;
- partition unchanged.

`COUNTERFACTUAL`:
- source model remains the source model;
- every changed dimension is declared and registered.

`CROSS_MODEL`:
- source fixture remains immutable;
- target model/adapter/runtime differences are explicit;
- only compatibility-required fields change unless additional registered dimensions are declared.

All modes verify fixture and asset integrity before any adapter call.

- [ ] **4.4 Run green test.**

```bash
pytest tests/test_capability_ratchet_replay.py -v
```

- [ ] **4.5 Commit.**

```bash
git add src/inverted/capability_ratchet/replay.py tests/test_capability_ratchet_replay.py
git commit -m "feat: add controlled failure replay executor"
```

---

## Task 5 — Add a Qwen replay adapter without changing V2 behavior

**Files**
- Modify: `src/inverted/universal_tuning/qwen_ollama.py`
- Create: `src/inverted/capability_ratchet/qwen_replay.py`
- Test: `tests/test_capability_ratchet_qwen_replay.py`
- Regression: `tests/test_universal_tuning_qwen_cli.py`

**Interfaces**
- Add only a reusable request-posting seam to V2 adapter internals.
- Preserve `QwenOllamaAdapter.complete()` signature and semantics exactly.
- Produce `QwenReplayAdapter` implementing the Task 4 `ReplayAdapter` protocol.

- [ ] **5.1 Write mocked-network request-fidelity tests.** Exact replay must transmit frozen messages/options/think values rather than regenerate a prompt from task text. Add a regression assertion that an existing V2 mocked `complete()` request is structurally identical before/after the helper extraction.

- [ ] **5.2 Run red/new test plus existing Qwen CLI regression.**

```bash
pytest tests/test_capability_ratchet_qwen_replay.py tests/test_universal_tuning_qwen_cli.py -v
```

Expected before implementation: new replay test fails; existing V2 test remains green.

- [ ] **5.3 Extract the minimum reusable seam.** A helper such as:

```python
def post_chat_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
    return self._post(payload)
```

is acceptable. Do not alter `_direct_options`, `_thinking_options`, `_batch_messages`, or `complete()` behavior. Cross-model replay may replace only `model` and compatibility-required fields named by the replay request and must emit an explicit adapter diff.

- [ ] **5.4 Run new adapter test and the complete explicit V2 universal-tuning regression set.**

```bash
pytest \
  tests/test_capability_ratchet_qwen_replay.py \
  tests/test_universal_tuning_end_to_end.py \
  tests/test_universal_tuning_qwen_cli.py \
  tests/test_universal_tuning_runner.py \
  tests/test_universal_tuning_scheduler.py \
  tests/test_universal_tuning_scoring.py \
  tests/test_universal_tuning_statistics.py \
  tests/test_universal_tuning_tasks.py \
  tests/test_universal_tuning_v1_audit.py \
  tests/test_qwen_thinking_tuning.py -v
```

Expected: all pass with mocked/fake network only.

- [ ] **5.5 Commit.**

```bash
git add src/inverted/universal_tuning/qwen_ollama.py src/inverted/capability_ratchet/qwen_replay.py tests/test_capability_ratchet_qwen_replay.py
git commit -m "feat: adapt frozen failures for Qwen replay"
```

---

## Task 6 — Seed `TEST_REPLAY.jsonl` from the preserved V2 dump with zero inference

**Files**
- Create: `src/inverted/capability_ratchet/historical.py`
- Test: `tests/test_capability_ratchet_historical.py`

**Interfaces**
- `V2EvidenceSource(root: Path)`
- `seed_v2_failures(source, replay_store) -> HistoricalSeedResult`
- `HistoricalSeedResult(total_observations, material_failures, fixtures_added, duplicate_fixtures, skipped_nonfailures, invalid_rows)`

- [ ] **6.1 Write failing miniature-V2 seeding tests.** Prove one fixture per atomic failure, shared replay asset for multiple failures from the same physical batch, manifest/task-pool mismatch aborts before append, missing raw trial cannot partially append that trial, rerun is idempotent, and imported source partition is always `HISTORICAL`.

Example:

```python
result = seed_v2_failures(V2EvidenceSource(mini_v2_run), store)
failures = [r for r in store.records() if r.record_type is ReplayRecordType.FAILURE_FIXTURE]
assert result.material_failures == 2
assert len(failures) == 2
assert failures[0].model_visible_asset_sha256 == failures[1].model_visible_asset_sha256
assert failures[0].focus_task_id != failures[1].focus_task_id
```

- [ ] **6.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_historical.py -v
```

- [ ] **6.3 Implement source validation and deterministic seeding.** Required source files:

```text
protocol-v2-manifest.json
task-pool-v2.json
atomic_observations.jsonl
raw_calls.jsonl
```

Validate source hashes/relationships before append. Build indexes by `trial_id`, `task_id`, and batch. A material failure includes semantic failure, contract failure, completion failure, non-empty failure classes, and any recorded reasoning-cap/negative-transfer condition explicitly required by the V3 spec. Successful observations are not imported as failure fixtures.

- [ ] **6.4 Run test and zero-call dry seed against committed V2 evidence.**

```bash
pytest tests/test_capability_ratchet_historical.py -v
python -m inverted.capability_ratchet.cli seed-v2 \
  --source live-evidence/qwen-thinking-tuning-v2-real-20260907 \
  --replay-root runs/v3-preflight-replay \
  --dry-run
```

Expected: source counts + predicted fixture count + `MODEL_CALLS=0`.

- [ ] **6.5 Commit.**

```bash
git add src/inverted/capability_ratchet/historical.py tests/test_capability_ratchet_historical.py
git commit -m "feat: seed replay corpus from V2 evidence"
```

---

## Task 7 — Add fast replay querying and a safe CLI

**Files**
- Create: `src/inverted/capability_ratchet/query.py`
- Create: `src/inverted/capability_ratchet/cli.py`
- Create: `scripts/run-test-replay.ps1`
- Test: `tests/test_capability_ratchet_query_cli.py`

**Interfaces**
- `ReplaySelector(source_model, target_model, family, failure_class, campaign, partition, promotion_state, snapshot_ids)`
- `select_failures(store, selector) -> tuple[FailureFixture, ...]`
- CLI commands: `validate`, `list`, `show`, `seed-v2 --dry-run`, `plan-replay`, `execute-replay`.
- `execute-replay` requires explicit `--allow-model-calls` before importing/constructing any model adapter.

- [ ] **7.1 Write failing selector and CLI-gate tests.** Prove deterministic filter order, model/family/failure/campaign/partition selection, one-snapshot selection, and hard rejection of `execute-replay` without `--allow-model-calls`.

- [ ] **7.2 Run red test.**

```bash
pytest tests/test_capability_ratchet_query_cli.py -v
```

- [ ] **7.3 Implement query/CLI.** `list` shows snapshot ID, source model, family, failure class, campaign, partition, and replay count. `show` exposes verified fixture/asset metadata while honoring privacy rules. `plan-replay` validates fixture/provenance/compatibility and prints changed dimensions + projected physical calls without adapter execution.

PowerShell wrapper:

```powershell
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
$ErrorActionPreference = 'Stop'
python -m inverted.capability_ratchet.cli @Args
exit $LASTEXITCODE
```

- [ ] **7.4 Run green tests and inspection-only commands.**

```bash
pytest tests/test_capability_ratchet_query_cli.py -v
python -m inverted.capability_ratchet.cli --help
python -m inverted.capability_ratchet.cli validate --replay-root runs/v3-preflight-replay
```

Do **not** invoke `execute-replay --allow-model-calls` in this plan.

- [ ] **7.5 Commit.**

```bash
git add src/inverted/capability_ratchet/query.py src/inverted/capability_ratchet/cli.py scripts/run-test-replay.ps1 tests/test_capability_ratchet_query_cli.py
git commit -m "feat: add fast TEST_REPLAY query CLI"
```

---

## Task 8 — Prove replay-kernel invariants end to end with zero inference

**Files**
- Create: `tests/test_capability_ratchet_preflight.py`
- Modify: `src/inverted/capability_ratchet/__init__.py` only for final stable exports.

- [ ] **8.1 Write the end-to-end synthetic preflight.** Construct a miniature V2 run containing one success plus semantic, contract-only, and completion failures. Seed replay fixtures, query them, execute one exact replay through `FakeReplayAdapter`, and validate registry lineage/integrity.

Minimum assertions:

```python
store = ReplayStore(replay_root)
seeded = seed_v2_failures(V2EvidenceSource(mini_v2_run), store)
assert seeded.material_failures == 3
fixtures = select_failures(store, ReplaySelector(source_model="qwen3.5:9b-q8_0"))
assert len(fixtures) == 3
result = ReplayExecutor(store, {fake.model_id: fake}).execute(
    ReplayRequest.for_exact(fixtures[0], decision_id="D1", hypothesis_id="H-reproducibility")
)
assert result.parent_failure_snapshot_id == fixtures[0].failure_snapshot_id
assert store.validate().ok
```

Also prove:
1. successful replay leaves original failure row byte-identical;
2. replay failure can become a child fixture with parent lineage;
3. exact and cross-model records remain distinguishable;
4. asset tampering blocks execution before adapter call;
5. supersession preserves old rows;
6. fresh/sealed partition cannot change;
7. another model can target the same source fixture without source mutation;
8. registry can be reconstructed solely from `TEST_REPLAY.jsonl` + verified replay assets;
9. no real network/Ollama opener is invoked by the preflight suite.

- [ ] **8.2 Run the focused V3 foundation suite.**

```bash
pytest \
  tests/test_capability_ratchet_core.py \
  tests/test_capability_ratchet_replay_store.py \
  tests/test_capability_ratchet_snapshot.py \
  tests/test_capability_ratchet_replay.py \
  tests/test_capability_ratchet_qwen_replay.py \
  tests/test_capability_ratchet_historical.py \
  tests/test_capability_ratchet_query_cli.py \
  tests/test_capability_ratchet_preflight.py -v
```

Expected: all pass and telemetry confirms zero real model/network calls.

- [ ] **8.3 Run the explicit complete V2 universal-tuning regression suite.**

```bash
pytest \
  tests/test_universal_tuning_end_to_end.py \
  tests/test_universal_tuning_qwen_cli.py \
  tests/test_universal_tuning_runner.py \
  tests/test_universal_tuning_scheduler.py \
  tests/test_universal_tuning_scoring.py \
  tests/test_universal_tuning_statistics.py \
  tests/test_universal_tuning_tasks.py \
  tests/test_universal_tuning_v1_audit.py \
  tests/test_qwen_thinking_tuning.py -v
```

Expected: all previously passing V2 tests remain green.

- [ ] **8.4 Run repository regression and integrity gates.**

```bash
pytest -q
git diff --check
git status --short
```

Expected: repository baseline remains green except only pre-existing documented skips/warnings; no generated `runs/` evidence is staged.

- [ ] **8.5 Verify real preserved V2 evidence can be parsed and planned with zero model calls.**

```bash
python -m inverted.capability_ratchet.cli seed-v2 \
  --source live-evidence/qwen-thinking-tuning-v2-real-20260907 \
  --dry-run

python -m inverted.capability_ratchet.cli seed-v2 \
  --source live-evidence/qwen-thinking-tuning-v2-real-20260907 \
  --replay-root runs/v3-v2-seed-check

python -m inverted.capability_ratchet.cli plan-replay \
  --replay-root runs/v3-v2-seed-check \
  --source-model qwen3.5:9b-q8_0 \
  --family ARITHMETIC \
  --limit 5
```

Expected: preview, seed, and planning all report `MODEL_CALLS=0`. The seed writes replay fixtures/assets but performs zero inference; planning then identifies exact source fixtures/physical-call projections without executing them.

- [ ] **8.6 Commit completed replay foundation.**

```bash
git add src/inverted/capability_ratchet src/inverted/universal_tuning/qwen_ollama.py scripts/run-test-replay.ps1 tests/test_capability_ratchet_*.py
git commit -m "test: validate V3 replay kernel end to end"
```

---

## Plan 1 Completion Gate

Plan 1 is complete only when all are true:

1. `TEST_REPLAY.jsonl` is append-only and hash/lineage validated.
2. Every material V2 failure can be represented without isolating it from its original model-visible batch state.
3. Large model-visible payloads are content-addressed and hash-verified before replay.
4. Exact replay rejects model/digest mismatch before adapter execution.
5. Counterfactual replay records every changed dimension.
6. Cross-model replay preserves the source fixture and records adapter/model changes separately.
7. Successful replay cannot overwrite the original failure.
8. Failed replay can become a child fixture without blind-retry semantics.
9. Historical/fresh/sealed contamination labels are immutable.
10. V2 evidence seeding is deterministic and idempotent.
11. Querying can select one fixture or cohorts by model/family/failure/campaign/partition.
12. CLI model execution is impossible without explicit `--allow-model-calls`.
13. All Plan 1 tests and all explicit V2 universal-tuning regressions pass.
14. The preserved real V2 dump can be parsed into a replay plan with **zero model calls**.

## Deliberate Scope Boundary

This plan does **not** implement the V3 autopsy engine, tailored intervention generation, intervention tournament scheduler, ablation/sham search, failure mutation, skill extraction, capability compilation, conditional controller, or fine-tuning lane. Those layers depend on the replay kernel being trustworthy. Building them before exact failure reconstruction and lineage are proven would make later causal results scientifically unsafe.

The next implementation increment begins only after this completion gate passes and will consume these stable replay interfaces rather than replacing them.
