from __future__ import annotations

import hashlib
from typing import Any


INTERVENTION_LIBRARY = ("retry_qwen", "repair_cogito", "switch_llama")
REAL_ARM_IDS = ("S2-B0", "S2-B1", "S2-B2", "S2-B3", "S2-B4")

_B2_KEYS = (
    "failed_requirement_ids",
    "failed_requirement_kinds",
    "failed_count",
    "failure_signature",
    "deterministic_success",
    "catastrophic",
)
_B3_KEYS = (
    "family",
    "complexity",
    "failed_requirement_ids",
    "failed_requirement_kinds",
    "failed_count",
    "failure_signature",
    "deterministic_success",
    "catastrophic",
    "previous_action",
    "previous_model",
    "retry_count",
    "budget_spent",
    "budget_remaining",
)


def public_router_state(arm_id: str, evidence_state: dict[str, Any]) -> dict[str, Any]:
    """Return only the preregistered decision-time feature view for one arm."""
    source = dict(evidence_state)
    if arm_id == "S2-B0":
        return {}
    if arm_id == "S2-B1":
        return {"family": source.get("family")}
    if arm_id == "S2-B2":
        return {key: source.get(key) for key in _B2_KEYS}
    if arm_id == "S2-B3":
        return {key: source.get(key) for key in _B3_KEYS}
    if arm_id == "S2-B4":
        # Negative control: routing must be independent of every observed
        # task/failure/outcome feature. Only the preregistered seed stream and
        # step index may influence action selection.
        return {}
    raise ValueError(f"unknown S2 arm: {arm_id}")


def _family_route(family: str, step_index: int) -> str:
    routes = {
        "dependency_order": ("repair_cogito", "switch_llama"),
        "repair_containment": ("repair_cogito", "retry_qwen"),
        "state": ("retry_qwen", "repair_cogito"),
        "policy": ("retry_qwen", "repair_cogito"),
        "reconciliation": ("retry_qwen", "repair_cogito"),
        "preservation": ("retry_qwen", "repair_cogito"),
    }
    return routes.get(str(family), ("retry_qwen", "repair_cogito"))[step_index]


def _failure_route(view: dict[str, Any], step_index: int) -> str:
    kinds = {str(value) for value in (view.get("failed_requirement_kinds") or [])}
    count = int(view.get("failed_count") or 0)
    if count >= 2:
        route = ("switch_llama", "repair_cogito")
    elif kinds & {"action_before", "action_present"}:
        route = ("repair_cogito", "switch_llama")
    elif "preserve" in kinds:
        route = ("retry_qwen", "repair_cogito")
    elif "action_absent" in kinds:
        route = ("retry_qwen", "repair_cogito")
    else:
        route = ("repair_cogito", "switch_llama")
    return route[step_index]


def _rich_route(view: dict[str, Any], step_index: int) -> str:
    kinds = {str(value) for value in (view.get("failed_requirement_kinds") or [])}
    count = int(view.get("failed_count") or 0)
    catastrophic = bool(view.get("catastrophic"))
    family = str(view.get("family") or "")
    previous = str(view.get("previous_action") or "")

    if step_index == 0:
        if kinds & {"action_before", "action_present"}:
            return "repair_cogito"
        if "preserve" in kinds:
            return "retry_qwen"
        if count >= 2 or catastrophic:
            return "switch_llama"
        if family == "repair_containment":
            return "repair_cogito"
        return "retry_qwen"

    if previous == "retry_qwen":
        return "repair_cogito"
    if previous == "repair_cogito":
        return "switch_llama"
    if previous == "switch_llama":
        return "repair_cogito"
    return _failure_route(view, 1)


def _random_route(step_index: int, random_seed: int) -> str:
    payload = f"{int(random_seed)}|{int(step_index)}"
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return INTERVENTION_LIBRARY[int.from_bytes(digest[:4], "big") % len(INTERVENTION_LIBRARY)]


def select_action(
    arm_id: str,
    evidence_state: dict[str, Any],
    *,
    step_index: int,
    random_seed: int,
) -> str:
    """Select one frozen S2 action from only the arm's allowed evidence view."""
    step = int(step_index)
    if step not in (0, 1):
        raise ValueError("S2 step_index must be 0 or 1")
    view = public_router_state(arm_id, evidence_state)
    if arm_id == "S2-B0":
        return ("retry_qwen", "repair_cogito")[step]
    if arm_id == "S2-B1":
        return _family_route(str(view.get("family") or ""), step)
    if arm_id == "S2-B2":
        return _failure_route(view, step)
    if arm_id == "S2-B3":
        return _rich_route(view, step)
    if arm_id == "S2-B4":
        return _random_route(step, random_seed)
    raise ValueError(f"unknown S2 arm: {arm_id}")
