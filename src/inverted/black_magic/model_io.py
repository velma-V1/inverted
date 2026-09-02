from __future__ import annotations

import json
from typing import Any

from inverted.models import MockModelAdapter, ModelCallError

from .budget import ExternalActionBudget
from .evidence import BlackMagicEvidenceStore
from .types import json_safe


def invoke_json_external(
    model: Any,
    messages: list[dict[str, str]],
    *,
    role: str,
    run_id: str,
    trial_id: str,
    call_id: str,
    budget: ExternalActionBudget,
    store: BlackMagicEvidenceStore,
    mock_payload: dict[str, Any] | None = None,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    sequence = budget.reserve(
        "model",
        {"call_id": call_id, "trial_id": trial_id, "role": role, "candidate_id": candidate_id},
    )
    store.append(
        "external_actions",
        {
            "sequence": sequence,
            "kind": "model",
            "call_id": call_id,
            "trial_id": trial_id,
            "role": role,
            "candidate_id": candidate_id,
        },
    )
    store.append(
        "prompts",
        {
            "call_id": call_id,
            "run_id": run_id,
            "trial_id": trial_id,
            "role": role,
            "candidate_id": candidate_id,
            "model": str(getattr(model, "model", "unknown")),
            "provider": str(getattr(model, "provider", "unknown")),
            "messages": messages,
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
                "parse_success": False,
                "error_class": record.error_class or type(exc).__name__,
                "error_message": record.error_message or str(exc),
            },
        )
        store.append("anomalies", {"type": "model_call_error", "call_id": call_id, "error": str(exc)})
        return {"ok": False, "parsed": None, "text": record.response, "record": record.to_dict(), "error": str(exc)}
    except Exception as exc:
        fallback = {
            "call_id": call_id,
            "run_id": run_id,
            "trial_id": trial_id,
            "candidate_id": candidate_id,
            "role": role,
            "model": str(getattr(model, "model", "unknown")),
            "provider": str(getattr(model, "provider", "unknown")),
            "parse_success": False,
            "parse_error": "NONCONFORMING_ADAPTER_EXCEPTION",
            "error_class": type(exc).__name__,
            "error_message": str(exc),
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
                "parse_success": False,
                "error_class": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        store.append("anomalies", {"type": "nonconforming_adapter_exception", **fallback})
        return {"ok": False, "parsed": None, "text": None, "record": fallback, "error": str(exc)}

    parsed: dict[str, Any] | None = None
    parse_error: str | None = None
    try:
        value = json.loads(result.text)
        if not isinstance(value, dict):
            raise ValueError("top-level model response must be a JSON object")
        parsed = value
        result.record.parse_success = True
        result.record.parse_error = None
    except Exception as exc:
        parse_error = f"{type(exc).__name__}: {exc}"
        result.record.parse_success = False
        result.record.parse_error = parse_error

    store.append("model_calls", result.record.to_dict())
    store.append(
        "responses",
        {
            "call_id": call_id,
            "run_id": run_id,
            "trial_id": trial_id,
            "response": result.text,
            "raw_provider_response": json_safe(result.raw),
            "parse_success": bool(result.record.parse_success),
            "parse_error": result.record.parse_error,
        },
    )
    if parse_error:
        store.append("anomalies", {"type": "response_parse_failure", "call_id": call_id, "error": parse_error})
    return {
        "ok": parsed is not None,
        "parsed": parsed,
        "text": result.text,
        "record": result.record.to_dict(),
        "raw": json_safe(result.raw),
        "error": parse_error,
    }
