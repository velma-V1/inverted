from __future__ import annotations

from pathlib import Path

import pytest

import inverted.capability_ratchet as cr
from inverted.capability_ratchet.core import Partition, PromotionState
from inverted.capability_ratchet.surface_analysis import SurfaceAnalyzer
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
from inverted.capability_ratchet.surface_interventions import semantic_contract_hash
from inverted.capability_ratchet.surface_planner import SurfacePlanner


STATE = "a" * 64


def _study(axis, values, *, mechanism="mechanism-preflight") -> SurfaceStudy:
    return SurfaceStudy.create(
        failure_snapshot_id="failure-preflight",
        mechanism_id=mechanism,
        parent_state_hash=STATE,
        partition=Partition.DEVELOPMENT,
        promotion_state=PromotionState.MOVEMENT,
        decision_id="D3",
        axes=(axis,),
        axis_values={axis.value: tuple(values)},
    )


def _obs(study, value, *, passed, latency=1.0, extra=None):
    point = SurfacePoint.create(
        study=study,
        axis=study.axes[0],
        value=value,
        decision_id=study.decision_id,
    )
    metrics = {
        "completed": True,
        "semantic_pass": passed,
        "contract_pass": True,
        "failure_classes": [] if passed else ["SEMANTIC_FAIL"],
        "physical_calls": 1,
        "latency_s": latency,
    }
    metrics.update(extra or {})
    return SurfaceObservation.create(
        point=point,
        evidence_kind=SurfaceEvidenceKind.SAME_STATE_CAUSAL,
        replay_result_ids=(f"result-{study.study_id}-{value}",),
        metrics=metrics,
    )


class AnalysisStore:
    def __init__(self, study, rows):
        self.study = study
        self.rows = tuple(rows)
        self.saved = []

    def studies(self):
        return (self.study,)

    def observations(self, study_id=None):
        return self.rows if study_id in (None, self.study.study_id) else ()

    def append_profile(self, profile):
        self.saved.append(profile)
        return profile.profile_id


class PlannerStore:
    def __init__(self, rows=(), profiles=()):
        self.rows = tuple(rows)
        self.profile_rows = tuple(profiles)

    def observations(self, study_id=None):
        return self.rows if study_id is None else tuple(row for row in self.rows if row.study_id == study_id)

    def profiles(self, mechanism_id=None):
        return self.profile_rows if mechanism_id is None else tuple(
            row for row in self.profile_rows if row.mechanism_id == mechanism_id
        )


class PlannerEvidence:
    def __init__(self, store):
        self.surface_store = store

    def answered_points(self, study):
        return frozenset(row.surface_point_id for row in self.surface_store.observations(study.study_id))


def test_planted_reasoning_band_recovers_threshold_and_high_budget_harm() -> None:
    study = _study(SurfaceAxis.REASONING_BUDGET, (0, 256, 512, 1024, 2048, 4096, 8192))
    rows = tuple(
        _obs(study, value, passed=value in {512, 1024, 2048, 4096})
        for value in study.axis_values[SurfaceAxis.REASONING_BUDGET.value]
    )
    profile = SurfaceAnalyzer(AnalysisStore(study, rows)).analyze(study.study_id)
    assert profile.disposition is SurfaceDisposition.HARM_BOUNDARY
    assert profile.lower_useful == 512
    assert profile.upper_useful == 4096
    assert profile.harm_onset == 8192
    assert profile.promotion_ceiling is PromotionState.MOVEMENT


def test_adaptive_planner_uses_fewer_than_exhaustive_points_and_keeps_extreme() -> None:
    study = _study(SurfaceAxis.REASONING_BUDGET, (0, 256, 512, 1024, 2048, 4096, 8192))
    baseline = _obs(study, 0, passed=False)
    movement = _obs(study, 512, passed=True)
    store = PlannerStore((baseline, movement))
    plan = SurfacePlanner(store, PlannerEvidence(store)).plan_next(study, max_new_points=2)
    assert 0 < len(plan.points) <= 2
    assert plan.worst_case_physical_calls < 7 * 2
    assert any(point.protected_exploration and point.value == 8192 for point in plan.points)
    assert "boundary" in plan.decision_reason.lower() or "harm" in plan.decision_reason.lower()


def test_flat_temperature_surface_remains_plateau_despite_latency_jitter() -> None:
    study = _study(SurfaceAxis.TEMPERATURE, (0.2, 0.7, 1.0))
    rows = (
        _obs(study, 0.2, passed=True, latency=9.0),
        _obs(study, 0.7, passed=True, latency=1.0),
        _obs(study, 1.0, passed=True, latency=5.0),
    )
    profile = SurfaceAnalyzer(AnalysisStore(study, rows)).analyze(study.study_id)
    assert profile.disposition is SurfaceDisposition.PLATEAU
    assert profile.recommended_region == (0.2, 0.7, 1.0)
    assert profile.lower_useful == 0.2
    assert profile.upper_useful == 1.0


def test_negative_transfer_blocks_global_interpretation() -> None:
    study = _study(SurfaceAxis.CONTEXT_DOSE, (0, 1), mechanism="mechanism-negative-transfer")
    rows = (
        _obs(study, 0, passed=False),
        _obs(study, 1, passed=True, extra={
            "protected_control_baseline_pass": True,
            "protected_control_candidate_pass": False,
        }),
    )
    profile = SurfaceAnalyzer(AnalysisStore(study, rows)).analyze(study.study_id)
    assert profile.disposition is SurfaceDisposition.NEGATIVE_TRANSFER
    assert profile.promotion_ceiling is PromotionState.MOVEMENT


def test_representation_contract_hash_preserves_meaning_and_detects_change() -> None:
    prose = "A must happen before B. Return the next valid step."
    fields = {"representation": "FIELDS", "semantic_payload": prose}
    changed = {"representation": "FIELDS", "semantic_payload": "B must happen before A."}
    assert semantic_contract_hash(prose) == semantic_contract_hash(fields)
    assert semantic_contract_hash(prose) != semantic_contract_hash(changed)


def test_plan3_public_exports_and_audit_surface_are_complete() -> None:
    required = {
        "OperatingSurfaceLab", "OperatingSurfaceProfile", "SurfaceAnalyzer",
        "SurfaceAxis", "SurfaceEvidenceCompiler", "SurfaceEvidenceStore",
        "SurfaceInterventionCompiler", "SurfacePlan", "SurfacePlanner",
        "SurfaceStepResult", "SurfaceStudy", "select_surface_study",
    }
    assert required.issubset(set(cr.__all__))

    audit = Path("scripts/audit-v3-replay-foundation.py").read_text(encoding="utf-8")
    for command in ("plan-surface", "show-surface", "run-surface"):
        assert f'"{command}"' in audit
    for filename in (
        "surface_core.py", "surface_store.py", "surface_evidence.py", "surface_planner.py",
        "surface_interventions.py", "surface_analysis.py", "surface_lab.py",
    ):
        assert filename in audit


def test_stage5_profile_cannot_promote_beyond_movement() -> None:
    study = _study(SurfaceAxis.REASONING_BUDGET, (512,))
    band = SurfaceBand(
        axis=SurfaceAxis.REASONING_BUDGET,
        disposition=SurfaceDisposition.USEFUL_BAND,
        lower_useful=512,
        upper_useful=512,
        recommended_region=(512,),
        harm_onset=None,
        evidence_observation_ids=("observation-1",),
    )
    with pytest.raises(ValueError, match="MOVEMENT"):
        OperatingSurfaceProfile.create(
            study=study,
            band=band,
            evidence_refs=("observation-1",),
            call_geometry=SurfaceCallGeometry(1, 1, 1, 0),
            promotion_ceiling=PromotionState.TIER_CANDIDATE,
        )
