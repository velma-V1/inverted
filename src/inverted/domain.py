from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import copy


@dataclass(frozen=True)
class WorldState:
    data: dict[str, Any]

    def clone(self) -> "WorldState":
        return WorldState(copy.deepcopy(self.data))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)

    def get(self, path: str) -> Any:
        """Read a dotted state path without mutating the world state."""
        current: Any = self.data
        for part in (p for p in path.split(".") if p):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current


@dataclass(frozen=True)
class Requirement:
    id: str
    kind: str
    path: str
    expected: Any
    critical: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    op: str
    path: str
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskCase:
    id: str
    family: str
    complexity: int
    goal: str
    initial_state: WorldState
    target_state: WorldState
    requirements: tuple[Requirement, ...]
    allowed_ops: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OracleResult:
    success: bool
    passed_requirement_ids: tuple[str, ...]
    failed_requirement_ids: tuple[str, ...]
    catastrophic: bool
    requirement_results: dict[str, bool]


@dataclass(frozen=True)
class Candidate:
    id: str
    state: WorldState
    actions: tuple[Action, ...]
    injected_faults: tuple[str, ...] = ()
    configured_quality: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
