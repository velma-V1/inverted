from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from typing import Any

from inverted.models import MockModelAdapter, ModelCallError

from .budget import PhysicalCallBudget
from .evidence import EvidenceStore
from .types import json_safe


def _as_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return json_safe(asdict(value))
    return json_safe(value)


def invoke_json(
    model: Any,
    messages: list[dict[str, str]],
    *,
    role: str,
    run_id: str,
    trial_id: str,
    call_id: str,
    budget: PhysicalCallBudget,
    store: EvidenceStore,
    mock_payload: dict[str, Any] | None = None,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    """Invoke one physical model call and persist all observable data.

    Budget reservation happens before invocation. A transport/model/parser failure
    therefore consumes the same physical-call budget as a successful call.
    """

    store.append(
        "prompts",
        {
            "call_id": call_id,
            "run_id": run_id,
            "trial_id": trial_id,
            "candidate_id": candidate_id,
            "role": role,
            "model": str(getattr(model, "model", "unknown")),
            "provider": str(getattr(model, "provider", "unknown")),
            "messages": messages,
        },
    )
    sequence = budget.reserve(call_id=call_id, trial_id=trial_id, role=role)
    store.event(
        "physical_call_reserved",
        {
            "call_id": call_id,
            "trial_id": trial_id,
            "role": role,
            "physical_call_sequence": sequence,
            "budget_used": budget.used,
            "budget_remaining": budget.remaining,
        },
    )

    context: dict[str, Any] = {
        "run_id": run_id,
        "trial_id": trial_id,
        "call_id": call_id,
        "candidate_id": candidate_id,
    }
    if isinstance(model, MockModelAdapter):
        context["mock_text"] = json.dumps(mock_payload or {}, sort_keys=True, ensure_ascii=False)

    try:
        result = model.complete(messages, role=role, context=context)
    except ModelCallError as exc:
        record = exc.record
        record.parse_success = False
        record.parse_error = f"MODEL_CALL_ERROR: {exc}"
        store.append("model_calls", record.to_dict())
        store.append(
            "responses",
            {
                "call_id": call_id,
                "run_id": run_id,
                "trial_id": trial_id,
                "response": record.response,
                "raw_provider_response": None,
                "error_class": record.error_class or type(exc).__name__,
                "error_message": record.error_message or str(exc),
            },
        )
        store.append(
            "anomalies",
            {
                "type": "model_call_error",
                "call_id": call_id,
                "trial_id": trial_id,
                "error_class": record.error_class or type(exc).__name__,
                "error_message": record.error_message or str(exc),
            },
        )
        store.event(
            "model_call_failed",
            {
                "call_id": call_id,
                "trial_id": trial_id,
                "physical_call_sequence": sequence,
                "budget_used": budget.used,
            },
        )
        return {
            "ok": False,
            "parsed": None,
            "text": record.response,
            "record": record.to_dict(),
            "raw": None,
            "error": record.error_message or str(exc),
        }
    except Exception as exc:
        # Existing adapters are expected to normalize inference failures into
        # ModelCallError. Preserve an explicit synthetic observation only for a
        # nonconforming adapter so no reserved physical call disappears.
        fallback = {
            "call_id": call_id,
            "run_id": run_id,
            "trial_id": trial_id,
            "candidate_id": candidate_id,
            "role": role,
            "model": str(getattr(model, "model", "unknown")),
            "provider": str(getattr(model, "provider", "unknown")),
            "start_ts": None,
            "end_ts": None,
            "latency_s": 0.0,
            "ttft_s": None,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "reasoning_tokens": None,
            "cached_tokens": None,
            "cache_write_tokens": None,
            "prompt_eval_duration_s": None,
            "eval_duration_s": None,
            "load_duration_s": None,
            "generated_tokens_per_s": None,
            "end_to_end_tokens_per_s": None,
            "status_code": None,
            "error_class": type(exc).__name__,
            "error_message": str(exc),
            "timeout": False,
            "retry_number": 0,
            "retry_reason": None,
            "finish_reason": None,
            "parse_success": False,
            "parse_error": "NONCONFORMING_ADAPTER_EXCEPTION",
            "params": {},
            "cost_usd": None,
            "raw_usage": {},
            "raw_provider_telemetry": {},
            "prompt": messages,
            "response": None,
        }
        store.append("model_calls", fallback)
        store.append(
            "responses",
            {
                "call_id": call_id,
                "run_id": run_id,
                "trial_id": trial_id,
                "response": None,
                "raw_provider_response": None,
                "error_class": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        store.append("anomalies", {"type": "nonconforming_adapter_exception", **fallback})
        store.event("model_call_failed", {"call_id": call_id, "trial_id": trial_id, "physical_call_sequence": sequence})
        return {"ok": False, "parsed": None, "text": None, "record": fallback, "raw": None, "error": str(exc)}

    parsed: Any = None
    parse_error: str | None = None
    try:
        parsed = json.loads(result.text)
        if not isinstance(parsed, dict):
            raise ValueError("top-level model response must be a JSON object")
        result.record.parse_success = True
        result.record.parse_error = None
    except Exception as exc:
        result.record.parse_success = False
        parse_error = f"{type(exc).__name__}: {exc}"
        result.record.parse_error = parse_error

    store.append("model_calls", result.record.to_dict())
    store.append(
        "responses",
        {
            "call_id": call_id,
            "run_id": run_id,
            "trial_id": trial_id,
            "response": result.text,
            "raw_provider_response": _as_jsonable(result.raw),
            "parse_success": result.record.parse_success,
            "parse_error": result.record.parse_error,
        },
    )
    if parse_error is not None:
        store.append(
            "anomalies",
            {
                "type": "response_parse_failure",
                "call_id": call_id,
                "trial_id": trial_id,
                "parse_error": parse_error,
                "response": result.text,
            },
        )
    store.event(
        "model_call_completed",
        {
            "call_id": call_id,
            "trial_id": trial_id,
            "physical_call_sequence": sequence,
            "parse_success": bool(result.record.parse_success),
            "budget_used": budget.used,
            "budget_remaining": budget.remaining,
        },
    )
    return {
        "ok": parsed is not None,
        "parsed": parsed,
        "text": result.text,
        "record": result.record.to_dict(),
        "raw": _as_jsonable(result.raw),
        "error": parse_error,
    }
