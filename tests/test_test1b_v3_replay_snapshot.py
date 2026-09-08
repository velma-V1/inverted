from __future__ import annotations

from pathlib import Path
from typing import Any

import inverted.capability_ratchet as ratchet
from inverted.capability_ratchet.core import FailureFixture, Partition
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.universal_tuning.core import AtomicTask


MODEL_ID = "qwen3.5:9b-q8_0"
MODEL_DIGEST = "a" * 64


def _api() -> dict[str, Any]:
    required = (
        "AttemptEvidence",
        "AttemptOutcome",
        "ReplayFailureSnapshotter",
        "RetryCampaignOrchestrator",
        "RetryIngredient",
    )
    missing = [name for name in required if not hasattr(ratchet, name)]
    assert not missing, f"Test1B-v3 replay snapshot API is missing: {missing}"
    return {name: getattr(ratchet, name) for name in required}


def _task() -> AtomicTask:
    return AtomicTask(
        task_id="logic-d3",
        family="LOGIC",
        difficulty=3,
        prompt="Return the only valid assignment.",
        expected={"answer": "B"},
        scorer="exact_value",
        contract="answer_object",
    )


def _runtime() -> dict[str, Any]:
    return {
        "provider": "ollama",
        "ollama_version": "0.32.15",
        "model": MODEL_ID,
        "model_digest": MODEL_DIGEST,
        "quantization": "Q8_0",
    }


def _evidence(AttemptEvidence: Any, *, stage: str) -> Any:
    request = {
        "model": MODEL_ID,
        "think": True,
        "stream": False,
        "options": {
            "temperature": 0.35,
            "top_p": 0.9,
            "top_k": 40,
            "min_p": 0.05,
            "repeat_penalty": 1.05,
            "seed": 1234,
            "num_predict": 2048,
        },
        "messages": [
            {"role": "system", "content": f"Test1B-v3 {stage}"},
            {"role": "user", "content": _task().prompt},
        ],
    }
    return AttemptEvidence(
        request_envelopes=(request,),
        forensic_payload={
            "raw_calls": (
                {
                    "request": request,
                    "response": {
                        "message": {
                            "role": "assistant",
                            "content": '{"answer":"A"}',
                            "thinking": f"exposed-runtime-thinking-{stage}",
                        }
                    },
                },
            ),
            "telemetry": {
                "ttft_s": 0.12,
                "latency_s": 1.7,
                "output_tokens": 17,
                "thinking_tokens": 731,
            },
        },
        oracle_payload={
            "task_id": _task().task_id,
            "expected": _task().expected,
            "contract": _task().contract,
            "scorer": _task().scorer,
            "score": {"semantic_pass": False, "contract_pass": True},
        },
        inference_profile={
            "thinking_mode": "THINKING",
            "thinking_budget": 2048,
            "temperature": 0.35,
            "top_p": 0.9,
            "top_k": 40,
            "min_p": 0.05,
            "presence_penalty": 0.0,
            "repeat_penalty": 1.05,
            "output_token_ceiling": 2048,
        },
        inference_seed=1234,
        source_evidence_refs=(f"live-attempt:{stage}",),
    )


def _build_hard_failure_store(tmp_path: Path):
    api = _api()
    AttemptEvidence = api["AttemptEvidence"]
    AttemptOutcome = api["AttemptOutcome"]
    ReplayFailureSnapshotter = api["ReplayFailureSnapshotter"]
    RetryCampaignOrchestrator = api["RetryCampaignOrchestrator"]
    RetryIngredient = api["RetryIngredient"]

    store = ReplayStore(tmp_path)
    snapshotter = ReplayFailureSnapshotter(
        store=store,
        source_campaign_id="test1b-v3-unit",
        runtime_provenance=_runtime(),
        partition=Partition.DEVELOPMENT,
    )

    def execute_attempt(context: Any) -> Any:
        return AttemptOutcome(
            passed=False,
            failure_classes=("SEMANTIC_FAIL",),
            failure_subtypes=(f"SEMANTIC_FAIL:{context.stage}",),
            evidence=_evidence(AttemptEvidence, stage=context.stage),
        )

    orchestrator = RetryCampaignOrchestrator(
        execute_attempt=execute_attempt,
        snapshot_failure=snapshotter,
        retry_a=RetryIngredient("retry-a", "minimal-diagnostic-reset"),
        retry_b=RetryIngredient("retry-b", "fresh-context-validator-evidence"),
    )
    result = orchestrator.run(model_id=MODEL_ID, tasks=(_task(),))
    return result, store


def test_each_failed_attempt_becomes_one_fixture_with_three_separate_assets(tmp_path) -> None:
    result, store = _build_hard_failure_store(tmp_path)

    fixtures = tuple(record for record in store.records() if isinstance(record, FailureFixture))
    assert len(fixtures) == 3
    assert result.task_results[0].failure_snapshot_ids == tuple(
        fixture.failure_snapshot_id for fixture in fixtures
    )

    for fixture, stage in zip(fixtures, ("INITIAL", "RETRY_A", "RETRY_B"), strict=True):
        visible_sha = fixture.model_visible_asset_sha256
        forensic_sha = fixture.metadata["forensic_asset_sha256"]
        oracle_sha = fixture.metadata["oracle_asset_sha256"]
        assert len({visible_sha, forensic_sha, oracle_sha}) == 3

        visible = store.read_asset(visible_sha)
        forensic = store.read_asset(forensic_sha)
        oracle = store.read_asset(oracle_sha)

        assert visible["request_envelopes"][0]["messages"][0]["content"] == f"Test1B-v3 {stage}"
        assert forensic["raw_calls"][0]["response"]["message"]["thinking"] == (
            f"exposed-runtime-thinking-{stage}"
        )
        assert oracle["expected"] == {"answer": "B"}
        assert "expected" not in repr(visible)
        assert "score" not in repr(visible)

        assert fixture.metadata["attempt_stage"] == stage
        assert fixture.metadata["failure_subtypes"] == (f"SEMANTIC_FAIL:{stage}",)
        assert fixture.metadata["retry_ingredient_id"] == (
            None if stage == "INITIAL" else "retry-a" if stage == "RETRY_A" else "retry-b"
        )
        assert fixture.inference_profile["thinking_budget"] == 2048
        assert fixture.inference_profile["temperature"] == 0.35


def test_retry_failure_fixtures_form_exact_parent_state_chain(tmp_path) -> None:
    _, store = _build_hard_failure_store(tmp_path)
    fixtures = tuple(record for record in store.records() if isinstance(record, FailureFixture))
    initial, retry_a, retry_b = fixtures

    assert initial.parent_failure_snapshot_id is None
    assert initial.parent_state_hash is None
    assert retry_a.parent_failure_snapshot_id == initial.failure_snapshot_id
    assert retry_a.parent_state_hash == initial.state_hash
    assert retry_b.parent_failure_snapshot_id == retry_a.failure_snapshot_id
    assert retry_b.parent_state_hash == retry_a.state_hash


def test_replay_validation_covers_forensic_and_oracle_assets(tmp_path) -> None:
    _, store = _build_hard_failure_store(tmp_path)
    assert store.validate().ok is True

    first = next(record for record in store.records() if isinstance(record, FailureFixture))
    forensic_sha = first.metadata["forensic_asset_sha256"]
    (store.asset_root / f"{forensic_sha}.json").unlink()

    validation = store.validate()
    assert validation.ok is False
    assert forensic_sha in validation.missing_assets
