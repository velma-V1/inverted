"""Deterministic zero-call Stage-9 fine-tuning eligibility scanning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .compilation_core import CompilationEligibilityStatus, CompilationKind
from .core import Partition
from .fine_tuning_core import FineTuningCandidate, FineTuningEligibilityStatus, FineTuningPolicy


_CHEAPER_THAN_FINE_TUNE = (
    CompilationKind.DETERMINISTIC_RULE,
    CompilationKind.STATE_REPRESENTATION,
    CompilationKind.FORMATTER_PARSER_VALIDATOR,
    CompilationKind.TOOL_POLICY,
    CompilationKind.SKILL_POLICY,
    CompilationKind.REASONING_POLICY,
    CompilationKind.VERIFIER_RECOVERY_POLICY,
)


@dataclass(frozen=True)
class FineTuningEligibilityResult:
    status: FineTuningEligibilityStatus
    mechanism_id: str | None
    failure_snapshot_ids: tuple[str, ...]
    candidate: FineTuningCandidate | None
    reasons: tuple[str, ...]
    model_calls: int = 0

    def __post_init__(self) -> None:
        status = self.status if isinstance(self.status, FineTuningEligibilityStatus) else FineTuningEligibilityStatus(self.status)
        object.__setattr__(self, "status", status)
        if self.mechanism_id is not None and (not isinstance(self.mechanism_id, str) or not self.mechanism_id.strip()):
            raise ValueError("mechanism_id must be non-blank when present")
        if isinstance(self.failure_snapshot_ids, (str, bytes, bytearray)):
            raise TypeError("failure_snapshot_ids must be a sequence")
        failures = tuple(sorted(str(item) for item in self.failure_snapshot_ids if str(item).strip()))
        object.__setattr__(self, "failure_snapshot_ids", failures)
        if not self.reasons or any(not isinstance(item, str) or not item.strip() for item in self.reasons):
            raise ValueError("reasons must contain non-blank strings")
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if self.model_calls != 0:
            raise ValueError("Stage-9 eligibility must use zero model calls")
        if status is FineTuningEligibilityStatus.ELIGIBLE and self.candidate is None:
            raise ValueError("ELIGIBLE result requires candidate")
        if status is not FineTuningEligibilityStatus.ELIGIBLE and self.candidate is not None:
            raise ValueError("ineligible result cannot carry candidate")

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "mechanism_id": self.mechanism_id,
            "failure_snapshot_ids": list(self.failure_snapshot_ids),
            "candidate_id": None if self.candidate is None else self.candidate.candidate_id,
            "reasons": list(self.reasons),
            "model_calls": 0,
        }


class FineTuningEligibilityScanner:
    """Consume Stage-8 admissions and admit only recurrent model-owned residuals."""

    def __init__(self, *, compilation_scanner: Any, qualification_store: Any, policy: FineTuningPolicy | None = None) -> None:
        if not callable(getattr(compilation_scanner, "scan", None)):
            raise TypeError("compilation_scanner must expose scan()")
        if not callable(getattr(qualification_store, "validate", None)) or not callable(getattr(qualification_store, "qualifications", None)):
            raise TypeError("qualification_store must expose validate() and qualifications()")
        self.compilation_scanner = compilation_scanner
        self.qualification_store = qualification_store
        self.policy = policy or FineTuningPolicy()

    @staticmethod
    def _partition(value: Any) -> Partition | None:
        try:
            return value if isinstance(value, Partition) else Partition(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    def _result(self, status: FineTuningEligibilityStatus, mechanism_id: str | None, failures: tuple[str, ...], reason: str, candidate: FineTuningCandidate | None = None) -> FineTuningEligibilityResult:
        return FineTuningEligibilityResult(status=status, mechanism_id=mechanism_id, failure_snapshot_ids=failures, candidate=candidate, reasons=(reason,), model_calls=0)

    def scan(self) -> tuple[FineTuningEligibilityResult, ...]:
        validation = self.qualification_store.validate()
        if not getattr(validation, "ok", False):
            raise ValueError("Stage-9 qualification store integrity validation failed")
        stage8_rows = tuple(self.compilation_scanner.scan())
        groups: dict[str, list[Any]] = {}
        output: list[FineTuningEligibilityResult] = []

        for row in stage8_rows:
            if getattr(row, "status", None) is not CompilationEligibilityStatus.ELIGIBLE:
                continue
            item = getattr(row, "candidate", None)
            if item is None:
                continue
            mechanism_id = str(getattr(item, "mechanism_id", ""))
            failure_id = str(getattr(item, "failure_snapshot_id", ""))
            if not mechanism_id or not failure_id:
                output.append(self._result(FineTuningEligibilityStatus.UNSUPPORTED_SOURCE, mechanism_id or None, (failure_id,) if failure_id else (), "Stage-8 candidate lacks fine-tuning lineage"))
                continue
            partition = self._partition(getattr(item, "partition", Partition.HISTORICAL))
            if partition in {Partition.FRESH, Partition.SEALED}:
                output.append(self._result(FineTuningEligibilityStatus.PROTECTED_PARTITION, mechanism_id, (failure_id,), "FRESH/SEALED evidence is protected from Stage-9 qualification"))
                continue
            kinds = tuple(getattr(item, "supported_kinds", ()))
            if CompilationKind.FINE_TUNE_CANDIDATE not in kinds or not bool(getattr(item, "model_internal_residual", False)):
                output.append(self._result(FineTuningEligibilityStatus.INSUFFICIENT_MODEL_OWNERSHIP_EVIDENCE, mechanism_id, (failure_id,), "Stage-8 evidence does not establish a model-internal fine-tuning residual"))
                continue
            generalization_ref = getattr(item, "generalization_profile_id", None) or getattr(item, "prior_generalized_evidence_ref", None)
            if not generalization_ref:
                output.append(self._result(FineTuningEligibilityStatus.INSUFFICIENT_GENERALIZATION_EVIDENCE, mechanism_id, (failure_id,), "Stage-8 candidate lacks accepted generalization evidence"))
                continue
            excluded = self._mapping(getattr(item, "excluded_cheaper_kinds", {}))
            missing = [kind.value for kind in _CHEAPER_THAN_FINE_TUNE if kind.value not in excluded]
            if missing:
                output.append(self._result(FineTuningEligibilityStatus.CHEAPER_OWNER_UNRESOLVED, mechanism_id, (failure_id,), "cheaper owner exclusions are incomplete: " + ",".join(missing)))
                continue
            groups.setdefault(mechanism_id, []).append(item)

        qualified_ids = {str(getattr(item, "candidate_id", "")) for item in self.qualification_store.qualifications() if getattr(item, "candidate_id", None)}
        for mechanism_id in sorted(groups):
            items = sorted(groups[mechanism_id], key=lambda item: str(getattr(item, "failure_snapshot_id", "")))
            failures = tuple(sorted({str(getattr(item, "failure_snapshot_id")) for item in items}))
            if len(failures) < self.policy.minimum_independent_failures:
                output.append(self._result(FineTuningEligibilityStatus.INSUFFICIENT_REPEATED_PATTERN, mechanism_id, failures, "fine-tuning requires recurrent independent failure instances"))
                continue
            first = items[0]
            stage8_ids = tuple(sorted(str(getattr(item, "candidate_id")) for item in items))
            evidence_refs: set[str] = set(stage8_ids)
            tomography_refs: set[str] = set()
            source_hashes: dict[str, str] = {}
            regression_refs: set[str] = set()
            partitions: set[Partition] = set()
            for item in items:
                gen = getattr(item, "generalization_profile_id", None) or getattr(item, "prior_generalized_evidence_ref", None)
                if gen:
                    evidence_refs.add(str(gen))
                tomo = getattr(item, "tomography_assessment_id", None)
                if tomo:
                    tomography_refs.add(str(tomo))
                partitions.add(self._partition(getattr(item, "partition", Partition.HISTORICAL)) or Partition.HISTORICAL)
                for key, digest in self._mapping(getattr(item, "source_hashes", {})).items():
                    key_s, digest_s = str(key), str(digest)
                    if key_s in source_hashes and source_hashes[key_s] != digest_s:
                        raise ValueError("conflicting Stage-8 source hash for fine-tuning recurrence group")
                    source_hashes[key_s] = digest_s
                regression_refs.update(str(x) for x in tuple(getattr(item, "evidence_refs", ()) or ()))
            if len(partitions) != 1 or next(iter(partitions)) in {Partition.FRESH, Partition.SEALED}:
                output.append(self._result(FineTuningEligibilityStatus.PROTECTED_PARTITION, mechanism_id, failures, "fine-tuning recurrence group crosses or uses protected partitions"))
                continue
            compiled_payload = self._mapping(getattr(first, "compiled_payload", {}))
            base_model_profile_id = str(getattr(first, "base_model_profile_id", "") or compiled_payload.get("base_model_profile_id") or f"source-profile:{mechanism_id}")
            try:
                candidate = FineTuningCandidate.create(
                    stage8_candidate_id=stage8_ids[0],
                    mechanism_id=mechanism_id,
                    failure_snapshot_ids=failures,
                    generalization_evidence_refs=tuple(sorted(evidence_refs)),
                    tomography_assessment_refs=tuple(sorted(tomography_refs)),
                    cheaper_owner_exclusions=dict(getattr(first, "excluded_cheaper_kinds", {})),
                    trigger_contract=dict(getattr(first, "trigger_contract", {}) or {"observable_failure_class": "MODEL_INTERNAL_RESIDUAL"}),
                    allowed_region=str(getattr(first, "tested_region", "generalized Stage-8 region")),
                    negative_transfer_boundary=tuple(getattr(first, "negative_transfer_boundary", ()) or ("preserve direct-solved region",)),
                    source_hashes=source_hashes or {str(next(iter(evidence_refs))): "0" * 64},
                    partition=next(iter(partitions)),
                    base_model_profile_id=base_model_profile_id,
                    regression_evidence_refs=tuple(sorted(regression_refs or evidence_refs)),
                    model_internal_residual=True,
                    generalization_complete=True,
                    cheaper_owners_resolved=True,
                )
            except (TypeError, ValueError) as exc:
                output.append(self._result(FineTuningEligibilityStatus.UNSUPPORTED_SOURCE, mechanism_id, failures, f"Stage-9 candidate contract is invalid: {exc}"))
                continue
            if candidate.candidate_id in qualified_ids:
                output.append(self._result(FineTuningEligibilityStatus.ALREADY_QUALIFIED, mechanism_id, failures, "candidate already has a Stage-9 qualification"))
            else:
                output.append(self._result(FineTuningEligibilityStatus.ELIGIBLE, mechanism_id, failures, "recurrent generalized model-internal residual has resolved cheaper owners", candidate))

        if not output and not groups:
            return ()
        return tuple(sorted(output, key=lambda row: (row.status.value, row.mechanism_id or "", row.failure_snapshot_ids)))


def plan_eligible_fine_tuning(scanner: FineTuningEligibilityScanner) -> dict[str, Any]:
    if not isinstance(scanner, FineTuningEligibilityScanner):
        raise TypeError("scanner must be FineTuningEligibilityScanner")
    rows = scanner.scan()
    eligible = tuple(row.candidate for row in rows if row.status is FineTuningEligibilityStatus.ELIGIBLE and row.candidate is not None)
    if eligible:
        status = "FINE_TUNING_PLAN_READY"
    elif rows and all(row.status is FineTuningEligibilityStatus.ALREADY_QUALIFIED for row in rows):
        status = "ALL_ELIGIBLE_FINE_TUNING_CANDIDATES_QUALIFIED"
    elif any(row.status is FineTuningEligibilityStatus.CHEAPER_OWNER_UNRESOLVED for row in rows):
        status = "CHEAPER_OWNER_UNRESOLVED"
    elif any(row.status in {FineTuningEligibilityStatus.INSUFFICIENT_REPEATED_PATTERN, FineTuningEligibilityStatus.INSUFFICIENT_GENERALIZATION_EVIDENCE, FineTuningEligibilityStatus.INSUFFICIENT_MODEL_OWNERSHIP_EVIDENCE} for row in rows):
        status = "REQUIRES_MORE_FINE_TUNING_EVIDENCE"
    else:
        status = "NO_ELIGIBLE_FINE_TUNING_CANDIDATES"
    return {"MODEL_CALLS": 0, "status": status, "eligible_candidate_ids": [item.candidate_id for item in eligible], "rows": [row.to_payload() for row in rows]}
