from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import campaign_base as base
from .core import Profile, profile_fingerprint
from .parameter_screening import (
    parameter_screen_call_geometry,
    screen_profile_parameters,
)
from .tasks import TASK_FAMILIES, TaskPool, build_qwen_task_pool, freeze_task_pool


REFINEMENT_STEPS = base.REFINEMENT_STEPS
CampaignResult = base.CampaignResult
QwenOllamaAdapter = base.QwenOllamaAdapter
ProgressReporter = base.ProgressReporter
UniversalRunner = base.UniversalRunner
AdaptiveScheduler = base.AdaptiveScheduler
ModeDecision = base.ModeDecision
ModelMetadata = base.ModelMetadata
TemperatureSurface = base.TemperatureSurface
BOOTSTRAP_ITERATIONS = base.BOOTSTRAP_ITERATIONS
CHECKPOINTS = base.CHECKPOINTS
CONFIDENCE_LEVEL = base.CONFIDENCE_LEVEL
write_campaign_report = base.write_campaign_report

# Keep the established evidence/statistics helpers available through the campaign module.
_profile_key = base._profile_key
_rows_for = base._rows_for
_vector = base._vector
_contract_rate = base._contract_rate
_completion_rate = base._completion_rate
_semantic_pass_rate = base._semantic_pass_rate
_wilson_interval = base._wilson_interval
_row_metrics = base._row_metrics
_run_profiles = base._run_profiles
_mode_gate = base._mode_gate
_temperature_outcomes = base._temperature_outcomes
_resolve_temperature_set = base._resolve_temperature_set
_temperature_candidates_for_interaction = base._temperature_candidates_for_interaction
_budget_candidates_for_interaction = base._budget_candidates_for_interaction
_holdout = base._holdout
_profile_payload = base._profile_payload
_surface_payload = base._surface_payload


@dataclass(frozen=True)
class ExperimentSpec:
    families: tuple[str, ...] = TASK_FAMILIES
    hard_call_ceiling: int = 18400
    coarse_temperatures: tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0, 1.2)
    budget_candidates: tuple[int, ...] = (256, 512, 1024, 2048)
    checkpoints: tuple[int, ...] = CHECKPOINTS
    bootstrap_seed: int = 20260907
    minimum_useful_effect: float = 0.05
    noninferiority_margin: float = -0.02
    acceptable_semantic_floor: float = 0.90
    task_seed: int = 20260907
    tasks_per_family: int = 720
    parameter_screen_enabled: bool = True


def call_geometry(
    family_count: int, *, parameter_screen_enabled: bool = True
) -> dict[str, int]:
    families = max(1, int(family_count))
    base_minimum = 48 * families
    base_expected = 312 * families
    base_worst = 1320 * families

    if parameter_screen_enabled:
        screen = parameter_screen_call_geometry(
            Profile(0, 0.7), supports_thinking=False
        )
        screen_minimum = int(screen["discovery_physical_ceiling"])
        # Discovery is the expected bounded screen; confirmation is only paid
        # when a candidate survives the independent scout comparison.
        screen_expected = screen_minimum
        screen_worst = int(screen["worst_case_physical_ceiling"])
    else:
        screen_minimum = 0
        screen_expected = 0
        screen_worst = 0

    return {
        "base_minimum": base_minimum,
        "parameter_screen_minimum": screen_minimum,
        "minimum": base_minimum + screen_minimum,
        "base_expected": base_expected,
        "parameter_screen_expected": screen_expected,
        "expected": base_expected + screen_expected,
        "base_worst_case": base_worst,
        "parameter_screen_worst_case": screen_worst,
        "worst_case": base_worst + screen_worst,
    }


def _profile_from_base(
    screened_base: Profile, *, thinking_budget: int, temperature: float
) -> Profile:
    """Change only dedicated thinking/temperature controls; preserve screened fields."""
    return replace(
        screened_base,
        thinking_budget=int(thinking_budget),
        temperature=float(temperature),
    )


def _budget_search(
    runner: UniversalRunner,
    scheduler: AdaptiveScheduler,
    spec: ExperimentSpec,
    family: str,
    temperature: float,
    screened_base: Profile,
):
    profiles = tuple(
        _profile_from_base(
            screened_base, thinking_budget=budget, temperature=temperature
        )
        for budget in spec.budget_candidates
    )
    decision = None
    count = spec.checkpoints[0]
    for count in spec.checkpoints:
        _run_profiles(
            runner,
            scheduler,
            family=family,
            stage="budget",
            profiles=profiles,
            atomic_count=count,
            reason="LOCALIZE_MINIMUM_USEFUL_BUDGET",
        )
        outcomes = {
            profile.thinking_budget: _vector(
                _rows_for(runner, scheduler, family, "budget", profile, count)
            )
            for profile in profiles
        }
        decision = base.select_minimum_budget(
            outcomes,
            bootstrap_seed=spec.bootstrap_seed,
            noninferiority_margin=spec.noninferiority_margin,
        )
        if decision.status != "EVIDENCE_CLOSE":
            break
    assert decision is not None
    selected = _profile_from_base(
        screened_base,
        thinking_budget=decision.selected_budget,
        temperature=temperature,
    )
    viable = tuple(
        budget
        for budget in sorted(spec.budget_candidates)
        if budget not in decision.inferior_budgets
    )
    if selected.thinking_budget not in viable:
        viable = (selected.thinking_budget,) + viable
    return decision, selected, viable, count


def _coarse_temperature_profiles(
    spec: ExperimentSpec, budget: int, screened_base: Profile
) -> tuple[Profile, ...]:
    values = tuple(sorted({round(float(value), 6) for value in spec.coarse_temperatures}))
    if len(values) < 2:
        raise ValueError("temperature search requires at least two coarse points")
    return tuple(
        _profile_from_base(
            screened_base, thinking_budget=budget, temperature=value
        )
        for value in values
    )


def _temperature_search(
    runner: UniversalRunner,
    scheduler: AdaptiveScheduler,
    spec: ExperimentSpec,
    family: str,
    budget: int,
    screened_base: Profile,
):
    tested = {
        profile.temperature
        for profile in _coarse_temperature_profiles(spec, budget, screened_base)
    }
    profiles = tuple(
        _profile_from_base(
            screened_base, thinking_budget=budget, temperature=temp
        )
        for temp in sorted(tested)
    )
    surface, count = _resolve_temperature_set(
        runner, scheduler, spec, family, profiles, spec.checkpoints[0]
    )
    if surface.kind in {"PLATEAU", "OPTIMUM"}:
        return surface, profiles, count

    center = surface.recommended
    if center is None:
        center = min(tested, key=lambda value: abs(value - 0.8))
    for step in REFINEMENT_STEPS:
        additions = {
            round(max(0.1, center - step), 6),
            round(min(1.5, center + step), 6),
        } - tested
        if additions:
            tested.update(additions)
            profiles = tuple(
                _profile_from_base(
                    screened_base, thinking_budget=budget, temperature=temp
                )
                for temp in sorted(tested)
            )
            surface, count = _resolve_temperature_set(
                runner, scheduler, spec, family, profiles, count
            )
        if surface.kind in {"PLATEAU", "OPTIMUM"}:
            return surface, profiles, count
        if surface.recommended is not None:
            center = surface.recommended
    return surface, profiles, count


def _interaction_search(
    runner: UniversalRunner,
    scheduler: AdaptiveScheduler,
    spec: ExperimentSpec,
    family: str,
    direct: Profile,
    selected_budget: int,
    viable_budgets: Iterable[int],
    surface: TemperatureSurface,
    tested_profiles: Iterable[Profile],
    screened_base: Profile,
):
    budgets = _budget_candidates_for_interaction(selected_budget, viable_budgets)
    temperatures = _temperature_candidates_for_interaction(
        surface, tested_profiles, selected_budget
    )
    candidates = tuple(
        _profile_from_base(
            screened_base, thinking_budget=budget, temperature=temp
        )
        for budget in budgets
        for temp in temperatures
    )
    profiles = (direct, *candidates)
    decision = None
    used_count = spec.checkpoints[0]
    for used_count in spec.checkpoints:
        _run_profiles(
            runner,
            scheduler,
            family=family,
            stage="interaction",
            profiles=profiles,
            atomic_count=used_count,
            reason="RESOLVE_BUDGET_TEMPERATURE_INTERACTION",
        )
        outcomes = {
            profile: _vector(
                _rows_for(
                    runner, scheduler, family, "interaction", profile, used_count
                )
            )
            for profile in profiles
        }
        decision = base.select_interaction_profile(
            outcomes, bootstrap_seed=spec.bootstrap_seed
        )
        if decision.status != "INTERACTION_CLOSE":
            break
    assert decision is not None
    return decision, profiles, used_count


def _family_policy(
    runner: UniversalRunner,
    scheduler: AdaptiveScheduler,
    spec: ExperimentSpec,
    family: str,
    metadata: ModelMetadata,
    screened_base: Profile,
) -> dict[str, Any]:
    direct = _profile_from_base(
        screened_base,
        thinking_budget=0,
        temperature=metadata.direct_temperature,
    )
    anchor_temp = (
        metadata.coding_thinking_temperature
        if family in {"CODING_GENERATION", "DEBUGGING_REVIEW"}
        else metadata.general_thinking_temperature
    )
    thinking_anchor = _profile_from_base(
        screened_base,
        thinking_budget=metadata.gate_thinking_budget,
        temperature=anchor_temp,
    )
    gate, gate_atomic = _mode_gate(
        runner, scheduler, spec, family, direct, thinking_anchor
    )
    gate_direct = _rows_for(
        runner, scheduler, family, "gate", direct, gate_atomic
    )
    gate_thinking = _rows_for(
        runner, scheduler, family, "gate", thinking_anchor, gate_atomic
    )
    base_policy = {
        "mode": gate.mode,
        "status": gate.status,
        "gate_atomic": gate_atomic,
        "screened_base_profile": _profile_payload(screened_base),
        "direct_semantic": sum(_vector(gate_direct)) / gate_atomic,
        "thinking_semantic": sum(_vector(gate_thinking)) / gate_atomic,
        "direct_vs_thinking_delta": (
            sum(_vector(gate_thinking)) - sum(_vector(gate_direct))
        ) / gate_atomic,
        "gate_direct_metrics": _row_metrics(gate_direct),
        "gate_thinking_metrics": _row_metrics(gate_thinking),
        "minimum_useful_budget": None,
        "temperature": None,
        "interaction": None,
        "selected_profile": None,
        "holdout_atomic": 0,
        "gate_diagnostic_used": False,
    }

    if gate.mode == "unresolved" and gate.status == "CAPABILITY_UNRESOLVED":
        diagnostic = _profile_from_base(
            screened_base,
            thinking_budget=metadata.diagnostic_budget,
            temperature=anchor_temp,
        )
        if diagnostic != thinking_anchor:
            _run_profiles(
                runner,
                scheduler,
                family=family,
                stage="gate",
                profiles=(direct, diagnostic),
                atomic_count=spec.checkpoints[-1],
                reason="CAPABILITY_HIGH_BUDGET_DIAGNOSTIC",
            )
            diagnostic_rows = _rows_for(
                runner,
                scheduler,
                family,
                "gate",
                diagnostic,
                spec.checkpoints[-1],
            )
            base_policy["gate_diagnostic_used"] = True
            base_policy["diagnostic_semantic"] = (
                sum(_vector(diagnostic_rows)) / len(diagnostic_rows)
            )
            if base_policy["diagnostic_semantic"] >= spec.acceptable_semantic_floor:
                gate = ModeDecision(
                    "thinking", "DIAGNOSTIC_BUDGET_RECOVERY", "budget"
                )
                base_policy["mode"] = gate.mode
                base_policy["status"] = gate.status

    if gate.mode == "unresolved":
        return base_policy

    if gate.mode == "direct":
        holdout, selected_rows, _alternate_rows, holdout_atomic = _holdout(
            runner, scheduler, spec, family, direct, (thinking_anchor,)
        )
        selected_metrics = _row_metrics(selected_rows)
        final_status = gate.status
        if selected_metrics["semantic_accuracy"] < spec.acceptable_semantic_floor:
            final_status = "CAPABILITY_UNRESOLVED"
        base_policy.update(
            {
                "status": final_status,
                "selected_profile": _profile_payload(direct),
                "holdout_atomic": holdout_atomic,
                "holdout_status": ",".join(
                    sorted({decision.status for decision in holdout.values()})
                ),
                "holdout_comparisons": {
                    str(_profile_key(profile)): asdict(decision)
                    for profile, decision in holdout.items()
                },
                "selected_metrics": selected_metrics,
                "holdout_semantic": selected_metrics["semantic_quality_mean"],
                "holdout_contract": selected_metrics["contract_accuracy"],
            }
        )
        return base_policy

    budget_decision, selected_budget_profile, viable_budgets, budget_atomic = (
        _budget_search(
            runner, scheduler, spec, family, anchor_temp, screened_base
        )
    )
    surface, tested_temperature_profiles, temperature_atomic = _temperature_search(
        runner,
        scheduler,
        spec,
        family,
        selected_budget_profile.thinking_budget,
        screened_base,
    )
    interaction, interaction_profiles, interaction_atomic = _interaction_search(
        runner,
        scheduler,
        spec,
        family,
        direct,
        selected_budget_profile.thinking_budget,
        viable_budgets,
        surface,
        tested_temperature_profiles,
        screened_base,
    )
    selected = interaction.profile
    preinteraction = _profile_from_base(
        screened_base,
        thinking_budget=selected_budget_profile.thinking_budget,
        temperature=(
            surface.optimum
            if surface.optimum is not None
            else float(surface.recommended)
        ),
    )
    interaction_rates = {
        profile: sum(
            _vector(
                _rows_for(
                    runner,
                    scheduler,
                    family,
                    "interaction",
                    profile,
                    interaction_atomic,
                )
            )
        )
        / interaction_atomic
        for profile in interaction_profiles
    }
    ranked_alternatives = sorted(
        (profile for profile in interaction_profiles if profile != selected),
        key=lambda profile: (
            -interaction_rates[profile],
            profile.thinking_budget,
            profile.temperature,
        ),
    )
    serious = ranked_alternatives[0] if ranked_alternatives else preinteraction
    alternates = (
        tuple(dict.fromkeys((direct, serious)))
        if selected != direct
        else (serious,)
    )
    holdout, selected_rows, _alternate_rows, holdout_atomic = _holdout(
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
    base_policy.update(
        {
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
            "holdout_status": ",".join(
                sorted({decision.status for decision in holdout.values()})
            ),
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
        }
    )
    return base_policy


def _validate_scope(pool: TaskPool, spec: ExperimentSpec) -> None:
    if not spec.families:
        raise ValueError("at least one task family is required")
    unknown = set(spec.families) - set(TASK_FAMILIES)
    if unknown:
        raise ValueError(f"unknown task families: {sorted(unknown)}")
    if spec.parameter_screen_enabled and spec.tasks_per_family < 720:
        raise ValueError("parameter screening requires at least 720 frozen tasks per family")
    for family in spec.families:
        count = sum(task.family == family for task in pool.tasks)
        if count < spec.tasks_per_family:
            raise ValueError(
                f"family {family} requires {spec.tasks_per_family} frozen tasks; found {count}"
            )
    geometry = call_geometry(
        len(spec.families), parameter_screen_enabled=spec.parameter_screen_enabled
    )
    if spec.hard_call_ceiling < geometry["minimum"]:
        raise ValueError("hard call ceiling cannot support minimum certification geometry")


def run_universal_campaign(
    root: str | Path,
    pool: TaskPool,
    adapter: Any,
    spec: ExperimentSpec,
    *,
    progress: ProgressReporter | None = None,
) -> CampaignResult:
    _validate_scope(pool, spec)
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    task_manifest = freeze_task_pool(path, pool)
    metadata = getattr(adapter, "metadata", ModelMetadata())
    provenance_fn = getattr(adapter, "runtime_provenance", None)
    provenance = (
        provenance_fn()
        if callable(provenance_fn)
        else {"provider": "synthetic", "adapter": type(adapter).__name__}
    )
    geometry = call_geometry(
        len(spec.families), parameter_screen_enabled=spec.parameter_screen_enabled
    )
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
        "parameter_screen_enabled": spec.parameter_screen_enabled,
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
        path,
        pool,
        adapter,
        manifest,
        max_physical_calls=spec.hard_call_ceiling,
        progress=progress,
    )
    scheduler = AdaptiveScheduler(pool, metadata)

    screened_base = Profile(0, metadata.direct_temperature)
    screen_result = None
    if progress is not None:
        progress.set_projection(
            runner.store.physical_calls_used() + geometry["expected"]
        )
    if spec.parameter_screen_enabled:
        screen_result = screen_profile_parameters(
            runner,
            scheduler,
            screened_base,
            supports_thinking=bool(getattr(adapter, "supports_thinking", True)),
            max_additional_physical_calls=geometry[
                "parameter_screen_worst_case"
            ],
            bootstrap_seed=spec.bootstrap_seed,
        )
        screened_base = screen_result.incumbent

    policy: dict[str, Any] = {}
    expected_per_family = call_geometry(
        1, parameter_screen_enabled=False
    )["expected"]
    for index, family in enumerate(spec.families):
        if progress is not None:
            progress.set_projection(
                runner.store.physical_calls_used()
                + expected_per_family * (len(spec.families) - index)
            )
        policy[family] = _family_policy(
            runner, scheduler, spec, family, metadata, screened_base
        )
        if progress is not None:
            progress.set_projection(
                runner.store.physical_calls_used()
                + expected_per_family * (len(spec.families) - index - 1)
            )

    physical_calls = runner.store.physical_calls_used()
    if progress is not None:
        progress.finalize(done=physical_calls)
    observation_count = len(runner.store.observation_rows())
    parameter_screen_summary = {
        "enabled": spec.parameter_screen_enabled,
        "selected_profile": _profile_payload(screened_base),
        "new_physical_calls": (
            int(screen_result.physical_calls) if screen_result is not None else 0
        ),
        "decision_count": (
            len(screen_result.decisions) if screen_result is not None else 0
        ),
    }
    summary = {
        "status": "COMPLETED",
        "protocol_version": 2,
        "families": list(spec.families),
        "physical_calls": physical_calls,
        "observation_count": observation_count,
        "hard_call_ceiling": spec.hard_call_ceiling,
        "call_geometry": geometry,
        "parameter_screen": parameter_screen_summary,
        "runtime_provenance": provenance,
    }
    (path / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_campaign_report(path, policy, summary)
    return CampaignResult(
        status="COMPLETED",
        policy=policy,
        physical_calls=physical_calls,
        observation_count=observation_count,
        call_geometry=geometry,
    )


def run_qwen_v2_cli(args: Any) -> int:
    root = Path(args.run_root) if args.run_root else Path.cwd() / "runs" / (
        "qwen-thinking-tuning-v2-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    ceiling = int(args.max_calls)
    spec = ExperimentSpec(hard_call_ceiling=ceiling)
    pool = build_qwen_task_pool(
        seed=spec.task_seed, per_family=spec.tasks_per_family
    )
    adapter = QwenOllamaAdapter(base_url=args.base_url)
    result = run_universal_campaign(
        root,
        pool,
        adapter,
        spec,
        progress=ProgressReporter(persistent=True),
    )
    print(
        json.dumps(
            {
                "status": result.status,
                "protocol_version": 2,
                "physical_calls": result.physical_calls,
                "observation_count": result.observation_count,
                "call_geometry": result.call_geometry,
                "run_root": str(root),
                "policy": result.policy,
            },
            sort_keys=True,
        )
    )
    return 0
