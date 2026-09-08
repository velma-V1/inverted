from __future__ import annotations

import json

import pytest

from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    InterventionDefinition,
    InterventionKind,
    MechanismRole,
)
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.core import (
    FailureFixture,
    MechanismLabel,
    Partition,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
)
from inverted.capability_ratchet.replay import ReplayExecutor
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.surface_core import SurfaceAxis, SurfacePoint, SurfaceStudy
from inverted.capability_ratchet.surface_interventions import (
    SurfaceInterventionCompiler,
    semantic_contract_hash,
)


STATE = "a" * 64


class FakeAdapter:
    def runtime_provenance(self):
        return {"provider": "fake", "model": "model", "model_digest": "digest"}

    def execute_fixture(self, fixture, visible_payload, request):
        raise AssertionError("Task-5 compilation tests must not execute a model")


def _seed(
    tmp_path,
    *,
    kind=InterventionKind.COGNITION,
    think=True,
    budget=1024,
    temperature=1.0,
    base_budget=2048,
    envelope_count=1,
):
    replay = ReplayStore(tmp_path / "replay")
    messages = [
        {"role": "system", "content": "Follow the contract."},
        {"role": "user", "content": "A must happen before B. Return the next valid step."},
    ]
    first_envelope = {
        "model": "model", "stream": False, "think": think,
        "options": {"seed": 7, "temperature": temperature, "num_predict": budget},
        "messages": messages,
    }
    envelopes = [first_envelope]
    for _ in range(1, envelope_count):
        envelopes.append({
            "model": "model", "stream": False, "think": False,
            "options": {"seed": 7, "temperature": 0.7, "num_predict": 768},
            "messages": [{"role": "user", "content": "Finalize from the prior state."}],
        })
    visible_payload = {"request_envelopes": envelopes}
    visible = replay.put_asset(visible_payload)
    fixture = FailureFixture(
        failure_snapshot_id="failure-surface", source_campaign_id="campaign",
        source_trial_id="trial", focus_observation_id="obs", focus_task_id="task",
        batch_task_ids=("task",), family="PLANNING_DEPENDENCIES",
        failure_classes=("SEMANTIC_FAIL",), source_model_id="model",
        source_model_digest="digest", source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": budget if think else 0, "temperature": temperature},
        inference_seed=7, partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible, state_hash=STATE,
        oracle_ref="oracle", expected_contract="answer object",
        source_evidence_refs=("raw:1",),
    )
    replay.append(fixture)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=(DivergenceClass.INSUFFICIENT_REASONING if kind is InterventionKind.COGNITION else DivergenceClass.MISSING_DEPENDENCY),
            observable_path="focus.semantic_pass", event_index=0,
            evidence_refs=("forensic:1",), confidence=0.9,
        ),
        owner_candidate=ArchitectureOwner.MODEL,
        claim="surface mechanism", expected_if_true="surface point changes outcome",
        falsifier="surface point does not change outcome",
    )
    causal.append_hypothesis(hypothesis)
    if kind is InterventionKind.COGNITION:
        dimensions = (
            "request_envelopes.0.think",
            "request_envelopes.0.options.num_predict",
        )
        overrides = {dimensions[0]: True, dimensions[1]: base_budget}
    else:
        dimensions = ("request_envelopes.0.messages.1.content",)
        overrides = {dimensions[0]: "DEPENDENCY STATE\nA must happen before B. Return the next valid step."}
    base = InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        kind=kind,
        label="base mechanism",
        changed_dimensions=dimensions,
        overrides=overrides,
        expected_causal_implication="base mechanism repairs the failure",
        projected_physical_calls=1,
    )
    causal.register_intervention(base)
    request = ReplayRequest(
        replay_request_id="base-request", failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id, parent_state_hash=fixture.state_hash,
        decision_id="D3", hypothesis_id=hypothesis.hypothesis_id,
        expected_causal_implication=base.expected_causal_implication,
        mode=ReplayMode.COUNTERFACTUAL, source_model_id="model", source_model_digest="digest",
        target_model_id="model", target_model_digest="digest", partition=fixture.partition,
        changed_dimensions=base.changed_dimensions, intervention_id=base.intervention_id,
        overrides=base.overrides,
    )
    replay.append(request)
    output = replay.put_asset({"answer": "B"})
    raw = replay.put_asset({"raw_calls": [{"request": visible_payload["request_envelopes"][0]}]})
    result = ReplayResult(
        replay_result_id="base-result", replay_request_id=request.replay_request_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash, mode=request.mode,
        target_model_id="model", target_model_digest="digest", partition=fixture.partition,
        completed=True, semantic_pass=True, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
    )
    replay.append(result)
    label = MechanismLabel(
        mechanism_label_id="surface-mechanism-label",
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        mechanism_id="mechanism-surface", hypothesis_id=hypothesis.hypothesis_id,
        intervention_ids=(base.intervention_id,), role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(result.replay_result_id,), confidence=0.9,
    )
    replay.append(label)
    assert replay.validate().ok
    return fixture, replay, causal, hypothesis, base, label, visible_payload


def _study(fixture, label, axis, values):
    return SurfaceStudy.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        mechanism_id=label.mechanism_id,
        parent_state_hash=fixture.state_hash,
        partition=fixture.partition,
        promotion_state="MOVEMENT",
        decision_id="D3" if axis in {SurfaceAxis.REASONING_BUDGET, SurfaceAxis.TEMPERATURE} else "D5",
        axes=(axis,),
        axis_values={axis.value: tuple(values)},
    )


def _compile(tmp_path, *, axis, value, values, **seed_kwargs):
    fixture, replay, causal, hypothesis, base, label, visible = _seed(tmp_path, **seed_kwargs)
    study = _study(fixture, label, axis, values)
    point = SurfacePoint.create(study=study, axis=axis, value=value, decision_id=study.decision_id)
    compiler = SurfaceInterventionCompiler(replay, causal)
    intervention, request = compiler.compile_point(
        study, point, request_id="surface-request", decision_id=study.decision_id,
    )
    return fixture, replay, causal, base, visible, intervention, request


def test_semantic_contract_hash_ignores_representation_wrapper_only() -> None:
    payload = "A must happen before B. Return the next valid step."
    wrapped = json.dumps({"representation": "FIELDS", "semantic_payload": payload}, sort_keys=True)
    assert semantic_contract_hash(payload) == semantic_contract_hash(wrapped)
    changed = json.dumps({"representation": "FIELDS", "semantic_payload": payload + " Extra."}, sort_keys=True)
    assert semantic_contract_hash(payload) != semantic_contract_hash(changed)


def test_reasoning_budget_changes_only_num_predict_when_thinking_is_already_active(tmp_path) -> None:
    fixture, replay, _, _, original, intervention, request = _compile(
        tmp_path, axis=SurfaceAxis.REASONING_BUDGET, value=512,
        values=(512, 1024, 2048), think=True, budget=1024, base_budget=2048,
    )
    assert intervention.kind is InterventionKind.COGNITION
    assert intervention.changed_dimensions == ("request_envelopes.0.options.num_predict",)
    assert dict(intervention.overrides) == {"request_envelopes.0.options.num_predict": 512}
    plan = ReplayExecutor(replay, {"model": FakeAdapter()}).plan(request)
    assert plan.changed_values == {"request_envelopes.0.options.num_predict": (1024, 512)}
    assert original["request_envelopes"][0]["options"]["temperature"] == 1.0


def test_direct_to_thinking_transition_declares_only_required_compatibility_leaves(tmp_path) -> None:
    _, replay, _, _, _, intervention, request = _compile(
        tmp_path, axis=SurfaceAxis.REASONING_BUDGET, value=512,
        values=(0, 512, 1024), think=False, budget=768, base_budget=1024,
    )
    assert intervention.kind is InterventionKind.COGNITION
    assert set(intervention.changed_dimensions) == {
        "request_envelopes.0.think",
        "request_envelopes.0.options.num_predict",
    }
    assert "direct-to-thinking" in intervention.label
    plan = ReplayExecutor(replay, {"model": FakeAdapter()}).plan(request)
    assert plan.changed_values["request_envelopes.0.think"] == (False, True)
    assert plan.changed_values["request_envelopes.0.options.num_predict"] == (768, 512)


def test_temperature_point_changes_only_temperature_after_cognition_is_active(tmp_path) -> None:
    _, replay, _, _, _, intervention, request = _compile(
        tmp_path, axis=SurfaceAxis.TEMPERATURE, value=0.6,
        values=(0.6, 0.8, 1.0), think=True, budget=1024, base_budget=1024,
    )
    assert intervention.changed_dimensions == ("request_envelopes.0.options.temperature",)
    plan = ReplayExecutor(replay, {"model": FakeAdapter()}).plan(request)
    assert plan.changed_values == {"request_envelopes.0.options.temperature": (1.0, 0.6)}


def test_representation_only_point_preserves_semantic_contract_hash(tmp_path) -> None:
    _, replay, _, base, _, intervention, request = _compile(
        tmp_path, axis=SurfaceAxis.REPRESENTATION, value="FIELDS",
        values=("PROSE", "FIELDS"), kind=InterventionKind.REPRESENTATION,
    )
    path = "request_envelopes.0.messages.1.content"
    baseline = dict(base.overrides)[path]
    represented = dict(intervention.overrides)[path]
    assert semantic_contract_hash(baseline) == semantic_contract_hash(represented)
    assert json.loads(represented)["representation"] == "FIELDS"
    assert intervention.changed_dimensions == (path,)
    plan = ReplayExecutor(replay, {"model": FakeAdapter()}).plan(request)
    assert path in plan.changed_values


def test_unrecognized_representation_is_rejected_before_replay_request(tmp_path) -> None:
    fixture, replay, causal, _, _, label, _ = _seed(tmp_path, kind=InterventionKind.REPRESENTATION)
    study = _study(fixture, label, SurfaceAxis.REPRESENTATION, ("PROSE", "ALIEN"))
    point = SurfacePoint.create(
        study=study, axis=SurfaceAxis.REPRESENTATION, value="ALIEN", decision_id="D5",
    )
    with pytest.raises(ValueError, match="representation"):
        SurfaceInterventionCompiler(replay, causal).compile_point(
            study, point, request_id="bad", decision_id="D5",
        )


def _effective_messages(base, visible):
    rows = [dict(message) for message in visible["request_envelopes"][0]["messages"]]
    path = "request_envelopes.0.messages.1.content"
    if path in base.overrides:
        rows[1]["content"] = dict(base.overrides)[path]
    return rows


def test_order_point_reverses_message_order_with_same_semantic_contract(tmp_path) -> None:
    _, replay, _, base, visible, intervention, request = _compile(
        tmp_path, axis=SurfaceAxis.ORDER, value="REVERSE",
        values=("BASE", "REVERSE"), kind=InterventionKind.REPRESENTATION,
    )
    baseline = _effective_messages(base, visible)
    assert intervention.changed_dimensions == ("request_envelopes.0.messages",)
    reordered = dict(intervention.overrides)["request_envelopes.0.messages"]
    assert [dict(row) for row in reordered] == list(reversed(baseline))
    assert semantic_contract_hash(baseline) == semantic_contract_hash(reordered)
    assert "request_envelopes.0.messages" in ReplayExecutor(replay, {"model": FakeAdapter()}).plan(request).changed_values


def test_placement_point_moves_mechanism_message_without_semantic_change(tmp_path) -> None:
    _, replay, _, base, visible, intervention, request = _compile(
        tmp_path, axis=SurfaceAxis.PLACEMENT, value="FRONT",
        values=("BASE", "FRONT", "END"), kind=InterventionKind.REPRESENTATION,
    )
    baseline = _effective_messages(base, visible)
    placed = dict(intervention.overrides)["request_envelopes.0.messages"]
    assert intervention.changed_dimensions == ("request_envelopes.0.messages",)
    assert placed[0]["content"] == baseline[1]["content"]
    assert semantic_contract_hash(baseline) == semantic_contract_hash(placed)
    assert "request_envelopes.0.messages" in ReplayExecutor(replay, {"model": FakeAdapter()}).plan(request).changed_values


def test_recurrence_point_repeats_only_the_registered_mechanism_message(tmp_path) -> None:
    _, replay, _, base, visible, intervention, request = _compile(
        tmp_path, axis=SurfaceAxis.RECURRENCE, value=2,
        values=(1, 2, 3), kind=InterventionKind.DELIVERY,
    )
    baseline = _effective_messages(base, visible)
    repeated = dict(intervention.overrides)["request_envelopes.0.messages"]
    assert intervention.changed_dimensions == ("request_envelopes.0.messages",)
    assert repeated.count(baseline[1]) == 2
    assert len(repeated) == len(baseline) + 1
    assert "request_envelopes.0.messages" in ReplayExecutor(replay, {"model": FakeAdapter()}).plan(request).changed_values


def test_timing_point_moves_mechanism_message_to_later_envelope(tmp_path) -> None:
    _, replay, _, base, visible, intervention, request = _compile(
        tmp_path, axis=SurfaceAxis.TIMING, value="LATE",
        values=("EARLY", "LATE"), kind=InterventionKind.DELIVERY,
        envelope_count=2,
    )
    baseline = _effective_messages(base, visible)
    assert set(intervention.changed_dimensions) == {
        "request_envelopes.0.messages",
        "request_envelopes.1.messages",
    }
    overrides = dict(intervention.overrides)
    first = overrides["request_envelopes.0.messages"]
    second = overrides["request_envelopes.1.messages"]
    assert baseline[1] not in [dict(row) for row in first]
    assert dict(second[-1]) == baseline[1]
    changed = ReplayExecutor(replay, {"model": FakeAdapter()}).plan(request).changed_values
    assert set(changed) == set(intervention.changed_dimensions)
