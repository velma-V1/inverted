from __future__ import annotations

import pytest

from inverted.test3_s0_types import (
    CounterfactualStatus,
    EvidenceState,
    FeatureProvenance,
    ZeroModelCallGuard,
)


def test_counterfactual_status_is_exhaustive():
    assert {x.value for x in CounterfactualStatus} == {
        "CAUSAL_REPLAY",
        "REQUIRES_NEW_INFERENCE",
        "INVALID_COUNTERFACTUAL",
    }


def test_section0_refuses_any_physical_model_call():
    guard = ZeroModelCallGuard()
    with pytest.raises(RuntimeError, match="Section 0 permits zero physical model calls"):
        guard.consume("forbidden")
    assert guard.physical_calls == 0


def test_feature_provenance_preserves_temporal_dependency_metadata():
    feature = FeatureProvenance(
        feature_name="failure_signature",
        observed_at_transition=3,
        derived_at_transition=3,
        source_event_ids=("event-1", "event-2"),
        depends_on=("candidate_text",),
        available_before_action=True,
        contains_post_action_dependency=False,
    )
    state = EvidenceState(
        task_id="task-1",
        feature_provenance=(feature,),
    )
    assert state.feature_provenance[0].available_before_action is True
    assert state.feature_provenance[0].contains_post_action_dependency is False
    assert state.feature_provenance[0].depends_on == ("candidate_text",)
