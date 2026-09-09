from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from inverted.capability_ratchet.compilation_core import (
    CompilationEligibilityStatus,
    CompilationKind,
)
from inverted.capability_ratchet.compilation_eligibility import (
    CompilationEligibilityScanner,
    plan_eligible_compilation,
)
from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.mutation_core import GeneralizationClass
from inverted.capability_ratchet.tomography_core import TomographyDisposition


@dataclass(frozen=True)
class _Validation:
    ok: bool = True


@dataclass(frozen=True)
class _Failure:
    failure_snapshot_id: str
    partition: Partition


@dataclass(frozen=True)
class _Label:
    mechanism_label_id: str
    failure_snapshot_id: str
    mechanism_id: str
    evidence_replay_result_ids: tuple[str, ...] = ("result-1",)


@dataclass(frozen=True)
class _Profile:
    profile_id: str
    failure_snapshot_id: str
    mechanism_id: str
    classification: GeneralizationClass
    metadata: dict = field(default_factory=dict)
    protected_failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Study:
    study_id: str
    failure_snapshot_id: str
    partition: Partition


@dataclass(frozen=True)
class _Assessment:
    profile_id: str
    study_id: str
    dispositions: tuple[TomographyDisposition, ...]
    route_back_stage: str | None = "stage4"


@dataclass(frozen=True)
class _Compiled:
    mechanism_id: str


class _ReplayStore:
    def __init__(self, failures=(), labels=()) -> None:
        self._failures = {item.failure_snapshot_id: item for item in failures}
        self._labels = tuple(labels)

    def validate(self):
        return _Validation()

    def get_failure(self, failure_snapshot_id: str):
        if failure_snapshot_id not in self._failures:
            raise KeyError(failure_snapshot_id)
        return self._failures[failure_snapshot_id]

    def records(self):
        return self._labels


class _MutationStore:
    def __init__(self, profiles=()) -> None:
        self._profiles = tuple(profiles)

    def validate(self):
        return _Validation()

    def profiles(self):
        return self._profiles


class _CompilationStore:
    def __init__(self, capabilities=()) -> None:
        self._capabilities = tuple(capabilities)

    def validate(self):
        return _Validation()

    def capabilities(self):
        return self._capabilities


class _TomographyStore:
    def __init__(self, studies=(), assessments=()) -> None:
        self._studies = tuple(studies)
        self._assessments = tuple(assessments)

    def validate(self):
        return _Validation()

    def studies(self):
        return self._studies

    def assessments(self):
        return self._assessments


def _contract(**updates):
    value = {
        "mechanism_label_ids": ["label-1"],
        "evidence_refs": ["result-1", "profile-1"],
        "source_hashes": {"profile-1": "a" * 64},
        "supported_kinds": [CompilationKind.TOOL_POLICY.value],
        "excluded_cheaper_kinds": {
            CompilationKind.DETERMINISTIC_RULE.value: "not deterministic",
            CompilationKind.STATE_REPRESENTATION.value: "state already complete",
            CompilationKind.FORMATTER_PARSER_VALIDATOR.value: "not an interface failure",
        },
        "trigger_contract": {"tool_eligible": True},
        "compiled_payload": {"allowed_tool": "calculator"},
        "verifier_contract": {"postcondition": "result parses"},
        "negative_transfer_boundary": ["direct-solved cases remain direct"],
        "tested_region": "tool-eligible arithmetic region",
        "rollback_action": "DISABLE",
        "tomography_assessment_id": "assessment-1",
    }
    value.update(updates)
    return {"compilation": value}


def _scanner(*, classification=GeneralizationClass.REGION_MECHANISM, metadata=None, partition=Partition.HISTORICAL,
             profiles=True, tomography_store=None, capabilities=(), protected_failures=()):
    failure = _Failure("failure-1", partition)
    label = _Label("label-1", "failure-1", "mechanism-1")
    profile = _Profile(
        "profile-1",
        "failure-1",
        "mechanism-1",
        classification,
        _contract() if metadata is None else metadata,
        protected_failures,
    )
    return CompilationEligibilityScanner(
        replay_store=_ReplayStore((failure,), (label,)),
        mutation_store=_MutationStore((profile,) if profiles else ()),
        compilation_store=_CompilationStore(capabilities),
        tomography_store=tomography_store,
    )


@pytest.mark.parametrize(
    "classification",
    [
        GeneralizationClass.LOCAL_MECHANISM,
        GeneralizationClass.REGION_MECHANISM,
        GeneralizationClass.CROSS_REGION_MECHANISM,
        GeneralizationClass.PROMOTION_CANDIDATE,
    ],
)
def test_generalized_profiles_with_complete_contract_are_eligible(classification) -> None:
    rows = _scanner(classification=classification).scan()
    assert len(rows) == 1
    row = rows[0]
    assert row.status is CompilationEligibilityStatus.ELIGIBLE
    assert row.candidate is not None
    assert row.candidate.generalization_class is classification
    assert row.candidate.mechanism_id == "mechanism-1"
    assert row.model_calls == 0


def test_instance_patch_is_never_eligible() -> None:
    row = _scanner(classification=GeneralizationClass.INSTANCE_PATCH).scan()[0]
    assert row.status is CompilationEligibilityStatus.INSTANCE_PATCH
    assert row.candidate is None


def test_missing_generalization_profile_is_reported_from_canonical_mechanism_label() -> None:
    row = _scanner(profiles=False).scan()[0]
    assert row.status is CompilationEligibilityStatus.MISSING_GENERALIZATION
    assert row.mechanism_id == "mechanism-1"
    assert row.candidate is None


def test_stage7_only_result_routes_back_to_stage456() -> None:
    tomography = _TomographyStore(
        studies=(_Study("study-7", "failure-1", Partition.HISTORICAL),),
        assessments=(
            _Assessment(
                "assessment-7",
                "study-7",
                (TomographyDisposition.TOOL_REQUIRED,),
                "stage4",
            ),
        ),
    )
    scanner = CompilationEligibilityScanner(
        replay_store=_ReplayStore((_Failure("failure-1", Partition.HISTORICAL),), ()),
        mutation_store=_MutationStore(()),
        compilation_store=_CompilationStore(()),
        tomography_store=tomography,
    )
    row = scanner.scan()[0]
    assert row.status is CompilationEligibilityStatus.REQUIRES_STAGE456_FEEDBACK
    assert row.tomography_assessment_id == "assessment-7"
    assert row.candidate is None


@pytest.mark.parametrize("partition", [Partition.FRESH, Partition.SEALED])
def test_protected_partitions_are_rejected_before_candidate_construction(partition) -> None:
    row = _scanner(partition=partition).scan()[0]
    assert row.status is CompilationEligibilityStatus.PROTECTED_PARTITION
    assert row.candidate is None


def test_missing_trigger_and_negative_transfer_contract_are_distinct() -> None:
    missing_trigger = _contract()
    missing_trigger["compilation"].pop("trigger_contract")
    row = _scanner(metadata=missing_trigger).scan()[0]
    assert row.status is CompilationEligibilityStatus.MISSING_TRIGGER_CONTRACT

    missing_boundary = _contract()
    missing_boundary["compilation"].pop("negative_transfer_boundary")
    row = _scanner(metadata=missing_boundary).scan()[0]
    assert row.status is CompilationEligibilityStatus.MISSING_NEGATIVE_TRANSFER_CONTRACT


def test_protected_generalization_failure_is_source_evidence_invalid() -> None:
    row = _scanner(protected_failures=("mutation-unsafe",)).scan()[0]
    assert row.status is CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID
    assert "protected" in " ".join(row.reasons).lower()


def test_already_compiled_mechanism_is_recognized() -> None:
    row = _scanner(capabilities=(_Compiled("mechanism-1"),)).scan()[0]
    assert row.status is CompilationEligibilityStatus.ALREADY_COMPILED
    assert row.candidate is None


def test_empty_historical_stores_return_zero_candidates_and_zero_calls() -> None:
    scanner = CompilationEligibilityScanner(
        replay_store=_ReplayStore((), ()),
        mutation_store=_MutationStore(()),
        compilation_store=_CompilationStore(()),
        tomography_store=None,
    )
    assert scanner.scan() == ()
    result = plan_eligible_compilation(scanner)
    assert result == {
        "MODEL_CALLS": 0,
        "status": "NO_ELIGIBLE_COMPILATION_CANDIDATES",
        "eligible_candidate_ids": [],
        "rows": [],
    }


def test_bootstrap_status_prefers_feedback_and_insufficient_evidence_boundaries() -> None:
    tomography = _TomographyStore(
        studies=(_Study("study-7", "failure-1", Partition.HISTORICAL),),
        assessments=(_Assessment("assessment-7", "study-7", (TomographyDisposition.TOOL_REQUIRED,), "stage4"),),
    )
    feedback_scanner = CompilationEligibilityScanner(
        replay_store=_ReplayStore((_Failure("failure-1", Partition.HISTORICAL),), ()),
        mutation_store=_MutationStore(()),
        compilation_store=_CompilationStore(()),
        tomography_store=tomography,
    )
    assert plan_eligible_compilation(feedback_scanner)["status"] == "REQUIRES_STAGE456_FEEDBACK"

    missing_scanner = _scanner(profiles=False)
    assert plan_eligible_compilation(missing_scanner)["status"] == "INSUFFICIENT_GENERALIZATION_EVIDENCE"
