from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable


def classify_replay(*, original_success: bool, targeted_success: bool, sham_success: bool) -> str:
    if bool(targeted_success) and not bool(original_success) and not bool(sham_success):
        return "CAUSAL"
    if bool(targeted_success) and bool(sham_success) and not bool(original_success):
        return "AMBIGUOUS"
    if bool(targeted_success) == bool(original_success):
        return "INEFFECTIVE"
    return "AMBIGUOUS"


def capture_fork_state(state: dict[str, Any], *, decision_index: int) -> dict[str, Any]:
    return {"decision_index": int(decision_index), "state": deepcopy(state)}


def apply_intervention(fork_state: dict[str, Any], intervention: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(fork_state)
    result["intervention"] = deepcopy(intervention)
    return result


def fork_and_replay(
    *,
    original: dict[str, Any],
    targeted_intervention: dict[str, Any],
    sham_intervention: dict[str, Any],
    replay: Callable[[dict[str, Any], dict[str, Any]], bool],
) -> dict[str, Any]:
    original_success = bool(original.get("success"))
    targeted_success = bool(replay(deepcopy(original), deepcopy(targeted_intervention)))
    sham_success = bool(replay(deepcopy(original), deepcopy(sham_intervention)))
    classification = classify_replay(
        original_success=original_success,
        targeted_success=targeted_success,
        sham_success=sham_success,
    )
    return {
        "original_success": original_success,
        "targeted_success": targeted_success,
        "sham_success": sham_success,
        "classification": classification,
        "causal_lift": int(targeted_success) - int(sham_success),
        "targeted_intervention": deepcopy(targeted_intervention),
        "sham_intervention": deepcopy(sham_intervention),
    }
