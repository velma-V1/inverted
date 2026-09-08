from __future__ import annotations

import json
from typing import Any

from inverted.capability_ratchet import Partition, QwenRetryAttemptExecutor, ReplayFailureSnapshotter
from inverted.capability_ratchet.orchestration import AttemptContext
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.universal_tuning.core import AtomicTask, Profile
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter


MODEL_ID = "qwen3.5:9b-q8_0"
MODEL_DIGEST = "d" * 64


def _task() -> AtomicTask:
    return AtomicTask(
        task_id="qwen-timeout-snapshot",
        family="LOGIC",
        difficulty=5,
        prompt="Return the only valid assignment as an answer object.",
        expected="B",
        scorer="exact_value",
        contract="answer_object",
    )


def _profile() -> Profile:
    return Profile(
        thinking_budget=0,
        temperature=0.7,
        top_p=0.81,
        top_k=37,
        min_p=0.04,
        repeat_penalty=1.06,
        num_ctx=12288,
        final_max_tokens=222,
    )


def test_timeout_outcome_round_trips_through_canonical_replay_store(tmp_path) -> None:
    posted: list[dict[str, Any]] = []

    def opener(request, *, timeout):
        posted.append(json.loads(request.data.decode("utf-8")))
        raise TimeoutError("canonical snapshot timeout")

    context = AttemptContext(
        model_id=MODEL_ID,
        task=_task(),
        stage="INITIAL",
        attempt_index=0,
        retry_ingredient=None,
        previous_outcome=None,
    )
    executor = QwenRetryAttemptExecutor(
        adapter=QwenOllamaAdapter(opener=opener),
        base_profile=_profile(),
        seed=777,
    )
    outcome = executor(context)

    store = ReplayStore(tmp_path / "replay")
    snapshotter = ReplayFailureSnapshotter(
        store=store,
        source_campaign_id="test1b-v3-runtime-failure",
        runtime_provenance={
            "provider": "ollama",
            "model": MODEL_ID,
            "model_digest": MODEL_DIGEST,
        },
        partition=Partition.HISTORICAL,
    )
    snapshot_id = snapshotter(context, outcome)
    fixture = store.get_failure(snapshot_id)

    assert fixture.failure_classes == ("TIMEOUT",)
    assert fixture.focus_task_id == _task().task_id
    assert fixture.inference_seed == 777
    assert fixture.metadata["attempt_stage"] == "INITIAL"

    visible = store.read_asset(fixture.model_visible_asset_sha256)
    assert visible["request_envelopes"] == posted
    assert "execution_error" not in json.dumps(visible)

    forensic_sha = fixture.metadata["forensic_asset_sha256"]
    forensic = store.read_asset(forensic_sha)
    assert forensic["execution_error"]["class"] == "TIMEOUT"
    assert forensic["raw_calls"][0]["request"] == posted[0]
    assert forensic["raw_calls"][0]["error"]["type"] == "TimeoutError"
    assert forensic["telemetry"]["physical_calls"] == 1

    validation = store.validate()
    assert validation.ok is True
    assert validation.row_count == 1
