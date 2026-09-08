from __future__ import annotations

import inverted.capability_ratchet as ratchet
from inverted.capability_ratchet.orchestration import RetryCampaignResult, TaskCampaignResult


def _task(task_id: str, difficulty: int, status: str, attempts: int) -> TaskCampaignResult:
    snapshots = {
        "FIRST_SHOT_PASS": (),
        "RECOVERED_RETRY_A": (f"{task_id}-initial",),
        "RECOVERED_RETRY_B": (f"{task_id}-initial", f"{task_id}-retry-a"),
        "HARD_FAILURE": (f"{task_id}-initial", f"{task_id}-retry-a", f"{task_id}-retry-b"),
    }[status]
    return TaskCampaignResult(
        task_id=task_id,
        difficulty=difficulty,
        status=status,
        attempt_count=attempts,
        failure_snapshot_ids=snapshots,
    )


def _derive(items: tuple[TaskCampaignResult, ...]):
    assert hasattr(ratchet, "derive_capability_boundaries")
    return ratchet.derive_capability_boundaries(
        RetryCampaignResult(model_id="qwen3.5:9b-q8_0", task_results=items)
    )


def test_clean_monotonic_ladder_reports_three_distinct_boundaries() -> None:
    boundaries = _derive((
        _task("d1", 1, "FIRST_SHOT_PASS", 1),
        _task("d2", 2, "FIRST_SHOT_PASS", 1),
        _task("d3", 3, "RECOVERED_RETRY_A", 2),
        _task("d4", 4, "RECOVERED_RETRY_B", 3),
        _task("d5", 5, "HARD_FAILURE", 3),
        _task("d6", 6, "HARD_FAILURE", 3),
    ))

    assert boundaries.model_id == "qwen3.5:9b-q8_0"
    assert boundaries.first_shot_boundary == 2
    assert boundaries.recoverable_boundary == 4
    assert boundaries.hard_failure_onset == 5
    assert boundaries.observed_first_shot_ceiling == 2
    assert boundaries.observed_recoverable_ceiling == 4
    assert boundaries.non_monotonic_task_ids == ()
    assert boundaries.is_monotonic is True


def test_success_above_hard_failure_does_not_inflate_reliable_boundary() -> None:
    boundaries = _derive((
        _task("d1", 1, "FIRST_SHOT_PASS", 1),
        _task("d2", 2, "HARD_FAILURE", 3),
        _task("d3", 3, "RECOVERED_RETRY_A", 2),
        _task("d4", 4, "FIRST_SHOT_PASS", 1),
    ))

    assert boundaries.first_shot_boundary == 1
    assert boundaries.recoverable_boundary == 1
    assert boundaries.hard_failure_onset == 2
    assert boundaries.observed_first_shot_ceiling == 4
    assert boundaries.observed_recoverable_ceiling == 4
    assert boundaries.non_monotonic_task_ids == ("d3", "d4")
    assert boundaries.is_monotonic is False


def test_same_difficulty_requires_all_cases_to_clear_frontier() -> None:
    boundaries = _derive((
        _task("d1-a", 1, "FIRST_SHOT_PASS", 1),
        _task("d1-b", 1, "FIRST_SHOT_PASS", 1),
        _task("d2-a", 2, "FIRST_SHOT_PASS", 1),
        _task("d2-b", 2, "RECOVERED_RETRY_A", 2),
        _task("d3-a", 3, "FIRST_SHOT_PASS", 1),
    ))

    assert boundaries.first_shot_boundary == 1
    assert boundaries.recoverable_boundary == 3
    assert boundaries.hard_failure_onset is None
    assert boundaries.observed_first_shot_ceiling == 3
    assert boundaries.observed_recoverable_ceiling == 3
    assert boundaries.non_monotonic_task_ids == ("d3-a",)
    assert boundaries.is_monotonic is False


def test_all_first_shot_passes_have_no_hard_failure_onset() -> None:
    boundaries = _derive((
        _task("d1", 1, "FIRST_SHOT_PASS", 1),
        _task("d2", 2, "FIRST_SHOT_PASS", 1),
        _task("d3", 3, "FIRST_SHOT_PASS", 1),
    ))

    assert boundaries.first_shot_boundary == 3
    assert boundaries.recoverable_boundary == 3
    assert boundaries.hard_failure_onset is None
    assert boundaries.is_monotonic is True


def test_empty_campaign_has_unknown_boundaries_not_fake_zeroes() -> None:
    boundaries = _derive(())

    assert boundaries.first_shot_boundary is None
    assert boundaries.recoverable_boundary is None
    assert boundaries.hard_failure_onset is None
    assert boundaries.observed_first_shot_ceiling is None
    assert boundaries.observed_recoverable_ceiling is None
    assert boundaries.non_monotonic_task_ids == ()
    assert boundaries.is_monotonic is True
