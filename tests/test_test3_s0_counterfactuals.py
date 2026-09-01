from __future__ import annotations

from inverted.test3_s0_counterfactuals import classify_counterfactual
from inverted.test3_s0_types import CounterfactualStatus, FeatureProvenance


def test_recomposition_of_observed_outputs_is_causal_replay():
    result = classify_counterfactual(False, False, False, False, True, True)
    assert result.status is CounterfactualStatus.CAUSAL_REPLAY


def test_prompt_changing_repair_requires_new_inference():
    result = classify_counterfactual(True, True, False, False, True, True)
    assert result.status is CounterfactualStatus.REQUIRES_NEW_INFERENCE


def test_hidden_gold_router_is_invalid():
    result = classify_counterfactual(False, False, True, False, True, True)
    assert result.status is CounterfactualStatus.INVALID_COUNTERFACTUAL


def test_post_action_feature_dependency_is_invalid_even_when_field_name_is_legal():
    feature = FeatureProvenance(
        feature_name="failure_signature",
        available_before_action=True,
        contains_post_action_dependency=True,
        depends_on=("final_candidate",),
    )
    result = classify_counterfactual(
        False,
        False,
        False,
        False,
        True,
        True,
        feature_provenance=(feature,),
    )
    assert result.status is CounterfactualStatus.INVALID_COUNTERFACTUAL
    assert "post-action" in result.reason.lower()


def test_missing_temporal_availability_is_not_silently_treated_as_safe():
    feature = FeatureProvenance(
        feature_name="retrieval_score",
        available_before_action=None,
        contains_post_action_dependency=None,
    )
    result = classify_counterfactual(
        False,
        False,
        False,
        False,
        True,
        True,
        feature_provenance=(feature,),
    )
    assert result.status is CounterfactualStatus.INVALID_COUNTERFACTUAL
    assert "temporal" in result.reason.lower()
