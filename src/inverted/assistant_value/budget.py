from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class CallBudgetExceeded(RuntimeError):
    """Raised before a model invocation would exceed the physical-call cap."""


@dataclass
class PhysicalCallBudget:
    name: str
    cap: int
    reservations: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cap = int(self.cap)
        if self.cap < 0:
            raise ValueError("physical call cap must be non-negative")

    @property
    def used(self) -> int:
        return len(self.reservations)

    @property
    def remaining(self) -> int:
        return max(0, self.cap - self.used)

    def reserve(self, *, call_id: str, trial_id: str, role: str) -> int:
        if self.used >= self.cap:
            raise CallBudgetExceeded(
                f"{self.name} physical model-call cap {self.cap} exhausted; "
                f"refusing call {call_id}"
            )
        sequence = self.used + 1
        self.reservations.append(
            {
                "sequence": sequence,
                "call_id": str(call_id),
                "trial_id": str(trial_id),
                "role": str(role),
                "reserved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return sequence

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cap": self.cap,
            "used": self.used,
            "remaining": self.remaining,
            "reservations": list(self.reservations),
        }
