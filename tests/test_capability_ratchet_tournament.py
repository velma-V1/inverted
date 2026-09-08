from __future__ import annotations

from inverted.capability_ratchet import FailureFixture, Partition
from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
    InterventionDefinition,
    InterventionKind,
)
from inverted.capability_ratchet.causal_store import CausalEvidenceStore
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.tournament import TournamentPlanner, build_ablations


def _fixture(tmp_path):
    replay = ReplayStore(tmp_path / "replay")
    visible = replay.put_asset({
        "request_envelopes": [{
            "model": "model",
            "stream": False,
            "think": False,
            "options": {"seed": 3, "temperature": 0.7, "num_predict": 128},
            "messages": [{"role": "user", "content": "Build the dependency-safe plan."}],
        }]
    })
    fixture = FailureFixture(
        failure_snapshot_id="failure-tournament",
        source_campaign_id="campaign",
        source_trial_id="trial",
        focus_observation_id="obs",
        focus_task_id="task",
        batch_task_ids=("task",),
        family="PLANNING",
        failure_classes=("SEMANTIC_FAIL",),
        source_model_id="model",
        source_model_digest="digest",
        source_runtime={"provider": "fake"},
        inference_profile={"temperature": 0.7},
        inference_seed=3,
        partition=Partition.DEVELOPMENT,
        model_visible_asset_sha256=visible,
        state_hash="8" * 64,
        oracle_ref="oracle",
        expected_contract="plan",
        source_evidence_refs=("raw:1",),
    )
    replay.append(fixture)
    return replay.get_failure(fixture.failure_snapshot_id), replay


def _hypothesis(fixture, suffix, *, protected=False, decision_changes=True):
    expected = f"target-{suffix}-repairs-parent"
    falsifier = f"target-{suffix}-fails-while-alternative-wins" if decision_changes else expected
    return CausalHypothesis.create(
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.MISSING_DEPENDENCY,
            observable_path="focus_observation.semantic_pass",
            event_index=0,
            evidence_refs=(f"evidence:{suffix}",),
            confidence=0.8,
        ),
        owner_candidate=ArchitectureOwner.SYSTEM,
        claim=f"dependency hypothesis {suffix}",
        expected_if_true=expected,
        falsifier=falsifier,
        protected_exploration=protected,
    )


def _target(fixture, hypothesis, suffix, *, protected=False):
    path = "request_envelopes.0.messages.0.content"
    return InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        kind=InterventionKind.REPRESENTATION,
        label=f"target-{suffix}",
        changed_dimensions=(path,),
        overrides={path: f"dependency treatment {suffix}"},
        expected_causal_implication=hypothesis.expected_if_true,
        protected_exploration=protected,
    )


def _sham(fixture, hypothesis, target):
    path = target.changed_dimensions[0]
    return InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        kind=InterventionKind.SHAM,
        label=f"sham-{target.label}",
        changed_dimensions=(path,),
        overrides={path: "matched neutral control"},
        expected_causal_implication="matched control should not reproduce causal gain",
        sham_for=target.intervention_id,
        protected_exploration=target.protected_exploration,
    )


def _case(tmp_path, *, protected_second=False, second_changes=True):
    fixture, replay = _fixture(tmp_path)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    h1 = _hypothesis(fixture, "one")
    h2 = _hypothesis(
        fixture, "two", protected=protected_second, decision_changes=second_changes
    )
    for hypothesis in (h1, h2):
        causal.append_hypothesis(hypothesis)
    t1 = _target(fixture, h1, "one")
    t2 = _target(fixture, h2, "two", protected=protected_second)
    s1 = _sham(fixture, h1, t1)
    s2 = _sham(fixture, h2, t2)
    for intervention in (t1, s1, t2, s2):
        causal.register_intervention(intervention)
    return fixture, causal, (h1, h2), (t1, s1, t2, s2)


def test_known_reproducibility_does_not_add_redundant_exact_replay(tmp_path) -> None:
    fixture, causal, hypotheses, interventions = _case(tmp_path)
    plan = TournamentPlanner(causal).plan(
        fixture, hypotheses, interventions, reproducibility_known=True
    )
    assert all(branch.mode != "EXACT" for branch in plan.branches)


def test_unknown_reproducibility_adds_one_decision_reasoned_exact_probe(tmp_path) -> None:
    fixture, causal, hypotheses, interventions = _case(tmp_path)
    plan = TournamentPlanner(causal).plan(
        fixture, hypotheses, interventions, reproducibility_known=False
    )
    exact = [branch for branch in plan.branches if branch.mode == "EXACT"]
    assert len(exact) == 1
    assert exact[0].intervention_ids == ()
    assert exact[0].projected_physical_calls == 1
    assert "reproduc" in exact[0].decision_reason.lower()


def test_one_target_per_live_hypothesis_precedes_redundant_variants_and_keeps_shams(tmp_path) -> None:
    fixture, causal, hypotheses, interventions = _case(tmp_path)
    plan = TournamentPlanner(causal).plan(
        fixture, hypotheses, interventions, max_branches=8
    )
    target_branches = [branch for branch in plan.branches if branch.mode == "TARGET"]
    sham_branches = [branch for branch in plan.branches if branch.mode == "SHAM"]
    assert len(target_branches) == len(hypotheses)
    assert len(sham_branches) == len(hypotheses)
    assert {branch.hypothesis_id for branch in target_branches} == {
        hypothesis.hypothesis_id for hypothesis in hypotheses
    }
    assert all(branch.unresolved_decision for branch in plan.branches)


def test_protected_exploration_survives_branch_pruning(tmp_path) -> None:
    fixture, causal, hypotheses, interventions = _case(tmp_path, protected_second=True)
    plan = TournamentPlanner(causal).plan(
        fixture, hypotheses, interventions, max_branches=2
    )
    assert len(plan.branches) == 2
    assert any(branch.protected_exploration for branch in plan.branches)
    protected_id = hypotheses[1].hypothesis_id
    assert any(branch.hypothesis_id == protected_id for branch in plan.branches)


def test_non_decision_changing_hypothesis_is_rejected(tmp_path) -> None:
    fixture, causal, hypotheses, interventions = _case(tmp_path, second_changes=False)
    plan = TournamentPlanner(causal).plan(
        fixture, hypotheses, interventions, max_branches=8
    )
    rejected_id = hypotheses[1].hypothesis_id
    assert not any(branch.hypothesis_id == rejected_id for branch in plan.branches)
    assert rejected_id in plan.rejected_hypothesis_ids


def test_call_geometry_is_explicit_and_bounded_by_selected_branches(tmp_path) -> None:
    fixture, causal, hypotheses, interventions = _case(tmp_path)
    plan = TournamentPlanner(causal).plan(fixture, hypotheses, interventions)
    selected_calls = sum(branch.projected_physical_calls for branch in plan.branches)
    assert 0 <= plan.minimum_physical_calls <= plan.expected_physical_calls <= plan.worst_case_physical_calls
    assert plan.worst_case_physical_calls == selected_calls


def test_compound_success_generates_leave_one_out_and_sham_not_power_set() -> None:
    compound = InterventionDefinition.create(
        hypothesis_id="hyp-compound",
        failure_snapshot_id="failure-compound",
        parent_state_hash="9" * 64,
        kind=InterventionKind.REPRESENTATION,
        label="A+B+C",
        changed_dimensions=("request_envelopes.0.messages.0.content",),
        overrides={"request_envelopes.0.messages.0.content": "compound treatment"},
        expected_causal_implication="compound repairs the parent",
        composition=("A", "B", "C"),
    )
    plan = build_ablations(compound, ("A", "B", "C"))
    assert {item.ablates for item in plan if item.kind is InterventionKind.ABLATION} == {
        ("A",), ("B",), ("C",)
    }
    assert sum(item.kind is InterventionKind.SHAM for item in plan) == 1
    assert len(plan) == 4


def test_reanchoring_recurrence_sequence_is_preserved_in_branch_geometry(tmp_path) -> None:
    fixture, replay = _fixture(tmp_path)
    causal = CausalEvidenceStore(tmp_path / "causal", replay_store=replay)
    hypothesis = _hypothesis(fixture, "reanchor", protected=True)
    causal.append_hypothesis(hypothesis)
    compound = InterventionDefinition.create(
        hypothesis_id=hypothesis.hypothesis_id,
        failure_snapshot_id=fixture.failure_snapshot_id,
        parent_state_hash=fixture.state_hash,
        kind=InterventionKind.DELIVERY,
        label="A+B+A re-anchor",
        changed_dimensions=("request_envelopes.0.messages.0.content",),
        overrides={"request_envelopes.0.messages.0.content": "re-anchor sequence"},
        expected_causal_implication=hypothesis.expected_if_true,
        composition=("A", "B", "A"),
        protected_exploration=True,
    )
    causal.register_intervention(compound)
    plan = TournamentPlanner(causal).plan(
        fixture, (hypothesis,), (compound,), max_branches=2
    )
    branch = next(branch for branch in plan.branches if branch.mode == "TARGET")
    assert branch.intervention_ids == ("A", "B", "A")
