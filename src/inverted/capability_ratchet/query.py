from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .core import FailureFixture, Partition, PromotionState, ReplayRequest
from .replay_store import ReplayStore, SupersessionRecord


@dataclass(frozen=True)
class ReplaySelector:
    source_model: str | None = None
    target_model: str | None = None
    family: str | None = None
    difficulty: int | None = None
    failure_class: str | None = None
    campaign: str | None = None
    partition: Partition | str | None = None
    promotion_state: PromotionState | str | None = None
    snapshot_ids: tuple[str, ...] = ()


def _resolve_active_group(snapshot_id: str, fixtures: list[FailureFixture], supersessions: tuple[SupersessionRecord, ...]) -> FailureFixture:
    if len(fixtures) == 1:
        return fixtures[0]
    ids = {fixture.record_id for fixture in fixtures}
    if None in ids:
        raise ValueError(f"failure fixture {snapshot_id!r} is missing committed record_id")
    links = {
        record.old_record_id: record.replacement_record_id
        for record in supersessions
        if record.old_record_id in ids and record.replacement_record_id in ids
    }
    active = [fixture for fixture in fixtures if fixture.record_id not in links]
    incoming = set(links.values())
    starts = [fixture for fixture in fixtures if fixture.record_id not in incoming]
    if len(links) != len(fixtures) - 1 or len(active) != 1 or len(starts) != 1:
        raise ValueError(f"failure fixture {snapshot_id!r} has invalid supersession chain")
    visited: set[str] = set()
    current = starts[0].record_id
    while current in links and current not in visited:
        visited.add(current)
        current = links[current]
    if current != active[0].record_id or len(visited) != len(fixtures) - 1:
        raise ValueError(f"failure fixture {snapshot_id!r} has invalid supersession chain")
    return active[0]


def _active_failures_from_records(records: tuple[object, ...]) -> tuple[FailureFixture, ...]:
    grouped: dict[str, list[FailureFixture]] = defaultdict(list)
    supersessions = tuple(record for record in records if isinstance(record, SupersessionRecord))
    for record in records:
        if isinstance(record, FailureFixture):
            grouped[record.failure_snapshot_id].append(record)
    return tuple(
        _resolve_active_group(snapshot_id, grouped[snapshot_id], supersessions)
        for snapshot_id in sorted(grouped)
    )


def select_failures(store: ReplayStore, selector: ReplaySelector) -> tuple[FailureFixture, ...]:
    if not isinstance(store, ReplayStore):
        raise TypeError("store must be ReplayStore")
    if not isinstance(selector, ReplaySelector):
        raise TypeError("selector must be ReplaySelector")
    records = store.records()
    partition = None if selector.partition is None else Partition(selector.partition)
    promotion = None if selector.promotion_state is None else PromotionState(selector.promotion_state)
    snapshots = set(selector.snapshot_ids)
    targeted_roots: set[str] | None = None
    if selector.target_model is not None:
        targeted_roots = {
            record.failure_snapshot_id
            for record in records
            if isinstance(record, ReplayRequest)
            and record.target_model_id == selector.target_model
        }

    selected: list[FailureFixture] = []
    for fixture in _active_failures_from_records(records):
        if selector.source_model is not None and fixture.source_model_id != selector.source_model:
            continue
        if selector.family is not None and fixture.family != selector.family:
            continue
        if selector.difficulty is not None and fixture.metadata.get("difficulty") != selector.difficulty:
            continue
        if selector.failure_class is not None and selector.failure_class not in fixture.failure_classes:
            continue
        if selector.campaign is not None and fixture.source_campaign_id != selector.campaign:
            continue
        if partition is not None and fixture.partition is not partition:
            continue
        if promotion is not None and fixture.promotion_state is not promotion:
            continue
        if snapshots and fixture.failure_snapshot_id not in snapshots:
            continue
        if targeted_roots is not None and fixture.failure_snapshot_id not in targeted_roots:
            continue
        selected.append(fixture)
    return tuple(selected)
