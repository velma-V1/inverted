from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import random
from typing import Any

from .cases import HarvestCase
from .types import stable_hash


class ClosureAmount(str, Enum):
    MINIMUM = "MINIMUM"
    COMPRESSED = "COMPRESSED"
    MODERATE = "MODERATE"
    FULL = "FULL"
    OVERLOADED = "OVERLOADED"


class ClosureOrdering(str, Enum):
    DEFAULT = "DEFAULT"
    TASK_OBJECTIVE_FIRST = "TASK_OBJECTIVE_FIRST"
    STATE_FIRST = "STATE_FIRST"
    EVIDENCE_FIRST = "EVIDENCE_FIRST"
    SAFETY_STATE_EVIDENCE_FIRST = "SAFETY_STATE_EVIDENCE_FIRST"
    SHUFFLED_CONTROL = "SHUFFLED_CONTROL"


@dataclass(frozen=True)
class ClosureInformationPlan:
    amount: ClosureAmount = ClosureAmount.FULL
    ordering: ClosureOrdering = ClosureOrdering.DEFAULT
    shuffle_seed: int = 20260903


@dataclass(frozen=True)
class ClosureInformationPacket:
    rendered: str
    rendered_hash: str
    semantic_field_hash: str
    field_order: tuple[str, ...]
    amount: str
    ordering: str
    approx_token_count: int


_AMOUNT_FIELDS: dict[ClosureAmount, tuple[str, ...]] = {
    ClosureAmount.MINIMUM: ("I1", "I2", "I4", "I6", "I7"),
    ClosureAmount.COMPRESSED: ("I1", "I2", "I3", "I4", "I6", "I7"),
    ClosureAmount.MODERATE: ("I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8"),
    ClosureAmount.FULL: tuple(f"I{i}" for i in range(1, 11)),
    ClosureAmount.OVERLOADED: tuple(f"I{i}" for i in range(1, 11)),
}


def _order(fields: list[str], plan: ClosureInformationPlan) -> list[str]:
    priority_maps: dict[ClosureOrdering, tuple[str, ...]] = {
        ClosureOrdering.TASK_OBJECTIVE_FIRST: tuple(f"I{i}" for i in range(1, 11)),
        ClosureOrdering.STATE_FIRST: ("I2", "I1", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I10"),
        ClosureOrdering.EVIDENCE_FIRST: ("I4", "I1", "I2", "I3", "I5", "I6", "I7", "I8", "I9", "I10"),
        ClosureOrdering.SAFETY_STATE_EVIDENCE_FIRST: ("I6", "I2", "I4", "I3", "I5", "I7", "I8", "I9", "I10", "I1"),
    }
    if plan.ordering is ClosureOrdering.SHUFFLED_CONTROL:
        shuffled = list(fields)
        random.Random(int(plan.shuffle_seed)).shuffle(shuffled)
        if len(shuffled) > 1 and shuffled == fields:
            shuffled = shuffled[1:] + shuffled[:1]
        return shuffled
    if plan.ordering in priority_maps:
        rank = {field_id: idx for idx, field_id in enumerate(priority_maps[plan.ordering])}
        return sorted(fields, key=lambda field_id: rank.get(field_id, 999))
    return list(fields)


def _approx_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def render_closure_packet(case: HarvestCase, plan: ClosureInformationPlan) -> ClosureInformationPacket:
    source = dict((case.metadata or {}).get("d3_information", {}))
    selected = [field_id for field_id in _AMOUNT_FIELDS[plan.amount] if field_id in source]
    ordered = _order(selected, plan)
    semantic_payload = {field_id: source[field_id] for field_id in sorted(selected)}

    if plan.amount is ClosureAmount.COMPRESSED:
        rendered = "; ".join(
            f"{field_id}={json.dumps(source[field_id], sort_keys=True, ensure_ascii=False)}"
            for field_id in ordered
        )
    else:
        rendered = "\n".join(
            f"{field_id}:{json.dumps(source[field_id], sort_keys=True, ensure_ascii=False)}"
            for field_id in ordered
        )

    if plan.amount is ClosureAmount.OVERLOADED:
        neutral = "NON_AUTHORITATIVE_HISTORY: retained only for burden measurement. "
        rendered += "\n" + (neutral * max(8, len(rendered) // max(1, len(neutral))))

    return ClosureInformationPacket(
        rendered=rendered,
        rendered_hash=stable_hash(rendered),
        semantic_field_hash=stable_hash(semantic_payload),
        field_order=tuple(ordered),
        amount=plan.amount.value,
        ordering=plan.ordering.value,
        approx_token_count=_approx_tokens(rendered),
    )
