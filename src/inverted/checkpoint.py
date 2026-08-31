from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .arms import TrialRecord
from .telemetry import ModelCallRecord


_TUPLE_FIELDS = {"failed_requirement_ids", "failure_reasons", "injected_faults"}


def _trial_from_dict(raw: dict[str, Any]) -> TrialRecord:
    row = dict(raw)
    calls = [ModelCallRecord(**dict(call)) for call in row.pop("model_calls", [])]
    events = list(row.pop("candidate_events", []))
    for field in _TUPLE_FIELDS:
        if field in row:
            row[field] = tuple(row[field] or ())
    return TrialRecord(**row, model_calls=calls, candidate_events=events)


class CheckpointStore:
    """Append-only, fsync-backed JSONL storage for completed trial records."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load_trials(self) -> list[TrialRecord]:
        if not self.path.exists():
            return []
        trials: list[TrialRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    raw = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid checkpoint JSON at line {line_no}: {exc}") from exc
                if not isinstance(raw, dict) or raw.get("record_type") != "trial":
                    raise ValueError(f"invalid checkpoint record at line {line_no}")
                trials.append(_trial_from_dict(dict(raw["trial"])))
        return trials

    def append_trial(self, trial: TrialRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"record_type": "trial", "trial": trial.to_dict(include_calls=True)}
        encoded = json.dumps(record, sort_keys=True, default=str) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
