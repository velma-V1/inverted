from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Any, Iterable

from .core import Profile, profile_fingerprint
from .parameter_catalog import ProfileScreenCandidate, parameter_catalog, plan_profile_screen
from .runner import UniversalRunner
from .scheduler import AdaptiveScheduler
from .statistics import PairedBatch, PairedComparison, classify_comparison, paired_bootstrap_ci
from .tasks import TASK_FAMILIES


BEHAVIOR_SCREEN_AXES = (
    "top_p",
    "top_k",
    "min_p",
    "presence_penalty",
    "repeat_penalty",
    "typical_p",
    "repeat_last_n",
    "frequency_penalty",
)

SCREEN_SCOUT_FAMILIES = (
    "STRICT_TRANSFORMATION",
    "LOGIC_CONSTRAINTS",
    "CODING_GENERATION",
    "SYSTEM_GOVERNANCE",
)
SCREEN_CONFIRM_FAMILIES = tuple(
    family for family in TASK_FAMILIES if family not in SCREEN_SCOUT_FAMILIES
)
SCREEN_CONFIRM_CHECKPOINTS = (40, 80, 120)
SCREEN_PANEL_KEY = "parameter-screen-v1"
SCREEN_PARTITION_ATOMIC = 120


@dataclass(frozen=True)
class ParameterScreenDecision:
    axis_name: str
    axis_value: Any
    incumbent_fingerprint: str
    candidate_fingerprint: str
    scout_atomic: int
    scout_status: str
    scout_delta: float
    scout_ci_low: float
    scout_ci_high: float
    confirmation_atomic: int = 0
    confirmation_status: str = "NOT_RUN"
    confirmation_delta: float | None = None
    confirmation_ci_low: float | None = None
    confirmation_ci_high: float | None = None
    promoted: bool = False


@dataclass(frozen=True)
class ParameterScreenResult:
    incumbent: Profile
    decisions: tuple[ParameterScreenDecision, ...]
    physical_calls: int
    call_geometry: dict[str, int]


def plan_behavior_screen(
    incumbent: Profile, *, supports_thinking: bool = True,
) -> tuple[ProfileScreenCandidate, ...]:
    if not supports_thinking and incumbent.thinking:
        raise ValueError("direct-only screening requires a direct incumbent")
    allowed = set(BEHAVIOR_SCREEN_AXES)
    return tuple(
        candidate
        for candidate in plan_profile_screen(
            incumbent, supports_thinking=supports_thinking
        )
        if candidate.axis_name in allowed
    )


def parameter_screen_call_geometry(
    incumbent: Profile, *, supports_thinking: bool = True,
) -> dict[str, int]:
    candidates = plan_behavior_screen(
        incumbent, supports_thinking=supports_thinking
    )
    factor = 2 if incumbent.thinking else 1
    discovery_per_candidate = (
        len(SCREEN_SCOUT_FAMILIES) * (10 // 5) * 2 * factor
    )
    confirmation_per_candidate = (
        len(SCREEN_CONFIRM_FAMILIES) * (15 // 5) * 2 * factor
    )
    return {
        "candidate_count": len(candidates),
        "discovery_atomic_per_candidate": 40,
        "confirmation_atomic_max_per_candidate": 120,
        "discovery_physical_ceiling": len(candidates) * discovery_per_candidate,
        "worst_case_physical_ceiling": len(candidates)
        * (discovery_per_candidate + confirmation_per_candidate),
    }


def _stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _axis_values(axis_name: str) -> tuple[Any, ...]:
    by_name = {axis.name: axis for axis in parameter_catalog()}
    try:
        axis = by_name[axis_name]
    except KeyError as exc:
        raise ValueError(f"unknown parameter-screen axis: {axis_name}") from exc
    if axis_name not in BEHAVIOR_SCREEN_AXES or axis.strategy != "SWEEP":
        raise ValueError(f"axis is not eligible for behavior screening: {axis_name}")
    return axis.candidates


def _screen_batch_offsets(
    scheduler: AdaptiveScheduler,
    family: str,
    tasks_per_family: int,
) -> tuple[int, ...]:
    if tasks_per_family < 5 or tasks_per_family % 5:
        raise ValueError("screen tasks_per_family must be a positive multiple of five")
    batch_count = tasks_per_family // 5
    available = list(range(0, SCREEN_PARTITION_ATOMIC, 5))
    if batch_count > len(available):
        raise ValueError("screen task request exceeds partition")
    available.sort(
        key=lambda offset: (
            _stable_seed(
                scheduler.pool.seed,
                family,
                "screen",
                SCREEN_PANEL_KEY,
                offset,
            ),
            offset,
        )
    )
    return tuple(available[:batch_count])


def _screen_task_ids(
    scheduler: AdaptiveScheduler,
    family: str,
    tasks_per_family: int,
) -> tuple[str, ...]:
    partition = scheduler.partition_task_ids(
        family, "screen", SCREEN_PARTITION_ATOMIC
    )
    return tuple(
        task_id
        for offset in _screen_batch_offsets(
            scheduler, family, tasks_per_family
        )
        for task_id in partition[offset:offset + 5]
    )


def _pending_physical_calls(runner: UniversalRunner, trials: Iterable[Any]) -> int:
    completed = runner.store.completed_trial_ids()
    pending = tuple(trial for trial in trials if trial.trial_id not in completed)
    return sum(trial.physical_calls for trial in pending)


def _run_block(
    runner: UniversalRunner,
    scheduler: AdaptiveScheduler,
    *,
    families: tuple[str, ...],
    tasks_per_family: int,
    baseline: Profile,
    candidate: Profile,
    decision_reason: str,
    start_calls: int,
    max_additional_physical_calls: int,
) -> None:
    trials = tuple(
        trial
        for family in families
        for task_offset in _screen_batch_offsets(
            scheduler, family, tasks_per_family
        )
        for trial in scheduler.paired_trials(
            family=family,
            stage="screen",
            baseline=baseline,
            candidate=candidate,
            atomic_count=5,
            task_offset=task_offset,
            decision_reason=decision_reason,
        )
    )
    projected = _pending_physical_calls(runner, trials)
    used = runner.store.physical_calls_used() - start_calls
    if used + projected > max_additional_physical_calls:
        raise RuntimeError("parameter screen physical-call ceiling reached")
    runner.run_trials(trials)


def _profile_rows(
    runner: UniversalRunner,
    scheduler: AdaptiveScheduler,
    *,
    family: str,
    profile: Profile,
    tasks_per_family: int,
) -> tuple[dict[str, Any], ...]:
    selected = _screen_task_ids(scheduler, family, tasks_per_family)
    wanted = set(selected)
    fingerprint = profile_fingerprint(profile)
    rows = [
        row
        for row in runner.store.observation_rows()
        if row.get("stage") == "screen"
        and row.get("family") == family
        and row.get("task_id") in wanted
        and profile_fingerprint(Profile(**row["profile"])) == fingerprint
    ]
    by_task: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_task.setdefault(row["task_id"], row)
    ordered = tuple(by_task[task_id] for task_id in selected if task_id in by_task)
    if len(ordered) != tasks_per_family:
        raise RuntimeError(
            f"missing parameter-screen evidence for {family}/{fingerprint[:16]}: "
            f"{len(ordered)}/{tasks_per_family}"
        )
    return ordered


def _compare(
    runner: UniversalRunner,
    scheduler: AdaptiveScheduler,
    *,
    families: tuple[str, ...],
    tasks_per_family: int,
    baseline: Profile,
    candidate: Profile,
    bootstrap_seed: int,
) -> tuple[PairedComparison, str]:
    batches = []
    for family in families:
        baseline_rows = _profile_rows(
            runner,
            scheduler,
            family=family,
            profile=baseline,
            tasks_per_family=tasks_per_family,
        )
        candidate_rows = _profile_rows(
            runner,
            scheduler,
            family=family,
            profile=candidate,
            tasks_per_family=tasks_per_family,
        )
        batches.append(
            PairedBatch(
                family,
                tuple(float(row.get("semantic_quality", 0.0)) for row in baseline_rows),
                tuple(float(row.get("semantic_quality", 0.0)) for row in candidate_rows),
            )
        )
    comparison = paired_bootstrap_ci(tuple(batches), seed=bootstrap_seed)
    return comparison, classify_comparison(comparison)


def _decision(
    *,
    axis_name: str,
    axis_value: Any,
    baseline: Profile,
    candidate: Profile,
    scout: PairedComparison,
    scout_status: str,
    confirmation: PairedComparison | None,
    confirmation_status: str,
    confirmation_atomic: int,
) -> ParameterScreenDecision:
    return ParameterScreenDecision(
        axis_name=axis_name,
        axis_value=axis_value,
        incumbent_fingerprint=profile_fingerprint(baseline),
        candidate_fingerprint=profile_fingerprint(candidate),
        scout_atomic=scout.n_atomic,
        scout_status=scout_status,
        scout_delta=scout.delta,
        scout_ci_low=scout.ci_low,
        scout_ci_high=scout.ci_high,
        confirmation_atomic=confirmation_atomic,
        confirmation_status=confirmation_status,
        confirmation_delta=None if confirmation is None else confirmation.delta,
        confirmation_ci_low=None if confirmation is None else confirmation.ci_low,
        confirmation_ci_high=None if confirmation is None else confirmation.ci_high,
    )


def screen_profile_parameters(
    runner: UniversalRunner,
    scheduler: AdaptiveScheduler,
    incumbent: Profile,
    *,
    supports_thinking: bool = True,
    axis_names: tuple[str, ...] | None = None,
    max_additional_physical_calls: int | None = None,
    bootstrap_seed: int = 20260908,
) -> ParameterScreenResult:
    if not supports_thinking and incumbent.thinking:
        raise ValueError("direct-only screening requires a direct incumbent")
    axes = BEHAVIOR_SCREEN_AXES if axis_names is None else tuple(axis_names)
    if not axes or len(set(axes)) != len(axes):
        raise ValueError("parameter screen requires unique behavior axes")
    for axis_name in axes:
        _axis_values(axis_name)

    geometry = parameter_screen_call_geometry(
        incumbent, supports_thinking=supports_thinking
    )
    if max_additional_physical_calls is None:
        max_additional_physical_calls = geometry["worst_case_physical_ceiling"]
    max_additional_physical_calls = int(max_additional_physical_calls)
    if max_additional_physical_calls < 0:
        raise ValueError("screen physical-call ceiling must be non-negative")

    start_calls = runner.store.physical_calls_used()
    current = incumbent
    decisions: list[ParameterScreenDecision] = []

    for axis_index, axis_name in enumerate(axes):
        axis_base = current
        axis_results: list[tuple[ParameterScreenDecision, Profile]] = []
        for value_index, axis_value in enumerate(_axis_values(axis_name)):
            if axis_value == getattr(axis_base, axis_name):
                continue
            candidate = replace(axis_base, **{axis_name: axis_value})
            scout_seed = _stable_seed(
                bootstrap_seed, axis_index, axis_name, value_index, "scout"
            )
            _run_block(
                runner,
                scheduler,
                families=SCREEN_SCOUT_FAMILIES,
                tasks_per_family=10,
                baseline=axis_base,
                candidate=candidate,
                decision_reason=f"PARAMETER_SCOUT:{axis_name}",
                start_calls=start_calls,
                max_additional_physical_calls=max_additional_physical_calls,
            )
            scout, scout_status = _compare(
                runner,
                scheduler,
                families=SCREEN_SCOUT_FAMILIES,
                tasks_per_family=10,
                baseline=axis_base,
                candidate=candidate,
                bootstrap_seed=scout_seed,
            )

            confirmation: PairedComparison | None = None
            confirmation_status = "NOT_RUN"
            confirmation_atomic = 0
            if scout_status in {"SUPERIOR", "CLOSE"}:
                for confirmation_atomic in SCREEN_CONFIRM_CHECKPOINTS:
                    tasks_per_family = confirmation_atomic // len(SCREEN_CONFIRM_FAMILIES)
                    _run_block(
                        runner,
                        scheduler,
                        families=SCREEN_CONFIRM_FAMILIES,
                        tasks_per_family=tasks_per_family,
                        baseline=axis_base,
                        candidate=candidate,
                        decision_reason=f"PARAMETER_CONFIRM:{axis_name}",
                        start_calls=start_calls,
                        max_additional_physical_calls=max_additional_physical_calls,
                    )
                    confirmation, confirmation_status = _compare(
                        runner,
                        scheduler,
                        families=SCREEN_CONFIRM_FAMILIES,
                        tasks_per_family=tasks_per_family,
                        baseline=axis_base,
                        candidate=candidate,
                        bootstrap_seed=_stable_seed(
                            bootstrap_seed,
                            axis_index,
                            axis_name,
                            value_index,
                            "confirm",
                            confirmation_atomic,
                        ),
                    )
                    if confirmation_status != "CLOSE":
                        break

            axis_results.append(
                (
                    _decision(
                        axis_name=axis_name,
                        axis_value=axis_value,
                        baseline=axis_base,
                        candidate=candidate,
                        scout=scout,
                        scout_status=scout_status,
                        confirmation=confirmation,
                        confirmation_status=confirmation_status,
                        confirmation_atomic=confirmation_atomic,
                    ),
                    candidate,
                )
            )

        eligible = [
            (index, decision, profile)
            for index, (decision, profile) in enumerate(axis_results)
            if decision.confirmation_status == "SUPERIOR"
        ]
        winner_index: int | None = None
        if eligible:
            winner_index, _, winner_profile = sorted(
                eligible,
                key=lambda item: (
                    -float(item[1].confirmation_ci_low),
                    -float(item[1].confirmation_delta),
                    repr(item[1].axis_value),
                ),
            )[0]
            current = winner_profile

        for index, (decision, _) in enumerate(axis_results):
            decisions.append(
                replace(decision, promoted=(winner_index is not None and index == winner_index))
            )

    physical_calls = runner.store.physical_calls_used() - start_calls
    return ParameterScreenResult(
        incumbent=current,
        decisions=tuple(decisions),
        physical_calls=physical_calls,
        call_geometry=geometry,
    )
