"""Append-only, tamper-evident metadata store for Stage-7 tomography."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .core import Partition
from .tomography_core import (
    TomographyAssessment,
    TomographyAxis,
    TomographyDisposition,
    TomographyOutcome,
    TomographyProbeSpec,
    TomographyStatus,
    TomographyStopReason,
    TomographyStudy,
)


_STUDIES_FILENAME = "tomography-studies.jsonl"
_OUTCOMES_FILENAME = "tomography-outcomes.jsonl"
_ASSESSMENTS_FILENAME = "tomography-assessments.jsonl"
_MANIFEST_FILENAME = "SHA256SUMS.csv"
_LEDGER_FILENAMES = (_STUDIES_FILENAME, _OUTCOMES_FILENAME, _ASSESSMENTS_FILENAME)
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
    manifest_errors: tuple[str, ...] = ()


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
        return TomographyProbeSpec(
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
    if kind in {"TOMOGRAPHY_PROFILE", "TOMOGRAPHY_ASSESSMENT"}:
        return TomographyAssessment(
            profile_id=record.get("profile_id", record.get("assessment_id")), study_id=record["study_id"],
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TomographyEvidenceStore:
    """Persist Stage-7 scientific metadata while canonical replay remains authoritative."""

    def __init__(
        self,
        root: str | Path,
        *,
        replay_result_exists: Callable[[str], bool] | None = None,
        failure_snapshot_exists: Callable[[str], bool] | None = None,
        failure_snapshot_state_matches: Callable[[str, str, Partition], bool] | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.studies_path = self.root / _STUDIES_FILENAME
        self.outcomes_path = self.root / _OUTCOMES_FILENAME
        self.assessments_path = self.root / _ASSESSMENTS_FILENAME
        self.manifest_path = self.root / _MANIFEST_FILENAME
        # Compatibility: legacy callers treated .path as the single metadata ledger.
        self.path = self.studies_path
        self.replay_result_exists = replay_result_exists
        self.failure_snapshot_exists = failure_snapshot_exists
        self.failure_snapshot_state_matches = failure_snapshot_state_matches

    @staticmethod
    def _logical_id(value: Any) -> str:
        if isinstance(value, TomographyStudy):
            return value.study_id
        if isinstance(value, TomographyProbeSpec):
            return value.probe_id
        if isinstance(value, TomographyOutcome):
            return value.outcome_id
        if isinstance(value, TomographyAssessment):
            return value.profile_id
        raise TypeError("unsupported tomography record")

    def _ledger_for(self, value: Any) -> Path:
        if isinstance(value, (TomographyStudy, TomographyProbeSpec)):
            return self.studies_path
        if isinstance(value, TomographyOutcome):
            return self.outcomes_path
        if isinstance(value, TomographyAssessment):
            return self.assessments_path
        raise TypeError("unsupported tomography record")

    def _read_path(self, path: Path) -> tuple[Any, ...]:
        if not path.exists():
            return ()
        records: list[Any] = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise TypeError("row must be an object")
                records.append(_parse(payload))
            except Exception as exc:
                raise ValueError(f"invalid tomography row {path.name}:{line_no}: {exc}") from exc
        return tuple(records)

    def _records(self) -> tuple[Any, ...]:
        records: list[Any] = []
        for path in (self.studies_path, self.outcomes_path, self.assessments_path):
            records.extend(self._read_path(path))
        return tuple(records)

    def _manifest_entries(self) -> dict[str, str]:
        if not self.manifest_path.exists():
            return {}
        entries: dict[str, str] = {}
        for line_no, line in enumerate(self.manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            parts = line.split(",")
            if len(parts) != 2:
                raise ValueError(f"invalid manifest row {line_no}")
            name, digest = parts
            if name in entries:
                raise ValueError(f"duplicate manifest filename: {name}")
            if name not in _LEDGER_FILENAMES:
                raise ValueError(f"unexpected manifest filename: {name}")
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError(f"invalid manifest digest for {name}")
            entries[name] = digest
        return entries

    def _manifest_errors(self) -> tuple[str, ...]:
        existing = {name for name in _LEDGER_FILENAMES if (self.root / name).exists()}
        if not existing and not self.manifest_path.exists():
            return ()
        if existing and not self.manifest_path.exists():
            return ("missing-manifest",)
        try:
            entries = self._manifest_entries()
        except Exception as exc:
            return (f"invalid-manifest:{exc}",)
        errors: list[str] = []
        if set(entries) != existing:
            for name in sorted(existing - set(entries)):
                errors.append(f"manifest-missing:{name}")
            for name in sorted(set(entries) - existing):
                errors.append(f"manifest-orphan:{name}")
        for name in sorted(existing & set(entries)):
            actual = _sha256(self.root / name)
            if entries[name] != actual:
                errors.append(f"manifest-hash-mismatch:{name}")
        return tuple(errors)

    def _write_manifest(self) -> None:
        rows = []
        for name in _LEDGER_FILENAMES:
            path = self.root / name
            if path.exists():
                rows.append(f"{name},{_sha256(path)}")
        self.manifest_path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8", newline="\n")

    def _assert_manifest_clean_before_append(self) -> None:
        errors = self._manifest_errors()
        if errors:
            raise ValueError(f"tomography manifest integrity failure: {errors}")

    def _append(self, value: Any) -> None:
        payload = value.to_record()
        unsafe = _unsafe(payload)
        if unsafe:
            raise ValueError(f"tomography metadata contains forbidden private payload fields: {unsafe}")
        if isinstance(value, TomographyStudy) and value.partition in {Partition.FRESH, Partition.SEALED}:
            raise ValueError("protected partition contamination is forbidden in Stage-7 metadata")
        self._assert_manifest_clean_before_append()
        logical = self._logical_id(value)
        if logical in {self._logical_id(item) for item in self._records()}:
            raise ValueError(f"duplicate tomography logical id: {logical}")
        path = self._ledger_for(value)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n")
        self._write_manifest()

    def append_study(self, value: TomographyStudy) -> None:
        if not isinstance(value, TomographyStudy):
            raise TypeError("value must be TomographyStudy")
        self._append(value)

    def append_probe(self, value: TomographyProbeSpec) -> None:
        if not isinstance(value, TomographyProbeSpec):
            raise TypeError("value must be TomographyProbeSpec")
        self._append(value)

    def append_outcome(self, value: TomographyOutcome) -> None:
        if not isinstance(value, TomographyOutcome):
            raise TypeError("value must be TomographyOutcome")
        self._append(value)

    def append_assessment(self, value: TomographyAssessment) -> None:
        if not isinstance(value, TomographyAssessment):
            raise TypeError("value must be TomographyAssessment")
        self._append(value)

    # Source compatibility only; new code should use assessment terminology.
    def append_profile(self, value: TomographyAssessment) -> None:
        self.append_assessment(value)

    def studies(self) -> tuple[TomographyStudy, ...]:
        return tuple(item for item in self._read_path(self.studies_path) if isinstance(item, TomographyStudy))

    def probes(self) -> tuple[TomographyProbeSpec, ...]:
        return tuple(item for item in self._read_path(self.studies_path) if isinstance(item, TomographyProbeSpec))

    def outcomes(self) -> tuple[TomographyOutcome, ...]:
        return tuple(item for item in self._read_path(self.outcomes_path) if isinstance(item, TomographyOutcome))

    def assessments(self) -> tuple[TomographyAssessment, ...]:
        return tuple(item for item in self._read_path(self.assessments_path) if isinstance(item, TomographyAssessment))

    def profiles(self) -> tuple[TomographyAssessment, ...]:
        return self.assessments()

    def validate(self) -> TomographyStoreValidation:
        manifest_errors = self._manifest_errors()
        payloads: list[dict[str, Any]] = []
        parsed: list[Any] = []
        unsafe: list[str] = []
        parse_errors: list[str] = []
        for path in (self.studies_path, self.outcomes_path, self.assessments_path):
            if not path.exists():
                continue
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise TypeError("row must be object")
                    value = _parse(payload)
                    payloads.append(payload)
                    parsed.append(value)
                    unsafe.extend(f"{path.name}:{line_no}:{hit}" for hit in _unsafe(payload))
                except Exception as exc:
                    parse_errors.append(f"{path.name}:{line_no}:{exc}")

        ids = [self._logical_id(item) for item in parsed]
        duplicates = tuple(sorted({item for item in ids if ids.count(item) > 1}))
        studies = {item.study_id: item for item in parsed if isinstance(item, TomographyStudy)}
        probes = {item.probe_id: item for item in parsed if isinstance(item, TomographyProbeSpec)}
        broken = list(parse_errors)

        for study in studies.values():
            if study.partition in {Partition.FRESH, Partition.SEALED}:
                broken.append(f"protected-partition:{study.study_id}:{study.partition.value}")
            if self.failure_snapshot_exists is not None and not self.failure_snapshot_exists(study.failure_snapshot_id):
                broken.append(f"missing-root-failure:{study.failure_snapshot_id}")
            if (
                self.failure_snapshot_state_matches is not None
                and not self.failure_snapshot_state_matches(
                    study.failure_snapshot_id, study.parent_state_hash, study.partition
                )
            ):
                broken.append(f"failure-state-mismatch:{study.failure_snapshot_id}")
            if self.replay_result_exists is not None:
                for ref in study.baseline_evidence_refs:
                    if not self.replay_result_exists(ref):
                        broken.append(f"missing-replay-result:{ref}")

        for item in parsed:
            if isinstance(item, TomographyProbeSpec):
                parent = studies.get(item.study_id)
                if parent is None:
                    broken.append(f"missing-study:{item.study_id}")
                elif item.probe_id not in parent.probe_ids:
                    broken.append(f"unregistered-probe:{item.probe_id}")
            elif isinstance(item, TomographyOutcome):
                parent = studies.get(item.study_id)
                probe = probes.get(item.probe_id)
                if parent is None:
                    broken.append(f"missing-study:{item.study_id}")
                if probe is None:
                    broken.append(f"missing-probe:{item.probe_id}")
                elif probe.study_id != item.study_id:
                    broken.append(f"probe-study-mismatch:{item.probe_id}")
                if self.replay_result_exists is not None:
                    for ref in (item.replay_result_id, *item.comparison_refs):
                        if not self.replay_result_exists(ref):
                            broken.append(f"missing-replay-result:{ref}")
                child = item.child_failure_snapshot_id
                if child is not None and self.failure_snapshot_exists is not None and not self.failure_snapshot_exists(child):
                    broken.append(f"missing-child-failure:{child}")
            elif isinstance(item, TomographyAssessment):
                if item.study_id not in studies:
                    broken.append(f"missing-study:{item.study_id}")
                if self.replay_result_exists is not None:
                    for ref in item.evidence_refs:
                        if not self.replay_result_exists(ref):
                            broken.append(f"missing-replay-result:{ref}")

        return TomographyStoreValidation(
            ok=not duplicates and not broken and not unsafe and not manifest_errors,
            record_count=len(payloads),
            duplicate_ids=duplicates,
            broken_references=tuple(dict.fromkeys(broken)),
            unsafe_fields=tuple(dict.fromkeys(unsafe)),
            manifest_errors=manifest_errors,
        )
