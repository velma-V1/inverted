from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
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
            try: return json.loads(text) == self.expected
            except (json.JSONDecodeError, TypeError): return False
        if self.kind is OracleKind.TEXT_EQUALS: return text.strip() == str(self.expected).strip()
        if self.kind is OracleKind.TEXT_CONTAINS: return str(self.expected) in text
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

def load_cases(path: str | Path) -> list[HarvestCase]:
    rows: list[HarvestCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        raw = json.loads(line)
        oracle_raw = raw.pop("oracle")
        rows.append(HarvestCase(raw["case_id"], raw["family"], raw["capability"], int(raw["difficulty"]), raw["prompt"],
                                Disposition(raw["expected_disposition"]), OracleSpec(OracleKind(oracle_raw["kind"]), oracle_raw["expected"]),
                                raw.get("metadata") or {}))
    return rows
