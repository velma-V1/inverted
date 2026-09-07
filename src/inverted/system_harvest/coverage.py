from __future__ import annotations

from dataclasses import dataclass, replace

from .types import CoverageStatus


_BLOCKING = {
    CoverageStatus.PENDING,
    CoverageStatus.CAPTURED_PARTIAL,
    CoverageStatus.NEEDS_RUNTIME_PROBE,
    CoverageStatus.NEEDS_STATIC_PROBE,
    CoverageStatus.NEEDS_GAP_CLOSURE,
}


@dataclass(frozen=True)
class CoverageItem:
    item_id: str
    status: CoverageStatus
    reason: str | None = None
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FutureQueryProbe:
    question: str
    evidence_ids: tuple[str, ...]
    passed: bool
    predefined: bool


@dataclass(frozen=True)
class CoverageLedger:
    items: tuple[CoverageItem, ...]
    future_queries: tuple[FutureQueryProbe, ...] = ()

    def __post_init__(self) -> None:
        ids = tuple(item.item_id for item in self.items)
        if any(not item_id.strip() for item_id in ids) or len(set(ids)) != len(ids):
            raise ValueError("coverage item IDs must be unique and non-empty")
    @property
    def is_open(self) -> bool:
        return any(item.status in _BLOCKING for item in self.items)

    @property
    def future_query_ready(self) -> bool:
        return any(q.passed and not q.predefined and q.evidence_ids for q in self.future_queries)

    def add_item(self, item: CoverageItem) -> "CoverageLedger":
        if any(existing.item_id == item.item_id for existing in self.items):
            raise ValueError(f"duplicate coverage item {item.item_id}")
        return CoverageLedger(self.items + (item,), self.future_queries)

    def resolve(self, item_id: str, status: CoverageStatus, *, reason: str | None = None,
                evidence_ids: tuple[str, ...] = ()) -> "CoverageLedger":
        if status is CoverageStatus.INACCESSIBLE and (not reason or not evidence_ids):
            raise ValueError("INACCESSIBLE requires reason and supporting evidence IDs")
        found = False
        updated = []
        for item in self.items:
            if item.item_id == item_id:
                found = True
                updated.append(replace(item, status=status, reason=reason, evidence_ids=tuple(evidence_ids)))
            else:
                updated.append(item)
        if not found:
            raise KeyError(item_id)
        return CoverageLedger(tuple(updated), self.future_queries)

    def add_future_query(self, probe: FutureQueryProbe) -> "CoverageLedger":
        if not probe.question.strip():
            raise ValueError("future query question must be non-empty")
        return CoverageLedger(self.items, self.future_queries + (probe,))
