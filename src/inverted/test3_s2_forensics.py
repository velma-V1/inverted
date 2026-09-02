from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if hasattr(value, "value"):
        return _plain(value.value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(
        _plain(value),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


def _record_digest(record_without_digest: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(record_without_digest).encode("utf-8")).hexdigest()


class S2ForensicJournal:
    """Append-only, hash-chained durable event journal for S2.

    The file is flushed and fsynced after every record so the journal remains
    the recoverable source of truth when the in-memory experiment aborts.
    """

    def __init__(self, run_dir: str | Path, run_id: str, *, filename: str = "forensic_journal.jsonl"):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = str(run_id)
        self.path = self.run_dir / filename
        records = self.read_records()
        integrity = self._verify(records)
        if records and not integrity["valid"]:
            raise RuntimeError("existing S2 forensic journal failed integrity verification")
        self._sequence = int(records[-1]["sequence"]) if records else 0
        self._previous_sha256 = str(records[-1]["record_sha256"]) if records else None

    def append(
        self,
        event_type: str,
        payload: Any,
        *,
        trial_id: str | None = None,
        call_id: str | None = None,
        arm_id: str | None = None,
        task_id: str | None = None,
        step_index: int | None = None,
    ) -> dict[str, Any]:
        base = {
            "sequence": self._sequence + 1,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": str(event_type),
            "trial_id": trial_id,
            "call_id": call_id,
            "arm_id": arm_id,
            "task_id": task_id,
            "step_index": step_index,
            "previous_sha256": self._previous_sha256,
            "payload": _plain(payload),
        }
        record = {**base, "record_sha256": _record_digest(base)}
        encoded = _canonical(record) + "\n"
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        self._sequence = int(record["sequence"])
        self._previous_sha256 = str(record["record_sha256"])
        return record

    def read_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                rows.append({"__invalid_json__": line})
                break
            rows.append(value if isinstance(value, dict) else {"__invalid_record__": value})
        return rows

    def _verify(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        previous: str | None = None
        for expected_sequence, record in enumerate(records, start=1):
            if "__invalid_json__" in record or "__invalid_record__" in record:
                return {
                    "valid": False,
                    "record_count": len(records),
                    "valid_prefix_count": expected_sequence - 1,
                    "first_invalid_sequence": expected_sequence,
                    "last_record_sha256": previous,
                }
            try:
                sequence = int(record.get("sequence"))
            except (TypeError, ValueError):
                sequence = -1
            stored = str(record.get("record_sha256") or "")
            base = dict(record)
            base.pop("record_sha256", None)
            computed = _record_digest(base)
            if sequence != expected_sequence or record.get("previous_sha256") != previous or stored != computed:
                return {
                    "valid": False,
                    "record_count": len(records),
                    "valid_prefix_count": expected_sequence - 1,
                    "first_invalid_sequence": expected_sequence,
                    "last_record_sha256": previous,
                }
            previous = stored
        return {
            "valid": True,
            "record_count": len(records),
            "valid_prefix_count": len(records),
            "first_invalid_sequence": None,
            "last_record_sha256": previous,
        }

    def snapshot_integrity(self) -> dict[str, Any]:
        result = self._verify(self.read_records())
        result.update({
            "path": self.path.name,
            "bytes": self.path.stat().st_size if self.path.exists() else 0,
            "ends_with_newline": self.path.read_bytes().endswith(b"\n") if self.path.exists() else True,
        })
        if result["record_count"] and not result["ends_with_newline"]:
            result["valid"] = False
            if result.get("first_invalid_sequence") is None:
                result["first_invalid_sequence"] = result["record_count"]
                result["valid_prefix_count"] = max(0, result["record_count"] - 1)
        return result
