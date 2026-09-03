from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Iterable


@dataclass(frozen=True)
class SystemInvolvement:
    context: bool = False
    state: bool = False
    decomposition: bool = False
    evidence: bool = False
    action_constraint: bool = False
    verification: bool = False
    recovery: bool = False
    routing: bool = False
    authority: bool = False
    knowledge: bool = False

    def triggered_channels(self) -> set[str]:
        return {f.name for f in fields(self) if getattr(self, f.name)}

    @property
    def any(self) -> bool:
        return bool(self.triggered_channels())


def architecture_intervention_ratio(rows: Iterable[SystemInvolvement]) -> float:
    items = list(rows)
    if not items:
        return 0.0
    return sum(1 for row in items if row.any) / len(items)
