"""Frozen action-accounting and local runtime planning primitives."""

from __future__ import annotations

from dataclasses import dataclass
import weakref


MODEL_ACTION_KINDS = frozenset({
    "model_call",
    "model_request",
    "model_action",
    "llm_call",
    "ai_call",
})
NON_MODEL_ACTION_KINDS = frozenset({
    "non_model_action",
    "provenance_api_call",
    "external_api_call",
    "filesystem_action",
    "telemetry_action",
})
_CANONICAL_ACTION_CLASSES = frozenset({"model", "non_model"})


class _BudgetRecord:
    __slots__ = ("owner_ref", "total_cap", "non_model_reserve", "action_ledger")

    def __init__(self, owner_ref: weakref.ReferenceType["CombinedActionBudget"], total_cap: int, non_model_reserve: int) -> None:
        self.owner_ref = owner_ref
        self.total_cap = total_cap
        self.non_model_reserve = non_model_reserve
        self.action_ledger: tuple[str, ...] = ()


_BUDGET_REGISTRY: dict[int, _BudgetRecord] = {}


def _discard_budget(reference: weakref.ReferenceType["CombinedActionBudget"], budget_id: int) -> None:
    record = _BUDGET_REGISTRY.get(budget_id)
    if record is not None and record.owner_ref is reference:
        del _BUDGET_REGISTRY[budget_id]


class CombinedActionBudget:
    """Account every external/model action against one campaign ceiling.

    The non-model reserve is a hard floor: model calls can use only the portion
    of the ceiling above that reserve, even when the reserve is not yet spent.
    """

    __slots__ = ("__weakref__",)

    def __init__(self, total_cap: int = 1000, non_model_reserve: int = 40) -> None:
        if isinstance(total_cap, bool) or not isinstance(total_cap, int) or not 1 <= total_cap <= 1000:
            raise ValueError("total action ceiling must be between 1 and 1000")
        if isinstance(non_model_reserve, bool) or not isinstance(non_model_reserve, int):
            raise ValueError("non-model reserve must be an integer")
        if not 0 <= non_model_reserve <= total_cap:
            raise ValueError("non-model reserve must be between 0 and total action ceiling")
        budget_id = id(self)
        reference = weakref.ref(self, lambda ref: _discard_budget(ref, budget_id))
        _BUDGET_REGISTRY[budget_id] = _BudgetRecord(reference, total_cap, non_model_reserve)

    def _record(self) -> _BudgetRecord:
        record = _BUDGET_REGISTRY.get(id(self))
        if record is None or record.owner_ref() is not self:
            raise RuntimeError("invalid action budget")
        return record

    def _validated_ledger(self) -> tuple[str, ...]:
        ledger = self._record().action_ledger
        if not isinstance(ledger, tuple) or any(
            action_class not in _CANONICAL_ACTION_CLASSES for action_class in ledger
        ):
            raise RuntimeError("invalid action ledger")
        return ledger

    @property
    def total_used(self) -> int:
        return len(self._validated_ledger())

    @property
    def model_used(self) -> int:
        return self._validated_ledger().count("model")

    @property
    def non_model_used(self) -> int:
        ledger = self._validated_ledger()
        return ledger.count("non_model")

    @property
    def remaining_actions(self) -> int:
        return self._record().total_cap - self.total_used

    @property
    def remaining_model_actions(self) -> int:
        record = self._record()
        model_capacity = record.total_cap - record.non_model_reserve - self.model_used
        return max(0, min(model_capacity, record.total_cap - self.total_used))

    @property
    def total_cap(self) -> int:
        return self._record().total_cap

    @property
    def non_model_reserve(self) -> int:
        return self._record().non_model_reserve

    def reserve(self, kind: str) -> None:
        if not isinstance(kind, str) or (
            kind not in MODEL_ACTION_KINDS and kind not in NON_MODEL_ACTION_KINDS
        ):
            raise ValueError(f"unknown action kind: {kind!r}")
        record = self._record()
        ledger = self._validated_ledger()
        total_used = len(ledger)
        model_used = ledger.count("model")
        non_model_used = ledger.count("non_model")
        if total_used >= self.total_cap:
            raise ValueError("combined action ceiling exhausted before action 1001")
        is_model = kind in MODEL_ACTION_KINDS
        if is_model and model_used >= self.total_cap - self.non_model_reserve:
            raise ValueError("model call cannot consume the frozen non-model reserve")
        next_total = total_used + 1
        next_model = model_used + int(is_model)
        next_non_model = non_model_used + int(not is_model)
        if next_total != next_model + next_non_model or next_total > self.total_cap:
            raise RuntimeError("invalid action-budget transition")
        record.action_ledger = ledger + ("model" if is_model else "non_model",)

    def to_dict(self) -> dict[str, int]:
        return {
            "total_cap": self.total_cap,
            "non_model_reserve": self.non_model_reserve,
            "total_used": self.total_used,
            "model_used": self.model_used,
            "non_model_used": self.non_model_used,
        }


@dataclass(frozen=True)
class RuntimeProfile:
    model_key: str
    planning_seconds: float
    stress_seconds: float | None = None

    @classmethod
    def small_a(cls) -> "RuntimeProfile":
        return cls("SMALL_A", 0.09)

    @classmethod
    def qwen(cls, *, stress: bool = False) -> "RuntimeProfile":
        return cls("QWEN", 77.22 if stress else 33.97, stress_seconds=77.22)

    @classmethod
    def devstral(cls) -> "RuntimeProfile":
        return cls("DEVSTRAL_24B", 8.75)
