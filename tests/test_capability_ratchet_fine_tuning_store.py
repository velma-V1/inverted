from __future__ import annotations

import json

import pytest

from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.fine_tuning_core import FineTuningCandidate
from inverted.capability_ratchet.fine_tuning_store import FineTuningEvidenceStore


def _candidate() -> FineTuningCandidate:
    return FineTuningCandidate.create(
        stage8_candidate_id="stage8-1", mechanism_id="mechanism-1",
        failure_snapshot_ids=("failure-1", "failure-2"),
        generalization_evidence_refs=("profile-1",), tomography_assessment_refs=("assessment-1",),
        cheaper_owner_exclusions={"TOOL_POLICY": "falsified"},
        trigger_contract={"observable": "model residual"}, allowed_region="r1-r3",
        negative_transfer_boundary=("direct solved",), source_hashes={"profile-1": "a" * 64},
        partition=Partition.HISTORICAL, base_model_profile_id="model-profile-1",
        regression_evidence_refs=("regression-1",), model_internal_residual=True,
        generalization_complete=True, cheaper_owners_resolved=True,
    )


def test_store_is_append_only_idempotent_and_manifested(tmp_path) -> None:
    store = FineTuningEvidenceStore(tmp_path)
    candidate = _candidate()
    assert store.append_candidate(candidate) == candidate.candidate_id
    assert store.append_candidate(candidate) == candidate.candidate_id
    assert store.candidates() == (candidate,)
    validation = store.validate()
    assert validation.ok
    assert validation.candidate_count == 1
    assert store.manifest_path.exists()


def test_store_refuses_append_after_manifest_tamper(tmp_path) -> None:
    store = FineTuningEvidenceStore(tmp_path)
    candidate = _candidate()
    store.append_candidate(candidate)
    store.candidate_path.write_text(store.candidate_path.read_text(encoding="utf-8") + json.dumps({"candidate_id": "tamper"}) + "\n", encoding="utf-8")
    assert store.validate().ok is False
    with pytest.raises(ValueError, match="manifest|integrity"):
        store.append_candidate(candidate)
