from __future__ import annotations

import json
from pathlib import Path

import pytest

from inverted.capability_ratchet import (
    FailureFixture,
    MechanismLabel,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayMode,
    ReplayRequest,
    ReplayResult,
)
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
from inverted.capability_ratchet.mechanisms import MechanismLocalizer
from inverted.capability_ratchet.query import ReplaySelector, select_failures
from inverted.capability_ratchet.replay_store import ReplayStore


PATH = "request_envelopes.0.messages.0.content"


def _root(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    visible = replay.put_asset({
        "request_envelopes": [{
            "model": "fake-model",
            "stream": False,
            "think": False,
            "options": {"seed": 1},
            "messages": [{"role": "user", "content": "dependency-sensitive task"}],
        }]
    })
    fixture = FailureFixture(
        failure_snapshot_id="failure-mechanism",
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
        inference_seed=1,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash="a" * 64,
        oracle_ref="oracle",
        expected_contract="plan",
        source_evidence_refs=("raw:1",),
    )
    replay.append(fixture)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    return replay.get_failure(fixture.failure_snapshot_id), replay, causal


def _hypothesis(fixture, causal, suffix="main"):
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.MISSING_DEPENDENCY,
            observable_path="focus_observation.semantic_pass",
            event_index=0,
            evidence_refs=(f"evidence:{suffix}",),
            confidence=0.9,
        ),
        owner_candidate=ArchitectureOwner.SYSTEM,
        claim=f"dependency representation {suffix} repairs the failure",
        expected_if_true="target succeeds while matched sham fails",
        falsifier="target fails or matched sham also succeeds",
    )
    causal.append_hypothesis(hypothesis)
    return hypothesis


def _intervention(
    fixture,
    causal,
    hypothesis,
    intervention_id,
    *,
    kind=InterventionKind.REPRESENTATION,
    composition=(),
    sham_for=None,
    ablates=(),
):
    value = InterventionDefinition(
        intervention_id=intervention_id,
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        kind=kind,
        label=intervention_id,
        changed_dimensions=(PATH,) if kind not in {InterventionKind.ABLATION} else (),
        overrides={PATH: intervention_id} if kind not in {InterventionKind.ABLATION} else {},
        expected_causal_implication="distinguish the causal mechanism",
        projected_physical_calls=1,
        composition=tuple(composition),
        sham_for=sham_for,
        ablates=tuple(ablates),
    )
    causal.register_intervention(value)
    return value


def _outcome(replay, fixture, hypothesis, intervention, *, passed, suffix):
    request = ReplayRequest(
        replay_request_id=f"request-{suffix}",
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        decision_id=f"decision-{suffix}",
        hypothesis_id=hypothesis.hypothesis_id,
        expected_causal_implication=intervention.expected_causal_implication,
        mode=ReplayMode.COUNTERFACTUAL,
        source_model_id=fixture.source_model_id,
        source_model_digest=fixture.source_model_digest,
        target_model_id=fixture.source_model_id,
        target_model_digest=fixture.source_model_digest,
        partition=fixture.partition,
        changed_dimensions=(PATH,),
        intervention_id=intervention.intervention_id,
        overrides={PATH: intervention.intervention_id},
        metadata={"intervention_kind": intervention.kind.value},
    )
    replay.append(request)
    child_id = None
    if not passed:
        child_id = f"child-{suffix}"
        child = FailureFixture(
            failure_snapshot_id=child_id,
            source_campaign_id=fixture.source_campaign_id,
            source_trial_id=f"replay:{suffix}",
            focus_observation_id=f"replay-obs:{suffix}",
            focus_task_id=fixture.focus_task_id,
            batch_task_ids=fixture.batch_task_ids,
            family=fixture.family,
            failure_classes=("SEMANTIC_FAIL",),
            source_model_id=fixture.source_model_id,
            source_model_digest=fixture.source_model_digest,
            source_runtime=fixture.source_runtime,
            inference_profile=fixture.inference_profile,
            inference_seed=fixture.inference_seed,
            partition=fixture.partition,
            model_visible_asset_sha256=fixture.model_visible_asset_sha256,
            state_hash=(suffix.encode("utf-8").hex() + "b" * 64)[:64],
            oracle_ref=fixture.oracle_ref,
            expected_contract=fixture.expected_contract,
            source_evidence_refs=(f"replay:{suffix}",),
            parent_failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
        )
        replay.append(child)
    output = replay.put_asset({"passed": passed, "suffix": suffix})
    raw = replay.put_asset({"raw_calls": [{"request": {"id": suffix}, "response": {"passed": passed}}]})
    result = ReplayResult(
        replay_result_id=f"result-{suffix}",
        replay_request_id=request.replay_request_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        mode=ReplayMode.COUNTERFACTUAL,
        target_model_id=fixture.source_model_id,
        target_model_digest=fixture.source_model_digest,
        partition=fixture.partition,
        completed=True,
        semantic_pass=passed,
        contract_pass=True,
        output_asset_sha256=output,
        raw_call_asset_sha256=raw,
        failure_classes=() if passed else ("SEMANTIC_FAIL",),
        child_failure_snapshot_id=child_id,
        metrics={"physical_calls": 1},
        metadata={"intervention_id": intervention.intervention_id},
    )
    replay.append(result)
    return result


def _simple_pair(tmp_path, *, target_pass, sham_pass):
    fixture, replay, causal = _root(tmp_path)
    hypothesis = _hypothesis(fixture, causal)
    target = _intervention(fixture, causal, hypothesis, "target")
    sham = _intervention(
        fixture,
        causal,
        hypothesis,
        "sham",
        kind=InterventionKind.SHAM,
        sham_for=target.intervention_id,
    )
    results = (
        _outcome(replay, fixture, hypothesis, target, passed=target_pass, suffix="target"),
        _outcome(replay, fixture, hypothesis, sham, passed=sham_pass, suffix="sham"),
    )
    assessment = MechanismLocalizer(replay, causal).evaluate(
        fixture.failure_snapshot_id, results
    )
    return fixture, replay, causal, hypothesis, target, sham, assessment


def test_target_success_sham_failure_earns_movement_not_certification(tmp_path):
    fixture, replay, _, hypothesis, _, _, assessment = _simple_pair(
        tmp_path, target_pass=True, sham_pass=False
    )
    assert hypothesis.hypothesis_id in assessment.supported_hypotheses
    assert any(label.role is MechanismRole.REQUIRED for label in assessment.labels)
    assert any(event.to_state is PromotionState.MOVEMENT for event in assessment.promotion_events)
    assert not any(
        event.to_state in {PromotionState.TIER_CANDIDATE, PromotionState.CERTIFIED}
        for event in assessment.promotion_events
    )
    assert replay.get_failure(fixture.failure_snapshot_id).promotion_state is PromotionState.UNASSESSED
    assert replay.validate().ok


def test_target_and_sham_both_passing_stays_unresolved_and_unpromoted(tmp_path):
    _, replay, _, hypothesis, _, _, assessment = _simple_pair(
        tmp_path, target_pass=True, sham_pass=True
    )
    assert hypothesis.hypothesis_id not in assessment.supported_hypotheses
    assert any(label.role is MechanismRole.UNRESOLVED for label in assessment.labels)
    assert not assessment.promotion_events
    assert replay.validate().ok


def test_target_failure_while_sham_passes_is_harmful_and_falsifies_hypothesis(tmp_path):
    _, replay, _, hypothesis, _, _, assessment = _simple_pair(
        tmp_path, target_pass=False, sham_pass=True
    )
    assert hypothesis.hypothesis_id in assessment.falsified_hypotheses
    assert any(label.role is MechanismRole.HARMFUL for label in assessment.labels)
    assert not assessment.promotion_events
    assert replay.validate().ok


def test_compound_ablation_distinguishes_required_and_redundant_components(tmp_path):
    fixture, replay, causal = _root(tmp_path)
    hypothesis = _hypothesis(fixture, causal, "compound")
    compound = _intervention(
        fixture, causal, hypothesis, "compound", composition=("A", "B")
    )
    sham = _intervention(
        fixture, causal, hypothesis, "compound-sham",
        kind=InterventionKind.SHAM, sham_for=compound.intervention_id,
    )
    ablate_a = _intervention(
        fixture, causal, hypothesis, "ablate-A",
        kind=InterventionKind.ABLATION, composition=("B",), ablates=("A",),
    )
    ablate_b = _intervention(
        fixture, causal, hypothesis, "ablate-B",
        kind=InterventionKind.ABLATION, composition=("A",), ablates=("B",),
    )
    results = (
        _outcome(replay, fixture, hypothesis, compound, passed=True, suffix="compound"),
        _outcome(replay, fixture, hypothesis, sham, passed=False, suffix="compound-sham"),
        _outcome(replay, fixture, hypothesis, ablate_a, passed=False, suffix="ablate-a"),
        _outcome(replay, fixture, hypothesis, ablate_b, passed=True, suffix="ablate-b"),
    )
    assessment = MechanismLocalizer(replay, causal).evaluate(fixture.failure_snapshot_id, results)
    roles = {(tuple(label.intervention_ids), label.role) for label in assessment.labels}
    assert (("A",), MechanismRole.REQUIRED) in roles
    assert (("B",), MechanismRole.REDUNDANT) in roles


def test_unordered_compound_with_no_successful_singletons_is_synergistic(tmp_path):
    fixture, replay, causal = _root(tmp_path)
    hypothesis = _hypothesis(fixture, causal, "synergy")
    a = _intervention(fixture, causal, hypothesis, "A")
    b = _intervention(fixture, causal, hypothesis, "B")
    compound = _intervention(fixture, causal, hypothesis, "A+B", composition=("A", "B"))
    sham = _intervention(
        fixture, causal, hypothesis, "A+B-sham", kind=InterventionKind.SHAM,
        sham_for=compound.intervention_id,
    )
    results = (
        _outcome(replay, fixture, hypothesis, a, passed=False, suffix="a"),
        _outcome(replay, fixture, hypothesis, b, passed=False, suffix="b"),
        _outcome(replay, fixture, hypothesis, compound, passed=True, suffix="ab"),
        _outcome(replay, fixture, hypothesis, sham, passed=False, suffix="ab-sham"),
    )
    assessment = MechanismLocalizer(replay, causal).evaluate(fixture.failure_snapshot_id, results)
    assert any(label.role is MechanismRole.SYNERGIST for label in assessment.labels)


def test_ordered_delivery_compound_can_identify_enabler(tmp_path):
    fixture, replay, causal = _root(tmp_path)
    hypothesis = _hypothesis(fixture, causal, "enable")
    a = _intervention(fixture, causal, hypothesis, "A")
    b = _intervention(fixture, causal, hypothesis, "B")
    compound = _intervention(
        fixture, causal, hypothesis, "A->B", kind=InterventionKind.DELIVERY,
        composition=("A", "B"),
    )
    sham = _intervention(
        fixture, causal, hypothesis, "A->B-sham", kind=InterventionKind.SHAM,
        sham_for=compound.intervention_id,
    )
    results = (
        _outcome(replay, fixture, hypothesis, a, passed=False, suffix="enable-a"),
        _outcome(replay, fixture, hypothesis, b, passed=False, suffix="enable-b"),
        _outcome(replay, fixture, hypothesis, compound, passed=True, suffix="enable-ab"),
        _outcome(replay, fixture, hypothesis, sham, passed=False, suffix="enable-sham"),
    )
    assessment = MechanismLocalizer(replay, causal).evaluate(fixture.failure_snapshot_id, results)
    assert any(
        label.role is MechanismRole.ENABLER and label.intervention_ids == ("A",)
        for label in assessment.labels
    )


def test_failed_compound_with_successful_prefix_identifies_suppressor(tmp_path):
    fixture, replay, causal = _root(tmp_path)
    hypothesis = _hypothesis(fixture, causal, "suppress")
    a = _intervention(fixture, causal, hypothesis, "A")
    compound = _intervention(
        fixture, causal, hypothesis, "A+B", composition=("A", "B")
    )
    results = (
        _outcome(replay, fixture, hypothesis, a, passed=True, suffix="suppress-a"),
        _outcome(replay, fixture, hypothesis, compound, passed=False, suffix="suppress-ab"),
    )
    assessment = MechanismLocalizer(replay, causal).evaluate(fixture.failure_snapshot_id, results)
    assert any(
        label.role is MechanismRole.SUPPRESSOR and label.intervention_ids == ("B",)
        for label in assessment.labels
    )


def test_cross_parent_result_is_rejected_from_causal_comparison(tmp_path):
    fixture, replay, causal, hypothesis, target, sham, _ = _simple_pair(
        tmp_path, target_pass=True, sham_pass=False
    )
    other_visible = replay.put_asset({"request_envelopes": [{"model": "fake-model", "messages": []}]})
    other = FailureFixture(
        failure_snapshot_id="other-root", source_campaign_id="campaign", source_trial_id="other",
        focus_observation_id="other-obs", focus_task_id="other-task", batch_task_ids=("other-task",),
        family="PLANNING", failure_classes=("SEMANTIC_FAIL",), source_model_id="fake-model",
        source_model_digest="fake-digest", source_runtime={"provider": "fake"},
        inference_profile={}, inference_seed=2, partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=other_visible, state_hash="c" * 64, oracle_ref="oracle",
        expected_contract="plan", source_evidence_refs=("raw:other",),
    )
    replay.append(other)
    foreign = _outcome(replay, other, hypothesis, target, passed=True, suffix="foreign")
    with pytest.raises(ValueError, match="parent|state|family|lineage"):
        MechanismLocalizer(replay, causal).evaluate(
            fixture.failure_snapshot_id,
            tuple(r for r in replay.records() if isinstance(r, ReplayResult)) + (foreign,),
        )


def test_movement_and_mechanism_queries_are_event_derived_without_fixture_mutation(tmp_path):
    fixture, replay, _, _, _, _, assessment = _simple_pair(
        tmp_path, target_pass=True, sham_pass=False
    )
    mechanism_id = assessment.labels[0].mechanism_id
    assert [item.failure_snapshot_id for item in select_failures(
        replay, ReplaySelector(promotion_state=PromotionState.MOVEMENT)
    )] == [fixture.failure_snapshot_id]
    assert [item.failure_snapshot_id for item in select_failures(
        replay, ReplaySelector(mechanism=mechanism_id)
    )] == [fixture.failure_snapshot_id]
    assert replay.get_failure(fixture.failure_snapshot_id).promotion_state is PromotionState.UNASSESSED


def test_mechanism_graph_rebuild_is_byte_identical_and_hash_linked(tmp_path):
    _, replay, causal, _, _, _, _ = _simple_pair(
        tmp_path, target_pass=True, sham_pass=False
    )
    localizer = MechanismLocalizer(replay, causal)
    path = localizer.rebuild_graph()
    first = path.read_bytes()
    payload = json.loads(first)
    assert payload["header"]["test_replay_sha256"] == replay.manifest_path.read_text(encoding="ascii").strip()
    assert payload["header"]["causal_store_manifest_sha256"]
    path.unlink()
    second_path = localizer.rebuild_graph()
    assert second_path.read_bytes() == first
    assert replay.validate().ok
    assert any(isinstance(record, MechanismLabel) for record in replay.records())
    assert any(isinstance(record, PromotionEvent) for record in replay.records())
