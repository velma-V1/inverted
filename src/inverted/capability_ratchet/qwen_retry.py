"""Physical Qwen execution for Test1B-v3 retry interventions.

This boundary converts a declared RetryIngredient into exact Ollama requests while
keeping oracle/scoring material out of model-visible state. Every physical request
and response is returned as AttemptEvidence so failed attempts can be snapshotted
by the canonical TEST_REPLAY store without a parallel evidence path.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, fields, replace
from typing import Any

from inverted.universal_tuning.core import Profile
from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter
from inverted.universal_tuning.scoring import score_atomic_task

from .orchestration import AttemptContext, AttemptEvidence, AttemptOutcome


_PROFILE_FIELDS = frozenset(field.name for field in fields(Profile))
_SAFE_SCORE_FIELDS = (
    "completed",
    "semantic_pass",
    "contract_pass",
    "semantic_quality",
    "contract_quality",
    "reason",
)


def _plain(value: Any) -> Any:
    """Convert frozen replay values back to ordinary JSON-compatible containers."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _message_from_previous(outcome: AttemptOutcome) -> dict[str, Any] | None:
    evidence = outcome.evidence
    if not isinstance(evidence, AttemptEvidence):
        return None
    raw_calls = evidence.forensic_payload.get("raw_calls")
    if not isinstance(raw_calls, (list, tuple)) or not raw_calls:
        return None
    last_call = raw_calls[-1]
    if not isinstance(last_call, Mapping):
        return None
    response = last_call.get("response")
    if not isinstance(response, Mapping):
        return None
    message = response.get("message")
    if not isinstance(message, Mapping):
        return None

    result: dict[str, Any] = {"role": "assistant"}
    content = message.get("content")
    if isinstance(content, str):
        result["content"] = content
    thinking = message.get("thinking")
    if isinstance(thinking, str) and thinking:
        result["thinking"] = thinking
    if len(result) == 1:
        return None
    return result


def _safe_validator_packet(outcome: AttemptOutcome) -> dict[str, Any]:
    """Return validator evidence that cannot disclose oracle answers."""
    packet: dict[str, Any] = {
        "failure_classes": list(outcome.failure_classes),
        "failure_subtypes": list(outcome.failure_subtypes),
    }
    evidence = outcome.evidence
    if not isinstance(evidence, AttemptEvidence):
        return packet

    oracle = evidence.oracle_payload
    validator: dict[str, Any] = {}
    contract = oracle.get("contract")
    if isinstance(contract, str) and contract.strip():
        validator["contract"] = contract
    score = oracle.get("score")
    if isinstance(score, Mapping):
        safe_score = {
            key: _plain(score[key])
            for key in _SAFE_SCORE_FIELDS
            if key in score
        }
        if safe_score:
            validator["score"] = safe_score
    if validator:
        packet["validator"] = validator
    return packet


def _failure_feedback(context: AttemptContext) -> dict[str, Any] | str | None:
    ingredient = context.retry_ingredient
    previous = context.previous_outcome
    if ingredient is None or previous is None:
        return None

    mode = ingredient.failure_feedback_mode
    if mode == "NONE":
        return None
    if mode == "GENERIC":
        return "The previous attempt failed validation."
    if mode == "CLASS_ONLY":
        return {"failure_classes": list(previous.failure_classes)}
    if mode == "VIOLATED_REQUIREMENT":
        return {"failure_subtypes": list(previous.failure_subtypes)}
    if mode == "REQUIREMENT_WITH_REASON":
        packet: dict[str, Any] = {
            "failure_classes": list(previous.failure_classes),
            "failure_subtypes": list(previous.failure_subtypes),
        }
        evidence = previous.evidence
        if isinstance(evidence, AttemptEvidence):
            score = evidence.oracle_payload.get("score")
            if isinstance(score, Mapping) and isinstance(score.get("reason"), str):
                packet["reason"] = score["reason"]
        return packet
    if mode in {"VALIDATOR_EVIDENCE", "STRUCTURED_PACKET"}:
        return _safe_validator_packet(previous)
    raise ValueError(f"unsupported failure feedback mode: {mode}")


class QwenRetryAttemptExecutor:
    """Execute one Test1B-v3 attempt using the declared causal intervention."""

    def __init__(
        self,
        *,
        adapter: QwenOllamaAdapter,
        base_profile: Profile,
        seed: int,
    ) -> None:
        if not isinstance(adapter, QwenOllamaAdapter):
            raise TypeError("adapter must be a QwenOllamaAdapter")
        if not isinstance(base_profile, Profile):
            raise TypeError("base_profile must be a Profile")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("seed must be an integer")
        self._adapter = adapter
        self._base_profile = base_profile
        self._seed = seed

    def _effective_profile(self, context: AttemptContext) -> Profile:
        ingredient = context.retry_ingredient
        if ingredient is None:
            return self._base_profile
        overrides = dict(ingredient.profile_overrides)
        unknown = sorted(set(overrides) - _PROFILE_FIELDS)
        if unknown:
            raise ValueError(f"unknown Profile override(s): {', '.join(unknown)}")
        return replace(self._base_profile, **overrides)

    def _starting_messages(self, context: AttemptContext) -> list[dict[str, Any]]:
        base = [dict(item) for item in self._adapter._batch_messages((context.task,))]
        ingredient = context.retry_ingredient
        if ingredient is None:
            return base

        previous = context.previous_outcome
        if previous is None or not isinstance(previous.evidence, AttemptEvidence):
            raise ValueError("Qwen retry execution requires preceding AttemptEvidence")

        if ingredient.context_mode == "PRESERVE":
            envelopes = previous.evidence.request_envelopes
            if not envelopes:
                raise ValueError("PRESERVE retry requires a preceding request envelope")
            previous_request = envelopes[-1]
            previous_messages = previous_request.get("messages")
            if not isinstance(previous_messages, (list, tuple)):
                raise ValueError("preceding request envelope does not contain messages")
            messages = _plain(previous_messages)
            if not isinstance(messages, list):
                raise TypeError("preceding messages are not JSON-compatible")
        elif ingredient.context_mode in {"FRESH", "SELECTIVE_RESET"}:
            messages = base
        else:
            raise ValueError(f"unsupported retry context mode: {ingredient.context_mode}")

        previous_message = _message_from_previous(previous)
        if ingredient.context_mode in {"PRESERVE", "SELECTIVE_RESET"} and previous_message:
            messages.append(previous_message)

        feedback = _failure_feedback(context)
        retry_parts = [f"Response mode: {ingredient.response_mode}."]
        if feedback is not None:
            if isinstance(feedback, str):
                retry_parts.append(f"Failure feedback: {feedback}")
            else:
                retry_parts.append(
                    "Failure feedback: "
                    + json.dumps(feedback, sort_keys=True, separators=(",", ":"))
                )
        if ingredient.instruction is not None:
            retry_parts.append(f"Retry instruction: {ingredient.instruction}")
        messages.append({"role": "user", "content": "\n".join(retry_parts)})
        return messages

    def _request(
        self,
        *,
        context: AttemptContext,
        profile: Profile,
        messages: list[dict[str, Any]],
        think: bool,
        num_predict: int,
        thinking_phase: bool,
    ) -> dict[str, Any]:
        return {
            "model": self._adapter.model_id,
            "messages": messages,
            "stream": False,
            "think": think,
            "options": self._adapter._profile_options(
                (context.task,),
                profile,
                self._seed,
                num_predict=num_predict,
                thinking_phase=thinking_phase,
            ),
            **self._adapter._request_controls(profile),
        }

    def __call__(self, context: AttemptContext) -> AttemptOutcome:
        if not isinstance(context, AttemptContext):
            raise TypeError("context must be an AttemptContext")
        if context.model_id != self._adapter.model_id:
            raise ValueError("attempt model_id does not match Qwen adapter model_id")

        # Resolve and validate the complete intervention before any physical call.
        profile = self._effective_profile(context)
        messages = self._starting_messages(context)

        raw_calls: list[dict[str, Any]] = []
        total_latency = 0.0
        thinking_tokens = 0
        output_tokens = 0

        if not profile.thinking:
            request = self._request(
                context=context,
                profile=profile,
                messages=messages,
                think=False,
                num_predict=profile.final_max_tokens,
                thinking_phase=False,
            )
            raw, elapsed = self._adapter.post_chat_payload(request)
            raw_calls.append({"request": request, "response": raw})
            total_latency += elapsed
            output_tokens += int(raw.get("eval_count", 0) or 0)
            final_content = str((raw.get("message") or {}).get("content") or "")
        else:
            first_request = self._request(
                context=context,
                profile=profile,
                messages=messages,
                think=True,
                num_predict=profile.thinking_budget,
                thinking_phase=True,
            )
            first, first_elapsed = self._adapter.post_chat_payload(first_request)
            raw_calls.append({"request": first_request, "response": first})
            total_latency += first_elapsed
            first_tokens = int(first.get("eval_count", 0) or 0)
            thinking_tokens = first_tokens
            output_tokens += first_tokens

            first_message = first.get("message") or {}
            exposed_thinking = str(first_message.get("thinking") or "")
            partial_content = str(first_message.get("content") or "")
            carried = list(messages) + [
                {
                    "role": "assistant",
                    "thinking": exposed_thinking,
                    "content": partial_content,
                },
                {
                    "role": "user",
                    "content": (
                        "Using the exposed reasoning above, return only the final JSON "
                        "answer required by the original task."
                    ),
                },
            ]
            second_request = self._request(
                context=context,
                profile=profile,
                messages=carried,
                think=False,
                num_predict=profile.final_max_tokens,
                thinking_phase=False,
            )
            second, second_elapsed = self._adapter.post_chat_payload(second_request)
            raw_calls.append({"request": second_request, "response": second})
            total_latency += second_elapsed
            second_tokens = int(second.get("eval_count", 0) or 0)
            output_tokens += second_tokens
            final_content = str((second.get("message") or {}).get("content") or "")

        normalized_response = self._adapter._split_batch_response(
            final_content, (context.task,)
        )[0]
        score = score_atomic_task(context.task, normalized_response)
        passed = bool(score.completed and score.semantic_pass and score.contract_pass)
        failure_classes = () if passed else tuple(item.value for item in score.failure_classes)
        failure_subtypes = () if passed or not score.reason.strip() else (score.reason,)

        score_payload = {
            "completed": score.completed,
            "semantic_pass": score.semantic_pass,
            "contract_pass": score.contract_pass,
            "semantic_quality": score.semantic_quality,
            "contract_quality": score.contract_quality,
            "failure_classes": [item.value for item in score.failure_classes],
            "normalized_answer": score.normalized_answer,
            "reason": score.reason,
        }
        evidence = AttemptEvidence(
            request_envelopes=tuple(call["request"] for call in raw_calls),
            forensic_payload={
                "raw_calls": tuple(raw_calls),
                "telemetry": {
                    "latency_s": total_latency,
                    "output_tokens": output_tokens,
                    "thinking_tokens": thinking_tokens,
                    "physical_calls": len(raw_calls),
                },
            },
            oracle_payload={
                "task_id": context.task.task_id,
                "expected": context.task.expected,
                "contract": context.task.contract,
                "scorer": context.task.scorer,
                "score": score_payload,
            },
            inference_profile=asdict(profile),
            inference_seed=self._seed,
            source_evidence_refs=(
                f"test1b-v3:{context.model_id}:{context.task.task_id}:{context.stage}",
            ),
        )
        return AttemptOutcome(
            passed=passed,
            failure_classes=failure_classes,
            failure_subtypes=failure_subtypes,
            evidence=evidence,
        )
