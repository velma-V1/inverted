from __future__ import annotations

import pytest

from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner, CausalHypothesis, DivergenceClass, FirstDivergence,
    InterventionDefinition, InterventionKind, MechanismRole,
)
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.core import (
    FailureFixture, MechanismLabel, Partition, PromotionEvent, PromotionState,
    ReplayMode, ReplayRequest, ReplayResult,
)
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.surface_core import SurfaceAxis, SurfacePoint, SurfaceStudy
from inverted.capability_ratchet.surface_evidence import SurfaceEvidenceCompiler
from inverted.capability_ratchet.surface_interventions import SurfaceInterventionCompiler
from inverted.capability_ratchet.surface_planner import SurfacePlanner
from inverted.capability_ratchet.surface_store import SurfaceEvidenceStore

STATE = "a" * 64


def _seed_family(tmp_path, *, kind: InterventionKind, envelope_count: int = 1, events=()):
    replay = ReplayStore(tmp_path / "replay")
    user = "A must happen before B. Return the next valid step."
    envelopes = [{
        "model": "model", "stream": False, "think": False,
        "options": {"seed": 7, "temperature": 0.7, "num_predict": 768},
        "messages": [
            {"role": "system", "content": "Follow the contract."},
            {"role": "user", "content": user},
        ],
    }]
    for _ in range(1, envelope_count):
        envelopes.append({
            "model": "model", "stream": False, "think": False,
            "options": {"seed": 7, "temperature": 0.7, "num_predict": 768},
            "messages": [{"role": "user", "content": "Finalize from the prior state."}],
        })
    visible_payload = {"request_envelopes": envelopes}
    visible = replay.put_asset(visible_payload)
    fixture = FailureFixture(
        failure_snapshot_id="failure-surface-gap", source_campaign_id="campaign",
        source_trial_id="trial", focus_observation_id="obs", focus_task_id="task",
        batch_task_ids=("task",), family="PLANNING_DEPENDENCIES",
        failure_classes=("SEMANTIC_FAIL",), source_model_id="model",
        source_model_digest="digest", source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": 0, "temperature": 0.7},
        inference_seed=7, partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible, state_hash=STATE,
        oracle_ref="oracle", expected_contract="answer object",
        source_evidence_refs=("raw:1",),
        metadata={"surface_delivery_events": list(events)},
    )
    replay.append(fixture)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    divergence = (
        DivergenceClass.INSUFFICIENT_REASONING
        if kind is InterventionKind.COGNITION else DivergenceClass.MISSING_DEPENDENCY
    )
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=divergence, observable_path="focus.semantic_pass",
            event_index=0, evidence_refs=("forensic:1",), confidence=0.9,
        ),
        owner_candidate=ArchitectureOwner.MODEL, claim="surface mechanism",
        expected_if_true="surface point changes outcome",
        falsifier="surface point does not change outcome",
    )
    causal.append_hypothesis(hypothesis)
    if kind is InterventionKind.COGNITION:
        dimensions = ("request_envelopes.0.think", "request_envelopes.0.options.num_predict")
        overrides = {dimensions[0]: True, dimensions[1]: 512}
    else:
        path = "request_envelopes.0.messages.1.content"
        dimensions = (path,)
        overrides = {path: user + "\n\nDEPENDENCY STATE\nA must happen before B."}
    base = InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash, kind=kind, label="base mechanism",
        changed_dimensions=dimensions, overrides=overrides,
        expected_causal_implication="base mechanism repairs the failure",
        projected_physical_calls=envelope_count,
    )
    causal.register_intervention(base)
    request = ReplayRequest(
        replay_request_id="base-request", failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash, decision_id="D5",
        hypothesis_id=hypothesis.hypothesis_id,
        expected_causal_implication=base.expected_causal_implication,
        mode=ReplayMode.COUNTERFACTUAL, source_model_id="model", source_model_digest="digest",
        target_model_id="model", target_model_digest="digest", partition=fixture.partition,
        changed_dimensions=base.changed_dimensions, intervention_id=base.intervention_id,
        overrides=base.overrides,
    )
    replay.append(request)
    output = replay.put_asset({"answer": "B"})
    raw = replay.put_asset({"raw_calls": [{"request": envelope} for envelope in envelopes]})
    result = ReplayResult(
        replay_result_id="base-result", replay_request_id=request.replay_request_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash, mode=request.mode,
        target_model_id="model", target_model_digest="digest", partition=fixture.partition,
        completed=True, semantic_pass=True, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
        metrics={"physical_calls": envelope_count},
    )
    replay.append(result)
    label = MechanismLabel(
        mechanism_label_id="surface-mechanism-label",
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash, mechanism_id="mechanism-surface",
        hypothesis_id=hypothesis.hypothesis_id, intervention_ids=(base.intervention_id,),
        role=MechanismRole.REQUIRED, evidence_replay_result_ids=(result.replay_result_id,),
        confidence=0.9,
    )
    replay.append(label)
    replay.append(PromotionEvent(
        promotion_event_id="surface-movement", failure_snapshot_id=fixture.failure_snapshot_id,
        mechanism_id=label.mechanism_id, from_state=PromotionState.UNASSESSED,
        to_state=PromotionState.MOVEMENT,
        reason="same-state base mechanism repaired the failure",
        evidence_replay_result_ids=(result.replay_result_id,), partition=fixture.partition,
    ))
    assert replay.validate().ok
    return fixture, replay, causal, base, label, visible_payload


def _study(fixture, label, axis, values):
    return SurfaceStudy.create(
        failure_snapshot_id=fixture.failure_snapshot_id, mechanism_id=label.mechanism_id,
        parent_state_hash=fixture.state_hash, partition=fixture.partition,
        promotion_state=PromotionState.MOVEMENT, decision_id="D5", axes=(axis,),
        axis_values={axis.value: tuple(values)},
    )


def test_context_dose_and_position_compile_from_registered_additive_context(tmp_path) -> None:
    fixture, replay, causal, base, label, _ = _seed_family(tmp_path, kind=InterventionKind.CONTEXT)
    compiler = SurfaceInterventionCompiler(replay, causal)
    dose_study = _study(fixture, label, SurfaceAxis.CONTEXT_DOSE, (0.5, 1.0))
    dose = SurfacePoint.create(study=dose_study, axis=SurfaceAxis.CONTEXT_DOSE, value=0.5, decision_id="D5")
    intervention, _ = compiler.compile_point(dose_study, dose, request_id="dose", decision_id="D5")
    path = base.changed_dimensions[0]
    assert intervention.kind is InterventionKind.CONTEXT
    assert path in intervention.changed_dimensions
    assert len(str(intervention.overrides[path])) < len(str(base.overrides[path]))

    position_study = _study(fixture, label, SurfaceAxis.CONTEXT_POSITION, ("INLINE", "FRONT", "END"))
    front = SurfacePoint.create(study=position_study, axis=SurfaceAxis.CONTEXT_POSITION, value="FRONT", decision_id="D5")
    positioned, _ = compiler.compile_point(position_study, front, request_id="front", decision_id="D5")
    assert positioned.changed_dimensions == ("request_envelopes.0.messages",)


def test_progressive_delivery_is_available_only_with_registered_state_transition(tmp_path) -> None:
    fixture, replay, causal, _, label, _ = _seed_family(tmp_path / "none", kind=InterventionKind.CONTEXT, envelope_count=2)
    study = _study(fixture, label, SurfaceAxis.DELIVERY_MODE, ("STATIC", "PROGRESSIVE"))
    point = SurfacePoint.create(study=study, axis=SurfaceAxis.DELIVERY_MODE, value="PROGRESSIVE", decision_id="D5")
    with pytest.raises(ValueError, match="state transition"):
        SurfaceInterventionCompiler(replay, causal).compile_point(study, point, request_id="bad-progressive", decision_id="D5")

    fixture, replay, causal, _, label, _ = _seed_family(
        tmp_path / "yes", kind=InterventionKind.CONTEXT, envelope_count=2,
        events=({"event": "STATE_TRANSITION", "envelope_index": 1},),
    )
    study = _study(fixture, label, SurfaceAxis.DELIVERY_MODE, ("STATIC", "PROGRESSIVE"))
    point = SurfacePoint.create(study=study, axis=SurfaceAxis.DELIVERY_MODE, value="PROGRESSIVE", decision_id="D5")
    intervention, _ = SurfaceInterventionCompiler(replay, causal).compile_point(
        study, point, request_id="progressive", decision_id="D5"
    )
    assert len(intervention.changed_dimensions) == 2


def test_trigger_mode_is_available_only_with_matching_observable_trigger(tmp_path) -> None:
    fixture, replay, causal, _, label, _ = _seed_family(tmp_path / "none", kind=InterventionKind.DELIVERY, envelope_count=2)
    study = _study(fixture, label, SurfaceAxis.TRIGGER_MODE, ("ALWAYS", "FAILURE_TRIGGERED"))
    point = SurfacePoint.create(study=study, axis=SurfaceAxis.TRIGGER_MODE, value="FAILURE_TRIGGERED", decision_id="D5")
    with pytest.raises(ValueError, match="trigger"):
        SurfaceInterventionCompiler(replay, causal).compile_point(study, point, request_id="bad-trigger", decision_id="D5")

    fixture, replay, causal, _, label, _ = _seed_family(
        tmp_path / "yes", kind=InterventionKind.DELIVERY, envelope_count=2,
        events=({"event": "FAILURE", "envelope_index": 1},),
    )
    study = _study(fixture, label, SurfaceAxis.TRIGGER_MODE, ("ALWAYS", "FAILURE_TRIGGERED"))
    point = SurfacePoint.create(study=study, axis=SurfaceAxis.TRIGGER_MODE, value="FAILURE_TRIGGERED", decision_id="D5")
    intervention, _ = SurfaceInterventionCompiler(replay, causal).compile_point(
        study, point, request_id="trigger", decision_id="D5"
    )
    assert intervention.changed_dimensions == ("request_envelopes.1.messages.0.content",)
    assert "request_envelopes.0.messages.1.content" not in intervention.changed_dimensions


def test_surface_store_rejects_axis_not_owned_by_originating_mechanism(tmp_path) -> None:
    fixture, replay, causal, _, label, _ = _seed_family(tmp_path, kind=InterventionKind.COGNITION)
    surface = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    study = _study(fixture, label, SurfaceAxis.REPRESENTATION, ("PROSE", "FIELDS"))
    with pytest.raises(ValueError, match="axis|originating"):
        surface.append_study(study)


def test_surface_store_rejects_progressive_or_trigger_geometry_without_observable_event(tmp_path) -> None:
    fixture, replay, causal, _, label, _ = _seed_family(tmp_path / "context", kind=InterventionKind.CONTEXT, envelope_count=2)
    surface = SurfaceEvidenceStore(tmp_path / "context-surface", replay_store=replay, causal_store=causal)
    progressive = _study(fixture, label, SurfaceAxis.DELIVERY_MODE, ("STATIC", "PROGRESSIVE"))
    with pytest.raises(ValueError, match="state transition"):
        surface.append_study(progressive)

    fixture, replay, causal, _, label, _ = _seed_family(tmp_path / "delivery", kind=InterventionKind.DELIVERY, envelope_count=2)
    surface = SurfaceEvidenceStore(tmp_path / "delivery-surface", replay_store=replay, causal_store=causal)
    triggered = _study(fixture, label, SurfaceAxis.TRIGGER_MODE, ("ALWAYS", "FAILURE_TRIGGERED"))
    with pytest.raises(ValueError, match="trigger"):
        surface.append_study(triggered)


def test_non_cognition_study_requires_registered_baseline_value(tmp_path) -> None:
    fixture, replay, causal, _, label, _ = _seed_family(tmp_path, kind=InterventionKind.REPRESENTATION)
    surface = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    study = _study(fixture, label, SurfaceAxis.ORDER, ("REVERSE",))
    with pytest.raises(ValueError, match="baseline"):
        surface.append_study(study)


def test_existing_plan2_movement_replay_answers_non_cognition_baseline(tmp_path) -> None:
    fixture, replay, causal, _, label, _ = _seed_family(tmp_path, kind=InterventionKind.REPRESENTATION)
    surface = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    study = _study(fixture, label, SurfaceAxis.REPRESENTATION, ("PROSE", "FIELDS"))
    surface.append_study(study)
    rows = SurfaceEvidenceCompiler(replay, causal, surface).same_state_observations(study)
    assert any(row.value == "PROSE" and row.replay_result_ids == ("base-result",) for row in rows)


def test_generated_surface_request_identity_recovers_non_cognition_point(tmp_path) -> None:
    fixture, replay, causal, _, label, _ = _seed_family(tmp_path, kind=InterventionKind.REPRESENTATION)
    surface = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    study = _study(fixture, label, SurfaceAxis.REPRESENTATION, ("PROSE", "FIELDS"))
    surface.append_study(study)
    point = SurfacePoint.create(study=study, axis=SurfaceAxis.REPRESENTATION, value="FIELDS", decision_id="D5")
    request_id = f"surface-replay-{point.surface_point_id}"
    _, request = SurfaceInterventionCompiler(replay, causal).compile_point(
        study, point, request_id=request_id, decision_id="D5"
    )
    replay.append(request)
    output = replay.put_asset({"answer": "B"})
    raw = replay.put_asset({"raw_calls": []})
    replay.append(ReplayResult(
        replay_result_id="surface-fields-result", replay_request_id=request.replay_request_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash, mode=request.mode,
        target_model_id="model", target_model_digest="digest", partition=fixture.partition,
        completed=True, semantic_pass=True, contract_pass=True,
        output_asset_sha256=output, raw_call_asset_sha256=raw,
        metrics={"physical_calls": 1},
    ))
    rows = SurfaceEvidenceCompiler(replay, causal, surface).same_state_observations(study)
    assert any(row.value == "FIELDS" and row.replay_result_ids == ("surface-fields-result",) for row in rows)


def test_call_geometry_uses_actual_frozen_envelope_count(tmp_path) -> None:
    fixture, replay, causal, _, label, _ = _seed_family(
        tmp_path, kind=InterventionKind.COGNITION, envelope_count=3
    )
    surface = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    study = _study(fixture, label, SurfaceAxis.REASONING_BUDGET, (0, 512, 8192))
    surface.append_study(study)
    evidence = SurfaceEvidenceCompiler(replay, causal, surface)
    point = SurfacePoint.create(study=study, axis=SurfaceAxis.REASONING_BUDGET, value=8192, decision_id="D5")
    assert evidence.point_physical_calls(study, point) == 3
    plan = SurfacePlanner(surface, evidence).plan_next(study, max_new_points=1)
    assert plan.minimum_physical_calls == 3
    assert plan.protected_exploration_calls in {0, 3}
