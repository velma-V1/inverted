from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import itertools
import uuid
from typing import Any, Callable

from .arms import Arm, Budget, TrialRecord, run_arm
from .tasks import generate_task


@dataclass(frozen=True)
class ExperimentConfig:
    families: tuple[str, ...] = ("state", "policy", "reconciliation")
    complexities: tuple[int, ...] = (1, 2, 3, 4)
    qualities: tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 0.95)
    seeds: tuple[int, ...] = (1, 2, 3)
    epochs: int = 2
    arms: tuple[str, ...] = tuple(a.value for a in Arm)
    max_candidates: int = 3
    max_tokens_per_trial: int = 4096
    decisive: bool = False
    minimum_primary_trials: int = 180
    bootstrap_samples: int = 2000
    bootstrap_seed: int = 20260830
    sequential_seed_stages: tuple[int, ...] = ()
    sequential_interim_confidence: tuple[float, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrialPlan:
    model_index: int
    epoch: int
    family: str
    complexity: int
    quality: float
    seed: int
    arm: str


@dataclass
class ExperimentResult:
    run_id: str
    started_at: str
    ended_at: str
    config: ExperimentConfig
    trials: list[TrialRecord]
    stopped_early: bool = False
    completed_seed_count: int | None = None
    sequential_decision: dict[str, Any] | None = None
    planned_trial_units: int = 0

    @property
    def model_calls(self):
        return [call for trial in self.trials for call in trial.model_calls]


_MODEL_DEPENDENT_ARMS = {Arm.A_DIRECT.value, Arm.B_DIRECT_CHECKED.value, Arm.D_INVERTED.value}
_MODEL_INDEPENDENT = "__model_independent__"


def _model_identity(model: Any) -> str:
    return f"{getattr(model, 'provider', 'none')}:{getattr(model, 'model', 'none')}"


def trial_plan_key(item: TrialPlan, models: list[Any]) -> tuple[Any, ...]:
    identity = _model_identity(models[item.model_index]) if item.arm in _MODEL_DEPENDENT_ARMS else _MODEL_INDEPENDENT
    return (identity, item.epoch, item.family, item.complexity, float(item.quality), item.seed, item.arm)


def trial_record_key(trial: TrialRecord) -> tuple[Any, ...]:
    identity = f"{trial.provider}:{trial.model}" if trial.arm in _MODEL_DEPENDENT_ARMS else _MODEL_INDEPENDENT
    return (identity, trial.epoch, trial.family, trial.complexity, float(trial.configured_executor_quality), trial.seed, trial.arm)


def _build_trial_plan_for_seeds(config: ExperimentConfig, models: list[Any], seeds: tuple[int, ...]) -> list[TrialPlan]:
    plan: list[TrialPlan] = []
    task_cells = list(itertools.product(
        range(config.epochs), config.families, config.complexities, seeds
    ))
    canonical_quality = config.qualities[0]

    # Within every sequential stage, controls and real-model arms use exactly
    # the same seed slice. This prevents interim looks from comparing a partial
    # model sample against controls from future seeds.
    for epoch, family, complexity, seed in task_cells:
        for arm_name in config.arms:
            arm = Arm(arm_name)
            if arm.value in _MODEL_DEPENDENT_ARMS:
                continue
            for quality in config.qualities:
                plan.append(TrialPlan(0, epoch, family, complexity, quality, seed, arm.value))

    # Keep each model contiguous inside a stage to minimize Ollama model-load
    # churn while ensuring every stage contains every model before evaluation.
    for model_index in range(len(models)):
        for epoch, family, complexity, seed in task_cells:
            for arm_name in config.arms:
                arm = Arm(arm_name)
                if arm in {Arm.A_DIRECT, Arm.B_DIRECT_CHECKED}:
                    plan.append(TrialPlan(model_index, epoch, family, complexity, canonical_quality, seed, arm.value))
                elif arm == Arm.D_INVERTED:
                    for quality in config.qualities:
                        plan.append(TrialPlan(model_index, epoch, family, complexity, quality, seed, arm.value))
    return plan


def build_trial_plan(config: ExperimentConfig, models: list[Any]) -> list[TrialPlan]:
    if not models:
        raise ValueError("at least one model is required")
    if not config.qualities:
        raise ValueError("at least one executor quality is required")
    return _build_trial_plan_for_seeds(config, models, tuple(config.seeds))


def build_trial_stages(config: ExperimentConfig, models: list[Any]) -> list[list[TrialPlan]]:
    if not models:
        raise ValueError("at least one model is required")
    if not config.qualities:
        raise ValueError("at least one executor quality is required")
    if not config.sequential_seed_stages:
        return [build_trial_plan(config, models)]

    stages = tuple(int(x) for x in config.sequential_seed_stages)
    if any(x <= 0 for x in stages) or tuple(sorted(set(stages))) != stages:
        raise ValueError("sequential_seed_stages must be strictly increasing positive cumulative seed counts")
    if stages[-1] != len(config.seeds):
        raise ValueError("final sequential seed stage must include every configured seed")

    result: list[list[TrialPlan]] = []
    previous = 0
    for cumulative in stages:
        if cumulative > len(config.seeds):
            raise ValueError("sequential seed stage exceeds configured seed count")
        stage_seeds = tuple(config.seeds[previous:cumulative])
        if not stage_seeds:
            raise ValueError("sequential stage cannot be empty")
        result.append(_build_trial_plan_for_seeds(config, models, stage_seeds))
        previous = cumulative
    return result


def run_experiment(
    config: ExperimentConfig,
    models: list[Any],
    run_id: str | None = None,
    *,
    checkpoint_store: Any | None = None,
    resume: bool = False,
    progress_callback: Callable[[int, int, TrialPlan], None] | None = None,
    stage_callback: Callable[[int, int, int, list[TrialRecord]], dict[str, Any] | None] | None = None,
) -> ExperimentResult:
    run_id = run_id or f"run-{uuid.uuid4().hex[:16]}"
    started = datetime.now(timezone.utc).isoformat()
    budget = Budget(config.max_candidates, config.max_tokens_per_trial)
    stages = build_trial_stages(config, models)
    plan = [item for stage in stages for item in stage]
    plan_keys = [trial_plan_key(item, models) for item in plan]
    if len(set(plan_keys)) != len(plan_keys):
        raise ValueError("execution plan contains duplicate trial keys")
    planned = set(plan_keys)

    trials_by_key: dict[tuple[Any, ...], TrialRecord] = {}
    if resume:
        if checkpoint_store is None:
            raise ValueError("resume requires a checkpoint store")
        for trial in checkpoint_store.load_trials():
            if trial.run_id != run_id:
                raise ValueError(f"checkpoint run_id {trial.run_id!r} does not match requested run_id {run_id!r}")
            key = trial_record_key(trial)
            if key not in planned:
                raise ValueError("checkpoint contains a trial outside the current execution plan")
            trials_by_key[key] = trial
    elif checkpoint_store is not None and checkpoint_store.load_trials():
        raise ValueError("checkpoint already contains trials; use resume=True or a new checkpoint path")

    completed = len(trials_by_key)
    total = len(plan)
    stopped_early = False
    sequential_decision: dict[str, Any] | None = None
    completed_seed_count: int | None = None

    flat_offset = 0
    for stage_number, stage in enumerate(stages, start=1):
        for item in stage:
            key = trial_plan_key(item, models)
            if key in trials_by_key:
                continue
            task_seed = (item.seed * 1009) + (item.epoch * 9176) + (item.complexity * 31)
            task = generate_task(item.family, item.complexity, task_seed)
            trial = run_arm(
                Arm(item.arm), task, models[item.model_index], item.quality, item.seed,
                run_id, budget, epoch=item.epoch,
            )
            trials_by_key[key] = trial
            if checkpoint_store is not None:
                checkpoint_store.append_trial(trial)
            completed += 1
            if progress_callback is not None:
                progress_callback(completed, total, item)

        flat_offset += len(stage)
        if config.sequential_seed_stages:
            completed_seed_count = int(config.sequential_seed_stages[stage_number - 1])
        else:
            completed_seed_count = len(config.seeds)

        # Interim evaluation is intentionally disabled for the final stage;
        # the original full-sample preregistered verdict rule remains authority.
        if stage_callback is not None and stage_number < len(stages):
            cumulative_trials = [trials_by_key[key] for key in plan_keys[:flat_offset] if key in trials_by_key]
            decision = stage_callback(stage_number, completed_seed_count, len(config.seeds), cumulative_trials) or {"stop": False}
            if bool(decision.get("stop")):
                stopped_early = True
                sequential_decision = dict(decision)
                break

    trials = [trials_by_key[key] for key in plan_keys if key in trials_by_key]
    ended = datetime.now(timezone.utc).isoformat()
    return ExperimentResult(
        run_id, started, ended, config, trials,
        stopped_early=stopped_early,
        completed_seed_count=completed_seed_count,
        sequential_decision=sequential_decision,
        planned_trial_units=total,
    )
