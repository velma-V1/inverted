from __future__ import annotations

from dataclasses import replace

import pytest

from inverted.capability_ratchet import Partition
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.snapshot import build_failure_fixture
from inverted.universal_tuning.core import AtomicTask, FailureClass, Observation, Profile


def tasks() -> tuple[AtomicTask, ...]:
    return tuple(
        AtomicTask(
            task_id=f"arith-{index}", family="ARITHMETIC", difficulty=2,
            prompt=f"Compute item {index}", expected=index + 10,
            scorer="exact_value", contract="answer_object",
        )
        for index in range(5)
    )


def batch_text() -> str:
    return "\n\n".join(f"TASK {task.task_id}\n{task.prompt}" for task in tasks())


def failed_observation(**changes: object) -> Observation:
    values = dict(
        observation_id="obs-2", batch_id="ARITHMETIC:gate:000", task_id="arith-2",
        family="ARITHMETIC", stage="gate", profile=Profile(thinking_budget=1024, temperature=1.0),
        inference_seed=1234, decision_reason="ESTABLISH_DIRECT_VS_THINKING",
        semantic_pass=False, contract_pass=True, completed=True,
        semantic_quality=0.0, contract_quality=1.0, latency_s=1.5,
        output_tokens=12, thinking_tokens=1024, physical_calls=2,
        response_text='{"answer":99}', failure_classes=(FailureClass.SEMANTIC_FAIL,),
        raw_call_refs=("trial-1:call:0", "trial-1:call:1"), metadata=(("trial_id", "trial-1"),),
    )
    values.update(changes)
    return Observation(**values)  # type: ignore[arg-type]


def raw_trial() -> dict[str, object]:
    return {
        "trial_id": "trial-1",
        "physical_calls": 2,
        "raw_calls": [
            {
                "request": {
                    "model": "qwen3.5:9b-q8_0", "think": True, "stream": False,
                    "options": {"temperature": 1.0, "num_predict": 1024, "seed": 1234},
                    "messages": [
                        {"role": "system", "content": "Follow contract."},
                        {"role": "user", "content": batch_text()},
                    ],
                },
                "response": {"message": {"role": "assistant", "content": "", "thinking": "private exposed runtime trace"}},
            },
            {
                "request": {
                    "model": "qwen3.5:9b-q8_0", "think": False, "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 768, "seed": 1234},
                    "messages": [
                        {"role": "system", "content": "Follow contract."},
                        {"role": "user", "content": batch_text()},
                        {"role": "assistant", "content": "", "thinking": "private exposed runtime trace"},
                        {"role": "user", "content": "Return final JSON."},
                    ],
                },
                "response": {"message": {"role": "assistant", "content": '{"answers":[]}' }},
            },
        ],
        "responses": ['{"answer":10}', '{"answer":11}', '{"answer":99}', '{"answer":13}', '{"answer":14}'],
    }


def runtime() -> dict[str, object]:
    return {
        "provider": "ollama", "ollama_version": "0.32.15",
        "model": "qwen3.5:9b-q8_0",
        "model_digest": "441ec31e4d2aedceb97dd834b036db104d943fbe3dbc1e5c8ac95eeaa9141c77",
        "base_url": "http://127.0.0.1:11434",
    }


def build(tmp_path, **changes: object):
    kwargs = dict(
        failed_observation=failed_observation(), atomic_tasks=tasks(), raw_trial=raw_trial(),
        store=ReplayStore(tmp_path), source_campaign_id="v2-real",
        runtime_provenance=runtime(), partition=Partition.HISTORICAL,
        source_evidence_refs=("raw_calls.jsonl:trial-1", "atomic_observations.jsonl:obs-2"),
    )
    kwargs.update(changes)
    return build_failure_fixture(**kwargs), kwargs["store"]


def test_snapshot_preserves_whole_physical_batch_and_exact_request_envelopes(tmp_path) -> None:
    fixture, store = build(tmp_path)
    visible = store.read_asset(fixture.model_visible_asset_sha256)

    assert tuple(fixture.batch_task_ids) == tuple(task.task_id for task in tasks())
    assert fixture.focus_task_id == "arith-2"
    assert visible["request_envelopes"] == [call["request"] for call in raw_trial()["raw_calls"]]
    assert len(visible["request_envelopes"]) == 2
    assert visible["request_envelopes"][1]["messages"][2]["thinking"] == "private exposed runtime trace"
    assert fixture.state_hash == fixture.model_visible_asset_sha256


def test_oracle_expected_and_original_outputs_are_not_model_visible(tmp_path) -> None:
    fixture, store = build(tmp_path)
    visible = store.read_asset(fixture.model_visible_asset_sha256)
    rendered = repr(visible)

    assert fixture.oracle_ref.startswith("task-pool-v2:arith-2:")
    assert fixture.expected_contract == "answer_object"
    assert "expected" not in visible
    assert "oracle" not in visible
    assert '"answer":99' not in rendered
    assert "responses" not in visible


def test_fixture_keeps_failure_and_source_lineage_outside_visible_asset(tmp_path) -> None:
    fixture, store = build(tmp_path)
    visible = store.read_asset(fixture.model_visible_asset_sha256)

    assert fixture.source_trial_id == "trial-1"
    assert fixture.source_campaign_id == "v2-real"
    assert fixture.focus_observation_id == "obs-2"
    assert fixture.failure_classes == ("SEMANTIC_FAIL",)
    assert fixture.partition is Partition.HISTORICAL
    assert fixture.source_model_id == "qwen3.5:9b-q8_0"
    assert fixture.source_model_digest == runtime()["model_digest"]
    assert fixture.source_evidence_refs == ("raw_calls.jsonl:trial-1", "atomic_observations.jsonl:obs-2")
    assert fixture.metadata["stage"] == "gate"
    assert fixture.metadata["original_response_text"] == '{"answer":99}'
    assert "original_response_text" not in visible


def test_snapshot_does_not_auto_append_fixture(tmp_path) -> None:
    fixture, store = build(tmp_path)
    assert fixture.record_id is None
    assert store.records() == ()
    assert not store.registry_path.exists()


def test_nonfailure_observation_is_rejected(tmp_path) -> None:
    observation = failed_observation(
        semantic_pass=True, contract_pass=True, completed=True,
        semantic_quality=1.0, contract_quality=1.0, failure_classes=(),
    )
    with pytest.raises(ValueError, match="failure"):
        build(tmp_path, failed_observation=observation)


def test_failure_class_is_derived_when_failed_boolean_has_no_class(tmp_path) -> None:
    observation = failed_observation(semantic_pass=False, failure_classes=())
    fixture, _ = build(tmp_path, failed_observation=observation)
    assert fixture.failure_classes == ("SEMANTIC_FAIL",)


@pytest.mark.parametrize("sensitive_key", ["authorization", "Authorization", "api_key", "API_KEY", "token", "password", "secret"])
def test_plaintext_sensitive_keys_are_rejected(tmp_path, sensitive_key) -> None:
    trial = raw_trial()
    trial["raw_calls"][0]["request"][sensitive_key] = "plaintext-value"
    with pytest.raises(ValueError, match="sensitive|secret"):
        build(tmp_path, raw_trial=trial)


def test_redacted_sensitive_key_is_allowed(tmp_path) -> None:
    trial = raw_trial()
    trial["raw_calls"][0]["request"]["Authorization"] = "<REDACTED>"
    fixture, store = build(tmp_path, raw_trial=trial)
    visible = store.read_asset(fixture.model_visible_asset_sha256)
    assert visible["request_envelopes"][0]["Authorization"] == "<REDACTED>"


def test_pem_private_key_marker_is_rejected_anywhere_in_visible_payload(tmp_path) -> None:
    trial = raw_trial()
    trial["raw_calls"][0]["request"]["messages"][0]["content"] = "-----BEGIN PRIVATE KEY-----\nabc"
    with pytest.raises(ValueError, match="private key|sensitive|secret"):
        build(tmp_path, raw_trial=trial)


def test_trial_identity_focus_and_family_must_match(tmp_path) -> None:
    with pytest.raises(ValueError, match="trial"):
        build(tmp_path, raw_trial={**raw_trial(), "trial_id": "other"})
    with pytest.raises(ValueError, match="focus|task"):
        build(tmp_path, failed_observation=failed_observation(task_id="missing"))
    bad_tasks = list(tasks())
    bad_tasks[4] = replace(bad_tasks[4], family="CODING_GENERATION")
    with pytest.raises(ValueError, match="family"):
        build(tmp_path, atomic_tasks=tuple(bad_tasks))


def test_runtime_model_must_match_every_request_envelope(tmp_path) -> None:
    trial = raw_trial()
    trial["raw_calls"][1]["request"]["model"] = "other-model"
    with pytest.raises(ValueError, match="model"):
        build(tmp_path, raw_trial=trial)


def test_snapshot_is_deterministic_and_reuses_content_addressed_asset(tmp_path) -> None:
    first, store = build(tmp_path)
    second = build_failure_fixture(
        failed_observation=failed_observation(), atomic_tasks=tasks(), raw_trial=raw_trial(), store=store,
        source_campaign_id="v2-real", runtime_provenance=runtime(), partition=Partition.HISTORICAL,
        source_evidence_refs=("raw_calls.jsonl:trial-1", "atomic_observations.jsonl:obs-2"),
    )
    assert first == second
    assert len(list(store.asset_root.glob("*.json"))) == 1



def test_task_pool_records_must_match_original_batch_prompt(tmp_path) -> None:
    bad_tasks = list(tasks())
    bad_tasks[1] = replace(bad_tasks[1], prompt="Different prompt content")
    with pytest.raises(ValueError, match="prompt|batch"):
        build(tmp_path, atomic_tasks=tuple(bad_tasks))


def test_first_request_seed_and_profile_must_match_observation(tmp_path) -> None:
    wrong_seed = raw_trial()
    wrong_seed["raw_calls"][0]["request"]["options"]["seed"] = 999
    with pytest.raises(ValueError, match="seed|profile"):
        build(tmp_path, raw_trial=wrong_seed)

    wrong_temperature = raw_trial()
    wrong_temperature["raw_calls"][0]["request"]["options"]["temperature"] = 0.2
    with pytest.raises(ValueError, match="temperature|profile"):
        build(tmp_path, raw_trial=wrong_temperature)


def test_rejected_snapshot_leaves_no_orphan_asset(tmp_path) -> None:
    observation = failed_observation(response_text="-----BEGIN PRIVATE KEY-----\nsecret")
    store = ReplayStore(tmp_path)
    with pytest.raises(ValueError, match="private key|secret"):
        build(tmp_path, failed_observation=observation, store=store)
    assert not store.asset_root.exists() or list(store.asset_root.glob("*.json")) == []


def test_camelcase_sensitive_key_is_rejected(tmp_path) -> None:
    trial = raw_trial()
    trial["raw_calls"][0]["request"]["ApiKey"] = "plaintext-value"
    with pytest.raises(ValueError, match="sensitive|secret"):
        build(tmp_path, raw_trial=trial)


def test_v2_nonfirst_atomic_observation_may_have_zero_attributed_physical_calls(tmp_path) -> None:
    observation = failed_observation(physical_calls=0)
    fixture, store = build(tmp_path, failed_observation=observation)
    visible = store.read_asset(fixture.model_visible_asset_sha256)
    assert len(visible["request_envelopes"]) == 2
    assert fixture.metadata["attributed_physical_calls"] == 0
    assert fixture.metadata["physical_calls"] == 2
