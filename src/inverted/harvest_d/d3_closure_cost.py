from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import math
from pathlib import Path


class CostClass(str, Enum):
    FREE = "FREE"
    NEAR_FREE = "NEAR_FREE"
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    VERY_EXPENSIVE = "VERY_EXPENSIVE"


@dataclass(frozen=True)
class CostProfile:
    profile_id: str
    residency_cliff_gib: float


@dataclass(frozen=True)
class CostObservation:
    system_only: bool = False
    installed_size_gib: float | None = None
    tiny_model: bool = False
    median_latency_s: float | None = None
    thinking: bool = False
    offload_observed: bool = False
    context_exhaustion_rate: float = 0.0


def load_cost_profile(path: str | Path) -> CostProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return CostProfile(
        profile_id=str(payload["profile_id"]),
        residency_cliff_gib=float(payload["residency_prior"]["cliff_gib"]),
    )


def classify_cost(observation: CostObservation, profile: CostProfile) -> CostClass:
    if observation.system_only:
        return CostClass.FREE

    size = observation.installed_size_gib
    latency = observation.median_latency_s

    if observation.offload_observed:
        return CostClass.VERY_EXPENSIVE
    if size is not None and size > profile.residency_cliff_gib:
        return CostClass.VERY_EXPENSIVE
    if observation.context_exhaustion_rate >= 0.25:
        return CostClass.VERY_EXPENSIVE
    if observation.thinking and (latency is None or latency >= 20.0):
        return CostClass.VERY_EXPENSIVE

    if observation.tiny_model and latency is not None and latency <= 2.0:
        return CostClass.NEAR_FREE
    if latency is not None and latency <= 2.0:
        return CostClass.FAST
    if latency is not None and latency > 20.0:
        return CostClass.VERY_EXPENSIVE

    # Under the current residency cliff, unknown or moderate local cost starts
    # at MEDIUM until calibration proves it is cheaper.
    return CostClass.MEDIUM


def sample_allowance(*, available_seconds: float, expected_call_seconds: float, hard_call_cap: int) -> int:
    if available_seconds < 0 or expected_call_seconds <= 0 or hard_call_cap < 0:
        raise ValueError("invalid cost budget inputs")
    return max(0, min(int(hard_call_cap), int(math.floor(available_seconds / expected_call_seconds))))


@dataclass
class CostBudgetState:
    max_physical_calls: int
    max_inference_seconds: float
    confirmation_reserved_calls: int
    confirmation_reserved_seconds: float
    physical_calls_used: int = 0
    inference_seconds_reserved: float = 0.0
    confirmation_calls_used: int = 0
    confirmation_seconds_reserved_used: float = 0.0
    system_only_operations: int = 0

    def __post_init__(self) -> None:
        if self.max_physical_calls < 0 or self.max_inference_seconds < 0:
            raise ValueError("budget ceilings must be non-negative")
        if not 0 <= self.confirmation_reserved_calls <= self.max_physical_calls:
            raise ValueError("invalid confirmation call reserve")
        if not 0 <= self.confirmation_reserved_seconds <= self.max_inference_seconds:
            raise ValueError("invalid confirmation time reserve")

    @property
    def development_calls_available(self) -> int:
        return max(
            0,
            self.max_physical_calls
            - self.confirmation_reserved_calls
            - (self.physical_calls_used - self.confirmation_calls_used),
        )

    @property
    def development_seconds_available(self) -> float:
        development_used = self.inference_seconds_reserved - self.confirmation_seconds_reserved_used
        return max(0.0, self.max_inference_seconds - self.confirmation_reserved_seconds - development_used)

    @property
    def confirmation_calls_available(self) -> int:
        return max(0, self.confirmation_reserved_calls - self.confirmation_calls_used)

    @property
    def confirmation_seconds_available(self) -> float:
        return max(0.0, self.confirmation_reserved_seconds - self.confirmation_seconds_reserved_used)

    def reserve_model_call(self, *, expected_seconds: float, confirmation: bool) -> None:
        if expected_seconds <= 0:
            raise ValueError("model call must reserve positive expected inference time")
        if self.physical_calls_used >= self.max_physical_calls:
            raise ValueError("physical-call runaway ceiling exhausted")

        if confirmation:
            if self.confirmation_calls_available < 1 or self.confirmation_seconds_available < expected_seconds:
                raise ValueError("protected confirmation budget exhausted")
            self.confirmation_calls_used += 1
            self.confirmation_seconds_reserved_used += expected_seconds
        else:
            if self.development_calls_available < 1 or self.development_seconds_available < expected_seconds:
                raise ValueError("development inference budget exhausted; confirmation reserve is protected")

        self.physical_calls_used += 1
        self.inference_seconds_reserved += expected_seconds

    def reconcile_actual_seconds(self, *, expected_seconds: float, actual_seconds: float, confirmation: bool) -> None:
        if expected_seconds <= 0 or actual_seconds < 0:
            raise ValueError("invalid inference-time reconciliation")
        delta = actual_seconds - expected_seconds
        self.inference_seconds_reserved += delta
        if confirmation:
            self.confirmation_seconds_reserved_used += delta
        if self.inference_seconds_reserved > self.max_inference_seconds + 1e-9:
            raise ValueError("actual inference time exceeded total budget")
        if self.confirmation_seconds_reserved_used > self.confirmation_reserved_seconds + 1e-9:
            raise ValueError("actual confirmation inference time exceeded protected reserve")

    def record_system_only_operation(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("system-only operation count must be non-negative")
        self.system_only_operations += count
