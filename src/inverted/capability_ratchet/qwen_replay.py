"""Frozen-request replay adapter for Qwen/Ollama."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter

from .core import FailureFixture, ReplayMode, ReplayRequest
from .replay import ReplayCompletion

ReplayScorer = Callable[[FailureFixture, str], tuple[bool, bool, tuple[str, ...]]]


def _json_copy(value: Any, *, name: str) -> Any:
    try:
        return json.loads(json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite JSON data") from exc


class QwenReplayAdapter:
    def __init__(self, qwen: QwenOllamaAdapter, *, scorer: ReplayScorer | None) -> None:
        if not isinstance(qwen, QwenOllamaAdapter):
            raise TypeError("qwen must be a QwenOllamaAdapter")
        self.qwen = qwen
        self.scorer = scorer

    def runtime_provenance(self) -> Mapping[str, Any]:
        return self.qwen.runtime_provenance()

    def execute_fixture(
        self,
        fixture: FailureFixture,
        visible_payload: Mapping[str, Any],
        request: ReplayRequest,
    ) -> ReplayCompletion:
        if self.scorer is None:
            raise ValueError("replay scorer is required before model execution")
        envelopes = visible_payload.get("request_envelopes")
        if not isinstance(envelopes, list) or not envelopes:
            raise ValueError("replay fixture requires request_envelopes")
        if self.qwen.model_id != request.target_model_id:
            raise ValueError("Qwen replay adapter target model mismatch")

        raw_calls: list[dict[str, Any]] = []
        elapsed_total = 0.0
        output_tokens = 0
        thinking_tokens = 0
        final_text = ""
        completed = True
        for index, frozen in enumerate(envelopes):
            if not isinstance(frozen, Mapping):
                raise ValueError(f"request envelope {index} must be an object")
            payload = _json_copy(frozen, name=f"request envelope {index}")
            if request.mode is ReplayMode.CROSS_MODEL:
                payload["model"] = request.target_model_id
            elif payload.get("model") != request.target_model_id:
                raise ValueError("same-model replay payload model mismatch")

            raw, elapsed = self.qwen.post_chat_payload(payload)
            raw_calls.append({"request": payload, "response": raw})
            elapsed_total += elapsed
            tokens = int(raw.get("eval_count", 0) or 0)
            output_tokens += tokens
            if bool(payload.get("think")):
                thinking_tokens += tokens
            if raw.get("done") is False:
                completed = False
            message = raw.get("message") or {}
            if isinstance(message, Mapping):
                final_text = str(message.get("content") or "")

        semantic_pass, contract_pass, failure_classes = self.scorer(fixture, final_text)
        if type(semantic_pass) is not bool or type(contract_pass) is not bool:
            raise TypeError("replay scorer must return boolean semantic/contract results")
        classes = tuple(failure_classes)
        if any(not isinstance(item, str) or not item for item in classes):
            raise TypeError("replay scorer failure classes must be non-blank strings")
        if not completed and "COMPLETION_FAIL" not in classes:
            classes = classes + ("COMPLETION_FAIL",)

        return ReplayCompletion(
            completed=completed,
            semantic_pass=semantic_pass,
            contract_pass=contract_pass,
            output_payload={"text": final_text},
            raw_calls=tuple(raw_calls),
            failure_classes=classes,
            metrics={
                "latency_s": elapsed_total,
                "physical_calls": len(raw_calls),
                "output_tokens": output_tokens,
                "thinking_tokens": thinking_tokens,
            },
        )


class V2ReplayScorer:
    """Score one frozen V2 fixture using only verified replay-corpus assets."""

    def __init__(self, store) -> None:
        from .replay_store import ReplayStore
        if not isinstance(store, ReplayStore):
            raise TypeError("store must be ReplayStore")
        self.store = store

    def __call__(self, fixture: FailureFixture, final_text: str) -> tuple[bool, bool, tuple[str, ...]]:
        from inverted.universal_tuning.core import AtomicTask
        from inverted.universal_tuning.scoring import score_atomic_task

        if fixture.oracle_asset_sha256 is None:
            raise ValueError("fixture has no self-contained oracle asset")
        payload = self.store.read_asset(fixture.oracle_asset_sha256)
        if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
            raise ValueError("fixture oracle asset is malformed")
        tasks = []
        for row in payload["tasks"]:
            if not isinstance(row, dict):
                raise ValueError("fixture oracle task row is malformed")
            tasks.append(AtomicTask(
                task_id=str(row["task_id"]), family=str(row["family"]),
                difficulty=int(row["difficulty"]), prompt=str(row["prompt"]),
                expected=row.get("expected"), scorer=str(row["scorer"]),
                contract=str(row["contract"]),
                metadata=tuple(tuple(item) for item in row.get("metadata", ())),
            ))
        batch = tuple(tasks)
        if tuple(task.task_id for task in batch) != tuple(fixture.batch_task_ids):
            raise ValueError("fixture oracle task order does not match replay batch")
        try:
            focus_index = fixture.batch_task_ids.index(fixture.focus_task_id)
        except ValueError as exc:
            raise ValueError("fixture focus task is absent from oracle batch") from exc
        responses = QwenOllamaAdapter._split_batch_response(final_text, batch)
        score = score_atomic_task(batch[focus_index], responses[focus_index])
        classes = tuple(
            item.value if hasattr(item, "value") else str(item)
            for item in score.failure_classes
        )
        return score.semantic_pass, score.contract_pass, classes
