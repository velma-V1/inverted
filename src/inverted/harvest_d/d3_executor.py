from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import uuid
from typing import Any, Iterable, Mapping

from .cases import HarvestCase, score_response
from .d3_store import D3EvidenceStore
from .models import ModelAdapter, ModelResponse
from .types import stable_hash


@dataclass(frozen=True)
class D3CallPlan:
    case_id: str
    prompt: str
    system: str | None
    information_packet: Mapping[str, Any]
    scheduler_event: Mapping[str, Any]
    arm_id: str = "RAW"
    phase: str = "D3"
    case: HarvestCase | None = None


@dataclass(frozen=True)
class D3CallResult:
    physical_model_call_id: str
    case_id: str
    model_id: str
    text: str
    failure_class: str
    capture_admissibility: str
    previous_physical_model_call_id: str | None


@dataclass(frozen=True)
class ReproducibilityCalibration:
    calls_used: int
    observations: tuple[dict[str, Any], ...]


_KNOWN_RUNTIME_FIELDS = {
    "model",
    "created_at",
    "message",
    "done",
    "done_reason",
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
}


def _classify_text(text: str) -> tuple[str, Any]:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return "FORMAT_OR_SCHEMA", None
    if not isinstance(parsed, (dict, list)):
        return "FORMAT_OR_SCHEMA", parsed
    return "NONE", parsed


def _classify_score(score: Mapping[str, Any]) -> str:
    if not bool(score.get("parseable_json", False)):
        return "FORMAT_OR_SCHEMA"
    if not bool(score.get("schema_valid", False)):
        return "FORMAT_OR_SCHEMA"
    if bool(score.get("overall_semantic_correct", False)):
        return "CORRECT"
    answer = bool(score.get("answer_correct", False))
    disposition = bool(score.get("disposition_correct", False))
    if answer and not disposition:
        return "ANSWER_RIGHT_DISPOSITION_WRONG"
    if disposition and not answer:
        return "ANSWER_WRONG_DISPOSITION_RIGHT"
    return "BOTH_WRONG"


class D3CallExecutor:
    """Executes exactly one physical model call per plan and never retries."""

    def __init__(self, *, store: D3EvidenceStore) -> None:
        self.store = store
        self._previous_call_id = store.last_call_id

    def execute_once(self, plan: D3CallPlan, adapter: ModelAdapter) -> D3CallResult:
        physical_call_id = f"d3-call-{uuid.uuid4().hex}"
        previous = self._previous_call_id
        messages: list[dict[str, str]] = []
        if plan.system:
            messages.append({"role": "system", "content": plan.system})
        messages.append({"role": "user", "content": plan.prompt})
        raw_request = {
            "case_id": plan.case_id,
            "arm_id": plan.arm_id,
            "phase": plan.phase,
            "model_id": str(getattr(adapter, "model_id", "unknown")),
            "messages": messages,
            "generation_options": dict(getattr(adapter, "generation_options", {}) or {}),
        }

        score_fields: dict[str, Any] | None = None
        try:
            response = adapter.complete(plan.prompt, system=plan.system)
            if not isinstance(response, ModelResponse):
                raise TypeError("model adapter returned non-ModelResponse")
            failure_class, parsed = _classify_text(response.text)
            if plan.case is not None:
                score_fields = asdict(score_response(plan.case, response.text))
                failure_class = _classify_score(score_fields)
            raw_payload = dict(response.raw)
            runtime_extras = {
                key: value for key, value in raw_payload.items() if key not in _KNOWN_RUNTIME_FIELDS
            }
            raw_response = {"payload": raw_payload, "text": response.text}
            normalized_call = {
                "case_id": plan.case_id,
                "arm_id": plan.arm_id,
                "phase": plan.phase,
                "model_id": response.model,
                "text": response.text,
                "parsed_response": parsed,
                "failure_class": failure_class,
                "score": score_fields,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": response.latency_ms,
                "previous_physical_model_call_id": previous,
                "runtime_extras": runtime_extras,
                "raw_payload_hash": stable_hash(raw_payload),
            }
            runtime_telemetry = {
                "model": response.model,
                "latency_ms": response.latency_ms,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "done_reason": raw_payload.get("done_reason"),
                "total_duration": raw_payload.get("total_duration"),
                "load_duration": raw_payload.get("load_duration"),
                "prompt_eval_count": raw_payload.get("prompt_eval_count"),
                "eval_count": raw_payload.get("eval_count"),
                "previous_physical_model_call_id": previous,
                "extras": runtime_extras,
            }
        except Exception as exc:  # one physical attempt; error becomes evidence
            failure_class = "INFRASTRUCTURE_OR_ADAPTER"
            raw_response = {
                "payload": {},
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            normalized_call = {
                "case_id": plan.case_id,
                "arm_id": plan.arm_id,
                "phase": plan.phase,
                "model_id": str(getattr(adapter, "model_id", "unknown")),
                "text": "",
                "parsed_response": None,
                "failure_class": failure_class,
                "score": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0.0,
                "previous_physical_model_call_id": previous,
                "runtime_extras": {},
            }
            runtime_telemetry = {
                "error_type": type(exc).__name__,
                "previous_physical_model_call_id": previous,
            }

        score_raw = {
            "case_id": plan.case_id,
            "failure_class": failure_class,
            "oracle_revealed": False,
            "measurement": score_fields,
        }
        score_normalized = {
            "case_id": plan.case_id,
            "failure_class": failure_class,
            "semantic_result": (
                "PASS"
                if score_fields is not None and bool(score_fields.get("overall_semantic_correct"))
                else "FAIL"
                if score_fields is not None
                else "UNSCORED"
            ),
            "measurement": score_fields,
        }
        bundle = {
            "physical_model_call_id": physical_call_id,
            "raw_request": raw_request,
            "raw_response": raw_response,
            "normalized_call": normalized_call,
            "information_packet": dict(plan.information_packet),
            "score_raw": score_raw,
            "score_normalized": score_normalized,
            "runtime_telemetry": runtime_telemetry,
            "scheduler_event": dict(plan.scheduler_event),
        }
        status = self.store.append_call_bundle(bundle)
        self._previous_call_id = physical_call_id

        return D3CallResult(
            physical_model_call_id=physical_call_id,
            case_id=plan.case_id,
            model_id=str(normalized_call["model_id"]),
            text=str(normalized_call["text"]),
            failure_class=failure_class,
            capture_admissibility=status.admissibility.value,
            previous_physical_model_call_id=previous,
        )


def run_reproducibility_block(
    executor: D3CallExecutor,
    *,
    adapters: Iterable[ModelAdapter],
    plans: Iterable[D3CallPlan],
    repetitions: int = 3,
) -> ReproducibilityCalibration:
    adapter_list = tuple(adapters)
    plan_list = tuple(plans)
    observations: list[dict[str, Any]] = []
    for repetition in range(max(0, int(repetitions))):
        for plan in plan_list:
            for adapter in adapter_list:
                result = executor.execute_once(plan, adapter)
                observation = {
                    "physical_model_call_id": result.physical_model_call_id,
                    "case_id": result.case_id,
                    "model_id": result.model_id,
                    "repetition": repetition,
                    "text_hash": stable_hash(result.text),
                    "failure_class": result.failure_class,
                }
                executor.store.append_record("d3_reproducibility_calibration.jsonl", observation)
                observations.append(observation)
    return ReproducibilityCalibration(
        calls_used=len(observations),
        observations=tuple(observations),
    )
