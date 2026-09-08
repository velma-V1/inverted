from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailureClass(str, Enum):
    SEMANTIC_FAIL = "SEMANTIC_FAIL"
    CONTRACT_FAIL = "CONTRACT_FAIL"
    COMPLETION_FAIL = "COMPLETION_FAIL"
    CAPABILITY_LIMIT = "CAPABILITY_LIMIT"
    PARAMETER_SENSITIVITY = "PARAMETER_SENSITIVITY"
    INFRASTRUCTURE_FAIL = "INFRASTRUCTURE_FAIL"
    PROVENANCE_FAIL = "PROVENANCE_FAIL"
    SCORER_INVALID = "SCORER_INVALID"


@dataclass(frozen=True)
class AtomicTask:
    task_id: str
    family: str
    difficulty: int
    prompt: str
    expected: Any
    scorer: str
    contract: str = "answer_object"
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class Profile:
    thinking_budget: int
    temperature: float
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    presence_penalty: float | None = None
    repeat_penalty: float | None = None
    typical_p: float | None = None
    repeat_last_n: int | None = None
    frequency_penalty: float | None = None
    num_keep: int | None = None
    num_ctx: int = 8192
    num_batch: int | None = None
    num_gpu: int | None = None
    main_gpu: int | None = None
    use_mmap: bool | None = None
    num_thread: int | None = None
    draft_num_predict: int | None = None
    final_max_tokens: int = 768
    stop: tuple[str, ...] = ()
    truncate: bool | None = None
    shift: bool | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None

    @property
    def thinking(self) -> bool:
        return self.thinking_budget > 0


@dataclass(frozen=True)
class AtomicScore:
    completed: bool
    semantic_pass: bool
    contract_pass: bool
    semantic_quality: float
    contract_quality: float
    failure_classes: tuple[FailureClass, ...] = ()
    normalized_answer: Any = None
    reason: str = ""


@dataclass(frozen=True)
class Observation:
    observation_id: str
    batch_id: str
    task_id: str
    family: str
    stage: str
    profile: Profile
    inference_seed: int
    decision_reason: str
    semantic_pass: bool
    contract_pass: bool
    completed: bool
    semantic_quality: float
    contract_quality: float
    latency_s: float
    output_tokens: int
    thinking_tokens: int
    physical_calls: int
    response_text: str
    failure_classes: tuple[FailureClass, ...] = ()
    raw_call_refs: tuple[str, ...] = ()
    metadata: tuple[tuple[str, Any], ...] = field(default_factory=tuple)
