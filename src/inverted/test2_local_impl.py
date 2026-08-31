from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from typing import Any

from .domain import Action, Candidate, TaskCase
from .models import CompletionResult
from .oracle import apply_actions, evaluate_task
from .test2_analysis import (
    OutcomeSnapshot,
    capability_matrix,
    classify_transition,
    derive_layered_router,
    model_complementarity,
)
from .test2_cases import (
    build_audit_candidate_bank,
    build_execution_cases,
    build_formalization_cases,
    build_holdout_cases,
    build_repair_candidate_bank,
)
from .test2_types import CallIdentity, PhysicalCallBudget


LOCAL_MODELS = (
    "qwen3.5:9b-q8_0",
    "llama3.1:8b",
    "ministral-3:3b-instruct-2512-q8_0",
    "cogito:3b-v1-preview-llama-q8_0",
    "granite4:7b-a1b-h",
)

LOCAL_PHASE_LIMITS = {
    "formalization": 60,
    "execution": 60,
    "auditing": 100,
    "atomic_audit": 20,
    "repair_factorial": 80,
    "progressive_holdout": 110,
    "stability": 40,
    "reserve": 10,
}

PROGRESSIVE_PIPELINES = (
    "S0_BEST_SINGLE_ALL_ROLES",
    "S1_SPECIALIZE_FORMALIZER",
    "S2_SPECIALIZE_FORMALIZER_EXECUTOR",
    "S3_SPECIALIZE_FORMALIZER_EXECUTOR_REPAIR",
    "S4_FULL_SPECIALIZATION",
    "ALT_AUDIT_BEFORE_REPAIR",
    "ONE_SHOT_CONTROL",
)


@dataclass(frozen=True)
class LocalTest2Plan:
    models: tuple[str, ...] = LOCAL_MODELS
    max_physical_calls: int = 480
    planned_max_physical_calls: int = 480


@dataclass
class BoundedCompletion:
    text: str
    record: Any
    identity: str
    cache_hit: bool
    prompt: list[dict[str, str]]
    response: str


class BoundedModelCaller:
    def __init__(self, budget: PhysicalCallBudget):
        self.budget = budget
        self._cache: dict[str, BoundedCompletion] = {}
        self.calls: list[BoundedCompletion] = []

    @staticmethod
    def _settings(model: Any) -> dict[str, Any]:
        names = (
            "temperature", "max_tokens", "think", "format_json",
            "context_limit", "timeout_s", "max_retries", "retry_backoff_s",
        )
        return {name: getattr(model, name, None) for name in names if hasattr(model, name)}

    def complete(
        self,
        model: Any,
        messages: list[dict[str, str]],
        *,
        role: str,
        context: dict[str, Any],
        response_schema: Any = None,
        allow_cache: bool = True,
    ) -> BoundedCompletion:
        identity = CallIdentity.build(
            model=str(getattr(model, "model", "unknown")),
            role=role,
            messages=messages,
            settings=self._settings(model),
            response_schema=response_schema,
        ).digest
        if allow_cache and identity in self._cache:
            cached = self._cache[identity]
            self.budget.note_cache_hit(identity)
            item = BoundedCompletion(
                text=cached.text,
                record=cached.record,
                identity=identity,
                cache_hit=True,
                prompt=messages,
                response=cached.response,
            )
            self.calls.append(item)
            return item

        self.budget.consume(identity)
        result: CompletionResult = model.complete(messages, role=role, context=context)
        item = BoundedCompletion(
            text=result.text,
            record=result.record,
            identity=identity,
            cache_hit=False,
            prompt=messages,
            response=result.text,
        )
        if allow_cache:
            self._cache[identity] = item
        self.calls.append(item)
        return item


def build_local_plan() -> LocalTest2Plan:
    total = sum(LOCAL_PHASE_LIMITS.values())
    if total != 480:
        raise AssertionError(f"local Test-2 phase limits must sum to 480, got {total}")
    return LocalTest2Plan(planned_max_physical_calls=total)


def build_progressive_role_assignments(
    *, best_single: str, formalizer: str, executor: str, repairer: str, auditor: str
) -> list[dict[str, Any]]:
    return [
        {
            "pipeline": PROGRESSIVE_PIPELINES[0],
            "roles": {"formalizer": best_single, "executor": best_single, "repairer": best_single, "auditor": best_single},
            "specialized_roles": 0,
        },
        {
            "pipeline": PROGRESSIVE_PIPELINES[1],
            "roles": {"formalizer": formalizer, "executor": best_single, "repairer": best_single, "auditor": best_single},
            "specialized_roles": 1,
        },
        {
            "pipeline": PROGRESSIVE_PIPELINES[2],
            "roles": {"formalizer": formalizer, "executor": executor, "repairer": best_single, "auditor": best_single},
            "specialized_roles": 2,
        },
        {
            "pipeline": PROGRESSIVE_PIPELINES[3],
            "roles": {"formalizer": formalizer, "executor": executor, "repairer": repairer, "auditor": best_single},
            "specialized_roles": 3,
        },
        {
            "pipeline": PROGRESSIVE_PIPELINES[4],
            "roles": {"formalizer": formalizer, "executor": executor, "repairer": repairer, "auditor": auditor},
            "specialized_roles": 4,
        },
    ]


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


def _parse_json(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _parse_actions(text: str) -> tuple[Action, ...] | None:
    obj = _parse_json(text)
    if obj is None or not isinstance(obj.get("actions"), list):
        return None
    try:
        return tuple(Action(str(x["op"]), str(x["path"]), x.get("value")) for x in obj["actions"])
    except Exception:
        return None


def _candidate_from_actions(task: TaskCase, actions: tuple[Action, ...] | None, candidate_id: str) -> Candidate | None:
    if actions is None:
        return None
    try:
        state = apply_actions(task.initial_state, actions)
    except Exception:
        return None
    return Candidate(candidate_id, state, actions, configured_quality=1.0)


def _candidate_row(
    *, task: TaskCase, candidate: Candidate, case_id: str, source: str,
    model: str | None = None, pipeline: str | None = None, phase: str | None = None,
) -> dict[str, Any]:
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    return {
        "case_id": case_id,
        "task_id": task.id,
        "family": task.family,
        "complexity": task.complexity,
        "source": source,
        "phase": phase,
        "model": model,
        "pipeline": pipeline,
        "candidate_id": candidate.id,
        "actions": [a.to_dict() for a in candidate.actions],
        "final_state": candidate.state.to_dict(),
        "oracle_success": oracle.success,
        "catastrophic": oracle.catastrophic,
        "passed_requirements": list(oracle.passed_requirement_ids),
        "failed_requirements": list(oracle.failed_requirement_ids),
        "injected_faults": list(candidate.injected_faults),
    }


def _event(events: list[dict[str, Any]], **row: Any) -> None:
    events.append(row)


def _call_row(completion: BoundedCompletion, *, phase: str, task_id: str, model: str, role: str, pipeline: str | None = None) -> dict[str, Any]:
    record = completion.record.to_dict() if hasattr(completion.record, "to_dict") else {}
    return {
        "phase": phase,
        "task_id": task_id,
        "model": model,
        "role": role,
        "pipeline": pipeline,
        "call_identity": completion.identity,
        "cache_hit": completion.cache_hit,
        "prompt": completion.prompt,
        "response": completion.response,
        "telemetry": record,
    }


def _requirement_key(raw: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(raw.get("kind")), str(raw.get("path")),
        json.dumps(raw.get("expected"), sort_keys=True, default=str),
    )


def _formalization_score(task: TaskCase, text: str) -> dict[str, Any]:
    obj = _parse_json(text) or {}
    predicted = obj.get("requirements") if isinstance(obj.get("requirements"), list) else []
    truth = task.metadata.get("public_requirements", [])
    predicted_keys = {_requirement_key(x) for x in predicted if isinstance(x, dict)}
    truth_keys = {_requirement_key(x) for x in truth}
    tp = len(predicted_keys & truth_keys)
    critical_truth = {
        _requirement_key({"kind": req.kind, "path": req.path, "expected": req.expected})
        for req in task.requirements if req.critical
    }
    return {
        "precision": tp / len(predicted_keys) if predicted_keys else 0.0,
        "recall": tp / len(truth_keys) if truth_keys else 1.0,
        "critical_recall": len(predicted_keys & critical_truth) / len(critical_truth) if critical_truth else 1.0,
        "hallucinated_requirements": len(predicted_keys - truth_keys),
        "exact_ir": predicted_keys == truth_keys,
        "success": predicted_keys == truth_keys,
    }


def _rank_models(rows: list[dict[str, Any]], role: str, count: int = 2) -> list[str]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("role") == role:
            groups[str(row["model"])].append(row)
    return sorted(
        groups,
        key=lambda model: (
            -(sum(bool(r.get("success")) for r in groups[model]) / len(groups[model])),
            -sum(float(r.get("preservation_rate", 0.0) or 0.0) for r in groups[model]),
            model,
        ),
    )[:count]


def _phase_check(budget: PhysicalCallBudget, start: int, phase: str) -> int:
    used = budget.physical_calls - start
    limit = LOCAL_PHASE_LIMITS[phase]
    if used > limit:
        raise AssertionError(f"phase {phase} used {used} physical calls, exceeds limit {limit}")
    return used


def _formalize(
    *, caller: BoundedModelCaller, model: Any, task: TaskCase, run_id: str,
    trial_id: str, prompt_text: str, phase: str, raw_calls: list[dict[str, Any]],
    pipeline: str | None = None,
) -> tuple[dict[str, Any], BoundedCompletion]:
    messages = [
        {"role": "system", "content": "Convert the request into machine-checkable requirements. Return ONLY JSON {\"requirements\":[{\"id\":string,\"kind\":string,\"path\":string,\"expected\":any,\"metadata\":object}]}. Do not invent requirements."},
        {"role": "user", "content": prompt_text},
    ]
    result = caller.complete(
        model, messages, role="formalizer",
        context={"run_id": run_id, "trial_id": trial_id, "call_id": f"{trial_id}-{model.model}-formalize"},
        response_schema={"type": "object"},
    )
    raw_calls.append(_call_row(result, phase=phase, task_id=trial_id, model=model.model, role="formalizer", pipeline=pipeline))
    return _parse_json(result.text) or {"requirements": []}, result


def _execute(
    *, caller: BoundedModelCaller, model: Any, task: TaskCase, ir: dict[str, Any] | None,
    run_id: str, trial_id: str, phase: str, raw_calls: list[dict[str, Any]],
    candidates: list[dict[str, Any]], pipeline: str | None = None,
    direct: bool = False,
) -> tuple[Candidate | None, BoundedCompletion]:
    payload = _public_task(task)
    if ir is not None and not direct:
        payload["formalized_ir"] = ir
    instruction = "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. Satisfy every listed requirement and add no unintended actions."
    messages = [{"role": "system", "content": instruction}, {"role": "user", "content": json.dumps(payload, sort_keys=True)}]
    result = caller.complete(
        model, messages, role="executor",
        context={"run_id": run_id, "trial_id": trial_id, "call_id": f"{trial_id}-{model.model}-execute-{'direct' if direct else 'ir'}"},
        response_schema={"type": "object"},
    )
    raw_calls.append(_call_row(result, phase=phase, task_id=trial_id, model=model.model, role="executor", pipeline=pipeline))
    candidate = _candidate_from_actions(task, _parse_actions(result.text), f"{trial_id}-{model.model}-exec")
    if candidate is not None:
        candidates.append(_candidate_row(task=task, candidate=candidate, case_id=trial_id, source="model_executor", model=model.model, pipeline=pipeline, phase=phase))
    return candidate, result


def _audit(
    *, caller: BoundedModelCaller, model: Any, task: TaskCase, candidate: Candidate | None,
    run_id: str, trial_id: str, phase: str, raw_calls: list[dict[str, Any]],
    pipeline: str | None = None, atomic: bool = False, allow_cache: bool = True,
) -> tuple[bool | None, dict[str, Any], BoundedCompletion]:
    payload = _public_task(task) | {
        "candidate_actions": [a.to_dict() for a in candidate.actions] if candidate else [],
        "candidate_final_state": candidate.state.to_dict() if candidate else None,
    }
    if atomic:
        system = "Evaluate EACH requirement independently before the final decision. Return ONLY JSON {\"requirements\":[{\"id\":string,\"pass\":true|false,\"reason\":string}],\"accept\":true|false}. accept may be true only if every requirement passes and there is no unintended behavior."
        role = "atomic_auditor"
    else:
        system = "Audit the candidate exhaustively. Return ONLY JSON {\"accept\":true|false,\"failed_requirements\":[string],\"reason\":string}. Reject any missing, wrong, prohibited, ordered-wrong, or unintended behavior."
        role = "auditor"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, sort_keys=True)}]
    result = caller.complete(
        model, messages, role=role,
        context={"run_id": run_id, "trial_id": trial_id, "candidate_id": candidate.id if candidate else None, "call_id": f"{trial_id}-{model.model}-{role}"},
        response_schema={"type": "object"}, allow_cache=allow_cache,
    )
    raw_calls.append(_call_row(result, phase=phase, task_id=trial_id, model=model.model, role=role, pipeline=pipeline))
    parsed = _parse_json(result.text) or {}
    accept = parsed.get("accept") if isinstance(parsed.get("accept"), bool) else None
    return accept, parsed, result


def _repair(
    *, caller: BoundedModelCaller, model: Any, task: TaskCase, candidate: Candidate | None,
    failed_ids: list[str], run_id: str, trial_id: str, phase: str,
    raw_calls: list[dict[str, Any]], candidates: list[dict[str, Any]],
    pipeline: str | None, feedback_style: str = "structured", strategy: str = "targeted",
) -> tuple[Candidate | None, BoundedCompletion]:
    req_by_id = {r.id: r for r in task.requirements}
    if feedback_style == "raw":
        feedback: Any = {"failed_requirements": failed_ids}
    else:
        feedback = {
            "failed_requirements": [
                {
                    "id": rid,
                    "path": req_by_id[rid].path,
                    "observed": candidate.state.get(req_by_id[rid].path) if candidate is not None and rid in req_by_id else None,
                    "expected": req_by_id[rid].expected,
                    "admissible": [req_by_id[rid].expected],
                }
                for rid in failed_ids if rid in req_by_id
            ]
        }
    system = (
        "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. "
        + ("Repair only failed parts and preserve every already-correct requirement." if strategy == "targeted" else "Regenerate the complete action plan from scratch.")
    )
    payload = _public_task(task) | {
        "previous_actions": [a.to_dict() for a in candidate.actions] if candidate else [],
        "validator_feedback": feedback,
    }
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, sort_keys=True)}]
    result = caller.complete(
        model, messages, role="repairer",
        context={"run_id": run_id, "trial_id": trial_id, "candidate_id": candidate.id if candidate else None, "call_id": f"{trial_id}-{model.model}-repair-{feedback_style}-{strategy}"},
        response_schema={"type": "object"},
    )
    raw_calls.append(_call_row(result, phase=phase, task_id=trial_id, model=model.model, role="repairer", pipeline=pipeline))
    repaired = _candidate_from_actions(task, _parse_actions(result.text), f"{trial_id}-{model.model}-repair")
    if repaired is not None:
        candidates.append(_candidate_row(task=task, candidate=repaired, case_id=trial_id, source="model_repair", model=model.model, pipeline=pipeline, phase=phase))
    return repaired, result


def _oracle_snapshot(task: TaskCase, candidate: Candidate | None, *, blocked: bool = False) -> OutcomeSnapshot:
    if candidate is None:
        return OutcomeSnapshot(False, blocked=blocked, failure_signature="parse_or_execution")
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    return OutcomeSnapshot(
        success=bool(oracle.success and not blocked),
        catastrophic=bool(oracle.catastrophic and not blocked),
        blocked=blocked,
        failure_signature=None if oracle.success else (",".join(oracle.failed_requirement_ids) or "oracle_failure"),
    )


def _run_full_pipeline(
    *, case: Any, roles: dict[str, str], model_by_name: dict[str, Any], caller: BoundedModelCaller,
    run_id: str, phase: str, raw_calls: list[dict[str, Any]], candidates: list[dict[str, Any]],
    events: list[dict[str, Any]], pipeline: str, audit_before_repair: bool = False,
) -> dict[str, Any]:
    start_physical = caller.budget.physical_calls
    start_logical = len(caller.calls)
    task = case.task

    fmodel = model_by_name[roles["formalizer"]]
    ir, _ = _formalize(
        caller=caller, model=fmodel, task=task, run_id=run_id,
        trial_id=f"{case.case_id}-{pipeline}", prompt_text=task.goal,
        phase=phase, raw_calls=raw_calls, pipeline=pipeline,
    )
    _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="formalizer", model=fmodel.model, exact_ir=_formalization_score(task, json.dumps(ir)).get("exact_ir", False))

    emodel = model_by_name[roles["executor"]]
    candidate, _ = _execute(
        caller=caller, model=emodel, task=task, ir=ir, run_id=run_id,
        trial_id=f"{case.case_id}-{pipeline}", phase=phase, raw_calls=raw_calls,
        candidates=candidates, pipeline=pipeline,
    )
    initial_snapshot = _oracle_snapshot(task, candidate)
    initial_oracle = evaluate_task(task, candidate.state, candidate.actions) if candidate else None
    failed_ids = list(initial_oracle.failed_requirement_ids) if initial_oracle else ["parse_or_execution"]
    _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="executor", model=emodel.model, success=initial_snapshot.success, failure_signature=initial_snapshot.failure_signature)

    auditor_accept: bool | None = None
    if audit_before_repair:
        amodel = model_by_name[roles["auditor"]]
        auditor_accept, _, _ = _audit(
            caller=caller, model=amodel, task=task, candidate=candidate, run_id=run_id,
            trial_id=f"{case.case_id}-{pipeline}-pre-repair", phase=phase,
            raw_calls=raw_calls, pipeline=pipeline,
        )
        _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="auditor_pre_repair", model=amodel.model, accept=auditor_accept, oracle_success=initial_snapshot.success)
        # Audit-first only triggers repair on explicit rejection. A false accept
        # reaches final deterministic authority and is blocked there.
        needs_repair = auditor_accept is False
    else:
        needs_repair = not initial_snapshot.success

    repaired = False
    if needs_repair:
        rmodel = model_by_name[roles["repairer"]]
        repaired_candidate, _ = _repair(
            caller=caller, model=rmodel, task=task, candidate=candidate,
            failed_ids=failed_ids, run_id=run_id,
            trial_id=f"{case.case_id}-{pipeline}", phase=phase,
            raw_calls=raw_calls, candidates=candidates, pipeline=pipeline,
        )
        if repaired_candidate is not None:
            candidate = repaired_candidate
        repaired = True
        _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="repair", model=rmodel.model, success=_oracle_snapshot(task, candidate).success)

    deterministic = _oracle_snapshot(task, candidate)
    _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="deterministic_revalidation", success=deterministic.success, catastrophic=deterministic.catastrophic)

    if not audit_before_repair:
        amodel = model_by_name[roles["auditor"]]
        auditor_accept, _, _ = _audit(
            caller=caller, model=amodel, task=task, candidate=candidate, run_id=run_id,
            trial_id=f"{case.case_id}-{pipeline}", phase=phase,
            raw_calls=raw_calls, pipeline=pipeline,
        )
        _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="auditor", model=amodel.model, accept=auditor_accept, oracle_success=deterministic.success)

    final_success = bool(deterministic.success and auditor_accept is True)
    blocked = bool(not deterministic.success or auditor_accept is not True)
    final = OutcomeSnapshot(
        success=final_success,
        catastrophic=bool(deterministic.catastrophic and not blocked),
        blocked=blocked,
        failure_signature=None if final_success else (
            deterministic.failure_signature if not deterministic.success else "auditor_reject_or_parse"
        ),
    )
    return {
        "phase": phase,
        "role": "pipeline",
        "pipeline": pipeline,
        "task_id": case.case_id,
        "family": task.family,
        "complexity": task.complexity,
        "model": "layered" if len(set(roles.values())) > 1 else next(iter(roles.values())),
        "roles": dict(roles),
        "success": final.success,
        "catastrophic": final.catastrophic,
        "blocked": final.blocked,
        "failure_class": final.failure_signature,
        "initial_executor_success": initial_snapshot.success,
        "repair_used": repaired,
        "auditor_accept": auditor_accept,
        "logical_calls": len(caller.calls) - start_logical,
        "physical_calls_added": caller.budget.physical_calls - start_physical,
    }


def run_local_campaign(models: list[Any], run_id: str = "test2-local", hard_limit: int = 480) -> dict[str, Any]:
    if tuple(str(getattr(model, "model", "")) for model in models) != LOCAL_MODELS:
        raise ValueError(f"local Test-2 models must be exactly {LOCAL_MODELS!r}")
    if hard_limit > 480:
        raise ValueError("hard_limit may not exceed the preregistered 480-call ceiling")

    budget = PhysicalCallBudget(max_calls=hard_limit)
    caller = BoundedModelCaller(budget)
    rows: list[dict[str, Any]] = []
    raw_calls: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    validator_results: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    phase_usage: dict[str, int] = {}
    model_by_name = {str(model.model): model for model in models}

    # Phase 1: formalization — 12 matched representation/task cases x 5.
    start = budget.physical_calls
    formalization_cases = build_formalization_cases()
    for model in models:
        for case in formalization_cases:
            parsed, result = _formalize(
                caller=caller, model=model, task=case.task, run_id=run_id,
                trial_id=case.case_id, prompt_text=case.prompt_text,
                phase="formalization", raw_calls=raw_calls,
            )
            score = _formalization_score(case.task, result.text)
            row = {
                "phase": "formalization", "role": "formalizer", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "representation": case.representation, "model": model.model, **score,
            }
            rows.append(row)
            _event(events, phase="formalization", task_id=case.case_id, model=model.model, success=score["success"], representation=case.representation)
    phase_usage["formalization"] = _phase_check(budget, start, "formalization")

    # Phase 2: one-shot execution — 3 families x 4 complexities x 5.
    start = budget.physical_calls
    execution_cases = build_execution_cases()
    for model in models:
        for case in execution_cases:
            candidate, _ = _execute(
                caller=caller, model=model, task=case.task, ir=None, run_id=run_id,
                trial_id=case.case_id, phase="execution", raw_calls=raw_calls,
                candidates=candidates, direct=True,
            )
            oracle = evaluate_task(case.task, candidate.state, candidate.actions) if candidate else None
            success = bool(oracle and oracle.success)
            row = {
                "phase": "execution", "role": "executor", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "requirement_count": len(case.task.requirements), "model": model.model,
                "success": success,
                "requirement_accuracy": (
                    len(oracle.passed_requirement_ids) / len(case.task.requirements)
                    if oracle is not None and case.task.requirements else (1.0 if oracle else 0.0)
                ),
                "failure_class": "parser_or_execution" if oracle is None else (",".join(oracle.failed_requirement_ids) if not success else None),
            }
            rows.append(row)
            _event(events, phase="execution", task_id=case.case_id, model=model.model, success=success, failure_class=row["failure_class"])
    phase_usage["execution"] = _phase_check(budget, start, "execution")

    # Phase 3: fixed-candidate holistic audit — exact same 20 candidates x 5.
    start = budget.physical_calls
    audit_bank = build_audit_candidate_bank()
    for case in audit_bank:
        candidates.append(_candidate_row(task=case.task, candidate=case.candidate, case_id=case.case_id, source="fixed_audit_bank", phase="auditing"))
    for model in models:
        for case in audit_bank:
            accept, parsed, _ = _audit(
                caller=caller, model=model, task=case.task, candidate=case.candidate,
                run_id=run_id, trial_id=case.case_id, phase="auditing", raw_calls=raw_calls,
            )
            correct = accept is not None and accept == case.oracle_success
            fault = case.candidate.injected_faults[0] if case.candidate.injected_faults else "none"
            row = {
                "phase": "auditing", "role": "auditor", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "requirement_count": len(case.task.requirements), "fault": fault,
                "model": model.model, "success": bool(correct), "oracle_success": case.oracle_success,
                "accept": accept,
                "tp": int(case.oracle_success and accept is True),
                "tn": int((not case.oracle_success) and accept is False),
                "fp": int((not case.oracle_success) and accept is True),
                "fn": int(case.oracle_success and accept is False),
                "reported_failed_requirements": list(parsed.get("failed_requirements") or []),
            }
            rows.append(row)
            _event(events, phase="auditing", task_id=case.case_id, model=model.model, decision="accept" if accept is True else "reject" if accept is False else "parse_failure", oracle_success=case.oracle_success, correct=bool(correct), fault=fault)
    phase_usage["auditing"] = _phase_check(budget, start, "auditing")

    top_auditors = _rank_models(rows, "auditor", 2)

    # Phase 4: atomic audit comparison — top 2 x 10 invalid/hard candidates.
    start = budget.physical_calls
    atomic_cases = [case for case in audit_bank if not case.oracle_success][:10]
    for model_name in top_auditors:
        model = model_by_name[model_name]
        for case in atomic_cases:
            accept, parsed, _ = _audit(
                caller=caller, model=model, task=case.task, candidate=case.candidate,
                run_id=run_id, trial_id=case.case_id, phase="atomic_audit",
                raw_calls=raw_calls, atomic=True,
            )
            correct = accept is not None and accept == case.oracle_success
            row = {
                "phase": "atomic_audit", "role": "atomic_auditor", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "requirement_count": len(case.task.requirements),
                "fault": case.candidate.injected_faults[0] if case.candidate.injected_faults else "none",
                "model": model_name, "success": bool(correct), "oracle_success": case.oracle_success,
                "accept": accept, "requirement_judgments": parsed.get("requirements") or [],
            }
            rows.append(row)
            _event(events, phase="atomic_audit", task_id=case.case_id, model=model_name, accept=accept, correct=bool(correct))
    phase_usage["atomic_audit"] = _phase_check(budget, start, "atomic_audit")

    # Phase 5: 2x2 repair factorial — top two executors x 10 failures x 4 conditions.
    start = budget.physical_calls
    repair_candidates = build_repair_candidate_bank()
    for case in repair_candidates:
        candidates.append(_candidate_row(task=case.task, candidate=case.candidate, case_id=case.case_id, source="fixed_repair_bank", phase="repair_factorial"))
    top_repair_candidates = _rank_models(rows, "executor", 2)
    for model_name in top_repair_candidates:
        model = model_by_name[model_name]
        for case in repair_candidates:
            original = evaluate_task(case.task, case.candidate.state, case.candidate.actions)
            original_passed = set(original.passed_requirement_ids)
            for feedback_style in ("raw", "structured"):
                for strategy in ("regenerate", "targeted"):
                    repaired_candidate, _ = _repair(
                        caller=caller, model=model, task=case.task, candidate=case.candidate,
                        failed_ids=list(original.failed_requirement_ids), run_id=run_id,
                        trial_id=f"{case.case_id}-{feedback_style}-{strategy}", phase="repair_factorial",
                        raw_calls=raw_calls, candidates=candidates, pipeline=None,
                        feedback_style=feedback_style, strategy=strategy,
                    )
                    oracle = evaluate_task(case.task, repaired_candidate.state, repaired_candidate.actions) if repaired_candidate else None
                    new_passed = set(oracle.passed_requirement_ids) if oracle else set()
                    row = {
                        "phase": "repair_factorial", "role": "repairer", "task_id": case.case_id,
                        "family": case.task.family, "complexity": case.task.complexity,
                        "fault": case.candidate.injected_faults[0] if case.candidate.injected_faults else "none",
                        "model": model_name, "feedback_style": feedback_style, "strategy": strategy,
                        "success": bool(oracle and oracle.success),
                        "original_passed": len(original_passed),
                        "preserved_passed": len(original_passed & new_passed),
                        "new_failures_introduced": len(original_passed - new_passed),
                        "failed_requirements_repaired": len(set(original.failed_requirement_ids) & new_passed),
                        "preservation_rate": len(original_passed & new_passed) / len(original_passed) if original_passed else 1.0,
                    }
                    rows.append(row)
                    repairs.append(row)
                    _event(events, phase="repair_factorial", task_id=case.case_id, model=model_name, feedback_style=feedback_style, strategy=strategy, success=row["success"], preservation_rate=row["preservation_rate"], new_failures_introduced=row["new_failures_introduced"])
    phase_usage["repair_factorial"] = _phase_check(budget, start, "repair_factorial")

    # Derive role champions only from phases where the role was directly tested.
    formalizer_champion = (_rank_models(rows, "formalizer", 1) or [LOCAL_MODELS[0]])[0]
    executor_champion = (_rank_models(rows, "executor", 1) or [LOCAL_MODELS[0]])[0]
    repair_champion = (_rank_models(rows, "repairer", 1) or [executor_champion])[0]
    auditor_champion = (top_auditors or [LOCAL_MODELS[0]])[0]

    pooled: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        if row.get("role") in {"formalizer", "executor", "auditor"}:
            pooled[str(row["model"])].append(bool(row.get("success")))
    best_single = sorted(pooled, key=lambda m: (-(sum(pooled[m]) / len(pooled[m])), m))[0]

    progressive_assignments = build_progressive_role_assignments(
        best_single=best_single,
        formalizer=formalizer_champion,
        executor=executor_champion,
        repairer=repair_champion,
        auditor=auditor_champion,
    )

    # Phase 6: four hard, untouched holdouts. Worst-case 25 logical calls/task
    # across the approved seven pipelines = 100, below the 110 allocation.
    start = budget.physical_calls
    holdout_all = build_holdout_cases()
    hard_holdouts = [
        next(case for case in holdout_all if case.task.family == "state" and case.task.complexity == 4),
        next(case for case in holdout_all if case.task.family == "policy" and case.task.complexity == 4),
        next(case for case in holdout_all if case.task.family == "reconciliation" and case.task.complexity == 4),
        next(case for case in holdout_all if case.task.family == "policy" and case.task.complexity == 3),
    ]
    progressive_transitions: list[dict[str, Any]] = []
    holdout_rows: list[dict[str, Any]] = []
    for case in hard_holdouts:
        per_task: list[dict[str, Any]] = []
        for assignment in progressive_assignments:
            row = _run_full_pipeline(
                case=case, roles=assignment["roles"], model_by_name=model_by_name,
                caller=caller, run_id=run_id, phase="progressive_holdout",
                raw_calls=raw_calls, candidates=candidates, events=events,
                pipeline=assignment["pipeline"], audit_before_repair=False,
            )
            row["specialized_roles"] = assignment["specialized_roles"]
            rows.append(row); holdout_rows.append(row); per_task.append(row)

        full_roles = progressive_assignments[-1]["roles"]
        alt = _run_full_pipeline(
            case=case, roles=full_roles, model_by_name=model_by_name,
            caller=caller, run_id=run_id, phase="progressive_holdout",
            raw_calls=raw_calls, candidates=candidates, events=events,
            pipeline=PROGRESSIVE_PIPELINES[5], audit_before_repair=True,
        )
        alt["specialized_roles"] = 4
        rows.append(alt); holdout_rows.append(alt)

        control_model = model_by_name[best_single]
        physical_before = budget.physical_calls
        logical_before = len(caller.calls)
        control_candidate, _ = _execute(
            caller=caller, model=control_model, task=case.task, ir=None, run_id=run_id,
            trial_id=f"{case.case_id}-one-shot", phase="progressive_holdout",
            raw_calls=raw_calls, candidates=candidates, pipeline=PROGRESSIVE_PIPELINES[6], direct=True,
        )
        control_snapshot = _oracle_snapshot(case.task, control_candidate)
        control = {
            "phase": "progressive_holdout", "role": "pipeline", "pipeline": PROGRESSIVE_PIPELINES[6],
            "task_id": case.case_id, "family": case.task.family, "complexity": case.task.complexity,
            "model": best_single, "roles": {"executor": best_single}, "success": control_snapshot.success,
            "catastrophic": control_snapshot.catastrophic, "blocked": False,
            "failure_class": control_snapshot.failure_signature, "specialized_roles": 0,
            "logical_calls": len(caller.calls) - logical_before,
            "physical_calls_added": budget.physical_calls - physical_before,
        }
        rows.append(control); holdout_rows.append(control)
        _event(events, phase="progressive_holdout", task_id=case.case_id, pipeline=PROGRESSIVE_PIPELINES[6], stage="one_shot_control", model=best_single, success=control_snapshot.success)

        for previous, current in zip(per_task, per_task[1:]):
            before = OutcomeSnapshot(bool(previous["success"]), bool(previous["catastrophic"]), bool(previous["blocked"]), previous.get("failure_class"))
            after = OutcomeSnapshot(bool(current["success"]), bool(current["catastrophic"]), bool(current["blocked"]), current.get("failure_class"))
            progressive_transitions.append({
                "task_id": case.case_id,
                "from_pipeline": previous["pipeline"],
                "to_pipeline": current["pipeline"],
                "transition": classify_transition(before, after),
                "from_success": before.success,
                "to_success": after.success,
            })
    phase_usage["progressive_holdout"] = _phase_check(budget, start, "progressive_holdout")

    # Phase 7: independent repeat on 8 fixed audit cells x all five models.
    start = budget.physical_calls
    stability_cases = audit_bank[:8]
    initial_audit = {
        (str(row["model"]), str(row["task_id"])): row
        for row in rows if row.get("phase") == "auditing"
    }
    stability_labels: list[dict[str, Any]] = []
    for model in models:
        for case in stability_cases:
            accept, _, _ = _audit(
                caller=caller, model=model, task=case.task, candidate=case.candidate,
                run_id=run_id, trial_id=f"{case.case_id}-stability", phase="stability",
                raw_calls=raw_calls, allow_cache=False,
            )
            correct = isinstance(accept, bool) and accept == case.oracle_success
            initial = initial_audit.get((model.model, case.case_id))
            stable = initial is not None and initial.get("accept") == accept
            label = "STABLE" if stable else "UNSTABLE" if initial is not None else "PROVISIONAL"
            row = {
                "phase": "stability", "role": "auditor", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "model": model.model, "success": bool(correct), "oracle_success": case.oracle_success,
                "accept": accept, "stability": label,
            }
            rows.append(row); stability_labels.append(row)
            _event(events, phase="stability", task_id=case.case_id, model=model.model, accept=accept, correct=bool(correct), stability=label)
    phase_usage["stability"] = _phase_check(budget, start, "stability")

    if budget.physical_calls > hard_limit:
        raise AssertionError("physical call ceiling violated")

    # Derived model specialization/routing requires no extra inference.
    baseline_role_rows = [
        row for row in rows if row.get("role") in {"formalizer", "executor", "auditor", "repairer"}
        and row.get("phase") != "stability"
    ]
    layered = derive_layered_router(baseline_role_rows)
    outcome_map: dict[str, dict[str, bool]] = defaultdict(dict)
    for row in baseline_role_rows:
        outcome_map[str(row["task_id"])][str(row["model"])] = bool(row.get("success"))
    pair_rows = []
    for index, model_a in enumerate(LOCAL_MODELS):
        for model_b in LOCAL_MODELS[index + 1:]:
            pair_rows.append(model_complementarity(outcome_map, model_a, model_b))

    role_champions = {
        "formalizer": formalizer_champion,
        "executor": executor_champion,
        "repairer": repair_champion,
        "auditor": auditor_champion,
    }
    return {
        "run_id": run_id,
        "physical_model_calls": budget.physical_calls,
        "cache_hits": budget.cache_hits,
        "hard_call_limit": hard_limit,
        "models": list(LOCAL_MODELS),
        "phase_limits": dict(LOCAL_PHASE_LIMITS),
        "phase_physical_calls": phase_usage,
        "records": rows,
        "raw_calls": raw_calls,
        "repairs": repairs,
        "validator_results": validator_results,
        "candidates": candidates,
        "events": events,
        "progressive_transitions": progressive_transitions,
        "stability_labels": stability_labels,
        "role_champions": role_champions,
        "layered_router": layered,
        "model_pair_synergy": pair_rows,
        "holdout_pipeline_rows": holdout_rows,
        "capability_by_role_model": capability_matrix(baseline_role_rows, ("role", "model")),
        "capability_by_family_model": capability_matrix(baseline_role_rows, ("family", "model")),
        "capability_by_fault_model": capability_matrix([r for r in baseline_role_rows if r.get("fault") is not None], ("fault", "model")),
        "capability_by_complexity_model": capability_matrix(baseline_role_rows, ("complexity", "model")),
        "capability_by_representation_model": capability_matrix([r for r in baseline_role_rows if r.get("representation") is not None], ("representation", "model")),
    }
