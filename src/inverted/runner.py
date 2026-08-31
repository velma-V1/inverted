from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import itertools
import uuid
from typing import Any

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

    @property
    def model_calls(self):
        return [call for trial in self.trials for call in trial.model_calls]


def build_trial_plan(config: ExperimentConfig, models: list[Any]) -> list[TrialPlan]:
    if not models:
        raise ValueError("at least one model is required")
    if not config.qualities:
        raise ValueError("at least one executor quality is required")

    plan: list[TrialPlan] = []
    task_cells = itertools.product(
        range(config.epochs), config.families, config.complexities, config.seeds
    )
    canonical_quality = config.qualities[0]

    for epoch, family, complexity, seed in task_cells:
        for arm_name in config.arms:
            arm = Arm(arm_name)
            if arm in {Arm.A_DIRECT, Arm.B_DIRECT_CHECKED}:
                for model_index in range(len(models)):
                    plan.append(TrialPlan(model_index, epoch, family, complexity, canonical_quality, seed, arm.value))
            elif arm == Arm.D_INVERTED:
                for model_index in range(len(models)):
                    for quality in config.qualities:
                        plan.append(TrialPlan(model_index, epoch, family, complexity, quality, seed, arm.value))
            else:
                # C/E/F do not consume model behavior. Execute them once per
                # task/quality condition rather than once for every model.
                for quality in config.qualities:
                    plan.append(TrialPlan(0, epoch, family, complexity, quality, seed, arm.value))
    return plan


def run_experiment(config: ExperimentConfig, models: list[Any], run_id: str | None = None) -> ExperimentResult:
    run_id = run_id or f"run-{uuid.uuid4().hex[:16]}"
    started = datetime.now(timezone.utc).isoformat()
    trials: list[TrialRecord] = []
    budget = Budget(config.max_candidates, config.max_tokens_per_trial)

    for item in build_trial_plan(config, models):
        task_seed = (item.seed * 1009) + (item.epoch * 9176) + (item.complexity * 31)
        task = generate_task(item.family, item.complexity, task_seed)
        trials.append(
            run_arm(
                Arm(item.arm), task, models[item.model_index], item.quality, item.seed,
                run_id, budget, epoch=item.epoch,
            )
        )

    ended = datetime.now(timezone.utc).isoformat()
    return ExperimentResult(run_id, started, ended, config, trials)
