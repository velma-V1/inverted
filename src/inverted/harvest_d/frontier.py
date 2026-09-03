from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .types import CapabilityState


@dataclass(frozen=True, order=True)
class CapabilityKey:
    model: str
    capability: str
    family: str


@dataclass(frozen=True)
class CapabilityEnvelope:
    version: int
    states: Mapping[CapabilityKey, CapabilityState] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "CapabilityEnvelope":
        return cls(version=0, states={})

    def with_state(self, key: CapabilityKey, state: CapabilityState) -> "CapabilityEnvelope":
        updated = dict(self.states)
        updated[key] = state
        return CapabilityEnvelope(version=self.version + 1, states=updated)

    def state_for(self, key: CapabilityKey) -> CapabilityState | None:
        return self.states.get(key)


@dataclass(frozen=True)
class OperatingPoint:
    name: str
    semantic_success: float
    hard_invariants_pass: bool
    silent_failure_rate: float
    qwen_calls: int
    model_calls: int
    system_involvement: float
    latency_ms: float


def size_dependence_index(raw_gap: float, assisted_gap: float) -> float | None:
    if raw_gap == 0:
        return None
    return assisted_gap / raw_gap


def synergy(qwen_assisted: float, qwen_raw: float, small_assisted: float, small_raw: float) -> float:
    return (qwen_assisted - qwen_raw) - (small_assisted - small_raw)


def intervention_value(outcome_delta: float, intervention_burden: float) -> float | None:
    if intervention_burden == 0:
        return None
    return outcome_delta / intervention_burden


def minimum_required_scaffolding(points: list[OperatingPoint], noninferiority_margin: float = 0.0) -> OperatingPoint:
    safe = [p for p in points if p.hard_invariants_pass]
    if not safe:
        raise ValueError("no operating point passes hard invariants")
    best_success = max(p.semantic_success for p in safe)
    eligible = [p for p in safe if p.semantic_success >= best_success - noninferiority_margin]
    return min(eligible, key=lambda p: (p.silent_failure_rate, p.qwen_calls, p.model_calls, p.system_involvement, p.latency_ms, p.name))
