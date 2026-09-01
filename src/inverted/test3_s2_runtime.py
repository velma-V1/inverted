from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from typing import Any

from .domain import Action, Candidate, TaskCase
from .models import MockModelAdapter
from .oracle import evaluate_task
from .system_executor import generate_candidate
from .test2_local import BoundedModelCaller
from .test2_types import PhysicalCallBudget
from .test3_s1_r3_runtime import compose_repair_patch
from .test3_s1_runtime import _call_row, _candidate, _public_task, public_failure_feedback
from .test3_s2_budget import CombinedActionBudget
from .test3_s2_cases import S2ExecutionCase, S2_HOLDOUT, S2_PROTOCOL_REVISION, build_seed_failure_s2
from .test3_s2_policy import INTERVENTION_LIBRARY, REAL_ARM_IDS, public_router_state, select_action


S2_MATCHED_CASES = 72
S2_CALLS_PER_ARM_TASK = 2
S2_ARM_COUNT = 5
S2_TRIAL_COUNT = S2_MATCHED_CASES * S2_ARM_COUNT
S2_PER_ARM_CALL_CAP = S2_MATCHED_CASES * S2_CALLS_PER_ARM_TASK
S2_EXACT_BUDGET = S2_TRIAL_COUNT * S2_CALLS_PER_ARM_TASK
S2_QWEN_MODEL = "qwen3.5:9b-q8_0"
S2_REPAIR_MODEL = "cogito:3b-v1-preview-llama-q8_0"
S2_LLAMA_MODEL = "llama3.1:8b"
S2_MODEL_NAMES = (S2_QWEN_MODEL, S2_REPAIR_MODEL, S2_LLAMA_MODEL)


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


def _execute_call(
    *,
    caller: BoundedModelCaller,
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
) -> tuple[Candidate | None, dict[str, Any]]:
    model_name, role = _model_for_action(action)
    if str(getattr(model, "model", "")) != model_name:
        raise ValueError(f"S2 model adapter mismatch for {action}: expected {model_name}")
    messages = _messages_for_action(action, task, candidate, status)
    action_budget.reserve("model_call")
    context = {
        "run_id": run_id,
        "trial_id": f"{case_id}-{arm_id}",
        "candidate_id": candidate.id if candidate is not None else None,
        "call_id": f"{run_id}-{arm_id}-{case_id}-{step_index}-{action}-{'active' if active else 'shadow'}",
    }
    if isinstance(model, MockModelAdapter) or str(getattr(model, "provider", "")) == "mock":
        context["mock_text"] = _mock_text(task, repair=(action == "repair_cogito"))
    completion = caller.complete(
        model,
        messages,
        role=role,
        context=context,
        response_schema={"type": "object"},
        allow_cache=False,
    )

    proposed: Candidate | None
    if action == "repair_cogito":
        try:
            raw = json.loads(completion.text)
            rows = raw.get("actions") if isinstance(raw, dict) else None
            patch = tuple(Action(str(row["op"]), str(row["path"]), row.get("value")) for row in rows) if isinstance(rows, list) else None
        except Exception:
            patch = None
        if patch is None:
            proposed = None
        else:
            try:
                proposed = compose_repair_patch(
                    task,
                    candidate,
                    patch,
                    list(status.get("failed_requirements") or []),
                    f"{case_id}-{arm_id}-s2-repair-{step_index}",
                )
            except Exception:
                proposed = None
    else:
        proposed = _candidate(task, completion.text, f"{case_id}-{arm_id}-{action}-{step_index}")

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
        outcomes = {(bool(row.get("success_after")), bool(row.get("catastrophic_after"))) for row in rows}
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
            "outcome_changed": len(outcomes) > 1,
        })
    return findings


def _validate_inputs(cases: list[S2ExecutionCase], model_by_name: dict[str, Any], exact_budget: int) -> None:
    if exact_budget != S2_EXACT_BUDGET:
        raise ValueError("S2-R1 requires exact 720-call budget")
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


def run_s2_screen(
    *,
    cases: list[S2ExecutionCase],
    model_by_name: dict[str, Any],
    run_id: str,
    exact_budget: int = S2_EXACT_BUDGET,
) -> dict[str, Any]:
    _validate_inputs(cases, model_by_name, exact_budget)
    physical = PhysicalCallBudget(max_calls=exact_budget)
    caller = BoundedModelCaller(physical)
    combined = CombinedActionBudget(exact_budget)
    trials: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    validators: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for case_index, case in enumerate(cases):
        for execution_position, arm_id in enumerate(_arm_order(case_index)):
            seed = build_seed_failure_s2(case)
            candidate: Candidate | None = seed
            status = _result(case.task, candidate)
            initial_status = dict(status)
            previous_action: str | None = None
            previous_model: str | None = None
            selected_actions: list[str] = []
            selected_models: list[str] = []
            trial_calls: list[dict[str, Any]] = []

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
                decisions.append({
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
                })
                snapshots.append({
                    "arm_id": arm_id,
                    "task_id": case.case_id,
                    "step_index": step_index,
                    "state": evidence,
                    "router_view": router_view,
                })
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
                )
                before = dict(status)
                if active:
                    candidate = proposed
                    status = _result(case.task, candidate)
                after = dict(status)
                call.update({
                    "base_task_id": case.metadata["base_task_id"],
                    "perturbation_class": case.metadata["perturbation_class"],
                    "execution_position": execution_position,
                    "success_before": bool(before.get("success")),
                    "catastrophic_before": bool(before.get("catastrophic")),
                    "success_after": bool(after.get("success")),
                    "catastrophic_after": bool(after.get("catastrophic")),
                })
                calls.append(call)
                trial_calls.append(call)
                validators.append({
                    "arm_id": arm_id,
                    "task_id": case.case_id,
                    "step_index": step_index,
                    "stage": "post_action_deterministic_validator",
                    "active_intervention": active,
                    "success": bool(after.get("success")),
                    "catastrophic": bool(after.get("catastrophic")),
                    "passed_requirements": list(after.get("passed_requirements") or []),
                    "failed_requirements": list(after.get("failed_requirements") or []),
                })
                events.append({
                    "event": "s2_action_observed",
                    "arm_id": arm_id,
                    "task_id": case.case_id,
                    "step_index": step_index,
                    "action": action,
                    "model": model_name,
                    "active": active,
                    "success_after": bool(after.get("success")),
                    "catastrophic_after": bool(after.get("catastrophic")),
                })
                selected_actions.append(action)
                selected_models.append(model_name)
                previous_action = action
                previous_model = model_name

            trials.append({
                "protocol_revision": S2_PROTOCOL_REVISION,
                "holdout": S2_HOLDOUT,
                "arm_id": arm_id,
                "task_id": case.case_id,
                "base_task_id": case.metadata["base_task_id"],
                "family": case.task.family,
                "complexity": int(case.task.complexity),
                "perturbation_class": case.metadata["perturbation_class"],
                "execution_position": execution_position,
                "initial_success": bool(initial_status.get("success")),
                "initial_catastrophic": bool(initial_status.get("catastrophic")),
                "initial_failed_requirements": list(initial_status.get("failed_requirements") or []),
                "success": bool(status.get("success")),
                "catastrophic": bool(status.get("catastrophic")),
                "final_failed_requirements": list(status.get("failed_requirements") or []),
                "actions_selected": selected_actions,
                "models_selected": selected_models,
                "calls_used": len(trial_calls),
                "active_calls": sum(bool(row.get("active_intervention")) for row in trial_calls),
                "shadow_calls": sum(bool(row.get("shadow_only")) for row in trial_calls),
                "complete": len(trial_calls) == S2_CALLS_PER_ARM_TASK,
            })

    if physical.physical_calls != exact_budget:
        raise AssertionError(f"S2 runtime consumed {physical.physical_calls}, expected exactly {exact_budget}")
    if combined.used != exact_budget:
        raise AssertionError(f"S2 combined action budget consumed {combined.used}, expected exactly {exact_budget}")
    if physical.cache_hits:
        raise AssertionError("S2 primary runtime forbids cache hits")

    call_counts = Counter(str(row["arm_id"]) for row in calls)
    arm_accounting = [
        {
            "arm_id": arm_id,
            "planned_physical_calls": S2_PER_ARM_CALL_CAP,
            "actual_physical_calls": int(call_counts.get(arm_id, 0)),
            "matched_cases": sum(1 for row in trials if row["arm_id"] == arm_id),
            "calls_per_case": S2_CALLS_PER_ARM_TASK,
        }
        for arm_id in REAL_ARM_IDS
    ]
    return {
        "run_id": run_id,
        "protocol_revision": S2_PROTOCOL_REVISION,
        "holdout": S2_HOLDOUT,
        "execution_mode": "balanced_task_blocks",
        "exact_budget": exact_budget,
        "matched_cases": S2_MATCHED_CASES,
        "trial_count": S2_TRIAL_COUNT,
        "physical_model_calls": physical.physical_calls,
        "action_budget": combined.snapshot(),
        "trials": trials,
        "model_calls": calls,
        "validator_results": validators,
        "routing_decisions": decisions,
        "routing_state_snapshots": snapshots,
        "events": events,
        "arm_accounting": arm_accounting,
        "stochastic_divergence": detect_stochastic_divergence(calls),
        "real_model_inference": any(str(getattr(model, "provider", "")) != "mock" for model in model_by_name.values()),
        "intervention_library": list(INTERVENTION_LIBRARY),
    }
