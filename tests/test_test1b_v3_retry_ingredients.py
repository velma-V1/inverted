from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

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
from inverted.universal_tuning.core import AtomicTask


MODEL_ID = "qwen3.5:9b-q8_0"
MODEL_DIGEST = "b" * 64


def _task() -> AtomicTask:
    return AtomicTask(
        task_id="retry-causal-d4",
        family="LOGIC",
        difficulty=4,
        prompt="Return the only valid assignment.",
        expected={"answer": "B"},
        scorer="exact_value",
        contract="answer_object",
    )


def _evidence(stage: str) -> AttemptEvidence:
    request = {
        "model": MODEL_ID,
        "messages": ({"role": "user", "content": _task().prompt},),
        "stage": stage,
    }
    return AttemptEvidence(
        request_envelopes=(request,),
        forensic_payload={"response": {"content": "wrong"}, "stage": stage},
        oracle_payload={"expected": _task().expected, "semantic_pass": False},
        inference_profile={"thinking_budget": 1024, "temperature": 0.35},
        inference_seed=444,
        source_evidence_refs=(f"attempt:{stage}",),
    )


def _failure(stage: str, subtype: str) -> AttemptOutcome:
    return AttemptOutcome(
        passed=False,
        failure_classes=("SEMANTIC_FAIL",),
        failure_subtypes=(subtype,),
        evidence=_evidence(stage),
    )


def _retry_a() -> RetryIngredient:
    return RetryIngredient(
        "retry-a",
        "preserve-state-minimal-diagnostic",
        context_mode="PRESERVE",
        failure_feedback_mode="CLASS_ONLY",
        response_mode="REPAIR",
        instruction="Repair only the failed constraint; preserve valid work.",
        profile_overrides={"thinking_budget": 2048, "temperature": 0.2},
    )


def _retry_b() -> RetryIngredient:
    return RetryIngredient(
        "retry-b",
        "fresh-context-validator-evidence",
        context_mode="FRESH",
        failure_feedback_mode="VALIDATOR_EVIDENCE",
        response_mode="REGENERATE",
        instruction="Reconstruct from scratch using the validator evidence.",
        profile_overrides={"thinking_budget": 4096, "temperature": 0.45},
    )


def test_retry_ingredient_is_immutable_machine_readable_causal_intervention() -> None:
    overrides = {"thinking_budget": 2048, "temperature": 0.2}
    ingredient = RetryIngredient(
        "retry-a",
        "minimal-diagnostic-reset",
        context_mode="PRESERVE",
        failure_feedback_mode="CLASS_ONLY",
        response_mode="REPAIR",
        instruction="Repair only the failed constraint.",
        profile_overrides=overrides,
    )
    overrides["temperature"] = 9.9

    assert ingredient.profile_overrides["temperature"] == 0.2
    with pytest.raises(TypeError):
        ingredient.profile_overrides["temperature"] = 0.8

    assert ingredient.to_payload() == {
        "ingredient_id": "retry-a",
        "description": "minimal-diagnostic-reset",
        "context_mode": "PRESERVE",
        "failure_feedback_mode": "CLASS_ONLY",
        "response_mode": "REPAIR",
        "instruction": "Repair only the failed constraint.",
        "profile_overrides": {"thinking_budget": 2048, "temperature": 0.2},
    }


def test_existing_two_argument_retry_ingredient_callers_remain_valid() -> None:
    ingredient = RetryIngredient("retry-a", "legacy-compatible")

    assert ingredient.context_mode == "PRESERVE"
    assert ingredient.failure_feedback_mode == "NONE"
    assert ingredient.response_mode == "REGENERATE"
    assert ingredient.instruction is None
    assert dict(ingredient.profile_overrides) == {}


def test_retry_attempt_receives_immediately_preceding_failed_outcome() -> None:
    contexts: list[Any] = []
    outcomes: list[AttemptOutcome] = []

    def execute(context: Any) -> AttemptOutcome:
        contexts.append(context)
        if context.stage == "INITIAL":
            outcome = _failure("INITIAL", "WRONG_ASSIGNMENT")
        elif context.stage == "RETRY_A":
            outcome = _failure("RETRY_A", "CONSTRAINT_DRIFT")
        else:
            outcome = AttemptOutcome(passed=True)
        outcomes.append(outcome)
        return outcome

    orchestrator = RetryCampaignOrchestrator(
        execute_attempt=execute,
        snapshot_failure=lambda context, outcome: f"snapshot-{context.stage}",
        retry_a=_retry_a(),
        retry_b=_retry_b(),
    )
    result = orchestrator.run(model_id=MODEL_ID, tasks=(_task(),))

    assert result.task_results[0].status == "RECOVERED_RETRY_B"
    assert contexts[0].previous_outcome is None
    assert contexts[1].previous_outcome is outcomes[0]
    assert contexts[2].previous_outcome is outcomes[1]
    assert contexts[1].retry_ingredient is _retry_a() or contexts[1].retry_ingredient.to_payload() == _retry_a().to_payload()
    assert contexts[2].retry_ingredient.to_payload() == _retry_b().to_payload()


def test_snapshot_persists_complete_retry_intervention_for_causal_replay(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    snapshotter = ReplayFailureSnapshotter(
        store=store,
        source_campaign_id="test1b-v3-retry-causal",
        runtime_provenance={
            "provider": "ollama",
            "model": MODEL_ID,
            "model_digest": MODEL_DIGEST,
            "ollama_version": "0.32.15",
        },
        partition=Partition.DEVELOPMENT,
    )

    def execute(context: Any) -> AttemptOutcome:
        return _failure(context.stage, f"FAIL:{context.stage}")

    RetryCampaignOrchestrator(
        execute_attempt=execute,
        snapshot_failure=snapshotter,
        retry_a=_retry_a(),
        retry_b=_retry_b(),
    ).run(model_id=MODEL_ID, tasks=(_task(),))

    fixtures = tuple(record for record in store.records() if isinstance(record, FailureFixture))
    assert len(fixtures) == 3
    initial, retry_a, retry_b = fixtures

    assert initial.metadata["retry_intervention"] is None
    assert retry_a.metadata["retry_intervention"]["context_mode"] == "PRESERVE"
    assert retry_a.metadata["retry_intervention"]["failure_feedback_mode"] == "CLASS_ONLY"
    assert retry_a.metadata["retry_intervention"]["response_mode"] == "REPAIR"
    assert retry_a.metadata["retry_intervention"]["profile_overrides"]["thinking_budget"] == 2048
    assert retry_b.metadata["retry_intervention"]["context_mode"] == "FRESH"
    assert retry_b.metadata["retry_intervention"]["failure_feedback_mode"] == "VALIDATOR_EVIDENCE"
    assert retry_b.metadata["retry_intervention"]["response_mode"] == "REGENERATE"
    assert retry_b.metadata["retry_intervention"]["profile_overrides"]["thinking_budget"] == 4096
