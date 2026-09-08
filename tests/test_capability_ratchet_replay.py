from __future__ import annotations

from dataclasses import replace

import pytest

from inverted.capability_ratchet import FailureFixture, Partition, ReplayMode, ReplayRequest
from inverted.capability_ratchet.replay import ReplayCompletion, ReplayExecutor
from inverted.capability_ratchet.replay_store import ReplayStore


class FakeReplayAdapter:
    def __init__(self, *, model="source-model", digest="source-digest", provider="fake",
                 completion=None, error=None) -> None:
        self.model = model
        self.digest = digest
        self.provider = provider
        self.completion = completion
        self.error = error
        self.calls = []

    def runtime_provenance(self):
        return {"provider": self.provider, "model": self.model,
                "model_digest": self.digest, "version": "1"}

    def execute_fixture(self, fixture, visible_payload, request):
        self.calls.append((fixture, visible_payload, request))
        if self.error is not None:
            raise self.error
        if self.completion is not None:
            return self.completion
        return successful_completion(visible_payload)


def visible_payload(model="source-model"):
    return {
        "request_envelopes": [{
            "model": model,
            "think": False,
            "stream": False,
            "options": {"seed": 7, "temperature": 0.7, "num_predict": 768},
            "messages": [
                {"role": "system", "content": "Follow contract."},
                {"role": "user", "content": "TASK t0\nReturn JSON."},
            ],
        }]
    }


def fixture_and_store(tmp_path):
    store = ReplayStore(tmp_path)
    asset = store.put_asset(visible_payload())
    fixture = FailureFixture(
        failure_snapshot_id="failure-root", source_campaign_id="v2-real",
        source_trial_id="trial-1", focus_observation_id="obs-1", focus_task_id="t0",
        batch_task_ids=("t0", "t1", "t2", "t3", "t4"), family="ARITHMETIC",
        failure_classes=("SEMANTIC_FAIL",), source_model_id="source-model",
        source_model_digest="source-digest", source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": 0, "temperature": 0.7}, inference_seed=7,
        partition=Partition.HISTORICAL, model_visible_asset_sha256=asset, state_hash=asset,
        oracle_ref="task-pool-v2:t0:expected", expected_contract="answer_object",
        source_evidence_refs=("raw:trial-1", "obs:obs-1"),
    )
    store.append(fixture)
    return fixture, store


def successful_completion(payload):
    return ReplayCompletion(
        completed=True, semantic_pass=True, contract_pass=True,
        output_payload={"answer": 42},
        raw_calls=tuple(
            {"request": request, "response": {"message": {"content": '{"answer":42}'}}}
            for request in payload["request_envelopes"]
        ),
        failure_classes=(), metrics={"latency_s": 0.1},
    )


def failed_completion(payload, *, model=None):
    requests = []
    for request in payload["request_envelopes"]:
        copied = {**request}
        if model is not None:
            copied["model"] = model
        requests.append(copied)
    return ReplayCompletion(
        completed=True, semantic_pass=False, contract_pass=True,
        output_payload={"answer": "wrong"},
        raw_calls=tuple(
            {"request": request, "response": {"message": {"content": "wrong"}}}
            for request in requests
        ),
        failure_classes=("SEMANTIC_FAIL",), metrics={"latency_s": 0.2},
    )


def exact_request(fixture):
    return ReplayRequest.for_exact(
        fixture, decision_id="D1", hypothesis_id="H-reproducibility",
        request_id="req-exact",
    )


def counterfactual_request(fixture, *, path="request_envelopes.0.options.temperature", value=0.2):
    return ReplayRequest(
        replay_request_id="req-cf", failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash, decision_id="D2", hypothesis_id="H-temp",
        expected_causal_implication="temperature changes behavior",
        mode=ReplayMode.COUNTERFACTUAL, source_model_id=fixture.source_model_id,
        source_model_digest=fixture.source_model_digest, target_model_id=fixture.source_model_id,
        target_model_digest=fixture.source_model_digest, partition=fixture.partition,
        changed_dimensions=(path,), overrides={path: value},
    )


def cross_model_request(fixture):
    return ReplayRequest(
        replay_request_id="req-cross", failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash, decision_id="D3", hypothesis_id="H-model",
        expected_causal_implication="compare compatible target model",
        mode=ReplayMode.CROSS_MODEL, source_model_id=fixture.source_model_id,
        source_model_digest=fixture.source_model_digest, target_model_id="target-model",
        target_model_digest="target-digest", partition=fixture.partition,
        changed_dimensions=("target_model",), overrides={},
    )


def test_exact_plan_rejects_source_digest_mismatch_before_adapter_execution(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter(digest="wrong")
    executor = ReplayExecutor(store, {fixture.source_model_id: adapter})
    with pytest.raises(ValueError, match="exact replay provenance mismatch"):
        executor.plan(exact_request(fixture))
    assert adapter.calls == []


def test_plan_rejects_corrupt_fixture_asset_before_adapter_execution(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter()
    asset = store.asset_root / f"{fixture.model_visible_asset_sha256}.json"
    asset.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity|asset"):
        ReplayExecutor(store, {fixture.source_model_id: adapter}).plan(exact_request(fixture))
    assert adapter.calls == []


def test_counterfactual_changes_only_declared_registered_leaf(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter()
    executor = ReplayExecutor(store, {fixture.source_model_id: adapter})
    original = store.read_asset(fixture.model_visible_asset_sha256)
    plan = executor.plan(counterfactual_request(fixture))

    assert plan.visible_payload["request_envelopes"][0]["options"]["temperature"] == 0.2
    assert plan.visible_payload["request_envelopes"][0]["options"]["seed"] == 7
    assert store.read_asset(fixture.model_visible_asset_sha256) == original
    assert plan.changed_values == {"request_envelopes.0.options.temperature": (0.7, 0.2)}


def test_counterfactual_rejects_unregistered_or_model_dimension(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter()
    executor = ReplayExecutor(store, {fixture.source_model_id: adapter})
    request = counterfactual_request(fixture, path="request_envelopes.0.model", value="other")
    with pytest.raises(ValueError, match="registered|dimension|model"):
        executor.plan(request)


def test_cross_model_plan_records_explicit_runtime_diff(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter(model="target-model", digest="target-digest", provider="other")
    plan = ReplayExecutor(store, {"target-model": adapter}).plan(cross_model_request(fixture))

    assert plan.adapter_changes["model"] == {"source": "source-model", "target": "target-model"}
    assert plan.adapter_changes["model_digest"] == {"source": "source-digest", "target": "target-digest"}
    assert plan.adapter_changes["provider"] == {"source": "fake", "target": "other"}
    assert store.read_asset(fixture.model_visible_asset_sha256) == visible_payload()


def test_partition_parent_state_and_source_identity_are_immutable(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter()
    executor = ReplayExecutor(store, {fixture.source_model_id: adapter})

    with pytest.raises(ValueError, match="partition"):
        executor.plan(replace(exact_request(fixture), partition=Partition.TRAINING))
    with pytest.raises(ValueError, match="parent state"):
        executor.plan(replace(exact_request(fixture), parent_state_hash="1" * 64))
    wrong_source = replace(
        exact_request(fixture), source_model_id="other", source_model_digest="other-digest",
        target_model_id="other", target_model_digest="other-digest",
    )
    with pytest.raises(ValueError, match="source identity|parent"):
        executor.plan(wrong_source)
    assert adapter.calls == []


def test_plan_is_pure_and_does_not_append_request(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    before = store.records()
    plan = ReplayExecutor(store, {fixture.source_model_id: FakeReplayAdapter()}).plan(exact_request(fixture))
    assert replace(plan.fixture, record_id=None) == fixture
    assert store.records() == before


def test_execute_success_appends_request_and_result_with_raw_assets(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter()
    result = ReplayExecutor(store, {fixture.source_model_id: adapter}).execute(exact_request(fixture))

    assert result.completed and result.semantic_pass and result.contract_pass
    assert result.child_failure_snapshot_id is None
    assert store.read_asset(result.output_asset_sha256) == {"answer": 42}
    raw = store.read_asset(result.raw_call_asset_sha256)
    assert raw["raw_calls"][0]["request"] == visible_payload()["request_envelopes"][0]
    records = store.records()
    assert any(getattr(record, "replay_request_id", None) == "req-exact" for record in records)
    assert any(getattr(record, "replay_result_id", None) == result.replay_result_id for record in records)
    assert store.validate().ok


def test_failed_replay_creates_child_fixture_with_exact_parent_lineage(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    completion = failed_completion(visible_payload())
    adapter = FakeReplayAdapter(completion=completion)
    result = ReplayExecutor(store, {fixture.source_model_id: adapter}).execute(exact_request(fixture))

    assert result.child_failure_snapshot_id is not None
    child = store.get_failure(result.child_failure_snapshot_id)
    assert child.parent_failure_snapshot_id == fixture.failure_snapshot_id
    assert child.parent_state_hash == fixture.state_hash
    assert child.family == fixture.family
    assert child.partition == fixture.partition
    assert (child.source_model_id, child.source_model_digest) == (fixture.source_model_id, fixture.source_model_digest)
    assert child.failure_classes == ("SEMANTIC_FAIL",)
    assert store.validate().ok


def test_cross_model_failure_child_uses_target_identity_and_actual_requests(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    completion = failed_completion(visible_payload(), model="target-model")
    adapter = FakeReplayAdapter(model="target-model", digest="target-digest", provider="other",
                                completion=completion)
    result = ReplayExecutor(store, {"target-model": adapter}).execute(cross_model_request(fixture))

    child = store.get_failure(result.child_failure_snapshot_id)
    assert (child.source_model_id, child.source_model_digest) == ("target-model", "target-digest")
    visible = store.read_asset(child.model_visible_asset_sha256)
    assert visible["request_envelopes"][0]["model"] == "target-model"
    assert result.adapter_changes["model"]["target"] == "target-model"
    assert store.validate().ok


def test_infrastructure_exception_is_not_reclassified_as_model_failure(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter(error=OSError("provider unavailable"))
    executor = ReplayExecutor(store, {fixture.source_model_id: adapter})

    with pytest.raises(OSError, match="provider unavailable"):
        executor.execute(exact_request(fixture))
    records = store.records()
    assert any(isinstance(record, ReplayRequest) and record.replay_request_id == "req-exact" for record in records)
    assert not any(getattr(record, "replay_result_id", None) for record in records)
    assert not any(isinstance(record, FailureFixture) and record.failure_snapshot_id != fixture.failure_snapshot_id
                   for record in records)
    assert store.validate().ok


def test_adapter_completion_raw_calls_are_required(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    completion = ReplayCompletion(
        completed=True, semantic_pass=True, contract_pass=True,
        output_payload={"answer": 42}, raw_calls=(), failure_classes=(), metrics={},
    )
    adapter = FakeReplayAdapter(completion=completion)
    with pytest.raises(ValueError, match="raw call"):
        ReplayExecutor(store, {fixture.source_model_id: adapter}).execute(exact_request(fixture))




def test_cross_model_result_records_actual_request_model_substitution(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    completion = failed_completion(visible_payload(), model="target-model")
    adapter = FakeReplayAdapter(
        model="target-model", digest="target-digest", provider="other", completion=completion,
    )
    result = ReplayExecutor(store, {"target-model": adapter}).execute(cross_model_request(fixture))
    assert result.adapter_changes["request_envelopes.0.model"] == {
        "source": "source-model", "target": "target-model",
    }


def test_counterfactual_accepts_frozen_nested_json_override(tmp_path) -> None:
    fixture, store = fixture_and_store(tmp_path)
    adapter = FakeReplayAdapter()
    replacement = [
        {"role": "user", "content": "TASK t0\nReturn JSON."},
        {"role": "system", "content": "Follow contract."},
    ]
    request = counterfactual_request(
        fixture, path="request_envelopes.0.messages", value=replacement,
    )
    plan = ReplayExecutor(store, {fixture.source_model_id: adapter}).plan(request)
    assert plan.visible_payload["request_envelopes"][0]["messages"] == replacement
    assert plan.changed_values["request_envelopes.0.messages"][1] == replacement
