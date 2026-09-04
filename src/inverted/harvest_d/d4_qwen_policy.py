from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
