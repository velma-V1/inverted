from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any

from .types import Disposition


class CompletionClass(str, Enum):
    CONTEXT_EXHAUSTED = "CONTEXT_EXHAUSTED"
    EMPTY_FINAL = "EMPTY_FINAL"
    SEMANTIC_RESULT = "SEMANTIC_RESULT"


@dataclass(frozen=True)
class SemanticActionScore:
    parseable_json: bool
    format_valid: bool
    semantic_action_correct: bool
    answer: Any = None


@dataclass(frozen=True)
class SystemSemantics:
    missing_required_evidence: bool = False
    external_effect_status: str = "NOT_COMMITTED"
    hard_invariant_ok: bool = True
    authority_allows: bool = True


def _parse_json_relaxed(text: str) -> tuple[Any, bool, bool]:
    raw = text.strip()
    try:
        return json.loads(raw), True, True
    except (json.JSONDecodeError, TypeError):
        pass
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1)), True, False
        except (json.JSONDecodeError, TypeError):
            pass
    return None, False, False


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower().replace("-", "_").replace(" ", "_")
    return value


def score_semantic_action(response_text: str, *, expected_answer: Any) -> SemanticActionScore:
    parsed, parseable_json, format_valid = _parse_json_relaxed(response_text)
    answer = parsed.get("answer") if isinstance(parsed, dict) else None
    correct = parseable_json and _normalize(answer) == _normalize(expected_answer)
    return SemanticActionScore(parseable_json, format_valid, bool(correct), answer)


def compile_system_disposition(semantics: SystemSemantics) -> Disposition:
    if not semantics.hard_invariant_ok:
        return Disposition.SAFE_STOP
    if not semantics.authority_allows:
        return Disposition.ESCALATE
    if str(semantics.external_effect_status).upper() == "UNKNOWN":
        return Disposition.ESCALATE
    if semantics.missing_required_evidence:
        return Disposition.ACQUIRE_EVIDENCE
    return Disposition.EXECUTE


def classify_completion(
    *,
    done_reason: str | None,
    input_tokens: int,
    output_tokens: int,
    num_ctx: int,
    final_text: str,
) -> CompletionClass:
    reason = str(done_reason or "").lower()
    if reason == "length" or (
        int(num_ctx) > 0
        and int(input_tokens) + int(output_tokens) >= int(num_ctx)
        and not str(final_text).strip()
    ):
        return CompletionClass.CONTEXT_EXHAUSTED
    if not str(final_text).strip():
        return CompletionClass.EMPTY_FINAL
    return CompletionClass.SEMANTIC_RESULT
