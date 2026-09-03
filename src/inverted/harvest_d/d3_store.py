from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .d3_types import CallCaptureStatus, D3Event


class D3IntegrityError(RuntimeError):
    pass


_RECORD_FILES = (
    "d3_system_events.jsonl",
    "d3_call_ledger.jsonl",
    "d3_raw_model_requests.jsonl",
    "d3_raw_model_responses.jsonl",
    "d3_normalized_model_calls.jsonl",
    "d3_information_packets.jsonl",
    "d3_information_field_lineage.jsonl",
    "d3_state_snapshots.jsonl",
    "d3_evidence_snapshots.jsonl",
    "d3_authority_snapshots.jsonl",
    "d3_assistance_events.jsonl",
    "d3_scheduler_events.jsonl",
    "d3_randomization_assignments.jsonl",
    "d3_sequential_analysis_state.jsonl",
    "d3_operator_events.jsonl",
    "d3_component_manifest.jsonl",
    "d3_recovery_trajectories.jsonl",
    "d3_edge_cases.jsonl",
    "d3_errors.jsonl",
    "d3_counterfactuals.jsonl",
    "d3_scores_raw.jsonl",
    "d3_scores_normalized.jsonl",
    "d3_runtime_telemetry.jsonl",
    "d3_case_lineage.jsonl",
    "d3_capture_field_matrix.jsonl",
    "d3_intervention_opportunities.jsonl",
    "d3_decision_opportunity_sets.jsonl",
    "d3_case_structural_features.jsonl",
    "d3_model_behavior_features.jsonl",
    "d3_decision_boundary_telemetry.jsonl",
    "d3_causal_claim_graph.jsonl",
    "d3_claim_evidence_edges.jsonl",
    "d3_uncovered_space.jsonl",
    "d3_evidence_saturation.jsonl",
    "d3_protocol_violations.jsonl",
    "d3_assumption_ledger.jsonl",
    "d3_campaign_journal.jsonl",
)

_REQUIRED_CALL_CAPTURE = (
    "raw_request",
    "raw_response",
    "normalized_call",
    "information_packet",
    "score_raw",
    "score_normalized",
    "runtime_telemetry",
    "scheduler_event",
)

_BUNDLE_DESTINATIONS = {
    "raw_request": "d3_raw_model_requests.jsonl",
    "raw_response": "d3_raw_model_responses.jsonl",
    "normalized_call": "d3_normalized_model_calls.jsonl",
    "information_packet": "d3_information_packets.jsonl",
    "score_raw": "d3_scores_raw.jsonl",
    "score_normalized": "d3_scores_normalized.jsonl",
    "runtime_telemetry": "d3_runtime_telemetry.jsonl",
    "scheduler_event": "d3_scheduler_events.jsonl",
}


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _canonical_line(value: object) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def _digest(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "file": path.name,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


class D3EvidenceStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for name in _RECORD_FILES:
            (self.root / name).touch(exist_ok=True)
        self._event_ids: set[str] = set()
        self._call_ids: set[str] = set()
        self._capture_status: dict[str, CallCaptureStatus] = {}
        self._last_event_sequence = 0
        self._load_existing_identity_state()

    def _load_existing_identity_state(self) -> None:
        event_path = self.root / "d3_system_events.jsonl"
        for line in event_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise D3IntegrityError("existing D3 event log is not valid JSONL") from exc
            event_id = str(row.get("event_id", ""))
            if not event_id or event_id in self._event_ids:
                raise D3IntegrityError("existing D3 event identity is missing or duplicated")
            self._event_ids.add(event_id)
            self._last_event_sequence = max(self._last_event_sequence, int(row.get("sequence", 0) or 0))

        ledger_path = self.root / "d3_call_ledger.jsonl"
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise D3IntegrityError("existing D3 call ledger is not valid JSONL") from exc
            call_id = str(row.get("physical_model_call_id", ""))
            if not call_id or call_id in self._call_ids:
                raise D3IntegrityError("existing physical model call identity is missing or duplicated")
            self._call_ids.add(call_id)
            missing = tuple(str(x) for x in row.get("missing_required", []))
            self._capture_status[call_id] = CallCaptureStatus(
                call_id,
                required_present=not missing,
                missing_required=missing,
            )

    def _append(self, name: str, value: object) -> None:
        path = self.root / name
        payload = _canonical_line(value)
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def append_event(self, event: D3Event) -> None:
        if not event.event_id or event.event_id in self._event_ids:
            raise D3IntegrityError(f"duplicate or empty event identity: {event.event_id!r}")
        if event.sequence <= self._last_event_sequence:
            raise D3IntegrityError(
                f"event sequence must be monotonic: {event.sequence}<={self._last_event_sequence}"
            )
        self._append("d3_system_events.jsonl", event)
        self._event_ids.add(event.event_id)
        self._last_event_sequence = event.sequence

    def append_call_bundle(self, bundle: Mapping[str, object]) -> CallCaptureStatus:
        call_id = str(bundle.get("physical_model_call_id", ""))
        if not call_id or call_id in self._call_ids:
            raise D3IntegrityError(f"duplicate or empty physical model call identity: {call_id!r}")

        missing = tuple(key for key in _REQUIRED_CALL_CAPTURE if key not in bundle)
        status = CallCaptureStatus(
            call_id,
            required_present=not missing,
            missing_required=missing,
        )

        for key, destination in _BUNDLE_DESTINATIONS.items():
            if key in bundle:
                value = bundle[key]
                if isinstance(value, Mapping):
                    row = dict(value)
                    row.setdefault("physical_model_call_id", call_id)
                    self._append(destination, row)
                else:
                    self._append(destination, {
                        "physical_model_call_id": call_id,
                        "value": value,
                    })

        for field_name in _REQUIRED_CALL_CAPTURE:
            self._append(
                "d3_capture_field_matrix.jsonl",
                {
                    "physical_model_call_id": call_id,
                    "field": field_name,
                    "present": field_name in bundle,
                    "required": True,
                },
            )

        self._append(
            "d3_call_ledger.jsonl",
            {
                "physical_model_call_id": call_id,
                "admissibility": status.admissibility.value,
                "missing_required": list(missing),
                "capture_complete": not missing,
            },
        )
        self._call_ids.add(call_id)
        self._capture_status[call_id] = status
        return status

    def capture_status(self, physical_model_call_id: str) -> CallCaptureStatus:
        try:
            return self._capture_status[physical_model_call_id]
        except KeyError as exc:
            raise D3IntegrityError(f"unknown physical model call: {physical_model_call_id}") from exc

    def commit_checkpoint(self) -> Path:
        manifest = [
            _digest(path)
            for path in sorted(self.root.iterdir())
            if path.is_file()
            and path.name not in {"d3_integrity_checkpoint.json", "SHA256SUMS.csv"}
        ]
        target = self.root / "d3_integrity_checkpoint.json"
        temporary = self.root / ".d3_integrity_checkpoint.tmp"
        temporary.write_text(
            json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
        return target

    def verify_integrity(self) -> bool:
        checkpoint = self.root / "d3_integrity_checkpoint.json"
        if not checkpoint.exists():
            raise D3IntegrityError("D3 integrity checkpoint does not exist")
        try:
            expected_rows = json.loads(checkpoint.read_text(encoding="utf-8"))["files"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise D3IntegrityError("D3 integrity checkpoint is corrupt") from exc
        for expected in expected_rows:
            path = self.root / str(expected["file"])
            if not path.exists():
                raise D3IntegrityError(f"D3 evidence artifact missing: {path.name}")
            actual = _digest(path)
            if actual["bytes"] != expected["bytes"] or actual["sha256"] != expected["sha256"]:
                raise D3IntegrityError(f"D3 evidence artifact changed after checkpoint: {path.name}")
        return True

    def finalize_manifest(self) -> Path:
        rows = [
            _digest(path)
            for path in sorted(self.root.iterdir())
            if path.is_file() and path.name != "SHA256SUMS.csv"
        ]
        output = self.root / "SHA256SUMS.csv"
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=("file", "bytes", "sha256"))
            writer.writeheader()
            writer.writerows(rows)
        return output
