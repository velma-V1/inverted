from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
from typing import Any

from .domain import Action, Candidate, TaskCase
from .models import CompletionResult
from .oracle import apply_actions, evaluate_task
from .test2_analysis import OutcomeSnapshot, classify_transition, derive_layered_router, model_complementarity
from .test2_cases import (
    build_audit_candidate_bank,
    build_execution_cases,
    build_formalization_cases,
    build_holdout_cases,
    build_repair_candidate_bank,
)
from .test2_gold import evaluate_test2_gold
from .test2_local_analysis import (
    audit_confusion_by_model,
    balanced_role_model_scores,
    build_layered_capability_outputs,
    progressive_compounding_effects,
    rank_auditors,
    repair_factorial_effects,
    select_stability_task_ids,
    structured_failure_feedback,
)
from .test2_types import CallIdentity, PhysicalCallBudget


LOCAL_MODELS = (
    "qwen3.5:9b-q8_0",
    "llama3.1:8b",
    "ministral-3:3b-instruct-2512-q8_0",
    "cogito:3b-v1-preview-llama-q8_0",
    "granite4:7b-a1b-h",
)

# The phase reservations sum to the hard ceiling. Actual planned worst-case
# physical use is <=477 because repair uses 97 and reserve is deliberately 0.
LOCAL_PHASE_LIMITS = {
    "formalization": 60,
    "execution": 60,
    "auditing": 100,
    "atomic_audit": 20,
    "repair_factorial": 100,
    "progressive_holdout": 100,
    "stability": 40,
    "reserve": 0,
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
    planned_max_physical_calls: int = 477


@dataclass
class BoundedCompletion:
    text: str
    record: Any
    identity: str
    cache_hit: bool
    prompt: list[dict[str, str]]
    response: str
    logical_index: int = 0
    physical_call_number: int | None = None


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
        logical_index = len(self.calls) + 1
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
                logical_index=logical_index,
                physical_call_number=None,
            )
            self.calls.append(item)
            return item

        self.budget.consume(identity)
        physical_number = self.budget.physical_calls
        result: CompletionResult = model.complete(messages, role=role, context=context)
        item = BoundedCompletion(
            text=result.text,
            record=result.record,
            identity=identity,
            cache_hit=False,
            prompt=messages,
            response=result.text,
            logical_index=logical_index,
            physical_call_number=physical_number,
        )
        if allow_cache:
            self._cache[identity] = item
        self.calls.append(item)
        return item


def build_local_plan() -> LocalTest2Plan:
    if sum(LOCAL_PHASE_LIMITS.values()) != 480:
        raise AssertionError("local Test-2 phase reservations must sum to 480")
    return LocalTest2Plan()


def build_progressive_role_assignments(
    *, best_single: str, formalizer: str, executor: str, repairer: str, auditor: str
) -> list[dict[str, Any]]:
    return [
        {"pipeline": PROGRESSIVE_PIPELINES[0], "roles": {"formalizer": best_single, "executor": best_single, "repairer": best_single, "auditor": best_single}, "specialized_roles": 0},
        {"pipeline": PROGRESSIVE_PIPELINES[1], "roles": {"formalizer": formalizer, "executor": best_single, "repairer": best_single, "auditor": best_single}, "specialized_roles": 1},
        {"pipeline": PROGRESSIVE_PIPELINES[2], "roles": {"formalizer": formalizer, "executor": executor, "repairer": best_single, "auditor": best_single}, "specialized_roles": 2},
        {"pipeline": PROGRESSIVE_PIPELINES[3], "roles": {"formalizer": formalizer, "executor": executor, "repairer": repairer, "auditor": best_single}, "specialized_roles": 3},
        {"pipeline": PROGRESSIVE_PIPELINES[4], "roles": {"formalizer": formalizer, "executor": executor, "repairer": repairer, "auditor": auditor}, "specialized_roles": 4},
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


def build_executor_payload(task: TaskCase, *, ir: dict[str, Any] | None, direct: bool) -> dict[str, Any]:
    if direct:
        return _public_task(task)
    if ir is None:
        raise ValueError("layered execution requires formalized IR")
    # Scientific isolation: downstream execution may not see the original goal
    # or oracle/public requirements, otherwise formalizer errors are bypassable.
    return {
        "task_id": task.id,
        "family": task.family,
        "complexity": task.complexity,
        "initial_state": task.initial_state.to_dict(),
        "allowed_ops": list(task.allowed_ops),
        "formalized_ir": ir,
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


def _requirement_key(raw: dict[str, Any]) -> tuple[Any, ...]:
    return (str(raw.get("kind")), str(raw.get("path")), json.dumps(raw.get("expected"), sort_keys=True, default=str))


def _ir_actions(task: TaskCase, ir: dict[str, Any]) -> tuple[Action, ...] | None:
    raw = ir.get("requirements")
    if not isinstance(raw, list):
        return None
    actions: list[Action] = []
    try:
        for req in raw:
            if not isinstance(req, dict):
                continue
            kind = str(req.get("kind"))
            path = str(req.get("path"))
            expected = req.get("expected")
            metadata = req.get("metadata") or {}
            if kind == "equal":
                default_op = "resolve" if "resolve" in task.allowed_ops and path.startswith("resolved.") else "set"
                actions.append(Action(str(metadata.get("op", default_op)), path, expected))
            elif kind == "action_before":
                after = metadata.get("after_action")
                if isinstance(after, dict):
                    candidate = Action(str(after.get("op")), str(after.get("path")), after.get("value"))
                    if not any((a.op, a.path, a.value) == (candidate.op, candidate.path, candidate.value) for a in actions):
                        actions.append(candidate)
            elif kind in {"action_absent", "preserve"}:
                continue
        return tuple(actions)
    except Exception:
        return None


def _formalization_score(task: TaskCase, text: str) -> dict[str, Any]:
    obj = _parse_json(text) or {}
    predicted = obj.get("requirements") if isinstance(obj.get("requirements"), list) else []
    truth = task.metadata.get("public_requirements", [])
    predicted_keys = {_requirement_key(x) for x in predicted if isinstance(x, dict)}
    truth_keys = {_requirement_key(x) for x in truth}
    tp = len(predicted_keys & truth_keys)
    critical_truth = {_requirement_key({"kind": req.kind, "path": req.path, "expected": req.expected}) for req in task.requirements if req.critical}
    actions = _ir_actions(task, obj)
    downstream = False
    if actions is not None:
        try:
            state = apply_actions(task.initial_state, actions)
            downstream = evaluate_task(task, state, actions).success
        except Exception:
            downstream = False
    return {
        "precision": tp / len(predicted_keys) if predicted_keys else 0.0,
        "recall": tp / len(truth_keys) if truth_keys else 1.0,
        "critical_recall": len(predicted_keys & critical_truth) / len(critical_truth) if critical_truth else 1.0,
        "hallucinated_requirements": len(predicted_keys - truth_keys),
        "missing_requirements": len(truth_keys - predicted_keys),
        "predicted_requirement_count": len(predicted_keys),
        "truth_requirement_count": len(truth_keys),
        "exact_ir": predicted_keys == truth_keys,
        "downstream_oracle_solvable": bool(downstream),
        "success": predicted_keys == truth_keys,
    }


def _evaluation_id(phase: str, role: str, task_id: str, **condition: Any) -> str:
    suffix = "|".join(f"{key}={condition[key]}" for key in sorted(condition) if condition[key] is not None)
    return f"{phase}|{role}|{task_id}" + (f"|{suffix}" if suffix else "")


def _candidate_row(*, task: TaskCase, candidate: Candidate, case_id: str, source: str, model: str | None = None, pipeline: str | None = None, phase: str | None = None) -> dict[str, Any]:
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    gold = evaluate_test2_gold(task, candidate)
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
        "deterministic_success": oracle.success,
        "hidden_gold_success": gold.success,
        "semantic_clean": gold.semantic_clean,
        "semantic_issues": list(gold.semantic_issues),
        "catastrophic": oracle.catastrophic,
        "passed_requirements": list(oracle.passed_requirement_ids),
        "failed_requirements": list(oracle.failed_requirement_ids),
        "injected_faults": list(candidate.injected_faults),
    }


def _event(events: list[dict[str, Any]], **row: Any) -> None:
    events.append({"event_index": len(events) + 1, **row})


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
        "logical_call_index": completion.logical_index,
        "physical_call_number": completion.physical_call_number,
        "prompt": completion.prompt,
        "response": completion.response,
        "telemetry": record,
    }


def _validator_row(task: TaskCase, candidate: Candidate | None, *, phase: str, task_id: str, stage: str, pipeline: str | None = None) -> dict[str, Any]:
    if candidate is None:
        return {
            "phase": phase, "task_id": task_id, "pipeline": pipeline, "stage": stage,
            "candidate_id": None, "deterministic_success": False, "catastrophic": False,
            "passed_requirements": [], "failed_requirements": ["parse_or_execution"],
            "hidden_gold_success": False, "semantic_clean": False, "semantic_issues": [],
        }
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    gold = evaluate_test2_gold(task, candidate)
    return {
        "phase": phase, "task_id": task_id, "pipeline": pipeline, "stage": stage,
        "candidate_id": candidate.id,
        "deterministic_success": bool(oracle.success), "catastrophic": bool(oracle.catastrophic),
        "passed_requirements": list(oracle.passed_requirement_ids), "failed_requirements": list(oracle.failed_requirement_ids),
        "hidden_gold_success": bool(gold.success), "semantic_clean": bool(gold.semantic_clean),
        "semantic_issues": list(gold.semantic_issues),
    }


def _phase_check(budget: PhysicalCallBudget, start: int, phase: str) -> int:
    used = budget.physical_calls - start
    limit = LOCAL_PHASE_LIMITS[phase]
    if used > limit:
        raise AssertionError(f"phase {phase} used {used} physical calls, exceeds limit {limit}")
    return used


def _formalize(*, caller: BoundedModelCaller, model: Any, task: TaskCase, run_id: str, trial_id: str, prompt_text: str, phase: str, raw_calls: list[dict[str, Any]], pipeline: str | None = None) -> tuple[dict[str, Any], BoundedCompletion]:
    messages = [
        {"role": "system", "content": "Convert the request into machine-checkable requirements. Return ONLY JSON {\"requirements\":[{\"id\":string,\"kind\":string,\"path\":string,\"expected\":any,\"metadata\":object}]}. Do not invent requirements."},
        {"role": "user", "content": prompt_text},
    ]
    result = caller.complete(model, messages, role="formalizer", context={"run_id": run_id, "trial_id": trial_id, "call_id": f"{trial_id}-{model.model}-formalize"}, response_schema={"type": "object"})
    raw_calls.append(_call_row(result, phase=phase, task_id=trial_id, model=model.model, role="formalizer", pipeline=pipeline))
    return _parse_json(result.text) or {"requirements": []}, result


def _execute(*, caller: BoundedModelCaller, model: Any, task: TaskCase, ir: dict[str, Any] | None, run_id: str, trial_id: str, phase: str, raw_calls: list[dict[str, Any]], candidates: list[dict[str, Any]], pipeline: str | None = None, direct: bool = False) -> tuple[Candidate | None, BoundedCompletion]:
    payload = build_executor_payload(task, ir=ir, direct=direct)
    messages = [
        {"role": "system", "content": "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. Satisfy every supplied machine-checkable requirement and add no unintended actions."},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]
    result = caller.complete(model, messages, role="executor", context={"run_id": run_id, "trial_id": trial_id, "call_id": f"{trial_id}-{model.model}-execute-{'direct' if direct else 'ir'}"}, response_schema={"type": "object"})
    raw_calls.append(_call_row(result, phase=phase, task_id=trial_id, model=model.model, role="executor", pipeline=pipeline))
    candidate = _candidate_from_actions(task, _parse_actions(result.text), f"{trial_id}-{model.model}-exec")
    if candidate is not None:
        candidates.append(_candidate_row(task=task, candidate=candidate, case_id=trial_id, source="model_executor", model=model.model, pipeline=pipeline, phase=phase))
    return candidate, result


def _audit(*, caller: BoundedModelCaller, model: Any, task: TaskCase, candidate: Candidate | None, run_id: str, trial_id: str, phase: str, raw_calls: list[dict[str, Any]], pipeline: str | None = None, atomic: bool = False, allow_cache: bool = True) -> tuple[bool | None, dict[str, Any], BoundedCompletion]:
    # Hidden gold, injected fault labels, and oracle outcome are intentionally
    # absent from this payload.
    payload = _public_task(task) | {
        "candidate_actions": [a.to_dict() for a in candidate.actions] if candidate else [],
        "candidate_final_state": candidate.state.to_dict() if candidate else None,
    }
    if atomic:
        system = "Evaluate EACH requirement independently, then check for unintended behavior. Return ONLY JSON {\"requirements\":[{\"id\":string,\"pass\":true|false,\"reason\":string}],\"accept\":true|false}. accept may be true only if every requirement passes and there is no unintended behavior."
        role = "atomic_auditor"
    else:
        system = "Audit the candidate exhaustively. Return ONLY JSON {\"accept\":true|false,\"failed_requirements\":[string],\"reason\":string}. Reject missing, wrong, prohibited, ordered-wrong, or unintended behavior."
        role = "auditor"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, sort_keys=True)}]
    result = caller.complete(model, messages, role=role, context={"run_id": run_id, "trial_id": trial_id, "candidate_id": candidate.id if candidate else None, "call_id": f"{trial_id}-{model.model}-{role}"}, response_schema={"type": "object"}, allow_cache=allow_cache)
    raw_calls.append(_call_row(result, phase=phase, task_id=trial_id, model=model.model, role=role, pipeline=pipeline))
    parsed = _parse_json(result.text) or {}
    accept = parsed.get("accept") if isinstance(parsed.get("accept"), bool) else None
    return accept, parsed, result


def _repair(*, caller: BoundedModelCaller, model: Any, task: TaskCase, candidate: Candidate | None, failed_ids: list[str], run_id: str, trial_id: str, phase: str, raw_calls: list[dict[str, Any]], candidates: list[dict[str, Any]], pipeline: str | None, feedback_style: str = "structured", strategy: str = "targeted", auditor_feedback: dict[str, Any] | None = None) -> tuple[Candidate | None, BoundedCompletion]:
    feedback: Any = {"failed_requirements": list(failed_ids)} if feedback_style == "raw" else structured_failure_feedback(task, candidate, failed_ids)
    if auditor_feedback:
        # This is model-produced evidence, not hidden benchmark gold.
        feedback["auditor_feedback"] = {
            "failed_requirements": list(auditor_feedback.get("failed_requirements") or []),
            "reason": auditor_feedback.get("reason"),
        }
    system = "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. " + ("Repair only failed parts and preserve every already-correct requirement." if strategy == "targeted" else "Regenerate the complete action plan from scratch.")
    payload = _public_task(task) | {"previous_actions": [a.to_dict() for a in candidate.actions] if candidate else [], "validator_feedback": feedback}
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, sort_keys=True)}]
    result = caller.complete(model, messages, role="repairer", context={"run_id": run_id, "trial_id": trial_id, "candidate_id": candidate.id if candidate else None, "call_id": f"{trial_id}-{model.model}-repair-{feedback_style}-{strategy}"}, response_schema={"type": "object"})
    raw_calls.append(_call_row(result, phase=phase, task_id=trial_id, model=model.model, role="repairer", pipeline=pipeline))
    repaired = _candidate_from_actions(task, _parse_actions(result.text), f"{trial_id}-{model.model}-repair")
    if repaired is not None:
        candidates.append(_candidate_row(task=task, candidate=repaired, case_id=trial_id, source="model_repair", model=model.model, pipeline=pipeline, phase=phase))
    return repaired, result


def _snapshot(task: TaskCase, candidate: Candidate | None, *, blocked: bool = False, auditor_accept: bool | None = None) -> OutcomeSnapshot:
    if candidate is None:
        return OutcomeSnapshot(False, blocked=blocked, failure_signature="parse_or_execution")
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    gold = evaluate_test2_gold(task, candidate)
    runtime_allowed = bool(oracle.success and (auditor_accept is True if auditor_accept is not None else True) and not blocked)
    success = bool(runtime_allowed and gold.success)
    failure = None
    if not success:
        if not oracle.success:
            failure = ",".join(oracle.failed_requirement_ids) or "deterministic_failure"
        elif not gold.semantic_clean and runtime_allowed:
            failure = "semantic_escape"
        elif blocked:
            failure = "blocked"
        else:
            failure = "semantic_residual"
    return OutcomeSnapshot(success=success, catastrophic=bool(oracle.catastrophic and runtime_allowed), blocked=blocked, failure_signature=failure)


def _rank_simple(rows: list[dict[str, Any]], role: str, count: int = 1) -> list[str]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("role") == role:
            groups[str(row["model"])].append(row)
    return sorted(groups, key=lambda model: (-(sum(bool(r.get("success")) for r in groups[model]) / len(groups[model])), -sum(float(r.get("preservation_rate", 0.0) or 0.0) for r in groups[model]), model))[:count]


def _repair_condition_choice(rows: list[dict[str, Any]]) -> tuple[str, str]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["feedback_style"]), str(row["strategy"]))].append(row)
    ranked = sorted(grouped, key=lambda key: (-(sum(bool(r.get("success")) for r in grouped[key]) / len(grouped[key])), -(sum(float(r.get("preservation_rate", 0.0)) for r in grouped[key]) / len(grouped[key])), sum(float(r.get("new_failures_introduced", 0.0)) for r in grouped[key]) / len(grouped[key]), key))
    return ranked[0] if ranked else ("structured", "targeted")


def _repair_champion(rows: list[dict[str, Any]], condition: tuple[str, str]) -> str:
    feedback, strategy = condition
    subset = [r for r in rows if r.get("feedback_style") == feedback and r.get("strategy") == strategy]
    return (_rank_simple(subset, "repairer", 1) or [LOCAL_MODELS[0]])[0]


def _run_full_pipeline(*, case: Any, roles: dict[str, str], model_by_name: dict[str, Any], caller: BoundedModelCaller, run_id: str, phase: str, raw_calls: list[dict[str, Any]], candidates: list[dict[str, Any]], events: list[dict[str, Any]], validator_results: list[dict[str, Any]], pipeline: str, audit_before_repair: bool, repair_feedback_style: str, repair_strategy: str) -> dict[str, Any]:
    start_physical = caller.budget.physical_calls
    start_logical = len(caller.calls)
    task = case.task
    trial_root = f"{case.case_id}-{pipeline}"

    fmodel = model_by_name[roles["formalizer"]]
    ir, fresult = _formalize(caller=caller, model=fmodel, task=task, run_id=run_id, trial_id=trial_root, prompt_text=task.goal, phase=phase, raw_calls=raw_calls, pipeline=pipeline)
    fscore = _formalization_score(task, fresult.text)
    _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="formalizer", model=fmodel.model, **fscore)

    emodel = model_by_name[roles["executor"]]
    candidate, _ = _execute(caller=caller, model=emodel, task=task, ir=ir, run_id=run_id, trial_id=trial_root, phase=phase, raw_calls=raw_calls, candidates=candidates, pipeline=pipeline, direct=False)
    initial_validation = _validator_row(task, candidate, phase=phase, task_id=case.case_id, stage="post_executor_validation", pipeline=pipeline)
    validator_results.append(initial_validation)
    failed_ids = list(initial_validation["failed_requirements"])
    _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="executor", model=emodel.model, deterministic_success=initial_validation["deterministic_success"], hidden_gold_success=initial_validation["hidden_gold_success"], semantic_clean=initial_validation["semantic_clean"])

    auditor_accept: bool | None = None
    auditor_feedback: dict[str, Any] | None = None
    repair_used = False

    if audit_before_repair:
        amodel = model_by_name[roles["auditor"]]
        auditor_accept, auditor_feedback, _ = _audit(caller=caller, model=amodel, task=task, candidate=candidate, run_id=run_id, trial_id=f"{trial_root}-pre-repair", phase=phase, raw_calls=raw_calls, pipeline=pipeline)
        _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="auditor_pre_repair", model=amodel.model, accept=auditor_accept, hidden_gold_success=initial_validation["hidden_gold_success"])
        needs_repair = bool(auditor_accept is False or not initial_validation["deterministic_success"])
    else:
        needs_repair = not bool(initial_validation["deterministic_success"])

    if needs_repair:
        rmodel = model_by_name[roles["repairer"]]
        repaired_candidate, _ = _repair(caller=caller, model=rmodel, task=task, candidate=candidate, failed_ids=failed_ids, run_id=run_id, trial_id=trial_root, phase=phase, raw_calls=raw_calls, candidates=candidates, pipeline=pipeline, feedback_style=repair_feedback_style, strategy=repair_strategy, auditor_feedback=auditor_feedback if audit_before_repair else None)
        if repaired_candidate is not None:
            candidate = repaired_candidate
        repair_used = True
        _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="repair", model=rmodel.model, feedback_style=repair_feedback_style, strategy=repair_strategy)

    revalidation = _validator_row(task, candidate, phase=phase, task_id=case.case_id, stage="post_mutation_revalidation", pipeline=pipeline)
    validator_results.append(revalidation)
    _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="deterministic_revalidation", deterministic_success=revalidation["deterministic_success"], hidden_gold_success=revalidation["hidden_gold_success"], semantic_clean=revalidation["semantic_clean"])

    # Audit only deterministic survivors. This is the production-relevant
    # selective route and avoids spending semantic calls on already-invalid work.
    if revalidation["deterministic_success"]:
        amodel = model_by_name[roles["auditor"]]
        auditor_accept, auditor_feedback, _ = _audit(caller=caller, model=amodel, task=task, candidate=candidate, run_id=run_id, trial_id=f"{trial_root}-post-repair", phase=phase, raw_calls=raw_calls, pipeline=pipeline)
        _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="auditor_final", model=amodel.model, accept=auditor_accept, hidden_gold_success=revalidation["hidden_gold_success"])
    else:
        auditor_accept = None
        _event(events, phase=phase, task_id=case.case_id, pipeline=pipeline, stage="auditor_skipped", reason="deterministic_revalidation_failed")

    final_validation = _validator_row(task, candidate, phase=phase, task_id=case.case_id, stage="final_deterministic_authority", pipeline=pipeline)
    validator_results.append(final_validation)
    runtime_allowed = bool(final_validation["deterministic_success"] and auditor_accept is True)
    hidden_success = bool(final_validation["hidden_gold_success"])
    final_success = bool(runtime_allowed and hidden_success)
    blocked = not runtime_allowed
    failure_class = None
    if not final_success:
        if not final_validation["deterministic_success"]:
            failure_class = ",".join(final_validation["failed_requirements"]) or "deterministic_failure"
        elif runtime_allowed and not hidden_success:
            failure_class = "semantic_escape"
        elif auditor_accept is False:
            failure_class = "auditor_block"
        else:
            failure_class = "auditor_parse_or_skip_block"

    return {
        "phase": phase,
        "role": "pipeline",
        "pipeline": pipeline,
        "task_id": case.case_id,
        "evaluation_id": _evaluation_id(phase, "pipeline", case.case_id, pipeline=pipeline),
        "family": task.family,
        "complexity": task.complexity,
        "model": "layered" if len(set(roles.values())) > 1 else next(iter(roles.values())),
        "roles": dict(roles),
        "success": final_success,
        "runtime_allowed": runtime_allowed,
        "hidden_gold_success": hidden_success,
        "semantic_clean": bool(final_validation["semantic_clean"]),
        "catastrophic": bool(final_validation["catastrophic"] and runtime_allowed),
        "blocked": blocked,
        "failure_class": failure_class,
        "initial_deterministic_success": bool(initial_validation["deterministic_success"]),
        "initial_hidden_gold_success": bool(initial_validation["hidden_gold_success"]),
        "repair_used": repair_used,
        "auditor_accept": auditor_accept,
        "repair_feedback_style": repair_feedback_style,
        "repair_strategy": repair_strategy,
        "logical_calls": len(caller.calls) - start_logical,
        "physical_calls_added": caller.budget.physical_calls - start_physical,
    }


def _efficiency_rows(raw_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in raw_calls:
        groups[(str(row.get("role")), str(row.get("model")))].append(row)
    out = []
    for (role, model), group in sorted(groups.items()):
        physical = [row for row in group if not row.get("cache_hit")]
        telemetry = [dict(row.get("telemetry") or {}) for row in physical]
        def total(field: str) -> float:
            return sum(float(t.get(field) or 0.0) for t in telemetry)
        out.append({
            "role": role, "model": model,
            "logical_calls": len(group), "physical_calls": len(physical), "cache_hits": len(group) - len(physical),
            "input_tokens": int(total("input_tokens")), "output_tokens": int(total("output_tokens")), "total_tokens": int(total("total_tokens")),
            "latency_s": total("latency_s"), "eval_duration_s": total("eval_duration_s"), "prompt_eval_duration_s": total("prompt_eval_duration_s"), "load_duration_s": total("load_duration_s"),
        })
    return out


def _ensemble_rows(audit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        grouped[str(row["task_id"])].append(row)
    policies = ("majority_3_of_5", "unanimous_accept", "any_reject")
    out = []
    for policy in policies:
        tp = tn = fp = fn = abstain = 0
        for task_id, group in grouped.items():
            truth = bool(group[0].get("gold_accept"))
            decisions = [row.get("accept") for row in group if isinstance(row.get("accept"), bool)]
            accepts = sum(value is True for value in decisions)
            rejects = sum(value is False for value in decisions)
            if policy == "majority_3_of_5":
                decision = True if accepts >= 3 else False if rejects >= 3 else None
            elif policy == "unanimous_accept":
                decision = True if len(decisions) == 5 and accepts == 5 else False
            else:
                decision = False if rejects >= 1 else True if len(decisions) == 5 else None
            if decision is None:
                abstain += 1
            elif decision and truth:
                tp += 1
            elif not decision and not truth:
                tn += 1
            elif decision and not truth:
                fp += 1
            else:
                fn += 1
        valid = tp + fn; invalid = tn + fp
        out.append({
            "policy": policy, "tp": tp, "tn": tn, "fp": fp, "fn": fn, "abstain": abstain,
            "specificity": tn / invalid if invalid else 0.0,
            "valid_accept_recall": tp / valid if valid else 0.0,
            "false_accept_rate": fp / invalid if invalid else 0.0,
            "accuracy": (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0,
        })
    return out


def _disagreement_risk(audit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        grouped[str(row["task_id"])].append(row)
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for task_id, group in grouped.items():
        decisions = [row.get("accept") for row in group if isinstance(row.get("accept"), bool)]
        accepts = sum(v is True for v in decisions); rejects = sum(v is False for v in decisions)
        minority = min(accepts, rejects) if decisions else 0
        buckets[minority].append({"truth": bool(group[0].get("gold_accept")), "accepts": accepts, "rejects": rejects})
    out = []
    for minority, group in sorted(buckets.items()):
        invalid = [row for row in group if not row["truth"]]
        any_false_accept = sum(1 for row in invalid if row["accepts"] > 0)
        out.append({
            "minority_vote_count": minority, "n": len(group), "invalid_n": len(invalid),
            "invalid_with_any_false_accept": any_false_accept,
            "false_accept_risk_given_invalid": any_false_accept / len(invalid) if invalid else 0.0,
        })
    return out


def run_local_campaign(models: list[Any], run_id: str = "test2-local", hard_limit: int = 480) -> dict[str, Any]:
    if tuple(str(getattr(model, "model", "")) for model in models) != LOCAL_MODELS:
        raise ValueError(f"local Test-2 models must be exactly {LOCAL_MODELS!r}")
    if hard_limit > 480:
        raise ValueError("hard_limit may not exceed the preregistered 480-call ceiling")
    for model in models:
        if int(getattr(model, "max_retries", 0) or 0) != 0:
            raise ValueError("Test-2 local models must disable adapter-internal retries so physical-call accounting is exact")

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

    # Phase 1 — formalization: 12 matched cases x all five models.
    start = budget.physical_calls
    formalization_cases = build_formalization_cases()
    for model in models:
        for case in formalization_cases:
            _, result = _formalize(caller=caller, model=model, task=case.task, run_id=run_id, trial_id=case.case_id, prompt_text=case.prompt_text, phase="formalization", raw_calls=raw_calls)
            score = _formalization_score(case.task, result.text)
            row = {"phase": "formalization", "role": "formalizer", "task_id": case.case_id, "evaluation_id": _evaluation_id("formalization", "formalizer", case.case_id), "family": case.task.family, "complexity": case.task.complexity, "representation": case.representation, "requirement_count": len(case.task.requirements), "model": model.model, **score}
            rows.append(row); _event(events, **row)
    phase_usage["formalization"] = _phase_check(budget, start, "formalization")

    # Phase 2 — one-shot execution: 3 families x 4 complexities x all models.
    start = budget.physical_calls
    for model in models:
        for case in build_execution_cases():
            candidate, _ = _execute(caller=caller, model=model, task=case.task, ir=None, run_id=run_id, trial_id=case.case_id, phase="execution", raw_calls=raw_calls, candidates=candidates, direct=True)
            oracle = evaluate_task(case.task, candidate.state, candidate.actions) if candidate else None
            gold = evaluate_test2_gold(case.task, candidate) if candidate else None
            row = {
                "phase": "execution", "role": "executor", "task_id": case.case_id,
                "evaluation_id": _evaluation_id("execution", "executor", case.case_id),
                "family": case.task.family, "complexity": case.task.complexity, "requirement_count": len(case.task.requirements), "model": model.model,
                "success": bool(gold and gold.success), "deterministic_success": bool(oracle and oracle.success), "semantic_clean": bool(gold and gold.semantic_clean),
                "requirement_accuracy": len(oracle.passed_requirement_ids) / len(case.task.requirements) if oracle is not None and case.task.requirements else 0.0,
                "failure_class": "parser_or_execution" if oracle is None else ("semantic_residual" if oracle.success and gold and not gold.semantic_clean else (",".join(oracle.failed_requirement_ids) if not oracle.success else None)),
            }
            rows.append(row); validator_results.append(_validator_row(case.task, candidate, phase="execution", task_id=case.case_id, stage="one_shot_scoring")); _event(events, **row)
    phase_usage["execution"] = _phase_check(budget, start, "execution")

    # Phase 3 — fixed 20-candidate audit bank x all models.
    start = budget.physical_calls
    audit_bank = build_audit_candidate_bank()
    for case in audit_bank:
        candidates.append(_candidate_row(task=case.task, candidate=case.candidate, case_id=case.case_id, source="fixed_audit_bank", phase="auditing"))
    audit_rows: list[dict[str, Any]] = []
    for model in models:
        for case in audit_bank:
            accept, parsed, _ = _audit(caller=caller, model=model, task=case.task, candidate=case.candidate, run_id=run_id, trial_id=case.case_id, phase="auditing", raw_calls=raw_calls)
            oracle = evaluate_task(case.task, case.candidate.state, case.candidate.actions)
            gold = evaluate_test2_gold(case.task, case.candidate)
            truth = bool(gold.success)
            correct = isinstance(accept, bool) and accept == truth
            fault = case.candidate.injected_faults[0].split("+")[0] if case.candidate.injected_faults else "none"
            failed_positions = [i + 1 for i, req in enumerate(case.task.requirements) if req.id in gold.failed_requirement_ids]
            reported = list(parsed.get("failed_requirements") or [])
            failed_set = set(gold.failed_requirement_ids); reported_set = set(map(str, reported))
            report_tp = len(failed_set & reported_set)
            row = {
                "phase": "auditing", "role": "auditor", "task_id": case.case_id,
                "evaluation_id": _evaluation_id("auditing", "auditor", case.case_id),
                "family": case.task.family, "complexity": case.task.complexity, "requirement_count": len(case.task.requirements), "fault": fault,
                "model": model.model, "success": bool(correct), "oracle_success": bool(oracle.success), "gold_accept": truth, "semantic_clean": gold.semantic_clean,
                "accept": accept, "tp": int(truth and accept is True), "tn": int((not truth) and accept is False), "fp": int((not truth) and accept is True), "fn": int(truth and accept is False),
                "reported_failed_requirements": reported, "gold_failed_requirements": list(gold.failed_requirement_ids), "semantic_issues": list(gold.semantic_issues),
                "failed_requirement_positions": failed_positions, "first_failed_position": min(failed_positions) if failed_positions else None, "last_failed_position": max(failed_positions) if failed_positions else None,
                "failed_id_report_precision": report_tp / len(reported_set) if reported_set else (1.0 if not failed_set else 0.0),
                "failed_id_report_recall": report_tp / len(failed_set) if failed_set else None,
            }
            rows.append(row); audit_rows.append(row); _event(events, phase="auditing", task_id=case.case_id, model=model.model, accept=accept, gold_accept=truth, correct=bool(correct), fault=fault)
    phase_usage["auditing"] = _phase_check(budget, start, "auditing")

    audit_ranking = rank_auditors(audit_rows)
    top_auditors = [row["model"] for row in audit_ranking[:2]]

    # Phase 4 — decision-sensitive atomic audit, balanced valid/invalid.
    start = budget.physical_calls
    atomic_selection = select_stability_task_ids(audit_rows, max_cases=10)
    selection_by_id = {row["task_id"]: row for row in atomic_selection}
    case_by_id = {case.case_id: case for case in audit_bank}
    atomic_cases = [case_by_id[row["task_id"]] for row in atomic_selection]
    atomic_rows: list[dict[str, Any]] = []
    for model_name in top_auditors:
        model = model_by_name[model_name]
        for case in atomic_cases:
            accept, parsed, _ = _audit(caller=caller, model=model, task=case.task, candidate=case.candidate, run_id=run_id, trial_id=case.case_id, phase="atomic_audit", raw_calls=raw_calls, atomic=True)
            gold = evaluate_test2_gold(case.task, case.candidate); truth = bool(gold.success)
            row = {
                "phase": "atomic_audit", "role": "atomic_auditor", "task_id": case.case_id,
                "evaluation_id": _evaluation_id("atomic_audit", "atomic_auditor", case.case_id),
                "family": case.task.family, "complexity": case.task.complexity, "requirement_count": len(case.task.requirements), "fault": case.candidate.injected_faults[0].split("+")[0] if case.candidate.injected_faults else "none",
                "model": model_name, "success": bool(isinstance(accept, bool) and accept == truth), "gold_accept": truth, "accept": accept,
                "requirement_judgments": parsed.get("requirements") or [], "selection_reason": selection_by_id[case.case_id],
            }
            rows.append(row); atomic_rows.append(row); _event(events, phase="atomic_audit", task_id=case.case_id, model=model_name, accept=accept, gold_accept=truth)
    phase_usage["atomic_audit"] = _phase_check(budget, start, "atomic_audit")

    # Phase 5 — all-model repair screen (25) + top-3 2x2 factorial (72) = 97.
    start = budget.physical_calls
    repair_candidates = build_repair_candidate_bank()
    for case in repair_candidates:
        candidates.append(_candidate_row(task=case.task, candidate=case.candidate, case_id=case.case_id, source="fixed_repair_bank", phase="repair_factorial"))
    repair_screen_rows: list[dict[str, Any]] = []
    for model in models:
        for case in repair_candidates[:5]:
            original = evaluate_task(case.task, case.candidate.state, case.candidate.actions)
            repaired_candidate, _ = _repair(caller=caller, model=model, task=case.task, candidate=case.candidate, failed_ids=list(original.failed_requirement_ids), run_id=run_id, trial_id=f"{case.case_id}-screen", phase="repair_factorial", raw_calls=raw_calls, candidates=candidates, pipeline=None, feedback_style="structured", strategy="targeted")
            gold = evaluate_test2_gold(case.task, repaired_candidate) if repaired_candidate else None
            repaired_oracle = evaluate_task(case.task, repaired_candidate.state, repaired_candidate.actions) if repaired_candidate else None
            original_passed = set(original.passed_requirement_ids); new_passed = set(repaired_oracle.passed_requirement_ids) if repaired_oracle else set()
            row = {
                "phase": "repair_screen", "role": "repairer", "task_id": case.case_id,
                "evaluation_id": _evaluation_id("repair_screen", "repairer", case.case_id, feedback_style="structured", strategy="targeted"),
                "family": case.task.family, "complexity": case.task.complexity, "fault": case.candidate.injected_faults[0].split("+")[0], "model": model.model,
                "feedback_style": "structured", "strategy": "targeted", "success": bool(gold and gold.success),
                "preserved_passed": len(original_passed & new_passed), "original_passed": len(original_passed), "new_failures_introduced": len(original_passed - new_passed),
                "failed_requirements_repaired": len(set(original.failed_requirement_ids) & new_passed), "preservation_rate": len(original_passed & new_passed) / len(original_passed) if original_passed else 1.0,
            }
            rows.append(row); repair_screen_rows.append(row); _event(events, **row)
    top_repair_models = _rank_simple(repair_screen_rows, "repairer", 3)

    factorial_rows: list[dict[str, Any]] = []
    primary_conditions = (
        ("raw", "regenerate"),
        ("raw", "targeted"),
        ("structured", "regenerate"),
        ("structured", "targeted"),
    )
    primary_group_index = 0
    for model_name in top_repair_models:
        model = model_by_name[model_name]
        for case in repair_candidates[:6]:
            original = evaluate_task(case.task, case.candidate.state, case.candidate.actions); original_passed = set(original.passed_requirement_ids)
            rotation = primary_group_index % len(primary_conditions)
            condition_order = (
                primary_conditions[rotation:]
                + primary_conditions[:rotation]
            )
            primary_group_index += 1
            for feedback_style, strategy in condition_order:
                repaired_candidate, _ = _repair(caller=caller, model=model, task=case.task, candidate=case.candidate, failed_ids=list(original.failed_requirement_ids), run_id=run_id, trial_id=f"{case.case_id}-{feedback_style}-{strategy}", phase="repair_factorial", raw_calls=raw_calls, candidates=candidates, pipeline=None, feedback_style=feedback_style, strategy=strategy)
                repaired_oracle = evaluate_task(case.task, repaired_candidate.state, repaired_candidate.actions) if repaired_candidate else None
                gold = evaluate_test2_gold(case.task, repaired_candidate) if repaired_candidate else None
                new_passed = set(repaired_oracle.passed_requirement_ids) if repaired_oracle else set()
                row = {
                    "phase": "repair_factorial", "role": "repairer", "task_id": case.case_id,
                    "evaluation_id": _evaluation_id("repair_factorial", "repairer", case.case_id, feedback_style=feedback_style, strategy=strategy),
                    "family": case.task.family, "complexity": case.task.complexity, "fault": case.candidate.injected_faults[0].split("+")[0], "model": model_name,
                    "feedback_style": feedback_style, "strategy": strategy, "success": bool(gold and gold.success),
                    "deterministic_success": bool(repaired_oracle and repaired_oracle.success), "semantic_clean": bool(gold and gold.semantic_clean),
                    "original_passed": len(original_passed), "preserved_passed": len(original_passed & new_passed), "new_failures_introduced": len(original_passed - new_passed),
                    "failed_requirements_repaired": len(set(original.failed_requirement_ids) & new_passed), "preservation_rate": len(original_passed & new_passed) / len(original_passed) if original_passed else 1.0,
                }
                rows.append(row); repairs.append(row); factorial_rows.append(row); validator_results.append(_validator_row(case.task, repaired_candidate, phase="repair_factorial", task_id=case.case_id, stage=f"repair_{feedback_style}_{strategy}")); _event(events, **row)
    phase_usage["repair_factorial"] = _phase_check(budget, start, "repair_factorial")

    repair_effects = repair_factorial_effects(factorial_rows)
    best_repair_condition = _repair_condition_choice(factorial_rows)
    repair_champion = _repair_champion(factorial_rows, best_repair_condition)
    formalizer_champion = (_rank_simple(rows, "formalizer", 1) or [LOCAL_MODELS[0]])[0]
    executor_champion = (_rank_simple(rows, "executor", 1) or [LOCAL_MODELS[0]])[0]
    auditor_champion = top_auditors[0] if top_auditors else LOCAL_MODELS[0]

    # Equal role weighting prevents the 100-row audit phase from dominating the
    # best-single choice. Repair uses the matched all-model screen only.
    best_single_source = [row for row in rows if row.get("phase") in {"formalization", "execution", "auditing", "repair_screen"} and row.get("role") in {"formalizer", "executor", "auditor", "repairer"}]
    balanced_scores = balanced_role_model_scores(best_single_source)
    best_single = balanced_scores[0]["model"] if balanced_scores else LOCAL_MODELS[0]

    progressive_assignments = build_progressive_role_assignments(best_single=best_single, formalizer=formalizer_champion, executor=executor_champion, repairer=repair_champion, auditor=auditor_champion)

    # Phase 6 — four untouched hard holdouts; <=100 physical calls.
    start = budget.physical_calls
    holdout_all = build_holdout_cases()
    hard_holdouts = [
        next(case for case in holdout_all if case.task.family == "state" and case.task.complexity == 4),
        next(case for case in holdout_all if case.task.family == "policy" and case.task.complexity == 4),
        next(case for case in holdout_all if case.task.family == "reconciliation" and case.task.complexity == 4),
        next(case for case in holdout_all if case.task.family == "policy" and case.task.complexity == 3),
    ]
    holdout_rows: list[dict[str, Any]] = []
    progressive_transitions: list[dict[str, Any]] = []
    for case in hard_holdouts:
        per_task: list[dict[str, Any]] = []
        for assignment in progressive_assignments:
            row = _run_full_pipeline(case=case, roles=assignment["roles"], model_by_name=model_by_name, caller=caller, run_id=run_id, phase="progressive_holdout", raw_calls=raw_calls, candidates=candidates, events=events, validator_results=validator_results, pipeline=assignment["pipeline"], audit_before_repair=False, repair_feedback_style=best_repair_condition[0], repair_strategy=best_repair_condition[1])
            row["specialized_roles"] = assignment["specialized_roles"]
            rows.append(row); holdout_rows.append(row); per_task.append(row)
        full_roles = progressive_assignments[-1]["roles"]
        alt = _run_full_pipeline(case=case, roles=full_roles, model_by_name=model_by_name, caller=caller, run_id=run_id, phase="progressive_holdout", raw_calls=raw_calls, candidates=candidates, events=events, validator_results=validator_results, pipeline=PROGRESSIVE_PIPELINES[5], audit_before_repair=True, repair_feedback_style=best_repair_condition[0], repair_strategy=best_repair_condition[1])
        alt["specialized_roles"] = 4; rows.append(alt); holdout_rows.append(alt)

        control_model = model_by_name[best_single]
        physical_before = budget.physical_calls; logical_before = len(caller.calls)
        control_candidate, _ = _execute(caller=caller, model=control_model, task=case.task, ir=None, run_id=run_id, trial_id=f"{case.case_id}-one-shot", phase="progressive_holdout", raw_calls=raw_calls, candidates=candidates, pipeline=PROGRESSIVE_PIPELINES[6], direct=True)
        gold = evaluate_test2_gold(case.task, control_candidate) if control_candidate else None
        control = {
            "phase": "progressive_holdout", "role": "pipeline", "pipeline": PROGRESSIVE_PIPELINES[6], "task_id": case.case_id,
            "evaluation_id": _evaluation_id("progressive_holdout", "pipeline", case.case_id, pipeline=PROGRESSIVE_PIPELINES[6]),
            "family": case.task.family, "complexity": case.task.complexity, "model": best_single, "roles": {"executor": best_single},
            "success": bool(gold and gold.success), "runtime_allowed": True, "hidden_gold_success": bool(gold and gold.success), "semantic_clean": bool(gold and gold.semantic_clean),
            "catastrophic": bool(gold and gold.catastrophic), "blocked": False, "failure_class": None if gold and gold.success else "one_shot_failure", "specialized_roles": 0,
            "logical_calls": len(caller.calls) - logical_before, "physical_calls_added": budget.physical_calls - physical_before,
        }
        rows.append(control); holdout_rows.append(control); validator_results.append(_validator_row(case.task, control_candidate, phase="progressive_holdout", task_id=case.case_id, stage="one_shot_control_scoring", pipeline=PROGRESSIVE_PIPELINES[6])); _event(events, **control)
        for previous, current in zip(per_task, per_task[1:]):
            before = OutcomeSnapshot(bool(previous["success"]), bool(previous["catastrophic"]), bool(previous["blocked"]), previous.get("failure_class")); after = OutcomeSnapshot(bool(current["success"]), bool(current["catastrophic"]), bool(current["blocked"]), current.get("failure_class"))
            progressive_transitions.append({"task_id": case.case_id, "from_pipeline": previous["pipeline"], "to_pipeline": current["pipeline"], "transition": classify_transition(before, after), "from_success": before.success, "to_success": after.success})
    phase_usage["progressive_holdout"] = _phase_check(budget, start, "progressive_holdout")

    # Phase 7 — 8 decision-sensitive balanced audit cells x all five models.
    start = budget.physical_calls
    stability_selection = select_stability_task_ids(audit_rows, max_cases=8)
    stability_case_ids = [row["task_id"] for row in stability_selection]
    initial_audit = {(str(row["model"]), str(row["task_id"])): row for row in audit_rows}
    stability_labels: list[dict[str, Any]] = []
    for model in models:
        for case_id in stability_case_ids:
            case = case_by_id[case_id]
            accept, _, _ = _audit(caller=caller, model=model, task=case.task, candidate=case.candidate, run_id=run_id, trial_id=f"{case.case_id}-stability", phase="stability", raw_calls=raw_calls, allow_cache=False)
            gold = evaluate_test2_gold(case.task, case.candidate); truth = bool(gold.success)
            initial = initial_audit.get((model.model, case.case_id)); stable = initial is not None and initial.get("accept") == accept
            label = "STABLE" if stable else "UNSTABLE" if initial is not None else "PROVISIONAL"
            row = {"phase": "stability", "role": "auditor", "task_id": case.case_id, "evaluation_id": _evaluation_id("stability", "auditor", case.case_id), "family": case.task.family, "complexity": case.task.complexity, "model": model.model, "success": bool(isinstance(accept, bool) and accept == truth), "gold_accept": truth, "accept": accept, "stability": label}
            rows.append(row); stability_labels.append(row); _event(events, **row)
    phase_usage["stability"] = _phase_check(budget, start, "stability")

    if budget.physical_calls > hard_limit:
        raise AssertionError("physical call ceiling violated")

    # Derived routing uses only matched all-model discovery rows. Evaluation IDs
    # preserve repair conditions and prevent same-task overwrites.
    baseline_role_rows = [row for row in rows if row.get("phase") in {"formalization", "execution", "auditing", "repair_screen"} and row.get("role") in {"formalizer", "executor", "auditor", "repairer"}]
    router_input = [{**row, "task_id": row["evaluation_id"]} for row in baseline_role_rows]
    layered = derive_layered_router(router_input)
    outcome_map: dict[str, dict[str, bool]] = defaultdict(dict)
    for row in baseline_role_rows:
        outcome_map[str(row["evaluation_id"])][str(row["model"])] = bool(row.get("success"))
    pair_rows = []
    for index, model_a in enumerate(LOCAL_MODELS):
        for model_b in LOCAL_MODELS[index + 1:]:
            pair_rows.append(model_complementarity(outcome_map, model_a, model_b))

    capabilities = build_layered_capability_outputs(baseline_role_rows)
    role_champions = {"formalizer": formalizer_champion, "executor": executor_champion, "repairer": repair_champion, "auditor": auditor_champion}

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
        "progressive_compounding_effects": progressive_compounding_effects(holdout_rows),
        "stability_labels": stability_labels,
        "stability_selection": stability_selection,
        "atomic_selection": atomic_selection,
        "role_champions": role_champions,
        "best_single_balanced_scores": balanced_scores,
        "audit_confusion": audit_confusion_by_model(audit_rows),
        "audit_ranking": audit_ranking,
        "auditor_ensemble_results": _ensemble_rows(audit_rows),
        "auditor_disagreement_risk": _disagreement_risk(audit_rows),
        "repair_screen": repair_screen_rows,
        "repair_factorial_effects": repair_effects,
        "best_repair_condition": {"feedback_style": best_repair_condition[0], "strategy": best_repair_condition[1]},
        "layered_router": layered,
        "model_pair_synergy": pair_rows,
        "holdout_pipeline_rows": holdout_rows,
        "model_efficiency": _efficiency_rows(raw_calls),
        "capability_by_role_model": capabilities["role"],
        "capability_by_family_model": capabilities["family"],
        "capability_by_fault_model": capabilities["fault"],
        "capability_by_complexity_model": capabilities["complexity"],
        "capability_by_representation_model": capabilities["representation"],
    }
