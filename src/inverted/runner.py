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


def run_experiment(config: ExperimentConfig, models: list[Any], run_id: str | None = None) -> ExperimentResult:
    run_id = run_id or f"run-{uuid.uuid4().hex[:16]}"
    started = datetime.now(timezone.utc).isoformat()
    trials: list[TrialRecord] = []
    budget = Budget(config.max_candidates, config.max_tokens_per_trial)
    for model in models:
        for epoch in range(config.epochs):
            for family, complexity, quality, seed in itertools.product(config.families, config.complexities, config.qualities, config.seeds):
                task_seed = (seed * 1009) + (epoch * 9176) + (complexity * 31)
                task = generate_task(family, complexity, task_seed)
                for arm_name in config.arms:
                    arm = Arm(arm_name)
                    trials.append(run_arm(arm, task, model, quality, seed, run_id, budget, epoch=epoch))
    ended = datetime.now(timezone.utc).isoformat()
    return ExperimentResult(run_id, started, ended, config, trials)
