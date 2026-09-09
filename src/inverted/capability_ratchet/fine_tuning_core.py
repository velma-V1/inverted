"""Frozen zero-inference contracts for V3 Stage-9 fine-tuning qualification."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .core import Partition


class FineTuningEligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    ALREADY_QUALIFIED = "ALREADY_QUALIFIED"
    CHEAPER_OWNER_UNRESOLVED = "CHEAPER_OWNER_UNRESOLVED"
    INSUFFICIENT_MODEL_OWNERSHIP_EVIDENCE = "INSUFFICIENT_MODEL_OWNERSHIP_EVIDENCE"
    INSUFFICIENT_REPEATED_PATTERN = "INSUFFICIENT_REPEATED_PATTERN"
    INSUFFICIENT_GENERALIZATION_EVIDENCE = "INSUFFICIENT_GENERALIZATION_EVIDENCE"
    INSUFFICIENT_TRAINING_EXAMPLES = "INSUFFICIENT_TRAINING_EXAMPLES"
    DATASET_LEAKAGE_RISK = "DATASET_LEAKAGE_RISK"
    PROTECTED_PARTITION = "PROTECTED_PARTITION"
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"
    NO_CANDIDATE = "NO_CANDIDATE"


class FineTuningDisposition(str, Enum):
    QUALIFY_CONTROLLED_LANE = "QUALIFY_CONTROLLED_LANE"
    NOT_JUSTIFIED = "NOT_JUSTIFIED"
    REQUIRES_MORE_EVIDENCE = "REQUIRES_MORE_EVIDENCE"
    ROUTE_STAGE10 = "ROUTE_STAGE10"
    ROUTE_ESCALATION = "ROUTE_ESCALATION"
    SAFE_STOP = "SAFE_STOP"
    ALREADY_QUALIFIED = "ALREADY_QUALIFIED"


class FineTuningPlanStatus(str, Enum):
    PLANNED = "PLANNED"
    NOT_JUSTIFIED = "NOT_JUSTIFIED"
    REQUIRES_MORE_EVIDENCE = "REQUIRES_MORE_EVIDENCE"
    ALREADY_QUALIFIED = "ALREADY_QUALIFIED"


class DatasetRole(str, Enum):
    TRAIN = "TRAIN"
    EVAL = "EVAL"


_FORBIDDEN_FRAGMENTS = (
    "oracle",
    "chain_of_thought",
    "chain-of-thought",
    "hidden_reasoning",
    "hidden-thinking",
    "raw_thinking",
    "raw_response",
    "raw_model_response",
    "forensic_thinking",
)
_ALLOWED_TARGET_TYPES = frozenset({"OBSERVABLE_CONTRACT_OUTPUT", "OBSERVABLE_VERIFIED_OUTPUT"})


def _required(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _strings(name: str, value: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a sequence of strings")
    result = tuple(value)
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise ValueError(f"{name} must contain non-blank strings")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must contain unique values")
    return result


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("fine-tuning payload numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported fine-tuning payload value: {type(value).__name__}")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("fine-tuning mapping keys must be strings")
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise TypeError("fine-tuning payload numbers must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported fine-tuning payload value: {type(value).__name__}")


def _scan_forbidden(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _FORBIDDEN_FRAGMENTS):
                return str(key)
            nested = _scan_forbidden(item)
            if nested is not None:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = _scan_forbidden(item)
            if nested is not None:
                return nested
    elif isinstance(value, str):
        lowered = value.lower()
        if any(fragment in lowered for fragment in _FORBIDDEN_FRAGMENTS):
            return value
    return None


def _mapping(name: str, value: Mapping[str, Any], *, required: bool = False) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if required and not value:
        raise ValueError(f"{name} is required")
    bad = _scan_forbidden(value)
    if bad is not None:
        raise ValueError(f"{name} contains forbidden oracle/raw thinking material: {bad}")
    return _freeze(value)


def _sha(name: str, value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _sha_mapping(name: str, value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{name} must be a non-empty mapping")
    normalized: dict[str, str] = {}
    for key, digest in value.items():
        normalized[_required(f"{name} key", key)] = _sha(f"{name} value", digest)
    return MappingProxyType(dict(sorted(normalized.items())))


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_json_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}-{_digest(payload)[:24]}"


@dataclass(frozen=True)
class FineTuningPolicy:
    schema_version: str = "v3-stage9-v1"
    decision_id: str = "D11"
    minimum_independent_failures: int = 2
    protect_fresh_and_sealed: bool = True
    require_model_internal_residual: bool = True
    require_cheaper_owners_resolved: bool = True
    require_generalization_evidence: bool = True
    require_disjoint_train_eval: bool = True
    require_observable_targets: bool = True
    require_no_oracle_leakage: bool = True
    require_regression_suite: bool = True
    certification_allowed: bool = False
    deployment_allowed: bool = False
    training_authorized_by_default: bool = False
    development_model_call_budget: int = 0

    def __post_init__(self) -> None:
        _required("schema_version", self.schema_version)
        if self.decision_id != "D11":
            raise ValueError("Stage 9 resolves D11")
        if not isinstance(self.minimum_independent_failures, int) or isinstance(self.minimum_independent_failures, bool) or self.minimum_independent_failures < 2:
            raise ValueError("minimum independent recurrence must be at least 2")
        if self.development_model_call_budget != 0:
            raise ValueError("Stage-9 development planning must use zero model calls")
        if self.certification_allowed or self.deployment_allowed or self.training_authorized_by_default:
            raise ValueError("Stage 9 cannot authorize training, certification, or deployment by default")


@dataclass(frozen=True)
class FineTuningCandidate:
    candidate_id: str
    stage8_candidate_id: str
    mechanism_id: str
    failure_snapshot_ids: tuple[str, ...]
    generalization_evidence_refs: tuple[str, ...]
    tomography_assessment_refs: tuple[str, ...]
    cheaper_owner_exclusions: Mapping[str, Any]
    trigger_contract: Mapping[str, Any]
    allowed_region: str
    negative_transfer_boundary: tuple[str, ...]
    source_hashes: Mapping[str, str]
    partition: Partition
    base_model_profile_id: str
    regression_evidence_refs: tuple[str, ...]
    model_internal_residual: bool
    generalization_complete: bool
    cheaper_owners_resolved: bool
    decision_id: str = "D11"

    def __post_init__(self) -> None:
        for name in ("candidate_id", "stage8_candidate_id", "mechanism_id", "allowed_region", "base_model_profile_id"):
            _required(name, getattr(self, name))
        if self.decision_id != "D11":
            raise ValueError("fine-tuning candidate must resolve D11")
        partition = self.partition if isinstance(self.partition, Partition) else Partition(self.partition)
        if partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("FRESH/SEALED protected partitions cannot enter Stage-9 qualification")
        failures = _strings("failure_snapshot_ids", self.failure_snapshot_ids)
        if len(failures) < 2:
            raise ValueError("independent failure recurrence requires at least two failures")
        if not self.model_internal_residual:
            raise ValueError("MODEL_INTERNAL residual ownership is required for fine-tuning qualification")
        if not self.generalization_complete:
            raise ValueError("generalization evidence is required before Stage-9 qualification")
        if not self.cheaper_owners_resolved:
            raise ValueError("cheaper owners must be resolved before Stage-9 qualification")
        generalization = _strings("generalization_evidence_refs", self.generalization_evidence_refs)
        tomography = _strings("tomography_assessment_refs", self.tomography_assessment_refs, allow_empty=True)
        boundary = _strings("negative_transfer_boundary", self.negative_transfer_boundary)
        regression = _strings("regression_evidence_refs", self.regression_evidence_refs)
        exclusions = _mapping("cheaper_owner_exclusions", self.cheaper_owner_exclusions, required=True)
        trigger = _mapping("trigger_contract", self.trigger_contract, required=True)
        object.__setattr__(self, "partition", partition)
        object.__setattr__(self, "failure_snapshot_ids", tuple(sorted(failures)))
        object.__setattr__(self, "generalization_evidence_refs", tuple(sorted(generalization)))
        object.__setattr__(self, "tomography_assessment_refs", tuple(sorted(tomography)))
        object.__setattr__(self, "negative_transfer_boundary", tuple(sorted(boundary)))
        object.__setattr__(self, "regression_evidence_refs", tuple(sorted(regression)))
        object.__setattr__(self, "cheaper_owner_exclusions", exclusions)
        object.__setattr__(self, "trigger_contract", trigger)
        object.__setattr__(self, "source_hashes", _sha_mapping("source_hashes", self.source_hashes))
        if self.candidate_id != self._canonical_id():
            raise ValueError("candidate_id does not match canonical Stage-9 candidate")

    def _payload(self) -> dict[str, Any]:
        return {
            "stage8_candidate_id": self.stage8_candidate_id,
            "mechanism_id": self.mechanism_id,
            "failure_snapshot_ids": self.failure_snapshot_ids,
            "generalization_evidence_refs": self.generalization_evidence_refs,
            "tomography_assessment_refs": self.tomography_assessment_refs,
            "cheaper_owner_exclusions": self.cheaper_owner_exclusions,
            "trigger_contract": self.trigger_contract,
            "allowed_region": self.allowed_region,
            "negative_transfer_boundary": self.negative_transfer_boundary,
            "source_hashes": self.source_hashes,
            "partition": self.partition,
            "base_model_profile_id": self.base_model_profile_id,
            "regression_evidence_refs": self.regression_evidence_refs,
            "model_internal_residual": self.model_internal_residual,
            "generalization_complete": self.generalization_complete,
            "cheaper_owners_resolved": self.cheaper_owners_resolved,
            "decision_id": self.decision_id,
        }

    def _canonical_id(self) -> str:
        return _stable_id("fine-tuning-candidate", self._payload())

    @classmethod
    def create(cls, **kwargs: Any) -> "FineTuningCandidate":
        values = dict(kwargs)
        values["failure_snapshot_ids"] = tuple(sorted(_strings("failure_snapshot_ids", values["failure_snapshot_ids"])))
        values["generalization_evidence_refs"] = tuple(sorted(_strings("generalization_evidence_refs", values["generalization_evidence_refs"])))
        values["tomography_assessment_refs"] = tuple(sorted(_strings("tomography_assessment_refs", values.get("tomography_assessment_refs", ()), allow_empty=True)))
        values["negative_transfer_boundary"] = tuple(sorted(_strings("negative_transfer_boundary", values["negative_transfer_boundary"])))
        values["regression_evidence_refs"] = tuple(sorted(_strings("regression_evidence_refs", values["regression_evidence_refs"])))
        values["partition"] = values["partition"] if isinstance(values["partition"], Partition) else Partition(values["partition"])
        values["cheaper_owner_exclusions"] = _mapping("cheaper_owner_exclusions", values["cheaper_owner_exclusions"], required=True)
        values["trigger_contract"] = _mapping("trigger_contract", values["trigger_contract"], required=True)
        values["source_hashes"] = _sha_mapping("source_hashes", values["source_hashes"])
        values.setdefault("decision_id", "D11")
        payload = {key: values[key] for key in (
            "stage8_candidate_id", "mechanism_id", "failure_snapshot_ids", "generalization_evidence_refs",
            "tomography_assessment_refs", "cheaper_owner_exclusions", "trigger_contract", "allowed_region",
            "negative_transfer_boundary", "source_hashes", "partition", "base_model_profile_id",
            "regression_evidence_refs", "model_internal_residual", "generalization_complete",
            "cheaper_owners_resolved", "decision_id",
        )}
        values["candidate_id"] = _stable_id("fine-tuning-candidate", payload)
        return cls(**values)


@dataclass(frozen=True)
class FineTuningExample:
    example_id: str
    failure_snapshot_id: str
    replay_evidence_refs: tuple[str, ...]
    model_visible_input_ref: str
    model_visible_input_hash: str
    observable_target_ref: str
    observable_target_hash: str
    target_type: str
    role: DatasetRole
    partition: Partition
    base_model_profile_id: str

    def __post_init__(self) -> None:
        for name in ("example_id", "failure_snapshot_id", "model_visible_input_ref", "observable_target_ref", "target_type", "base_model_profile_id"):
            _required(name, getattr(self, name))
        partition = self.partition if isinstance(self.partition, Partition) else Partition(self.partition)
        if partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("FRESH/SEALED protected partitions cannot enter Stage-9 datasets")
        role = self.role if isinstance(self.role, DatasetRole) else DatasetRole(self.role)
        if self.target_type not in _ALLOWED_TARGET_TYPES:
            raise ValueError("hidden reasoning/oracle target types are forbidden; target must be observable")
        if _scan_forbidden({"target_type": self.target_type, "target_ref": self.observable_target_ref}) is not None:
            raise ValueError("hidden reasoning/oracle target material is forbidden")
        object.__setattr__(self, "partition", partition)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "replay_evidence_refs", tuple(sorted(_strings("replay_evidence_refs", self.replay_evidence_refs))))
        object.__setattr__(self, "model_visible_input_hash", _sha("model_visible_input_hash", self.model_visible_input_hash))
        object.__setattr__(self, "observable_target_hash", _sha("observable_target_hash", self.observable_target_hash))
        if self.example_id != self._canonical_id():
            raise ValueError("example_id does not match canonical Stage-9 example")

    def _payload(self) -> dict[str, Any]:
        return {
            "failure_snapshot_id": self.failure_snapshot_id,
            "replay_evidence_refs": self.replay_evidence_refs,
            "model_visible_input_ref": self.model_visible_input_ref,
            "model_visible_input_hash": self.model_visible_input_hash,
            "observable_target_ref": self.observable_target_ref,
            "observable_target_hash": self.observable_target_hash,
            "target_type": self.target_type,
            "role": self.role,
            "partition": self.partition,
            "base_model_profile_id": self.base_model_profile_id,
        }

    def _canonical_id(self) -> str:
        return _stable_id("fine-tuning-example", self._payload())

    @classmethod
    def create(cls, **kwargs: Any) -> "FineTuningExample":
        values = dict(kwargs)
        values["replay_evidence_refs"] = tuple(sorted(_strings("replay_evidence_refs", values["replay_evidence_refs"])))
        values["role"] = values["role"] if isinstance(values["role"], DatasetRole) else DatasetRole(values["role"])
        values["partition"] = values["partition"] if isinstance(values["partition"], Partition) else Partition(values["partition"])
        payload = {key: values[key] for key in (
            "failure_snapshot_id", "replay_evidence_refs", "model_visible_input_ref", "model_visible_input_hash",
            "observable_target_ref", "observable_target_hash", "target_type", "role", "partition", "base_model_profile_id",
        )}
        values["example_id"] = _stable_id("fine-tuning-example", payload)
        return cls(**values)


@dataclass(frozen=True)
class FineTuningDataset:
    dataset_id: str
    dataset_hash: str
    candidate_id: str
    examples: tuple[FineTuningExample, ...]
    train_example_ids: tuple[str, ...]
    eval_example_ids: tuple[str, ...]
    regression_evidence_refs: tuple[str, ...]
    negative_transfer_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _required("dataset_id", self.dataset_id)
        _required("candidate_id", self.candidate_id)
        _sha("dataset_hash", self.dataset_hash)
        if not isinstance(self.examples, (list, tuple)) or len(self.examples) < 2 or any(not isinstance(item, FineTuningExample) for item in self.examples):
            raise ValueError("dataset requires at least two FineTuningExample rows")
        examples = tuple(sorted(self.examples, key=lambda item: item.example_id))
        train = tuple(sorted(item.example_id for item in examples if item.role is DatasetRole.TRAIN))
        eval_ids = tuple(sorted(item.example_id for item in examples if item.role is DatasetRole.EVAL))
        if not train or not eval_ids:
            raise ValueError("dataset requires both TRAIN and EVAL examples")
        train_rows = [item for item in examples if item.role is DatasetRole.TRAIN]
        eval_rows = [item for item in examples if item.role is DatasetRole.EVAL]
        if {x.failure_snapshot_id for x in train_rows} & {x.failure_snapshot_id for x in eval_rows}:
            raise ValueError("train/eval failure lineage must be disjoint")
        if {x.model_visible_input_hash for x in train_rows} & {x.model_visible_input_hash for x in eval_rows}:
            raise ValueError("train/eval source content hashes must be disjoint to prevent leakage")
        if set(train) & set(eval_ids):
            raise ValueError("train/eval example IDs must be disjoint")
        regression = _strings("regression_evidence_refs", self.regression_evidence_refs)
        negative = _strings("negative_transfer_refs", self.negative_transfer_refs)
        object.__setattr__(self, "examples", examples)
        object.__setattr__(self, "train_example_ids", train)
        object.__setattr__(self, "eval_example_ids", eval_ids)
        object.__setattr__(self, "regression_evidence_refs", tuple(sorted(regression)))
        object.__setattr__(self, "negative_transfer_refs", tuple(sorted(negative)))
        payload = self._payload()
        expected_hash = _digest(payload)
        if self.dataset_hash != expected_hash or self.dataset_id != f"fine-tuning-dataset-{expected_hash[:24]}":
            raise ValueError("dataset identity does not match canonical content")

    def _payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "examples": [item._payload() | {"example_id": item.example_id} for item in self.examples],
            "regression_evidence_refs": self.regression_evidence_refs,
            "negative_transfer_refs": self.negative_transfer_refs,
        }

    @classmethod
    def create(cls, *, candidate_id: str, examples: tuple[FineTuningExample, ...], regression_evidence_refs: tuple[str, ...], negative_transfer_refs: tuple[str, ...]) -> "FineTuningDataset":
        _required("candidate_id", candidate_id)
        ordered = tuple(sorted(examples, key=lambda item: item.example_id))
        regression = tuple(sorted(_strings("regression_evidence_refs", regression_evidence_refs)))
        negative = tuple(sorted(_strings("negative_transfer_refs", negative_transfer_refs)))
        payload = {
            "candidate_id": candidate_id,
            "examples": [item._payload() | {"example_id": item.example_id} for item in ordered],
            "regression_evidence_refs": regression,
            "negative_transfer_refs": negative,
        }
        digest = _digest(payload)
        return cls(
            dataset_id=f"fine-tuning-dataset-{digest[:24]}", dataset_hash=digest, candidate_id=candidate_id,
            examples=ordered, train_example_ids=tuple(item.example_id for item in ordered if item.role is DatasetRole.TRAIN),
            eval_example_ids=tuple(item.example_id for item in ordered if item.role is DatasetRole.EVAL),
            regression_evidence_refs=regression, negative_transfer_refs=negative,
        )


@dataclass(frozen=True)
class FineTuningQualification:
    qualification_id: str
    candidate_id: str
    disposition: FineTuningDisposition
    evidence_refs: tuple[str, ...]
    dataset_id: str | None
    unresolved_risks: tuple[str, ...]
    route: str
    training_completed: bool = False
    certified: bool = False
    deployment_allowed: bool = False
    stage11_confirmation_required: bool = True
    decision_id: str = "D11"

    def __post_init__(self) -> None:
        for name in ("qualification_id", "candidate_id", "route"):
            _required(name, getattr(self, name))
        disposition = self.disposition if isinstance(self.disposition, FineTuningDisposition) else FineTuningDisposition(self.disposition)
        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "evidence_refs", tuple(sorted(_strings("evidence_refs", self.evidence_refs))))
        object.__setattr__(self, "unresolved_risks", tuple(sorted(_strings("unresolved_risks", self.unresolved_risks, allow_empty=True))))
        if disposition is FineTuningDisposition.QUALIFY_CONTROLLED_LANE and not self.dataset_id:
            raise ValueError("qualified controlled lane requires dataset_id")
        if self.dataset_id is not None:
            _required("dataset_id", self.dataset_id)
        if self.training_completed or self.certified or self.deployment_allowed:
            raise ValueError("Stage-9 qualification is not training, certification, or deployment")
        if not self.stage11_confirmation_required:
            raise ValueError("Stage 11 confirmation remains mandatory")
        if self.decision_id != "D11":
            raise ValueError("Stage 9 qualification must resolve D11")
        if self.qualification_id != self._canonical_id():
            raise ValueError("qualification_id does not match canonical qualification")

    def _payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id, "disposition": self.disposition, "evidence_refs": self.evidence_refs,
            "dataset_id": self.dataset_id, "unresolved_risks": self.unresolved_risks, "route": self.route,
            "training_completed": False, "certified": False, "deployment_allowed": False,
            "stage11_confirmation_required": True, "decision_id": self.decision_id,
        }

    def _canonical_id(self) -> str:
        return _stable_id("fine-tuning-qualification", self._payload())

    @classmethod
    def create(cls, **kwargs: Any) -> "FineTuningQualification":
        values = dict(kwargs)
        values["disposition"] = values["disposition"] if isinstance(values["disposition"], FineTuningDisposition) else FineTuningDisposition(values["disposition"])
        values["evidence_refs"] = tuple(sorted(_strings("evidence_refs", values["evidence_refs"])))
        values["unresolved_risks"] = tuple(sorted(_strings("unresolved_risks", values.get("unresolved_risks", ()), allow_empty=True)))
        values.setdefault("training_completed", False); values.setdefault("certified", False); values.setdefault("deployment_allowed", False)
        values.setdefault("stage11_confirmation_required", True); values.setdefault("decision_id", "D11")
        payload = {key: values[key] for key in (
            "candidate_id", "disposition", "evidence_refs", "dataset_id", "unresolved_risks", "route",
            "training_completed", "certified", "deployment_allowed", "stage11_confirmation_required", "decision_id",
        )}
        values["qualification_id"] = _stable_id("fine-tuning-qualification", payload)
        return cls(**values)


@dataclass(frozen=True)
class ControlledTuningPlan:
    plan_id: str
    qualification_id: str
    dataset_id: str
    base_model_profile_id: str
    objective: str
    hyperparameter_envelope: Mapping[str, Any]
    physical_training_budget_ceiling: int
    evaluation_refs: tuple[str, ...]
    regression_refs: tuple[str, ...]
    abort_criteria: tuple[str, ...]
    rollback_rule: str
    authorization_status: str = "NOT_AUTHORIZED"
    training_authorized: bool = False
    projected_development_model_calls: int = 0
    stage11_confirmation_required: bool = True

    def __post_init__(self) -> None:
        for name in ("plan_id", "qualification_id", "dataset_id", "base_model_profile_id", "objective", "rollback_rule"):
            _required(name, getattr(self, name))
        if self.authorization_status != "NOT_AUTHORIZED" or self.training_authorized:
            raise ValueError("Stage-9 controlled lane must remain NOT_AUTHORIZED")
        if self.projected_development_model_calls != 0:
            raise ValueError("Stage-9 development plan must use zero model calls")
        if not self.stage11_confirmation_required:
            raise ValueError("Stage 11 confirmation remains mandatory")
        if not isinstance(self.physical_training_budget_ceiling, int) or isinstance(self.physical_training_budget_ceiling, bool) or self.physical_training_budget_ceiling < 1:
            raise ValueError("physical_training_budget_ceiling must be a positive integer")
        envelope = _mapping("hyperparameter_envelope", self.hyperparameter_envelope, required=True)
        object.__setattr__(self, "hyperparameter_envelope", envelope)
        for name in ("evaluation_refs", "regression_refs", "abort_criteria"):
            object.__setattr__(self, name, tuple(sorted(_strings(name, getattr(self, name)))))
        if self.plan_id != self._canonical_id():
            raise ValueError("plan_id does not match canonical controlled tuning plan")

    def _payload(self) -> dict[str, Any]:
        return {
            "qualification_id": self.qualification_id, "dataset_id": self.dataset_id,
            "base_model_profile_id": self.base_model_profile_id, "objective": self.objective,
            "hyperparameter_envelope": self.hyperparameter_envelope,
            "physical_training_budget_ceiling": self.physical_training_budget_ceiling,
            "evaluation_refs": self.evaluation_refs, "regression_refs": self.regression_refs,
            "abort_criteria": self.abort_criteria, "rollback_rule": self.rollback_rule,
            "authorization_status": self.authorization_status, "training_authorized": False,
            "projected_development_model_calls": 0, "stage11_confirmation_required": True,
        }

    def _canonical_id(self) -> str:
        return _stable_id("controlled-tuning-plan", self._payload())

    @classmethod
    def create(cls, **kwargs: Any) -> "ControlledTuningPlan":
        values = dict(kwargs)
        values["hyperparameter_envelope"] = _mapping("hyperparameter_envelope", values["hyperparameter_envelope"], required=True)
        for name in ("evaluation_refs", "regression_refs", "abort_criteria"):
            values[name] = tuple(sorted(_strings(name, values[name])))
        values.setdefault("authorization_status", "NOT_AUTHORIZED")
        values.setdefault("training_authorized", False)
        values.setdefault("projected_development_model_calls", 0)
        values.setdefault("stage11_confirmation_required", True)
        payload = {key: values[key] for key in (
            "qualification_id", "dataset_id", "base_model_profile_id", "objective", "hyperparameter_envelope",
            "physical_training_budget_ceiling", "evaluation_refs", "regression_refs", "abort_criteria", "rollback_rule",
            "authorization_status", "training_authorized", "projected_development_model_calls", "stage11_confirmation_required",
        )}
        values["plan_id"] = _stable_id("controlled-tuning-plan", payload)
        return cls(**values)
