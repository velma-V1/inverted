from __future__ import annotations

import pytest

import inverted.capability_ratchet as ratchet
from inverted.capability_ratchet.orchestration import RetryCampaignResult, TaskCampaignResult
from inverted.universal_tuning.core import AtomicTask


SMALL = "qwen-small:1.7b"
QWEN = "qwen3.5:9b-q8_0"
DEVSTRAL = "devstral-small-2:24b"


def _task(task_id: str, difficulty: int) -> AtomicTask:
    return AtomicTask(
        task_id=task_id,
        family="LOGIC",
        difficulty=difficulty,
        prompt=f"Solve {task_id}.",
        expected="B",
        scorer="exact_value",
        contract="answer_object",
    )


def _result(model_id: str, rows: tuple[tuple[str, int, str], ...]) -> RetryCampaignResult:
    items: list[TaskCampaignResult] = []
    for task_id, difficulty, status in rows:
        snapshots = {
            "FIRST_SHOT_PASS": (),
            "RECOVERED_RETRY_A": (f"{model_id}:{task_id}:initial",),
            "RECOVERED_RETRY_B": (
                f"{model_id}:{task_id}:initial",
                f"{model_id}:{task_id}:retry-a",
            ),
            "HARD_FAILURE": (
                f"{model_id}:{task_id}:initial",
                f"{model_id}:{task_id}:retry-a",
                f"{model_id}:{task_id}:retry-b",
            ),
        }[status]
        attempts = {
            "FIRST_SHOT_PASS": 1,
            "RECOVERED_RETRY_A": 2,
            "RECOVERED_RETRY_B": 3,
            "HARD_FAILURE": 3,
        }[status]
        items.append(TaskCampaignResult(
            task_id=task_id,
            difficulty=difficulty,
            status=status,
            attempt_count=attempts,
            failure_snapshot_ids=snapshots,
        ))
    return RetryCampaignResult(model_id=model_id, task_results=tuple(items))


def _api():
    assert hasattr(ratchet, "ThreeModelSessionOrchestrator")
    assert hasattr(ratchet, "QueuedFailureReplay")
    return ratchet.ThreeModelSessionOrchestrator, ratchet.QueuedFailureReplay


def test_runs_matched_ladders_in_load_order_then_batches_small_and_qwen_failures_into_one_devstral_session() -> None:
    Orchestrator, QueuedFailureReplay = _api()
    tasks = (_task("d1", 1), _task("d2", 2))
    campaigns = {
        SMALL: _result(SMALL, (
            ("d1", 1, "FIRST_SHOT_PASS"),
            ("d2", 2, "HARD_FAILURE"),
        )),
        QWEN: _result(QWEN, (
            ("d1", 1, "FIRST_SHOT_PASS"),
            ("d2", 2, "RECOVERED_RETRY_A"),
        )),
        DEVSTRAL: _result(DEVSTRAL, (
            ("d1", 1, "FIRST_SHOT_PASS"),
            ("d2", 2, "HARD_FAILURE"),
        )),
    }
    events: list[tuple] = []
    seen_ladders: list[tuple[str, tuple[tuple[str, int], ...]]] = []

    def load_model(model_id: str) -> None:
        events.append(("load", model_id))

    def unload_model(model_id: str) -> None:
        events.append(("unload", model_id))

    def run_campaign(model_id: str, ladder: tuple[AtomicTask, ...]) -> RetryCampaignResult:
        events.append(("campaign", model_id))
        seen_ladders.append((model_id, tuple((task.task_id, task.difficulty) for task in ladder)))
        return campaigns[model_id]

    replay_queue_seen = []

    def replay_failures(model_id: str, queue):
        events.append(("replay", model_id))
        replay_queue_seen.extend(queue)
        return tuple(f"receipt:{item.failure_snapshot_id}" for item in queue)

    result = Orchestrator(
        load_model=load_model,
        unload_model=unload_model,
        run_campaign=run_campaign,
        replay_failures=replay_failures,
    ).run(
        small_model_id=SMALL,
        qwen_model_id=QWEN,
        devstral_model_id=DEVSTRAL,
        tasks=tasks,
    )

    assert events == [
        ("load", SMALL),
        ("campaign", SMALL),
        ("unload", SMALL),
        ("load", QWEN),
        ("campaign", QWEN),
        ("unload", QWEN),
        ("load", DEVSTRAL),
        ("campaign", DEVSTRAL),
        ("replay", DEVSTRAL),
        ("unload", DEVSTRAL),
    ]
    expected_ladder = (("d1", 1), ("d2", 2))
    assert seen_ladders == [
        (SMALL, expected_ladder),
        (QWEN, expected_ladder),
        (DEVSTRAL, expected_ladder),
    ]

    expected_queue = (
        QueuedFailureReplay(SMALL, "d2", 2, "INITIAL", f"{SMALL}:d2:initial"),
        QueuedFailureReplay(SMALL, "d2", 2, "RETRY_A", f"{SMALL}:d2:retry-a"),
        QueuedFailureReplay(SMALL, "d2", 2, "RETRY_B", f"{SMALL}:d2:retry-b"),
        QueuedFailureReplay(QWEN, "d2", 2, "INITIAL", f"{QWEN}:d2:initial"),
    )
    assert tuple(replay_queue_seen) == expected_queue
    assert result.queued_failures == expected_queue
    assert all(item.source_model_id != DEVSTRAL for item in result.queued_failures)
    assert result.devstral_replay_receipts == tuple(
        f"receipt:{item.failure_snapshot_id}" for item in expected_queue
    )
    assert result.model_order == (SMALL, QWEN, DEVSTRAL)
    assert result.small_campaign == campaigns[SMALL]
    assert result.qwen_campaign == campaigns[QWEN]
    assert result.devstral_campaign == campaigns[DEVSTRAL]
    assert result.small_boundaries.hard_failure_onset == 2
    assert result.qwen_boundaries.first_shot_boundary == 1
    assert result.qwen_boundaries.recoverable_boundary == 2
    assert result.devstral_boundaries.hard_failure_onset == 2


def test_campaign_result_must_match_exact_task_ids_difficulties_and_order_and_unloads_on_mismatch() -> None:
    Orchestrator, _ = _api()
    tasks = (_task("d1", 1), _task("d2", 2))
    events: list[tuple[str, str]] = []

    good_small = _result(SMALL, (
        ("d1", 1, "FIRST_SHOT_PASS"),
        ("d2", 2, "FIRST_SHOT_PASS"),
    ))
    bad_qwen = _result(QWEN, (
        ("d2", 2, "FIRST_SHOT_PASS"),
        ("d1", 1, "FIRST_SHOT_PASS"),
    ))

    def run_campaign(model_id: str, ladder: tuple[AtomicTask, ...]) -> RetryCampaignResult:
        events.append(("campaign", model_id))
        return good_small if model_id == SMALL else bad_qwen

    orchestrator = Orchestrator(
        load_model=lambda model_id: events.append(("load", model_id)),
        unload_model=lambda model_id: events.append(("unload", model_id)),
        run_campaign=run_campaign,
        replay_failures=lambda model_id, queue: (),
    )

    with pytest.raises(ValueError, match="matched task ladder"):
        orchestrator.run(
            small_model_id=SMALL,
            qwen_model_id=QWEN,
            devstral_model_id=DEVSTRAL,
            tasks=tasks,
        )

    assert events == [
        ("load", SMALL), ("campaign", SMALL), ("unload", SMALL),
        ("load", QWEN), ("campaign", QWEN), ("unload", QWEN),
    ]


def test_campaign_result_model_id_mismatch_is_rejected_inside_loaded_session() -> None:
    Orchestrator, _ = _api()
    tasks = (_task("d1", 1),)
    events: list[tuple[str, str]] = []
    wrong = _result("wrong-model", (("d1", 1, "FIRST_SHOT_PASS"),))

    orchestrator = Orchestrator(
        load_model=lambda model_id: events.append(("load", model_id)),
        unload_model=lambda model_id: events.append(("unload", model_id)),
        run_campaign=lambda model_id, ladder: wrong,
        replay_failures=lambda model_id, queue: (),
    )

    with pytest.raises(ValueError, match="model_id"):
        orchestrator.run(
            small_model_id=SMALL,
            qwen_model_id=QWEN,
            devstral_model_id=DEVSTRAL,
            tasks=tasks,
        )

    assert events == [("load", SMALL), ("unload", SMALL)]


def test_devstral_is_unloaded_even_when_batched_replay_raises() -> None:
    Orchestrator, _ = _api()
    tasks = (_task("d1", 1),)
    events: list[tuple[str, str]] = []
    campaigns = {
        SMALL: _result(SMALL, (("d1", 1, "HARD_FAILURE"),)),
        QWEN: _result(QWEN, (("d1", 1, "FIRST_SHOT_PASS"),)),
        DEVSTRAL: _result(DEVSTRAL, (("d1", 1, "FIRST_SHOT_PASS"),)),
    }

    def replay_failures(model_id: str, queue):
        events.append(("replay", model_id))
        raise RuntimeError("replay backend failed")

    orchestrator = Orchestrator(
        load_model=lambda model_id: events.append(("load", model_id)),
        unload_model=lambda model_id: events.append(("unload", model_id)),
        run_campaign=lambda model_id, ladder: (
            events.append(("campaign", model_id)) or campaigns[model_id]
        ),
        replay_failures=replay_failures,
    )

    with pytest.raises(RuntimeError, match="replay backend failed"):
        orchestrator.run(
            small_model_id=SMALL,
            qwen_model_id=QWEN,
            devstral_model_id=DEVSTRAL,
            tasks=tasks,
        )

    assert events[-4:] == [
        ("load", DEVSTRAL),
        ("campaign", DEVSTRAL),
        ("replay", DEVSTRAL),
        ("unload", DEVSTRAL),
    ]
    assert events.count(("load", DEVSTRAL)) == 1
    assert events.count(("unload", DEVSTRAL)) == 1


def test_three_model_ids_must_be_distinct_before_any_model_load() -> None:
    Orchestrator, _ = _api()
    events: list[tuple[str, str]] = []
    orchestrator = Orchestrator(
        load_model=lambda model_id: events.append(("load", model_id)),
        unload_model=lambda model_id: events.append(("unload", model_id)),
        run_campaign=lambda model_id, ladder: _result(model_id, ()),
        replay_failures=lambda model_id, queue: (),
    )

    with pytest.raises(ValueError, match="distinct"):
        orchestrator.run(
            small_model_id=QWEN,
            qwen_model_id=QWEN,
            devstral_model_id=DEVSTRAL,
            tasks=(_task("d1", 1),),
        )

    assert events == []
