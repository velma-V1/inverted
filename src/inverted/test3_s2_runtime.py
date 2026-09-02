from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from typing import Any, Callable

from .domain import Action, Candidate, TaskCase
from .models import MockModelAdapter, ModelCallError
from .oracle import apply_actions, evaluate_task
from .system_executor import generate_candidate
from .test2_local import BoundedModelCaller
from .test2_types import PhysicalCallBudget
from .test3_s1_r3_runtime import compose_repair_patch
from .test3_s1_runtime import _call_row, _public_task, public_failure_feedback
from .test3_s2_budget import CombinedActionBudget
from .test3_s2_cases import S2ExecutionCase, S2_HOLDOUT, S2_PROTOCOL_REVISION, build_seed_failure_s2, fixture_seed_s2
from .test3_s2_forensics import S2ForensicJournal
from .test3_s2_policy import INTERVENTION_LIBRARY, REAL_ARM_IDS, public_router_state, select_action


S2_MATCHED_CASES = 72
S2_CALLS_PER_ARM_TASK = 2
S2_ARM_COUNT = 5
S2_TRIAL_COUNT = S2_MATCHED_CASES * S2_ARM_COUNT
S2_PER_ARM_CALL_CAP = S2_MATCHED_CASES * S2_CALLS_PER_ARM_TASK
S2_EXACT_BUDGET = S2_TRIAL_COUNT * S2_CALLS_PER_ARM_TASK
S2_PROVENANCE_API_CALL_BUDGET = 12
S2_COMBINED_ACTION_BUDGET = S2_EXACT_BUDGET + S2_PROVENANCE_API_CALL_BUDGET
S2_QWEN_MODEL = "qwen3.5:9b-q8_0"
S2_REPAIR_MODEL = "cogito:3b-v1-preview-llama-q8_0"
S2_LLAMA_MODEL = "llama3.1:8b"
S2_MODEL_NAMES = (S2_QWEN_MODEL, S2_REPAIR_MODEL, S2_LLAMA_MODEL)

FailureInjector = Callable[[str, dict[str, Any]], None]


class _RawCaptureProxy:
    def __init__(self, adapter: Any, capture: dict[str, Any]):
        self._adapter = adapter
        self._capture = capture

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)

    def complete(self, messages: list[dict[str, str]], *, role: str, context: dict[str, Any]):
        try:
            result = self._adapter.complete(messages, role=role, context=context)
        except ModelCallError as exc:
            self._capture["error_record"] = exc.record.to_dict() if hasattr(exc.record, "to_dict") else {}
            raise
        self._capture["raw"] = result.raw
        return result


class S2BoundedModelCaller(BoundedModelCaller):
    """S2 caller that retains the provider payload discarded by the legacy bounded caller."""

    def complete(
        self,
        model: Any,
        messages: list[dict[str, str]],
        *,
        role: str,
        context: dict[str, Any],
        response_schema: Any = None,
        allow_cache: bool = True,
    ):
        capture: dict[str, Any] = {}
        proxy = _RawCaptureProxy(model, capture)
        item = super().complete(
            proxy,
            messages,
            role=role,
            context=context,
            response_schema=response_schema,
            allow_cache=allow_cache,
        )
        item.raw = capture.get("raw")
        item.raw_error_record = capture.get("error_record")
        return item


def _assert_public_prompt(messages: list[dict[str, str]]) -> None:
    text = json.dumps(messages, sort_keys=True)
    forbidden = (
        '"critical"',
        "target_state",
        "hidden_gold",
        "injected_fault",
        "perturbation_class",
        "private_fixture_label",
        "s2_seed_failure",
        "stress_case",
    )
    leaked = [term for term in forbidden if term in text]
    if leaked:
        raise AssertionError("S2 public prompt boundary violated: " + ", ".join(leaked))


def _result(task: TaskCase, candidate: Candidate | None) -> dict[str, Any]:
    if candidate is None:
        return {
            "success": False,
            "catastrophic": False,
            "passed_requirements": [],
            "failed_requirements": ["parse_or_execution"],
        }
    item = evaluate_task(task, candidate.state, candidate.actions)
    return {
        "success": bool(item.success),
        "catastrophic": bool(item.catastrophic),
        "passed_requirements": list(item.passed_requirement_ids),
        "failed_requirements": list(item.failed_requirement_ids),
    }


def _candidate_snapshot(candidate: Candidate | None) -> dict[str, Any]:
    if candidate is None:
        return {"id": None, "state": None, "actions": []}
    return {
        "id": candidate.id,
        "state": candidate.state.to_dict(),
        "actions": [action.to_dict() for action in candidate.actions],
    }


def _diagnostic(stage: str | None = None, exc: BaseException | None = None) -> dict[str, Any]:
    return {
        "failure_stage": stage,
        "error_class": type(exc).__name__ if exc is not None else None,
        "error": str(exc) if exc is not None else None,
    }


def decode_s2_candidate_response(task: TaskCase, text: str, candidate_id: str) -> tuple[Candidate | None, dict[str, Any]]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, _diagnostic("response_json_parse_failure", exc)
    try:
        rows = value.get("actions") if isinstance(value, dict) else None
        if not isinstance(rows, list):
            raise ValueError("response must be an object containing an actions list")
        actions = tuple(Action(str(row["op"]), str(row["path"]), row.get("value")) for row in rows)
    except (KeyError, TypeError, ValueError) as exc:
        return None, _diagnostic("response_schema_or_action_decode_failure", exc)
    try:
        state = apply_actions(task.initial_state, actions)
    except Exception as exc:
        return None, _diagnostic("action_application_failure", exc)
    return Candidate(candidate_id, state, actions, configured_quality=1.0), _diagnostic()


def decode_s2_repair_response(
    task: TaskCase,
    candidate: Candidate | None,
    text: str,
    failed_ids: list[str],
    candidate_id: str,
) -> tuple[Candidate | None, dict[str, Any]]:
    try:
        value = json.loads(text)
        rows = value.get("actions") if isinstance(value, dict) else None
        if not isinstance(rows, list):
            raise ValueError("repair response must be an object containing an actions list")
        patch = tuple(Action(str(row["op"]), str(row["path"]), row.get("value")) for row in rows)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return None, _diagnostic("repair_patch_parse_failure", exc)
    try:
        proposed = compose_repair_patch(task, candidate, patch, failed_ids, candidate_id)
    except Exception as exc:
        return None, _diagnostic("repair_patch_composition_failure", exc)
    return proposed, _diagnostic()


def _provider_diagnostic(completion: Any) -> dict[str, Any] | None:
    record = getattr(completion, "record", None)
    error_class = str(getattr(record, "error_class", "") or "")
    if not error_class:
        return None
    error_message = str(getattr(record, "error_message", "") or "")
    if error_class == "GENERATION_CENSORED":
        stage = "generation_censored"
    elif error_class == "EmptyModelResponse":
        stage = "empty_model_response"
    else:
        stage = "model_transport_failure"
    return {"failure_stage": stage, "error_class": error_class, "error": error_message}


def _failure_signature(task: TaskCase, failed_ids: list[str]) -> str:
    by_id = {req.id: req for req in task.requirements}
    parts: list[str] = []
    for req_id in failed_ids:
        req = by_id.get(str(req_id))
        if req is None:
            parts.append(str(req_id))
        elif req.kind == "action_before":
            parts.append(f"action_before:{req.path}>{req.expected}")
        elif req.kind == "action_present":
            parts.append(f"action_present:{req.path}@{req.expected}")
        else:
            parts.append(f"{req.kind}:{req.path}")
    return "|".join(sorted(parts)) or "none"


def failure_state(
    task: TaskCase,
    candidate: Candidate | None,
    deterministic_result: dict[str, Any],
    *,
    previous_action: str | None,
    previous_model: str | None,
    retry_count: int,
    budget_spent: int,
    budget_remaining: int,
) -> dict[str, Any]:
    failed_ids = [str(value) for value in (deterministic_result.get("failed_requirements") or [])]
    by_id = {req.id: req for req in task.requirements}
    kinds = [by_id[item].kind if item in by_id else "parse_or_execution" for item in failed_ids]
    return {
        "family": task.family,
        "complexity": int(task.complexity),
        "failed_requirement_ids": failed_ids,
        "failed_requirement_kinds": kinds,
        "failed_count": len(failed_ids),
        "failure_signature": _failure_signature(task, failed_ids),
        "deterministic_success": bool(deterministic_result.get("success")),
        "catastrophic": bool(deterministic_result.get("catastrophic")),
        "previous_action": previous_action,
        "previous_model": previous_model,
        "retry_count": int(retry_count),
        "budget_spent": int(budget_spent),
        "budget_remaining": int(budget_remaining),
        "candidate_action_count": len(candidate.actions) if candidate is not None else 0,
    }


def _model_for_action(action: str) -> tuple[str, str]:
    if action == "retry_qwen":
        return S2_QWEN_MODEL, "executor"
    if action == "repair_cogito":
        return S2_REPAIR_MODEL, "repairer"
    if action == "switch_llama":
        return S2_LLAMA_MODEL, "executor"
    raise ValueError(f"unknown S2 intervention: {action}")


def _mock_text(task: TaskCase, *, repair: bool) -> str:
    valid = generate_candidate(task, 1.0, 9_999_991)
    if not evaluate_task(task, valid.state, valid.actions).success:
        raise AssertionError("S2 mock fixture could not generate valid candidate")
    return json.dumps({"actions": [action.to_dict() for action in valid.actions]}, sort_keys=True)


def _messages_for_action(action: str, task: TaskCase, candidate: Candidate | None, status: dict[str, Any]) -> list[dict[str, str]]:
    payload = _public_task(task)
    if action == "repair_cogito":
        payload = payload | {
            "previous_actions": [item.to_dict() for item in candidate.actions] if candidate else [],
            "validator_feedback": public_failure_feedback(task, candidate, list(status.get("failed_requirements") or [])),
        }
        system = (
            "Return ONLY a JSON repair patch {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. "
            "Include only actions needed to fix failed public requirements. The runtime composes the patch onto prior correct work."
        )
    else:
        system = (
            "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. "
            "Produce a complete replacement action plan satisfying every supplied machine-checkable requirement with no unintended actions."
        )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]
    _assert_public_prompt(messages)
    return messages


def _journal(
    journal: S2ForensicJournal | None,
    event_type: str,
    payload: Any,
    *,
    run_id: str,
    arm_id: str | None = None,
    task_id: str | None = None,
    step_index: int | None = None,
    trial_id: str | None = None,
    call_id: str | None = None,
) -> None:
    if journal is not None:
        journal.append(
            event_type,
            payload,
            trial_id=trial_id,
            call_id=call_id,
            arm_id=arm_id,
            task_id=task_id,
            step_index=step_index,
        )


def _inject(failure_injector: FailureInjector | None, point: str, payload: dict[str, Any]) -> None:
    if failure_injector is not None:
        failure_injector(point, payload)


def _request_payload(model: Any, messages: list[dict[str, str]], role: str) -> dict[str, Any]:
    builder = getattr(model, "_payload", None)
    if callable(builder):
        value = builder(messages, role)
        if isinstance(value, dict):
            return value
    return {
        "model": str(getattr(model, "model", "unknown")),
        "messages": messages,
        "role": role,
    }


def _execute_call(
    *,
    caller: S2BoundedModelCaller,
    action_budget: CombinedActionBudget,
    action: str,
    model: Any,
    task: TaskCase,
    candidate: Candidate | None,
    status: dict[str, Any],
    run_id: str,
    arm_id: str,
    case_id: str,
    step_index: int,
    active: bool,
    journal: S2ForensicJournal | None,
    external_action_ledger: list[dict[str, Any]],
    failure_injector: FailureInjector | None,
) -> tuple[Candidate | None, dict[str, Any]]:
    model_name, role = _model_for_action(action)
    if str(getattr(model, "model", "")) != model_name:
        raise ValueError(f"S2 model adapter mismatch for {action}: expected {model_name}")
    before_snapshot = _candidate_snapshot(candidate)
    messages = _messages_for_action(action, task, candidate, status)
    call_id = f"{run_id}-{arm_id}-{case_id}-{step_index}-{action}-{'active' if active else 'shadow'}"
    trial_id = f"{case_id}-{arm_id}"
    request_payload = _request_payload(model, messages, role)
    context = {
        "run_id": run_id,
        "trial_id": trial_id,
        "candidate_id": candidate.id if candidate is not None else None,
        "call_id": call_id,
    }
    if isinstance(model, MockModelAdapter) or str(getattr(model, "provider", "")) == "mock":
        context["mock_text"] = _mock_text(task, repair=(action == "repair_cogito"))

    _journal(
        journal,
        "model_request_prepared",
        {
            "action": action,
            "model": model_name,
            "role": role,
            "active_intervention": active,
            "messages": messages,
            "provider_request_payload": request_payload,
            "candidate_before": before_snapshot,
        },
        run_id=run_id,
        arm_id=arm_id,
        task_id=case_id,
        step_index=step_index,
        trial_id=trial_id,
        call_id=call_id,
    )
    action_budget.reserve("model_call")
    ledger_row = {
        "kind": "model_call",
        "run_id": run_id,
        "trial_id": trial_id,
        "call_id": call_id,
        "arm_id": arm_id,
        "task_id": case_id,
        "step_index": step_index,
        "action": action,
        "model": model_name,
        "budget_after_reservation": action_budget.snapshot(),
    }
    external_action_ledger.append(ledger_row)
    _journal(
        journal,
        "external_action_reserved",
        ledger_row,
        run_id=run_id,
        arm_id=arm_id,
        task_id=case_id,
        step_index=step_index,
        trial_id=trial_id,
        call_id=call_id,
    )
    _inject(failure_injector, "after_model_budget_reserved", ledger_row)
    _journal(
        journal,
        "model_call_started",
        {"physical_call_number_expected": caller.budget.physical_calls + 1, "model": model_name, "role": role},
        run_id=run_id,
        arm_id=arm_id,
        task_id=case_id,
        step_index=step_index,
        trial_id=trial_id,
        call_id=call_id,
    )

    completion = caller.complete(
        model,
        messages,
        role=role,
        context=context,
        response_schema={"type": "object"},
        allow_cache=False,
    )
    telemetry = completion.record.to_dict() if hasattr(completion.record, "to_dict") else {}
    _journal(
        journal,
        "model_call_completed",
        {
            "physical_call_number": completion.physical_call_number,
            "logical_call_index": completion.logical_index,
            "prompt_fingerprint": completion.identity,
            "response": completion.response,
            "raw_provider_response": getattr(completion, "raw", None),
            "raw_error_record": getattr(completion, "raw_error_record", None),
            "telemetry": telemetry,
        },
        run_id=run_id,
        arm_id=arm_id,
        task_id=case_id,
        step_index=step_index,
        trial_id=trial_id,
        call_id=call_id,
    )
    _inject(
        failure_injector,
        "after_model_completion_before_processing",
        {"call_id": call_id, "physical_call_number": completion.physical_call_number},
    )

    provider_failure = _provider_diagnostic(completion)
    if provider_failure is not None:
        proposed = None
        diagnostic = provider_failure
    elif action == "repair_cogito":
        proposed, diagnostic = decode_s2_repair_response(
            task,
            candidate,
            completion.text,
            list(status.get("failed_requirements") or []),
            f"{case_id}-{arm_id}-s2-repair-{step_index}",
        )
    else:
        proposed, diagnostic = decode_s2_candidate_response(
            task,
            completion.text,
            f"{case_id}-{arm_id}-{action}-{step_index}",
        )

    if hasattr(completion.record, "parse_success"):
        completion.record.parse_success = diagnostic.get("failure_stage") is None
        completion.record.parse_error = diagnostic.get("error")
        telemetry = completion.record.to_dict()

    proposed_snapshot = _candidate_snapshot(proposed)
    proposed_status = _result(task, proposed)
    _journal(
        journal,
        "transformation_result",
        {
            "action": action,
            "diagnostic": diagnostic,
            "proposed_candidate": proposed_snapshot,
            "proposed_status": proposed_status,
        },
        run_id=run_id,
        arm_id=arm_id,
        task_id=case_id,
        step_index=step_index,
        trial_id=trial_id,
        call_id=call_id,
    )

    row = _call_row(
        completion,
        arm_id=arm_id,
        task_id=case_id,
        component=action,
        role=role,
        model=model_name,
        active_intervention=active,
    )
    response = str(row.get("response") or "")
    row.update({
        "step_index": int(step_index),
        "action_selected": action,
        "prompt_fingerprint": completion.identity,
        "response_digest": hashlib.sha256(response.encode("utf-8")).hexdigest(),
        "provider_request_payload": request_payload,
        "raw_provider_response": getattr(completion, "raw", None),
        "raw_error_record": getattr(completion, "raw_error_record", None),
        "failure_stage": diagnostic.get("failure_stage"),
        "failure_detail": diagnostic,
        "candidate_before_id": before_snapshot["id"],
        "candidate_before_state": before_snapshot["state"],
        "candidate_before_actions": before_snapshot["actions"],
        "proposed_candidate_id": proposed_snapshot["id"],
        "proposed_candidate_state": proposed_snapshot["state"],
        "proposed_candidate_actions": proposed_snapshot["actions"],
        "proposed_success": bool(proposed_status.get("success")),
        "proposed_catastrophic": bool(proposed_status.get("catastrophic")),
        "proposed_passed_requirements": list(proposed_status.get("passed_requirements") or []),
        "proposed_failed_requirements": list(proposed_status.get("failed_requirements") or []),
        "counterfactual_evaluated": not active,
        "telemetry": telemetry,
    })
    return proposed, row


def _arm_order(case_index: int) -> tuple[str, ...]:
    shift = int(case_index) % len(REAL_ARM_IDS)
    return REAL_ARM_IDS[shift:] + REAL_ARM_IDS[:shift]


def _random_seed(case_index: int, arm_id: str) -> int:
    payload = f"S2-R1|{case_index}|{arm_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def detect_stochastic_divergence(model_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in model_calls:
        fingerprint = str(row.get("prompt_fingerprint") or row.get("call_identity") or "")
        if fingerprint:
            grouped[fingerprint].append(row)
    findings: list[dict[str, Any]] = []
    for fingerprint, rows in grouped.items():
        digests = sorted({str(row.get("response_digest") or "") for row in rows})
        if len(digests) <= 1:
            continue
        outcomes = {
            (
                bool(row.get("proposed_success", row.get("success_after"))),
                bool(row.get("proposed_catastrophic", row.get("catastrophic_after"))),
            )
            for row in rows
        }
        findings.append({
            "classification": "STOCHASTIC_RESPONSE_DIVERGENCE",
            "prompt_fingerprint": fingerprint,
            "model": rows[0].get("model"),
            "call_count": len(rows),
            "response_digests": digests,
            "call_identities": [row.get("call_identity") for row in rows],
            "arm_ids": [row.get("arm_id") for row in rows],
            "task_ids": [row.get("task_id") for row in rows],
            "responses": [row.get("response") for row in rows],
            "telemetry": [row.get("telemetry") for row in rows],
            "raw_provider_responses": [row.get("raw_provider_response") for row in rows],
            "proposed_outcomes": [
                {
                    "success": bool(row.get("proposed_success", row.get("success_after"))),
                    "catastrophic": bool(row.get("proposed_catastrophic", row.get("catastrophic_after"))),
                }
                for row in rows
            ],
            "outcome_changed": len(outcomes) > 1,
        })
    return findings


def _validate_inputs(cases: list[S2ExecutionCase], model_by_name: dict[str, Any], exact_budget: int) -> None:
    if exact_budget != S2_EXACT_BUDGET:
        raise ValueError("S2-R1 requires exact 720-call inference budget")
    if len(cases) != S2_MATCHED_CASES:
        raise ValueError("S2-R1 requires exactly 72 Holdout B cases")
    if any(not str(case.case_id).startswith("test3-s2-BR1-") for case in cases):
        raise ValueError("S2-R1 received case outside Holdout B-R1")
    for name in S2_MODEL_NAMES:
        if name not in model_by_name:
            raise ValueError(f"missing S2 model adapter: {name}")
        retries = int(getattr(model_by_name[name], "max_retries", 0) or 0)
        if retries != 0:
            raise ValueError("S2 model adapters must disable transport retries")


def _holdout_manifest(cases: list[S2ExecutionCase]) -> list[dict[str, Any]]:
    """Preserve private fixture/selection provenance without exposing it to routers or prompts."""
    manifest: list[dict[str, Any]] = []
    for case in cases:
        seed = build_seed_failure_s2(case)
        status = _result(case.task, seed)
        by_id = {req.id: req for req in case.task.requirements}
        failed_ids = list(status.get("failed_requirements") or [])
        manifest.append({
            "task_id": case.case_id,
            "base_task_id": case.metadata.get("base_task_id"),
            "family": case.task.family,
            "complexity": int(case.task.complexity),
            "perturbation_class": case.metadata.get("perturbation_class"),
            "selected_seed": int(case.metadata.get("selected_seed")),
            "seed_scan_offset": int(case.metadata.get("seed_scan_offset")),
            "requirement_count": int(case.metadata.get("requirement_count")),
            "fixture_seed": int(seed.metadata.get("fixture_seed") or fixture_seed_s2(case)),
            "fixture_candidate_id": seed.id,
            "fixture_candidate_metadata": dict(seed.metadata),
            "fixture_injected_faults": list(seed.injected_faults),
            "fixture_actions": [action.to_dict() for action in seed.actions],
            "fixture_state": seed.state.to_dict(),
            "initial_success": bool(status.get("success")),
            "initial_catastrophic": bool(status.get("catastrophic")),
            "initial_passed_requirements": list(status.get("passed_requirements") or []),
            "initial_failed_requirements": failed_ids,
            "initial_failed_requirement_kinds": [by_id[item].kind if item in by_id else "parse_or_execution" for item in failed_ids],
            "public_task": _public_task(case.task),
        })
    return manifest


def _runtime_payload(
    *,
    run_id: str,
    exact_budget: int,
    combined: CombinedActionBudget,
    physical: PhysicalCallBudget,
    holdout_manifest: list[dict[str, Any]],
    trials: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    validators: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    events: list[dict[str, Any]],
    external_action_ledger: list[dict[str, Any]],
    action_start: int,
    complete: bool,
    journal: S2ForensicJournal | None,
) -> dict[str, Any]:
    call_counts = Counter(str(row.get("arm_id")) for row in calls)
    arm_accounting = [
        {
            "arm_id": arm_id,
            "planned_physical_calls": S2_PER_ARM_CALL_CAP,
            "actual_physical_calls": int(call_counts.get(arm_id, 0)),
            "matched_cases": sum(1 for row in trials if row.get("arm_id") == arm_id),
            "calls_per_case": S2_CALLS_PER_ARM_TASK,
        }
        for arm_id in REAL_ARM_IDS
    ]
    raw_transactions = [{
        "arm_id": row.get("arm_id"),
        "task_id": row.get("task_id"),
        "base_task_id": row.get("base_task_id"),
        "step_index": row.get("step_index"),
        "action_selected": row.get("action_selected"),
        "model": row.get("model"),
        "role": row.get("role"),
        "call_identity": row.get("call_identity"),
        "physical_call_number": row.get("physical_call_number"),
        "prompt": row.get("prompt"),
        "provider_request_payload": row.get("provider_request_payload"),
        "response": row.get("response"),
        "raw_provider_response": row.get("raw_provider_response"),
        "raw_error_record": row.get("raw_error_record"),
        "telemetry": row.get("telemetry"),
    } for row in calls]
    failures = [{
        "arm_id": row.get("arm_id"),
        "task_id": row.get("task_id"),
        "base_task_id": row.get("base_task_id"),
        "step_index": row.get("step_index"),
        "action_selected": row.get("action_selected"),
        "model": row.get("model"),
        "call_identity": row.get("call_identity"),
        "response": row.get("response"),
        "raw_provider_response": row.get("raw_provider_response"),
        "raw_error_record": row.get("raw_error_record"),
        "failure_stage": row.get("failure_stage"),
        "failure_detail": row.get("failure_detail"),
    } for row in calls if row.get("failure_stage")]
    return {
        "run_id": run_id,
        "protocol_revision": S2_PROTOCOL_REVISION,
        "holdout": S2_HOLDOUT,
        "execution_mode": "balanced_task_blocks",
        "exact_budget": exact_budget,
        "combined_action_budget_limit": combined.limit,
        "matched_cases": S2_MATCHED_CASES,
        "trial_count": S2_TRIAL_COUNT,
        "physical_model_calls": physical.physical_calls,
        "inference_action_delta": combined.used - action_start,
        "action_budget": combined.snapshot(),
        "holdout_manifest": holdout_manifest,
        "trials": trials,
        "model_calls": calls,
        "validator_results": validators,
        "routing_decisions": decisions,
        "routing_state_snapshots": snapshots,
        "events": events,
        "arm_accounting": arm_accounting,
        "stochastic_divergence": detect_stochastic_divergence(calls),
        "real_model_inference": False,
        "intervention_library": list(INTERVENTION_LIBRARY),
        "raw_model_transactions": raw_transactions,
        "parse_and_composition_failures": failures,
        "external_action_ledger": external_action_ledger,
        "journal_integrity": journal.snapshot_integrity() if journal is not None else {},
        "runtime_complete": bool(complete),
    }


def run_s2_screen(
    *,
    cases: list[S2ExecutionCase],
    model_by_name: dict[str, Any],
    run_id: str,
    exact_budget: int = S2_EXACT_BUDGET,
    action_budget: CombinedActionBudget | None = None,
    journal: S2ForensicJournal | None = None,
    failure_injector: FailureInjector | None = None,
) -> dict[str, Any]:
    _validate_inputs(cases, model_by_name, exact_budget)
    physical = PhysicalCallBudget(max_calls=exact_budget)
    caller = S2BoundedModelCaller(physical)
    combined = action_budget if action_budget is not None else CombinedActionBudget(S2_COMBINED_ACTION_BUDGET)
    if combined.remaining < exact_budget:
        raise ValueError("S2 shared action budget does not have room for the exact 720 inference actions")
    action_start = combined.used
    holdout_manifest = _holdout_manifest(cases)
    trials: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    validators: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    external_action_ledger: list[dict[str, Any]] = []

    _journal(
        journal,
        "runtime_started",
        {
            "protocol_revision": S2_PROTOCOL_REVISION,
            "holdout": S2_HOLDOUT,
            "exact_budget": exact_budget,
            "combined_action_budget": combined.snapshot(),
            "matched_cases": len(cases),
        },
        run_id=run_id,
    )
    _journal(journal, "holdout_manifest_ready", {"rows": holdout_manifest}, run_id=run_id)

    try:
        for case_index, case in enumerate(cases):
            for execution_position, arm_id in enumerate(_arm_order(case_index)):
                seed = build_seed_failure_s2(case)
                candidate: Candidate | None = seed
                status = _result(case.task, candidate)
                initial_status = dict(status)
                initial_candidate = _candidate_snapshot(candidate)
                previous_action: str | None = None
                previous_model: str | None = None
                selected_actions: list[str] = []
                selected_models: list[str] = []
                trial_calls: list[dict[str, Any]] = []
                trial_id = f"{case.case_id}-{arm_id}"
                _journal(
                    journal,
                    "trial_started",
                    {
                        "base_task_id": case.metadata.get("base_task_id"),
                        "execution_position": execution_position,
                        "initial_candidate": initial_candidate,
                        "initial_status": initial_status,
                    },
                    run_id=run_id,
                    arm_id=arm_id,
                    task_id=case.case_id,
                    trial_id=trial_id,
                )

                for step_index in (0, 1):
                    evidence = failure_state(
                        case.task,
                        candidate,
                        status,
                        previous_action=previous_action,
                        previous_model=previous_model,
                        retry_count=step_index,
                        budget_spent=combined.used,
                        budget_remaining=combined.remaining,
                    )
                    router_view = public_router_state(arm_id, evidence)
                    action = select_action(
                        arm_id,
                        evidence,
                        step_index=step_index,
                        random_seed=_random_seed(case_index, arm_id),
                    )
                    model_name, _ = _model_for_action(action)
                    active = not bool(status.get("success"))
                    decision = {
                        "arm_id": arm_id,
                        "task_id": case.case_id,
                        "base_task_id": case.metadata["base_task_id"],
                        "step_index": step_index,
                        "action_selected": action,
                        "model_selected": model_name,
                        "active_intervention": active,
                        "shadow_only": not active,
                        "evidence_state": router_view,
                        "full_public_state": evidence,
                        "execution_position": execution_position,
                    }
                    decisions.append(decision)
                    snapshots.append({
                        "arm_id": arm_id,
                        "task_id": case.case_id,
                        "step_index": step_index,
                        "state": evidence,
                        "router_view": router_view,
                    })
                    _journal(
                        journal,
                        "router_decision",
                        decision,
                        run_id=run_id,
                        arm_id=arm_id,
                        task_id=case.case_id,
                        step_index=step_index,
                        trial_id=trial_id,
                    )
                    _inject(failure_injector, "after_router_decision", decision)

                    proposed, call = _execute_call(
                        caller=caller,
                        action_budget=combined,
                        action=action,
                        model=model_by_name[model_name],
                        task=case.task,
                        candidate=candidate,
                        status=status,
                        run_id=run_id,
                        arm_id=arm_id,
                        case_id=case.case_id,
                        step_index=step_index,
                        active=active,
                        journal=journal,
                        external_action_ledger=external_action_ledger,
                        failure_injector=failure_injector,
                    )
                    before = dict(status)
                    if active:
                        candidate = proposed
                        status = _result(case.task, candidate)
                    after = dict(status)
                    after_candidate = _candidate_snapshot(candidate)
                    call.update({
                        "base_task_id": case.metadata["base_task_id"],
                        "perturbation_class": case.metadata["perturbation_class"],
                        "execution_position": execution_position,
                        "success_before": bool(before.get("success")),
                        "catastrophic_before": bool(before.get("catastrophic")),
                        "success_after": bool(after.get("success")),
                        "catastrophic_after": bool(after.get("catastrophic")),
                        "candidate_after_id": after_candidate["id"],
                        "candidate_after_state": after_candidate["state"],
                        "candidate_after_actions": after_candidate["actions"],
                    })
                    calls.append(call)
                    trial_calls.append(call)
                    validator = {
                        "arm_id": arm_id,
                        "task_id": case.case_id,
                        "step_index": step_index,
                        "stage": "post_action_deterministic_validator",
                        "active_intervention": active,
                        "shadow_only": not active,
                        "success": bool(after.get("success")),
                        "catastrophic": bool(after.get("catastrophic")),
                        "passed_requirements": list(after.get("passed_requirements") or []),
                        "failed_requirements": list(after.get("failed_requirements") or []),
                        "proposed_success": bool(call.get("proposed_success")),
                        "proposed_catastrophic": bool(call.get("proposed_catastrophic")),
                        "proposed_passed_requirements": list(call.get("proposed_passed_requirements") or []),
                        "proposed_failed_requirements": list(call.get("proposed_failed_requirements") or []),
                        "counterfactual_evaluated": bool(call.get("counterfactual_evaluated")),
                        "candidate_before_id": call.get("candidate_before_id"),
                        "candidate_before_state": call.get("candidate_before_state"),
                        "candidate_before_actions": call.get("candidate_before_actions"),
                        "proposed_candidate_id": call.get("proposed_candidate_id"),
                        "proposed_candidate_state": call.get("proposed_candidate_state"),
                        "proposed_candidate_actions": call.get("proposed_candidate_actions"),
                        "candidate_after_id": call.get("candidate_after_id"),
                        "candidate_after_state": call.get("candidate_after_state"),
                        "candidate_after_actions": call.get("candidate_after_actions"),
                        "failure_stage": call.get("failure_stage"),
                        "failure_detail": call.get("failure_detail"),
                    }
                    validators.append(validator)
                    _journal(
                        journal,
                        "validator_result",
                        validator,
                        run_id=run_id,
                        arm_id=arm_id,
                        task_id=case.case_id,
                        step_index=step_index,
                        trial_id=trial_id,
                    )
                    event = {
                        "event": "s2_action_observed",
                        "arm_id": arm_id,
                        "task_id": case.case_id,
                        "step_index": step_index,
                        "action": action,
                        "model": model_name,
                        "active": active,
                        "success_after": bool(after.get("success")),
                        "catastrophic_after": bool(after.get("catastrophic")),
                        "proposed_success": bool(call.get("proposed_success")),
                        "proposed_catastrophic": bool(call.get("proposed_catastrophic")),
                        "counterfactual_evaluated": bool(call.get("counterfactual_evaluated")),
                        "candidate_before_id": call.get("candidate_before_id"),
                        "proposed_candidate_id": call.get("proposed_candidate_id"),
                        "candidate_after_id": call.get("candidate_after_id"),
                        "failure_stage": call.get("failure_stage"),
                    }
                    events.append(event)
                    _journal(
                        journal,
                        "state_transition",
                        {
                            "before": before,
                            "after": after,
                            "candidate_after": after_candidate,
                            "event": event,
                        },
                        run_id=run_id,
                        arm_id=arm_id,
                        task_id=case.case_id,
                        step_index=step_index,
                        trial_id=trial_id,
                    )
                    selected_actions.append(action)
                    selected_models.append(model_name)
                    previous_action = action
                    previous_model = model_name

                final_candidate = _candidate_snapshot(candidate)
                trial = {
                    "protocol_revision": S2_PROTOCOL_REVISION,
                    "holdout": S2_HOLDOUT,
                    "arm_id": arm_id,
                    "task_id": case.case_id,
                    "base_task_id": case.metadata["base_task_id"],
                    "family": case.task.family,
                    "complexity": int(case.task.complexity),
                    "perturbation_class": case.metadata["perturbation_class"],
                    "selected_seed": case.metadata.get("selected_seed"),
                    "seed_scan_offset": case.metadata.get("seed_scan_offset"),
                    "requirement_count": case.metadata.get("requirement_count"),
                    "fixture_seed": seed.metadata.get("fixture_seed"),
                    "execution_position": execution_position,
                    "initial_candidate_id": initial_candidate["id"],
                    "initial_candidate_state": initial_candidate["state"],
                    "initial_candidate_actions": initial_candidate["actions"],
                    "initial_success": bool(initial_status.get("success")),
                    "initial_catastrophic": bool(initial_status.get("catastrophic")),
                    "initial_failed_requirements": list(initial_status.get("failed_requirements") or []),
                    "final_candidate_id": final_candidate["id"],
                    "final_candidate_state": final_candidate["state"],
                    "final_candidate_actions": final_candidate["actions"],
                    "success": bool(status.get("success")),
                    "catastrophic": bool(status.get("catastrophic")),
                    "final_failed_requirements": list(status.get("failed_requirements") or []),
                    "actions_selected": selected_actions,
                    "models_selected": selected_models,
                    "calls_used": len(trial_calls),
                    "active_calls": sum(bool(row.get("active_intervention")) for row in trial_calls),
                    "shadow_calls": sum(bool(row.get("shadow_only")) for row in trial_calls),
                    "complete": len(trial_calls) == S2_CALLS_PER_ARM_TASK,
                }
                trials.append(trial)
                _journal(
                    journal,
                    "trial_completed",
                    trial,
                    run_id=run_id,
                    arm_id=arm_id,
                    task_id=case.case_id,
                    trial_id=trial_id,
                )

        if physical.physical_calls != exact_budget:
            raise AssertionError(f"S2 runtime consumed {physical.physical_calls}, expected exactly {exact_budget}")
        inference_action_delta = combined.used - action_start
        if inference_action_delta != exact_budget:
            raise AssertionError(f"S2 inference consumed {inference_action_delta} shared actions, expected exactly {exact_budget}")
        if physical.cache_hits:
            raise AssertionError("S2 primary runtime forbids cache hits")

        result = _runtime_payload(
            run_id=run_id,
            exact_budget=exact_budget,
            combined=combined,
            physical=physical,
            holdout_manifest=holdout_manifest,
            trials=trials,
            calls=calls,
            validators=validators,
            decisions=decisions,
            snapshots=snapshots,
            events=events,
            external_action_ledger=external_action_ledger,
            action_start=action_start,
            complete=True,
            journal=journal,
        )
        result["real_model_inference"] = any(str(getattr(model, "provider", "")) != "mock" for model in model_by_name.values())
        _journal(
            journal,
            "runtime_completed",
            {
                "physical_model_calls": result["physical_model_calls"],
                "inference_action_delta": result["inference_action_delta"],
                "trial_rows": len(trials),
            },
            run_id=run_id,
        )
        if journal is not None:
            result["journal_integrity"] = journal.snapshot_integrity()
        return result
    except BaseException as exc:
        partial = _runtime_payload(
            run_id=run_id,
            exact_budget=exact_budget,
            combined=combined,
            physical=physical,
            holdout_manifest=holdout_manifest,
            trials=trials,
            calls=calls,
            validators=validators,
            decisions=decisions,
            snapshots=snapshots,
            events=events,
            external_action_ledger=external_action_ledger,
            action_start=action_start,
            complete=False,
            journal=journal,
        )
        partial["real_model_inference"] = any(str(getattr(model, "provider", "")) != "mock" for model in model_by_name.values())
        try:
            _journal(
                journal,
                "runtime_aborted",
                {
                    "error_class": type(exc).__name__,
                    "error": str(exc),
                    "physical_model_calls": physical.physical_calls,
                    "action_budget": combined.snapshot(),
                    "trial_rows": len(trials),
                    "model_call_rows": len(calls),
                    "routing_decision_rows": len(decisions),
                },
                run_id=run_id,
            )
            if journal is not None:
                partial["journal_integrity"] = journal.snapshot_integrity()
        except BaseException as journal_exc:
            partial["journal_abort_error"] = {
                "error_class": type(journal_exc).__name__,
                "error": str(journal_exc),
            }
        try:
            setattr(exc, "s2_partial_runtime", partial)
        except Exception:
            pass
        raise
