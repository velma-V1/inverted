from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from inverted.capability_ratchet.core import Partition, PromotionState
from inverted.capability_ratchet.surface_core import (
    OperatingSurfaceProfile,
    SurfaceAxis,
    SurfaceBand,
    SurfaceCallGeometry,
    SurfaceDisposition,
    SurfaceEvidenceKind,
    SurfaceObservation,
    SurfacePoint,
    SurfaceStudy,
)


PARENT_HASH = "a" * 64


def _study(**overrides) -> SurfaceStudy:
    payload = {
        "failure_snapshot_id": "failure-1",
        "mechanism_id": "mechanism-1",
        "parent_state_hash": PARENT_HASH,
        "partition": Partition.HISTORICAL,
        "promotion_state": PromotionState.MOVEMENT,
        "decision_id": "D3",
        "axes": (SurfaceAxis.REASONING_BUDGET,),
        "axis_values": {"REASONING_BUDGET": (0, 256, 512, 1024, 2048)},
    }
    payload.update(overrides)
    return SurfaceStudy.create(**payload)


def test_surface_study_is_deterministic_frozen_and_json_safe() -> None:
    first = _study()
    second = _study()
    assert first == second
    assert first.study_id == second.study_id
    assert first.study_id.startswith("surface-study-")
    assert first.axes == (SurfaceAxis.REASONING_BUDGET,)
    assert first.axis_values["REASONING_BUDGET"] == (0, 256, 512, 1024, 2048)
    with pytest.raises(FrozenInstanceError):
        first.decision_id = "D4"  # type: ignore[misc]
    with pytest.raises(TypeError):
        first.axis_values["REASONING_BUDGET"] = (0,)  # type: ignore[index]


def test_surface_study_requires_movement_or_decision_critical_reason() -> None:
    with pytest.raises(ValueError, match="MOVEMENT"):
        _study(promotion_state=PromotionState.UNASSESSED)

    critical = _study(
        promotion_state=PromotionState.UNASSESSED,
        decision_critical_reason="D3 remains unresolved after Plan 2 matched intervention evidence",
    )
    assert critical.decision_critical_reason

    with pytest.raises(ValueError, match="REJECTED"):
        _study(
            promotion_state=PromotionState.REJECTED,
            decision_critical_reason="must not revive rejected mechanism",
        )


def test_surface_study_rejects_fresh_and_sealed_characterization() -> None:
    for partition in (Partition.FRESH, Partition.SEALED):
        with pytest.raises(ValueError, match="FRESH|SEALED"):
            _study(partition=partition)


def test_surface_study_rejects_duplicate_axes_and_axis_values() -> None:
    with pytest.raises(ValueError, match="axes must be unique"):
        _study(axes=(SurfaceAxis.REASONING_BUDGET, SurfaceAxis.REASONING_BUDGET))
    with pytest.raises(ValueError, match="axis values must be unique"):
        _study(axis_values={"REASONING_BUDGET": (0, 512, 512, 1024)})
    with pytest.raises(ValueError, match="exactly match axes"):
        _study(axis_values={"TEMPERATURE": (0.6, 1.0)})


def test_surface_point_identity_binds_one_axis_value_to_immutable_parent() -> None:
    study = _study()
    first = SurfacePoint.create(
        study=study,
        axis=SurfaceAxis.REASONING_BUDGET,
        value=512,
        decision_id="D3",
        protected_exploration=False,
    )
    second = SurfacePoint.create(
        study=study,
        axis=SurfaceAxis.REASONING_BUDGET,
        value=512,
        decision_id="D3",
        protected_exploration=False,
    )
    assert first == second
    assert first.surface_point_id == second.surface_point_id
    assert first.parent_state_hash == PARENT_HASH
    assert first.failure_snapshot_id == study.failure_snapshot_id
    assert first.mechanism_id == study.mechanism_id

    with pytest.raises(ValueError, match="not registered"):
        SurfacePoint.create(
            study=study,
            axis=SurfaceAxis.REASONING_BUDGET,
            value=8192,
            decision_id="D3",
        )


def test_surface_observation_requires_explicit_causal_or_prior_lineage() -> None:
    point = SurfacePoint.create(
        study=_study(), axis=SurfaceAxis.REASONING_BUDGET, value=512, decision_id="D3"
    )
    causal = SurfaceObservation.create(
        point=point,
        evidence_kind=SurfaceEvidenceKind.SAME_STATE_CAUSAL,
        replay_result_ids=("replay-result-1",),
        metrics={"semantic_pass": True, "contract_pass": True, "MODEL_CALLS": 1},
    )
    assert causal.replay_result_ids == ("replay-result-1",)
    assert causal.source_evidence_refs == ()

    prior = SurfaceObservation.create(
        point=point,
        evidence_kind=SurfaceEvidenceKind.HISTORICAL_PRIOR,
        source_evidence_refs=("v2:atomic_observations.jsonl:12",),
        metrics={"semantic_pass": True, "thinking_tokens": 510},
    )
    assert prior.source_evidence_refs
    assert prior.replay_result_ids == ()

    with pytest.raises(ValueError, match="replay_result_ids"):
        SurfaceObservation.create(
            point=point,
            evidence_kind=SurfaceEvidenceKind.SAME_STATE_CAUSAL,
            source_evidence_refs=("v2:row",),
            metrics={"semantic_pass": True},
        )
    with pytest.raises(ValueError, match="source_evidence_refs"):
        SurfaceObservation.create(
            point=point,
            evidence_kind=SurfaceEvidenceKind.HISTORICAL_PRIOR,
            replay_result_ids=("replay-result-1",),
            metrics={"semantic_pass": True},
        )


def test_surface_call_geometry_is_ordered_and_includes_exploration_reserve() -> None:
    geometry = SurfaceCallGeometry(
        minimum_physical_calls=2,
        expected_physical_calls=4,
        worst_case_physical_calls=8,
        protected_exploration_calls=1,
    )
    assert geometry.minimum_physical_calls <= geometry.expected_physical_calls <= geometry.worst_case_physical_calls
    with pytest.raises(ValueError, match="minimum.*expected.*worst"):
        SurfaceCallGeometry(5, 4, 8, 1)
    with pytest.raises(ValueError, match="protected"):
        SurfaceCallGeometry(2, 4, 8, 9)


def test_operating_surface_profile_is_capped_at_movement() -> None:
    study = _study()
    band = SurfaceBand(
        axis=SurfaceAxis.REASONING_BUDGET,
        disposition=SurfaceDisposition.USEFUL_BAND,
        lower_useful=512,
        upper_useful=2048,
        recommended_region=(512, 1024, 2048),
        harm_onset=8192,
        evidence_observation_ids=("surface-observation-1", "surface-observation-2"),
        unresolved_edges=(4096,),
    )
    profile = OperatingSurfaceProfile.create(
        study=study,
        band=band,
        evidence_refs=("surface-observation-1", "surface-observation-2"),
        call_geometry=SurfaceCallGeometry(2, 4, 8, 1),
    )
    assert profile.promotion_ceiling is PromotionState.MOVEMENT
    assert profile.lower_useful == 512
    assert profile.upper_useful == 2048
    assert profile.recommended_region == (512, 1024, 2048)
    assert profile.harm_onset == 8192

    with pytest.raises(ValueError, match="MOVEMENT"):
        OperatingSurfaceProfile.create(
            study=study,
            band=band,
            evidence_refs=("surface-observation-1",),
            call_geometry=SurfaceCallGeometry(2, 4, 8, 1),
            promotion_ceiling=PromotionState.TIER_CANDIDATE,
        )


def test_surface_observation_retains_reconstructable_point_coordinates() -> None:
    point = SurfacePoint.create(
        study=_study(), axis=SurfaceAxis.REASONING_BUDGET, value=512, decision_id="D3"
    )
    observation = SurfaceObservation.create(
        point=point,
        evidence_kind=SurfaceEvidenceKind.HISTORICAL_PRIOR,
        source_evidence_refs=("v2:row",),
    )
    assert observation.axis is SurfaceAxis.REASONING_BUDGET
    assert observation.value == 512
    assert observation.decision_id == "D3"
    assert observation.protected_exploration is False


def test_surface_point_identity_is_independent_of_decision_label() -> None:
    study = _study()
    d3 = SurfacePoint.create(
        study=study, axis=SurfaceAxis.REASONING_BUDGET, value=512, decision_id="D3"
    )
    d4 = SurfacePoint.create(
        study=study, axis=SurfaceAxis.REASONING_BUDGET, value=512, decision_id="D4"
    )
    assert d3.surface_point_id == d4.surface_point_id
    assert d3.decision_id != d4.decision_id


def test_surface_point_identity_is_independent_of_exploration_label() -> None:
    surface_study = _study()
    ordinary = SurfacePoint.create(
        study=surface_study, axis=SurfaceAxis.REASONING_BUDGET, value=2048,
        decision_id="D3", protected_exploration=False,
    )
    protected = SurfacePoint.create(
        study=surface_study, axis=SurfaceAxis.REASONING_BUDGET, value=2048,
        decision_id="D3", protected_exploration=True,
    )
    assert ordinary.surface_point_id == protected.surface_point_id
