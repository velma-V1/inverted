"""Deterministic bounded-retry orchestration for Test1B-v3 campaigns.

This module owns control flow only. Model execution and immutable failure capture are
injected so the campaign can reuse the existing runner and TEST_REPLAY snapshot store
without creating a second evidence system.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from inverted.universal_tuning.core import AtomicTask

from .core import _freeze, _json_value


_INITIAL = "INITIAL"
_RETRY_A = "RETRY_A"
_RETRY_B = "RETRY_B"

_FIRST_SHOT_PASS = "FIRST_SHOT_PASS"
_RECOVERED_RETRY_A = "RECOVERED_RETRY_A"
_RECOVERED_RETRY_B = "RECOVERED_RETRY_B"
_HARD_FAILURE = "HARD_FAILURE"

_CONTEXT_MODES = frozenset({"PRESERVE", "FRESH", "SELECTIVE_RESET"})
_FAILURE_FEEDBACK_MODES = frozenset({
    "NONE",
    "GENERIC",
    "CLASS_ONLY",
    "VIOLATED_REQUIREMENT",
    "REQUIREMENT_WITH_REASON",
    "VALIDATOR_EVIDENCE",
    "STRUCTURED_PACKET",
})
_RESPONSE_MODES = frozenset({"REPAIR", "REGENERATE"})
_RETRY_STRATEGIES = frozenset({_RETRY_A, _RETRY_B})


def _required(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _string_tuple(name: str, value: Any, *, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a sequence of strings")
    items = tuple(value)
    if not allow_empty and not items:
        raise ValueError(f"{name} must not be empty")
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise TypeError(f"{name} must contain non-blank strings")
    return items


@dataclass(frozen=True)
class RetryIngredient:
    """One declared, machine-readable intervention used after a failed attempt.

    Defaults intentionally preserve the original two-argument API: keep context,
    provide no failure feedback, regenerate, and leave the inference profile unchanged.
    """

    ingredient_id: str
    description: str
    context_mode: str = "PRESERVE"
    failure_feedback_mode: str = "NONE"
    response_mode: str = "REGENERATE"
    instruction: str | None = None
    profile_overrides: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required("ingredient_id", self.ingredient_id)
        _required("description", self.description)
        if self.context_mode not in _CONTEXT_MODES:
            raise ValueError(f"context_mode must be one of {sorted(_CONTEXT_MODES)}")
        if self.failure_feedback_mode not in _FAILURE_FEEDBACK_MODES:
            raise ValueError(
                "failure_feedback_mode must be one of "
                f"{sorted(_FAILURE_FEEDBACK_MODES)}"
            )
        if self.response_mode not in _RESPONSE_MODES:
            raise ValueError(f"response_mode must be one of {sorted(_RESPONSE_MODES)}")
        if self.instruction is not None:
            _required("instruction", self.instruction)
        if not isinstance(self.profile_overrides, Mapping):
            raise TypeError("profile_overrides must be a mapping")
        object.__setattr__(self, "profile_overrides", _freeze(self.profile_overrides))

    def to_payload(self) -> dict[str, Any]:
        """Return a stable JSON-compatible causal-intervention payload."""
        return {
            "ingredient_id": self.ingredient_id,
            "description": self.description,
            "context_mode": self.context_mode,
            "failure_feedback_mode": self.failure_feedback_mode,
            "response_mode": self.response_mode,
            "instruction": self.instruction,
            "profile_overrides": _json_value(self.profile_overrides),
        }


@dataclass(frozen=True)
class AttemptEvidence:
    """Exact evidence required to turn a failed attempt into TEST_REPLAY data."""

    request_envelopes: tuple[Mapping[str, Any], ...]
    forensic_payload: Mapping[str, Any]
    oracle_payload: Mapping[str, Any]
    inference_profile: Mapping[str, Any]
    inference_seed: int
    source_evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        envelopes = tuple(self.request_envelopes)
        if not envelopes or any(not isinstance(item, Mapping) for item in envelopes):
            raise TypeError("request_envelopes must contain at least one mapping")
        if not isinstance(self.forensic_payload, Mapping):
            raise TypeError("forensic_payload must be a mapping")
        if not isinstance(self.oracle_payload, Mapping):
            raise TypeError("oracle_payload must be a mapping")
        if not isinstance(self.inference_profile, Mapping):
            raise TypeError("inference_profile must be a mapping")
        if not isinstance(self.inference_seed, int) or isinstance(self.inference_seed, bool):
            raise TypeError("inference_seed must be an integer")
        refs = _string_tuple(
            "source_evidence_refs", self.source_evidence_refs, allow_empty=False
        )
        object.__setattr__(self, "request_envelopes", _freeze(envelopes))
        object.__setattr__(self, "forensic_payload", _freeze(self.forensic_payload))
        object.__setattr__(self, "oracle_payload", _freeze(self.oracle_payload))
        object.__setattr__(self, "inference_profile", _freeze(self.inference_profile))
        object.__setattr__(self, "source_evidence_refs", refs)


@dataclass(frozen=True)
class AttemptOutcome:
    """Normalized result returned by the model-specific attempt executor."""

    passed: bool
    failure_classes: tuple[str, ...] = ()
    failure_subtypes: tuple[str, ...] = ()
    evidence: AttemptEvidence | None = None

    def __post_init__(self) -> None:
        if type(self.passed) is not bool:
            raise TypeError("passed must be boolean")
        classes = _string_tuple(
            "failure_classes", self.failure_classes, allow_empty=self.passed
        )
        subtypes = _string_tuple(
            "failure_subtypes", self.failure_subtypes, allow_empty=True
        )
        if self.passed and (classes or subtypes):
            raise ValueError("passed outcomes cannot contain failure classes or subtypes")
        if self.evidence is not None and not isinstance(self.evidence, AttemptEvidence):
            raise TypeError("evidence must be AttemptEvidence or None")
        object.__setattr__(self, "failure_classes", classes)
        object.__setattr__(self, "failure_subtypes", subtypes)


@dataclass(frozen=True)
class AttemptContext:
    """System-owned context for exactly one physical/logical campaign attempt.

    For retries, ``stage`` is the strategy identity (RETRY_A or RETRY_B) while
    ``attempt_index`` is the retry position. They are intentionally independent so
    retry order can be counterbalanced without losing causal strategy identity.
    """

    model_id: str
    task: AtomicTask
    stage: str
    attempt_index: int
    retry_ingredient: RetryIngredient | None
    previous_outcome: AttemptOutcome | None = None

    def __post_init__(self) -> None:
        _required("model_id", self.model_id)
        if not isinstance(self.task, AtomicTask):
            raise TypeError("task must be an AtomicTask")
        if self.stage not in {_INITIAL, _RETRY_A, _RETRY_B}:
            raise ValueError("stage must be INITIAL, RETRY_A, or RETRY_B")
        if self.attempt_index not in {0, 1, 2}:
            raise ValueError("attempt_index must be 0, 1, or 2")
        if self.stage == _INITIAL:
            if self.attempt_index != 0 or self.retry_ingredient is not None:
                raise ValueError("INITIAL attempt cannot contain a retry ingredient")
            if self.previous_outcome is not None:
                raise ValueError("INITIAL attempt cannot contain a previous outcome")
        else:
            if self.attempt_index not in {1, 2}:
                raise ValueError("retry attempts require attempt_index 1 or 2")
            if not isinstance(self.retry_ingredient, RetryIngredient):
                raise TypeError("retry attempts require a RetryIngredient")
            if not isinstance(self.previous_outcome, AttemptOutcome):
                raise TypeError("retry attempts require the preceding AttemptOutcome")
            if self.previous_outcome.passed:
                raise ValueError("retry attempts require a failed previous outcome")


@dataclass(frozen=True)
class TaskCampaignResult:
    task_id: str
    difficulty: int
    status: str
    attempt_count: int
    failure_snapshot_ids: tuple[str, ...]
    retry_order: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required("task_id", self.task_id)
        if self.status not in {
            _FIRST_SHOT_PASS,
            _RECOVERED_RETRY_A,
            _RECOVERED_RETRY_B,
            _HARD_FAILURE,
        }:
            raise ValueError("invalid task campaign status")
        if self.attempt_count not in {1, 2, 3}:
            raise ValueError("attempt_count must be 1, 2, or 3")
        snapshots = tuple(self.failure_snapshot_ids)
        if any(not isinstance(item, str) or not item.strip() for item in snapshots):
            raise TypeError("failure_snapshot_ids must contain non-blank strings")
        retry_order = tuple(self.retry_order)
        if any(item not in _RETRY_STRATEGIES for item in retry_order):
            raise ValueError("retry_order may contain only RETRY_A and RETRY_B")
        if len(retry_order) not in {0, 2}:
            raise ValueError("retry_order must be empty or contain both retry strategies")
        if retry_order and set(retry_order) != _RETRY_STRATEGIES:
            raise ValueError("retry_order must contain RETRY_A and RETRY_B exactly once")
        object.__setattr__(self, "failure_snapshot_ids", snapshots)
        object.__setattr__(self, "retry_order", retry_order)


@dataclass(frozen=True)
class RetryCampaignResult:
    model_id: str
    task_results: tuple[TaskCampaignResult, ...]

    def __post_init__(self) -> None:
        _required("model_id", self.model_id)
        results = tuple(self.task_results)
        if any(not isinstance(item, TaskCampaignResult) for item in results):
            raise TypeError("task_results must contain TaskCampaignResult values")
        object.__setattr__(self, "task_results", results)

    @property
    def hard_failure_task_ids(self) -> tuple[str, ...]:
        return tuple(
            item.task_id for item in self.task_results if item.status == _HARD_FAILURE
        )

    @property
    def total_attempts(self) -> int:
        return sum(item.attempt_count for item in self.task_results)


AttemptExecutor = Callable[[AttemptContext], AttemptOutcome]
FailureSnapshotter = Callable[[AttemptContext, AttemptOutcome], str]


class RetryCampaignOrchestrator:
    """Run a task ladder with at most two declared recovery interventions per failure."""

    def __init__(
        self,
        *,
        execute_attempt: AttemptExecutor,
        snapshot_failure: FailureSnapshotter,
        retry_a: RetryIngredient,
        retry_b: RetryIngredient,
    ) -> None:
        if not callable(execute_attempt):
            raise TypeError("execute_attempt must be callable")
        if not callable(snapshot_failure):
            raise TypeError("snapshot_failure must be callable")
        if not isinstance(retry_a, RetryIngredient) or not isinstance(retry_b, RetryIngredient):
            raise TypeError("retry_a and retry_b must be RetryIngredient values")
        if retry_a.ingredient_id == retry_b.ingredient_id:
            raise ValueError("retry_a and retry_b must use distinct intervention identities")
        self._execute_attempt = execute_attempt
        self._snapshot_failure = snapshot_failure
        self._retry_a = retry_a
        self._retry_b = retry_b

    def _execute(self, context: AttemptContext) -> AttemptOutcome:
        outcome = self._execute_attempt(context)
        if not isinstance(outcome, AttemptOutcome):
            raise TypeError("execute_attempt must return AttemptOutcome")
        return outcome

    def _snapshot(self, context: AttemptContext, outcome: AttemptOutcome) -> str:
        snapshot_id = self._snapshot_failure(context, outcome)
        _required("failure snapshot id", snapshot_id)
        return snapshot_id

    def run(self, *, model_id: str, tasks: Iterable[AtomicTask]) -> RetryCampaignResult:
        _required("model_id", model_id)
        task_list = tuple(tasks)
        if any(not isinstance(task, AtomicTask) for task in task_list):
            raise TypeError("tasks must contain AtomicTask values")
        task_ids = tuple(task.task_id for task in task_list)
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("campaign task_ids must be unique")

        results: list[TaskCampaignResult] = []
        failed_initial_ordinal = 0
        for task in task_list:
            snapshots: list[str] = []

            initial = AttemptContext(
                model_id=model_id,
                task=task,
                stage=_INITIAL,
                attempt_index=0,
                retry_ingredient=None,
                previous_outcome=None,
            )
            initial_outcome = self._execute(initial)
            if initial_outcome.passed:
                results.append(TaskCampaignResult(
                    task_id=task.task_id,
                    difficulty=task.difficulty,
                    status=_FIRST_SHOT_PASS,
                    attempt_count=1,
                    failure_snapshot_ids=(),
                    retry_order=(),
                ))
                continue
            snapshots.append(self._snapshot(initial, initial_outcome))

            if failed_initial_ordinal % 2 == 0:
                retry_plan = (
                    (_RETRY_A, self._retry_a),
                    (_RETRY_B, self._retry_b),
                )
            else:
                retry_plan = (
                    (_RETRY_B, self._retry_b),
                    (_RETRY_A, self._retry_a),
                )
            failed_initial_ordinal += 1
            retry_order = tuple(stage for stage, _ in retry_plan)

            previous_outcome = initial_outcome
            recovered = False
            for attempt_index, (stage, ingredient) in enumerate(retry_plan, 1):
                retry = AttemptContext(
                    model_id=model_id,
                    task=task,
                    stage=stage,
                    attempt_index=attempt_index,
                    retry_ingredient=ingredient,
                    previous_outcome=previous_outcome,
                )
                retry_outcome = self._execute(retry)
                if retry_outcome.passed:
                    results.append(TaskCampaignResult(
                        task_id=task.task_id,
                        difficulty=task.difficulty,
                        status=(
                            _RECOVERED_RETRY_A
                            if stage == _RETRY_A
                            else _RECOVERED_RETRY_B
                        ),
                        attempt_count=attempt_index + 1,
                        failure_snapshot_ids=tuple(snapshots),
                        retry_order=retry_order,
                    ))
                    recovered = True
                    break
                snapshots.append(self._snapshot(retry, retry_outcome))
                previous_outcome = retry_outcome

            if recovered:
                continue
            results.append(TaskCampaignResult(
                task_id=task.task_id,
                difficulty=task.difficulty,
                status=_HARD_FAILURE,
                attempt_count=3,
                failure_snapshot_ids=tuple(snapshots),
                retry_order=retry_order,
            ))

        return RetryCampaignResult(model_id=model_id, task_results=tuple(results))
