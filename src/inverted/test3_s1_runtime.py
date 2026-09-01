from __future__ import annotations

import json
from typing import Any, Callable, Iterable

from .domain import Action, Candidate, TaskCase
from .oracle import apply_actions, evaluate_task
from .test2_gold import evaluate_test2_gold
from .test2_local import BoundedModelCaller
from .test2_local_analysis import structured_failure_feedback
from .test2_types import PhysicalCallBudget
from .test3_s1_cases import build_seed_failure, build_seed_failure_r2, r2_arm_order


# Backward-compatible R1 exports. New callers select R2 explicitly.
S1_PROTOCOL_REVISION = "S1-R1"
S1_HOLDOUT = "A-R1"
S1_R2_PROTOCOL_REVISION = "S1-R2"
S1_R2_HOLDOUT = "A-R2"
S1_CALLS_PER_ARM_TASK = 2
S1_COMPONENTS = frozenset({
    "requirement_validator",
    "retry",
    "targeted_repair",
    "final_validator",
})
S1_MODEL_CALL_COMPONENTS = frozenset({"retry", "targeted_repair"})
S1_ARM_IDS = ("S1-A0", "S1-A1", "S1-A2", "S1-A3")


def _protocol_contract(protocol_revision: str) -> dict[str, Any]:
    if protocol_revision == S1_PROTOCOL_REVISION:
        return {
            "protocol_revision": S1_PROTOCOL_REVISION,
            "holdout": S1_HOLDOUT,
            "matched_tasks": 10,
            "per_arm_call_cap": 20,
            "exact_budget": 80,
            "trial_count": 40,
            "seed_builder": build_seed_failure,
            "case_prefix": "test3-s1-AR1-",
            "execution_mode": "arm_first",
        }
    if protocol_revision == S1_R2_PROTOCOL_REVISION:
        return {
            "protocol_revision": S1_R2_PROTOCOL_REVISION,
            "holdout": S1_R2_HOLDOUT,
            "matched_tasks": 25,
            "per_arm_call_cap": 50,
            "exact_budget": 200,
            "trial_count": 100,
            "seed_builder": build_seed_failure_r2,
            "case_prefix": "test3-s1-AR2-",
            "execution_mode": "balanced_task_blocks",
        }
    raise ValueError(f"unsupported S1 protocol revision: {protocol_revision}")


def _components(arm: dict[str, Any]) -> list[str]:
    order = arm.get("order")
    if order in (None, ""):
        return []
    parts = [part.strip() for part in str(order).split("->") if part.strip()]
    unknown = [part for part in parts if part not in S1_COMPONENTS]
    if unknown:
        raise ValueError("unknown S1 component(s): " + ", ".join(unknown))
    if len(parts) != len(set(parts)):
        raise ValueError("S1 fixed order may not contain duplicate components")
    return parts


def _validate_arm_protocol(arm: dict[str, Any], *, protocol_revision: str = S1_PROTOCOL_REVISION) -> None:
    role = str(arm.get("role") or "")
    parts = _components(arm)
    if role == "best_single_model_baseline":
        if parts:
            raise ValueError(f"{protocol_revision} best-single baseline must not define a component order")
        return
    if set(parts) != S1_COMPONENTS or len(parts) != len(S1_COMPONENTS):
        raise ValueError(f"{protocol_revision} fixed/order arms must contain each production component exactly once")
    model_positions = [parts.index(name) for name in S1_MODEL_CALL_COMPONENTS]
    if min(model_positions) > parts.index("final_validator"):
        raise ValueError(f"{protocol_revision} fixed/order arm would terminate before any active model intervention")


def worst_case_calls_for_arm(arm: dict[str, Any]) -> int:
    _validate_arm_protocol(arm)
    return S1_CALLS_PER_ARM_TASK


def matched_task_limit(arms: Iterable[dict[str, Any]], *, available_cases: int) -> int:
    rows = [dict(arm) for arm in arms]
    if not rows or available_cases <= 0:
        return 0
    limits = []
    for arm in rows:
        _validate_arm_protocol(arm)
        cap = int(arm.get("physical_call_cap") or 0)
        if cap <= 0:
            raise ValueError("S1 arm physical_call_cap must be positive")
        limits.append(cap // S1_CALLS_PER_ARM_TASK)
    return max(0, min(available_cases, min(limits)))


def _public_task(task: TaskCase) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "family": task.family,
        "complexity": task.complexity,
        "goal": task.goal,
        "initial_state": task.initial_state.to_dict(),
        "allowed_ops": list(task.allowed_ops),
        "requirements": task.metadata.get("public_requirements", []),
    }


def public_failure_feedback(
    task: TaskCase,
    candidate: Candidate | None,
    failed_ids: list[str],
) -> dict[str, Any]:
    """Return deterministic failure evidence restricted to S1-public fields."""
    feedback = structured_failure_feedback(task, candidate, failed_ids)
    rows = feedback.get("failed_requirements") if isinstance(feedback, dict) else None
    sanitized: list[dict[str, Any]] = []
    for raw in rows if isinstance(rows, list) else []:
        if not isinstance(raw, dict):
            continue
        clean = dict(raw)
        clean.pop("critical", None)
        sanitized.append(clean)
    return {"failed_requirements": sanitized}


def _parse_actions(text: str) -> tuple[Action, ...] | None:
    try:
        value = json.loads(text)
        raw = value.get("actions") if isinstance(value, dict) else None
        if not isinstance(raw, list):
            return None
        return tuple(Action(str(row["op"]), str(row["path"]), row.get("value")) for row in raw)
    except Exception:
        return None


def _candidate(task: TaskCase, text: str, candidate_id: str) -> Candidate | None:
    actions = _parse_actions(text)
    if actions is None:
        return None
    try:
        state = apply_actions(task.initial_state, actions)
    except Exception:
        return None
    return Candidate(candidate_id, state, actions, configured_quality=1.0)


def _deterministic(task: TaskCase, candidate: Candidate | None) -> dict[str, Any]:
    if candidate is None:
        return {
            "success": False,
            "catastrophic": False,
            "passed_requirements": [],
            "failed_requirements": ["parse_or_execution"],
        }
    result = evaluate_task(task, candidate.state, candidate.actions)
    return {
        "success": bool(result.success),
        "catastrophic": bool(result.catastrophic),
        "passed_requirements": list(result.passed_requirement_ids),
        "failed_requirements": list(result.failed_requirement_ids),
    }


def _gold(task: TaskCase, candidate: Candidate | None) -> dict[str, Any]:
    if candidate is None:
        return {"success": False, "semantic_clean": False, "semantic_issues": []}
    result = evaluate_test2_gold(task, candidate)
    return {
        "success": bool(result.success),
        "semantic_clean": bool(result.semantic_clean),
        "semantic_issues": list(result.semantic_issues),
    }


def _assert_public_prompt(prompt: Any) -> None:
    text = json.dumps(prompt, sort_keys=True)
    forbidden = (
        '"critical"',
        "target_state",
        "hidden_gold",
        "injected_fault",
        "s1_r1_seed_failure",
        "s1_r2_seed_failure",
        "stress_case",
    )
    leaked = [term for term in forbidden if term in text]
    if leaked:
        raise AssertionError("S1 public prompt boundary violated: " + ", ".join(leaked))


def _call_row(
    completion: Any,
    *,
    arm_id: str,
    task_id: str,
    component: str,
    role: str,
    model: str,
    active_intervention: bool,
) -> dict[str, Any]:
    telemetry = completion.record.to_dict() if hasattr(completion.record, "to_dict") else {}
    return {
        "arm_id": arm_id,
        "task_id": task_id,
        "component": component,
        "planned_component": component,
        "role": role,
        "model": model,
        "active_intervention": bool(active_intervention),
        "shadow_only": not bool(active_intervention),
        "call_identity": completion.identity,
        "cache_hit": bool(completion.cache_hit),
        "logical_call_index": completion.logical_index,
        "physical_call_number": completion.physical_call_number,
        "prompt": completion.prompt,
        "response": completion.response,
        "telemetry": telemetry,
    }


def _executor_call(
    *,
    caller: BoundedModelCaller,
    model: Any,
    task: TaskCase,
    run_id: str,
    arm_id: str,
    task_id: str,
    component: str,
    attempt: int,
    active_intervention: bool,
) -> tuple[Candidate | None, dict[str, Any]]:
    payload = _public_task(task)
    messages = [
        {"role": "system", "content": "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. Satisfy every supplied machine-checkable requirement and add no unintended actions."},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]
    _assert_public_prompt(messages)
    suffix = "active" if active_intervention else "shadow"
    completion = caller.complete(
        model,
        messages,
        role="executor",
        context={
            "run_id": run_id,
            "trial_id": f"{task_id}-{arm_id}",
            "call_id": f"{run_id}-{arm_id}-{task_id}-{component}-{attempt}-{suffix}",
        },
        response_schema={"type": "object"},
        allow_cache=False,
    )
    candidate = _candidate(task, completion.text, f"{task_id}-{arm_id}-{component}-{attempt}")
    return candidate, _call_row(
        completion,
        arm_id=arm_id,
        task_id=task_id,
        component=component,
        role="executor",
        model=str(model.model),
        active_intervention=active_intervention,
    )


def _repair_call(
    *,
    caller: BoundedModelCaller,
    model: Any,
    task: TaskCase,
    candidate: Candidate | None,
    failed_ids: list[str],
    run_id: str,
    arm_id: str,
    task_id: str,
    active_intervention: bool,
) -> tuple[Candidate | None, dict[str, Any]]:
    feedback = public_failure_feedback(task, candidate, failed_ids)
    payload = _public_task(task) | {
        "previous_actions": [action.to_dict() for action in candidate.actions] if candidate else [],
        "validator_feedback": feedback,
    }
    messages = [
        {"role": "system", "content": "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. Repair only failed parts and preserve every already-correct requirement."},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]
    _assert_public_prompt(messages)
    suffix = "active" if active_intervention else "shadow"
    completion = caller.complete(
        model,
        messages,
        role="repairer",
        context={
            "run_id": run_id,
            "trial_id": f"{task_id}-{arm_id}",
            "candidate_id": candidate.id if candidate else None,
            "call_id": f"{run_id}-{arm_id}-{task_id}-targeted-repair-{suffix}",
        },
        response_schema={"type": "object"},
        allow_cache=False,
    )
    repaired = _candidate(task, completion.text, f"{task_id}-{arm_id}-targeted-repair")
    return repaired, _call_row(
        completion,
        arm_id=arm_id,
        task_id=task_id,
        component="targeted_repair",
        role="repairer",
        model=str(model.model),
        active_intervention=active_intervention,
    )


def _trace_row(
    component: str,
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    blocked_before: bool,
    blocked_after: bool,
    terminal: bool = False,
    shadow_only: bool = False,
) -> dict[str, Any]:
    return {
        "component": component,
        "before_deterministic_success": bool(before.get("success")),
        "before_blocked": blocked_before,
        "after_deterministic_success": bool(after.get("success")),
        "after_blocked": blocked_after,
        "terminal": terminal,
        "shadow_only": shadow_only,
    }


def _finalize_trial(
    *,
    contract: dict[str, Any],
    task: TaskCase,
    task_id: str,
    arm: dict[str, Any],
    candidate: Candidate | None,
    current: dict[str, Any],
    seed_status: dict[str, Any],
    blocked: bool,
    start_calls: int,
    caller: BoundedModelCaller,
    raw_calls: list[dict[str, Any]],
    validators: list[dict[str, Any]],
    trace: list[dict[str, Any]],
    first_active_component: str | None,
) -> dict[str, Any]:
    gold = _gold(task, candidate)
    final_success = bool(current["success"] and gold["success"] and not blocked)
    catastrophic = bool(current["catastrophic"])
    failure_class = None
    if not final_success:
        if not current["success"]:
            failure_class = ",".join(current["failed_requirements"]) or "deterministic_failure"
        elif blocked:
            failure_class = "blocked_by_fixed_stack"
        elif not gold["semantic_clean"]:
            failure_class = "semantic_escape"
        else:
            failure_class = "hidden_gold_failure"

    total_tokens = active_tokens = shadow_tokens = 0
    latency_s = 0.0
    for row in raw_calls:
        telemetry = row.get("telemetry") or {}
        tokens = int(telemetry.get("total_tokens") or 0)
        total_tokens += tokens
        if row.get("active_intervention"):
            active_tokens += tokens
        else:
            shadow_tokens += tokens
        latency_s += float(telemetry.get("latency_s") or 0.0)

    active_calls = sum(bool(row.get("active_intervention")) for row in raw_calls)
    shadow_calls = sum(bool(row.get("shadow_only")) for row in raw_calls)
    calls_added = caller.budget.physical_calls - start_calls
    revision = str(contract["protocol_revision"])
    if calls_added != S1_CALLS_PER_ARM_TASK or len(raw_calls) != S1_CALLS_PER_ARM_TASK:
        raise AssertionError(
            f"{revision} arm-task must consume exactly {S1_CALLS_PER_ARM_TASK} physical calls; "
            f"observed calls_added={calls_added}, rows={len(raw_calls)}"
        )
    if active_calls < 1:
        raise AssertionError(f"{revision} arm-task must expose at least one active model intervention")

    return {
        "protocol_revision": revision,
        "holdout": contract["holdout"],
        "task_id": task_id,
        "arm_id": str(arm.get("arm_id") or ""),
        "arm_role": arm.get("role"),
        "order": arm.get("order"),
        "family": task.family,
        "complexity": task.complexity,
        "complete": True,
        "seed_failure_verified": not bool(seed_status["success"]),
        "seed_passed_requirements": list(seed_status["passed_requirements"]),
        "seed_failed_requirements": list(seed_status["failed_requirements"]),
        "final_passed_requirements": list(current["passed_requirements"]),
        "final_failed_requirements": list(current["failed_requirements"]),
        "first_active_component": first_active_component,
        "active_inference_calls": active_calls,
        "shadow_inference_calls": shadow_calls,
        "intervention_exposure_valid": bool(not seed_status["success"] and active_calls >= 1 and calls_added == S1_CALLS_PER_ARM_TASK),
        "cache_hits": sum(bool(row.get("cache_hit")) for row in raw_calls),
        "success": final_success,
        "deterministic_success": bool(current["success"]),
        "hidden_gold_success": bool(gold["success"]),
        "semantic_clean": bool(gold["semantic_clean"]),
        "semantic_issues": list(gold["semantic_issues"]),
        "catastrophic": catastrophic,
        "blocked": blocked,
        "failure_class": failure_class,
        "physical_calls_added": calls_added,
        "total_tokens": total_tokens,
        "active_total_tokens": active_tokens,
        "shadow_total_tokens": shadow_tokens,
        "latency_s": latency_s,
        "trace": trace,
        "raw_calls": raw_calls,
        "validator_results": validators,
    }


def _seed_for_case(case: Any, contract: dict[str, Any]) -> tuple[Candidate, dict[str, Any]]:
    builder: Callable[[Any], Candidate] = contract["seed_builder"]
    seed = builder(case)
    status = _deterministic(case.task, seed)
    if status["success"]:
        raise AssertionError(f"{contract['protocol_revision']} deterministic seed fixture unexpectedly succeeds")
    return seed, status


def _run_baseline_task(
    case: Any,
    arm: dict[str, Any],
    *,
    contract: dict[str, Any],
    executor: Any,
    repairer: Any,
    caller: BoundedModelCaller,
    run_id: str,
) -> dict[str, Any]:
    del repairer
    arm_id = str(arm.get("arm_id") or "")
    task_id = str(case.case_id)
    task: TaskCase = case.task
    seed, seed_status = _seed_for_case(case, contract)
    current = dict(seed_status)
    start_calls = caller.budget.physical_calls
    raw_calls: list[dict[str, Any]] = []
    validators: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = [{
        "component": "seed_failure",
        "before_deterministic_success": None,
        "before_blocked": False,
        "after_deterministic_success": False,
        "after_blocked": False,
        "terminal": False,
        "shadow_only": False,
    }]

    candidate: Candidate | None = seed
    first_active_component = "best_single_regenerate"
    for attempt in (1, 2):
        active = not bool(current["success"])
        proposed, call = _executor_call(
            caller=caller,
            model=executor,
            task=task,
            run_id=run_id,
            arm_id=arm_id,
            task_id=task_id,
            component="best_single_regenerate",
            attempt=attempt,
            active_intervention=active,
        )
        raw_calls.append(call)
        before = dict(current)
        if active:
            candidate = proposed
            current = _deterministic(task, candidate)
        trace.append(_trace_row(
            "best_single_regenerate",
            before,
            current,
            blocked_before=False,
            blocked_after=False,
            shadow_only=not active,
        ))

    validators.append({
        "arm_id": arm_id,
        "task_id": task_id,
        "stage": "baseline_final_validator",
        "deterministic_success": bool(current["success"]),
        "catastrophic": bool(current["catastrophic"]),
        "passed_requirements": list(current["passed_requirements"]),
        "failed_requirements": list(current["failed_requirements"]),
    })
    return _finalize_trial(
        contract=contract,
        task=task,
        task_id=task_id,
        arm=arm,
        candidate=candidate,
        current=current,
        seed_status=seed_status,
        blocked=False,
        start_calls=start_calls,
        caller=caller,
        raw_calls=raw_calls,
        validators=validators,
        trace=trace,
        first_active_component=first_active_component,
    )


def _run_fixed_task(
    case: Any,
    arm: dict[str, Any],
    *,
    contract: dict[str, Any],
    executor: Any,
    repairer: Any,
    caller: BoundedModelCaller,
    run_id: str,
) -> dict[str, Any]:
    arm_id = str(arm.get("arm_id") or "")
    task_id = str(case.case_id)
    task: TaskCase = case.task
    seed, seed_status = _seed_for_case(case, contract)
    candidate: Candidate | None = seed
    current = dict(seed_status)
    start_calls = caller.budget.physical_calls
    raw_calls: list[dict[str, Any]] = []
    validators: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = [{
        "component": "seed_failure",
        "before_deterministic_success": None,
        "before_blocked": False,
        "after_deterministic_success": False,
        "after_blocked": False,
        "terminal": False,
        "shadow_only": False,
    }]
    blocked = False
    terminal = False
    first_active_component: str | None = None
    retry_attempt = 0

    for component in _components(arm):
        before = dict(current)
        blocked_before = blocked
        if component == "requirement_validator":
            validators.append({
                "arm_id": arm_id,
                "task_id": task_id,
                "stage": "requirement_validator",
                "deterministic_success": bool(current["success"]),
                "catastrophic": bool(current["catastrophic"]),
                "passed_requirements": list(current["passed_requirements"]),
                "failed_requirements": list(current["failed_requirements"]),
            })
            if not current["success"]:
                blocked = True
            trace.append(_trace_row(component, before, current, blocked_before=blocked_before, blocked_after=blocked))

        elif component == "retry":
            active = not terminal and (not current["success"] or blocked)
            retry_attempt += 1
            proposed, call = _executor_call(
                caller=caller,
                model=executor,
                task=task,
                run_id=run_id,
                arm_id=arm_id,
                task_id=task_id,
                component="retry",
                attempt=retry_attempt,
                active_intervention=active,
            )
            raw_calls.append(call)
            if active:
                if first_active_component is None:
                    first_active_component = "retry"
                candidate = proposed
                current = _deterministic(task, candidate)
                blocked = False
            trace.append(_trace_row(
                component,
                before,
                current,
                blocked_before=blocked_before,
                blocked_after=blocked,
                terminal=terminal,
                shadow_only=not active,
            ))

        elif component == "targeted_repair":
            active = not terminal and (not current["success"] or blocked)
            proposed, call = _repair_call(
                caller=caller,
                model=repairer,
                task=task,
                candidate=candidate,
                failed_ids=list(current["failed_requirements"]),
                run_id=run_id,
                arm_id=arm_id,
                task_id=task_id,
                active_intervention=active,
            )
            raw_calls.append(call)
            if active:
                if first_active_component is None:
                    first_active_component = "targeted_repair"
                candidate = proposed
                current = _deterministic(task, candidate)
                blocked = False
            trace.append(_trace_row(
                component,
                before,
                current,
                blocked_before=blocked_before,
                blocked_after=blocked,
                terminal=terminal,
                shadow_only=not active,
            ))

        elif component == "final_validator":
            validators.append({
                "arm_id": arm_id,
                "task_id": task_id,
                "stage": "final_validator",
                "deterministic_success": bool(current["success"]),
                "catastrophic": bool(current["catastrophic"]),
                "passed_requirements": list(current["passed_requirements"]),
                "failed_requirements": list(current["failed_requirements"]),
            })
            if not current["success"]:
                terminal = True
                blocked = True
            trace.append(_trace_row(
                component,
                before,
                current,
                blocked_before=blocked_before,
                blocked_after=blocked,
                terminal=terminal,
            ))

        else:  # pragma: no cover
            raise ValueError(f"unknown S1 component: {component}")

    return _finalize_trial(
        contract=contract,
        task=task,
        task_id=task_id,
        arm=arm,
        candidate=candidate,
        current=current,
        seed_status=seed_status,
        blocked=blocked,
        start_calls=start_calls,
        caller=caller,
        raw_calls=raw_calls,
        validators=validators,
        trace=trace,
        first_active_component=first_active_component,
    )


def _run_arm_task_with_caller(
    case: Any,
    arm: dict[str, Any],
    *,
    contract: dict[str, Any],
    model_by_name: dict[str, Any],
    best_single_model: str,
    repair_model: str,
    caller: BoundedModelCaller,
    run_id: str,
) -> dict[str, Any]:
    _validate_arm_protocol(arm, protocol_revision=str(contract["protocol_revision"]))
    if best_single_model not in model_by_name or repair_model not in model_by_name:
        raise ValueError("S1 model adapter map is missing frozen best-single or repair model")
    executor = model_by_name[best_single_model]
    repairer = model_by_name[repair_model]
    if str(arm.get("role") or "") == "best_single_model_baseline":
        return _run_baseline_task(
            case,
            arm,
            contract=contract,
            executor=executor,
            repairer=repairer,
            caller=caller,
            run_id=run_id,
        )
    return _run_fixed_task(
        case,
        arm,
        contract=contract,
        executor=executor,
        repairer=repairer,
        caller=caller,
        run_id=run_id,
    )


def run_arm_task(
    case: Any,
    arm: dict[str, Any],
    *,
    model_by_name: dict[str, Any],
    best_single_model: str,
    repair_model: str,
    budget: PhysicalCallBudget,
    run_id: str,
    protocol_revision: str = S1_PROTOCOL_REVISION,
) -> dict[str, Any]:
    contract = _protocol_contract(protocol_revision)
    caller = BoundedModelCaller(budget)
    return _run_arm_task_with_caller(
        case,
        arm,
        contract=contract,
        model_by_name=model_by_name,
        best_single_model=best_single_model,
        repair_model=repair_model,
        caller=caller,
        run_id=run_id,
    )


def _validate_screen_inputs(
    *,
    arm_rows: list[dict[str, Any]],
    cases: list[Any],
    model_by_name: dict[str, Any],
    best_single_model: str,
    repair_model: str,
    exact_budget: int,
    contract: dict[str, Any],
) -> int:
    revision = str(contract["protocol_revision"])
    expected_budget = int(contract["exact_budget"])
    expected_cap = int(contract["per_arm_call_cap"])
    expected_matched = int(contract["matched_tasks"])

    if len(arm_rows) != 4 or exact_budget != expected_budget:
        label = "exact-200" if revision == S1_R2_PROTOCOL_REVISION else "exact-80"
        raise ValueError(f"{revision} runtime requires the frozen four-arm {label}-call contract")
    if tuple(str(row.get("arm_id") or "") for row in arm_rows) != S1_ARM_IDS:
        raise ValueError(f"{revision} runtime requires frozen A0-A3 arm order in the arm definition")
    for arm in arm_rows:
        _validate_arm_protocol(arm, protocol_revision=revision)
        if int(arm.get("physical_call_cap") or 0) != expected_cap:
            raise ValueError(f"{revision} requires exactly {expected_cap} physical calls per arm")
    for name in {best_single_model, repair_model}:
        model = model_by_name.get(name)
        if model is None:
            raise ValueError(f"missing S1 model adapter: {name}")
        if int(getattr(model, "max_retries", 0) or 0) != 0:
            raise ValueError("S1 model adapters must disable internal retries")

    matched_n = matched_task_limit(arm_rows, available_cases=len(cases))
    if matched_n != expected_matched:
        raise ValueError(f"{revision} requires exactly {expected_matched} matched cases; resolved {matched_n}")
    selected = cases[:matched_n]
    prefix = str(contract["case_prefix"])
    if any(not str(case.case_id).startswith(prefix) for case in selected):
        raise ValueError(f"{revision} received cases outside frozen holdout {contract['holdout']}")
    return matched_n


def _record_result(
    *,
    result: dict[str, Any],
    task_index: int,
    arm_position: int,
    execution_ordinal: int,
    trials: list[dict[str, Any]],
    raw_calls: list[dict[str, Any]],
    validators: list[dict[str, Any]],
    events: list[dict[str, Any]],
    run_id: str,
) -> None:
    trial = {key: value for key, value in result.items() if key not in {"raw_calls", "validator_results"}}
    trial["task_index"] = task_index
    trial["arm_execution_position"] = arm_position
    trial["execution_ordinal"] = execution_ordinal
    trials.append(trial)
    raw_calls.extend(result["raw_calls"])
    validators.extend(result["validator_results"])
    events.append({
        "event": "task_completed",
        "run_id": run_id,
        "task_index": task_index,
        "arm_execution_position": arm_position,
        "execution_ordinal": execution_ordinal,
        "arm_id": result["arm_id"],
        "task_id": result["task_id"],
        "family": result["family"],
        "success": result["success"],
        "physical_calls_added": result["physical_calls_added"],
        "active_inference_calls": result["active_inference_calls"],
        "shadow_inference_calls": result["shadow_inference_calls"],
        "first_active_component": result["first_active_component"],
    })


def run_s1_screen(
    *,
    cases: list[Any],
    arms: Iterable[dict[str, Any]],
    model_by_name: dict[str, Any],
    best_single_model: str,
    repair_model: str,
    run_id: str,
    exact_budget: int = 80,
    protocol_revision: str = S1_PROTOCOL_REVISION,
) -> dict[str, Any]:
    contract = _protocol_contract(protocol_revision)
    arm_rows = [dict(arm) for arm in arms]
    matched_n = _validate_screen_inputs(
        arm_rows=arm_rows,
        cases=cases,
        model_by_name=model_by_name,
        best_single_model=best_single_model,
        repair_model=repair_model,
        exact_budget=exact_budget,
        contract=contract,
    )
    selected_cases = cases[:matched_n]
    revision = str(contract["protocol_revision"])
    expected_cap = int(contract["per_arm_call_cap"])

    trials: list[dict[str, Any]] = []
    raw_calls: list[dict[str, Any]] = []
    validators: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = [{
        "event": "run_started",
        "run_id": run_id,
        "protocol_revision": revision,
        "holdout": contract["holdout"],
        "planned_physical_model_calls": exact_budget,
        "execution_mode": contract["execution_mode"],
    }]

    arms_by_id = {str(arm["arm_id"]): arm for arm in arm_rows}
    budgets = {arm_id: PhysicalCallBudget(expected_cap) for arm_id in S1_ARM_IDS}
    callers = {arm_id: BoundedModelCaller(budgets[arm_id]) for arm_id in S1_ARM_IDS}
    arm_active = {arm_id: 0 for arm_id in S1_ARM_IDS}
    arm_shadow = {arm_id: 0 for arm_id in S1_ARM_IDS}
    arm_first_ops = {arm_id: set() for arm_id in S1_ARM_IDS}
    execution_ordinal = 0

    if revision == S1_PROTOCOL_REVISION:
        schedule = [
            (task_index, arm_position, arm_id, case)
            for arm_position, arm_id in enumerate(S1_ARM_IDS)
            for task_index, case in enumerate(selected_cases)
        ]
    else:
        schedule = []
        for task_index, case in enumerate(selected_cases):
            for arm_position, arm_id in enumerate(r2_arm_order(task_index)):
                schedule.append((task_index, arm_position, arm_id, case))

    for task_index, arm_position, arm_id, case in schedule:
        result = _run_arm_task_with_caller(
            case,
            arms_by_id[arm_id],
            contract=contract,
            model_by_name=model_by_name,
            best_single_model=best_single_model,
            repair_model=repair_model,
            caller=callers[arm_id],
            run_id=run_id,
        )
        _record_result(
            result=result,
            task_index=task_index,
            arm_position=arm_position,
            execution_ordinal=execution_ordinal,
            trials=trials,
            raw_calls=raw_calls,
            validators=validators,
            events=events,
            run_id=run_id,
        )
        execution_ordinal += 1
        arm_active[arm_id] += int(result["active_inference_calls"])
        arm_shadow[arm_id] += int(result["shadow_inference_calls"])
        if result.get("first_active_component"):
            arm_first_ops[arm_id].add(str(result["first_active_component"]))

    arm_accounting: list[dict[str, Any]] = []
    for arm_id in S1_ARM_IDS:
        budget = budgets[arm_id]
        if budget.physical_calls != expected_cap:
            raise AssertionError(
                f"{revision} arm {arm_id} must consume its exact {expected_cap}-call reservation; used {budget.physical_calls}"
            )
        arm_accounting.append({
            "arm_id": arm_id,
            "physical_call_cap": expected_cap,
            "physical_calls_used": budget.physical_calls,
            "physical_calls_remaining": budget.remaining,
            "cache_hits": budget.cache_hits,
            "calls_per_matched_task": S1_CALLS_PER_ARM_TASK,
            "matched_tasks_completed": len(selected_cases),
            "active_inference_calls": arm_active[arm_id],
            "shadow_inference_calls": arm_shadow[arm_id],
            "first_active_components": sorted(arm_first_ops[arm_id]),
        })

    total_calls = sum(int(row["physical_calls_used"]) for row in arm_accounting)
    if total_calls != exact_budget:
        raise AssertionError(f"{revision} exact physical call contract violated: {total_calls} != {exact_budget}")
    if any(row.get("cache_hit") for row in raw_calls):
        raise AssertionError("S1 fresh-inference screen must not use model-call cache hits")
    if len(trials) != int(contract["trial_count"]) or any(not row.get("intervention_exposure_valid") for row in trials):
        raise AssertionError(f"{revision} intervention exposure contract failed")
    fixed_first_ops = {
        str(row.get("first_active_component") or "")
        for row in trials
        if row.get("arm_id") in {"S1-A1", "S1-A2", "S1-A3"}
    }
    fixed_first_ops.discard("")
    if len(fixed_first_ops) < 2:
        raise AssertionError(f"{revision} fixed/order arms do not expose at least two distinct first active operations")

    if revision == S1_R2_PROTOCOL_REVISION:
        observed_schedule = [
            (int(row["task_index"]), int(row["arm_execution_position"]), str(row["arm_id"]))
            for row in trials
        ]
        expected_schedule = [
            (task_index, position, arm_id)
            for task_index in range(25)
            for position, arm_id in enumerate(r2_arm_order(task_index))
        ]
        if observed_schedule != expected_schedule:
            raise AssertionError("S1-R2 balanced arm execution schedule drifted from preregistration")

    events.append({
        "event": "run_ended",
        "run_id": run_id,
        "physical_model_calls": total_calls,
        "protocol_valid_for_primary_claim": True,
    })
    return {
        "protocol_revision": revision,
        "holdout": contract["holdout"],
        "run_id": run_id,
        "physical_model_calls": total_calls,
        "exact_budget": exact_budget,
        "matched_task_limit": matched_n,
        "matched_task_ids": [case.case_id for case in selected_cases],
        "trials": trials,
        "model_calls": raw_calls,
        "validator_results": validators,
        "events": events,
        "arm_accounting": arm_accounting,
        "protocol_valid_for_primary_claim": True,
        "execution_mode": contract["execution_mode"],
        "intervention_exposure": {
            "all_seed_failures_verified": all(bool(row.get("seed_failure_verified")) for row in trials),
            "all_arm_tasks_have_active_intervention": all(int(row.get("active_inference_calls") or 0) >= 1 for row in trials),
            "distinct_fixed_first_active_components": len(fixed_first_ops),
            "fixed_first_active_components": sorted(fixed_first_ops),
        },
        "real_model_inference": any(str(getattr(model, "provider", "")) != "mock" for model in model_by_name.values()),
    }
