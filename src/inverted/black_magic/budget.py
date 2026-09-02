from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ExternalActionBudgetExceeded(RuntimeError):
    pass


@dataclass
class ExternalActionBudget:
    name: str
    cap: int
    _used: int = 0
    reservations: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cap = int(self.cap)
        if self.cap < 0:
            raise ValueError("external-action cap must be non-negative")

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return self.cap - self._used

    def reserve(self, kind: str, metadata: dict[str, Any] | None = None) -> int:
        if self._used >= self.cap:
            raise ExternalActionBudgetExceeded(
                f"{self.name} external-action cap {self.cap} exceeded; refusing action {self._used + 1}"
            )
        self._used += 1
        self.reservations.append(
            {"sequence": self._used, "kind": str(kind), "metadata": dict(metadata or {})}
        )
        return self._used

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cap": self.cap,
            "used": self.used,
            "remaining": self.remaining,
            "reservations": list(self.reservations),
        }
