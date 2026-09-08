from __future__ import annotations

from dataclasses import dataclass

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
    PromotionEvent,
    PromotionState,
    ReplayRequest,
)
from inverted.capability_ratchet.interventions import InterventionGenerator
from inverted.capability_ratchet.replay import ReplayCompletion, ReplayExecutor
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.surface_analysis import SurfaceAnalyzer
from inverted.capability_ratchet.surface_core import SurfaceAxis, SurfaceDisposition, SurfaceStudy
from inverted.capability_ratchet.surface_evidence import SurfaceEvidenceCompiler
from inverted.capability_ratchet.surface_interventions import SurfaceInterventionCompiler
from inverted.capability_ratchet.surface_lab import OperatingSurfaceLab
from inverted.capability_ratchet.surface_planner import SurfacePlanner
from inverted.capability_ratchet.surface_store import SurfaceEvidenceStore


class FakeReplayAdapter:
    def __init__(self) -> None:
        self.calls = []

    def runtime_provenance(self):
        return {"provider": "fake", "model": "model", "model_digest": "digest", "version": "1"}

    def execute_fixture(self, fixture, visible_payload, request):
        self.calls.append((fixture.failure_snapshot_id, request.replay_request_id))
        envelope = visible_payload["request_envelopes"][0]
        budget = int(envelope.get("options", {}).get("num_predict", 0) or 0)
        passed = bool(envelope.get("think")) and 512 <= budget < 8192
        return ReplayCompletion(
            completed=True,
            semantic_pass=passed,
            contract_pass=True,
            output_payload={"passed": passed, "budget": budget},
            raw_calls=tuple(
                {"request": item, "response": {"done": True, "message": {"content": "ok"}}}
                for item in visible_payload["request_envelopes"]
            ),
            failure_classes=() if passed else ("SEMANTIC_FAIL",),
            metrics={"physical_calls": len(visible_payload["request_envelopes"]), "thinking_tokens": budget},
        )


@dataclass
class Case:
    replay: ReplayStore
    causal: CausalEvidenceStore
    surface: SurfaceEvidenceStore
    study: SurfaceStudy
    lab: OperatingSurfaceLab
    adapter: FakeReplayAdapter


def build_case(tmp_path) -> Case:
    replay = ReplayStore(tmp_path / "replay")
    visible_payload = {
        "request_envelopes": [{
            "model": "model",
            "stream": False,
            "think": False,
            "options": {"seed": 7, "temperature": 0.7, "num_predict": 128},
            "messages": [{"role": "user", "content": "Return the correct answer object."}],
        }]
    }
    visible = replay.put_asset(visible_payload)
    fixture = FailureFixture(
        failure_snapshot_id="failure-surface-lab",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="obs",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="ARITHMETIC",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="model",
        source_model_digest="digest",
        source_runtime={"provider": "fake", "model": "model", "model_digest": "digest"},
        inference_profile={"thinking_budget": 0, "temperature": 0.7},
        inference_seed=7,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash=visible,
        oracle_ref="oracle",
        expected_contract="answer_object",
        source_evidence_refs=("source:1",),
    )
    replay.append(fixture)
    fixture = replay.get_failure(fixture.failure_snapshot_id)

    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.INSUFFICIENT_REASONING,
            observable_path="focus.semantic_pass",
            event_index=0,
            evidence_refs=("forensic:focus",),
            confidence=0.9,
        ),
        owner_candidate=ArchitectureOwner.MODEL,
        claim="bounded reasoning repairs the failure",
        expected_if_true="a bounded reasoning budget repairs the same parent state",
        falsifier="bounded reasoning does not repair the same parent state",
    )
    causal.append_hypothesis(hypothesis)
    base = InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        kind=InterventionKind.COGNITION,
        label="bounded reasoning 512",
        changed_dimensions=(
            "request_envelopes.0.think",
            "request_envelopes.0.options.num_predict",
        ),
        overrides={
            "request_envelopes.0.think": True,
            "request_envelopes.0.options.num_predict": 512,
        },
        expected_causal_implication="512 reasoning budget repairs the failure",
        projected_physical_calls=1,
    )
    causal.register_intervention(base)

    adapter = FakeReplayAdapter()
    executor = ReplayExecutor(replay, {"model": adapter})
    baseline = ReplayRequest.for_exact(
        fixture,
        decision_id="D1",
        hypothesis_id=hypothesis.hypothesis_id,
        request_id="baseline-exact",
    )
    executor.execute(baseline)
    generator = InterventionGenerator(replay, causal)
    movement_request = generator.compile_request(
        fixture, base, "movement-512", "D3"
    )
    movement_result = executor.execute(movement_request)
    assert movement_result.semantic_pass

    replay.append(MechanismLabel(
        mechanism_label_id="mechanism-label-surface",
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        mechanism_id="mechanism-surface",
        hypothesis_id=hypothesis.hypothesis_id,
        intervention_ids=(base.intervention_id,),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(movement_result.replay_result_id,),
        confidence=0.95,
    ))
    replay.append(PromotionEvent(
        promotion_event_id="promotion-surface-movement",
        failure_snapshot_id=fixture.failure_snapshot_id,
        mechanism_id="mechanism-surface",
        from_state=PromotionState.UNASSESSED,
        to_state=PromotionState.MOVEMENT,
        reason="matched same-state intervention repaired the failure",
        evidence_replay_result_ids=(movement_result.replay_result_id,),
        partition=fixture.partition,
    ))
    assert replay.validate().ok

    surface = SurfaceEvidenceStore(tmp_path / "surface", replay_store=replay, causal_store=causal)
    study = SurfaceStudy.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        mechanism_id="mechanism-surface",
        parent_state_hash=fixture.state_hash,
        partition=fixture.partition,
        promotion_state=PromotionState.MOVEMENT,
        decision_id="D3",
        axes=(SurfaceAxis.REASONING_BUDGET,),
        axis_values={"REASONING_BUDGET": (0, 512, 8192)},
    )
    surface.append_study(study)
    evidence = SurfaceEvidenceCompiler(replay, causal, surface)
    planner = SurfacePlanner(surface, evidence)
    compiler = SurfaceInterventionCompiler(replay, causal)
    analyzer = SurfaceAnalyzer(surface)
    lab = OperatingSurfaceLab(replay, causal, surface, evidence, planner, compiler, analyzer)
    return Case(replay, causal, surface, study, lab, adapter)


def test_prepare_reuses_existing_points_and_does_not_execute_adapter(tmp_path) -> None:
    case = build_case(tmp_path)
    calls_before = len(case.adapter.calls)
    replay_before = case.replay.registry_path.read_bytes()

    plan = case.lab.prepare(case.study.study_id)

    assert [point.value for point in plan.points] == [8192]
    assert plan.points[0].protected_exploration is True
    assert plan.minimum_physical_calls > 0
    assert len(case.adapter.calls) == calls_before
    assert case.replay.registry_path.read_bytes() == replay_before


def test_execute_delegates_once_captures_failed_child_and_returns_resolved_profile(tmp_path) -> None:
    case = build_case(tmp_path)
    plan = case.lab.prepare(case.study.study_id)
    calls_before = len(case.adapter.calls)

    result = case.lab.execute(plan, {"model": case.adapter})

    assert len(result.replay_results) == 1
    assert len(case.adapter.calls) == calls_before + 1
    assert result.child_failure_snapshot_ids
    child = case.replay.get_failure(result.child_failure_snapshot_ids[0])
    assert child.parent_failure_snapshot_id == case.study.failure_snapshot_id
    assert result.profile.disposition is SurfaceDisposition.HARM_BOUNDARY
    assert result.profile.lower_useful == 512
    assert result.profile.harm_onset == 8192
    assert result.next_plan.points == ()
    assert result.next_plan.stop_reason
    assert any(
        result.replay_results[0].replay_result_id in row.replay_result_ids
        for row in result.observations
    )
    assert result.model_calls_are_fake_only is True


def test_execute_rejects_stopped_plan_before_adapter_use(tmp_path) -> None:
    case = build_case(tmp_path)
    first = case.lab.prepare(case.study.study_id)
    case.lab.execute(first, {"model": case.adapter})
    stopped = case.lab.prepare(case.study.study_id)
    calls_before = len(case.adapter.calls)
    with pytest.raises(ValueError, match="stopped|points"):
        case.lab.execute(stopped, {"model": case.adapter})
    assert len(case.adapter.calls) == calls_before
