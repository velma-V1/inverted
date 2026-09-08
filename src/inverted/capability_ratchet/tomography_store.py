"""Append-only metadata store for Stage-7 tomography."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .core import Partition
from .tomography_core import (
    TomographyAxis,
    TomographyDisposition,
    TomographyOutcome,
    TomographyProbe,
    TomographyProfile,
    TomographyStatus,
    TomographyStopReason,
    TomographyStudy,
)


_FILENAME = "CAPABILITY_RATCHET_V3_TOMOGRAPHY.jsonl"
_FORBIDDEN_KEYS = {
    "raw_response", "raw_calls", "raw_call", "exposed_thinking", "thinking",
    "tool_result_payload", "tool_payload", "oracle_payload", "forensic_payload",
}


@dataclass(frozen=True)
class TomographyStoreValidation:
    ok: bool
    record_count: int
    duplicate_ids: tuple[str, ...]
    broken_references: tuple[str, ...]
    unsafe_fields: tuple[str, ...]


def _unsafe(value: Any, path: str = "") -> tuple[str, ...]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            if str(key).casefold() in _FORBIDDEN_KEYS:
                hits.append(child)
            hits.extend(_unsafe(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_unsafe(item, f"{path}.{index}"))
    return tuple(hits)


def _parse(record: dict[str, Any]):
    kind = record.get("record_type")
    if kind == "TOMOGRAPHY_STUDY":
        return TomographyStudy(
            study_id=record["study_id"], failure_snapshot_id=record["failure_snapshot_id"],
            parent_state_hash=record["parent_state_hash"], partition=Partition(record["partition"]),
            decision_ids=tuple(record["decision_ids"]),
            candidate_axes=tuple(TomographyAxis(item) for item in record["candidate_axes"]),
            baseline_evidence_refs=tuple(record["baseline_evidence_refs"]),
            probe_ids=tuple(record["probe_ids"]), max_new_probes=record["max_new_probes"],
            projected_calls=record["projected_calls"], status=TomographyStatus(record["status"]),
            stop_reason=(None if record.get("stop_reason") is None else TomographyStopReason(record["stop_reason"])),
        )
    if kind == "TOMOGRAPHY_PROBE":
        return TomographyProbe(
            probe_id=record["probe_id"], study_id=record["study_id"],
            axis=TomographyAxis(record["axis"]), intervention_id=record["intervention_id"],
            control_intervention_id=record.get("control_intervention_id"),
            changed_dimensions=tuple(record["changed_dimensions"]),
            expected_implication=record["expected_implication"],
            projected_calls=record["projected_calls"], protected=record["protected"],
        )
    if kind == "TOMOGRAPHY_OUTCOME":
        return TomographyOutcome(
            outcome_id=record["outcome_id"], study_id=record["study_id"], probe_id=record["probe_id"],
            replay_result_id=record["replay_result_id"], semantic_success=record["semantic_success"],
            contract_valid=record["contract_valid"], score=record["score"],
            first_divergence=record.get("first_divergence"),
            comparison_refs=tuple(record["comparison_refs"]),
            protected_regression=record["protected_regression"],
            child_failure_snapshot_id=record.get("child_failure_snapshot_id"),
        )
    if kind == "TOMOGRAPHY_PROFILE":
        return TomographyProfile(
            profile_id=record["profile_id"], study_id=record["study_id"],
            dispositions=tuple(TomographyDisposition(item) for item in record["dispositions"]),
            supported_hypotheses=tuple(record["supported_hypotheses"]),
            falsified_hypotheses=tuple(record["falsified_hypotheses"]),
            evidence_refs=tuple(record["evidence_refs"]), next_decisions=tuple(record["next_decisions"]),
            route_back_stage=record.get("route_back_stage"),
            model_internal_boundary=record["model_internal_boundary"],
            promotion_allowed=record["promotion_allowed"], certification_allowed=record["certification_allowed"],
            stop_reason=(None if record.get("stop_reason") is None else TomographyStopReason(record["stop_reason"])),
        )
    raise ValueError(f"unsupported tomography record_type: {kind!r}")


class TomographyEvidenceStore:
    """Persist only scientific metadata; canonical replay remains authoritative."""

    def __init__(
        self,
        root: str | Path,
        *,
        replay_result_exists: Callable[[str], bool] | None = None,
        failure_snapshot_exists: Callable[[str], bool] | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / _FILENAME
        self.replay_result_exists = replay_result_exists
        self.failure_snapshot_exists = failure_snapshot_exists

    @staticmethod
    def _logical_id(value: Any) -> str:
        for name in ("study_id", "probe_id", "outcome_id", "profile_id"):
            if hasattr(value, name):
                return str(getattr(value, name))
        raise TypeError("unsupported tomography record")

    def _records(self) -> tuple[Any, ...]:
        if not self.path.exists():
            return ()
        records: list[Any] = []
        for line_no, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise TypeError("row must be an object")
                records.append(_parse(payload))
            except Exception as exc:
                raise ValueError(f"invalid tomography row {line_no}: {exc}") from exc
        return tuple(records)

    def _append(self, value: Any) -> None:
        payload = value.to_record()
        unsafe = _unsafe(payload)
        if unsafe:
            raise ValueError(f"tomography metadata contains forbidden private payload fields: {unsafe}")
        logical = self._logical_id(value)
        if logical in {self._logical_id(item) for item in self._records()}:
            raise ValueError(f"duplicate tomography logical id: {logical}")
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")

    def append_study(self, value: TomographyStudy) -> None:
        if not isinstance(value, TomographyStudy):
            raise TypeError("value must be TomographyStudy")
        self._append(value)

    def append_probe(self, value: TomographyProbe) -> None:
        if not isinstance(value, TomographyProbe):
            raise TypeError("value must be TomographyProbe")
        self._append(value)

    def append_outcome(self, value: TomographyOutcome) -> None:
        if not isinstance(value, TomographyOutcome):
            raise TypeError("value must be TomographyOutcome")
        self._append(value)

    def append_profile(self, value: TomographyProfile) -> None:
        if not isinstance(value, TomographyProfile):
            raise TypeError("value must be TomographyProfile")
        self._append(value)

    def studies(self) -> tuple[TomographyStudy, ...]:
        return tuple(item for item in self._records() if isinstance(item, TomographyStudy))

    def probes(self) -> tuple[TomographyProbe, ...]:
        return tuple(item for item in self._records() if isinstance(item, TomographyProbe))

    def outcomes(self) -> tuple[TomographyOutcome, ...]:
        return tuple(item for item in self._records() if isinstance(item, TomographyOutcome))

    def profiles(self) -> tuple[TomographyProfile, ...]:
        return tuple(item for item in self._records() if isinstance(item, TomographyProfile))

    def validate(self) -> TomographyStoreValidation:
        if not self.path.exists():
            return TomographyStoreValidation(True, 0, (), (), ())
        payloads: list[dict[str, Any]] = []
        unsafe: list[str] = []
        parse_errors: list[str] = []
        for line_no, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise TypeError("row must be object")
                _parse(payload)
                payloads.append(payload)
                unsafe.extend(f"row:{line_no}:{hit}" for hit in _unsafe(payload))
            except Exception as exc:
                parse_errors.append(f"row:{line_no}:{exc}")
        ids: list[str] = []
        for payload in payloads:
            for key in ("study_id", "probe_id", "outcome_id", "profile_id"):
                if key in payload and payload.get("record_type") == {
                    "study_id": "TOMOGRAPHY_STUDY",
                    "probe_id": "TOMOGRAPHY_PROBE",
                    "outcome_id": "TOMOGRAPHY_OUTCOME",
                    "profile_id": "TOMOGRAPHY_PROFILE",
                }[key]:
                    ids.append(payload[key])
                    break
        duplicates = tuple(sorted({item for item in ids if ids.count(item) > 1}))
        study_ids = {row["study_id"] for row in payloads if row.get("record_type") == "TOMOGRAPHY_STUDY"}
        probe_ids = {row["probe_id"] for row in payloads if row.get("record_type") == "TOMOGRAPHY_PROBE"}
        broken = list(parse_errors)
        for row in payloads:
            kind = row.get("record_type")
            if kind in {"TOMOGRAPHY_PROBE", "TOMOGRAPHY_OUTCOME", "TOMOGRAPHY_PROFILE"} and row.get("study_id") not in study_ids:
                broken.append(f"missing-study:{row.get('study_id')}")
            if kind == "TOMOGRAPHY_OUTCOME":
                if row.get("probe_id") not in probe_ids:
                    broken.append(f"missing-probe:{row.get('probe_id')}")
                if self.replay_result_exists is not None and not self.replay_result_exists(row["replay_result_id"]):
                    broken.append(f"missing-replay-result:{row['replay_result_id']}")
                child = row.get("child_failure_snapshot_id")
                if child is not None and self.failure_snapshot_exists is not None and not self.failure_snapshot_exists(child):
                    broken.append(f"missing-child-failure:{child}")
        return TomographyStoreValidation(
            ok=not duplicates and not broken and not unsafe,
            record_count=len(payloads),
            duplicate_ids=duplicates,
            broken_references=tuple(broken),
            unsafe_fields=tuple(unsafe),
        )
