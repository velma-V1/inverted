from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .types import stable_hash


_LOCAL_SEARCH_RULE = {
    "version": "HD-NEXT-1-LOCAL-SEARCH-v1",
    "leave_one_out": "every active I1-I10/A1-A4 and every non-minimal delivery-complexity component",
    "joint_removal": "one deterministic pairwise support-removal attack when legal",
    "negative_transfer": ["OVERLOADED", "FULL_EXTRA_SUPPORT"],
    "all_information_off_forbidden": True,
}
LOCAL_SEARCH_RULE_HASH = stable_hash(_LOCAL_SEARCH_RULE)


@dataclass(frozen=True)
class LocalVariant:
    variant_id: str
    kind: str
    component_ids: tuple[str, ...]
    factor_vector: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "variant_id": self.variant_id,
            "kind": self.kind,
            "component_ids": list(self.component_ids),
            "factor_vector": dict(self.factor_vector),
            "local_search_rule_hash": LOCAL_SEARCH_RULE_HASH,
        }


def active_support_components(vector: Mapping[str, str]) -> tuple[str, ...]:
    components: list[str] = []
    components.extend(f"I{i}" for i in range(1, 11) if vector.get(f"I{i}") == "ON")
    components.extend(f"A{i}" for i in range(1, 5) if vector.get(f"A{i}") == "TARGET")
    if vector.get("representation", "RAW_PROSE") != "RAW_PROSE":
        components.append("representation")
    if vector.get("ordering", "DEFAULT") != "DEFAULT":
        components.append("ordering")
    if vector.get("amount", "MINIMUM") != "MINIMUM":
        components.append("amount")
    if vector.get("timing", "UPFRONT") != "UPFRONT":
        components.append("timing")
    if vector.get("placement", "TASK_CONTEXT") != "TASK_CONTEXT":
        components.append("placement")
    return tuple(components)


def _legal(vector: Mapping[str, str]) -> bool:
    return any(vector.get(f"I{i}") == "ON" for i in range(1, 11))


def _remove(vector: Mapping[str, str], component: str) -> dict[str, str]:
    row = dict(vector)
    if component.startswith("I"):
        row[component] = "OFF"
    elif component.startswith("A"):
        row[component] = "OFF"
    elif component == "representation":
        row[component] = "RAW_PROSE"
    elif component == "ordering":
        row[component] = "DEFAULT"
    elif component == "amount":
        row[component] = "MINIMUM"
    elif component == "timing":
        row[component] = "UPFRONT"
    elif component == "placement":
        row[component] = "TASK_CONTEXT"
    else:
        raise ValueError(f"unknown support component: {component}")
    return row


def variant_identity(kind: str, component_ids: tuple[str, ...], factor_vector: Mapping[str, str]) -> str:
    return stable_hash(
        {
            "local_search_rule_hash": LOCAL_SEARCH_RULE_HASH,
            "kind": str(kind),
            "component_ids": list(component_ids),
            "factor_vector": dict(sorted(factor_vector.items())),
        }
    )


def _variant(kind: str, components: tuple[str, ...], vector: Mapping[str, str]) -> LocalVariant:
    row = dict(vector)
    if not _legal(row):
        raise ValueError("HD-NEXT-1 local search may not remove all model-visible information")
    return LocalVariant(variant_identity(kind, components, row), kind, components, row)


def generate_local_variants(winner: Mapping[str, str]) -> tuple[LocalVariant, ...]:
    if not _legal(winner):
        raise ValueError("winning treatment must expose at least one information field")
    result: list[LocalVariant] = []
    active = active_support_components(winner)
    for component in active:
        row = _remove(winner, component)
        if _legal(row):
            result.append(_variant("LEAVE_ONE_OUT", (component,), row))

    pair_candidates = [item for item in active if item.startswith(("I", "A"))]
    pair: tuple[str, str] | None = None
    for left_index, left in enumerate(pair_candidates):
        for right in pair_candidates[left_index + 1 :]:
            row = _remove(_remove(winner, left), right)
            if _legal(row):
                pair = (left, right)
                result.append(_variant("JOINT_REMOVAL", pair, row))
                break
        if pair is not None:
            break

    overloaded = dict(winner)
    overloaded["amount"] = "OVERLOADED"
    result.append(_variant("NEGATIVE_TRANSFER", ("amount:OVERLOADED",), overloaded))

    full_support = dict(winner)
    for i in range(1, 11):
        full_support[f"I{i}"] = "ON"
    for i in range(1, 5):
        full_support[f"A{i}"] = "TARGET"
    full_support["amount"] = "FULL"
    result.append(_variant("NEGATIVE_TRANSFER", ("FULL_EXTRA_SUPPORT",), full_support))

    unique: list[LocalVariant] = []
    seen: set[str] = set()
    for row in result:
        if row.variant_id not in seen:
            seen.add(row.variant_id)
            unique.append(row)
    return tuple(unique)


def validate_generated_treatment(record: Mapping[str, object]) -> bool:
    if str(record.get("local_search_rule_hash") or "") != LOCAL_SEARCH_RULE_HASH:
        return False
    kind = str(record.get("kind") or "")
    components = tuple(str(item) for item in (record.get("component_ids") or ()))
    vector = record.get("factor_vector")
    if not isinstance(vector, dict) or not _legal(vector):
        return False
    return str(record.get("treatment_id") or record.get("variant_id") or "") == variant_identity(kind, components, vector)
