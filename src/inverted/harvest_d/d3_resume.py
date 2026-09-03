from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping


class ProvenanceMismatch(RuntimeError):
    pass


class ResumeIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class D3ResumeState:
    completed_call_ids: tuple[str, ...]
    incomplete_call_ids: tuple[str, ...]
    replayable_action_ids: tuple[str, ...]
    next_action_id: str | None
    requires_reconciliation: bool


class D3Journal:
    """Minimal append-only campaign journal with durable provenance identity."""

    def __init__(self, root: str | Path, *, provenance: Mapping[str, Any]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "d3_campaign_journal.jsonl"
        self.path.touch(exist_ok=True)
        self.provenance_path = self.root / "d3_provenance.json"
        self.provenance = dict(provenance)
        if self.provenance_path.exists():
            existing = json.loads(self.provenance_path.read_text(encoding="utf-8"))
            if existing != self.provenance:
                raise ProvenanceMismatch("journal provenance differs from existing campaign provenance")
        else:
            temp = self.root / ".d3_provenance.tmp"
            temp.write_text(json.dumps(self.provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            os.replace(temp, self.provenance_path)

    def _append(self, event: Mapping[str, Any]) -> None:
        payload = json.dumps(dict(event), sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def schedule(self, action_id: str) -> None:
        self._append({"event": "SCHEDULED", "action_id": str(action_id)})

    def record_call_received(self, action_id: str, call_id: str) -> None:
        self._append(
            {
                "event": "CALL_RECEIVED",
                "action_id": str(action_id),
                "physical_model_call_id": str(call_id),
            }
        )

    def commit_call(self, action_id: str, call_id: str) -> None:
        self._append(
            {
                "event": "CALL_COMMITTED",
                "action_id": str(action_id),
                "physical_model_call_id": str(call_id),
            }
        )


def _read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ResumeIntegrityError(f"invalid journal JSON at line {line_number}") from exc
        if not isinstance(row, dict) or not row.get("event"):
            raise ResumeIntegrityError(f"invalid journal record at line {line_number}")
        events.append(row)
    return events


def resume_campaign(
    root: str | Path,
    *,
    current_provenance: Mapping[str, Any],
) -> D3ResumeState:
    root_path = Path(root)
    provenance_path = root_path / "d3_provenance.json"
    journal_path = root_path / "d3_campaign_journal.jsonl"
    if not provenance_path.exists() or not journal_path.exists():
        raise ResumeIntegrityError("D3 resume requires provenance and campaign journal")

    expected = json.loads(provenance_path.read_text(encoding="utf-8"))
    if expected != dict(current_provenance):
        raise ProvenanceMismatch("current provenance does not match the campaign segment")

    events = _read_events(journal_path)
    scheduled_order: list[str] = []
    received_by_action: dict[str, str] = {}
    committed_by_action: dict[str, str] = {}
    committed_call_ids: set[str] = set()

    for row in events:
        event = str(row["event"])
        action = str(row.get("action_id", ""))
        if event == "SCHEDULED":
            if not action or action in scheduled_order:
                raise ResumeIntegrityError(f"duplicate or empty scheduled action: {action!r}")
            scheduled_order.append(action)
        elif event == "CALL_RECEIVED":
            call_id = str(row.get("physical_model_call_id", ""))
            if action not in scheduled_order or not call_id:
                raise ResumeIntegrityError("received call lacks a prior scheduled action or call identity")
            if action in received_by_action:
                raise ResumeIntegrityError("multiple physical calls recorded for one scheduled action")
            received_by_action[action] = call_id
        elif event == "CALL_COMMITTED":
            call_id = str(row.get("physical_model_call_id", ""))
            if received_by_action.get(action) != call_id:
                raise ResumeIntegrityError("committed call does not match received call")
            if call_id in committed_call_ids:
                raise ResumeIntegrityError("duplicate committed physical call identity")
            committed_call_ids.add(call_id)
            committed_by_action[action] = call_id

    incomplete_call_ids = tuple(
        received_by_action[action]
        for action in scheduled_order
        if action in received_by_action and action not in committed_by_action
    )
    replayable = tuple(
        action
        for action in scheduled_order
        if action not in received_by_action and action not in committed_by_action
    )

    # The next action may be a never-started scheduled action. An action whose
    # physical response was received but not durably committed is deliberately
    # not replayable; it requires explicit reconciliation/new evidence policy.
    next_action = replayable[0] if replayable else None
    return D3ResumeState(
        completed_call_ids=tuple(committed_by_action[action] for action in scheduled_order if action in committed_by_action),
        incomplete_call_ids=incomplete_call_ids,
        replayable_action_ids=replayable,
        next_action_id=next_action,
        requires_reconciliation=bool(incomplete_call_ids),
    )
