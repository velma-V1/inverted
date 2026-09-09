from __future__ import annotations

import pytest

from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.fine_tuning_core import DatasetRole, FineTuningCandidate, FineTuningExample
from inverted.capability_ratchet.fine_tuning_dataset import FineTuningDatasetCompiler


def _candidate() -> FineTuningCandidate:
    return FineTuningCandidate.create(
        stage8_candidate_id="stage8-1",
        mechanism_id="mechanism-1",
        failure_snapshot_ids=("failure-1", "failure-2"),
        generalization_evidence_refs=("profile-1",),
        tomography_assessment_refs=("assessment-1",),
        cheaper_owner_exclusions={"TOOL_POLICY": "falsified"},
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


def _example(failure: str, role: DatasetRole, input_hash: str, target_hash: str) -> FineTuningExample:
    return FineTuningExample.create(
        failure_snapshot_id=failure,
        replay_evidence_refs=(f"replay-{failure}",),
        model_visible_input_ref=f"input-{failure}",
        model_visible_input_hash=input_hash,
        observable_target_ref=f"target-{failure}",
        observable_target_hash=target_hash,
        target_type="OBSERVABLE_CONTRACT_OUTPUT",
        role=role,
        partition=Partition.HISTORICAL,
        base_model_profile_id="model-profile-1",
    )


def test_compiler_is_deterministic_and_requires_regression_and_negative_transfer() -> None:
    compiler = FineTuningDatasetCompiler()
    train = _example("failure-1", DatasetRole.TRAIN, "a" * 64, "b" * 64)
    eval_row = _example("failure-2", DatasetRole.EVAL, "c" * 64, "d" * 64)
    left = compiler.compile(
        candidate=_candidate(),
        examples=(train, eval_row),
        regression_evidence_refs=("regression-1",),
        negative_transfer_refs=("negative-1",),
    )
    right = compiler.compile(
        candidate=_candidate(),
        examples=(eval_row, train),
        regression_evidence_refs=("regression-1",),
        negative_transfer_refs=("negative-1",),
    )
    assert left.dataset_hash == right.dataset_hash
    assert left.dataset_id == right.dataset_id
    with pytest.raises(ValueError, match="regression"):
        compiler.compile(candidate=_candidate(), examples=(train, eval_row), regression_evidence_refs=(), negative_transfer_refs=("negative-1",))
    with pytest.raises(ValueError, match="negative"):
        compiler.compile(candidate=_candidate(), examples=(train, eval_row), regression_evidence_refs=("regression-1",), negative_transfer_refs=())


def test_compiler_rejects_cross_split_content_hash_leakage() -> None:
    compiler = FineTuningDatasetCompiler()
    train = _example("failure-1", DatasetRole.TRAIN, "a" * 64, "b" * 64)
    leaked = _example("failure-2", DatasetRole.EVAL, "a" * 64, "d" * 64)
    with pytest.raises(ValueError, match="hash|leak|disjoint"):
        compiler.compile(
            candidate=_candidate(),
            examples=(train, leaked),
            regression_evidence_refs=("regression-1",),
            negative_transfer_refs=("negative-1",),
        )
