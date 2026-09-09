"""Frozen, zero-inference contracts for Stage-8 capability compilation."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .core import Partition
from .mutation_core import GeneralizationClass


class CompilationKind(str, Enum):
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    STATE_REPRESENTATION = "STATE_REPRESENTATION"
    FORMATTER_PARSER_VALIDATOR = "FORMATTER_PARSER_VALIDATOR"
    TOOL_POLICY = "TOOL_POLICY"
    SKILL_POLICY = "SKILL_POLICY"
    REASONING_POLICY = "REASONING_POLICY"
    VERIFIER_RECOVERY_POLICY = "VERIFIER_RECOVERY_POLICY"
    FINE_TUNE_CANDIDATE = "FINE_TUNE_CANDIDATE"
    ESCALATION_POLICY = "ESCALATION_POLICY"
    SAFE_STOP_BOUNDARY = "SAFE_STOP_BOUNDARY"


COMPILATION_KIND_ORDER = (
    CompilationKind.DETERMINISTIC_RULE,
    CompilationKind.STATE_REPRESENTATION,
    CompilationKind.FORMATTER_PARSER_VALIDATOR,
    CompilationKind.TOOL_POLICY,
    CompilationKind.SKILL_POLICY,
    CompilationKind.REASONING_POLICY,
    CompilationKind.VERIFIER_RECOVERY_POLICY,
    CompilationKind.FINE_TUNE_CANDIDATE,
    CompilationKind.ESCALATION_POLICY,
    CompilationKind.SAFE_STOP_BOUNDARY,
)


class CompilationEligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INSTANCE_PATCH = "INSTANCE_PATCH"
    MISSING_GENERALIZATION = "MISSING_GENERALIZATION"
    MISSING_TRIGGER_CONTRACT = "MISSING_TRIGGER_CONTRACT"
    MISSING_NEGATIVE_TRANSFER_CONTRACT = "MISSING_NEGATIVE_TRANSFER_CONTRACT"
    CONFLICTING_OWNERSHIP = "CONFLICTING_OWNERSHIP"
    PROTECTED_PARTITION = "PROTECTED_PARTITION"
    REQUIRES_STAGE456_FEEDBACK = "REQUIRES_STAGE456_FEEDBACK"
    SOURCE_EVIDENCE_INVALID = "SOURCE_EVIDENCE_INVALID"
    ALREADY_COMPILED = "ALREADY_COMPILED"


class CompilationDisposition(str, Enum):
    COMPILED = "COMPILED"
    FINE_TUNE_CANDIDATE = "FINE_TUNE_CANDIDATE"
    ESCALATION_CANDIDATE = "ESCALATION_CANDIDATE"
    SAFE_STOP_BOUNDARY = "SAFE_STOP_BOUNDARY"
    HARD_BOUNDARY = "HARD_BOUNDARY"
    REQUIRES_MORE_EVIDENCE = "REQUIRES_MORE_EVIDENCE"
    INELIGIBLE = "INELIGIBLE"


_FORBIDDEN_TRIGGER_FRAGMENTS = ("oracle", "family")
_FORBIDDEN_RAW_KEYS = frozenset(
    {
        "raw_response",
        "raw_model_response",
        "raw_call",
        "model_output",
        "output_text",
        "prompt",
        "messages",
    }
)


def _required(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("compilation mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("compilation payload numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported compilation payload value: {type(value).__name__}")


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("compilation payload numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported compilation payload value: {type(value).__name__}")


def _stable_id(prefix: str, payload: Mapping[str, Any], *, length: int = 24) -> str:
    encoded = json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:length]}"


def _string_tuple(name: str, value: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a sequence of strings")
    result = tuple(value)
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise TypeError(f"{name} must contain non-blank strings")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must be unique")
    return result


def _enum_tuple(name: str, value: Any, enum_type: type[Enum]) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a sequence")
    result = tuple(item if isinstance(item, enum_type) else enum_type(item) for item in value)
    if not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must be unique")
    return result


def _validate_sha_mapping(name: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if not value:
        raise ValueError(f"{name} must not be empty")
    for key, digest in value.items():
        _required(f"{name} key", key)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ValueError(f"{name} values must be lowercase SHA-256 digests")
    return _freeze(value)


def _contains_forbidden_trigger_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = key.lower()
            if any(fragment in lowered for fragment in _FORBIDDEN_TRIGGER_FRAGMENTS):
                return key
            nested = _contains_forbidden_trigger_key(item)
            if nested is not None:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = _contains_forbidden_trigger_key(item)
            if nested is not None:
                return nested
    return None


def _contains_raw_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _FORBIDDEN_RAW_KEYS:
                return key
            nested = _contains_raw_key(item)
            if nested is not None:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = _contains_raw_key(item)
            if nested is not None:
                return nested
    return None


def _mapping(name: str, value: Mapping[str, Any], *, required: bool = False) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if required and not value:
        raise ValueError(f"{name} is required")
    bad_raw = _contains_raw_key(value)
    if bad_raw is not None:
        raise ValueError(f"{name} may not duplicate raw model payload field {bad_raw}")
    return _freeze(value)


@dataclass(frozen=True)
class CompilationPolicy:
    owner_order: tuple[CompilationKind, ...] = COMPILATION_KIND_ORDER
    decision_id: str = "D12"

    def __post_init__(self) -> None:
        order = tuple(
            item if isinstance(item, CompilationKind) else CompilationKind(item)
            for item in self.owner_order
        )
        if order != COMPILATION_KIND_ORDER:
            raise ValueError("owner_order must exactly match the governing V3 compilation order")
        _required("decision_id", self.decision_id)
        object.__setattr__(self, "owner_order", order)


@dataclass(frozen=True)
class CompilationCandidate:
    candidate_id: str
    failure_snapshot_id: str
    mechanism_id: str
    generalization_profile_id: str | None
    prior_generalized_evidence_ref: str | None
    generalization_class: GeneralizationClass
    mechanism_label_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_hashes: Mapping[str, str]
    supported_kinds: tuple[CompilationKind, ...]
    excluded_cheaper_kinds: Mapping[str, Any]
    trigger_contract: Mapping[str, Any]
    compiled_payload: Mapping[str, Any]
    verifier_contract: Mapping[str, Any]
    negative_transfer_boundary: tuple[str, ...]
    tested_region: str
    rollback_action: str
    partition: Partition
    operating_surface_profile_id: str | None = None
    tomography_assessment_id: str | None = None
    model_internal_residual: bool = False
    decision_id: str = "D12"

    def __post_init__(self) -> None:
        for name in ("candidate_id", "failure_snapshot_id", "mechanism_id", "tested_region", "rollback_action", "decision_id"):
            _required(name, getattr(self, name))
        if not isinstance(self.generalization_class, GeneralizationClass):
            object.__setattr__(self, "generalization_class", GeneralizationClass(self.generalization_class))
        if self.generalization_class is GeneralizationClass.INSTANCE_PATCH:
            raise ValueError("INSTANCE_PATCH is not eligible for Stage-8 compilation")
        if not isinstance(self.partition, Partition):
            object.__setattr__(self, "partition", Partition(self.partition))
        if self.partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("FRESH/SEALED protected partitions cannot enter Stage-8 development compilation")
        if type(self.model_internal_residual) is not bool:
            raise TypeError("model_internal_residual must be boolean")

        has_profile = self.generalization_profile_id is not None
        has_prior = self.prior_generalized_evidence_ref is not None
        if has_profile == has_prior:
            raise ValueError("exactly one canonical generalization source is required")
        if self.generalization_profile_id is not None:
            _required("generalization_profile_id", self.generalization_profile_id)
        if self.prior_generalized_evidence_ref is not None:
            _required("prior_generalized_evidence_ref", self.prior_generalized_evidence_ref)
        if self.operating_surface_profile_id is not None:
            _required("operating_surface_profile_id", self.operating_surface_profile_id)
        if self.tomography_assessment_id is not None:
            _required("tomography_assessment_id", self.tomography_assessment_id)

        labels = _string_tuple("mechanism_label_ids", self.mechanism_label_ids)
        evidence = _string_tuple("evidence_refs", self.evidence_refs)
        kinds = _enum_tuple("supported_kinds", self.supported_kinds, CompilationKind)
        boundary = _string_tuple("negative_transfer_boundary", self.negative_transfer_boundary)
        trigger = _mapping("trigger_contract", self.trigger_contract, required=True)
        bad_trigger = _contains_forbidden_trigger_key(trigger)
        if bad_trigger is not None:
            raise ValueError(f"trigger_contract contains forbidden oracle/family key {bad_trigger}")
        payload = _mapping("compiled_payload", self.compiled_payload, required=True)
        verifier = _mapping("verifier_contract", self.verifier_contract)
        excluded = _mapping("excluded_cheaper_kinds", self.excluded_cheaper_kinds)
        allowed_exclusion_keys = {item.value for item in COMPILATION_KIND_ORDER}
        if any(key not in allowed_exclusion_keys for key in excluded):
            raise ValueError("excluded_cheaper_kinds contains unknown CompilationKind")
        if any(not isinstance(reason, str) or not reason.strip() for reason in excluded.values()):
            raise ValueError("excluded_cheaper_kinds values must be non-blank reasons")

        object.__setattr__(self, "mechanism_label_ids", labels)
        object.__setattr__(self, "evidence_refs", evidence)
        object.__setattr__(self, "source_hashes", _validate_sha_mapping("source_hashes", self.source_hashes))
        object.__setattr__(self, "supported_kinds", kinds)
        object.__setattr__(self, "excluded_cheaper_kinds", excluded)
        object.__setattr__(self, "trigger_contract", trigger)
        object.__setattr__(self, "compiled_payload", payload)
        object.__setattr__(self, "verifier_contract", verifier)
        object.__setattr__(self, "negative_transfer_boundary", boundary)

        expected = self._canonical_id()
        if self.candidate_id != expected:
            raise ValueError("candidate_id does not match canonical compilation candidate")

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "failure_snapshot_id": self.failure_snapshot_id,
            "mechanism_id": self.mechanism_id,
            "generalization_profile_id": self.generalization_profile_id,
            "prior_generalized_evidence_ref": self.prior_generalized_evidence_ref,
            "generalization_class": self.generalization_class,
            "mechanism_label_ids": self.mechanism_label_ids,
            "evidence_refs": self.evidence_refs,
            "source_hashes": self.source_hashes,
            "supported_kinds": self.supported_kinds,
            "excluded_cheaper_kinds": self.excluded_cheaper_kinds,
            "trigger_contract": self.trigger_contract,
            "compiled_payload": self.compiled_payload,
            "verifier_contract": self.verifier_contract,
            "negative_transfer_boundary": self.negative_transfer_boundary,
            "tested_region": self.tested_region,
            "rollback_action": self.rollback_action,
            "partition": self.partition,
            "operating_surface_profile_id": self.operating_surface_profile_id,
            "tomography_assessment_id": self.tomography_assessment_id,
            "model_internal_residual": self.model_internal_residual,
            "decision_id": self.decision_id,
        }

    def _canonical_id(self) -> str:
        return _stable_id("compilation-candidate", self._identity_payload())

    @classmethod
    def create(
        cls,
        *,
        failure_snapshot_id: str,
        mechanism_id: str,
        generalization_profile_id: str | None,
        prior_generalized_evidence_ref: str | None,
        generalization_class: GeneralizationClass,
        mechanism_label_ids: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        source_hashes: Mapping[str, str],
        supported_kinds: tuple[CompilationKind, ...],
        excluded_cheaper_kinds: Mapping[str, Any],
        trigger_contract: Mapping[str, Any],
        compiled_payload: Mapping[str, Any],
        verifier_contract: Mapping[str, Any],
        negative_transfer_boundary: tuple[str, ...],
        tested_region: str,
        rollback_action: str,
        partition: Partition,
        operating_surface_profile_id: str | None = None,
        tomography_assessment_id: str | None = None,
        model_internal_residual: bool = False,
        decision_id: str = "D12",
    ) -> "CompilationCandidate":
        provisional = cls.__new__(cls)
        # Build the canonical payload using the same normalization rules as __post_init__.
        values = {
            "candidate_id": "placeholder",
            "failure_snapshot_id": failure_snapshot_id,
            "mechanism_id": mechanism_id,
            "generalization_profile_id": generalization_profile_id,
            "prior_generalized_evidence_ref": prior_generalized_evidence_ref,
            "generalization_class": generalization_class,
            "mechanism_label_ids": mechanism_label_ids,
            "evidence_refs": evidence_refs,
            "source_hashes": source_hashes,
            "supported_kinds": supported_kinds,
            "excluded_cheaper_kinds": excluded_cheaper_kinds,
            "trigger_contract": trigger_contract,
            "compiled_payload": compiled_payload,
            "verifier_contract": verifier_contract,
            "negative_transfer_boundary": negative_transfer_boundary,
            "tested_region": tested_region,
            "rollback_action": rollback_action,
            "partition": partition,
            "operating_surface_profile_id": operating_surface_profile_id,
            "tomography_assessment_id": tomography_assessment_id,
            "model_internal_residual": model_internal_residual,
            "decision_id": decision_id,
        }
        # Construct once with a temporary ID, validate/normalize all fields except ID,
        # then derive the real content address from the normalized scientific payload.
        for name, value in values.items():
            object.__setattr__(provisional, name, value)
        # Reuse the validation code by manually performing normalization before hashing.
        if not isinstance(provisional.generalization_class, GeneralizationClass):
            object.__setattr__(provisional, "generalization_class", GeneralizationClass(provisional.generalization_class))
        if provisional.generalization_class is GeneralizationClass.INSTANCE_PATCH:
            raise ValueError("INSTANCE_PATCH is not eligible for Stage-8 compilation")
        if not isinstance(provisional.partition, Partition):
            object.__setattr__(provisional, "partition", Partition(provisional.partition))
        if provisional.partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("FRESH/SEALED protected partitions cannot enter Stage-8 development compilation")
        if type(provisional.model_internal_residual) is not bool:
            raise TypeError("model_internal_residual must be boolean")
        has_profile = provisional.generalization_profile_id is not None
        has_prior = provisional.prior_generalized_evidence_ref is not None
        if has_profile == has_prior:
            raise ValueError("exactly one canonical generalization source is required")
        if provisional.generalization_profile_id is not None:
            _required("generalization_profile_id", provisional.generalization_profile_id)
        if provisional.prior_generalized_evidence_ref is not None:
            _required("prior_generalized_evidence_ref", provisional.prior_generalized_evidence_ref)
        for name in ("failure_snapshot_id", "mechanism_id", "tested_region", "rollback_action", "decision_id"):
            _required(name, getattr(provisional, name))
        if provisional.operating_surface_profile_id is not None:
            _required("operating_surface_profile_id", provisional.operating_surface_profile_id)
        if provisional.tomography_assessment_id is not None:
            _required("tomography_assessment_id", provisional.tomography_assessment_id)
        object.__setattr__(provisional, "mechanism_label_ids", _string_tuple("mechanism_label_ids", provisional.mechanism_label_ids))
        object.__setattr__(provisional, "evidence_refs", _string_tuple("evidence_refs", provisional.evidence_refs))
        object.__setattr__(provisional, "source_hashes", _validate_sha_mapping("source_hashes", provisional.source_hashes))
        object.__setattr__(provisional, "supported_kinds", _enum_tuple("supported_kinds", provisional.supported_kinds, CompilationKind))
        object.__setattr__(provisional, "negative_transfer_boundary", _string_tuple("negative_transfer_boundary", provisional.negative_transfer_boundary))
        trigger = _mapping("trigger_contract", provisional.trigger_contract, required=True)
        bad_trigger = _contains_forbidden_trigger_key(trigger)
        if bad_trigger is not None:
            raise ValueError(f"trigger_contract contains forbidden oracle/family key {bad_trigger}")
        object.__setattr__(provisional, "trigger_contract", trigger)
        object.__setattr__(provisional, "compiled_payload", _mapping("compiled_payload", provisional.compiled_payload, required=True))
        object.__setattr__(provisional, "verifier_contract", _mapping("verifier_contract", provisional.verifier_contract))
        excluded = _mapping("excluded_cheaper_kinds", provisional.excluded_cheaper_kinds)
        allowed_exclusion_keys = {item.value for item in COMPILATION_KIND_ORDER}
        if any(key not in allowed_exclusion_keys for key in excluded):
            raise ValueError("excluded_cheaper_kinds contains unknown CompilationKind")
        if any(not isinstance(reason, str) or not reason.strip() for reason in excluded.values()):
            raise ValueError("excluded_cheaper_kinds values must be non-blank reasons")
        object.__setattr__(provisional, "excluded_cheaper_kinds", excluded)
        candidate_id = _stable_id("compilation-candidate", provisional._identity_payload())
        return cls(candidate_id=candidate_id, **{key: value for key, value in values.items() if key != "candidate_id"})


@dataclass(frozen=True)
class CompilationPlan:
    plan_id: str
    candidate_id: str
    selected_kind: CompilationKind
    rejected_cheaper_kinds: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    projected_model_calls: int
    expected_disposition: CompilationDisposition

    def __post_init__(self) -> None:
        for name in ("plan_id", "candidate_id"):
            _required(name, getattr(self, name))
        if not isinstance(self.selected_kind, CompilationKind):
            object.__setattr__(self, "selected_kind", CompilationKind(self.selected_kind))
        if not isinstance(self.expected_disposition, CompilationDisposition):
            object.__setattr__(self, "expected_disposition", CompilationDisposition(self.expected_disposition))
        if self.projected_model_calls != 0:
            raise ValueError("Stage-8 compilation plans must project zero model calls")
        object.__setattr__(self, "rejected_cheaper_kinds", _mapping("rejected_cheaper_kinds", self.rejected_cheaper_kinds))
        object.__setattr__(self, "evidence_refs", _string_tuple("evidence_refs", self.evidence_refs))
        expected = _stable_id(
            "compilation-plan",
            {
                "candidate_id": self.candidate_id,
                "selected_kind": self.selected_kind,
                "rejected_cheaper_kinds": self.rejected_cheaper_kinds,
                "evidence_refs": self.evidence_refs,
                "projected_model_calls": self.projected_model_calls,
                "expected_disposition": self.expected_disposition,
            },
        )
        if self.plan_id != expected:
            raise ValueError("plan_id does not match canonical compilation plan")

    @classmethod
    def create(
        cls,
        *,
        candidate_id: str,
        selected_kind: CompilationKind,
        rejected_cheaper_kinds: Mapping[str, Any],
        evidence_refs: tuple[str, ...],
        expected_disposition: CompilationDisposition,
    ) -> "CompilationPlan":
        selected_kind = selected_kind if isinstance(selected_kind, CompilationKind) else CompilationKind(selected_kind)
        expected_disposition = (
            expected_disposition
            if isinstance(expected_disposition, CompilationDisposition)
            else CompilationDisposition(expected_disposition)
        )
        rejected = _mapping("rejected_cheaper_kinds", rejected_cheaper_kinds)
        refs = _string_tuple("evidence_refs", evidence_refs)
        payload = {
            "candidate_id": candidate_id,
            "selected_kind": selected_kind,
            "rejected_cheaper_kinds": rejected,
            "evidence_refs": refs,
            "projected_model_calls": 0,
            "expected_disposition": expected_disposition,
        }
        return cls(plan_id=_stable_id("compilation-plan", payload), **payload)


@dataclass(frozen=True)
class CompiledCapability:
    capability_id: str
    capability_key: str
    candidate_id: str
    failure_snapshot_id: str
    mechanism_id: str
    generalization_profile_id: str | None
    prior_generalized_evidence_ref: str | None
    selected_kind: CompilationKind
    version: int
    previous_capability_id: str | None
    disposition: CompilationDisposition
    trigger_contract: Mapping[str, Any]
    compiled_payload: Mapping[str, Any]
    verifier_contract: Mapping[str, Any]
    negative_transfer_boundary: tuple[str, ...]
    tested_region: str
    evidence_refs: tuple[str, ...]
    source_hashes: Mapping[str, str]
    rollback_action: str
    partition: Partition
    handoff: str
    deployment_allowed: bool = False
    fresh_validation_required: bool = True

    def __post_init__(self) -> None:
        for name in ("capability_id", "capability_key", "candidate_id", "failure_snapshot_id", "mechanism_id", "tested_region", "rollback_action", "handoff"):
            _required(name, getattr(self, name))
        if not isinstance(self.selected_kind, CompilationKind):
            object.__setattr__(self, "selected_kind", CompilationKind(self.selected_kind))
        if not isinstance(self.disposition, CompilationDisposition):
            object.__setattr__(self, "disposition", CompilationDisposition(self.disposition))
        if not isinstance(self.partition, Partition):
            object.__setattr__(self, "partition", Partition(self.partition))
        if self.partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("compiled Stage-8 capability cannot originate from protected FRESH/SEALED partition")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise ValueError("version must be an integer >= 1")
        if self.version == 1 and self.previous_capability_id is not None:
            raise ValueError("version 1 may not reference a previous capability")
        if self.version > 1 and (not isinstance(self.previous_capability_id, str) or not self.previous_capability_id.strip()):
            raise ValueError("version > 1 requires previous capability ID")
        if self.deployment_allowed is not False:
            raise ValueError("Stage 8 cannot set deployment_allowed=True")
        if self.fresh_validation_required is not True:
            raise ValueError("Stage-8 compiled capabilities require fresh validation")
        object.__setattr__(self, "trigger_contract", _mapping("trigger_contract", self.trigger_contract, required=True))
        bad_trigger = _contains_forbidden_trigger_key(self.trigger_contract)
        if bad_trigger is not None:
            raise ValueError(f"trigger_contract contains forbidden oracle/family key {bad_trigger}")
        object.__setattr__(self, "compiled_payload", _mapping("compiled_payload", self.compiled_payload, required=True))
        object.__setattr__(self, "verifier_contract", _mapping("verifier_contract", self.verifier_contract))
        object.__setattr__(self, "negative_transfer_boundary", _string_tuple("negative_transfer_boundary", self.negative_transfer_boundary))
        object.__setattr__(self, "evidence_refs", _string_tuple("evidence_refs", self.evidence_refs))
        object.__setattr__(self, "source_hashes", _validate_sha_mapping("source_hashes", self.source_hashes))

    @classmethod
    def create(
        cls,
        *,
        candidate: CompilationCandidate,
        selected_kind: CompilationKind,
        version: int,
        previous_capability_id: str | None,
        disposition: CompilationDisposition,
        handoff: str,
    ) -> "CompiledCapability":
        if not isinstance(candidate, CompilationCandidate):
            raise TypeError("candidate must be CompilationCandidate")
        selected = selected_kind if isinstance(selected_kind, CompilationKind) else CompilationKind(selected_kind)
        if selected not in candidate.supported_kinds:
            raise ValueError("selected_kind must be supported by candidate evidence")
        disposition = disposition if isinstance(disposition, CompilationDisposition) else CompilationDisposition(disposition)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError("version must be an integer >= 1")
        if version == 1 and previous_capability_id is not None:
            raise ValueError("version 1 may not reference a previous capability")
        if version > 1 and (not isinstance(previous_capability_id, str) or not previous_capability_id.strip()):
            raise ValueError("version > 1 requires previous capability ID")
        _required("handoff", handoff)

        capability_key = _stable_id(
            "capability-key",
            {
                "mechanism_id": candidate.mechanism_id,
                "trigger_contract": candidate.trigger_contract,
            },
            length=20,
        )
        payload = {
            "capability_key": capability_key,
            "candidate_id": candidate.candidate_id,
            "failure_snapshot_id": candidate.failure_snapshot_id,
            "mechanism_id": candidate.mechanism_id,
            "generalization_profile_id": candidate.generalization_profile_id,
            "prior_generalized_evidence_ref": candidate.prior_generalized_evidence_ref,
            "selected_kind": selected,
            "version": version,
            "previous_capability_id": previous_capability_id,
            "disposition": disposition,
            "trigger_contract": candidate.trigger_contract,
            "compiled_payload": candidate.compiled_payload,
            "verifier_contract": candidate.verifier_contract,
            "negative_transfer_boundary": candidate.negative_transfer_boundary,
            "tested_region": candidate.tested_region,
            "evidence_refs": candidate.evidence_refs,
            "source_hashes": candidate.source_hashes,
            "rollback_action": candidate.rollback_action,
            "partition": candidate.partition,
            "handoff": handoff,
            "deployment_allowed": False,
            "fresh_validation_required": True,
        }
        capability_id = _stable_id("compiled-capability", payload)
        return cls(capability_id=capability_id, **payload)
