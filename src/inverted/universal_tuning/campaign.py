from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from .core import Profile
from .qwen_ollama import QwenOllamaAdapter
from .report import write_campaign_report
from .runner import ProgressReporter, UniversalRunner
from .scheduler import (
    AdaptiveScheduler, ModeDecision, ModelMetadata, TemperatureSurface,
    discover_temperature_surface, evaluate_holdout,
    select_interaction_profile, select_minimum_budget, select_mode,
)
from .statistics import BOOTSTRAP_ITERATIONS, CHECKPOINTS, CONFIDENCE_LEVEL
from .tasks import TASK_FAMILIES, TaskPool, build_qwen_task_pool, freeze_task_pool


REFINEMENT_STEPS = (0.10, 0.05, 0.02, 0.01, 0.001)


@dataclass(frozen=True)
class ExperimentSpec:
    families: tuple[str, ...] = TASK_FAMILIES
    hard_call_ceiling: int = 15840
    coarse_temperatures: tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0, 1.2)
    budget_candidates: tuple[int, ...] = (256, 512, 1024, 2048)
    checkpoints: tuple[int, ...] = CHECKPOINTS
    bootstrap_seed: int = 20260907
    minimum_useful_effect: float = 0.05
    noninferiority_margin: float = -0.02
    acceptable_semantic_floor: float = 0.90
    task_seed: int = 20260907
    tasks_per_family: int = 600


@dataclass(frozen=True)
class CampaignResult:
    status: str
    policy: dict[str, Any]
    physical_calls: int
    observation_count: int
    call_geometry: dict[str, int]


def call_geometry(family_count: int) -> dict[str, int]:
    families = max(1, int(family_count))
    # Per family: direct/thinking gate + fresh holdout at 40 atomic tasks.
    minimum = 48 * families
    # Expected full thinking path at 40 tasks with one temperature refinement pair.
    expected = 312 * families
    # Worst case: every comparison expands to 120 and all ten refinement points run.
    worst = 1320 * families
    return {"minimum": minimum, "expected": expected, "worst_case": worst}


def _profile_key(profile: Profile) -> tuple[int, float]:
    return int(profile.thinking_budget), round(float(profile.temperature), 6)

def _rows_for(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, family: str, stage: str,
    profile: Profile, atomic_count: int,
) -> tuple[dict[str, Any], ...]:
    wanted = set(scheduler.partition_task_ids(family, stage, 120)[:atomic_count])
    key = _profile_key(profile)
    rows = [
        row for row in runner.store.observation_rows()
        if row.get("family") == family and row.get("stage") == stage
        and row.get("task_id") in wanted
        and _profile_key(Profile(**row["profile"])) == key
    ]
    by_task: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_task.setdefault(row["task_id"], row)
    ordered = tuple(by_task[task_id] for task_id in sorted(wanted) if task_id in by_task)
    if len(ordered) != atomic_count:
        raise RuntimeError(
            f"missing evidence for {family}/{stage}/{key}: {len(ordered)}/{atomic_count}"
        )
    return ordered


def _vector(rows: Iterable[Mapping[str, Any]]) -> tuple[float, ...]:
    return tuple(float(row.get("semantic_quality", 0.0)) for row in rows)


def _contract_rate(rows: Iterable[Mapping[str, Any]]) -> float:
    values = tuple(bool(row.get("contract_pass")) for row in rows)
    return sum(values) / len(values) if values else 0.0


def _completion_rate(rows: Iterable[Mapping[str, Any]]) -> float:
    values = tuple(bool(row.get("completed")) for row in rows)
    return sum(values) / len(values) if values else 0.0


def _semantic_pass_rate(rows: Iterable[Mapping[str, Any]]) -> float:
    values = tuple(bool(row.get("semantic_pass")) for row in rows)
    return sum(values) / len(values) if values else 0.0


def _wilson_interval(rows: Iterable[Mapping[str, Any]]) -> tuple[float, float]:
    values = tuple(bool(row.get("semantic_pass")) for row in rows)
    if not values:
        return 0.0, 0.0
    n = len(values)
    p_hat = sum(values) / n
    z = 1.959963984540054
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _row_metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    values = tuple(rows)
    thinking = sorted(int(row.get("thinking_tokens", 0)) for row in values)
    failures: dict[str, int] = {}
    for row in values:
        for failure in row.get("failure_classes", ()): failures[failure] = failures.get(failure, 0) + 1
    p95 = thinking[max(0, math.ceil(0.95 * len(thinking)) - 1)] if thinking else 0
    return {
        "semantic_accuracy": _semantic_pass_rate(values),
        "semantic_quality_mean": sum(_vector(values)) / len(values) if values else 0.0,
        "semantic_ci95": list(_wilson_interval(values)),
        "contract_accuracy": _contract_rate(values),
        "completion_reliability": _completion_rate(values),
        "mean_latency_s": sum(float(row.get("latency_s", 0.0)) for row in values) / len(values) if values else 0.0,
        "mean_output_tokens": sum(int(row.get("output_tokens", 0)) for row in values) / len(values) if values else 0.0,
        "thinking_tokens_mean": sum(thinking) / len(thinking) if thinking else 0.0,
        "thinking_tokens_p95": p95,
        "thinking_tokens_max": max(thinking) if thinking else 0,
        "failure_classes": failures,
    }

def _run_profiles(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, *, family: str, stage: str,
    profiles: tuple[Profile, ...], atomic_count: int, reason: str,
) -> None:
    if not profiles:
        return
    if len(profiles) == 1:
        raise ValueError("profile comparison requires at least two profiles")
    baseline = profiles[0]
    for candidate in profiles[1:]:
        trials = scheduler.paired_trials(
            family=family, stage=stage, baseline=baseline, candidate=candidate,
            atomic_count=atomic_count, task_offset=0, decision_reason=reason,
        )
        runner.run_trials(trials)


def _mode_gate(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, spec: ExperimentSpec,
    family: str, direct: Profile, thinking: Profile,
):
    last = None
    for count in spec.checkpoints:
        _run_profiles(
            runner, scheduler, family=family, stage="gate",
            profiles=(direct, thinking), atomic_count=count,
            reason="ESTABLISH_DIRECT_VS_THINKING",
        )
        direct_rows = _rows_for(runner, scheduler, family, "gate", direct, count)
        thinking_rows = _rows_for(runner, scheduler, family, "gate", thinking, count)
        last = select_mode(
            _vector(direct_rows), _vector(thinking_rows),
            direct_contract_rate=_contract_rate(direct_rows),
            thinking_contract_rate=_contract_rate(thinking_rows),
            direct_completion_rate=_completion_rate(direct_rows),
            thinking_completion_rate=_completion_rate(thinking_rows),
            bootstrap_seed=spec.bootstrap_seed,
            acceptable_semantic_floor=spec.acceptable_semantic_floor,
            minimum_useful_effect=spec.minimum_useful_effect,
            noninferiority_margin=spec.noninferiority_margin,
            final_checkpoint=spec.checkpoints[-1],
        )
        if last.status != "EVIDENCE_CLOSE":
            return last, count
    return last, spec.checkpoints[-1]

def _budget_search(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, spec: ExperimentSpec,
    family: str, temperature: float,
):
    profiles = tuple(Profile(budget, temperature) for budget in spec.budget_candidates)
    decision = None
    count = spec.checkpoints[0]
    for count in spec.checkpoints:
        _run_profiles(
            runner, scheduler, family=family, stage="budget", profiles=profiles,
            atomic_count=count, reason="LOCALIZE_MINIMUM_USEFUL_BUDGET",
        )
        outcomes = {
            profile.thinking_budget: _vector(
                _rows_for(runner, scheduler, family, "budget", profile, count)
            )
            for profile in profiles
        }
        decision = select_minimum_budget(
            outcomes, bootstrap_seed=spec.bootstrap_seed,
            noninferiority_margin=spec.noninferiority_margin,
        )
        if decision.status != "EVIDENCE_CLOSE":
            break
    assert decision is not None
    selected = Profile(decision.selected_budget, temperature)
    viable = tuple(
        budget for budget in sorted(spec.budget_candidates)
        if budget not in decision.inferior_budgets
    )
    if selected.thinking_budget not in viable:
        viable = (selected.thinking_budget,) + viable
    return decision, selected, viable, count


def _coarse_temperature_profiles(spec: ExperimentSpec, budget: int) -> tuple[Profile, ...]:
    values = tuple(sorted({round(float(value), 6) for value in spec.coarse_temperatures}))
    if len(values) < 2:
        raise ValueError("temperature search requires at least two coarse points")
    return tuple(Profile(budget, value) for value in values)

def _temperature_outcomes(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, family: str,
    profiles: Iterable[Profile], atomic_count: int,
) -> dict[float, tuple[float, ...]]:
    return {
        round(profile.temperature, 6): _vector(
            _rows_for(runner, scheduler, family, "temperature", profile, atomic_count)
        )
        for profile in profiles
    }


def _resolve_temperature_set(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, spec: ExperimentSpec,
    family: str, profiles: tuple[Profile, ...], start_count: int,
) -> tuple[TemperatureSurface, int]:
    checkpoints = tuple(count for count in spec.checkpoints if count >= start_count)
    surface = None
    used_count = start_count
    for used_count in checkpoints:
        _run_profiles(
            runner, scheduler, family=family, stage="temperature", profiles=profiles,
            atomic_count=used_count, reason="RESOLVE_TEMPERATURE_SURFACE",
        )
        surface = discover_temperature_surface(
            _temperature_outcomes(runner, scheduler, family, profiles, used_count),
            bootstrap_seed=spec.bootstrap_seed,
            minimum_useful_effect=spec.minimum_useful_effect,
            noninferiority_margin=spec.noninferiority_margin,
        )
        if surface.kind != "EVIDENCE_CLOSE":
            return surface, used_count
    assert surface is not None
    return surface, used_count


def _temperature_search(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, spec: ExperimentSpec,
    family: str, budget: int,
):
    tested = {profile.temperature for profile in _coarse_temperature_profiles(spec, budget)}
    profiles = tuple(Profile(budget, temp) for temp in sorted(tested))
    surface, count = _resolve_temperature_set(
        runner, scheduler, spec, family, profiles, spec.checkpoints[0]
    )
    if surface.kind in {"PLATEAU", "OPTIMUM"}:
        return surface, profiles, count
    center = surface.recommended
    if center is None:
        center = min(tested, key=lambda x: abs(x - 0.8))
    for step in REFINEMENT_STEPS:
        additions = {
            round(max(0.1, center - step), 6),
            round(min(1.5, center + step), 6),
        } - tested
        if additions:
            tested.update(additions)
            profiles = tuple(Profile(budget, temp) for temp in sorted(tested))
            surface, count = _resolve_temperature_set(
                runner, scheduler, spec, family, profiles, count
            )
        if surface.kind in {"PLATEAU", "OPTIMUM"}:
            return surface, profiles, count
        if surface.recommended is not None:
            center = surface.recommended
    return surface, profiles, count


def _temperature_candidates_for_interaction(
    surface: TemperatureSurface, tested_profiles: Iterable[Profile], budget: int,
) -> tuple[float, ...]:
    tested = sorted({round(profile.temperature, 6) for profile in tested_profiles})
    if surface.kind == "OPTIMUM" and surface.optimum is not None:
        ordered = sorted(tested, key=lambda t: (abs(t - surface.optimum), t))
        return tuple(ordered[:2])
    midpoint = (surface.lower + surface.upper) / 2.0
    inside = [t for t in tested if surface.lower - 1e-9 <= t <= surface.upper + 1e-9]
    ordered = sorted(inside or tested, key=lambda t: (abs(t - midpoint), t))
    return tuple(ordered[:2])


def _budget_candidates_for_interaction(
    selected_budget: int, viable_budgets: Iterable[int]
) -> tuple[int, ...]:
    values = sorted(set(int(value) for value in viable_budgets))
    ordered = sorted(values, key=lambda value: (abs(value - selected_budget), value))
    if selected_budget in ordered:
        ordered.remove(selected_budget)
    return tuple([selected_budget, *ordered][:2])

def _interaction_search(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, spec: ExperimentSpec,
    family: str, direct: Profile, selected_budget: int, viable_budgets: Iterable[int],
    surface: TemperatureSurface, tested_profiles: Iterable[Profile],
):
    budgets = _budget_candidates_for_interaction(selected_budget, viable_budgets)
    temperatures = _temperature_candidates_for_interaction(surface, tested_profiles, selected_budget)
    candidates = tuple(
        Profile(budget, temp) for budget in budgets for temp in temperatures
    )
    profiles = (direct, *candidates)
    decision = None
    used_count = spec.checkpoints[0]
    for used_count in spec.checkpoints:
        _run_profiles(
            runner, scheduler, family=family, stage="interaction", profiles=profiles,
            atomic_count=used_count, reason="RESOLVE_BUDGET_TEMPERATURE_INTERACTION",
        )
        outcomes = {
            profile: _vector(
                _rows_for(runner, scheduler, family, "interaction", profile, used_count)
            )
            for profile in profiles
        }
        decision = select_interaction_profile(outcomes, bootstrap_seed=spec.bootstrap_seed)
        if decision.status != "INTERACTION_CLOSE":
            break
    assert decision is not None
    return decision, profiles, used_count


def _holdout(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, spec: ExperimentSpec,
    family: str, selected: Profile, alternates: tuple[Profile, ...],
):
    unique_alternates = tuple(dict.fromkeys(
        profile for profile in alternates if profile != selected
    ))
    if not unique_alternates:
        raise ValueError("holdout requires at least one serious alternative")
    decisions: dict[Profile, Any] = {}
    used_count = spec.checkpoints[0]
    for used_count in spec.checkpoints:
        _run_profiles(
            runner, scheduler, family=family, stage="holdout",
            profiles=(selected, *unique_alternates), atomic_count=used_count,
            reason="CERTIFY_FRESH_HOLDOUT",
        )
        selected_rows = _rows_for(
            runner, scheduler, family, "holdout", selected, used_count
        )
        decisions = {}
        all_certified = True
        for alternate in unique_alternates:
            alternate_rows = _rows_for(
                runner, scheduler, family, "holdout", alternate, used_count
            )
            decision = evaluate_holdout(
                _vector(alternate_rows), _vector(selected_rows),
                bootstrap_seed=spec.bootstrap_seed,
            )
            decisions[alternate] = decision
            all_certified = all_certified and decision.certified
        if all_certified:
            break
    alternate_rows = {
        profile: _rows_for(runner, scheduler, family, "holdout", profile, used_count)
        for profile in unique_alternates
    }
    return decisions, selected_rows, alternate_rows, used_count


def _profile_payload(profile: Profile) -> dict[str, Any]:
    return asdict(profile)


def _surface_payload(surface: TemperatureSurface | None) -> dict[str, Any] | None:
    return None if surface is None else asdict(surface)


def _family_policy(
    runner: UniversalRunner, scheduler: AdaptiveScheduler, spec: ExperimentSpec,
    family: str, metadata: ModelMetadata,
) -> dict[str, Any]:
    direct = Profile(0, metadata.direct_temperature)
    anchor_temp = (
        metadata.coding_thinking_temperature
        if family in {"CODING_GENERATION", "DEBUGGING_REVIEW"}
        else metadata.general_thinking_temperature
    )
    thinking_anchor = Profile(metadata.gate_thinking_budget, anchor_temp)
    gate, gate_atomic = _mode_gate(
        runner, scheduler, spec, family, direct, thinking_anchor
    )
    gate_direct = _rows_for(runner, scheduler, family, "gate", direct, gate_atomic)
    gate_thinking = _rows_for(runner, scheduler, family, "gate", thinking_anchor, gate_atomic)
    base = {
        "mode": gate.mode, "status": gate.status, "gate_atomic": gate_atomic,
        "direct_semantic": sum(_vector(gate_direct)) / gate_atomic,
        "thinking_semantic": sum(_vector(gate_thinking)) / gate_atomic,
        "direct_vs_thinking_delta": (
            sum(_vector(gate_thinking)) - sum(_vector(gate_direct))
        ) / gate_atomic,
        "gate_direct_metrics": _row_metrics(gate_direct),
        "gate_thinking_metrics": _row_metrics(gate_thinking),
        "minimum_useful_budget": None, "temperature": None,
        "interaction": None, "selected_profile": None, "holdout_atomic": 0,
        "gate_diagnostic_used": False,
    }
    if gate.mode == "unresolved" and gate.status == "CAPABILITY_UNRESOLVED":
        diagnostic = Profile(metadata.diagnostic_budget, anchor_temp)
        if diagnostic != thinking_anchor:
            _run_profiles(
                runner, scheduler, family=family, stage="gate",
                profiles=(direct, diagnostic), atomic_count=spec.checkpoints[-1],
                reason="CAPABILITY_HIGH_BUDGET_DIAGNOSTIC",
            )
            diagnostic_rows = _rows_for(
                runner, scheduler, family, "gate", diagnostic, spec.checkpoints[-1]
            )
            base["gate_diagnostic_used"] = True
            base["diagnostic_semantic"] = sum(_vector(diagnostic_rows)) / len(diagnostic_rows)
            if base["diagnostic_semantic"] >= spec.acceptable_semantic_floor:
                gate = ModeDecision("thinking", "DIAGNOSTIC_BUDGET_RECOVERY", "budget")
                base["mode"] = gate.mode
                base["status"] = gate.status
    if gate.mode == "unresolved":
        return base
    if gate.mode == "direct":
        holdout, selected_rows, alternate_rows, holdout_atomic = _holdout(
            runner, scheduler, spec, family, direct, (thinking_anchor,)
        )
        selected_metrics = _row_metrics(selected_rows)
        final_status = gate.status
        if selected_metrics["semantic_accuracy"] < spec.acceptable_semantic_floor:
            final_status = "CAPABILITY_UNRESOLVED"
        base.update({
            "status": final_status,
            "selected_profile": _profile_payload(direct),
            "holdout_atomic": holdout_atomic,
            "holdout_status": ",".join(sorted({d.status for d in holdout.values()})),
            "holdout_comparisons": {
                str(_profile_key(profile)): asdict(decision)
                for profile, decision in holdout.items()
            },
            "selected_metrics": selected_metrics,
            "holdout_semantic": selected_metrics["semantic_quality_mean"],
            "holdout_contract": selected_metrics["contract_accuracy"],
        })
        return base

    budget_decision, selected_budget_profile, viable_budgets, budget_atomic = _budget_search(
        runner, scheduler, spec, family, anchor_temp
    )
    surface, tested_temperature_profiles, temperature_atomic = _temperature_search(
        runner, scheduler, spec, family, selected_budget_profile.thinking_budget
    )
    interaction, interaction_profiles, interaction_atomic = _interaction_search(
        runner, scheduler, spec, family, direct,
        selected_budget_profile.thinking_budget, viable_budgets,
        surface, tested_temperature_profiles,
    )
    selected = interaction.profile
    preinteraction = Profile(
        selected_budget_profile.thinking_budget,
        surface.optimum if surface.optimum is not None else float(surface.recommended),
    )
    interaction_rates = {
        profile: sum(_vector(_rows_for(
            runner, scheduler, family, "interaction", profile, interaction_atomic
        ))) / interaction_atomic
        for profile in interaction_profiles
    }
    ranked_alternatives = sorted(
        (profile for profile in interaction_profiles if profile != selected),
        key=lambda profile: (-interaction_rates[profile], profile.thinking_budget, profile.temperature),
    )
    serious = ranked_alternatives[0] if ranked_alternatives else preinteraction
    alternates = tuple(dict.fromkeys((direct, serious))) if selected != direct else (serious,)
    holdout, selected_rows, alternate_rows, holdout_atomic = _holdout(
        runner, scheduler, spec, family, selected, alternates
    )
    selected_metrics = _row_metrics(selected_rows)
    final_mode = "thinking" if selected.thinking else "direct"
    if selected_metrics["semantic_accuracy"] < spec.acceptable_semantic_floor:
        final_status = "CAPABILITY_UNRESOLVED"
    elif not selected.thinking:
        final_status = "DIRECT_SUFFICIENT"
    elif surface.kind == "PLATEAU":
        final_status = "PLATEAU"
    else:
        final_status = "VALIDATED"
    temperature_stop_reason = {
        "PLATEAU": "validated_plateau_no_finer_semantic_gain",
        "OPTIMUM": "semantic_optimum_resolved",
        "UNRESOLVED_POINT": "maximum_resolution_without_supported_point_optimum",
        "EVIDENCE_CLOSE": "maximum_evidence_reached",
    }.get(surface.kind, "decision_settled")
    base.update({
        "mode": final_mode,
        "status": final_status,
        "minimum_useful_budget": budget_decision.selected_budget,
        "budget_reference": budget_decision.reference_budget,
        "budget_atomic": budget_atomic,
        "temperature": _surface_payload(surface),
        "temperature_atomic": temperature_atomic,
        "temperature_stop_reason": temperature_stop_reason,
        "interaction": {
            **asdict(interaction),
            "profile": _profile_payload(interaction.profile),
            "interaction_atomic": interaction_atomic,
        },
        "selected_profile": _profile_payload(selected),
        "holdout_atomic": holdout_atomic,
        "holdout_status": ",".join(sorted({d.status for d in holdout.values()})),
        "holdout_comparisons": {
            str(_profile_key(profile)): asdict(decision)
            for profile, decision in holdout.items()
        },
        "selected_metrics": selected_metrics,
        "holdout_semantic": selected_metrics["semantic_quality_mean"],
        "holdout_contract": selected_metrics["contract_accuracy"],
        "natural_thinking_tokens": {
            "mean": selected_metrics["thinking_tokens_mean"],
            "p95": selected_metrics["thinking_tokens_p95"],
            "max": selected_metrics["thinking_tokens_max"],
        },
    })
    return base


def _validate_scope(pool: TaskPool, spec: ExperimentSpec) -> None:
    if not spec.families:
        raise ValueError("at least one task family is required")
    unknown = set(spec.families) - set(TASK_FAMILIES)
    if unknown:
        raise ValueError(f"unknown task families: {sorted(unknown)}")
    for family in spec.families:
        count = sum(task.family == family for task in pool.tasks)
        if count < 600:
            raise ValueError(f"family {family} requires 600 frozen tasks; found {count}")
    geometry = call_geometry(len(spec.families))
    if spec.hard_call_ceiling < geometry["minimum"]:
        raise ValueError("hard call ceiling cannot support minimum certification geometry")

def run_universal_campaign(
    root: str | Path, pool: TaskPool, adapter: Any, spec: ExperimentSpec,
    *, progress: ProgressReporter | None = None,
) -> CampaignResult:
    _validate_scope(pool, spec)
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    task_manifest = freeze_task_pool(path, pool)
    metadata = getattr(adapter, "metadata", ModelMetadata())
    provenance_fn = getattr(adapter, "runtime_provenance", None)
    provenance = provenance_fn() if callable(provenance_fn) else {
        "provider": "synthetic", "adapter": type(adapter).__name__
    }
    geometry = call_geometry(len(spec.families))
    manifest = {
        "protocol_version": 2,
        "task_pool_sha256": pool.manifest_hash,
        "families": list(spec.families),
        "task_seed": spec.task_seed,
        "bootstrap_seed": spec.bootstrap_seed,
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "confidence_level": CONFIDENCE_LEVEL,
        "minimum_useful_effect": spec.minimum_useful_effect,
        "noninferiority_margin": spec.noninferiority_margin,
        "acceptable_semantic_floor": spec.acceptable_semantic_floor,
        "tasks_per_family": spec.tasks_per_family,
        "checkpoints": list(spec.checkpoints),
        "budget_candidates": list(spec.budget_candidates),
        "coarse_temperatures": list(spec.coarse_temperatures),
        "refinement_steps": list(REFINEMENT_STEPS),
        "hard_call_ceiling": spec.hard_call_ceiling,
        "call_geometry": geometry,
        "model_metadata": asdict(metadata),
        "runtime_provenance": provenance,
        "task_manifest": task_manifest,
    }
    runner = UniversalRunner(
        path, pool, adapter, manifest,
        max_physical_calls=spec.hard_call_ceiling, progress=progress,
    )
    scheduler = AdaptiveScheduler(pool, metadata)
    policy: dict[str, Any] = {}
    expected_per_family = call_geometry(1)["expected"]
    if progress is not None:
        progress.set_projection(
            runner.store.physical_calls_used() + expected_per_family * len(spec.families)
        )
    for index, family in enumerate(spec.families):
        if progress is not None:
            progress.set_projection(
                runner.store.physical_calls_used()
                + expected_per_family * (len(spec.families) - index)
            )
        policy[family] = _family_policy(runner, scheduler, spec, family, metadata)
        if progress is not None:
            progress.set_projection(
                runner.store.physical_calls_used()
                + expected_per_family * (len(spec.families) - index - 1)
            )
    physical_calls = runner.store.physical_calls_used()
    if progress is not None:
        progress.finalize(done=physical_calls)
    observation_count = len(runner.store.observation_rows())
    summary = {
        "status": "COMPLETED",
        "protocol_version": 2,
        "families": list(spec.families),
        "physical_calls": physical_calls,
        "observation_count": observation_count,
        "hard_call_ceiling": spec.hard_call_ceiling,
        "call_geometry": geometry,
        "runtime_provenance": provenance,
    }
    (path / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_campaign_report(path, policy, summary)
    return CampaignResult(
        status="COMPLETED", policy=policy, physical_calls=physical_calls,
        observation_count=observation_count, call_geometry=geometry,
    )


def run_qwen_v2_cli(args: Any) -> int:
    root = Path(args.run_root) if args.run_root else Path.cwd() / "runs" / (
        "qwen-thinking-tuning-v2-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    pool = build_qwen_task_pool(seed=20260907, per_family=600)
    adapter = QwenOllamaAdapter(base_url=args.base_url)
    ceiling = int(args.max_calls)
    spec = ExperimentSpec(hard_call_ceiling=ceiling)
    result = run_universal_campaign(root, pool, adapter, spec, progress=ProgressReporter(persistent=True))
    print(json.dumps({
        "status": result.status,
        "protocol_version": 2,
        "physical_calls": result.physical_calls,
        "observation_count": result.observation_count,
        "call_geometry": result.call_geometry,
        "run_root": str(root),
        "policy": result.policy,
    }, sort_keys=True))
    return 0
