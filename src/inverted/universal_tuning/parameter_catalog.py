"""Exhaustive Test1B-v3 inference-control catalog and safe screen planner.

Every currently known control is classified. Only controls whose values are safe to
compare without hardware or task-specific discovery enter the automatic one-factor
screen. This prevents silent gaps without turning the campaign into a Cartesian grid.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .core import UNRESTRICTED_THINKING, Profile


_STRATEGIES = frozenset({
    "SWEEP",
    "CONDITIONAL",
    "TASK_BOUND",
    "RUNTIME_DISCOVERY",
    "SUPPORT_PROBE",
    "CAPABILITY_PROBE",
    "SEED_REPLICATION",
})
_CONTROL_PATHS = frozenset({"PROFILE", "INFERENCE_ARGUMENT", "CAPABILITY"})


@dataclass(frozen=True)
class ParameterAxis:
    """One known inference/runtime control and how Test1B-v3 must characterize it."""

    name: str
    category: str
    strategy: str
    control_path: str
    candidates: tuple[Any, ...]
    rationale: str

    def __post_init__(self) -> None:
        for label, value in (
            ("name", self.name),
            ("category", self.category),
            ("strategy", self.strategy),
            ("control_path", self.control_path),
            ("rationale", self.rationale),
        ):
            if not isinstance(value, str) or not value.strip():
                raise TypeError(f"{label} must be a non-blank string")
        if self.strategy not in _STRATEGIES:
            raise ValueError("unknown parameter strategy")
        if self.control_path not in _CONTROL_PATHS:
            raise ValueError("unknown parameter control_path")
        candidates = tuple(self.candidates)
        if self.strategy == "SWEEP" and not candidates:
            raise ValueError("SWEEP axes require candidates")
        if len({repr(item) for item in candidates}) != len(candidates):
            raise ValueError("parameter candidates must be unique")
        object.__setattr__(self, "candidates", candidates)


@dataclass(frozen=True)
class ProfileScreenCandidate:
    """One one-factor-at-a-time profile candidate against an incumbent profile."""

    candidate_id: str
    axis_name: str
    axis_value: Any
    category: str
    profile: Profile

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise TypeError("candidate_id must be a non-blank string")
        if not isinstance(self.axis_name, str) or not self.axis_name.strip():
            raise TypeError("axis_name must be a non-blank string")
        if not isinstance(self.category, str) or not self.category.strip():
            raise TypeError("category must be a non-blank string")
        if not isinstance(self.profile, Profile):
            raise TypeError("profile must be Profile")


def _axis(
    name: str,
    category: str,
    strategy: str,
    control_path: str = "PROFILE",
    candidates: tuple[Any, ...] = (),
    rationale: str = "Explicitly classified Test1B-v3 control.",
) -> ParameterAxis:
    return ParameterAxis(
        name=name,
        category=category,
        strategy=strategy,
        control_path=control_path,
        candidates=candidates,
        rationale=rationale,
    )


def parameter_catalog() -> tuple[ParameterAxis, ...]:
    """Return the complete known Test1B-v3 inference-control surface.

    Hardware-dependent controls are intentionally marked ``RUNTIME_DISCOVERY`` so
    their legal/sensible values are derived from the frozen machine/runtime manifest
    instead of guessed globally. Request/observability controls are support probes,
    and task-bound controls are varied only on cases where they are causally relevant.
    """

    return (
        _axis(
            "thinking_budget", "REASONING", "SWEEP",
            candidates=(
                0,
                256,
                512,
                1024,
                2048,
                4096,
                8192,
                16384,
                UNRESTRICTED_THINKING,
            ),
            rationale=(
                "Measure direct, minimum-effective, saturation, overthinking, and a "
                "true unrestricted-thinking comparator."
            ),
        ),
        _axis(
            "temperature", "SAMPLER", "SWEEP",
            candidates=(0.0, 0.1, 0.2, 0.35, 0.5, 0.7, 0.9, 1.1),
            rationale="Approved broad discovery screen before local refinement around survivors.",
        ),
        _axis(
            "top_p", "SAMPLER", "SWEEP",
            candidates=(0.7, 0.8, 0.9, 0.95, 1.0),
            rationale="Measure nucleus-sampling sensitivity around common useful operating values.",
        ),
        _axis(
            "top_k", "SAMPLER", "SWEEP",
            candidates=(10, 20, 40, 80, 160),
            rationale="Measure candidate-pool restriction without crossing it with every sampler knob.",
        ),
        _axis(
            "min_p", "SAMPLER", "SWEEP",
            candidates=(0.0, 0.01, 0.02, 0.05, 0.1),
            rationale="Measure low-probability token pruning sensitivity.",
        ),
        _axis(
            "presence_penalty", "REPETITION", "SWEEP",
            candidates=(0.0, 0.25, 0.5, 1.0, 1.5),
            rationale="Measure novelty pressure and repetition-related reliability effects.",
        ),
        _axis(
            "repeat_penalty", "REPETITION", "SWEEP",
            candidates=(1.0, 1.05, 1.1, 1.15, 1.2),
            rationale="Measure direct repetition suppression and degradation from over-penalization.",
        ),
        _axis(
            "typical_p", "SAMPLER", "SWEEP",
            candidates=(0.7, 0.8, 0.9, 0.95, 1.0),
            rationale="Measure typical-sampling sensitivity separately from top-p/min-p.",
        ),
        _axis(
            "repeat_last_n", "REPETITION", "SWEEP",
            candidates=(0, 64, 128, 256, 512),
            rationale="Measure the repetition-history window independently of penalty strength.",
        ),
        _axis(
            "frequency_penalty", "REPETITION", "SWEEP",
            candidates=(0.0, 0.25, 0.5, 1.0, 1.5),
            rationale="Measure frequency-sensitive repetition control independently.",
        ),
        _axis(
            "num_keep", "CONTEXT", "CONDITIONAL",
            rationale="Only meaningful in context-pressure/shift cases; global variation would confound normal tasks.",
        ),
        _axis(
            "num_ctx", "RUNTIME", "RUNTIME_DISCOVERY",
            rationale="Legal/effective context sizes depend on model artifact, memory budget, and frozen runtime.",
        ),
        _axis(
            "num_batch", "RUNTIME", "RUNTIME_DISCOVERY",
            rationale="Throughput/memory operating values must be derived from the actual hardware manifest.",
        ),
        _axis(
            "num_gpu", "RUNTIME", "RUNTIME_DISCOVERY",
            rationale="GPU-layer placement is hardware/model-size dependent and must not use guessed global values.",
        ),
        _axis(
            "main_gpu", "RUNTIME", "RUNTIME_DISCOVERY",
            rationale="Valid GPU identities come from the frozen runtime hardware inventory.",
        ),
        _axis(
            "use_mmap", "RUNTIME", "RUNTIME_DISCOVERY",
            candidates=(False, True),
            rationale="Measure only after runtime support and model-loading conditions are established.",
        ),
        _axis(
            "num_thread", "RUNTIME", "RUNTIME_DISCOVERY",
            rationale="Thread candidates must be derived from the host CPU topology and contention policy.",
        ),
        _axis(
            "draft_num_predict", "RUNTIME", "RUNTIME_DISCOVERY",
            rationale="Speculative/draft behavior is runtime/model dependent and requires capability discovery first.",
        ),
        _axis(
            "final_max_tokens", "COMPLETION", "SWEEP",
            candidates=(192, 384, 768, 1024, 1536, 2048),
            rationale="Find the minimum completion allowance that avoids truncation without paying needless latency.",
        ),
        _axis(
            "stop", "COMPLETION", "TASK_BOUND",
            rationale="Stop sequences are task/contract semantics, not a globally meaningful numeric sweep.",
        ),
        _axis(
            "truncate", "REQUEST", "SUPPORT_PROBE",
            candidates=(False, True),
            rationale="Probe runtime support and characterize only on deliberate context-overflow cases.",
        ),
        _axis(
            "shift", "REQUEST", "SUPPORT_PROBE",
            candidates=(False, True),
            rationale="Probe runtime support and isolate behavior under deliberate context-shift pressure.",
        ),
        _axis(
            "logprobs", "OBSERVABILITY", "SUPPORT_PROBE",
            candidates=(False, True),
            rationale="Observability control; validate support/cost without treating it as a quality optimizer.",
        ),
        _axis(
            "top_logprobs", "OBSERVABILITY", "SUPPORT_PROBE",
            candidates=(1, 3, 5, 10),
            rationale="Dependent observability depth; only meaningful after logprobs support is established.",
        ),
        _axis(
            "inference_seed", "STOCHASTICITY", "SEED_REPLICATION", "INFERENCE_ARGUMENT",
            candidates=(11, 29, 47, 71, 101),
            rationale="Replication axis for separating stable effects from seed-specific luck.",
        ),
        _axis(
            "native_thinking_effort", "REASONING", "CAPABILITY_PROBE", "CAPABILITY",
            candidates=("low", "medium", "high"),
            rationale="Current Ollama can expose effort levels on supported models; probe support separately from token-budget throttling.",
        ),
    )


def plan_profile_screen(
    incumbent: Profile,
    *,
    supports_thinking: bool,
) -> tuple[ProfileScreenCandidate, ...]:
    """Plan a safe one-factor screen against ``incumbent``.

    The planner intentionally excludes runtime-discovery, request-probe, conditional,
    task-bound, seed, and capability-only controls. Those controls remain explicit in
    the catalog and get dedicated experiments once their prerequisites are known.
    """

    if not isinstance(incumbent, Profile):
        raise TypeError("incumbent must be Profile")
    if type(supports_thinking) is not bool:
        raise TypeError("supports_thinking must be boolean")
    if incumbent.thinking and not supports_thinking:
        raise ValueError("incumbent uses thinking but model does not support thinking")

    planned: list[ProfileScreenCandidate] = []
    for axis in parameter_catalog():
        if axis.control_path != "PROFILE" or axis.strategy != "SWEEP":
            continue
        if axis.name == "thinking_budget" and not supports_thinking:
            continue
        current = getattr(incumbent, axis.name)
        for index, value in enumerate(axis.candidates):
            if value == current:
                continue
            candidate_profile = replace(incumbent, **{axis.name: value})
            planned.append(ProfileScreenCandidate(
                candidate_id=f"profile-screen:{axis.name}:{index:02d}",
                axis_name=axis.name,
                axis_value=value,
                category=axis.category,
                profile=candidate_profile,
            ))
    return tuple(planned)
