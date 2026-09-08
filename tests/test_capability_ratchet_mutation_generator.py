from __future__ import annotations

from dataclasses import replace

import pytest

from inverted.capability_ratchet.core import FailureFixture, Partition
from inverted.capability_ratchet.mutation_core import MutationAxis, MutationDirection, MutationSpec
from inverted.capability_ratchet.mutation_generator import (
    MutationGenerator,
    MutationTemplate,
    semantic_contract_hash,
)
from inverted.capability_ratchet.replay_store import ReplayStore


def _source(store: ReplayStore, *, partition: Partition = Partition.DEVELOPMENT) -> FailureFixture:
    visible = store.put_asset({"seed": "source"})
    fixture = FailureFixture(
        failure_snapshot_id="failure-root",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="observation",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"temperature": 0},
        inference_seed=11,
        partition=partition,
        model_visible_asset_sha256=visible,
        state_hash="a" * 64,
        oracle_ref="oracle",
        expected_contract="answer",
        source_evidence_refs=("source:1",),
    )
    store.append(fixture)
    return fixture


def _template(store: ReplayStore, *, partition: Partition = Partition.DEVELOPMENT) -> tuple[FailureFixture, MutationTemplate]:
    source = _source(store, partition=partition)
    model_visible = {
        "task": {
            "number": 2,
            "dependency_depth": 2,
            "requirements": ["r1"],
            "action_space": ["a", "b"],
            "critical_information_position": "front",
            "distractors": [],
            "evidence_state": "sufficient",
            "authority_state": "owner",
            "reversibility_consequence": "reversible",
            "tool_available": True,
            "context_pressure": 0,
            "order": ["a", "b"],
            "recovery_opportunity": False,
        }
    }
    oracle = {"answer": 4}
    semantic_contract = {"type": "object", "required": ["answer"]}
    operator_state = {
        "mechanism_id": "mechanism-1",
        MutationAxis.NUMBERS_ENTITIES.value: {
            "visible_path": ["task", "number"],
            "oracle_path": ["answer"],
            "requires_oracle": True,
        },
        MutationAxis.DEPENDENCY_DEPTH.value: {"visible_path": ["task", "dependency_depth"]},
        MutationAxis.REQUIREMENT_COUNT.value: {"visible_path": ["task", "requirements"]},
        MutationAxis.ACTION_SPACE_SIZE.value: {"visible_path": ["task", "action_space"]},
        MutationAxis.CRITICAL_INFORMATION_POSITION.value: {
            "visible_path": ["task", "critical_information_position"]
        },
        MutationAxis.DISTRACTORS.value: {"visible_path": ["task", "distractors"]},
        MutationAxis.EVIDENCE_STATE.value: {"visible_path": ["task", "evidence_state"]},
        MutationAxis.AUTHORITY_STATE.value: {"visible_path": ["task", "authority_state"]},
        MutationAxis.REVERSIBILITY_CONSEQUENCE.value: {
            "visible_path": ["task", "reversibility_consequence"]
        },
        MutationAxis.TOOL_AVAILABILITY.value: {"visible_path": ["task", "tool_available"]},
        MutationAxis.CONTEXT_PRESSURE.value: {"visible_path": ["task", "context_pressure"]},
        MutationAxis.ORDER.value: {"visible_path": ["task", "order"]},
        MutationAxis.RECOVERY_OPPORTUNITY.value: {
            "visible_path": ["task", "recovery_opportunity"]
        },
    }
    return source, MutationTemplate(
        source_failure_snapshot_id=source.failure_snapshot_id,
        structural_region_id="planning/dependency",
        semantic_contract=semantic_contract,
        model_visible_template=model_visible,
        oracle_template=oracle,
        allowed_axes=tuple(MutationAxis),
        operator_state=operator_state,
    )


def _spec(axis: MutationAxis, value, *, direction: MutationDirection = MutationDirection.LATERAL) -> MutationSpec:
    return MutationSpec(
        axis=axis,
        direction=direction,
        value=value,
        structural_region_id="planning/dependency",
        decision_id="D12",
    )


def _read_path(payload, path: list[str]):
    current = payload
    for part in path:
        current = current[part]
    return current


def test_semantic_contract_hash_is_canonical() -> None:
    assert semantic_contract_hash({"b": [2, 1], "a": 3}) == semantic_contract_hash(
        {"a": 3, "b": [2, 1]}
    )


def test_generator_rejects_axis_not_authorized_by_template(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    _, template = _template(store)
    restricted = replace(template, allowed_axes=(MutationAxis.DEPENDENCY_DEPTH,))

    with pytest.raises(ValueError, match="not authorized"):
        MutationGenerator(store).generate(
            restricted, _spec(MutationAxis.DISTRACTORS, ["noise"])
        )


def test_semantic_mutation_requires_deterministic_oracle_transform(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    _, template = _template(store)

    with pytest.raises(ValueError, match="oracle"):
        MutationGenerator(store).generate(
            template, _spec(MutationAxis.NUMBERS_ENTITIES, {"visible": 3})
        )

    fixture = MutationGenerator(store).generate(
        template,
        _spec(MutationAxis.NUMBERS_ENTITIES, {"visible": 3, "oracle": 6}),
    )
    assert store.read_asset(fixture.model_visible_asset_sha256)["task"]["number"] == 3
    assert store.read_asset(fixture.oracle_asset_sha256)["answer"] == 6


def test_generator_rejects_fresh_and_sealed_synthetic_mutation(tmp_path) -> None:
    for partition in (Partition.FRESH, Partition.SEALED):
        store = ReplayStore(tmp_path / partition.value.lower())
        _, template = _template(store, partition=partition)
        with pytest.raises(ValueError, match="FRESH|SEALED"):
            MutationGenerator(store).generate(
                template,
                _spec(MutationAxis.DEPENDENCY_DEPTH, 3, direction=MutationDirection.HARDER),
            )


def test_generator_rejects_provenance_mutation_attempt(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    _, template = _template(store)
    with pytest.raises(ValueError, match="provenance"):
        MutationGenerator(store).generate(
            template,
            _spec(
                MutationAxis.DISTRACTORS,
                {"source_model_id": "different-model", "visible": ["noise"]},
            ),
        )


def test_generate_many_rejects_duplicate_specs_in_one_schedule(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    _, template = _template(store)
    spec = _spec(MutationAxis.DEPENDENCY_DEPTH, 3)
    with pytest.raises(ValueError, match="duplicate"):
        MutationGenerator(store).generate_many(template, (spec, spec))


@pytest.mark.parametrize(
    ("axis", "value", "path", "expected"),
    (
        (MutationAxis.DEPENDENCY_DEPTH, 4, ["task", "dependency_depth"], 4),
        (MutationAxis.REQUIREMENT_COUNT, ["r1", "r2"], ["task", "requirements"], ["r1", "r2"]),
        (MutationAxis.DISTRACTORS, ["noise"], ["task", "distractors"], ["noise"]),
        (MutationAxis.CRITICAL_INFORMATION_POSITION, "tail", ["task", "critical_information_position"], "tail"),
        (MutationAxis.AUTHORITY_STATE, "delegate", ["task", "authority_state"], "delegate"),
        (MutationAxis.TOOL_AVAILABILITY, False, ["task", "tool_available"], False),
        (MutationAxis.CONTEXT_PRESSURE, 4096, ["task", "context_pressure"], 4096),
        (MutationAxis.ORDER, ["b", "a"], ["task", "order"], ["b", "a"]),
        (MutationAxis.RECOVERY_OPPORTUNITY, True, ["task", "recovery_opportunity"], True),
    ),
)
def test_template_bound_operators_write_exact_canonical_visible_assets(
    tmp_path, axis, value, path, expected
) -> None:
    store = ReplayStore(tmp_path)
    _, template = _template(store)
    fixture = MutationGenerator(store).generate(template, _spec(axis, value))
    visible = store.read_asset(fixture.model_visible_asset_sha256)
    assert _read_path(visible, path) == expected
    assert fixture.semantic_contract_hash == semantic_contract_hash(template.semantic_contract)
    assert store.validate().ok


def test_generation_is_byte_identical_and_registry_idempotent(tmp_path) -> None:
    store = ReplayStore(tmp_path)
    _, template = _template(store)
    spec = _spec(MutationAxis.DEPENDENCY_DEPTH, 4, direction=MutationDirection.HARDER)
    generator = MutationGenerator(store)

    first = generator.generate(template, spec)
    registry_before = store.registry_path.read_bytes()
    second = generator.generate(template, spec)

    assert first.mutation_fixture_id == second.mutation_fixture_id
    assert first.model_visible_asset_sha256 == second.model_visible_asset_sha256
    assert first.oracle_asset_sha256 == second.oracle_asset_sha256
    assert first.record_id == second.record_id
    assert store.registry_path.read_bytes() == registry_before
    assert len([row for row in store.records() if getattr(row, "record_type", None).value == "MUTATION_FIXTURE"]) == 1
