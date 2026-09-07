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
        "state_hash": "9" * 64,
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
        parent_state_hash=fixture.state_hash,
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
        child_failure_snapshot_id="child-result-001",
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
            parent_state_hash="d" * 64,
            decision_id="D1",
            hypothesis_id="H1",
            expected_causal_implication="invalid combination test",
            mode=mode,
            source_model_id="qwen",
            source_model_digest="digest",
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
            parent_state_hash="d" * 64,
            decision_id="D4",
            hypothesis_id="H-context",
            expected_causal_implication="context change repairs failure",
            mode=ReplayMode.COUNTERFACTUAL,
            source_model_id="qwen",
            source_model_digest="digest",
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
    "field", ["replay_request_id", "parent_failure_snapshot_id", "decision_id", "hypothesis_id",
              "expected_causal_implication", "source_model_id", "source_model_digest"]
)
def test_replay_request_rejects_blank_required_ids(field: str) -> None:
    values = {
        "replay_request_id": "request-001",
        "parent_failure_snapshot_id": "fail-001",
        "parent_state_hash": "d" * 64,
        "decision_id": "D1",
        "hypothesis_id": "H1",
        "expected_causal_implication": "exact reproduction only",
        "mode": ReplayMode.EXACT,
        "source_model_id": "qwen",
        "source_model_digest": "digest",
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


def test_exact_request_rejects_overrides_and_target_model_change() -> None:
    fixture = make_fixture()
    with pytest.raises(ValueError, match="EXACT"):
        ReplayRequest(
            replay_request_id="request-exact-overrides",
            parent_failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            decision_id="D1",
            hypothesis_id="H1",
            expected_causal_implication="exact reproduction only",
            mode=ReplayMode.EXACT,
            source_model_id=fixture.source_model_id,
            source_model_digest=fixture.source_model_digest,
            target_model_id=fixture.source_model_id,
            target_model_digest=fixture.source_model_digest,
            partition=fixture.partition,
            overrides={"temperature": 0.2},
        )
    with pytest.raises(ValueError, match="EXACT"):
        ReplayRequest(
            replay_request_id="request-exact-model",
            parent_failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            decision_id="D1", hypothesis_id="H1",
            expected_causal_implication="exact reproduction only",
            mode=ReplayMode.EXACT,
            source_model_id=fixture.source_model_id,
            source_model_digest=fixture.source_model_digest,
            target_model_id="other-model",
            target_model_digest="other-digest",
            partition=fixture.partition,
        )


def test_counterfactual_overrides_must_match_declared_dimensions_and_source_model() -> None:
    fixture = make_fixture()
    with pytest.raises(ValueError, match="changed_dimensions"):
        ReplayRequest(
            replay_request_id="request-cf",
            parent_failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            decision_id="D2", hypothesis_id="H2",
            expected_causal_implication="temperature repairs the failure",
            mode=ReplayMode.COUNTERFACTUAL,
            source_model_id=fixture.source_model_id,
            source_model_digest=fixture.source_model_digest,
            target_model_id=fixture.source_model_id,
            target_model_digest=fixture.source_model_digest,
            partition=fixture.partition,
            changed_dimensions=("temperature",),
            overrides={"prompt": "changed"},
        )
    with pytest.raises(ValueError, match="COUNTERFACTUAL"):
        ReplayRequest(
            replay_request_id="request-cf-model",
            parent_failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            decision_id="D2", hypothesis_id="H2",
            expected_causal_implication="temperature repairs the failure",
            mode=ReplayMode.COUNTERFACTUAL,
            source_model_id=fixture.source_model_id,
            source_model_digest=fixture.source_model_digest,
            target_model_id="other-model",
            target_model_digest="other-digest",
            partition=fixture.partition,
            changed_dimensions=("temperature",),
            overrides={"temperature": 0.2},
        )


def test_replay_branch_requires_parent_state_and_expected_implication() -> None:
    fixture = make_fixture()
    request = ReplayRequest.for_exact(fixture, decision_id="D1", hypothesis_id="H1")
    assert request.parent_state_hash == fixture.state_hash
    assert request.expected_causal_implication
    payload = to_payload(request)
    assert payload["parent_state_hash"] == fixture.state_hash
    assert payload["expected_causal_implication"]


def test_failure_fixture_parent_id_and_state_hash_are_atomic() -> None:
    with pytest.raises(ValueError, match="parent"):
        make_fixture(parent_failure_snapshot_id="parent-1")
    with pytest.raises(ValueError, match="parent"):
        make_fixture(parent_state_hash="d" * 64)


def test_replay_result_failure_requires_child_snapshot_and_success_forbids_one() -> None:
    common = dict(
        replay_result_id="result-1", replay_request_id="request-1",
        parent_failure_snapshot_id="fail-1", parent_state_hash="d" * 64,
        mode=ReplayMode.EXACT, target_model_id="qwen", target_model_digest="digest",
        partition=Partition.DEVELOPMENT, output_asset_sha256="e" * 64,
        raw_call_asset_sha256="f" * 64,
    )
    with pytest.raises(ValueError, match="child_failure_snapshot_id"):
        ReplayResult(**common, completed=True, semantic_pass=False, contract_pass=True,
                     failure_classes=("SEMANTIC_FAIL",))
    with pytest.raises(ValueError, match="child_failure_snapshot_id"):
        ReplayResult(**common, completed=True, semantic_pass=True, contract_pass=True,
                     child_failure_snapshot_id="child-1")

def test_schema_rejects_mutable_non_json_values_and_non_string_mapping_keys() -> None:
    with pytest.raises(TypeError):
        make_fixture(metadata={"bad": {1, 2}})
    with pytest.raises(TypeError):
        make_fixture(metadata={1: "collision", "1": "other"})
    with pytest.raises(TypeError):
        make_fixture(failure_classes="SEMANTIC_FAIL")


def test_schema_deep_freezes_nested_json_and_rejects_non_boolean_result_flags() -> None:
    nested = {"items": [{"x": [1, 2]}]}
    fixture = make_fixture(metadata=nested)
    nested["items"][0]["x"].append(3)
    assert tuple(fixture.metadata["items"][0]["x"]) == (1, 2)
    with pytest.raises(TypeError, match="completed"):
        ReplayResult(
            replay_result_id="result-bool", replay_request_id="request-bool",
            parent_failure_snapshot_id="fail-1", parent_state_hash="d" * 64,
            mode=ReplayMode.EXACT, target_model_id="qwen", target_model_digest="digest",
            partition=Partition.DEVELOPMENT, completed="yes",
            semantic_pass=True, contract_pass=True,
            output_asset_sha256="e" * 64, raw_call_asset_sha256="f" * 64,
        )

def test_counterfactual_requires_concrete_override_for_every_declared_dimension() -> None:
    fixture = make_fixture()
    with pytest.raises(ValueError, match="changed_dimensions"):
        ReplayRequest(
            replay_request_id="request-cf-empty", parent_failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash, decision_id="D2", hypothesis_id="H2",
            expected_causal_implication="temperature repairs failure", mode=ReplayMode.COUNTERFACTUAL,
            source_model_id=fixture.source_model_id, source_model_digest=fixture.source_model_digest,
            target_model_id=fixture.source_model_id, target_model_digest=fixture.source_model_digest,
            partition=fixture.partition, changed_dimensions=("temperature",), overrides={},
        )


def test_counterfactual_cannot_mutate_frozen_provenance_dimensions() -> None:
    fixture = make_fixture()
    for dimension in ("source_model_id", "source_model_digest", "partition", "parent_state_hash", "state_hash"):
        with pytest.raises(ValueError, match="immutable"):
            ReplayRequest(
                replay_request_id=f"request-{dimension}", parent_failure_snapshot_id=fixture.failure_snapshot_id,
                parent_state_hash=fixture.state_hash, decision_id="D2", hypothesis_id="H2",
                expected_causal_implication="invalid provenance intervention", mode=ReplayMode.COUNTERFACTUAL,
                source_model_id=fixture.source_model_id, source_model_digest=fixture.source_model_digest,
                target_model_id=fixture.source_model_id, target_model_digest=fixture.source_model_digest,
                partition=fixture.partition, changed_dimensions=(dimension,), overrides={dimension: "changed"},
            )

def test_failed_replay_child_snapshot_cannot_equal_parent() -> None:
    with pytest.raises(ValueError, match="child_failure_snapshot_id"):
        ReplayResult(
            replay_result_id="result-cycle", replay_request_id="request-cycle",
            parent_failure_snapshot_id="fail-cycle", parent_state_hash="d" * 64,
            mode=ReplayMode.EXACT, target_model_id="qwen", target_model_digest="digest",
            partition=Partition.DEVELOPMENT, completed=True, semantic_pass=False, contract_pass=True,
            output_asset_sha256="e" * 64, raw_call_asset_sha256="f" * 64,
            failure_classes=("SEMANTIC_FAIL",), child_failure_snapshot_id="fail-cycle",
        )

def test_replay_request_always_has_stable_branch_identity() -> None:
    fixture = make_fixture()
    first = ReplayRequest.for_exact(fixture, decision_id="D1", hypothesis_id="H1")
    second = ReplayRequest.for_exact(fixture, decision_id="D1", hypothesis_id="H1")
    assert first.intervention_id and first.counterfactual_group_id
    assert first.intervention_id == second.intervention_id
    assert first.counterfactual_group_id == second.counterfactual_group_id
    payload = to_payload(first)
    assert payload["intervention_id"] == first.intervention_id
    assert payload["counterfactual_group_id"] == first.counterfactual_group_id


def test_blank_or_non_string_explicit_branch_ids_are_rejected() -> None:
    fixture = make_fixture()
    for field, value in (("intervention_id", ""), ("counterfactual_group_id", 7)):
        kwargs = {field: value}
        with pytest.raises((TypeError, ValueError), match=field):
            ReplayRequest(
                replay_request_id=f"request-{field}", parent_failure_snapshot_id=fixture.failure_snapshot_id,
                parent_state_hash=fixture.state_hash, decision_id="D2", hypothesis_id="H2",
                expected_causal_implication="temperature repairs failure", mode=ReplayMode.COUNTERFACTUAL,
                source_model_id=fixture.source_model_id, source_model_digest=fixture.source_model_digest,
                target_model_id=fixture.source_model_id, target_model_digest=fixture.source_model_digest,
                partition=fixture.partition, changed_dimensions=("temperature",), overrides={"temperature": 0.2},
                **kwargs,
            )

def test_non_cross_model_result_rejects_adapter_changes() -> None:
    with pytest.raises(ValueError, match="adapter_changes"):
        ReplayResult(
            replay_result_id="result-adapter", replay_request_id="request-adapter",
            parent_failure_snapshot_id="fail-adapter", parent_state_hash="d" * 64,
            mode=ReplayMode.EXACT, target_model_id="qwen", target_model_digest="digest",
            partition=Partition.DEVELOPMENT, completed=True, semantic_pass=True, contract_pass=True,
            output_asset_sha256="e" * 64, raw_call_asset_sha256="f" * 64,
            adapter_changes={"runtime": "translated"},
        )


def test_non_finite_numbers_are_rejected_from_canonical_payloads() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(TypeError, match="finite"):
            make_fixture(metadata={"value": value})