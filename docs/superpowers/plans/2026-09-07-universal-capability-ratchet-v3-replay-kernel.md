# Universal Capability Ratchet V3 Replay Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the zero-inference V3 replay foundation that converts every material model failure into an immutable, queryable `TEST_REPLAY.jsonl` fixture that can later be reconstructed, replayed on the source model, forked under controlled interventions, or replayed on another compatible model.

**Architecture:** Keep `src/inverted/universal_tuning/` as the stable V2 experimental chassis. Add a new `src/inverted/capability_ratchet/` layer that consumes V2 tasks, profiles, observations, scoring, statistics, and Qwen/Ollama provenance but owns V3 failure snapshots, replay assets, replay lineage, compatibility adapters, historical seeding, and replay selection. The canonical replay source is one append-only `TEST_REPLAY.jsonl`; large payloads are content-addressed replay assets, while any secondary indexes are regenerable views.

**Tech Stack:** Python 3.14, stdlib dataclasses/enums/protocols/pathlib/hashlib/json, pytest, existing `inverted.universal_tuning` modules, PowerShell launcher wrappers.

**Spec:** `docs/superpowers/specs/2026-09-07-universal-capability-ratchet-v3-design.md`

## Global Constraints

- No real model inference may run while implementing or validating this plan.
- `TEST_REPLAY.jsonl` is the single canonical replay registry; snapshot/branch indexes are derived only.
- Failure fixtures are immutable after append. Corrections append superseding records; they never rewrite old rows.
- A successful replay may never overwrite or hide the original failure.
- Exact replay, counterfactual replay, and cross-model replay remain analytically distinct.
- Historical replay can never be relabeled as fresh or sealed evidence.
- Fresh/sealed partition labels are immutable and cannot leak into development/training eligibility.
- Model-visible material required for reconstruction must be embedded or referenced by verified content-addressed asset hash.
- Credentials, secrets, unrelated private machine data, and inaccessible private chain-of-thought are never persisted.
- V2 raw evidence and existing V2 behavior remain unchanged.
- Same-model exact replay requires provenance compatibility; cross-model replay records every adapter change explicitly.
- Every replay definition must state a `decision_id`, `hypothesis_id`, replay mode, and registered changed dimensions.
- Tests must use fake/mocked adapters only; network/Ollama calls are forbidden in this plan.

---

## File Structure

### New package

- `src/inverted/capability_ratchet/__init__.py` — public V3 replay-kernel exports only.
- `src/inverted/capability_ratchet/core.py` — immutable enums/dataclasses and serialization contracts.
- `src/inverted/capability_ratchet/replay_store.py` — append-only `TEST_REPLAY.jsonl`, content-addressed assets, integrity, query, supersession.
- `src/inverted/capability_ratchet/snapshot.py` — convert scored V2 trials/observations into replayable failure fixtures.
- `src/inverted/capability_ratchet/replay.py` — replay request validation, exact/counterfactual/cross-model execution orchestration, child-result recording.
- `src/inverted/capability_ratchet/qwen_replay.py` — Qwen/Ollama replay adapter that can reconstruct frozen model-visible messages without requiring a new `AtomicTask` batch.
- `src/inverted/capability_ratchet/historical.py` — zero-call V2 historical importer/seeder and evidence-atlas seed records.
- `src/inverted/capability_ratchet/query.py` — deterministic filtering/group selection for fast replay sets.
- `src/inverted/capability_ratchet/cli.py` — `validate`, `list`, `show`, `plan-replay`, and explicitly gated `execute-replay` command surface.
- `scripts/run-test-replay.ps1` — thin PowerShell entry point to the replay CLI.

### Existing files modified

- `src/inverted/universal_tuning/qwen_ollama.py` — extract one small reusable request-construction/provenance seam only; preserve existing V2 `complete()` behavior exactly.
- `src/inverted/universal_tuning/__init__.py` — no new behavior; export only if required by existing package convention.

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

### Task 1: Freeze the V3 replay schema

**Files:**
- Create: `src/inverted/capability_ratchet/__init__.py`
- Create: `src/inverted/capability_ratchet/core.py`
- Test: `tests/test_capability_ratchet_core.py`

**Interfaces:**
- Produces `ReplayRecordType`, `ReplayMode`, `PromotionState`, `Partition`, `FailureFixture`, `ReplayRequest`, `ReplayResult`, `ReplayRecord`.
- Produces `to_payload(value) -> dict[str, Any]` and `from_payload(payload) -> ReplayRecord`.
- Later tasks must use these exact types rather than independent dictionaries.

- [ ] **Step 1: Write the failing schema tests**

```python
from inverted.capability_ratchet.core import (
    FailureFixture, Partition, ReplayMode, ReplayRecordType,
    ReplayRequest, from_payload, to_payload,
)


def test_failure_fixture_round_trip_preserves_replay_identity():
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
    record = from_payload(to_payload(fixture))
    assert record == fixture
    assert record.record_type is ReplayRecordType.FAILURE_FIXTURE


def test_cross_model_request_cannot_claim_exact_replay():
    request = ReplayRequest(
        replay_request_id="req-1",
        failure_snapshot_id="fail-001",
        target_model_id="other-model",
        replay_mode=ReplayMode.CROSS_MODEL,
        decision_id="D2",
        hypothesis_id="H-model-boundary",
        changed_dimensions=("target_model",),
        compatibility_adapter="ollama-chat-v1",
    )
    assert request.replay_mode is ReplayMode.CROSS_MODEL
```

- [ ] **Step 2: Run the tests and verify they fail because the package/types do not exist**

Run:

```bash
pytest tests/test_capability_ratchet_core.py -v
```

Expected: import failure for `inverted.capability_ratchet`.

- [ ] **Step 3: Implement immutable enums/dataclasses and explicit serialization**

Use frozen dataclasses. `FailureFixture.record_type` must be a computed/default field fixed to `FAILURE_FIXTURE`; the constructor must not accept an arbitrary record type. `ReplayRequest` must validate that `EXACT` does not contain `target_model` in `changed_dimensions`, and `CROSS_MODEL` does.

```python
class ReplayRecordType(str, Enum):
    FAILURE_FIXTURE = "FAILURE_FIXTURE"
    REPLAY_REQUEST = "REPLAY_REQUEST"
    REPLAY_RESULT = "REPLAY_RESULT"
    MUTATION_FIXTURE = "MUTATION_FIXTURE"
    MECHANISM_LABEL = "MECHANISM_LABEL"
    PROMOTION_EVENT = "PROMOTION_EVENT"
    SUPERSESSION = "SUPERSESSION"


class ReplayMode(str, Enum):
    EXACT = "EXACT"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    CROSS_MODEL = "CROSS_MODEL"


class Partition(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    HISTORICAL = "HISTORICAL"
    FRESH = "FRESH"
    SEALED = "SEALED"


@dataclass(frozen=True)
class FailureFixture:
    failure_snapshot_id: str
    source_campaign_id: str
    source_trial_id: str
    focus_observation_id: str
    focus_task_id: str
    batch_task_ids: tuple[str, ...]
    family: str
    failure_classes: tuple[str, ...]
    source_model_id: str
    source_model_digest: str
    source_runtime: dict[str, Any]
    inference_profile: dict[str, Any]
    inference_seed: int
    partition: Partition
    model_visible_asset_sha256: str
    oracle_ref: str
    expected_contract: str
    source_evidence_refs: tuple[str, ...]
    metadata: dict[str, Any]
    record_type: ReplayRecordType = field(default=ReplayRecordType.FAILURE_FIXTURE, init=False)
```

Implement equivalent explicit fields for `ReplayRequest` and `ReplayResult`; do not use an untyped catch-all record as the canonical schema.

- [ ] **Step 4: Run the schema tests**

Run:

```bash
pytest tests/test_capability_ratchet_core.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/capability_ratchet tests/test_capability_ratchet_core.py
git commit -m "feat: define capability ratchet replay schema"
```

---

### Task 2: Implement the canonical append-only replay store

**Files:**
- Create: `src/inverted/capability_ratchet/replay_store.py`
- Test: `tests/test_capability_ratchet_replay_store.py`

**Interfaces:**
- Consumes the Task 1 record types.
- Produces `ReplayStore(root: Path)`.
- Produces `put_asset(payload: Any) -> str`, `read_asset(sha256: str) -> Any`, `append(record) -> str`, `records() -> tuple[ReplayRecord, ...]`, `get_failure(id) -> FailureFixture`, `validate() -> ReplayValidation`, `supersede(old_record_id, replacement_record_id, reason) -> str`.
- Canonical paths: `<root>/TEST_REPLAY.jsonl`, `<root>/replay-assets/sha256/<digest>.json`, `<root>/TEST_REPLAY.sha256`.

- [ ] **Step 1: Write failing append-only/integrity tests**

```python
import json
from inverted.capability_ratchet.replay_store import ReplayStore


def test_store_appends_canonical_row_and_content_addressed_asset(tmp_path, failure_fixture):
    store = ReplayStore(tmp_path)
    asset_sha = store.put_asset({"messages": [{"role": "user", "content": "x"}]})
    fixture = replace(failure_fixture, model_visible_asset_sha256=asset_sha)
    record_id = store.append(fixture)

    rows = (tmp_path / "TEST_REPLAY.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["record_id"] == record_id
    assert store.read_asset(asset_sha)["messages"][0]["content"] == "x"
    assert store.validate().ok is True


def test_store_never_rewrites_old_rows(tmp_path, failure_fixture):
    store = ReplayStore(tmp_path)
    asset_sha = store.put_asset({"messages": []})
    first = replace(failure_fixture, model_visible_asset_sha256=asset_sha)
    first_id = store.append(first)
    before = (tmp_path / "TEST_REPLAY.jsonl").read_bytes()
    correction_id = store.append(replace(first, failure_snapshot_id="fail-corrected"))
    store.supersede(first_id, correction_id, "metadata correction")
    assert (tmp_path / "TEST_REPLAY.jsonl").read_bytes().startswith(before)
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
pytest tests/test_capability_ratchet_replay_store.py -v
```

Expected: missing `ReplayStore`.

- [ ] **Step 3: Implement canonical JSONL + asset hashing**

Use canonical JSON (`sort_keys=True`, compact separators, UTF-8) and `os.fsync()` after every append, matching the durability pattern already used by V2 `EvidenceStore`. Compute each row's `record_id` as SHA-256 of the payload before adding `record_id`; duplicate identical appends must be idempotent rather than creating duplicate rows.

`validate()` must check:

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

It must verify every referenced replay asset, every failure parent, every replay request/result link, and the registry SHA manifest.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_capability_ratchet_replay_store.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/capability_ratchet/replay_store.py tests/test_capability_ratchet_replay_store.py
git commit -m "feat: add canonical TEST_REPLAY store"
```

---

### Task 3: Build replayable failure snapshots from V2 evidence

**Files:**
- Create: `src/inverted/capability_ratchet/snapshot.py`
- Test: `tests/test_capability_ratchet_snapshot.py`

**Interfaces:**
- Consumes `universal_tuning.core.AtomicTask`, `Observation`, V2 raw trial rows, task-pool records, and `ReplayStore`.
- Produces `build_failure_fixture(...) -> FailureFixture`.
- The fixture represents the **original physical batch/model-visible envelope**, while `focus_task_id` identifies the atomic failure being studied. Do not isolate an atomic task from its original five-task batch and call that an exact replay.

- [ ] **Step 1: Write failing tests for full-batch reconstruction and secret rejection**

```python
def test_snapshot_keeps_original_batch_context(tmp_path, failed_observation, atomic_tasks, raw_trial):
    store = ReplayStore(tmp_path)
    fixture = build_failure_fixture(
        observation=failed_observation,
        batch_tasks=atomic_tasks,
        raw_trial=raw_trial,
        runtime_provenance={"model": "qwen3.5:9b-q8_0", "model_digest": "digest"},
        partition=Partition.HISTORICAL,
        store=store,
        source_campaign_id="v2-real",
    )
    visible = store.read_asset(fixture.model_visible_asset_sha256)
    assert tuple(fixture.batch_task_ids) == tuple(task.task_id for task in atomic_tasks)
    assert fixture.focus_task_id == failed_observation.task_id
    assert visible["request_envelopes"] == [call["request"] for call in raw_trial["raw_calls"]]


def test_snapshot_rejects_plaintext_secret_material(tmp_path, failed_observation, atomic_tasks, raw_trial):
    raw_trial["raw_calls"][0]["request"]["headers"] = {"Authorization": "Bearer sk-secret"}
    with pytest.raises(ValueError, match="sensitive replay material"):
        build_failure_fixture(...)
```

- [ ] **Step 2: Run tests and verify failure**

```bash
pytest tests/test_capability_ratchet_snapshot.py -v
```

- [ ] **Step 3: Implement deterministic snapshot extraction**

`build_failure_fixture` must:

1. refuse observations with no material failure;
2. resolve the exact V2 `trial_id` from observation metadata;
3. retain every raw request envelope needed to reproduce the model-visible state;
4. keep all batch task IDs and designate one focus atomic failure;
5. store expected task/oracle references separately from model-visible input;
6. preserve partition/contamination lineage;
7. run a bounded sensitive-field scanner before `put_asset`;
8. write the model-visible envelope as one content-addressed asset;
9. return but not automatically append the fixture, keeping snapshot construction testable separately from persistence.

Sensitive-key rejection must include case-insensitive keys matching `authorization`, `api_key`, `token`, `password`, `secret`, and PEM private-key markers. Redacted placeholder values such as `<REDACTED>` are allowed.

- [ ] **Step 4: Run snapshot tests plus V2 evidence tests**

```bash
pytest tests/test_capability_ratchet_snapshot.py tests/test_universal_tuning_runner.py -v
```

If the existing runner test file has a different exact name, use the repository's existing universal-runner test file discovered at execution time; do not alter V2 expectations.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/capability_ratchet/snapshot.py tests/test_capability_ratchet_snapshot.py
git commit -m "feat: snapshot V2 failures for exact replay"
```

---

### Task 4: Implement replay requests, controlled diffs, and child result lineage

**Files:**
- Create: `src/inverted/capability_ratchet/replay.py`
- Test: `tests/test_capability_ratchet_replay.py`

**Interfaces:**
- Produces protocol `ReplayAdapter` with `runtime_provenance()` and `execute_fixture(fixture, visible_payload, request) -> ReplayCompletion`.
- Produces `ReplayExecutor(store, adapters)` and `plan(request) -> ReplayPlan`, `execute(request) -> ReplayResult`.
- Tests use `FakeReplayAdapter`; no real Ollama call.

- [ ] **Step 1: Write failing exact/counterfactual/cross-model lineage tests**

```python
class FakeReplayAdapter:
    def __init__(self, model_id="qwen3.5:9b-q8_0", digest="digest"):
        self.model_id = model_id
        self.digest = digest
        self.calls = []

    def runtime_provenance(self):
        return {"model": self.model_id, "model_digest": self.digest, "provider": "fake"}

    def execute_fixture(self, fixture, visible_payload, request):
        self.calls.append((fixture, visible_payload, request))
        return ReplayCompletion(
            raw_calls=({"request": visible_payload, "response": {"message": {"content": "ok"}}},),
            response_text="ok", physical_calls=1, latency_s=0.01,
            output_tokens=1, thinking_tokens=0, completion_reason="stop",
        )


def test_exact_replay_requires_same_source_provenance(replay_store, failure_fixture):
    executor = ReplayExecutor(replay_store, {failure_fixture.source_model_id: FakeReplayAdapter(digest="wrong")})
    request = exact_request(failure_fixture)
    with pytest.raises(ValueError, match="exact replay provenance mismatch"):
        executor.plan(request)


def test_cross_model_replay_records_target_adapter_change(replay_store, failure_fixture):
    adapter = FakeReplayAdapter(model_id="model-b", digest="digest-b")
    executor = ReplayExecutor(replay_store, {"model-b": adapter})
    request = ReplayRequest(
        replay_request_id="req-b", failure_snapshot_id=failure_fixture.failure_snapshot_id,
        target_model_id="model-b", replay_mode=ReplayMode.CROSS_MODEL,
        decision_id="D2", hypothesis_id="H-capability-boundary",
        changed_dimensions=("target_model",), compatibility_adapter="same-chat-contract-v1",
    )
    result = executor.execute(request)
    assert result.parent_failure_snapshot_id == failure_fixture.failure_snapshot_id
    assert result.target_model_id == "model-b"
    assert result.replay_mode is ReplayMode.CROSS_MODEL
```

- [ ] **Step 2: Run tests and verify failure**

```bash
pytest tests/test_capability_ratchet_replay.py -v
```

- [ ] **Step 3: Implement replay planning/execution**

`ReplayExecutor.plan()` must verify before any adapter call:

- fixture exists and asset hash validates;
- request references an unresolved/allowed decision;
- `EXACT`: target model ID and digest match source, `changed_dimensions == ()`, partition unchanged;
- `COUNTERFACTUAL`: source model remains source model and all changed dimensions are declared;
- `CROSS_MODEL`: only adapter/model/runtime compatibility fields may change unless additional dimensions are explicitly registered;
- historical/fresh/sealed labels cannot be mutated;
- replay result receives parent fixture/request IDs and raw-call asset hashes.

If execution fails semantically later, that outcome is still a `REPLAY_RESULT`; the higher V3 campaign layer will create a new child `FAILURE_FIXTURE`. Infrastructure exceptions are recorded separately and must not be converted to semantic failure.

- [ ] **Step 4: Run replay tests**

```bash
pytest tests/test_capability_ratchet_replay.py -v
```

Expected: all pass using fake adapters only.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/capability_ratchet/replay.py tests/test_capability_ratchet_replay.py
git commit -m "feat: add controlled failure replay executor"
```

---

### Task 5: Add a Qwen replay adapter without changing V2 behavior

**Files:**
- Modify: `src/inverted/universal_tuning/qwen_ollama.py`
- Create: `src/inverted/capability_ratchet/qwen_replay.py`
- Test: `tests/test_capability_ratchet_qwen_replay.py`
- Re-run: existing Qwen/V2 adapter tests.

**Interfaces:**
- Add only a reusable helper to V2 adapter request handling; `QwenOllamaAdapter.complete()` signature and behavior remain unchanged.
- Produce `QwenReplayAdapter(QwenOllamaAdapter)` implementing the Task 4 `ReplayAdapter` protocol.

- [ ] **Step 1: Write mocked-network tests proving request fidelity and zero call on invalid provenance**

```python
def test_qwen_replay_uses_frozen_messages_and_options(fake_opener, fixture, visible_payload):
    base = QwenOllamaAdapter(opener=fake_opener)
    adapter = QwenReplayAdapter(base)
    completion = adapter.execute_fixture(fixture, visible_payload, exact_request(fixture))
    sent = fake_opener.requests[-1]
    assert sent["messages"] == visible_payload["request_envelopes"][0]["messages"]
    assert sent["options"] == visible_payload["request_envelopes"][0]["options"]
    assert sent["think"] == visible_payload["request_envelopes"][0]["think"]
    assert completion.physical_calls == len(visible_payload["request_envelopes"])
```

Also add a regression test that an existing V2 `complete()` mocked request is byte/structure equivalent before and after the helper extraction.

- [ ] **Step 2: Run tests and verify the new adapter test fails while existing V2 tests pass**

```bash
pytest tests/test_capability_ratchet_qwen_replay.py tests/test_universal_tuning_qwen_cli.py -v
```

Use the repository's exact existing Qwen adapter/CLI test filename if named differently.

- [ ] **Step 3: Refactor the minimum shared seam**

Add a public-neutral helper such as:

```python
def post_chat_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
    return self._post(payload)
```

Do not change `_direct_options`, `_thinking_options`, `_batch_messages`, or `complete()` semantics. `QwenReplayAdapter` replays the frozen request envelopes directly; it does not regenerate a new prompt from the task text for `EXACT` mode.

For a cross-model request, adapter code may replace only `model` and compatibility-required inference fields declared in the `ReplayRequest`; it must emit an explicit adapter-diff record.

- [ ] **Step 4: Run new + complete V2 universal tuning tests**

```bash
pytest tests/test_capability_ratchet_qwen_replay.py tests/test_universal_tuning*.py -v
```

Expected: all pass, zero live network calls.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/universal_tuning/qwen_ollama.py src/inverted/capability_ratchet/qwen_replay.py tests/test_capability_ratchet_qwen_replay.py
git commit -m "feat: adapt frozen failures for Qwen replay"
```

---

### Task 6: Seed `TEST_REPLAY.jsonl` from the preserved V2 dump with zero inference

**Files:**
- Create: `src/inverted/capability_ratchet/historical.py`
- Test: `tests/test_capability_ratchet_historical.py`

**Interfaces:**
- Produces `V2EvidenceSource(root: Path)`.
- Produces `seed_v2_failures(source, replay_store) -> HistoricalSeedResult`.
- Produces `HistoricalSeedResult(total_observations, material_failures, fixtures_added, duplicate_fixtures, skipped_nonfailures, invalid_rows)`.

- [ ] **Step 1: Write a miniature V2 evidence fixture test**

```python
def test_v2_seeder_creates_one_fixture_per_atomic_failure_but_reuses_batch_asset(tmp_path, mini_v2_run):
    store = ReplayStore(tmp_path / "replay")
    result = seed_v2_failures(V2EvidenceSource(mini_v2_run), store)
    failures = [r for r in store.records() if r.record_type is ReplayRecordType.FAILURE_FIXTURE]
    assert result.material_failures == 2
    assert len(failures) == 2
    assert failures[0].model_visible_asset_sha256 == failures[1].model_visible_asset_sha256
    assert failures[0].focus_task_id != failures[1].focus_task_id
```

Add tests for:

- manifest/task-pool hash mismatch => hard failure before append;
- missing raw trial for a failed observation => invalid source and zero partial append for that trial;
- rerunning seeding => idempotent, no duplicate rows;
- source partition always `HISTORICAL`.

- [ ] **Step 2: Run tests and verify failure**

```bash
pytest tests/test_capability_ratchet_historical.py -v
```

- [ ] **Step 3: Implement V2 source validation and deterministic seeding**

Required source files:

```text
protocol-v2-manifest.json
task-pool-v2.json
atomic_observations.jsonl
raw_calls.jsonl
```

Validate the V2 manifest/task pool relationship before any fixture append. Build indexes by `trial_id`, `task_id`, and batch. A material failure is any observation with `semantic_pass == false`, `contract_pass == false`, `completed == false`, non-empty `failure_classes`, or a recorded reasoning-cap/negative-transfer condition required by the V3 spec.

Do not import V2 successful observations into `TEST_REPLAY.jsonl` as failure fixtures. Preserve their references in an optional historical-atlas summary only.

- [ ] **Step 4: Run tests and a zero-call dry seed against the committed V2 evidence path**

Run only file parsing; no adapter is constructed:

```bash
python -m inverted.capability_ratchet.cli seed-v2 \
  --source live-evidence/qwen-thinking-tuning-v2-real-20260907 \
  --replay-root runs/v3-preflight-replay \
  --dry-run
```

Expected output must include source counts and predicted fixture count, and explicitly state `MODEL_CALLS=0`.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/capability_ratchet/historical.py tests/test_capability_ratchet_historical.py
git commit -m "feat: seed replay corpus from V2 evidence"
```

---

### Task 7: Add fast replay querying and a safe CLI

**Files:**
- Create: `src/inverted/capability_ratchet/query.py`
- Create: `src/inverted/capability_ratchet/cli.py`
- Create: `scripts/run-test-replay.ps1`
- Test: `tests/test_capability_ratchet_query_cli.py`

**Interfaces:**
- Produces `ReplaySelector` fields: `source_model`, `target_model`, `family`, `failure_class`, `campaign`, `partition`, `promotion_state`, `snapshot_ids`.
- Produces `select_failures(store, selector) -> tuple[FailureFixture, ...]` with deterministic ordering.
- CLI commands: `validate`, `list`, `show`, `seed-v2 --dry-run`, `plan-replay`, `execute-replay`.
- `execute-replay` requires an explicit `--allow-model-calls`; absence must terminate before adapter construction.

- [ ] **Step 1: Write failing selector/CLI safety tests**

```python
def test_selector_can_pull_all_arithmetic_failures_for_one_source_model(store_with_failures):
    rows = select_failures(
        store_with_failures,
        ReplaySelector(source_model="qwen3.5:9b-q8_0", family="ARITHMETIC"),
    )
    assert rows
    assert all(r.source_model_id == "qwen3.5:9b-q8_0" and r.family == "ARITHMETIC" for r in rows)


def test_execute_replay_requires_explicit_model_call_gate(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ratchet", "execute-replay", "--snapshot", "fail-1"])
    assert main() == 2
    assert "--allow-model-calls" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests and verify failure**

```bash
pytest tests/test_capability_ratchet_query_cli.py -v
```

- [ ] **Step 3: Implement deterministic query and CLI surfaces**

`list` outputs compact rows containing snapshot ID, source model, family, failure classes, source campaign, partition, and replay count. `show` prints the fixture and verified asset metadata but must redact any field rejected by the snapshot privacy rules.

`plan-replay` performs all fixture/provenance/compatibility validation and prints the exact changed dimensions and expected physical calls without calling the adapter.

`execute-replay` checks `--allow-model-calls` before importing/constructing the Qwen adapter. This lets tests prove that ordinary replay inspection can never accidentally contact Ollama.

PowerShell wrapper:

```powershell
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
$ErrorActionPreference = 'Stop'
python -m inverted.capability_ratchet.cli @Args
exit $LASTEXITCODE
```

- [ ] **Step 4: Run CLI tests and manually inspect help only**

```bash
pytest tests/test_capability_ratchet_query_cli.py -v
python -m inverted.capability_ratchet.cli --help
python -m inverted.capability_ratchet.cli validate --replay-root runs/v3-preflight-replay
```

No `execute-replay --allow-model-calls` invocation is permitted in this plan.

- [ ] **Step 5: Commit**

```bash
git add src/inverted/capability_ratchet/query.py src/inverted/capability_ratchet/cli.py scripts/run-test-replay.ps1 tests/test_capability_ratchet_query_cli.py
git commit -m "feat: add fast TEST_REPLAY query CLI"
```

---

### Task 8: Prove replay-kernel invariants end to end with zero inference

**Files:**
- Create: `tests/test_capability_ratchet_preflight.py`
- Modify: `src/inverted/capability_ratchet/__init__.py` only for final stable exports.

**Interfaces:**
- Exercises Tasks 1–7 as one synthetic pipeline.
- Does not instantiate any network-enabled adapter.

- [ ] **Step 1: Write the end-to-end synthetic preflight tests**

The test must construct a miniature V2 run with one successful task and at least three failure types in the same/following batches: semantic failure, contract-only failure, and completion failure. Then:

```python
def test_v3_replay_kernel_end_to_end_without_model_calls(tmp_path, mini_v2_run):
    replay_root = tmp_path / "replay"
    store = ReplayStore(replay_root)
    seeded = seed_v2_failures(V2EvidenceSource(mini_v2_run), store)
    assert seeded.material_failures == 3

    fixtures = select_failures(store, ReplaySelector(source_model="qwen3.5:9b-q8_0"))
    assert len(fixtures) == 3

    exact = ReplayRequest.for_exact(fixtures[0], decision_id="D1", hypothesis_id="H-reproducibility")
    fake = FakeReplayAdapter(model_id=fixtures[0].source_model_id, digest=fixtures[0].source_model_digest)
    result = ReplayExecutor(store, {fake.model_id: fake}).execute(exact)

    assert result.parent_failure_snapshot_id == fixtures[0].failure_snapshot_id
    assert len(fake.calls) == 1
    assert store.validate().ok
    assert (replay_root / "TEST_REPLAY.jsonl").exists()
```

Also add explicit tests proving:

1. successful replay leaves original failure row byte-identical;
2. replay failure can be converted to a child fixture with parent lineage;
3. exact and cross-model records cannot be confused by query/filtering;
4. tampering with a replay asset blocks replay before adapter execution;
5. supersession preserves old rows;
6. fresh/sealed fixture partition cannot be changed by replay request;
7. same failure can be selected for another model without modifying the source fixture;
8. registry can be reconstructed solely from `TEST_REPLAY.jsonl` + verified replay assets;
9. zero network opener/API/Ollama function is invoked by the entire test module.

- [ ] **Step 2: Run the focused V3 foundation suite**

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

Expected: all pass; test telemetry confirms zero real model/network calls.

- [ ] **Step 3: Run the complete V2 universal-tuning regression suite**

```bash
pytest tests/test_universal_tuning*.py tests/test_qwen_thinking_tuning.py -v
```

Expected: all previously passing V2 tests remain green.

- [ ] **Step 4: Run the repository regression gate and integrity checks**

```bash
pytest -q
git diff --check
git status --short
```

Expected: repository test baseline remains green except only pre-existing documented skips/warnings; `git diff --check` reports no new whitespace defects; no generated `runs/` artifacts are staged.

- [ ] **Step 5: Verify the real preserved V2 dump can be parsed and planned with zero calls**

```bash
python -m inverted.capability_ratchet.cli seed-v2 \
  --source live-evidence/qwen-thinking-tuning-v2-real-20260907 \
  --replay-root runs/v3-v2-seed-check \
  --dry-run

python -m inverted.capability_ratchet.cli plan-replay \
  --replay-root runs/v3-v2-seed-check \
  --source-model qwen3.5:9b-q8_0 \
  --family ARITHMETIC \
  --limit 5
```

Expected: both commands report `MODEL_CALLS=0`; the plan identifies exact source fixtures and physical-call projections without executing them.

- [ ] **Step 6: Commit the completed replay foundation**

```bash
git add src/inverted/capability_ratchet src/inverted/universal_tuning/qwen_ollama.py scripts/run-test-replay.ps1 tests/test_capability_ratchet_*.py
git commit -m "test: validate V3 replay kernel end to end"
```

---

## Plan 1 Completion Gate

This plan is complete only when all of the following are true:

1. `TEST_REPLAY.jsonl` is append-only and validated by hash/lineage.
2. Every material V2 failure can be represented as a replayable fixture without isolating it from its original model-visible batch state.
3. Large model-visible payloads are content-addressed and hash-verified before replay.
4. Exact replay rejects model/digest mismatch before adapter execution.
5. Counterfactual replay records all changed dimensions.
6. Cross-model replay preserves the source fixture and records adapter/model changes separately.
7. Successful replay cannot overwrite the original failure.
8. Failed replay can become a child failure fixture without loops or blind retry semantics.
9. Historical/fresh/sealed contamination labels are immutable.
10. V2 evidence seeding is deterministic and idempotent.
11. Querying can select one fixture or large cohorts by model/family/failure/campaign/partition.
12. CLI model execution is impossible without explicit `--allow-model-calls`.
13. All Plan 1 tests and existing V2 universal-tuning regressions pass.
14. The preserved real V2 dump can be parsed into a replay plan with **zero model calls**.

## Deliberate Scope Boundary

This plan does **not** yet implement the V3 autopsy engine, tailor-made intervention generation, intervention tournament scheduler, ablation/sham search, failure mutation, skill extraction, capability compilation, controller training, or fine-tuning lane. Those components depend on the replay kernel being trustworthy. Building them before exact failure reconstruction and lineage are proven would make later causal results scientifically unsafe.

The next implementation increment begins only after this completion gate passes and will consume the stable interfaces defined here rather than replacing them.
