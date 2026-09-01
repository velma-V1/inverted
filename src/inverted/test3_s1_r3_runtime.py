from __future__ import annotations

import json
from typing import Any, Iterable

from .domain import Action, Candidate, TaskCase
from .oracle import apply_actions
from .test2_local import BoundedModelCaller
from .test2_types import PhysicalCallBudget
from .test3_s1_cases import build_seed_failure_r3, r3_arm_order
from .test3_s1_runtime import (
    S1_ARM_IDS,
    S1_CALLS_PER_ARM_TASK,
    _assert_public_prompt,
    _call_row,
    _components,
    _deterministic,
    _executor_call,
    _finalize_trial,
    _public_task,
    _record_result,
    _run_baseline_task,
    _trace_row,
    _validate_arm_protocol,
    public_failure_feedback,
)


S1_R3_PROTOCOL_REVISION = "S1-R3"
S1_R3_HOLDOUT = "A-R3"
S1_R3_MATCHED_TASKS = 25
S1_R3_PER_ARM_CALL_CAP = 50
S1_R3_EXACT_BUDGET = 200
S1_R3_TRIAL_COUNT = 100


def causal_order_signature(arm: dict[str, Any]) -> tuple[str, ...]:
    """Return only components that can change or terminate the causal path.

    ``requirement_validator`` is deterministic observation/gating. R2 showed that
    moving it after ``final_validator`` did not create an independent intervention:
    A1 and A3 executed identical model-call/terminal sequences. R3 therefore
    requires unique signatures over retry, targeted_repair, and final_validator.
    """
    return tuple(part for part in _components(arm) if part != "requirement_validator")


def _action_matches(action: Action, spec: dict[str, Any]) -> bool:
    op = spec.get("op")
    path = spec.get("path")
    return (op is None or action.op == str(op)) and (path is None or action.path == str(path))


def compose_repair_patch(
    task: TaskCase,
    previous: Candidate | None,
    patch_actions: tuple[Action, ...] | list[Action],
    failed_ids: list[str],
    candidate_id: str,
) -> Candidate:
    """Compose a public repair patch onto previously correct work.

    Failed requirement evidence determines which old actions are eligible for
    removal. Unrelated actions survive. Patch actions then replace prior actions
    on the same state path and are appended in the model-returned order.
    """
    prior = list(previous.actions if previous is not None else ())
    failed = {str(value) for value in failed_ids}
    requirements = [req for req in task.requirements if req.id in failed]

    def remove_for_requirement(action: Action) -> bool:
        for req in requirements:
            if req.kind in {"equal", "preserve"} and action.path == req.path:
                return True
            if req.kind == "action_absent":
                if action.op == req.path and (req.expected is None or action.path == str(req.expected)):
                    return True
            if req.kind == "action_present":
                if action.op == req.path and (req.expected is None or action.path == str(req.expected)):
                    return True
            if req.kind == "action_before":
                before = req.metadata.get("before_action") if isinstance(req.metadata, dict) else None
                after = req.metadata.get("after_action") if isinstance(req.metadata, dict) else None
                if isinstance(before, dict) and _action_matches(action, before):
                    return True
                if isinstance(after, dict) and _action_matches(action, after):
                    return True
        return False

    retained = [action for action in prior if not remove_for_requirement(action)]
    patch = tuple(patch_actions)
    patch_paths = {action.path for action in patch}
    if patch_paths:
        retained = [action for action in retained if action.path not in patch_paths]
    composed = tuple(retained) + patch
    state = apply_actions(task.initial_state, composed)
    return Candidate(candidate_id, state, composed, configured_quality=1.0)


def _parse_patch(text: str) -> tuple[Action, ...] | None:
    try:
        value = json.loads(text)
        raw = value.get("actions") if isinstance(value, dict) else None
        if not isinstance(raw, list):
            return None
        return tuple(Action(str(row["op"]), str(row["path"]), row.get("value")) for row in raw)
    except Exception:
        return None


def _repair_call_r3(
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
        {
            "role": "system",
            "content": (
                "Return ONLY a JSON repair patch {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. "
                "Include only actions needed to fix the failed public requirements. The runtime composes this patch with "
                "previous_actions; do not repeat unrelated already-correct actions."
            ),
        },
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]
    _assert_public_prompt(messages)
    if "s1_r3_seed_failure" in json.dumps(messages, sort_keys=True):
        raise AssertionError("S1-R3 public prompt boundary violated: s1_r3_seed_failure")
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
    patch = _parse_patch(completion.text)
    repaired = None
    if patch is not None:
        try:
            repaired = compose_repair_patch(
                task,
                candidate,
                patch,
                failed_ids,
                f"{task_id}-{arm_id}-targeted-repair-r3",
            )
        except Exception:
            repaired = None
    return repaired, _call_row(
        completion,
        arm_id=arm_id,
        task_id=task_id,
        component="targeted_repair",
        role="repairer",
        model=str(model.model),
        active_intervention=active_intervention,
    )


def _r3_contract() -> dict[str, Any]:
    return {
        "protocol_revision": S1_R3_PROTOCOL_REVISION,
        "holdout": S1_R3_HOLDOUT,
        "matched_tasks": S1_R3_MATCHED_TASKS,
        "per_arm_call_cap": S1_R3_PER_ARM_CALL_CAP,
        "exact_budget": S1_R3_EXACT_BUDGET,
        "trial_count": S1_R3_TRIAL_COUNT,
        "seed_builder": build_seed_failure_r3,
        "case_prefix": "test3-s1-AR3-",
        "execution_mode": "balanced_task_blocks",
    }


def _run_fixed_task_r3(
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
    seed = build_seed_failure_r3(case)
    seed_status = _deterministic(task, seed)
    if seed_status["success"]:
        raise AssertionError("S1-R3 deterministic seed fixture unexpectedly succeeds")
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
                component, before, current,
                blocked_before=blocked_before, blocked_after=blocked,
                terminal=terminal, shadow_only=not active,
            ))

        elif component == "targeted_repair":
            active = not terminal and (not current["success"] or blocked)
            proposed, call = _repair_call_r3(
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
                component, before, current,
                blocked_before=blocked_before, blocked_after=blocked,
                terminal=terminal, shadow_only=not active,
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
                component, before, current,
                blocked_before=blocked_before, blocked_after=blocked,
                terminal=terminal,
            ))
        else:  # pragma: no cover
            raise ValueError(f"unknown S1-R3 component: {component}")

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


def _validate_r3_inputs(
    *,
    arm_rows: list[dict[str, Any]],
    cases: list[Any],
    model_by_name: dict[str, Any],
    best_single_model: str,
    repair_model: str,
    exact_budget: int,
) -> None:
    if len(arm_rows) != 4 or exact_budget != S1_R3_EXACT_BUDGET:
        raise ValueError("S1-R3 runtime requires the frozen four-arm exact-200-call contract")
    if tuple(str(row.get("arm_id") or "") for row in arm_rows) != S1_ARM_IDS:
        raise ValueError("S1-R3 runtime requires frozen A0-A3 arm identities")
    for arm in arm_rows:
        _validate_arm_protocol(arm, protocol_revision=S1_R3_PROTOCOL_REVISION)
        if int(arm.get("physical_call_cap") or 0) != S1_R3_PER_ARM_CALL_CAP:
            raise ValueError("S1-R3 requires exactly 50 physical calls per arm")
    signatures = [causal_order_signature(arm) for arm in arm_rows[1:]]
    if len(set(signatures)) != len(signatures):
        raise ValueError("S1-R3 causal-order collision: production/control fixed arms must have distinct causal signatures")
    if len(cases) < S1_R3_MATCHED_TASKS:
        raise ValueError("S1-R3 requires exactly 25 matched cases")
    selected = cases[:S1_R3_MATCHED_TASKS]
    if any(not str(case.case_id).startswith("test3-s1-AR3-") for case in selected):
        raise ValueError("S1-R3 received cases outside frozen holdout A-R3")
    for name in {best_single_model, repair_model}:
        model = model_by_name.get(name)
        if model is None:
            raise ValueError(f"missing S1-R3 model adapter: {name}")
        if int(getattr(model, "max_retries", 0) or 0) != 0:
            raise ValueError("S1-R3 model adapters must disable internal retries")


def _run_arm_task_r3(
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
    return _run_fixed_task_r3(
        case,
        arm,
        contract=contract,
        executor=executor,
        repairer=repairer,
        caller=caller,
        run_id=run_id,
    )


def run_s1_r3_screen(
    *,
    cases: list[Any],
    arms: Iterable[dict[str, Any]],
    model_by_name: dict[str, Any],
    best_single_model: str,
    repair_model: str,
    run_id: str,
    exact_budget: int = S1_R3_EXACT_BUDGET,
) -> dict[str, Any]:
    arm_rows = [dict(arm) for arm in arms]
    _validate_r3_inputs(
        arm_rows=arm_rows,
        cases=cases,
        model_by_name=model_by_name,
        best_single_model=best_single_model,
        repair_model=repair_model,
        exact_budget=exact_budget,
    )
    contract = _r3_contract()
    selected_cases = cases[:S1_R3_MATCHED_TASKS]
    arms_by_id = {str(arm["arm_id"]): arm for arm in arm_rows}
    signatures = {str(arm["arm_id"]): causal_order_signature(arm) for arm in arm_rows[1:]}

    budgets = {arm_id: PhysicalCallBudget(S1_R3_PER_ARM_CALL_CAP) for arm_id in S1_ARM_IDS}
    callers = {arm_id: BoundedModelCaller(budgets[arm_id]) for arm_id in S1_ARM_IDS}
    trials: list[dict[str, Any]] = []
    raw_calls: list[dict[str, Any]] = []
    validators: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = [{
        "event": "run_started",
        "run_id": run_id,
        "protocol_revision": S1_R3_PROTOCOL_REVISION,
        "holdout": S1_R3_HOLDOUT,
        "planned_physical_model_calls": exact_budget,
        "execution_mode": "balanced_task_blocks",
        "causal_order_signatures": {key: list(value) for key, value in signatures.items()},
    }]
    arm_active = {arm_id: 0 for arm_id in S1_ARM_IDS}
    arm_shadow = {arm_id: 0 for arm_id in S1_ARM_IDS}
    arm_first_ops = {arm_id: set() for arm_id in S1_ARM_IDS}
    execution_ordinal = 0

    for task_index, case in enumerate(selected_cases):
        for arm_position, arm_id in enumerate(r3_arm_order(task_index)):
            result = _run_arm_task_r3(
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
        if budget.physical_calls != S1_R3_PER_ARM_CALL_CAP:
            raise AssertionError(
                f"S1-R3 arm {arm_id} must consume exact 50-call reservation; used {budget.physical_calls}"
            )
        arm_accounting.append({
            "arm_id": arm_id,
            "physical_call_cap": S1_R3_PER_ARM_CALL_CAP,
            "physical_calls_used": budget.physical_calls,
            "physical_calls_remaining": budget.remaining,
            "cache_hits": budget.cache_hits,
            "calls_per_matched_task": S1_CALLS_PER_ARM_TASK,
            "matched_tasks_completed": S1_R3_MATCHED_TASKS,
            "active_inference_calls": arm_active[arm_id],
            "shadow_inference_calls": arm_shadow[arm_id],
            "first_active_components": sorted(arm_first_ops[arm_id]),
            "causal_order_signature": list(signatures[arm_id]) if arm_id in signatures else [],
        })

    total_calls = sum(int(row["physical_calls_used"]) for row in arm_accounting)
    if total_calls != S1_R3_EXACT_BUDGET or len(trials) != S1_R3_TRIAL_COUNT:
        raise AssertionError("S1-R3 exact physical-call/trial contract violated")
    if any(row.get("cache_hit") for row in raw_calls):
        raise AssertionError("S1-R3 must not use model-call cache hits")
    if any(not row.get("intervention_exposure_valid") for row in trials):
        raise AssertionError("S1-R3 intervention exposure contract failed")

    observed_schedule = [
        (int(row["task_index"]), int(row["arm_execution_position"]), str(row["arm_id"]))
        for row in trials
    ]
    expected_schedule = [
        (task_index, position, arm_id)
        for task_index in range(S1_R3_MATCHED_TASKS)
        for position, arm_id in enumerate(r3_arm_order(task_index))
    ]
    if observed_schedule != expected_schedule:
        raise AssertionError("S1-R3 balanced arm execution schedule drifted from preregistration")

    fixed_first_ops = {
        str(row.get("first_active_component") or "")
        for row in trials
        if row.get("arm_id") in {"S1-A1", "S1-A2", "S1-A3"}
    }
    fixed_first_ops.discard("")
    events.append({
        "event": "run_ended",
        "run_id": run_id,
        "physical_model_calls": total_calls,
        "protocol_valid_for_primary_claim": True,
    })
    return {
        "protocol_revision": S1_R3_PROTOCOL_REVISION,
        "holdout": S1_R3_HOLDOUT,
        "run_id": run_id,
        "physical_model_calls": total_calls,
        "exact_budget": exact_budget,
        "matched_task_limit": S1_R3_MATCHED_TASKS,
        "matched_task_ids": [case.case_id for case in selected_cases],
        "trials": trials,
        "model_calls": raw_calls,
        "validator_results": validators,
        "events": events,
        "arm_accounting": arm_accounting,
        "protocol_valid_for_primary_claim": True,
        "execution_mode": "balanced_task_blocks",
        "intervention_exposure": {
            "all_seed_failures_verified": all(bool(row.get("seed_failure_verified")) for row in trials),
            "all_arm_tasks_have_active_intervention": all(int(row.get("active_inference_calls") or 0) >= 1 for row in trials),
            "distinct_fixed_first_active_components": len(fixed_first_ops),
            "fixed_first_active_components": sorted(fixed_first_ops),
            "causal_order_signatures_unique": len(set(signatures.values())) == 3,
            "causal_order_signatures": {key: list(value) for key, value in signatures.items()},
        },
        "real_model_inference": any(str(getattr(model, "provider", "")) != "mock" for model in model_by_name.values()),
    }
