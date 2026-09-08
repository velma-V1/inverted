from __future__ import annotations

from typing import Any

import inverted.capability_ratchet as ratchet


def _api() -> dict[str, Any]:
    required = (
        "AttemptOutcome",
        "CampaignTask",
        "RetryCampaignOrchestrator",
        "RetryIngredient",
    )
    missing = [name for name in required if not hasattr(ratchet, name)]
    assert not missing, f"Test1B-v3 orchestration API is missing: {missing}"
    return {name: getattr(ratchet, name) for name in required}


def test_hard_failure_gets_exactly_two_retries_is_snapshotted_and_campaign_continues() -> None:
    api = _api()
    CampaignTask = api["CampaignTask"]
    RetryIngredient = api["RetryIngredient"]
    AttemptOutcome = api["AttemptOutcome"]
    RetryCampaignOrchestrator = api["RetryCampaignOrchestrator"]

    calls: list[tuple[str, str, str | None]] = []
    snapshots: list[tuple[str, str, tuple[str, ...]]] = []

    def execute_attempt(context: Any) -> Any:
        ingredient_id = (
            None if context.retry_ingredient is None else context.retry_ingredient.ingredient_id
        )
        calls.append((context.task.task_id, context.stage, ingredient_id))
        if context.task.task_id == "difficulty-1":
            return AttemptOutcome(passed=False, failure_classes=("SEMANTIC_FAIL",))
        return AttemptOutcome(passed=True)

    def snapshot_failure(context: Any, outcome: Any) -> str:
        snapshots.append((context.task.task_id, context.stage, outcome.failure_classes))
        return f"snapshot-{context.task.task_id}-{context.stage.lower()}"

    orchestrator = RetryCampaignOrchestrator(
        execute_attempt=execute_attempt,
        snapshot_failure=snapshot_failure,
        retry_a=RetryIngredient("retry-a", "minimal-diagnostic-reset"),
        retry_b=RetryIngredient("retry-b", "fresh-context-validator-evidence"),
    )

    result = orchestrator.run(
        model_id="qwen3.5-9b-q8",
        tasks=(
            CampaignTask("difficulty-1", difficulty=1),
            CampaignTask("difficulty-2", difficulty=2),
        ),
    )

    assert calls == [
        ("difficulty-1", "INITIAL", None),
        ("difficulty-1", "RETRY_A", "retry-a"),
        ("difficulty-1", "RETRY_B", "retry-b"),
        ("difficulty-2", "INITIAL", None),
    ]
    assert snapshots == [
        ("difficulty-1", "INITIAL", ("SEMANTIC_FAIL",)),
        ("difficulty-1", "RETRY_A", ("SEMANTIC_FAIL",)),
        ("difficulty-1", "RETRY_B", ("SEMANTIC_FAIL",)),
    ]
    assert [item.status for item in result.task_results] == [
        "HARD_FAILURE",
        "FIRST_SHOT_PASS",
    ]
    assert result.hard_failure_task_ids == ("difficulty-1",)
    assert result.total_attempts == 4


def test_retry_a_recovery_stops_retrying_that_task_but_continues_ladder() -> None:
    api = _api()
    CampaignTask = api["CampaignTask"]
    RetryIngredient = api["RetryIngredient"]
    AttemptOutcome = api["AttemptOutcome"]
    RetryCampaignOrchestrator = api["RetryCampaignOrchestrator"]

    calls: list[tuple[str, str]] = []
    snapshots: list[str] = []

    def execute_attempt(context: Any) -> Any:
        calls.append((context.task.task_id, context.stage))
        if context.task.task_id == "difficulty-1" and context.stage == "INITIAL":
            return AttemptOutcome(passed=False, failure_classes=("CONTRACT_FAIL",))
        return AttemptOutcome(passed=True)

    def snapshot_failure(context: Any, outcome: Any) -> str:
        snapshots.append(f"{context.task.task_id}:{context.stage}")
        return f"snapshot-{len(snapshots)}"

    orchestrator = RetryCampaignOrchestrator(
        execute_attempt=execute_attempt,
        snapshot_failure=snapshot_failure,
        retry_a=RetryIngredient("retry-a", "minimal-diagnostic-reset"),
        retry_b=RetryIngredient("retry-b", "fresh-context-validator-evidence"),
    )
    result = orchestrator.run(
        model_id="qwen3.5-9b-q8",
        tasks=(
            CampaignTask("difficulty-1", difficulty=1),
            CampaignTask("difficulty-2", difficulty=2),
        ),
    )

    assert calls == [
        ("difficulty-1", "INITIAL"),
        ("difficulty-1", "RETRY_A"),
        ("difficulty-2", "INITIAL"),
    ]
    assert snapshots == ["difficulty-1:INITIAL"]
    assert [item.status for item in result.task_results] == [
        "RECOVERED_RETRY_A",
        "FIRST_SHOT_PASS",
    ]
    assert result.hard_failure_task_ids == ()


def test_retry_b_recovery_records_both_pre_recovery_failures() -> None:
    api = _api()
    CampaignTask = api["CampaignTask"]
    RetryIngredient = api["RetryIngredient"]
    AttemptOutcome = api["AttemptOutcome"]
    RetryCampaignOrchestrator = api["RetryCampaignOrchestrator"]

    snapshots: list[str] = []

    def execute_attempt(context: Any) -> Any:
        if context.stage == "RETRY_B":
            return AttemptOutcome(passed=True)
        return AttemptOutcome(passed=False, failure_classes=("SEMANTIC_FAIL",))

    def snapshot_failure(context: Any, outcome: Any) -> str:
        snapshots.append(context.stage)
        return f"snapshot-{context.stage.lower()}"

    orchestrator = RetryCampaignOrchestrator(
        execute_attempt=execute_attempt,
        snapshot_failure=snapshot_failure,
        retry_a=RetryIngredient("retry-a", "minimal-diagnostic-reset"),
        retry_b=RetryIngredient("retry-b", "fresh-context-validator-evidence"),
    )
    result = orchestrator.run(
        model_id="qwen3.5-9b-q8",
        tasks=(CampaignTask("difficulty-1", difficulty=1),),
    )

    assert snapshots == ["INITIAL", "RETRY_A"]
    assert result.task_results[0].status == "RECOVERED_RETRY_B"
    assert result.task_results[0].attempt_count == 3
    assert result.task_results[0].failure_snapshot_ids == (
        "snapshot-initial",
        "snapshot-retry_a",
    )
