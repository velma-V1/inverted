from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Iterable, Mapping


class QwenCompletionClass(str, Enum):
    CONTEXT_EXHAUSTED = "CONTEXT_EXHAUSTED"
    EMPTY_FINAL = "EMPTY_FINAL"
    SEMANTIC_RESULT = "SEMANTIC_RESULT"


@dataclass(frozen=True)
class QwenPolicy:
    policy_id: str
    chat_options: dict[str, Any] = field(default_factory=dict)
    max_calls: int = 48

    def __post_init__(self) -> None:
        if self.max_calls < 0 or self.max_calls > 48:
            raise ValueError("D4 Qwen policy max_calls must be in [0,48]")


def classify_qwen_completion(
    *,
    done_reason: str | None,
    input_tokens: int,
    output_tokens: int,
    num_ctx: int,
    final_text: str,
) -> QwenCompletionClass:
    reason = str(done_reason or "").lower()
    if reason == "length" or (
        int(num_ctx) > 0
        and int(input_tokens) + int(output_tokens) >= int(num_ctx)
        and not str(final_text).strip()
    ):
        return QwenCompletionClass.CONTEXT_EXHAUSTED
    if not str(final_text).strip():
        return QwenCompletionClass.EMPTY_FINAL
    return QwenCompletionClass.SEMANTIC_RESULT


def _matched_anytime_interval(values: Iterable[float], alpha: float = 0.05) -> dict[str, float | int | str]:
    xs = [float(value) for value in values]
    if not xs:
        return {"n": 0, "mean": 0.0, "lower": -1.0, "upper": 1.0, "method": "D4_MATCHED_ANYTIME_HOEFFDING_V1"}
    if any(value < -1.0 or value > 1.0 for value in xs):
        raise ValueError("D4 matched deltas must be bounded in [-1,1]")
    n = len(xs)
    transformed = [(value + 1.0) / 2.0 for value in xs]
    alpha_n = float(alpha) * 6.0 / (math.pi**2 * n**2)
    half = math.sqrt(math.log(2.0 / alpha_n) / (2.0 * n))
    transformed_mean = sum(transformed) / n
    lower_t = max(0.0, transformed_mean - half)
    upper_t = min(1.0, transformed_mean + half)
    return {
        "n": n,
        "mean": 2.0 * transformed_mean - 1.0,
        "lower": 2.0 * lower_t - 1.0,
        "upper": 2.0 * upper_t - 1.0,
        "method": "D4_MATCHED_ANYTIME_HOEFFDING_V1",
    }


def select_qwen_policy(
    records: Iterable[Mapping[str, Any]],
    *,
    model_id: str,
    minimum_matched_cases: int = 12,
) -> dict[str, Any]:
    by_case: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in records:
        case_id = str(row.get("case_id", ""))
        policy_id = str(row.get("policy_id", ""))
        if not case_id or policy_id not in {"DEFAULT", "THINK_OFF"}:
            continue
        by_case.setdefault(case_id, {})[policy_id] = row

    matched = [pair for pair in by_case.values() if {"DEFAULT", "THINK_OFF"} <= set(pair)]
    deltas = [
        float(bool(pair["THINK_OFF"].get("semantic_action_correct", False)))
        - float(bool(pair["DEFAULT"].get("semantic_action_correct", False)))
        for pair in matched
    ]
    interval = _matched_anytime_interval(deltas)
    default_exhausted = sum(
        str(pair["DEFAULT"].get("completion_class", "")) == QwenCompletionClass.CONTEXT_EXHAUSTED.value
        for pair in matched
    )
    off_exhausted = sum(
        str(pair["THINK_OFF"].get("completion_class", "")) == QwenCompletionClass.CONTEXT_EXHAUSTED.value
        for pair in matched
    )

    semantic_decision = "UNRESOLVED"
    state = "UNRESOLVED"
    policy_id: str | None = None
    chat_options: dict[str, Any] = {}

    if len(matched) >= int(minimum_matched_cases):
        lower = float(interval["lower"])
        upper = float(interval["upper"])
        if lower > 0.0 and off_exhausted <= default_exhausted:
            semantic_decision = "SUPERIOR"
            state = "FROZEN"
            policy_id = "THINK_OFF"
            chat_options = {"think": False}
        elif upper < 0.0 and default_exhausted <= off_exhausted:
            semantic_decision = "HARMFUL"
            state = "FROZEN"
            policy_id = "DEFAULT"
            chat_options = {}

    return {
        "state": state,
        "policy_id": policy_id,
        "model_id": str(model_id),
        "chat_options": chat_options,
        "matched_cases": len(matched),
        "semantic_decision": semantic_decision,
        "semantic_delta_interval": interval,
        "default_context_exhausted": default_exhausted,
        "think_off_context_exhausted": off_exhausted,
        "selection_rule": "freeze only on anytime-valid matched semantic superiority/harm with no worse context-exhaustion direction",
    }
