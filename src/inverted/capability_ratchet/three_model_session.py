"""Matched three-model session orchestration for Test1B-v3.

The campaign order is intentionally fixed: small model, Qwen, then Devstral.
Small/Qwen failure snapshots are queued with source attribution and replayed only
after Devstral completes the same matched task ladder, while Devstral remains in
one loaded session.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from inverted.universal_tuning.core import AtomicTask

from .boundaries import CapabilityBoundaries, derive_capability_boundaries
from .orchestration import RetryCampaignResult, TaskCampaignResult


_ATTEMPT_STAGES = ("INITIAL", "RETRY_A", "RETRY_B")


@dataclass(frozen=True)
class QueuedFailureReplay:
    """One canonical failure snapshot queued for Devstral replay."""

    source_model_id: str
    task_id: str
    difficulty: int
    attempt_stage: str
    failure_snapshot_id: str


@dataclass(frozen=True)
class ThreeModelSessionResult:
    """Matched campaign results, boundaries, and Devstral replay receipts."""

    small_campaign: RetryCampaignResult
    qwen_campaign: RetryCampaignResult
    devstral_campaign: RetryCampaignResult
    small_boundaries: CapabilityBoundaries
    qwen_boundaries: CapabilityBoundaries
    devstral_boundaries: CapabilityBoundaries
    queued_failures: tuple[QueuedFailureReplay, ...]
    devstral_replay_receipts: tuple[str, ...]

    @property
    def model_order(self) -> tuple[str, str, str]:
        return (
            self.small_campaign.model_id,
            self.qwen_campaign.model_id,
            self.devstral_campaign.model_id,
        )


class ThreeModelSessionOrchestrator:
    """Run the approved Test1B-v3 load/session order exactly once per model."""

    def __init__(
        self,
        *,
        load_model: Callable[[str], None],
        unload_model: Callable[[str], None],
        run_campaign: Callable[[str, tuple[AtomicTask, ...]], RetryCampaignResult],
        replay_failures: Callable[
            [str, tuple[QueuedFailureReplay, ...]],
            Iterable[str],
        ],
    ) -> None:
        for name, callback in (
            ("load_model", load_model),
            ("unload_model", unload_model),
            ("run_campaign", run_campaign),
            ("replay_failures", replay_failures),
        ):
            if not callable(callback):
                raise TypeError(f"{name} must be callable")
        self._load_model = load_model
        self._unload_model = unload_model
        self._run_campaign = run_campaign
        self._replay_failures = replay_failures

    @staticmethod
    def _validate_model_ids(
        small_model_id: str,
        qwen_model_id: str,
        devstral_model_id: str,
    ) -> None:
        model_ids = (small_model_id, qwen_model_id, devstral_model_id)
        if any(not isinstance(model_id, str) or not model_id.strip() for model_id in model_ids):
            raise ValueError("all three model ids must be non-empty strings")
        if len(set(model_ids)) != 3:
            raise ValueError("small, Qwen, and Devstral model ids must be distinct")

    @staticmethod
    def _validate_campaign(
        *,
        model_id: str,
        tasks: tuple[AtomicTask, ...],
        result: RetryCampaignResult,
    ) -> RetryCampaignResult:
        if not isinstance(result, RetryCampaignResult):
            raise TypeError("run_campaign must return RetryCampaignResult")
        if result.model_id != model_id:
            raise ValueError(
                f"campaign result model_id {result.model_id!r} does not match loaded model_id {model_id!r}"
            )
        expected = tuple((task.task_id, task.difficulty) for task in tasks)
        actual = tuple((item.task_id, item.difficulty) for item in result.task_results)
        if actual != expected:
            raise ValueError(
                f"campaign result for {model_id!r} does not match the matched task ladder"
            )
        return result

    def _run_loaded_campaign(
        self,
        *,
        model_id: str,
        tasks: tuple[AtomicTask, ...],
    ) -> RetryCampaignResult:
        self._load_model(model_id)
        try:
            result = self._run_campaign(model_id, tasks)
            return self._validate_campaign(model_id=model_id, tasks=tasks, result=result)
        finally:
            self._unload_model(model_id)

    @staticmethod
    def _queue_failures(
        campaigns: tuple[RetryCampaignResult, ...],
    ) -> tuple[QueuedFailureReplay, ...]:
        queued: list[QueuedFailureReplay] = []
        for campaign in campaigns:
            for task_result in campaign.task_results:
                if not isinstance(task_result, TaskCampaignResult):
                    raise TypeError("campaign task_results must contain TaskCampaignResult values")
                if len(task_result.failure_snapshot_ids) > len(_ATTEMPT_STAGES):
                    raise ValueError(
                        f"task {task_result.task_id!r} has more failure snapshots than Test1B-v3 attempts"
                    )
                queued.extend(
                    QueuedFailureReplay(
                        source_model_id=campaign.model_id,
                        task_id=task_result.task_id,
                        difficulty=task_result.difficulty,
                        attempt_stage=_ATTEMPT_STAGES[index],
                        failure_snapshot_id=snapshot_id,
                    )
                    for index, snapshot_id in enumerate(task_result.failure_snapshot_ids)
                )
        return tuple(queued)

    def run(
        self,
        *,
        small_model_id: str,
        qwen_model_id: str,
        devstral_model_id: str,
        tasks: Iterable[AtomicTask],
    ) -> ThreeModelSessionResult:
        self._validate_model_ids(small_model_id, qwen_model_id, devstral_model_id)
        task_ladder = tuple(tasks)
        if any(not isinstance(task, AtomicTask) for task in task_ladder):
            raise TypeError("tasks must contain only AtomicTask values")

        small_campaign = self._run_loaded_campaign(
            model_id=small_model_id,
            tasks=task_ladder,
        )
        qwen_campaign = self._run_loaded_campaign(
            model_id=qwen_model_id,
            tasks=task_ladder,
        )
        queued_failures = self._queue_failures((small_campaign, qwen_campaign))

        self._load_model(devstral_model_id)
        try:
            devstral_campaign = self._validate_campaign(
                model_id=devstral_model_id,
                tasks=task_ladder,
                result=self._run_campaign(devstral_model_id, task_ladder),
            )
            if queued_failures:
                devstral_replay_receipts = tuple(
                    self._replay_failures(devstral_model_id, queued_failures)
                )
                if len(devstral_replay_receipts) != len(queued_failures):
                    raise ValueError(
                        "Devstral replay receipt count must match the queued failure count"
                    )
            else:
                devstral_replay_receipts = ()
        finally:
            self._unload_model(devstral_model_id)

        return ThreeModelSessionResult(
            small_campaign=small_campaign,
            qwen_campaign=qwen_campaign,
            devstral_campaign=devstral_campaign,
            small_boundaries=derive_capability_boundaries(small_campaign),
            qwen_boundaries=derive_capability_boundaries(qwen_campaign),
            devstral_boundaries=derive_capability_boundaries(devstral_campaign),
            queued_failures=queued_failures,
            devstral_replay_receipts=devstral_replay_receipts,
        )
