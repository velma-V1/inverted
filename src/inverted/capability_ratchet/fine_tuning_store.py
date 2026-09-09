"""Append-only metadata store for V3 Stage-9 fine-tuning qualification."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, TypeVar

from .core import Partition
from .fine_tuning_core import (
    ControlledTuningPlan,
    DatasetRole,
    FineTuningCandidate,
    FineTuningDataset,
    FineTuningDisposition,
    FineTuningExample,
    FineTuningQualification,
)

T = TypeVar("T")
_DATA_FILES = (
    "fine-tuning-candidates.jsonl",
    "fine-tuning-datasets.jsonl",
    "fine-tuning-qualifications.jsonl",
    "controlled-tuning-plans.jsonl",
)
_FORBIDDEN = frozenset({"raw_response", "raw_model_response", "raw_thinking", "chain_of_thought", "oracle_answer", "messages", "prompt"})


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(x) for x in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported Stage-9 store value: {type(value).__name__}")


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(_json_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _forbidden(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN:
                return str(key)
            nested = _forbidden(item)
            if nested:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = _forbidden(item)
            if nested:
                return nested
    return None


def _candidate_payload(x: FineTuningCandidate) -> dict[str, Any]:
    return {
        "candidate_id": x.candidate_id, "stage8_candidate_id": x.stage8_candidate_id, "mechanism_id": x.mechanism_id,
        "failure_snapshot_ids": x.failure_snapshot_ids, "generalization_evidence_refs": x.generalization_evidence_refs,
        "tomography_assessment_refs": x.tomography_assessment_refs, "cheaper_owner_exclusions": x.cheaper_owner_exclusions,
        "trigger_contract": x.trigger_contract, "allowed_region": x.allowed_region,
        "negative_transfer_boundary": x.negative_transfer_boundary, "source_hashes": x.source_hashes,
        "partition": x.partition.value, "base_model_profile_id": x.base_model_profile_id,
        "regression_evidence_refs": x.regression_evidence_refs, "model_internal_residual": x.model_internal_residual,
        "generalization_complete": x.generalization_complete, "cheaper_owners_resolved": x.cheaper_owners_resolved,
        "decision_id": x.decision_id,
    }


def _candidate_from(p: Mapping[str, Any]) -> FineTuningCandidate:
    q = dict(p)
    return FineTuningCandidate(
        candidate_id=str(q["candidate_id"]), stage8_candidate_id=str(q["stage8_candidate_id"]), mechanism_id=str(q["mechanism_id"]),
        failure_snapshot_ids=tuple(q["failure_snapshot_ids"]), generalization_evidence_refs=tuple(q["generalization_evidence_refs"]),
        tomography_assessment_refs=tuple(q["tomography_assessment_refs"]), cheaper_owner_exclusions=dict(q["cheaper_owner_exclusions"]),
        trigger_contract=dict(q["trigger_contract"]), allowed_region=str(q["allowed_region"]),
        negative_transfer_boundary=tuple(q["negative_transfer_boundary"]), source_hashes=dict(q["source_hashes"]),
        partition=Partition(q["partition"]), base_model_profile_id=str(q["base_model_profile_id"]),
        regression_evidence_refs=tuple(q["regression_evidence_refs"]), model_internal_residual=bool(q["model_internal_residual"]),
        generalization_complete=bool(q["generalization_complete"]), cheaper_owners_resolved=bool(q["cheaper_owners_resolved"]),
        decision_id=str(q.get("decision_id", "D11")),
    )


def _example_payload(x: FineTuningExample) -> dict[str, Any]:
    return {
        "example_id": x.example_id, "failure_snapshot_id": x.failure_snapshot_id, "replay_evidence_refs": x.replay_evidence_refs,
        "model_visible_input_ref": x.model_visible_input_ref, "model_visible_input_hash": x.model_visible_input_hash,
        "observable_target_ref": x.observable_target_ref, "observable_target_hash": x.observable_target_hash,
        "target_type": x.target_type, "role": x.role.value, "partition": x.partition.value,
        "base_model_profile_id": x.base_model_profile_id,
    }


def _example_from(p: Mapping[str, Any]) -> FineTuningExample:
    q = dict(p)
    return FineTuningExample(
        example_id=str(q["example_id"]), failure_snapshot_id=str(q["failure_snapshot_id"]), replay_evidence_refs=tuple(q["replay_evidence_refs"]),
        model_visible_input_ref=str(q["model_visible_input_ref"]), model_visible_input_hash=str(q["model_visible_input_hash"]),
        observable_target_ref=str(q["observable_target_ref"]), observable_target_hash=str(q["observable_target_hash"]), target_type=str(q["target_type"]),
        role=DatasetRole(q["role"]), partition=Partition(q["partition"]), base_model_profile_id=str(q["base_model_profile_id"]),
    )


def _dataset_payload(x: FineTuningDataset) -> dict[str, Any]:
    return {
        "dataset_id": x.dataset_id, "dataset_hash": x.dataset_hash, "candidate_id": x.candidate_id,
        "examples": [_example_payload(e) for e in x.examples], "train_example_ids": x.train_example_ids,
        "eval_example_ids": x.eval_example_ids, "regression_evidence_refs": x.regression_evidence_refs,
        "negative_transfer_refs": x.negative_transfer_refs,
    }


def _dataset_from(p: Mapping[str, Any]) -> FineTuningDataset:
    q = dict(p)
    return FineTuningDataset(
        dataset_id=str(q["dataset_id"]), dataset_hash=str(q["dataset_hash"]), candidate_id=str(q["candidate_id"]),
        examples=tuple(_example_from(x) for x in q["examples"]), train_example_ids=tuple(q["train_example_ids"]),
        eval_example_ids=tuple(q["eval_example_ids"]), regression_evidence_refs=tuple(q["regression_evidence_refs"]),
        negative_transfer_refs=tuple(q["negative_transfer_refs"]),
    )


def _qualification_payload(x: FineTuningQualification) -> dict[str, Any]:
    return {
        "qualification_id": x.qualification_id, "candidate_id": x.candidate_id, "disposition": x.disposition.value,
        "evidence_refs": x.evidence_refs, "dataset_id": x.dataset_id, "unresolved_risks": x.unresolved_risks, "route": x.route,
        "training_completed": x.training_completed, "certified": x.certified, "deployment_allowed": x.deployment_allowed,
        "stage11_confirmation_required": x.stage11_confirmation_required, "decision_id": x.decision_id,
    }


def _qualification_from(p: Mapping[str, Any]) -> FineTuningQualification:
    q = dict(p)
    return FineTuningQualification(
        qualification_id=str(q["qualification_id"]), candidate_id=str(q["candidate_id"]), disposition=FineTuningDisposition(q["disposition"]),
        evidence_refs=tuple(q["evidence_refs"]), dataset_id=q.get("dataset_id"), unresolved_risks=tuple(q["unresolved_risks"]), route=str(q["route"]),
        training_completed=bool(q.get("training_completed", False)), certified=bool(q.get("certified", False)),
        deployment_allowed=bool(q.get("deployment_allowed", False)), stage11_confirmation_required=bool(q.get("stage11_confirmation_required", True)),
        decision_id=str(q.get("decision_id", "D11")),
    )


def _plan_payload(x: ControlledTuningPlan) -> dict[str, Any]:
    return {
        "plan_id": x.plan_id, "qualification_id": x.qualification_id, "dataset_id": x.dataset_id,
        "base_model_profile_id": x.base_model_profile_id, "objective": x.objective, "hyperparameter_envelope": x.hyperparameter_envelope,
        "physical_training_budget_ceiling": x.physical_training_budget_ceiling, "evaluation_refs": x.evaluation_refs,
        "regression_refs": x.regression_refs, "abort_criteria": x.abort_criteria, "rollback_rule": x.rollback_rule,
        "authorization_status": x.authorization_status, "training_authorized": x.training_authorized,
        "projected_development_model_calls": x.projected_development_model_calls,
        "stage11_confirmation_required": x.stage11_confirmation_required,
    }


def _plan_from(p: Mapping[str, Any]) -> ControlledTuningPlan:
    q = dict(p)
    return ControlledTuningPlan(
        plan_id=str(q["plan_id"]), qualification_id=str(q["qualification_id"]), dataset_id=str(q["dataset_id"]),
        base_model_profile_id=str(q["base_model_profile_id"]), objective=str(q["objective"]), hyperparameter_envelope=dict(q["hyperparameter_envelope"]),
        physical_training_budget_ceiling=int(q["physical_training_budget_ceiling"]), evaluation_refs=tuple(q["evaluation_refs"]),
        regression_refs=tuple(q["regression_refs"]), abort_criteria=tuple(q["abort_criteria"]), rollback_rule=str(q["rollback_rule"]),
        authorization_status=str(q.get("authorization_status", "NOT_AUTHORIZED")), training_authorized=bool(q.get("training_authorized", False)),
        projected_development_model_calls=int(q.get("projected_development_model_calls", 0)),
        stage11_confirmation_required=bool(q.get("stage11_confirmation_required", True)),
    )


@dataclass(frozen=True)
class FineTuningStoreValidation:
    ok: bool
    candidate_count: int
    dataset_count: int
    qualification_count: int
    plan_count: int
    hash_mismatches: tuple[str, ...]
    malformed_rows: tuple[str, ...]
    duplicate_ids: tuple[str, ...]


class FineTuningEvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.candidate_path = self.root / _DATA_FILES[0]
        self.dataset_path = self.root / _DATA_FILES[1]
        self.qualification_path = self.root / _DATA_FILES[2]
        self.plan_path = self.root / _DATA_FILES[3]
        self.manifest_path = self.root / "SHA256SUMS.csv"
        self._lock = threading.RLock()

    def _manifest_bytes(self) -> bytes:
        rows = []
        for name in _DATA_FILES:
            path = self.root / name
            if path.exists():
                rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()},{name}")
        return (("\n".join(rows) + "\n") if rows else "").encode("ascii")

    def _manifest_ok(self) -> bool:
        expected = self._manifest_bytes()
        if not expected:
            return not self.manifest_path.exists() or self.manifest_path.read_bytes() == b""
        return self.manifest_path.exists() and self.manifest_path.read_bytes() == expected

    def _write_manifest(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_bytes(self._manifest_bytes())

    @staticmethod
    def _rows(path: Path, decoder: Callable[[Mapping[str, Any]], T], id_name: str) -> tuple[T, ...]:
        if not path.exists():
            return ()
        raw = path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise ValueError(f"{path.name} must end with newline")
        result = []
        for number, line in enumerate(raw.splitlines(), 1):
            if not line:
                raise ValueError(f"{path.name}:{number} blank row")
            payload = json.loads(line.decode("utf-8"))
            if line != _canonical(payload):
                raise ValueError(f"{path.name}:{number} is not canonical JSON")
            if _forbidden(payload):
                raise ValueError(f"{path.name}:{number} duplicates forbidden raw/oracle material")
            result.append(decoder(payload))
        ids = [str(getattr(x, id_name)) for x in result]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{path.name} contains duplicate logical IDs")
        return tuple(result)

    def _append(self, path: Path, logical_id: str, payload: Mapping[str, Any], decoder: Callable[[Mapping[str, Any]], T], id_name: str) -> str:
        line = _canonical(payload)
        if _forbidden(payload):
            raise ValueError("Stage-9 metadata may not duplicate raw thinking/oracle material")
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            if not self._manifest_ok():
                raise ValueError("Stage-9 manifest integrity mismatch; refusing append")
            existing = self._rows(path, decoder, id_name)
            for item in existing:
                if str(getattr(item, id_name)) == logical_id:
                    if _canonical(payload) != _canonical(self._payload_for(item)):
                        raise ValueError("existing logical ID has different canonical content")
                    return logical_id
            with path.open("ab") as handle:
                handle.write(line + b"\n")
                handle.flush(); os.fsync(handle.fileno())
            self._write_manifest()
        return logical_id

    @staticmethod
    def _payload_for(value: Any) -> Mapping[str, Any]:
        if isinstance(value, FineTuningCandidate): return _candidate_payload(value)
        if isinstance(value, FineTuningDataset): return _dataset_payload(value)
        if isinstance(value, FineTuningQualification): return _qualification_payload(value)
        if isinstance(value, ControlledTuningPlan): return _plan_payload(value)
        raise TypeError("unsupported Stage-9 evidence type")

    def append_candidate(self, value: FineTuningCandidate) -> str:
        return self._append(self.candidate_path, value.candidate_id, _candidate_payload(value), _candidate_from, "candidate_id")

    def append_dataset(self, value: FineTuningDataset) -> str:
        if value.candidate_id not in {x.candidate_id for x in self.candidates()}:
            raise ValueError("dataset references unknown Stage-9 candidate")
        return self._append(self.dataset_path, value.dataset_id, _dataset_payload(value), _dataset_from, "dataset_id")

    def append_qualification(self, value: FineTuningQualification) -> str:
        if value.candidate_id not in {x.candidate_id for x in self.candidates()}:
            raise ValueError("qualification references unknown Stage-9 candidate")
        if value.dataset_id is not None and value.dataset_id not in {x.dataset_id for x in self.datasets()}:
            raise ValueError("qualification references unknown Stage-9 dataset")
        return self._append(self.qualification_path, value.qualification_id, _qualification_payload(value), _qualification_from, "qualification_id")

    def append_plan(self, value: ControlledTuningPlan) -> str:
        if value.qualification_id not in {x.qualification_id for x in self.qualifications()}:
            raise ValueError("plan references unknown Stage-9 qualification")
        return self._append(self.plan_path, value.plan_id, _plan_payload(value), _plan_from, "plan_id")

    def candidates(self) -> tuple[FineTuningCandidate, ...]: return self._rows(self.candidate_path, _candidate_from, "candidate_id")
    def datasets(self) -> tuple[FineTuningDataset, ...]: return self._rows(self.dataset_path, _dataset_from, "dataset_id")
    def qualifications(self) -> tuple[FineTuningQualification, ...]: return self._rows(self.qualification_path, _qualification_from, "qualification_id")
    def plans(self) -> tuple[ControlledTuningPlan, ...]: return self._rows(self.plan_path, _plan_from, "plan_id")

    def get_candidate(self, logical_id: str) -> FineTuningCandidate:
        matches = [x for x in self.candidates() if x.candidate_id == logical_id]
        if len(matches) != 1: raise KeyError(logical_id)
        return matches[0]

    def get_dataset(self, logical_id: str) -> FineTuningDataset:
        matches = [x for x in self.datasets() if x.dataset_id == logical_id]
        if len(matches) != 1: raise KeyError(logical_id)
        return matches[0]

    def get_qualification(self, logical_id: str) -> FineTuningQualification:
        matches = [x for x in self.qualifications() if x.qualification_id == logical_id]
        if len(matches) != 1: raise KeyError(logical_id)
        return matches[0]

    def validate(self) -> FineTuningStoreValidation:
        malformed: list[str] = []
        duplicates: list[str] = []
        counts = [0, 0, 0, 0]
        specs = ((self.candidate_path, _candidate_from, "candidate_id"), (self.dataset_path, _dataset_from, "dataset_id"), (self.qualification_path, _qualification_from, "qualification_id"), (self.plan_path, _plan_from, "plan_id"))
        for idx, (path, decoder, id_name) in enumerate(specs):
            try:
                rows = self._rows(path, decoder, id_name); counts[idx] = len(rows)
            except Exception as exc:
                malformed.append(f"{path.name}:{exc}")
        hash_mismatches = () if self._manifest_ok() else ("SHA256SUMS.csv",)
        ok = not malformed and not duplicates and not hash_mismatches
        return FineTuningStoreValidation(ok, counts[0], counts[1], counts[2], counts[3], tuple(hash_mismatches), tuple(malformed), tuple(duplicates))
