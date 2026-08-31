from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


class PhysicalCallLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class CallIdentity:
    digest: str

    @classmethod
    def build(
        cls,
        model: str,
        role: str,
        messages: list[dict[str, str]],
        settings: dict[str, Any],
        response_schema: Any = None,
    ) -> "CallIdentity":
        payload = {
            "model": model,
            "role": role,
            "messages": messages,
            "settings": settings,
            "response_schema": response_schema,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return cls(hashlib.sha256(raw.encode("utf-8")).hexdigest())


@dataclass
class PhysicalCallBudget:
    max_calls: int = 480
    physical_calls: int = 0
    cache_hits: int = 0

    def __post_init__(self) -> None:
        if self.max_calls < 0:
            raise ValueError("max_calls must be non-negative")

    @property
    def remaining(self) -> int:
        return self.max_calls - self.physical_calls

    def consume(self, label: str | None = None) -> None:
        if self.physical_calls >= self.max_calls:
            detail = f" ({label})" if label else ""
            raise PhysicalCallLimitExceeded(
                f"physical model call hard limit {self.max_calls} exceeded{detail}"
            )
        self.physical_calls += 1

    def note_cache_hit(self, label: str | None = None) -> None:
        self.cache_hits += 1


OUTCOME_TRANSITIONS = (
    "FAIL_TO_SUCCESS",
    "SUCCESS_TO_FAIL",
    "FAIL_TO_BLOCKED",
    "FAIL_TO_DIFFERENT_FAIL",
    "CATASTROPHIC_TO_SAFE",
    "SAFE_TO_CATASTROPHIC",
    "SUCCESS_TO_SUCCESS",
    "FAIL_TO_FAIL",
)
