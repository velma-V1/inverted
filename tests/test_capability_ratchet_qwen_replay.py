from __future__ import annotations

import json

import pytest

from inverted.capability_ratchet import FailureFixture, Partition, ReplayMode, ReplayRequest
from inverted.capability_ratchet.qwen_replay import QwenReplayAdapter
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter


class Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def fixture() -> FailureFixture:
    return FailureFixture(
        failure_snapshot_id="failure-root", source_campaign_id="v2-real",
        source_trial_id="trial-1", focus_observation_id="obs-1", focus_task_id="t0",
        batch_task_ids=("t0", "t1", "t2", "t3", "t4"), family="ARITHMETIC",
        failure_classes=("SEMANTIC_FAIL",), source_model_id="qwen3.5:9b-q8_0",
        source_model_digest="digest", source_runtime={"provider": "ollama"},
        inference_profile={"thinking_budget": 0, "temperature": 0.7}, inference_seed=7,
        partition=Partition.HISTORICAL, model_visible_asset_sha256="a" * 64,
        state_hash="a" * 64, oracle_ref="task-pool-v2:t0:expected",
        expected_contract="answer_object", source_evidence_refs=("raw:trial-1",),
    )


def exact_request(item: FailureFixture) -> ReplayRequest:
    return ReplayRequest.for_exact(
        item, decision_id="D1", hypothesis_id="H-repro", request_id="req-exact"
    )


def score_ok(item, text):
    assert item.failure_snapshot_id == "failure-root"
    assert isinstance(text, str)
    return True, True, ()


def direct_visible():
    return {"request_envelopes": [{
        "model": "qwen3.5:9b-q8_0", "stream": False, "think": False,
        "options": {"seed": 7, "temperature": 0.7, "num_predict": 768},
        "messages": [{"role": "user", "content": "frozen direct request"}],
    }]}


def test_exact_replay_posts_frozen_payload_byte_for_structure() -> None:
    posted = []
    def opener(request, *, timeout):
        posted.append(json.loads(request.data.decode("utf-8")))
        return Response({
            "model": "qwen3.5:9b-q8_0", "done": True, "eval_count": 8,
            "message": {"content": '{"answer":42}'},
        })
    qwen = QwenOllamaAdapter(opener=opener)
    adapter = QwenReplayAdapter(qwen, scorer=score_ok)
    completion = adapter.execute_fixture(fixture(), direct_visible(), exact_request(fixture()))

    assert posted == direct_visible()["request_envelopes"]
    assert completion.completed is True
    assert completion.semantic_pass is True
    assert completion.contract_pass is True
    assert completion.raw_calls[0]["request"] == posted[0]
    assert completion.output_payload == {"text": '{"answer":42}'}


def test_two_stage_exact_replay_posts_both_frozen_envelopes_without_regeneration() -> None:
    visible = direct_visible()
    first = {**visible["request_envelopes"][0], "think": True,
             "options": {"seed": 7, "temperature": 1.0, "num_predict": 1024}}
    second = {**visible["request_envelopes"][0], "messages": [
        {"role": "assistant", "thinking": "frozen exposed trace", "content": ""},
        {"role": "user", "content": "frozen finalizer"},
    ]}
    visible = {"request_envelopes": [first, second]}
    posted = []
    responses = iter([
        {"model": "qwen3.5:9b-q8_0", "done": True, "eval_count": 100,
         "message": {"thinking": "new trace", "content": ""}},
        {"model": "qwen3.5:9b-q8_0", "done": True, "eval_count": 20,
         "message": {"content": '{"answer":42}'}},
    ])
    def opener(request, *, timeout):
        posted.append(json.loads(request.data.decode("utf-8")))
        return Response(next(responses))
    adapter = QwenReplayAdapter(QwenOllamaAdapter(opener=opener), scorer=score_ok)
    completion = adapter.execute_fixture(fixture(), visible, exact_request(fixture()))

    assert posted == visible["request_envelopes"]
    assert completion.metrics["physical_calls"] == 2
    assert completion.metrics["output_tokens"] == 120
    assert completion.metrics["thinking_tokens"] == 100


def test_counterfactual_payload_is_posted_as_supplied_not_rebuilt() -> None:
    visible = direct_visible()
    visible["request_envelopes"][0]["options"]["temperature"] = 0.2
    request = ReplayRequest(
        replay_request_id="req-cf", failure_snapshot_id="failure-root",
        parent_failure_snapshot_id="failure-root", parent_state_hash="a" * 64,
        decision_id="D2", hypothesis_id="H-temp", expected_causal_implication="temperature",
        mode=ReplayMode.COUNTERFACTUAL, source_model_id="qwen3.5:9b-q8_0",
        source_model_digest="digest", target_model_id="qwen3.5:9b-q8_0",
        target_model_digest="digest", partition=Partition.HISTORICAL,
        changed_dimensions=("request_envelopes.0.options.temperature",),
        overrides={"request_envelopes.0.options.temperature": 0.2},
    )
    posted = []
    def opener(req, *, timeout):
        posted.append(json.loads(req.data.decode("utf-8")))
        return Response({"model": "qwen3.5:9b-q8_0", "done": True, "eval_count": 3,
                         "message": {"content": '{"answer":42}'}})
    adapter = QwenReplayAdapter(QwenOllamaAdapter(opener=opener), scorer=score_ok)
    adapter.execute_fixture(fixture(), visible, request)
    assert posted[0]["options"]["temperature"] == 0.2
    assert posted[0] == visible["request_envelopes"][0]


def test_cross_model_replaces_only_model_field_by_default() -> None:
    visible = direct_visible()
    request = ReplayRequest(
        replay_request_id="req-cross", failure_snapshot_id="failure-root",
        parent_failure_snapshot_id="failure-root", parent_state_hash="a" * 64,
        decision_id="D3", hypothesis_id="H-model", expected_causal_implication="model swap",
        mode=ReplayMode.CROSS_MODEL, source_model_id="qwen3.5:9b-q8_0",
        source_model_digest="digest", target_model_id="qwen-other",
        target_model_digest="other-digest", partition=Partition.HISTORICAL,
        changed_dimensions=("target_model",), overrides={},
    )
    posted = []
    def opener(req, *, timeout):
        posted.append(json.loads(req.data.decode("utf-8")))
        return Response({"model": "qwen-other", "done": True, "eval_count": 4,
                         "message": {"content": '{"answer":42}'}})
    qwen = QwenOllamaAdapter(model_id="qwen-other", opener=opener)
    adapter = QwenReplayAdapter(qwen, scorer=score_ok)
    adapter.execute_fixture(fixture(), visible, request)

    expected = json.loads(json.dumps(visible["request_envelopes"][0]))
    expected["model"] = "qwen-other"
    assert posted == [expected]


def test_missing_scorer_is_rejected_before_posting() -> None:
    posted = []
    qwen = QwenOllamaAdapter(opener=lambda request, *, timeout: posted.append(request))
    adapter = QwenReplayAdapter(qwen, scorer=None)
    with pytest.raises(ValueError, match="scorer"):
        adapter.execute_fixture(fixture(), direct_visible(), exact_request(fixture()))
    assert posted == []


def test_scorer_exception_propagates_without_reclassification() -> None:
    def scorer(item, text):
        raise RuntimeError("scorer invalid")
    def opener(request, *, timeout):
        return Response({"model": "qwen3.5:9b-q8_0", "done": True, "eval_count": 1,
                         "message": {"content": "x"}})
    adapter = QwenReplayAdapter(QwenOllamaAdapter(opener=opener), scorer=scorer)
    with pytest.raises(RuntimeError, match="scorer invalid"):
        adapter.execute_fixture(fixture(), direct_visible(), exact_request(fixture()))
