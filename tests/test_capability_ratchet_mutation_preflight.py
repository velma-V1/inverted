from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

import inverted.capability_ratchet as cr
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
from inverted.capability_ratchet.cli import main
from inverted.capability_ratchet.core import (
    FailureFixture,
    MechanismLabel,
    MutationFixture,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayMode,
    ReplayRecordType,
    ReplayRequest,
    ReplayResult,
)
from inverted.capability_ratchet.mutation_analysis import MutationAnalyzer
from inverted.capability_ratchet.mutation_core import (
    GeneralizationClass,
    MutationAxis,
    MutationDirection,
    MutationOrigin,
    MutationPolicy,
    MutationSpec,
)
from inverted.capability_ratchet.mutation_generator import MutationGenerator, MutationTemplate
from inverted.capability_ratchet.mutation_lab import MutationLab
from inverted.capability_ratchet.mutation_planner import MutationPlanner
from inverted.capability_ratchet.mutation_replay import MutationReplayCompiler
from inverted.capability_ratchet.mutation_store import MutationEvidenceStore, MutationStudy
from inverted.capability_ratchet.replay import ReplayCompletion
from inverted.capability_ratchet.replay_store import ReplayStore


PATH = "request_envelopes.0.messages.0.content"
REPAIR = "\n\nDEPENDENCY STATE\nEnumerate prerequisites before choosing an action."
REGION_A = "planning/dependency"
REGION_B = "planning/action"


class SurfaceStub:
    def profiles(self, mechanism_id=None):
        return ()

    def validate(self):
        return SimpleNamespace(ok=True)


class FakeAdapter:
    def __init__(self, *, fail_context_pressure: int | None = None) -> None:
        self.fail_context_pressure = fail_context_pressure
        self.calls: list[str] = []

    def runtime_provenance(self):
        return {"provider": "fake", "model": "fake-model", "model_digest": "fake-digest"}

    def execute_fixture(self, fixture, visible_payload, request):
        pressure = visible_payload["task"]["context_pressure"]
        passed = pressure != self.fail_context_pressure
        self.calls.append(request.metadata["mutation_fixture_id"])
        calls = tuple(
            {"request": envelope, "response": {"passed": passed}}
            for envelope in visible_payload["request_envelopes"]
        )
        return ReplayCompletion(
            completed=True,
            semantic_pass=passed,
            contract_pass=True,
            output_payload={"passed": passed},
            raw_calls=calls,
            failure_classes=() if passed else ("SEMANTIC_FAIL",),
            metrics={"physical_calls": len(calls)},
        )


@dataclass
class Preflight:
    replay: ReplayStore
    causal: CausalEvidenceStore
    mutation: MutationEvidenceStore
    source: FailureFixture
    study: MutationStudy
    lab: MutationLab


def _spec(
    axis: MutationAxis,
    direction: MutationDirection,
    value,
    region: str = REGION_A,
    *,
    protected: bool = False,
) -> MutationSpec:
    return MutationSpec(
        axis=axis,
        direction=direction,
        value=value,
        structural_region_id=region,
        decision_id="D12",
        protected=protected,
    )


def _instance_specs() -> tuple[MutationSpec, ...]:
    return (_spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, 3),)


def _local_specs() -> tuple[MutationSpec, ...]:
    return (
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, 3),
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.HARDER, 4),
    )


def _region_specs() -> tuple[MutationSpec, ...]:
    return (
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, 3),
        _spec(MutationAxis.REQUIREMENT_COUNT, MutationDirection.LATERAL, ["r1", "r2"]),
        _spec(MutationAxis.DISTRACTORS, MutationDirection.LATERAL, ["noise"]),
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.HARDER, 5),
    )


def _cross_region_specs() -> tuple[MutationSpec, ...]:
    return (
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.HARDER, 3),
        _spec(MutationAxis.REQUIREMENT_COUNT, MutationDirection.LATERAL, ["r1", "r2"]),
        _spec(MutationAxis.DISTRACTORS, MutationDirection.LATERAL, ["noise"]),
        _spec(MutationAxis.ORDER, MutationDirection.LATERAL, ["b", "a"], REGION_B),
        _spec(MutationAxis.CONTEXT_PRESSURE, MutationDirection.LATERAL, 4, REGION_B),
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, 4, REGION_B),
    )


def _promotion_specs() -> tuple[MutationSpec, ...]:
    return (
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.HARDER, 3),
        _spec(MutationAxis.REQUIREMENT_COUNT, MutationDirection.HARDER, ["r1", "r2"]),
        _spec(MutationAxis.DISTRACTORS, MutationDirection.LATERAL, ["noise"]),
        _spec(MutationAxis.ORDER, MutationDirection.LATERAL, ["b", "a"], REGION_B),
        _spec(MutationAxis.CONTEXT_PRESSURE, MutationDirection.LATERAL, 4, REGION_B),
        _spec(MutationAxis.DEPENDENCY_DEPTH, MutationDirection.LATERAL, 4, REGION_B),
    )


def _base_visible():
    return {
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 7, "num_predict": 128, "temperature": 0.0},
            "messages": [{"role": "user", "content": "BASE TASK"}],
        }],
        "task": {
            "depth": 2,
            "requirements": ["r1"],
            "distractors": [],
            "order": ["a", "b"],
            "context_pressure": 0,
        },
    }


def _template(source: FailureFixture, mechanism_id: str, region: str) -> MutationTemplate:
    return MutationTemplate(
        source_failure_snapshot_id=source.failure_snapshot_id,
        structural_region_id=region,
        semantic_contract={"type": "plan"},
        model_visible_template=_base_visible(),
        oracle_template={"answer": "base"},
        allowed_axes=(
            MutationAxis.DEPENDENCY_DEPTH,
            MutationAxis.REQUIREMENT_COUNT,
            MutationAxis.DISTRACTORS,
            MutationAxis.ORDER,
            MutationAxis.CONTEXT_PRESSURE,
        ),
        operator_state={
            "mechanism_id": mechanism_id,
            MutationAxis.DEPENDENCY_DEPTH.value: {"visible_path": ["task", "depth"]},
            MutationAxis.REQUIREMENT_COUNT.value: {"visible_path": ["task", "requirements"]},
            MutationAxis.DISTRACTORS.value: {"visible_path": ["task", "distractors"]},
            MutationAxis.ORDER.value: {"visible_path": ["task", "order"]},
            MutationAxis.CONTEXT_PRESSURE.value: {"visible_path": ["task", "context_pressure"]},
        },
        metadata={"operating_surface_profile_id": "preflight-surface"},
    )


def _environment(tmp_path: Path, specs: tuple[MutationSpec, ...]) -> Preflight:
    replay = ReplayStore(tmp_path / "replay")
    visible = _base_visible()
    source = FailureFixture(
        failure_snapshot_id="failure-stage6-preflight",
        source_campaign_id="preflight",
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
        model_visible_asset_sha256=replay.put_asset(visible),
        state_hash="a" * 64,
        oracle_ref="oracle:base",
        expected_contract="return a valid plan",
        source_evidence_refs=("preflight:source",),
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
            evidence_refs=("preflight:source",),
            confidence=1.0,
        ),
        owner_candidate=ArchitectureOwner.SYSTEM,
        claim="explicit dependency representation repairs this failure",
        expected_if_true="repair transfers to the mutation",
        falsifier="repair fails on the mutation",
    )
    causal.append_hypothesis(hypothesis)
    intervention = InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        kind=InterventionKind.REPRESENTATION,
        label="preflight dependency representation",
        changed_dimensions=(PATH,),
        overrides={PATH: "BASE TASK" + REPAIR},
        expected_causal_implication=hypothesis.expected_if_true,
    )
    causal.register_intervention(intervention)
    movement_request = ReplayRequest(
        replay_request_id="preflight-movement-request",
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
        replay_result_id="preflight-movement-result",
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
        raw_call_asset_sha256=replay.put_asset({"raw_calls": [{"request": visible["request_envelopes"][0]}]}),
    )
    replay.append(movement_result)
    mechanism = MechanismLabel(
        mechanism_label_id="preflight-mechanism-label",
        failure_snapshot_id=source.failure_snapshot_id,
        parent_failure_snapshot_id=source.failure_snapshot_id,
        parent_state_hash=source.state_hash,
        mechanism_id="preflight-mechanism",
        hypothesis_id=hypothesis.hypothesis_id,
        intervention_ids=(intervention.intervention_id,),
        role=MechanismRole.REQUIRED,
        evidence_replay_result_ids=(movement_result.replay_result_id,),
        confidence=1.0,
    )
    replay.append(mechanism)
    replay.append(PromotionEvent(
        promotion_event_id="preflight-movement-event",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=mechanism.mechanism_id,
        from_state=PromotionState.UNASSESSED,
        to_state=PromotionState.MOVEMENT,
        reason="planted repair earned movement",
        evidence_replay_result_ids=(movement_result.replay_result_id,),
        partition=source.partition,
    ))

    surface = SurfaceStub()
    mutation = MutationEvidenceStore(
        tmp_path / "mutation", replay_store=replay, surface_store=surface
    )
    study = MutationStudy(
        study_id="preflight-study",
        failure_snapshot_id=source.failure_snapshot_id,
        mechanism_id=mechanism.mechanism_id,
        source_failure_snapshot_id=source.failure_snapshot_id,
        source_state_hash=source.state_hash,
        operating_surface_profile_id=None,
        policy=MutationPolicy(),
        decision_id="D12",
        candidate_specs=specs,
        protected_spec_ids=tuple(item.spec_id for item in specs if item.protected),
    )
    mutation.append_study(study)
    templates = {
        REGION_A: _template(source, mechanism.mechanism_id, REGION_A),
        REGION_B: _template(source, mechanism.mechanism_id, REGION_B),
    }
    lab = MutationLab(
        replay,
        causal,
        mutation,
        templates=templates,
        generator=MutationGenerator(replay),
        planner=MutationPlanner(mutation),
        replay_compiler=MutationReplayCompiler(replay, causal),
        analyzer=MutationAnalyzer(replay, mutation),
    )
    assert replay.validate().ok and mutation.validate().ok
    return Preflight(replay, causal, mutation, source, study, lab)


def _run_all(env: Preflight, adapter: FakeAdapter):
    last = None
    for _ in range(8):
        plan = env.lab.prepare(env.study.study_id, max_new_mutations=8)
        if not plan.specs:
            break
        last = env.lab.execute(plan, {"fake-model": adapter})
        if last.next_plan.stop_reason is not None:
            break
    assert last is not None
    return last


@pytest.mark.parametrize(
    ("specs", "expected"),
    (
        (_instance_specs(), GeneralizationClass.INSTANCE_PATCH),
        (_local_specs(), GeneralizationClass.LOCAL_MECHANISM),
        (_region_specs(), GeneralizationClass.REGION_MECHANISM),
        (_cross_region_specs(), GeneralizationClass.CROSS_REGION_MECHANISM),
        (_promotion_specs(), GeneralizationClass.PROMOTION_CANDIDATE),
    ),
)
def test_planted_preflight_distinguishes_all_five_generalization_classes(
    tmp_path, specs, expected
) -> None:
    env = _environment(tmp_path / expected.value, specs)
    result = _run_all(env, FakeAdapter())
    assert result.profile.classification is expected
    assert result.model_calls_are_fake_only is True
    assert env.replay.validate().ok
    assert env.mutation.validate().ok


def test_promotion_candidate_is_append_only_and_never_certified(tmp_path) -> None:
    env = _environment(tmp_path, _promotion_specs())
    result = _run_all(env, FakeAdapter())
    assert result.profile.classification is GeneralizationClass.PROMOTION_CANDIDATE
    events = [row for row in env.replay.records() if isinstance(row, PromotionEvent)]
    assert any(
        row.from_state is PromotionState.MOVEMENT
        and row.to_state is PromotionState.TIER_CANDIDATE
        for row in events
    )
    assert not any(row.to_state is PromotionState.CERTIFIED for row in events)
    assert env.replay.get_failure(env.source.failure_snapshot_id).promotion_state is PromotionState.UNASSESSED


def test_protected_negative_transfer_blocks_promotion_and_creates_child_without_retry(tmp_path) -> None:
    protected_failure = _spec(
        MutationAxis.CONTEXT_PRESSURE,
        MutationDirection.HARDER,
        99,
        REGION_B,
        protected=True,
    )
    specs = _promotion_specs() + (protected_failure,)
    env = _environment(tmp_path, specs)
    adapter = FakeAdapter(fail_context_pressure=99)
    result = _run_all(env, adapter)
    assert result.profile.classification is not GeneralizationClass.PROMOTION_CANDIDATE
    assert result.profile.protected_failures
    events = [row for row in env.replay.records() if isinstance(row, PromotionEvent)]
    assert not any(row.to_state is PromotionState.TIER_CANDIDATE for row in events)
    children = [
        row for row in env.replay.records()
        if isinstance(row, FailureFixture) and row.parent_failure_snapshot_id is not None
    ]
    assert len(children) == 1
    assert children[0].parent_failure_snapshot_id == env.source.failure_snapshot_id
    mutation_rows = [row for row in env.replay.records() if isinstance(row, MutationFixture)]
    assert all(row.record_type is ReplayRecordType.MUTATION_FIXTURE for row in mutation_rows)
    assert all(row.origin is MutationOrigin.SYNTHETIC_NEIGHBORHOOD for row in mutation_rows)
    assert len(adapter.calls) == len(env.mutation.outcomes(env.study.study_id))


def test_answered_mutation_is_reused_before_any_new_physical_call(tmp_path) -> None:
    env = _environment(tmp_path, _local_specs())
    adapter = FakeAdapter()
    first = env.lab.prepare(env.study.study_id, max_new_mutations=1)
    first_result = env.lab.execute(first, {"fake-model": adapter})
    assert len(adapter.calls) == 1
    second = first_result.next_plan
    assert second.reused_fixture_ids
    env.lab.execute(second, {"fake-model": adapter})
    assert len(adapter.calls) == 2
    assert len(set(adapter.calls)) == 2


def test_real_transport_constructor_is_unreachable_without_explicit_gate(tmp_path, monkeypatch, capsys) -> None:
    import inverted.universal_tuning.qwen_ollama as qwen_module

    class ForbiddenTransport:
        def __init__(self, *args, **kwargs):
            raise AssertionError("real Qwen/Ollama transport constructed during zero-call preflight")

    monkeypatch.setattr(qwen_module, "QwenOllamaAdapter", ForbiddenTransport)
    rc = main([
        "run-mutations",
        "--replay-root", str(tmp_path / "missing-replay"),
        "--causal-root", str(tmp_path / "missing-causal"),
        "--surface-root", str(tmp_path / "missing-surface"),
        "--mutation-root", str(tmp_path / "missing-mutation"),
        "--study-id", "missing-study",
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "--allow-model-calls" in captured.err


def test_stage6_public_contracts_audit_and_completion_workflow_are_present() -> None:
    required_exports = {
        "GeneralizationClass", "GeneralizationProfile", "MutationAnalyzer",
        "MutationAxis", "MutationDirection", "MutationEvidenceStore", "MutationFixture",
        "MutationGenerator", "MutationLab", "MutationOrigin", "MutationOutcome",
        "MutationPlan", "MutationPlanner", "MutationPolicy", "MutationReplayCompiler",
        "MutationSpec", "MutationStepResult", "MutationStoreValidation", "MutationStudy",
        "MutationTemplate",
    }
    assert required_exports.issubset(set(cr.__all__))

    audit = Path("scripts/audit-v3-replay-foundation.py").read_text(encoding="utf-8")
    for token in (
        "stage6_axis_count",
        "stage6_mutation_fixture_roundtrip",
        "stage6_synthetic_fresh_sealed_count",
        "stage6_certified_event_count",
        "stage6_zero_call_plan_contract",
    ):
        assert token in audit

    workflow = Path(".github/workflows/v3-stage6-completion.yml")
    assert workflow.is_file()
    text = workflow.read_text(encoding="utf-8")
    assert "tests/test_capability_ratchet_mutation_*.py" in text
    assert "tests/test_capability_ratchet_*.py" in text
    assert "audit-v3-replay-foundation.py" in text
    assert "MODEL_CALLS" in text
    assert "NO_ELIGIBLE_MECHANISMS" in text
    assert "NO_MUTATION_TEMPLATE" in text
