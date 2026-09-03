from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
from typing import Any


class ClaimState(str, Enum):
    OBSERVED = "OBSERVED"
    HYPOTHESIZED = "HYPOTHESIZED"
    CAUSALLY_VERIFIED = "CAUSALLY_VERIFIED"
    GENERALIZED = "GENERALIZED"
    PROMOTED = "PROMOTED"
    CONTRADICTED = "CONTRADICTED"


class Disposition(str, Enum):
    EXECUTE = "EXECUTE"
    ACQUIRE_EVIDENCE = "ACQUIRE_EVIDENCE"
    ESCALATE = "ESCALATE"
    SAFE_STOP = "SAFE_STOP"


class RouteMode(str, Enum):
    ROUTINE_LOCAL = "ROUTINE_LOCAL"
    SCAFFOLDED_LOCAL = "SCAFFOLDED_LOCAL"
    QWEN_STANDARD = "QWEN_STANDARD"
    QWEN_MAX = "QWEN_MAX"
    NOVELTY_INVESTIGATION = "NOVELTY_INVESTIGATION"
    ACQUIRE_EVIDENCE = "ACQUIRE_EVIDENCE"
    SAFE_STOP = "SAFE_STOP"


class CapabilityState(str, Enum):
    RELIABLE = "RELIABLE"
    CONDITIONAL = "CONDITIONAL"
    UNSTABLE = "UNSTABLE"
    FAILS = "FAILS"


class MechanismClass(str, Enum):
    REQUIRED = "REQUIRED"
    CONDITIONAL = "CONDITIONAL"
    REDUNDANT = "REDUNDANT"
    HARMFUL = "HARMFUL"
    UNRESOLVED = "UNRESOLVED"


class PromotionState(str, Enum):
    OBSERVED = "OBSERVED"
    HYPOTHESIZED = "HYPOTHESIZED"
    CAUSALLY_VERIFIED = "CAUSALLY_VERIFIED"
    NEIGHBOR_GENERALIZED = "NEIGHBOR_GENERALIZED"
    FRESH_GENERALIZED = "FRESH_GENERALIZED"
    REGRESSION_SAFE = "REGRESSION_SAFE"
    PROMOTED = "PROMOTED"
    SUSPENDED = "SUSPENDED"


class ClosureState(str, Enum):
    FREEZE = "FREEZE"
    TUNE = "TUNE"
    REJECT = "REJECT"
    DEFER = "DEFER"
    UNRESOLVED_BUT_IDENTIFIED = "UNRESOLVED_BUT_IDENTIFIED"


class SequentialDecision(str, Enum):
    SUPERIOR = "SUPERIOR"
    NONINFERIOR = "NONINFERIOR"
    HARMFUL = "HARMFUL"
    FUTILE = "FUTILE"
    UNRESOLVED = "UNRESOLVED"


class DuplicateIdentityError(ValueError):
    pass


class IdentityRegistry:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def register(self, identity: str) -> None:
        if not identity or identity in self._seen:
            raise DuplicateIdentityError(identity)
        self._seen.add(identity)


def _canonical(value: Any) -> Any:
    if is_dataclass(value):
        return _canonical(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, set):
        return sorted((_canonical(v) for v in value), key=repr)
    return value


def stable_hash(value: Any) -> str:
    payload = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
