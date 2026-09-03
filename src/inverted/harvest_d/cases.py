from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any

from .types import Disposition


class OracleKind(str, Enum):
    JSON_EQUALS = "JSON_EQUALS"
    TEXT_EQUALS = "TEXT_EQUALS"
    TEXT_CONTAINS = "TEXT_CONTAINS"


@dataclass(frozen=True)
class OracleSpec:
    kind: OracleKind
    expected: Any

    def evaluate(self, text: str) -> bool:
        if self.kind is OracleKind.JSON_EQUALS:
            try:
                return json.loads(text) == self.expected
            except (json.JSONDecodeError, TypeError):
                return False
        if self.kind is OracleKind.TEXT_EQUALS:
            return text.strip() == str(self.expected).strip()
        if self.kind is OracleKind.TEXT_CONTAINS:
            return str(self.expected) in text
        return False


@dataclass(frozen=True)
class HarvestCase:
    case_id: str
    family: str
    capability: str
    difficulty: int
    prompt: str
    expected_disposition: Disposition
    oracle: OracleSpec
    metadata: dict[str, Any] | None = None

    def model_prompt(self) -> str:
        return self.prompt

    def evaluate(self, response_text: str) -> bool:
        return self.oracle.evaluate(response_text)


@dataclass(frozen=True)
class ResponseScore:
    parseable_json: bool
    format_valid: bool
    schema_valid: bool
    disposition_correct: bool
    answer_correct: bool
    overall_semantic_correct: bool
    contract_success: bool


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


def _normalize_semantic_value(value: Any) -> Any:
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized.startswith("queue_") and len(normalized) > len("queue_"):
            normalized = normalized[len("queue_"):]
        return normalized
    return value


def score_response(case: HarvestCase, response_text: str) -> ResponseScore:
    if case.oracle.kind is not OracleKind.JSON_EQUALS or not isinstance(case.oracle.expected, dict):
        ok = case.evaluate(response_text)
        return ResponseScore(False, ok, ok, ok, ok, ok, ok)

    parsed, parseable_json, format_valid = _parse_json_relaxed(response_text)
    expected = case.oracle.expected
    if not isinstance(parsed, dict):
        return ResponseScore(parseable_json, format_valid, False, False, False, False, False)

    schema_valid = set(parsed) == set(expected)
    disposition_correct = _normalize_semantic_value(parsed.get("disposition")) == _normalize_semantic_value(expected.get("disposition"))

    answer = parsed.get("answer")
    if "answer" not in parsed:
        aliases = list((case.metadata or {}).get("answer_key_aliases", []))
        if not aliases:
            aliases = ["route", "reason", "reason_token", "missing_evidence", "recovery_token", "order", "next_step_token"]
        for key in aliases:
            if key in parsed:
                answer = parsed[key]
                break

    accepted_answers = [expected.get("answer")]
    accepted_answers.extend((case.metadata or {}).get("accepted_answer_aliases", []))
    answer_correct = any(
        _normalize_semantic_value(answer) == _normalize_semantic_value(candidate)
        for candidate in accepted_answers
    )

    overall_semantic_correct = bool(disposition_correct and answer_correct)
    contract_success = bool(format_valid and schema_valid and overall_semantic_correct)
    return ResponseScore(
        parseable_json,
        format_valid,
        schema_valid,
        disposition_correct,
        answer_correct,
        overall_semantic_correct,
        contract_success,
    )


def load_cases(path: str | Path) -> list[HarvestCase]:
    rows: list[HarvestCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        oracle_raw = raw.pop("oracle")
        rows.append(
            HarvestCase(
                raw["case_id"],
                raw["family"],
                raw["capability"],
                int(raw["difficulty"]),
                raw["prompt"],
                Disposition(raw["expected_disposition"]),
                OracleSpec(OracleKind(oracle_raw["kind"]), oracle_raw["expected"]),
                raw.get("metadata") or {},
            )
        )
    return rows
