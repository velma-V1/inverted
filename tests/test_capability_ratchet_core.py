from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from inverted.capability_ratchet import (
    FailureFixture,
    Partition,
    PromotionState,
    ReplayMode,
    ReplayRecordType,
    ReplayRequest,
    ReplayResult,
    from_payload,
    to_payload,
)


def make_fixture(**changes: object) -> FailureFixture:
    values: dict[str, object] = {
        "failure_snapshot_id": "fail-001",
        "source_campaign_id": "v2-real",
        "source_trial_id": "ARITHMETIC:gate:000:candidate",
        "focus_observation_id": "obs-001",
        "focus_task_id": "arith-001",
        "batch_task_ids": (
            "arith-001",
            "arith-002",
            "arith-003",
            "arith-004",
            "arith-005",
        ),
        "family": "ARITHMETIC",
        "failure_classes": ("SEMANTIC_FAIL",),
        "source_model_id": "qwen3.5:9b-q8_0",
        "source_model_digest": "digest-1",
        "source_runtime": {"provider": "ollama", "version": "0.32.15"},
        "inference_profile": {"thinking_budget": 1024, "temperature": 1.0},
        "inference_seed": 42,
        "partition": Partition.DEVELOPMENT,
        "model_visible_asset_sha256": "a" * 64,
        "oracle_ref": "task-pool-v2:arith-001",
        "expected_contract": "answer_object",
        "source_evidence_refs": (
            "raw_calls.jsonl:12",
            "atomic_observations.jsonl:25",
        ),
        "metadata": {"stage": "gate"},
    }
    values.update(changes)
    return FailureFixture(**values)  # type: ignore[arg-type]


def test_failure_fixture_round_trip_and_frozen_record_type() -> None:
    fixture = make_fixture()

    assert from_payload(to_payload(fixture)) == fixture
    assert fixture.record_type is ReplayRecordType.FAILURE_FIXTURE
    with pytest.raises(FrozenInstanceError):
        fixture.record_type = ReplayRecordType.REPLAY_RESULT  # type: ignore[misc]
    with pytest.raises(TypeError):
        FailureFixture(  # type: ignore[call-arg]
            **{**fixture.__dict__, "record_type": ReplayRecordType.REPLAY_RESULT}
        )


def test_all_canonical_records_round_trip_with_explicit_types() -> None:
    fixture = make_fixture()
    request = ReplayRequest.for_exact(
        fixture,
        decision_id="D1",
        hypothesis_id="H-reproducibility",
        request_id="request-001",
    )
    result = ReplayResult(
        replay_result_id="result-001",
        replay_request_id=request.replay_request_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        mode=ReplayMode.EXACT,
        target_model_id=fixture.source_model_id,
        target_model_digest=fixture.source_model_digest,
        partition=fixture.partition,
        completed=True,
        semantic_pass=False,
        contract_pass=True,
        output_asset_sha256="b" * 64,
        raw_call_asset_sha256="c" * 64,
        failure_classes=("SEMANTIC_FAIL",),
    )

    for value, expected_type in (
        (request, ReplayRecordType.REPLAY_REQUEST),
        (result, ReplayRecordType.REPLAY_RESULT),
    ):
        payload = to_payload(value)
        assert payload["record_type"] == expected_type.value
        assert from_payload(payload) == value


@pytest.mark.parametrize(
    ("mode", "changed_dimensions"),
    [
        (ReplayMode.EXACT, ("temperature",)),
        (ReplayMode.CROSS_MODEL, ()),
        (ReplayMode.CROSS_MODEL, ("runtime",)),
    ],
)
def test_invalid_replay_mode_dimension_combinations_are_rejected(
    mode: ReplayMode, changed_dimensions: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError):
        ReplayRequest(
            replay_request_id="request-001",
            parent_failure_snapshot_id="fail-001",
            decision_id="D1",
            hypothesis_id="H1",
            mode=mode,
            target_model_id="other-model",
            target_model_digest="other-digest",
            partition=Partition.DEVELOPMENT,
            changed_dimensions=changed_dimensions,
        )


def test_counterfactual_requires_a_declared_changed_dimension() -> None:
    with pytest.raises(ValueError, match="COUNTERFACTUAL"):
        ReplayRequest(
            replay_request_id="request-001",
            parent_failure_snapshot_id="fail-001",
            decision_id="D4",
            hypothesis_id="H-context",
            mode=ReplayMode.COUNTERFACTUAL,
            target_model_id="qwen",
            target_model_digest="digest",
            partition=Partition.DEVELOPMENT,
        )


@pytest.mark.parametrize(
    ("serialized", "expected"),
    [
        ("HISTORICAL", Partition.HISTORICAL),
        ("DEVELOPMENT", Partition.DEVELOPMENT),
        ("TRAINING", Partition.TRAINING),
        ("FRESH", Partition.FRESH),
        ("SEALED", Partition.SEALED),
    ],
)
def test_partition_parsing(serialized: str, expected: Partition) -> None:
    payload = to_payload(make_fixture())
    payload["partition"] = serialized
    assert from_payload(payload).partition is expected


def test_unknown_partition_and_record_type_are_rejected() -> None:
    payload = to_payload(make_fixture())
    payload["partition"] = "dev-ish"
    with pytest.raises(ValueError):
        from_payload(payload)

    payload = to_payload(make_fixture())
    payload["record_type"] = "UNKNOWN"
    with pytest.raises(ValueError):
        from_payload(payload)


@pytest.mark.parametrize(
    "field",
    [
        "failure_snapshot_id",
        "source_campaign_id",
        "source_trial_id",
        "focus_observation_id",
        "focus_task_id",
        "source_model_id",
        "source_model_digest",
        "model_visible_asset_sha256",
        "oracle_ref",
        "expected_contract",
    ],
)
def test_failure_fixture_rejects_blank_required_ids(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        make_fixture(**{field: "  "})


@pytest.mark.parametrize(
    "field", ["replay_request_id", "parent_failure_snapshot_id", "decision_id", "hypothesis_id"]
)
def test_replay_request_rejects_blank_required_ids(field: str) -> None:
    values = {
        "replay_request_id": "request-001",
        "parent_failure_snapshot_id": "fail-001",
        "decision_id": "D1",
        "hypothesis_id": "H1",
        "mode": ReplayMode.EXACT,
        "target_model_id": "qwen",
        "target_model_digest": "digest",
        "partition": Partition.DEVELOPMENT,
    }
    values[field] = ""
    with pytest.raises(ValueError, match=field):
        ReplayRequest(**values)  # type: ignore[arg-type]


def test_fixture_rejects_invalid_focus_batch_and_hash() -> None:
    with pytest.raises(ValueError, match="batch_task_ids"):
        make_fixture(batch_task_ids=("arith-002",))
    with pytest.raises(ValueError, match="model_visible_asset_sha256"):
        make_fixture(model_visible_asset_sha256="not-a-sha256")


def test_enums_are_frozen_to_documented_values() -> None:
    assert tuple(member.value for member in ReplayMode) == (
        "EXACT",
        "COUNTERFACTUAL",
        "CROSS_MODEL",
    )
    assert tuple(member.value for member in PromotionState) == (
        "UNASSESSED",
        "MOVEMENT",
        "TIER_CANDIDATE",
        "CERTIFIED",
        "REJECTED",
    )
