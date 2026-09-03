from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .types import Disposition


class FaultDefinitionError(ValueError):
    pass


class FaultLayer(str, Enum):
    STATE = "STATE"
    EVIDENCE = "EVIDENCE"
    CONTEXT = "CONTEXT"
    TOPOLOGY = "TOPOLOGY"
    AUTHORITY = "AUTHORITY"
    TRANSACTION = "TRANSACTION"
    VERIFIER_ORACLE = "VERIFIER_ORACLE"
    RECOVERY = "RECOVERY"
    ROUTING = "ROUTING"


@dataclass(frozen=True)
class FaultInjection:
    fault_id: str
    layer: FaultLayer
    injection_time: str
    visible_information: dict[str, Any]
    hidden_truth: dict[str, Any]
    expected_detection: str
    expected_disposition: Disposition
    allowed_recovery: tuple[str, ...]
    forbidden_behavior: tuple[str, ...]
    semantic_oracle: str
    hard_invariant: str
    cleanup_replay: str

    def __post_init__(self) -> None:
        required = {
            "fault_id": self.fault_id,
            "injection_time": self.injection_time,
            "expected_detection": self.expected_detection,
            "semantic_oracle": self.semantic_oracle,
            "hard_invariant": self.hard_invariant,
            "cleanup_replay": self.cleanup_replay,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise FaultDefinitionError(f"fault injection missing required fields: {missing}")
