from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any

import inverted.universal_tuning as tuning
from inverted.capability_ratchet import (
    AttemptEvidence,
    AttemptOutcome,
    Partition,
    ReplayFailureSnapshotter,
    RetryCampaignOrchestrator,
    RetryIngredient,
)
from inverted.capability_ratchet.core import FailureFixture
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.snapshot import _validate_first_request_profile
from inverted.universal_tuning.core import AtomicTask, FailureClass, Observation, Profile
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter


MODEL_ID = "qwen3.5:9b-q8_0"
MODEL_DIGEST = "b" * 64


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _task(task_id: str = "contract-repair") -> AtomicTask:
    return AtomicTask(
        task_id=task_id,
        family="TEST1B_V3",
        difficulty=4,
        prompt="Return the exact requested JSON answer.",
        expected={"answer": 4},
        scorer="exact_value",
    )


def _observation(budget: tuning.ThinkingBudget, *, index: int, passed: bool) -> Observation:
    return Observation(
        observation_id=f"obs:{budget}:{index}",
        batch_id=f"batch:{budget}",
        task_id=f"task:{budget}:{index}",
        family="LOGIC_CONSTRAINTS",
        stage="budget",
        profile=Profile(budget, 0.7),
        inference_seed=index,
        decision_reason="test1b-v3-contract-repair",
        semantic_pass=passed,
        contract_pass=True,
        completed=True,
        semantic_quality=1.0 if passed else 0.0,
        contract_quality=1.0,
        latency_s=1.0,
        output_tokens=16,
        thinking_tokens=32 if budget != 0 else 0,
        physical_calls=2 if budget != 0 else 1,
        response_text="ok" if passed else "wrong",
        failure_classes=() if passed else (FailureClass.SEMANTIC_FAIL,),
    )


def _retry_a() -> RetryIngredient:
    return RetryIngredient("retry-a", "strategy-a")


def _retry_b() -> RetryIngredient:
    return RetryIngredient("retry-b", "strategy-b")


def test_unrestricted_thinking_is_explicit_planned_and_maps_to_ollama_infinite_cap() -> None:
    unrestricted = tuning.UNRESTRICTED_THINKING
    profile = Profile(
        thinking_budget=unrestricted,
        temperature=0.7,
        final_max_tokens=333,
    )

    assert unrestricted == "unrestricted"
    assert profile.thinking is True
    assert profile.unrestricted_thinking is True
    axis = next(item for item in tuning.parameter_catalog() if item.name == "thinking_budget")
    assert unrestricted in axis.candidates
    planned = tuning.plan_profile_screen(Profile(0, 0.7), supports_thinking=True)
    assert sum(
        item.axis_name == "thinking_budget" and item.axis_value == unrestricted
        for item in planned
    ) == 1

    payloads: list[dict[str, Any]] = []
    responses = iter((
        {
            "model": MODEL_ID,
            "message": {"thinking": "natural reasoning", "content": ""},
            "eval_count": 111,
        },
        {
            "model": MODEL_ID,
            "message": {"content": '{"answer":4}'},
            "eval_count": 5,
        },
    ))

    def opener(request, *, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response(next(responses))

    result = QwenOllamaAdapter(opener=opener).complete((_task(),), profile, seed=99)

    assert result.physical_calls == 2
    assert payloads[0]["think"] is True
    assert payloads[0]["options"]["num_predict"] == -1
    assert payloads[1]["think"] is False
    assert payloads[1]["options"]["num_predict"] == 333


def test_unrestricted_thinking_is_separate_from_numeric_curve_and_replay_exact() -> None:
    unrestricted = tuning.UNRESTRICTED_THINKING
    observations = tuple(
        _observation(budget, index=index, passed=(budget != 0))
        for budget in (0, 256, unrestricted)
        for index in range(2)
    )

    result = tuning.analyze_thinking_curve(
        observations,
        success_threshold=0.5,
        min_observations_per_budget=2,
        material_delta=0.05,
    )

    assert [point.thinking_budget for point in result.points] == [0, 256]
    assert result.optimum_budget == 256
    assert result.unrestricted_point is not None
    assert result.unrestricted_point.thinking_budget == unrestricted
    assert result.unrestricted_point.success_rate == 1.0

    observation = next(
        row for row in observations if row.profile.thinking_budget == unrestricted
    )
    _validate_first_request_profile(
        observation,
        [{
            "think": True,
            "options": {
                "seed": observation.inference_seed,
                "temperature": 0.7,
                "num_predict": -1,
            },
        }],
    )


def test_retry_strategies_are_deterministically_counterbalanced_across_failed_initials() -> None:
    seen: dict[str, list[Any]] = defaultdict(list)

    def execute(context):
        if context.stage != "INITIAL":
            seen[context.task.task_id].append(context)
        if context.stage == "INITIAL" or context.attempt_index == 1:
            return AttemptOutcome(
                passed=False,
                failure_classes=("SEMANTIC_FAIL",),
            )
        return AttemptOutcome(passed=True)

    result = RetryCampaignOrchestrator(
        execute_attempt=execute,
        snapshot_failure=lambda context, outcome: (
            f"{context.task.task_id}:{context.stage}:{context.attempt_index}"
        ),
        retry_a=_retry_a(),
        retry_b=_retry_b(),
    ).run(
        model_id=MODEL_ID,
        tasks=tuple(_task(f"task-{index}") for index in range(5)),
    )

    orders = [
        [context.retry_ingredient.ingredient_id for context in seen[f"task-{index}"]]
        for index in range(5)
    ]
    assert orders == [
        ["retry-a", "retry-b"],
        ["retry-b", "retry-a"],
        ["retry-a", "retry-b"],
        ["retry-b", "retry-a"],
        ["retry-a", "retry-b"],
    ]
    assert all(
        [context.attempt_index for context in seen[f"task-{index}"]] == [1, 2]
        for index in range(5)
    )
    assert [item.status for item in result.task_results] == [
        "RECOVERED_RETRY_B",
        "RECOVERED_RETRY_A",
        "RECOVERED_RETRY_B",
        "RECOVERED_RETRY_A",
        "RECOVERED_RETRY_B",
    ]
    assert [item.retry_order for item in result.task_results] == [
        ("RETRY_A", "RETRY_B"),
        ("RETRY_B", "RETRY_A"),
        ("RETRY_A", "RETRY_B"),
        ("RETRY_B", "RETRY_A"),
        ("RETRY_A", "RETRY_B"),
    ]


def _attempt_evidence(context) -> AttemptEvidence:
    request = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": context.task.prompt}],
        "stage": context.stage,
        "attempt_index": context.attempt_index,
    }
    return AttemptEvidence(
        request_envelopes=(request,),
        forensic_payload={"response": "wrong"},
        oracle_payload={"expected": context.task.expected},
        inference_profile={"thinking_budget": 0, "temperature": 0.7},
        inference_seed=17,
        source_evidence_refs=(
            f"attempt:{context.task.task_id}:{context.stage}:{context.attempt_index}",
        ),
    )


def test_retry_snapshot_separates_strategy_identity_from_retry_position(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    snapshotter = ReplayFailureSnapshotter(
        store=store,
        source_campaign_id="test1b-v3-counterbalance",
        runtime_provenance={
            "provider": "ollama",
            "model": MODEL_ID,
            "model_digest": MODEL_DIGEST,
            "ollama_version": "0.32.15",
        },
        partition=Partition.DEVELOPMENT,
    )

    def execute(context):
        return AttemptOutcome(
            passed=False,
            failure_classes=("SEMANTIC_FAIL",),
            evidence=_attempt_evidence(context),
        )

    RetryCampaignOrchestrator(
        execute_attempt=execute,
        snapshot_failure=snapshotter,
        retry_a=_retry_a(),
        retry_b=_retry_b(),
    ).run(
        model_id=MODEL_ID,
        tasks=(_task("task-0"), _task("task-1")),
    )

    fixtures = tuple(record for record in store.records() if isinstance(record, FailureFixture))
    task_one = [fixture for fixture in fixtures if fixture.focus_task_id == "task-1"]
    retry_one = next(item for item in task_one if item.metadata["attempt_index"] == 1)
    retry_two = next(item for item in task_one if item.metadata["attempt_index"] == 2)

    assert retry_one.metadata["retry_position"] == 1
    assert retry_one.metadata["retry_strategy"] == "RETRY_B"
    assert retry_one.metadata["retry_ingredient_id"] == "retry-b"
    assert retry_two.metadata["retry_position"] == 2
    assert retry_two.metadata["retry_strategy"] == "RETRY_A"
    assert retry_two.metadata["retry_ingredient_id"] == "retry-a"
