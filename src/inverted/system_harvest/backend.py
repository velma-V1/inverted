from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .execution import AttemptOutcome


@dataclass(frozen=True)
class BackendObservation:
    kind: str
    artifact_id: str
    raw_text: str | None
    source_path: str
    ordinal: int
    format: str
    raw_bytes: bytes | None = None

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("backend observation ordinal must be non-negative")
        if not self.kind or not self.artifact_id or not self.source_path or not self.format:
            raise ValueError("backend observation identity fields must be non-empty")
        if self.raw_text is None and self.raw_bytes is None:
            raise ValueError("backend observation requires raw_text or raw_bytes")


@dataclass(frozen=True)
class BackendResult:
    outcome: AttemptOutcome
    session_handle: str | None
    verifier_payload: dict[str, Any]


@dataclass(frozen=True)
class FakeExecutionScript:
    observations: tuple[BackendObservation, ...]
    result: BackendResult

    def __post_init__(self) -> None:
        ordinals = [item.ordinal for item in self.observations]
        if ordinals != sorted(ordinals) or len(ordinals) != len(set(ordinals)):
            raise ValueError("fake backend observations must have unique ascending ordinals")


class ExecutionBackend(Protocol):
    def execute(self, cell_id: str, execution_id: str, escalation_level: int): ...
    def resume(self, cell_id: str, execution_id: str, escalation_level: int, session_handle: str): ...
    def continue_from_escalation(self, cell_id: str, execution_id: str, escalation_level: int,
                                 capsule_id: str, selected_model_id: str): ...


class FakeExecutionBackend:
    def __init__(self, scripts):
        self._scripts = dict(scripts)
        self._indices: dict[tuple[str, int], int] = {}
        self._calls: list[tuple[str, str, str, int, str | None]] = []

    @property
    def calls(self):
        return tuple(self._calls)

    def _next_script(self, key: tuple[str, int]) -> FakeExecutionScript:
        if key not in self._scripts:
            raise KeyError(f"no fake execution script for {key[0]} level {key[1]}")
        value = self._scripts[key]
        if isinstance(value, FakeExecutionScript):
            return value
        sequence = tuple(value)
        index = self._indices.get(key, 0)
        if index >= len(sequence):
            raise RuntimeError(f"fake execution script sequence exhausted for {key[0]} level {key[1]}")
        self._indices[key] = index + 1
        return sequence[index]

    def _run(self, mode: str, cell_id: str, execution_id: str,
             escalation_level: int, session_handle: str | None):
        key = (cell_id, escalation_level)
        self._calls.append((mode, cell_id, execution_id, escalation_level, session_handle))
        script = self._next_script(key)
        return script.observations, script.result

    def execute(self, cell_id: str, execution_id: str, escalation_level: int):
        return self._run("START", cell_id, execution_id, escalation_level, None)

    def resume(self, cell_id: str, execution_id: str, escalation_level: int,
               session_handle: str):
        return self._run("RESUME", cell_id, execution_id, escalation_level, session_handle)

    def continue_from_escalation(self, cell_id: str, execution_id: str, escalation_level: int,
                                 capsule_id: str, selected_model_id: str):
        return self._run("ESCALATE", cell_id, execution_id, escalation_level,
                         f"{capsule_id}|{selected_model_id}")
