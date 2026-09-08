from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from inverted.capability_ratchet.core import Partition, PromotionState
from inverted.capability_ratchet.surface_analysis import SurfaceAnalyzer
from inverted.capability_ratchet.surface_core import (
    OperatingSurfaceProfile,
    SurfaceAxis,
    SurfaceDisposition,
    SurfaceEvidenceKind,
    SurfaceObservation,
    SurfacePoint,
    SurfaceStudy,
)


STATE = "b" * 64


def study(axis, values):
    return SurfaceStudy.create(
        failure_snapshot_id="failure-analysis", mechanism_id="mechanism-analysis",
        parent_state_hash=STATE, partition=Partition.DEVELOPMENT,
        promotion_state=PromotionState.MOVEMENT, decision_id="D3",
        axes=(axis,), axis_values={axis.value: tuple(values)},
    )


def obs(surface_study, value, passed, *, latency=0.1, protected=False, prior=False, extra=None):
    point = SurfacePoint.create(
        study=surface_study, axis=surface_study.axes[0], value=value,
        decision_id=surface_study.decision_id, protected_exploration=protected,
    )
    metrics = {
        "completed": True, "semantic_pass": passed, "contract_pass": True,
        "physical_calls": 1 if value == 0 else 2, "latency_s": latency,
    }
    if extra:
        metrics.update(extra)
    if prior:
        return SurfaceObservation.create(
            point=point, evidence_kind=SurfaceEvidenceKind.HISTORICAL_PRIOR,
            source_evidence_refs=(f"prior:{value}",), metrics=metrics,
        )
    return SurfaceObservation.create(
        point=point, evidence_kind=SurfaceEvidenceKind.SAME_STATE_CAUSAL,
        replay_result_ids=(f"result:{value}:{latency}",), metrics=metrics,
    )


@dataclass
class FakeStore:
    surface_study: SurfaceStudy
    rows: tuple[SurfaceObservation, ...]
    saved: list[OperatingSurfaceProfile] = field(default_factory=list)

    def studies(self, mechanism_id=None):
        values = (self.surface_study,)
        return values if mechanism_id is None else tuple(x for x in values if x.mechanism_id == mechanism_id)

    def observations(self, study_id=None):
        return self.rows if study_id in (None, self.surface_study.study_id) else ()

    def append_profile(self, profile):
        if all(existing.profile_id != profile.profile_id for existing in self.saved):
            self.saved.append(profile)
        return profile.profile_id


def test_reasoning_surface_finds_lower_bound_robust_band_and_harm_onset() -> None:
    s = study(SurfaceAxis.REASONING_BUDGET, (0, 256, 512, 1024, 2048, 4096, 8192))
    rows = tuple(obs(s, value, passed) for value, passed in (
        (0, False), (256, False), (512, True), (1024, True),
        (2048, True), (4096, True), (8192, False),
    ))
    store = FakeStore(s, rows)
    profile = SurfaceAnalyzer(store).analyze(s.study_id)
    assert profile.disposition is SurfaceDisposition.HARM_BOUNDARY
    assert profile.lower_useful == 512
    assert profile.upper_useful == 4096
    assert profile.recommended_region == (512, 1024, 2048, 4096)
    assert profile.harm_onset == 8192
    assert profile.unresolved_edges == ()
    assert store.saved == [profile]


def test_flat_temperature_surface_remains_plateau_despite_latency_jitter() -> None:
    s = study(SurfaceAxis.TEMPERATURE, (0.6, 0.8, 1.0))
    rows = (
        obs(s, 0.6, True, latency=0.9),
        obs(s, 0.8, True, latency=0.1),
        obs(s, 1.0, True, latency=0.5),
    )
    profile = SurfaceAnalyzer(FakeStore(s, rows)).analyze(s.study_id)
    assert profile.disposition is SurfaceDisposition.PLATEAU
    assert profile.recommended_region == (0.6, 0.8, 1.0)
    assert profile.harm_onset is None


def test_negative_transfer_overrides_local_gain_with_conditional_boundary() -> None:
    s = study(SurfaceAxis.REASONING_BUDGET, (0, 512, 1024))
    rows = (
        obs(s, 0, False),
        obs(s, 512, True),
        obs(s, 1024, True, extra={
            "protected_control_baseline_pass": True,
            "protected_control_candidate_pass": False,
        }),
    )
    profile = SurfaceAnalyzer(FakeStore(s, rows)).analyze(s.study_id)
    assert profile.disposition is SurfaceDisposition.NEGATIVE_TRANSFER
    assert profile.lower_useful == 512
    assert profile.recommended_region == (512, 1024)


def test_historical_priors_alone_cannot_create_causal_surface_bound() -> None:
    s = study(SurfaceAxis.REASONING_BUDGET, (0, 512, 1024))
    rows = (
        obs(s, 0, False, prior=True),
        obs(s, 512, True, prior=True),
        obs(s, 1024, True, prior=True),
    )
    with pytest.raises(ValueError, match="same-state causal"):
        SurfaceAnalyzer(FakeStore(s, rows)).analyze(s.study_id)


def test_paired_clustered_evidence_blocks_false_useful_region() -> None:
    s = study(SurfaceAxis.REASONING_BUDGET, (512,))
    rows = []
    for index in range(40):
        rows.append(obs(
            s, 512, index < 30, latency=0.1 + index / 1000,
            extra={
                "paired_batch_id": f"batch-{index}",
                "paired_baseline_pass": True,
            },
        ))
    profile = SurfaceAnalyzer(FakeStore(s, tuple(rows))).analyze(s.study_id)
    assert profile.disposition is SurfaceDisposition.NO_USEFUL_REGION
    assert profile.recommended_region == ()
