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


def _exact_paired_pvalue(think_off_wins: int, default_wins: int) -> float:
    discordant = int(think_off_wins) + int(default_wins)
    if discordant <= 0:
        return 1.0
    tail = min(int(think_off_wins), int(default_wins))
    probability = sum(math.comb(discordant, k) for k in range(tail + 1)) / (2.0**discordant)
    return min(1.0, 2.0 * probability)


def select_qwen_policy(
    records: Iterable[Mapping[str, Any]],
    *,
    model_id: str,
    minimum_matched_cases: int = 24,
) -> dict[str, Any]:
    """Freeze the operating policy only after the preregistered 24-pair horizon.

    A decisive paired semantic difference is reported as such. If semantics are
    not decisively different, D4 still has to hand Closure a stable operating
    policy: choose the higher observed semantic accuracy, then fewer context
    exhaustions, then DEFAULT as the conservative exact-tie fallback. Such a
    selection is explicitly labelled provisional rather than promoted as a
    causal semantic superiority claim.
    """

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
    default_correct = sum(bool(pair["DEFAULT"].get("semantic_action_correct", False)) for pair in matched)
    off_correct = sum(bool(pair["THINK_OFF"].get("semantic_action_correct", False)) for pair in matched)
    off_wins = sum(
        bool(pair["THINK_OFF"].get("semantic_action_correct", False))
        and not bool(pair["DEFAULT"].get("semantic_action_correct", False))
        for pair in matched
    )
    default_wins = sum(
        bool(pair["DEFAULT"].get("semantic_action_correct", False))
        and not bool(pair["THINK_OFF"].get("semantic_action_correct", False))
        for pair in matched
    )
    paired_p = _exact_paired_pvalue(off_wins, default_wins)
    default_exhausted = sum(
        str(pair["DEFAULT"].get("completion_class", "")) == QwenCompletionClass.CONTEXT_EXHAUSTED.value
        for pair in matched
    )
    off_exhausted = sum(
        str(pair["THINK_OFF"].get("completion_class", "")) == QwenCompletionClass.CONTEXT_EXHAUSTED.value
        for pair in matched
    )

    state = "UNRESOLVED"
    policy_id: str | None = None
    chat_options: dict[str, Any] = {}
    semantic_decision = "UNRESOLVED"
    evidence_status = "INCOMPLETE"
    selection_reason = "preregistered fixed horizon not reached"

    if len(matched) >= int(minimum_matched_cases):
        state = "FROZEN"
        decisive = paired_p <= 0.05 and off_wins != default_wins
        if decisive and off_wins > default_wins:
            policy_id = "THINK_OFF"
            chat_options = {"think": False}
            semantic_decision = "SUPERIOR"
            evidence_status = "DECISIVE"
            selection_reason = "paired semantic superiority at fixed horizon"
        elif decisive and default_wins > off_wins:
            policy_id = "DEFAULT"
            semantic_decision = "HARMFUL"
            evidence_status = "DECISIVE"
            selection_reason = "paired semantic harm from THINK_OFF at fixed horizon"
        else:
            semantic_decision = "NO_DECISIVE_DIFFERENCE"
            evidence_status = "PROVISIONAL_FIXED_HORIZON"
            if off_correct > default_correct:
                policy_id = "THINK_OFF"
                chat_options = {"think": False}
                selection_reason = "higher observed semantic correctness; difference not confirmatory"
            elif default_correct > off_correct:
                policy_id = "DEFAULT"
                selection_reason = "higher observed semantic correctness; difference not confirmatory"
            elif off_exhausted < default_exhausted:
                policy_id = "THINK_OFF"
                chat_options = {"think": False}
                selection_reason = "semantic tie; fewer context-exhausted completions"
            else:
                policy_id = "DEFAULT"
                selection_reason = "semantic/exhaustion tie or DEFAULT no worse; conservative fallback"

    return {
        "state": state,
        "policy_id": policy_id,
        "model_id": str(model_id),
        "chat_options": chat_options,
        "matched_cases": len(matched),
        "semantic_decision": semantic_decision,
        "evidence_status": evidence_status,
        "semantic_delta_interval": interval,
        "paired_exact_pvalue": paired_p,
        "default_semantic_correct": default_correct,
        "think_off_semantic_correct": off_correct,
        "default_only_correct": default_wins,
        "think_off_only_correct": off_wins,
        "default_context_exhausted": default_exhausted,
        "think_off_context_exhausted": off_exhausted,
        "selection_reason": selection_reason,
        "selection_rule": "24 matched pairs; exact paired semantic decision, then semantic count, context exhaustion, DEFAULT tie-break",
    }
