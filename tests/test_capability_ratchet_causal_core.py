from __future__ import annotations

from inverted.capability_ratchet.causal_core import (
    ArchitectureOwner,
    CausalHypothesis,
    DivergenceClass,
    FirstDivergence,
)


def test_hypothesis_is_falsifiable_and_bound_to_failure() -> None:
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id="failure-1",
        parent_state_hash="a" * 64,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.CONTRACT_INTERFACE,
            observable_path="focus_observation.contract_pass",
            event_index=0,
            evidence_refs=("forensic:focus_observation",),
            confidence=1.0,
        ),
        owner_candidate=ArchitectureOwner.SYSTEM,
        claim="schema failure is independent of semantic reasoning",
        expected_if_true="a deterministic formatter repairs contract without cognition change",
        falsifier="formatter treatment fails while cognition treatment repairs the same state",
    )

    assert hypothesis.failure_snapshot_id == "failure-1"
    assert hypothesis.parent_state_hash == "a" * 64
    assert hypothesis.hypothesis_id.startswith("hyp-")
    assert hypothesis.divergence.observable_path == "focus_observation.contract_pass"
    assert hypothesis.falsifier.startswith("formatter treatment")

from inverted.capability_ratchet.causal_core import InterventionDefinition, InterventionKind


def test_intervention_is_bound_to_hypothesis_and_parent_state() -> None:
    intervention = InterventionDefinition.create(
        hypothesis_id="hyp-123",
        failure_snapshot_id="failure-1",
        parent_state_hash="b" * 64,
        kind=InterventionKind.PROMPT,
        label="constraint-emphasis",
        changed_dimensions=("request_envelopes.0.messages.0.content",),
        overrides={"request_envelopes.0.messages.0.content": "state constraints before answering"},
        expected_causal_implication="explicit constraints repair the failure",
        projected_physical_calls=1,
    )
    assert intervention.intervention_id.startswith("int-")
    assert intervention.hypothesis_id == "hyp-123"
    assert intervention.parent_state_hash == "b" * 64
    assert tuple(intervention.overrides) == intervention.changed_dimensions


def test_intervention_rejects_duplicate_changed_dimensions() -> None:
    import pytest

    with pytest.raises(ValueError, match="unique"):
        InterventionDefinition.create(
            hypothesis_id="hyp-123",
            failure_snapshot_id="failure-1",
            parent_state_hash="b" * 64,
            kind=InterventionKind.PROMPT,
            label="bad-duplicate",
            changed_dimensions=("request_envelopes.0.think", "request_envelopes.0.think"),
            overrides={"request_envelopes.0.think": True},
            expected_causal_implication="duplicate dimensions are invalid",
            projected_physical_calls=1,
        )

from inverted.capability_ratchet.core import (
    MechanismLabel,
    Partition,
    PromotionEvent,
    PromotionState,
    from_payload,
    to_payload,
)
from inverted.capability_ratchet.causal_core import MechanismRole


def test_mechanism_and_promotion_records_round_trip() -> None:
    label = MechanismLabel(
        mechanism_label_id="label-1",
        failure_snapshot_id="failure-1",
        parent_failure_snapshot_id="failure-1",
        parent_state_hash="c" * 64,
        mechanism_id="mechanism-dependency-representation",
        hypothesis_id="hyp-123",
        intervention_ids=("int-target", "int-sham"),
        role=MechanismRole.ENABLER,
        evidence_replay_result_ids=("result-target", "result-sham"),
        confidence=0.95,
    )
    event = PromotionEvent(
        promotion_event_id="promotion-1",
        failure_snapshot_id="failure-1",
        mechanism_id=label.mechanism_id,
        from_state=PromotionState.UNASSESSED,
        to_state=PromotionState.MOVEMENT,
        reason="target repaired the parent while matched sham failed",
        evidence_replay_result_ids=label.evidence_replay_result_ids,
        partition=Partition.HISTORICAL,
    )

    assert from_payload(to_payload(label)) == label
    assert from_payload(to_payload(event)) == event

from inverted.capability_ratchet.causal_core import HypothesisStatus


def test_hypothesis_defaults_active_and_can_mark_protected_exploration() -> None:
    hypothesis = CausalHypothesis.create(
        failure_snapshot_id="failure-protected",
        parent_state_hash="d" * 64,
        divergence=FirstDivergence(
            divergence_class=DivergenceClass.UNKNOWN_NOVEL,
            observable_path="focus_observation.failure_classes",
            event_index=0,
            evidence_refs=("forensic:focus_observation",),
            confidence=0.25,
        ),
        owner_candidate=ArchitectureOwner.MODEL,
        claim="the observed failure does not fit a known supported mechanism",
        expected_if_true="a protected alternative treatment changes the unresolved ownership decision",
        falsifier="registered alternatives fail to move the same parent state",
        protected_exploration=True,
    )
    assert hypothesis.status is HypothesisStatus.ACTIVE
    assert hypothesis.protected_exploration is True


def test_intervention_deep_freezes_override_payload_after_identity() -> None:
    path = "request_envelopes.0.messages.0.content"
    nested = {"instruction": ["preserve", "constraints"]}
    intervention = InterventionDefinition.create(
        hypothesis_id="hyp-deep-freeze",
        failure_snapshot_id="failure-deep-freeze",
        parent_state_hash="e" * 64,
        kind=InterventionKind.PROMPT,
        label="deep-freeze",
        changed_dimensions=(path,),
        overrides={path: nested},
        expected_causal_implication="intervention identity remains immutable after construction",
        projected_physical_calls=1,
    )
    nested["instruction"].append("mutated")
    assert intervention.overrides[path]["instruction"] == ("preserve", "constraints")
