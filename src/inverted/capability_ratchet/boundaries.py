"""Conservative capability-boundary analysis for Test1B-v3 campaigns."""

from __future__ import annotations

from dataclasses import dataclass

from .orchestration import RetryCampaignResult, TaskCampaignResult


_FIRST_SHOT_PASS = "FIRST_SHOT_PASS"
_RECOVERED_RETRY_A = "RECOVERED_RETRY_A"
_RECOVERED_RETRY_B = "RECOVERED_RETRY_B"
_HARD_FAILURE = "HARD_FAILURE"

_STATUS_TIER = {
    _FIRST_SHOT_PASS: 3,
    _RECOVERED_RETRY_A: 2,
    _RECOVERED_RETRY_B: 2,
    _HARD_FAILURE: 1,
}


@dataclass(frozen=True)
class CapabilityBoundaries:
    """Observed reliable frontiers for one model's ordered difficulty ladder.

    Boundaries are conservative: a frontier advances only when every observed
    case at that difficulty, and every easier difficulty, clears the relevant
    criterion. Observed ceilings separately retain harder isolated successes.
    """

    model_id: str
    first_shot_boundary: int | None
    recoverable_boundary: int | None
    hard_failure_onset: int | None
    observed_first_shot_ceiling: int | None
    observed_recoverable_ceiling: int | None
    non_monotonic_task_ids: tuple[str, ...] = ()

    @property
    def is_monotonic(self) -> bool:
        return not self.non_monotonic_task_ids


def _group_by_difficulty(
    task_results: tuple[TaskCampaignResult, ...],
) -> tuple[tuple[int, tuple[TaskCampaignResult, ...]], ...]:
    grouped: dict[int, list[TaskCampaignResult]] = {}
    for item in task_results:
        grouped.setdefault(item.difficulty, []).append(item)
    return tuple(
        (difficulty, tuple(grouped[difficulty]))
        for difficulty in sorted(grouped)
    )


def derive_capability_boundaries(result: RetryCampaignResult) -> CapabilityBoundaries:
    """Derive first-shot, recoverable, and hard-failure boundaries.

    `first_shot_boundary` is the highest contiguous difficulty for which every
    case through that level passed on the initial attempt.

    `recoverable_boundary` is the highest contiguous difficulty for which every
    case through that level succeeded within the initial attempt plus two
    declared retries.

    `hard_failure_onset` is the lowest difficulty containing any hard failure.
    The two observed ceiling fields retain isolated successes above a reliable
    frontier, while `non_monotonic_task_ids` identifies harder cases whose
    outcome tier improves after a weaker tier has already been observed.
    """
    if not isinstance(result, RetryCampaignResult):
        raise TypeError("result must be a RetryCampaignResult")

    grouped = _group_by_difficulty(result.task_results)
    if not grouped:
        return CapabilityBoundaries(
            model_id=result.model_id,
            first_shot_boundary=None,
            recoverable_boundary=None,
            hard_failure_onset=None,
            observed_first_shot_ceiling=None,
            observed_recoverable_ceiling=None,
            non_monotonic_task_ids=(),
        )

    first_shot_boundary: int | None = None
    recoverable_boundary: int | None = None
    hard_failure_onset: int | None = None
    observed_first_shot_ceiling: int | None = None
    observed_recoverable_ceiling: int | None = None
    first_shot_frontier_open = True
    recoverable_frontier_open = True
    lowest_prior_tier: int | None = None
    non_monotonic: list[str] = []

    for difficulty, items in grouped:
        statuses = tuple(item.status for item in items)
        all_first_shot = all(status == _FIRST_SHOT_PASS for status in statuses)
        all_recoverable = all(status != _HARD_FAILURE for status in statuses)
        any_first_shot = any(status == _FIRST_SHOT_PASS for status in statuses)
        any_recoverable = any(status != _HARD_FAILURE for status in statuses)
        any_hard_failure = any(status == _HARD_FAILURE for status in statuses)

        if first_shot_frontier_open:
            if all_first_shot:
                first_shot_boundary = difficulty
            else:
                first_shot_frontier_open = False

        if recoverable_frontier_open:
            if all_recoverable:
                recoverable_boundary = difficulty
            else:
                recoverable_frontier_open = False

        if any_first_shot:
            observed_first_shot_ceiling = difficulty
        if any_recoverable:
            observed_recoverable_ceiling = difficulty
        if hard_failure_onset is None and any_hard_failure:
            hard_failure_onset = difficulty

        tiers = tuple(_STATUS_TIER[item.status] for item in items)
        if lowest_prior_tier is not None:
            non_monotonic.extend(
                item.task_id
                for item in items
                if _STATUS_TIER[item.status] > lowest_prior_tier
            )
        group_floor = min(tiers)
        lowest_prior_tier = (
            group_floor
            if lowest_prior_tier is None
            else min(lowest_prior_tier, group_floor)
        )

    return CapabilityBoundaries(
        model_id=result.model_id,
        first_shot_boundary=first_shot_boundary,
        recoverable_boundary=recoverable_boundary,
        hard_failure_onset=hard_failure_onset,
        observed_first_shot_ceiling=observed_first_shot_ceiling,
        observed_recoverable_ceiling=observed_recoverable_ceiling,
        non_monotonic_task_ids=tuple(non_monotonic),
    )
