from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

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
    MutationFixture,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
)
from inverted.capability_ratchet.mutation_analysis import MutationAnalyzer
from inverted.capability_ratchet.mutation_core import (
    MutationAxis,
    MutationDirection,
    MutationPolicy,
    MutationSpec,
)
from inverted.capability_ratchet.mutation_generator import MutationGenerator, MutationTemplate
from inverted.capability_ratchet.mutation_lab import MutationLab, MutationStepResult
from inverted.capability_ratchet.mutation_planner import MutationPlanner
from inverted.capability_ratchet.mutation_replay import MutationReplayCompiler
from inverted.capability_ratchet.mutation_store import MutationEvidenceStore, MutationStudy
from inverted.capability_ratchet.query import ReplaySelector, select_failures
from inverted.capability_ratchet.replay import ReplayCompletion
from inverted.capability_ratchet.replay_store import ReplayStore


PATH = "request_envelopes.0.messages.0.content"
REPAIR_SUFFIX = "\n\nDEPENDENCY STATE\nEnumerate visible prerequisites before choosing an action."


class SurfaceStub:
    def __init__(self, profile):
        self.profile = profile

    def profiles(self, mechanism_id=None):
        rows = (self.profile,)
        if mechanism_id is None:
            return rows
        return tuple(row for row in rows if row.mechanism_id == mechanism_id)

    def validate(self):
        return SimpleNamespace(ok=True)


class RecordingAdapter:
    def __init__(self, *, fail_on_depth: int | None = None):
        self.fail_on_depth = fail_on_depth
        self.calls = []

    def runtime_provenance(self):
        return {"provider": "fake", "model": "fake-model", "model_digest": "fake-digest"}

    def execute_fixture(self, fixture, visible_payload, request):
        depth = visible_payload["task"]["depth"]
        passed = depth != self.fail_on_depth
        self.calls.append((fixture.failure_snapshot_id, depth, request.replay_request_id))
        raw_calls = tuple(
            {"request": envelope, "response": {"passed": passed}}
            for envelope in visible_payload["request_envelopes"]
        )
        return ReplayCompletion(
            completed=True,
            semantic_pass=passed,
            contract_pass=True,
            output_payload={"passed": passed, "depth": depth},
            raw_calls=raw_calls,
            failure_classes=() if passed else ("SEMANTIC_FAIL",),
            metrics={"physical_calls": len(raw_calls)},
        )


@dataclass
class Environment:
    replay: ReplayStore
    causal: CausalEvidenceStore
    mutation: MutationEvidenceStore
    source: FailureFixture
    mechanism: MechanismLabel
    study: MutationStudy
    template: MutationTemplate
    lab: MutationLab


def _environment(tmp_path, *, specs=None) -> Environment:
    replay = ReplayStore(tmp_path / "replay")
    source_visible = {
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 7, "num_predict": 128, "temperature": 0.2},
            "messages": [{"role": "user", "content": "BASE TASK"}],
        }],
        "task": {"depth": 2, "requirements": ["r1"], "distractors": []},
    }
    source = FailureFixture(
        failure_snapshot_id="failure-stage6-lab",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="obs",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="fake-model",
        source_model_digest="fake-digest",
        source_runtime={"provider": "fake"},
        inference_profile={"thinking_budget": 0},
        inference_seed=7,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=replay.put_asset(source_visible),
        state_hash="a" * 64,
        oracle_ref="oracle:base",
        expected_contract="return a valid plan",
        source_evidence_refs=("evidence:base",),
        oracle_asset_sha256=replay.put_asset({"answer": "base"}),
    )
    replay.append(source)
    source = replay.get_failure(source.failure_snapshot_id)

    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.MISSING_DEPENDENCY,
            observable_path="focus_observation.semantic_pass",
            event_index=0,
            evidence_refs=("evidence:base",),
            confidence=0.95,
        ),
        owner_candidate=ArchitectureOwner.SYSTEM,
        claim="explicit dependency representation repairs this failure",
        expected_if_true="target succeeds while control fails",
        falsifier="target fails or control succeeds",
    )
    causal.append_hypothesis(hypothesis)
    intervention = InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        kind=InterventionKind.REPRESENTATION,
        label="proven dependency representation",
        changed_dimensions=(PATH,),
        overrides={PATH: "BASE TASK" + REPAIR_SUFFIX},
        expected_causal_implication=hypothesis.expected_if_true,
    )
    causal.register_intervention(intervention)
    movement_request = ReplayRequest(
        replay_request_id="movement-request",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        decision_id="D4",
        hypothesis_id=hypothesis.hypothesis_id,
        expected_causal_implication=intervention.expected_causal_implication,
        mode=ReplayMode.COUNTERFACTUAL,
        source_model_id=source.source_model_id,
        source_model_digest=source.source_model_digest,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        changed_dimensions=intervention.changed_dimensions,
        intervention_id=intervention.intervention_id,
        overrides=intervention.overrides,
    )
    replay.append(movement_request)
    movement_result = ReplayResult(
        replay_result_id="movement-result",
        replay_request_id=movement_request.replay_request_id,
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mode=movement_request.mode,
        target_model_id=source.source_model_id,
        target_model_digest=source.source_model_digest,
        partition=source.partition,
        completed=True,
        semantic_pass=True,
        contract_pass=True,
        output_asset_sha256=replay.put_asset({"passed": True}),
        raw_call_asset_sha256=replay.put_asset({"raw_calls": [{"request": source_visible["request_envelopes"][0]}]}),
        metadata={"intervention_id": intervention.intervention_id},
    )
    replay.append(movement_result)
    mechanism = MechanismLabel(
        mechanism_label_id="mechanism-label-stage6",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mechanism_id="mechanism-stage6",
        hypothesis_id=hypothesis.hypothesis_id,
        intervention_ids=(intervention.intervention_id,),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(movement_result.replay_result_id,),
        confidence=0.95,
    )
    replay.append(mechanism)
    replay.append(PromotionEvent(
        promotion_event_id="movement-event-stage6",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=mechanism.mechanism_id,
        from_state=PromotionState.UNASSESSED,
        to_state=PromotionState.MOVEMENT,
        reason="causal repair earned movement",
        evidence_replay_result_ids=(movement_result.replay_result_id,),
        partition=source.partition,
    ))

    profile = SimpleNamespace(
        profile_id="surface-profile-stage6",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=mechanism.mechanism_id,
    )
    surface = SurfaceStub(profile)
    mutation = MutationEvidenceStore(
        tmp_path / "mutation", replay_store=replay, surface_store=surface
    )
    if specs is None:
        specs = (
            MutationSpec(
                axis=MutationAxis.DEPENDENCY_DEPTH,
                direction=MutationDirection.LATERAL,
                value=3,
                structural_region_id="planning/dependency",
            ),
            MutationSpec(
                axis=MutationAxis.DEPENDENCY_DEPTH,
                direction=MutationDirection.HARDER,
                value=5,
                structural_region_id="planning/dependency",
                protected=True,
            ),
        )
    study = MutationStudy(
        study_id="mutation-study-stage6",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=mechanism.mechanism_id,
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        operating_surface_profile_id=profile.profile_id,
        policy=MutationPolicy(),
        decision_id="D12",
        candidate_specs=tuple(specs),
        protected_spec_ids=tuple(spec.spec_id for spec in specs if spec.protected),
    )
    mutation.append_study(study)
    template = MutationTemplate(
        source_failure_snapshot_id=source.failure_snapshot_id,
        structural_region_id="planning/dependency",
        semantic_contract={"type": "plan"},
        model_visible_template=source_visible,
        oracle_template={"answer": "base"},
        allowed_axes=(MutationAxis.DEPENDENCY_DEPTH,),
        operator_state={
            "mechanism_id": mechanism.mechanism_id,
            MutationAxis.DEPENDENCY_DEPTH.value: {"visible_path": ["task", "depth"]},
        },
        metadata={"operating_surface_profile_id": profile.profile_id},
    )
    generator = MutationGenerator(replay)
    planner = MutationPlanner(mutation)
    compiler = MutationReplayCompiler(replay, causal)
    analyzer = MutationAnalyzer(replay, mutation)
    lab = MutationLab(
        replay,
        causal,
        mutation,
        templates={study.study_id: template},
        generator=generator,
        planner=planner,
        replay_compiler=compiler,
        analyzer=analyzer,
    )
    return Environment(replay, causal, mutation, source, mechanism, study, template, lab)


def _mutation_rows(env):
    return tuple(
        row for row in env.replay.records()
        if isinstance(row, MutationFixture) and row.failure_snapshot_id == env.source.failure_snapshot_id
    )


def test_prepare_materializes_only_current_bounded_plan_without_model_calls(tmp_path):
    env = _environment(tmp_path)
    before_results = tuple(row for row in env.replay.records() if isinstance(row, ReplayResult))

    plan = env.lab.prepare(env.study.study_id, max_new_mutations=1)

    rows = _mutation_rows(env)
    assert len(plan.specs) == 1
    assert len(rows) == 1
    assert rows[0].metadata["mutation_spec_id"] == plan.specs[0].spec_id
    assert rows[0].metadata["operating_surface_profile_id"] == "surface-profile-stage6"
    assert tuple(row for row in env.replay.records() if isinstance(row, ReplayResult)) == before_results
    assert env.replay.validate().ok


def test_prepare_reuses_existing_materialized_fixture_without_duplicate_row(tmp_path):
    env = _environment(tmp_path)
    first = env.lab.prepare(env.study.study_id, max_new_mutations=1)
    before = env.replay.registry_path.read_bytes()

    second = env.lab.prepare(env.study.study_id, max_new_mutations=1)

    assert second.specs == first.specs
    assert env.replay.registry_path.read_bytes() == before
    assert len(_mutation_rows(env)) == 1


def test_prepare_refuses_to_invent_missing_mutation_template(tmp_path):
    env = _environment(tmp_path)
    lab = MutationLab(
        env.replay,
        env.causal,
        env.mutation,
        templates={},
        generator=MutationGenerator(env.replay),
        planner=MutationPlanner(env.mutation),
        replay_compiler=MutationReplayCompiler(env.replay, env.causal),
        analyzer=MutationAnalyzer(env.replay, env.mutation),
    )
    with pytest.raises(ValueError, match="NO_MUTATION_TEMPLATE"):
        lab.prepare(env.study.study_id)


def test_execute_uses_existing_replay_executor_appends_outcomes_and_adapts_next_plan(tmp_path):
    env = _environment(tmp_path)
    plan = env.lab.prepare(env.study.study_id, max_new_mutations=1)
    adapter = RecordingAdapter()

    result = env.lab.execute(plan, {"fake-model": adapter})

    assert isinstance(result, MutationStepResult)
    assert len(result.replay_results) == 1
    assert len(result.outcomes) == 1
    assert result.replay_results[0].metadata["mutation_fixture_id"] == result.outcomes[0].mutation_fixture_id
    assert result.profile.study_id == env.study.study_id
    assert result.model_calls_are_fake_only is True
    assert len(adapter.calls) == 1
    assert len(env.mutation.outcomes(env.study.study_id)) == 1
    assert result.next_plan.reused_fixture_ids
    assert env.replay.validate().ok
    assert env.mutation.validate().ok


def test_failed_harder_probe_creates_queryable_child_and_never_retries(tmp_path):
    hard = MutationSpec(
        axis=MutationAxis.DEPENDENCY_DEPTH,
        direction=MutationDirection.HARDER,
        value=5,
        structural_region_id="planning/dependency",
        protected=True,
    )
    env = _environment(tmp_path, specs=(hard,))
    plan = env.lab.prepare(env.study.study_id)
    adapter = RecordingAdapter(fail_on_depth=5)
    source_before = env.replay.get_failure(env.source.failure_snapshot_id)

    result = env.lab.execute(plan, {"fake-model": adapter})

    assert len(adapter.calls) == 1
    assert len(result.child_failure_snapshot_ids) == 1
    child_id = result.child_failure_snapshot_ids[0]
    child = env.replay.get_failure(child_id)
    assert child.parent_failure_snapshot_id == env.source.failure_snapshot_id
    assert child.metadata["mutation_fixture_id"] == result.outcomes[0].mutation_fixture_id
    assert env.replay.get_failure(env.source.failure_snapshot_id) == source_before
    assert [row.failure_snapshot_id for row in select_failures(
        env.replay, ReplaySelector(snapshot_ids=(child_id,))
    )] == [child_id]
    assert result.profile.protected_failures == (result.outcomes[0].mutation_fixture_id,)
    assert result.next_plan.stop_reason is not None
