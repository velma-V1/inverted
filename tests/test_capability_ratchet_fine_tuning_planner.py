from __future__ import annotations

from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.fine_tuning_analysis import FineTuningAnalyzer
from inverted.capability_ratchet.fine_tuning_core import (
    DatasetRole,
    FineTuningCandidate,
    FineTuningDataset,
    FineTuningDisposition,
    FineTuningExample,
)
from inverted.capability_ratchet.fine_tuning_planner import FineTuningPlanner


def _candidate() -> FineTuningCandidate:
    return FineTuningCandidate.create(
        stage8_candidate_id="stage8-1",
        mechanism_id="mechanism-1",
        failure_snapshot_ids=("failure-1", "failure-2"),
        generalization_evidence_refs=("profile-1",),
        tomography_assessment_refs=("assessment-1",),
        cheaper_owner_exclusions={"TOOL_POLICY": "falsified", "SKILL_POLICY": "falsified"},
        trigger_contract={"observable": "model residual"},
        allowed_region="r1-r3",
        negative_transfer_boundary=("direct solved",),
        source_hashes={"profile-1": "a" * 64},
        partition=Partition.HISTORICAL,
        base_model_profile_id="model-profile-1",
        regression_evidence_refs=("regression-1",),
        model_internal_residual=True,
        generalization_complete=True,
        cheaper_owners_resolved=True,
    )


def _dataset() -> FineTuningDataset:
    rows = (
        FineTuningExample.create(
            failure_snapshot_id="failure-1", replay_evidence_refs=("replay-1",),
            model_visible_input_ref="input-1", model_visible_input_hash="a" * 64,
            observable_target_ref="target-1", observable_target_hash="b" * 64,
            target_type="OBSERVABLE_CONTRACT_OUTPUT", role=DatasetRole.TRAIN,
            partition=Partition.HISTORICAL, base_model_profile_id="model-profile-1",
        ),
        FineTuningExample.create(
            failure_snapshot_id="failure-2", replay_evidence_refs=("replay-2",),
            model_visible_input_ref="input-2", model_visible_input_hash="c" * 64,
            observable_target_ref="target-2", observable_target_hash="d" * 64,
            target_type="OBSERVABLE_CONTRACT_OUTPUT", role=DatasetRole.EVAL,
            partition=Partition.HISTORICAL, base_model_profile_id="model-profile-1",
        ),
    )
    return FineTuningDataset.create(
        candidate_id=_candidate().candidate_id,
        examples=rows,
        regression_evidence_refs=("regression-1",),
        negative_transfer_refs=("negative-1",),
    )


def test_analyzer_qualifies_only_the_controlled_lane_not_training() -> None:
    qualification = FineTuningAnalyzer().analyze(candidate=_candidate(), dataset=_dataset())
    assert qualification.disposition is FineTuningDisposition.QUALIFY_CONTROLLED_LANE
    assert qualification.training_completed is False
    assert qualification.certified is False
    assert qualification.deployment_allowed is False
    assert qualification.stage11_confirmation_required is True


def test_planner_emits_bounded_not_authorized_zero_call_plan() -> None:
    qualification = FineTuningAnalyzer().analyze(candidate=_candidate(), dataset=_dataset())
    plan = FineTuningPlanner().plan(
        qualification=qualification,
        dataset=_dataset(),
        objective="repair recurrent model-internal failure",
        hyperparameter_envelope={"epochs": {"min": 1, "max": 3}, "learning_rate": {"min": 1e-6, "max": 1e-4}},
        physical_training_budget_ceiling=3,
        evaluation_refs=("eval-suite-1",),
        regression_refs=("regression-1",),
        abort_criteria=("protected regression", "evaluation collapse"),
        rollback_rule="discard tuned candidate and retain base model",
    )
    assert plan.authorization_status == "NOT_AUTHORIZED"
    assert plan.training_authorized is False
    assert plan.projected_development_model_calls == 0
    assert plan.stage11_confirmation_required is True
