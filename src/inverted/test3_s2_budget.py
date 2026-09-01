from __future__ import annotations

from collections import Counter


ABSOLUTE_PER_TEST_ACTION_CEILING = 1000


class CombinedActionBudget:
    """One fail-closed counter shared by every externally executed S2 action."""

    def __init__(self, limit: int):
        value = int(limit)
        if value < 0:
            raise ValueError("combined action budget must be non-negative")
        if value > ABSOLUTE_PER_TEST_ACTION_CEILING:
            raise ValueError("combined action budget may not exceed absolute 1000-action ceiling")
        self.limit = value
        self._used = 0
        self._by_kind: Counter[str] = Counter()

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return self.limit - self._used

    def reserve(self, kind: str, count: int = 1) -> None:
        amount = int(count)
        if amount < 0:
            raise ValueError("combined action budget reservation must be non-negative")
        if self._used + amount > self.limit:
            raise RuntimeError("combined action budget exhausted; refusing external action")
        key = str(kind or "unknown")
        self._used += amount
        self._by_kind[key] += amount

    def snapshot(self) -> dict[str, object]:
        return {
            "limit": self.limit,
            "combined_used": self._used,
            "remaining": self.remaining,
            "by_kind": dict(sorted(self._by_kind.items())),
        }
