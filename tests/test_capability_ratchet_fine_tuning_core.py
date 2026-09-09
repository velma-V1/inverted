from __future__ import annotations

import math

import pytest

from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.fine_tuning_core import (
    ControlledTuningPlan,
    DatasetRole,
    FineTuningCandidate,
    FineTuningDataset,
    FineTuningDisposition,
    FineTuningEligibilityStatus,
    FineTuningExample,
    FineTuningPlanStatus,
    FineTuningPolicy,
    FineTuningQualification,
)


def _candidate(**overrides) -> FineTuningCandidate:
    values = dict(
        stage8_candidate_id="compilation-candidate-1",
        mechanism_id="mechanism-1",
        failure_snapshot_ids=("failure-1", "failure-2"),
        generalization_evidence_refs=("profile-1",),
        tomography_assessment_refs=("assessment-1",),
        cheaper_owner_exclusions={"TOOL_POLICY": "tool ownership falsified", "VERIFIER_RECOVERY_POLICY": "verifier ownership falsified"},
        trigger_contract={"observable_failure_class": "MODEL_INTERNAL_RESIDUAL"},
        allowed_region="generalized region r1-r3",
        negative_transfer_boundary=("direct-solved cases",),
        source_hashes={"profile-1": "a" * 64, "assessment-1": "b" * 64},
        partition=Partition.HISTORICAL,
        base_model_profile_id="qwen-profile-1",
        regression_evidence_refs=("regression-1",),
        model_internal_residual=True,
        generalization_complete=True,
        cheaper_owners_resolved=True,
    )
    values.update(overrides)
    return FineTuningCandidate.create(**values)


def _example(failure: str, role: DatasetRole, suffix: str) -> FineTuningExample:
    return FineTuningExample.create(
        failure_snapshot_id=failure,
        replay_evidence_refs=(f"replay-{suffix}",),
        model_visible_input_ref=f"model-visible-{suffix}",
        model_visible_input_hash=(suffix * 64)[:64],
        observable_target_ref=f"target-{suffix}",
        observable_target_hash=(("f" if suffix == "a" else "e") * 64),
        target_type="OBSERVABLE_CONTRACT_OUTPUT",
        role=role,
        partition=Partition.HISTORICAL,
        base_model_profile_id="qwen-profile-1",
    )


def test_stage9_vocabulary_does_not_encode_promotion() -> None:
    assert {x.value for x in FineTuningDisposition}.isdisjoint({"MOVEMENT", "TIER_CANDIDATE", "CERTIFIED"})
    assert FineTuningEligibilityStatus.ELIGIBLE.value == "ELIGIBLE"
    assert FineTuningPlanStatus.PLANNED.value == "PLANNED"


def test_policy_is_conservative_zero_call_d11_gate() -> None:
    policy = FineTuningPolicy()
    assert policy.schema_version == "v3-stage9-v1"
    assert policy.decision_id == "D11"
    assert policy.minimum_independent_failures == 2
    assert policy.development_model_call_budget == 0
    assert policy.certification_allowed is False
    assert policy.deployment_allowed is False
    assert policy.training_authorized_by_default is False


def test_candidate_is_content_addressed_and_rejects_unearned_tuning() -> None:
    assert _candidate().candidate_id == _candidate().candidate_id
    with pytest.raises(ValueError, match="independent|recurrence"):
        _candidate(failure_snapshot_ids=("failure-1",))
    with pytest.raises(ValueError, match="model.internal|MODEL_INTERNAL"):
        _candidate(model_internal_residual=False)
    with pytest.raises(ValueError, match="cheaper"):
        _candidate(cheaper_owners_resolved=False)
    with pytest.raises(ValueError, match="generalization"):
        _candidate(generalization_complete=False)
    with pytest.raises(ValueError, match="FRESH|SEALED|protected"):
        _candidate(partition=Partition.FRESH)


def test_candidate_rejects_oracle_raw_thinking_and_nonfinite_metadata() -> None:
    with pytest.raises(ValueError, match="oracle|thinking|raw"):
        _candidate(trigger_contract={"oracle_answer": "42"})
    with pytest.raises(TypeError, match="finite"):
        _candidate(trigger_contract={"threshold": math.inf})


def test_dataset_requires_disjoint_train_eval_lineage_and_hashes() -> None:
    candidate = _candidate()
    train = _example("failure-1", DatasetRole.TRAIN, "a")
    eval_row = _example("failure-2", DatasetRole.EVAL, "b")
    dataset = FineTuningDataset.create(
        candidate_id=candidate.candidate_id,
        examples=(train, eval_row),
        regression_evidence_refs=("regression-1",),
        negative_transfer_refs=("negative-1",),
    )
    assert dataset.dataset_id
    assert dataset.dataset_hash
    assert dataset.train_example_ids == (train.example_id,)
    assert dataset.eval_example_ids == (eval_row.example_id,)

    duplicate_lineage = FineTuningExample.create(
        failure_snapshot_id="failure-1",
        replay_evidence_refs=("replay-b",),
        model_visible_input_ref="model-visible-b",
        model_visible_input_hash="c" * 64,
        observable_target_ref="target-b",
        observable_target_hash="d" * 64,
        target_type="OBSERVABLE_CONTRACT_OUTPUT",
        role=DatasetRole.EVAL,
        partition=Partition.HISTORICAL,
        base_model_profile_id="qwen-profile-1",
    )
    with pytest.raises(ValueError, match="train.*eval|disjoint|lineage"):
        FineTuningDataset.create(
            candidate_id=candidate.candidate_id,
            examples=(train, duplicate_lineage),
            regression_evidence_refs=("regression-1",),
            negative_transfer_refs=("negative-1",),
        )


def test_example_rejects_protected_partition_and_forbidden_target_type() -> None:
    with pytest.raises(ValueError, match="FRESH|SEALED|protected"):
        FineTuningExample.create(
            failure_snapshot_id="failure-1",
            replay_evidence_refs=("replay-1",),
            model_visible_input_ref="input-1",
            model_visible_input_hash="a" * 64,
            observable_target_ref="target-1",
            observable_target_hash="b" * 64,
            target_type="OBSERVABLE_CONTRACT_OUTPUT",
            role=DatasetRole.TRAIN,
            partition=Partition.SEALED,
            base_model_profile_id="qwen-profile-1",
        )
    with pytest.raises(ValueError, match="hidden|reasoning|oracle|target"):
        FineTuningExample.create(
            failure_snapshot_id="failure-1",
            replay_evidence_refs=("replay-1",),
            model_visible_input_ref="input-1",
            model_visible_input_hash="a" * 64,
            observable_target_ref="target-1",
            observable_target_hash="b" * 64,
            target_type="HIDDEN_CHAIN_OF_THOUGHT",
            role=DatasetRole.TRAIN,
            partition=Partition.HISTORICAL,
            base_model_profile_id="qwen-profile-1",
        )


def test_qualification_and_plan_never_mean_trained_certified_or_deployed() -> None:
    candidate = _candidate()
    dataset = FineTuningDataset.create(
        candidate_id=candidate.candidate_id,
        examples=(_example("failure-1", DatasetRole.TRAIN, "a"), _example("failure-2", DatasetRole.EVAL, "b")),
        regression_evidence_refs=("regression-1",),
        negative_transfer_refs=("negative-1",),
    )
    qualification = FineTuningQualification.create(
        candidate_id=candidate.candidate_id,
        disposition=FineTuningDisposition.QUALIFY_CONTROLLED_LANE,
        evidence_refs=("profile-1", "assessment-1"),
        dataset_id=dataset.dataset_id,
        unresolved_risks=(),
        route="CONTROLLED_LANE",
    )
    assert qualification.training_completed is False
    assert qualification.certified is False
    assert qualification.deployment_allowed is False

    plan = ControlledTuningPlan.create(
        qualification_id=qualification.qualification_id,
        dataset_id=dataset.dataset_id,
        base_model_profile_id="qwen-profile-1",
        objective="reduce recurrent model-internal contract failure",
        hyperparameter_envelope={"epochs": {"min": 1, "max": 3}},
        physical_training_budget_ceiling=3,
        evaluation_refs=("eval-suite-1",),
        regression_refs=("regression-1",),
        abort_criteria=("protected regression",),
        rollback_rule="discard tuned candidate",
    )
    assert plan.authorization_status == "NOT_AUTHORIZED"
    assert plan.projected_development_model_calls == 0
    assert plan.training_authorized is False
    assert plan.stage11_confirmation_required is True
