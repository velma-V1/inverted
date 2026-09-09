from __future__ import annotations

from pathlib import Path

import pytest

from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.tomography_core import (
    TomographyAxis,
    TomographyDisposition,
    TomographyOutcome,
    TomographyProbeSpec,
    TomographyAssessment,
    TomographyStatus,
    TomographyStudy,
)
from inverted.capability_ratchet.tomography_store import TomographyEvidenceStore

SHA = "a" * 64


def _study(*, partition: Partition = Partition.DEVELOPMENT) -> TomographyStudy:
    return TomographyStudy(
        study_id="study-1",
        failure_snapshot_id="failure-root",
        parent_state_hash=SHA,
        partition=partition,
        decision_ids=("D6",),
        candidate_axes=(TomographyAxis.TOOL_AVAILABILITY,),
        baseline_evidence_refs=("result-baseline",),
        probe_ids=("probe-1",),
        max_new_probes=3,
        projected_calls=1,
        status=TomographyStatus.PLANNED,
    )


def _probe() -> TomographyProbeSpec:
    return TomographyProbeSpec(
        probe_id="probe-1",
        study_id="study-1",
        axis=TomographyAxis.TOOL_AVAILABILITY,
        intervention_id="intervention-1",
        control_intervention_id=None,
        changed_dimensions=("request_envelopes.0.tools",),
        expected_implication="tool availability isolates ownership",
        projected_calls=1,
        protected=False,
    )


def _outcome() -> TomographyOutcome:
    return TomographyOutcome(
        outcome_id="outcome-1",
        study_id="study-1",
        probe_id="probe-1",
        replay_result_id="result-probe-1",
        semantic_success=True,
        contract_valid=True,
        score=1.0,
        first_divergence=None,
        comparison_refs=("result-baseline",),
        protected_regression=False,
    )


def _assessment(*, profile_id: str = "assessment-1", disposition=TomographyDisposition.TOOL_REQUIRED) -> TomographyAssessment:
    return TomographyAssessment(
        profile_id=profile_id,
        study_id="study-1",
        dispositions=(disposition,),
        supported_hypotheses=("stage7:TOOL_REQUIRED",),
        falsified_hypotheses=(),
        evidence_refs=("result-probe-1",),
        next_decisions=("D6",),
        route_back_stage=None,
        model_internal_boundary=False,
        promotion_allowed=False,
        certification_allowed=False,
    )


def _store(tmp_path: Path, *, missing_failure: str | None = None, missing_result: str | None = None, state_matches: bool = True):
    return TomographyEvidenceStore(
        tmp_path,
        failure_snapshot_exists=lambda value: value != missing_failure,
        replay_result_exists=lambda value: value != missing_result,
        failure_snapshot_state_matches=lambda failure_id, parent_hash, partition: state_matches,
    )


def _populate(store: TomographyEvidenceStore) -> None:
    store.append_study(_study())
    store.append_probe(_probe())
    store.append_outcome(_outcome())
    store.append_assessment(_assessment())


def test_store_uses_corrected_split_ledgers_and_manifest_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _populate(store)

    assert {path.name for path in tmp_path.iterdir()} == {
        "tomography-studies.jsonl",
        "tomography-outcomes.jsonl",
        "tomography-assessments.jsonl",
        "SHA256SUMS.csv",
    }
    assert "TOMOGRAPHY_STUDY" in (tmp_path / "tomography-studies.jsonl").read_text(encoding="utf-8")
    assert "TOMOGRAPHY_PROBE" in (tmp_path / "tomography-studies.jsonl").read_text(encoding="utf-8")
    assert "TOMOGRAPHY_OUTCOME" in (tmp_path / "tomography-outcomes.jsonl").read_text(encoding="utf-8")
    assert "TOMOGRAPHY_PROFILE" in (tmp_path / "tomography-assessments.jsonl").read_text(encoding="utf-8")
    manifest = (tmp_path / "SHA256SUMS.csv").read_text(encoding="utf-8")
    assert manifest.count("tomography-") == 3

    report = store.validate()
    assert report.ok
    assert report.record_count == 4
    assert report.manifest_errors == ()


def test_manifest_detects_tampering_and_append_cannot_launder_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _populate(store)
    outcomes = tmp_path / "tomography-outcomes.jsonl"
    outcomes.write_text(outcomes.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")

    report = store.validate()
    assert not report.ok
    assert any("tomography-outcomes.jsonl" in item for item in report.manifest_errors)
    with pytest.raises(ValueError, match="manifest"):
        store.append_assessment(_assessment(profile_id="assessment-2"))


def test_validation_checks_root_failure_parent_state_and_canonical_replay_refs(tmp_path: Path) -> None:
    missing_root = _store(tmp_path / "missing-root", missing_failure="failure-root")
    _populate(missing_root)
    report = missing_root.validate()
    assert not report.ok
    assert "missing-root-failure:failure-root" in report.broken_references

    bad_state = _store(tmp_path / "bad-state", state_matches=False)
    _populate(bad_state)
    report = bad_state.validate()
    assert not report.ok
    assert "failure-state-mismatch:failure-root" in report.broken_references

    missing_replay = _store(tmp_path / "missing-replay", missing_result="result-probe-1")
    _populate(missing_replay)
    report = missing_replay.validate()
    assert not report.ok
    assert "missing-replay-result:result-probe-1" in report.broken_references


def test_store_rejects_protected_partition_contamination(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="protected partition"):
        store.append_study(_study(partition=Partition.FRESH))
    with pytest.raises(ValueError, match="protected partition"):
        store.append_study(_study(partition=Partition.SEALED))


def test_logical_ids_are_immutable_and_conclusions_cannot_be_silently_rewritten(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _populate(store)
    with pytest.raises(ValueError, match="duplicate"):
        store.append_probe(_probe())

    conflicting = _assessment(disposition=TomographyDisposition.UNRESOLVED)
    with pytest.raises(ValueError, match="duplicate"):
        store.append_assessment(conflicting)


def test_legacy_profile_api_is_read_only_compatibility_alias(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _populate(store)
    assert store.assessments() == store.profiles()
    assert store.path == store.studies_path
