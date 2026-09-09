from __future__ import annotations

from dataclasses import dataclass

from inverted.capability_ratchet.compilation_core import CompilationKind
from inverted.capability_ratchet.fine_tuning_eligibility import (
    FineTuningEligibilityScanner,
    plan_eligible_fine_tuning,
)
from inverted.capability_ratchet.fine_tuning_core import FineTuningEligibilityStatus


@dataclass(frozen=True)
class _Validation:
    ok: bool = True


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    mechanism_id: str
    failure_snapshot_id: str
    supported_kinds: tuple[CompilationKind, ...]
    model_internal_residual: bool
    excluded_cheaper_kinds: dict[str, str]
    generalization_profile_id: str | None = "profile-1"
    prior_generalized_evidence_ref: str | None = None
    evidence_refs: tuple[str, ...] = ("profile-1",)
    source_hashes: dict[str, str] | None = None
    trigger_contract: dict[str, object] | None = None
    negative_transfer_boundary: tuple[str, ...] = ("direct-solved",)
    tested_region: str = "region-r1"
    partition: str = "HISTORICAL"
    tomography_assessment_id: str | None = "assessment-1"

    def __post_init__(self):
        if self.source_hashes is None:
            object.__setattr__(self, "source_hashes", {"profile-1": "a" * 64})
        if self.trigger_contract is None:
            object.__setattr__(self, "trigger_contract", {"observable_failure_class": "MODEL_INTERNAL_RESIDUAL"})


@dataclass(frozen=True)
class _Row:
    status: object
    candidate: object | None


class _CompilationScanner:
    def __init__(self, candidates):
        self._candidates = tuple(candidates)

    def scan(self):
        from inverted.capability_ratchet.compilation_core import CompilationEligibilityStatus
        return tuple(_Row(CompilationEligibilityStatus.ELIGIBLE, item) for item in self._candidates)


class _QualificationStore:
    def validate(self):
        return _Validation()

    def qualifications(self):
        return ()


def _candidate(failure: str, **overrides):
    values = dict(
        candidate_id=f"candidate-{failure}",
        mechanism_id="mechanism-1",
        failure_snapshot_id=failure,
        supported_kinds=(CompilationKind.FINE_TUNE_CANDIDATE,),
        model_internal_residual=True,
        excluded_cheaper_kinds={kind.value: "falsified" for kind in (
            CompilationKind.DETERMINISTIC_RULE,
            CompilationKind.STATE_REPRESENTATION,
            CompilationKind.FORMATTER_PARSER_VALIDATOR,
            CompilationKind.TOOL_POLICY,
            CompilationKind.SKILL_POLICY,
            CompilationKind.REASONING_POLICY,
            CompilationKind.VERIFIER_RECOVERY_POLICY,
        )},
    )
    values.update(overrides)
    return _Candidate(**values)


def test_requires_recurrent_independent_model_internal_stage8_handoff() -> None:
    scanner = FineTuningEligibilityScanner(
        compilation_scanner=_CompilationScanner((_candidate("failure-1"), _candidate("failure-2"))),
        qualification_store=_QualificationStore(),
    )
    rows = scanner.scan()
    eligible = [row for row in rows if row.status is FineTuningEligibilityStatus.ELIGIBLE]
    assert len(eligible) == 1
    assert eligible[0].candidate is not None
    assert eligible[0].candidate.failure_snapshot_ids == ("failure-1", "failure-2")
    assert eligible[0].model_calls == 0


def test_one_off_pattern_is_explicitly_ineligible() -> None:
    rows = FineTuningEligibilityScanner(
        compilation_scanner=_CompilationScanner((_candidate("failure-1"),)),
        qualification_store=_QualificationStore(),
    ).scan()
    assert any(row.status is FineTuningEligibilityStatus.INSUFFICIENT_REPEATED_PATTERN for row in rows)


def test_non_model_owner_and_unresolved_cheaper_owner_are_vetoed() -> None:
    tool = _candidate("failure-1", supported_kinds=(CompilationKind.TOOL_POLICY,), model_internal_residual=False)
    unresolved = _candidate("failure-2", excluded_cheaper_kinds={})
    rows = FineTuningEligibilityScanner(
        compilation_scanner=_CompilationScanner((tool, unresolved)),
        qualification_store=_QualificationStore(),
    ).scan()
    statuses = {row.status for row in rows}
    assert FineTuningEligibilityStatus.INSUFFICIENT_MODEL_OWNERSHIP_EVIDENCE in statuses
    assert FineTuningEligibilityStatus.CHEAPER_OWNER_UNRESOLVED in statuses


def test_historical_empty_boundary_is_truthful_and_zero_call() -> None:
    scanner = FineTuningEligibilityScanner(
        compilation_scanner=_CompilationScanner(()),
        qualification_store=_QualificationStore(),
    )
    result = plan_eligible_fine_tuning(scanner)
    assert result["MODEL_CALLS"] == 0
    assert result["status"] == "NO_ELIGIBLE_FINE_TUNING_CANDIDATES"
    assert result["eligible_candidate_ids"] == []
