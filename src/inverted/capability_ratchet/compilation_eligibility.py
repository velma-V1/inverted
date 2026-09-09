"""Deterministic, zero-inference Stage-8 compilation eligibility scanning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .compilation_core import (
    CompilationCandidate,
    CompilationEligibilityStatus,
)
from .core import Partition
from .mutation_core import GeneralizationClass


@dataclass(frozen=True)
class CompilationEligibilityResult:
    """One deterministic Stage-8 admission decision."""

    status: CompilationEligibilityStatus
    failure_snapshot_id: str
    mechanism_id: str | None
    generalization_profile_id: str | None
    tomography_assessment_id: str | None
    candidate: CompilationCandidate | None
    reasons: tuple[str, ...]
    model_calls: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.status, CompilationEligibilityStatus):
            object.__setattr__(self, "status", CompilationEligibilityStatus(self.status))
        if not isinstance(self.failure_snapshot_id, str) or not self.failure_snapshot_id.strip():
            raise ValueError("failure_snapshot_id is required")
        for name in ("mechanism_id", "generalization_profile_id", "tomography_assessment_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be non-blank when present")
        if self.candidate is not None and not isinstance(self.candidate, CompilationCandidate):
            raise TypeError("candidate must be CompilationCandidate or None")
        if isinstance(self.reasons, (str, bytes, bytearray)) or not isinstance(self.reasons, (list, tuple)):
            raise TypeError("reasons must be a sequence of strings")
        reasons = tuple(self.reasons)
        if not reasons or any(not isinstance(item, str) or not item.strip() for item in reasons):
            raise ValueError("reasons must contain non-blank strings")
        object.__setattr__(self, "reasons", reasons)
        if self.model_calls != 0:
            raise ValueError("Stage-8 eligibility scanning must use zero model calls")
        if self.status is CompilationEligibilityStatus.ELIGIBLE and self.candidate is None:
            raise ValueError("ELIGIBLE result requires candidate")
        if self.status is not CompilationEligibilityStatus.ELIGIBLE and self.candidate is not None:
            raise ValueError("ineligible result cannot carry a candidate")

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "failure_snapshot_id": self.failure_snapshot_id,
            "mechanism_id": self.mechanism_id,
            "generalization_profile_id": self.generalization_profile_id,
            "tomography_assessment_id": self.tomography_assessment_id,
            "candidate_id": None if self.candidate is None else self.candidate.candidate_id,
            "reasons": list(self.reasons),
            "model_calls": 0,
        }


class CompilationEligibilityScanner:
    """Admit only explicitly generalized canonical evidence into Stage 8."""

    def __init__(
        self,
        *,
        replay_store: Any,
        mutation_store: Any,
        compilation_store: Any,
        tomography_store: Any | None = None,
    ) -> None:
        self._require_methods("replay_store", replay_store, ("validate", "get_failure", "records"))
        self._require_methods("mutation_store", mutation_store, ("validate", "profiles"))
        self._require_methods("compilation_store", compilation_store, ("validate", "capabilities"))
        if tomography_store is not None:
            self._require_methods("tomography_store", tomography_store, ("validate", "studies"))
            if not callable(getattr(tomography_store, "assessments", None)) and not callable(
                getattr(tomography_store, "profiles", None)
            ):
                raise TypeError("tomography_store must expose assessments() or profiles()")
        self.replay_store = replay_store
        self.mutation_store = mutation_store
        self.compilation_store = compilation_store
        self.tomography_store = tomography_store

    @staticmethod
    def _require_methods(name: str, value: Any, methods: tuple[str, ...]) -> None:
        missing = [method for method in methods if not callable(getattr(value, method, None))]
        if missing:
            raise TypeError(f"{name} must expose {', '.join(missing)}")

    @staticmethod
    def _require_valid(name: str, store: Any) -> None:
        result = store.validate()
        if not getattr(result, "ok", False):
            raise ValueError(f"{name} source evidence integrity validation failed")

    def _validate_sources(self) -> None:
        self._require_valid("replay", self.replay_store)
        self._require_valid("mutation", self.mutation_store)
        self._require_valid("compilation", self.compilation_store)
        if self.tomography_store is not None:
            self._require_valid("tomography", self.tomography_store)

    def _labels(self) -> tuple[Any, ...]:
        values = []
        for record in self.replay_store.records():
            if all(hasattr(record, name) for name in ("mechanism_label_id", "failure_snapshot_id", "mechanism_id")):
                values.append(record)
        return tuple(values)

    def _assessments(self) -> tuple[Any, ...]:
        if self.tomography_store is None:
            return ()
        method = getattr(self.tomography_store, "assessments", None)
        if callable(method):
            return tuple(method())
        return tuple(self.tomography_store.profiles())

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any] | None:
        return value if isinstance(value, Mapping) else None

    @staticmethod
    def _result(
        *,
        status: CompilationEligibilityStatus,
        failure_snapshot_id: str,
        mechanism_id: str | None,
        generalization_profile_id: str | None = None,
        tomography_assessment_id: str | None = None,
        candidate: CompilationCandidate | None = None,
        reasons: tuple[str, ...],
    ) -> CompilationEligibilityResult:
        return CompilationEligibilityResult(
            status=status,
            failure_snapshot_id=failure_snapshot_id,
            mechanism_id=mechanism_id,
            generalization_profile_id=generalization_profile_id,
            tomography_assessment_id=tomography_assessment_id,
            candidate=candidate,
            reasons=reasons,
            model_calls=0,
        )

    def _scan_profile(
        self,
        profile: Any,
        *,
        labels: tuple[Any, ...],
        compiled_mechanisms: frozenset[str],
    ) -> CompilationEligibilityResult:
        profile_id = str(getattr(profile, "profile_id", ""))
        failure_snapshot_id = str(getattr(profile, "failure_snapshot_id", ""))
        mechanism_id = str(getattr(profile, "mechanism_id", ""))
        if not profile_id or not failure_snapshot_id or not mechanism_id:
            raise ValueError("generalization profile is missing required Stage-8 lineage fields")

        try:
            failure = self.replay_store.get_failure(failure_snapshot_id)
        except KeyError:
            return self._result(
                status=CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("generalization profile references missing canonical failure",),
            )

        partition = getattr(failure, "partition", None)
        if not isinstance(partition, Partition):
            try:
                partition = Partition(partition)
            except (TypeError, ValueError):
                return self._result(
                    status=CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
                    failure_snapshot_id=failure_snapshot_id,
                    mechanism_id=mechanism_id,
                    generalization_profile_id=profile_id,
                    reasons=("canonical failure partition is invalid",),
                )
        if partition in {Partition.FRESH, Partition.SEALED}:
            return self._result(
                status=CompilationEligibilityStatus.PROTECTED_PARTITION,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("FRESH/SEALED evidence is protected from Stage-8 development compilation",),
            )

        if mechanism_id in compiled_mechanisms:
            return self._result(
                status=CompilationEligibilityStatus.ALREADY_COMPILED,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("mechanism already has a compiled capability version",),
            )

        classification = getattr(profile, "classification", None)
        if not isinstance(classification, GeneralizationClass):
            try:
                classification = GeneralizationClass(classification)
            except (TypeError, ValueError):
                return self._result(
                    status=CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
                    failure_snapshot_id=failure_snapshot_id,
                    mechanism_id=mechanism_id,
                    generalization_profile_id=profile_id,
                    reasons=("generalization classification is missing or invalid",),
                )
        if classification is GeneralizationClass.INSTANCE_PATCH:
            return self._result(
                status=CompilationEligibilityStatus.INSTANCE_PATCH,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("INSTANCE_PATCH cannot enter Stage-8 capability compilation",),
            )

        protected_failures = tuple(getattr(profile, "protected_failures", ()) or ())
        if protected_failures:
            return self._result(
                status=CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("generalization evidence contains protected negative-transfer failures",),
            )

        metadata = self._mapping(getattr(profile, "metadata", None))
        contract = self._mapping(None if metadata is None else metadata.get("compilation"))
        if contract is None:
            return self._result(
                status=CompilationEligibilityStatus.MISSING_TRIGGER_CONTRACT,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("generalized mechanism has no explicit Stage-8 compilation trigger contract",),
            )
        trigger = contract.get("trigger_contract")
        if not isinstance(trigger, Mapping) or not trigger:
            return self._result(
                status=CompilationEligibilityStatus.MISSING_TRIGGER_CONTRACT,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("explicit observable trigger contract is missing",),
            )
        boundary = contract.get("negative_transfer_boundary")
        if isinstance(boundary, (str, bytes, bytearray)) or not isinstance(boundary, (list, tuple)) or not boundary:
            return self._result(
                status=CompilationEligibilityStatus.MISSING_NEGATIVE_TRANSFER_CONTRACT,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("negative-transfer boundary is missing",),
            )

        matching_labels = tuple(
            label
            for label in labels
            if getattr(label, "failure_snapshot_id", None) == failure_snapshot_id
            and getattr(label, "mechanism_id", None) == mechanism_id
        )
        declared_label_ids = contract.get("mechanism_label_ids")
        if isinstance(declared_label_ids, (str, bytes, bytearray)) or not isinstance(declared_label_ids, (list, tuple)):
            return self._result(
                status=CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("compilation contract is missing canonical mechanism-label references",),
            )
        available_label_ids = {str(getattr(label, "mechanism_label_id")) for label in matching_labels}
        if not declared_label_ids or not set(map(str, declared_label_ids)).issubset(available_label_ids):
            return self._result(
                status=CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                reasons=("declared mechanism-label lineage is absent from canonical replay evidence",),
            )

        try:
            candidate = CompilationCandidate.create(
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                prior_generalized_evidence_ref=None,
                generalization_class=classification,
                mechanism_label_ids=tuple(str(item) for item in declared_label_ids),
                evidence_refs=tuple(str(item) for item in contract.get("evidence_refs", ())),
                source_hashes=dict(contract.get("source_hashes", {})),
                supported_kinds=tuple(contract.get("supported_kinds", ())),
                excluded_cheaper_kinds=dict(contract.get("excluded_cheaper_kinds", {})),
                trigger_contract=dict(trigger),
                compiled_payload=dict(contract.get("compiled_payload", {})),
                verifier_contract=dict(contract.get("verifier_contract", {})),
                negative_transfer_boundary=tuple(str(item) for item in boundary),
                tested_region=str(contract.get("tested_region", "")),
                rollback_action=str(contract.get("rollback_action", "")),
                partition=partition,
                operating_surface_profile_id=contract.get("operating_surface_profile_id"),
                tomography_assessment_id=contract.get("tomography_assessment_id"),
                model_internal_residual=bool(contract.get("model_internal_residual", False)),
                decision_id=str(contract.get("decision_id", "D12")),
            )
        except (TypeError, ValueError) as exc:
            return self._result(
                status=CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
                failure_snapshot_id=failure_snapshot_id,
                mechanism_id=mechanism_id,
                generalization_profile_id=profile_id,
                tomography_assessment_id=contract.get("tomography_assessment_id"),
                reasons=(f"explicit compilation contract is invalid: {exc}",),
            )

        return self._result(
            status=CompilationEligibilityStatus.ELIGIBLE,
            failure_snapshot_id=failure_snapshot_id,
            mechanism_id=mechanism_id,
            generalization_profile_id=profile_id,
            tomography_assessment_id=contract.get("tomography_assessment_id"),
            candidate=candidate,
            reasons=("generalized canonical mechanism has a complete explicit Stage-8 compilation contract",),
        )

    def _tomography_feedback_rows(
        self,
        *,
        generalized_failures: frozenset[str],
    ) -> tuple[CompilationEligibilityResult, ...]:
        if self.tomography_store is None:
            return ()
        studies = {
            str(getattr(study, "study_id")): study
            for study in self.tomography_store.studies()
            if getattr(study, "study_id", None) is not None
        }
        rows: list[CompilationEligibilityResult] = []
        for assessment in self._assessments():
            assessment_id = getattr(assessment, "profile_id", None)
            study_id = getattr(assessment, "study_id", None)
            if not assessment_id or not study_id or str(study_id) not in studies:
                continue
            study = studies[str(study_id)]
            failure_snapshot_id = str(getattr(study, "failure_snapshot_id", ""))
            if not failure_snapshot_id or failure_snapshot_id in generalized_failures:
                continue
            partition = getattr(study, "partition", None)
            try:
                partition = partition if isinstance(partition, Partition) else Partition(partition)
            except (TypeError, ValueError):
                partition = None
            status = (
                CompilationEligibilityStatus.PROTECTED_PARTITION
                if partition in {Partition.FRESH, Partition.SEALED}
                else CompilationEligibilityStatus.REQUIRES_STAGE456_FEEDBACK
            )
            reason = (
                "Stage-7 result belongs to protected FRESH/SEALED evidence"
                if status is CompilationEligibilityStatus.PROTECTED_PARTITION
                else "Stage-7 ownership evidence must route through Stage 4→5→6 before compilation"
            )
            rows.append(
                self._result(
                    status=status,
                    failure_snapshot_id=failure_snapshot_id,
                    mechanism_id=None,
                    tomography_assessment_id=str(assessment_id),
                    reasons=(reason,),
                )
            )
        return tuple(rows)

    def scan(self) -> tuple[CompilationEligibilityResult, ...]:
        self._validate_sources()
        profiles = tuple(self.mutation_store.profiles())
        labels = self._labels()
        compiled_mechanisms = frozenset(
            str(getattr(item, "mechanism_id"))
            for item in self.compilation_store.capabilities()
            if getattr(item, "mechanism_id", None)
        )

        rows: list[CompilationEligibilityResult] = []
        covered_pairs: set[tuple[str, str]] = set()
        generalized_failures: set[str] = set()
        for profile in sorted(
            profiles,
            key=lambda item: (
                str(getattr(item, "failure_snapshot_id", "")),
                str(getattr(item, "mechanism_id", "")),
                str(getattr(item, "profile_id", "")),
            ),
        ):
            failure_snapshot_id = str(getattr(profile, "failure_snapshot_id", ""))
            mechanism_id = str(getattr(profile, "mechanism_id", ""))
            if failure_snapshot_id and mechanism_id:
                covered_pairs.add((failure_snapshot_id, mechanism_id))
                generalized_failures.add(failure_snapshot_id)
            rows.append(
                self._scan_profile(
                    profile,
                    labels=labels,
                    compiled_mechanisms=compiled_mechanisms,
                )
            )

        for label in labels:
            failure_snapshot_id = str(getattr(label, "failure_snapshot_id"))
            mechanism_id = str(getattr(label, "mechanism_id"))
            if (failure_snapshot_id, mechanism_id) in covered_pairs:
                continue
            try:
                failure = self.replay_store.get_failure(failure_snapshot_id)
                partition = getattr(failure, "partition", None)
                partition = partition if isinstance(partition, Partition) else Partition(partition)
            except (KeyError, TypeError, ValueError):
                rows.append(
                    self._result(
                        status=CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
                        failure_snapshot_id=failure_snapshot_id,
                        mechanism_id=mechanism_id,
                        reasons=("mechanism label references invalid canonical failure lineage",),
                    )
                )
                covered_pairs.add((failure_snapshot_id, mechanism_id))
                continue
            status = (
                CompilationEligibilityStatus.PROTECTED_PARTITION
                if partition in {Partition.FRESH, Partition.SEALED}
                else CompilationEligibilityStatus.MISSING_GENERALIZATION
            )
            rows.append(
                self._result(
                    status=status,
                    failure_snapshot_id=failure_snapshot_id,
                    mechanism_id=mechanism_id,
                    reasons=(
                        "FRESH/SEALED evidence is protected from Stage-8 development compilation"
                        if status is CompilationEligibilityStatus.PROTECTED_PARTITION
                        else "canonical mechanism label has no Stage-6 generalization profile",
                    ),
                )
            )
            covered_pairs.add((failure_snapshot_id, mechanism_id))

        rows.extend(
            self._tomography_feedback_rows(generalized_failures=frozenset(generalized_failures))
        )

        unique: dict[tuple[Any, ...], CompilationEligibilityResult] = {}
        for row in rows:
            key = (
                row.status.value,
                row.failure_snapshot_id,
                row.mechanism_id or "",
                row.generalization_profile_id or "",
                row.tomography_assessment_id or "",
            )
            unique.setdefault(key, row)
        return tuple(unique[key] for key in sorted(unique))


def plan_eligible_compilation(scanner: CompilationEligibilityScanner) -> dict[str, Any]:
    """Return the zero-call historical Stage-8 boundary/ready state."""

    if not isinstance(scanner, CompilationEligibilityScanner):
        raise TypeError("scanner must be CompilationEligibilityScanner")
    rows = scanner.scan()
    eligible = tuple(
        row.candidate
        for row in rows
        if row.status is CompilationEligibilityStatus.ELIGIBLE and row.candidate is not None
    )
    if eligible:
        status = "COMPILATION_PLAN_READY"
    elif rows and all(row.status is CompilationEligibilityStatus.ALREADY_COMPILED for row in rows):
        status = "ALL_ELIGIBLE_CAPABILITIES_COMPILED"
    elif any(row.status is CompilationEligibilityStatus.REQUIRES_STAGE456_FEEDBACK for row in rows):
        status = "REQUIRES_STAGE456_FEEDBACK"
    elif any(
        row.status
        in {
            CompilationEligibilityStatus.MISSING_GENERALIZATION,
            CompilationEligibilityStatus.MISSING_TRIGGER_CONTRACT,
            CompilationEligibilityStatus.MISSING_NEGATIVE_TRANSFER_CONTRACT,
            CompilationEligibilityStatus.CONFLICTING_OWNERSHIP,
            CompilationEligibilityStatus.SOURCE_EVIDENCE_INVALID,
        }
        for row in rows
    ):
        status = "INSUFFICIENT_GENERALIZATION_EVIDENCE"
    else:
        status = "NO_ELIGIBLE_COMPILATION_CANDIDATES"
    return {
        "MODEL_CALLS": 0,
        "status": status,
        "eligible_candidate_ids": [item.candidate_id for item in eligible],
        "rows": [row.to_payload() for row in rows],
    }
