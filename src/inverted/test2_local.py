from __future__ import annotations

from dataclasses import dataclass
import json
from collections import defaultdict
from typing import Any

from .domain import Action, Candidate, Requirement, TaskCase
from .models import CompletionResult
from .oracle import apply_actions, evaluate_task
from .test2_analysis import capability_matrix, derive_layered_router, model_complementarity
from .test2_cases import (
    CandidateProbe,
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
            result = BoundedCompletion(
                text=cached.text,
                record=cached.record,
                identity=identity,
                cache_hit=True,
                prompt=messages,
                response=cached.response,
            )
            self.calls.append(result)
            return result

        self.budget.consume(identity)
        result: CompletionResult = model.complete(messages, role=role, context=context)
        completion = BoundedCompletion(
            text=result.text,
            record=result.record,
            identity=identity,
            cache_hit=False,
            prompt=messages,
            response=result.text,
        )
        if allow_cache:
            self._cache[identity] = completion
        self.calls.append(completion)
        return completion


def build_local_plan() -> LocalTest2Plan:
    total = sum(LOCAL_PHASE_LIMITS.values())
    if total != 480:
        raise AssertionError(f"local Test-2 phase limits must sum to 480, got {total}")
    return LocalTest2Plan(planned_max_physical_calls=total)


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


def _candidate_from_actions(task: TaskCase, actions: tuple[Action, ...], candidate_id: str) -> Candidate | None:
    try:
        state = apply_actions(task.initial_state, actions)
    except Exception:
        return None
    return Candidate(candidate_id, state, actions, configured_quality=1.0)


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
    precision = tp / len(predicted_keys) if predicted_keys else 0.0
    recall = tp / len(truth_keys) if truth_keys else 1.0
    hallucinated = len(predicted_keys - truth_keys)
    critical_truth = {
        _requirement_key({"kind": req.kind, "path": req.path, "expected": req.expected})
        for req in task.requirements if req.critical
    }
    critical_recall = (
        len(predicted_keys & critical_truth) / len(critical_truth)
        if critical_truth else 1.0
    )
    return {
        "precision": precision,
        "recall": recall,
        "critical_recall": critical_recall,
        "hallucinated_requirements": hallucinated,
        "exact_ir": predicted_keys == truth_keys,
        "success": predicted_keys == truth_keys,
    }


def _rank_models(rows: list[dict[str, Any]], role: str, count: int = 2) -> list[str]:
    groups: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        if row.get("role") == role:
            groups[str(row["model"])].append(bool(row.get("success")))
    ranked = sorted(
        groups,
        key=lambda model: (
            -(sum(groups[model]) / len(groups[model]) if groups[model] else 0.0),
            model,
        ),
    )
    return ranked[:count]


def _call_row(completion: BoundedCompletion, *, phase: str, task_id: str, model: str, role: str) -> dict[str, Any]:
    record = completion.record.to_dict() if hasattr(completion.record, "to_dict") else {}
    return {
        "phase": phase,
        "task_id": task_id,
        "model": model,
        "role": role,
        "call_identity": completion.identity,
        "cache_hit": completion.cache_hit,
        "prompt": completion.prompt,
        "response": completion.response,
        "telemetry": record,
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
    validator_rows: list[dict[str, Any]] = []

    model_by_name = {str(model.model): model for model in models}

    # Phase 1: 12 x 5 = 60 formalization calls.
    for model in models:
        for case in build_formalization_cases():
            messages = [
                {"role": "system", "content": "Convert the request into machine-checkable requirements. Return ONLY JSON {\"requirements\":[{\"id\":string,\"kind\":string,\"path\":string,\"expected\":any,\"metadata\":object}]}. Do not invent requirements."},
                {"role": "user", "content": case.prompt_text},
            ]
            context = {"run_id": run_id, "trial_id": case.case_id, "call_id": f"{case.case_id}-{model.model}-formalize"}
            result = caller.complete(model, messages, role="formalizer", context=context, response_schema={"type": "object"})
            score = _formalization_score(case.task, result.text)
            rows.append({
                "phase": "formalization", "role": "formalizer", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "representation": case.representation, "model": model.model, **score,
            })
            raw_calls.append(_call_row(result, phase="formalization", task_id=case.case_id, model=model.model, role="formalizer"))

    # Phase 2: 12 x 5 = 60 one-shot executor calls.
    for model in models:
        for case in build_execution_cases():
            messages = [
                {"role": "system", "content": "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. Satisfy every listed requirement and add no unintended actions."},
                {"role": "user", "content": json.dumps(_public_task(case.task), sort_keys=True)},
            ]
            context = {"run_id": run_id, "trial_id": case.case_id, "call_id": f"{case.case_id}-{model.model}-execute"}
            result = caller.complete(model, messages, role="executor", context=context, response_schema={"type": "object"})
            actions = _parse_actions(result.text)
            candidate = _candidate_from_actions(case.task, actions, f"{case.case_id}-{model.model}") if actions is not None else None
            oracle = evaluate_task(case.task, candidate.state, candidate.actions) if candidate is not None else None
            success = bool(oracle and oracle.success)
            rows.append({
                "phase": "execution", "role": "executor", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "model": model.model, "success": success,
                "requirement_accuracy": (
                    len(oracle.passed_requirement_ids) / len(case.task.requirements)
                    if oracle is not None and case.task.requirements else (1.0 if oracle else 0.0)
                ),
                "failure_class": "parser_or_execution" if candidate is None else (",".join(oracle.failed_requirement_ids) if not oracle.success else None),
            })
            raw_calls.append(_call_row(result, phase="execution", task_id=case.case_id, model=model.model, role="executor"))

    # Phase 3: 20 fixed candidates x 5 = 100 auditor calls.
    audit_bank = build_audit_candidate_bank()
    for model in models:
        for case in audit_bank:
            payload = _public_task(case.task) | {
                "candidate_actions": [a.to_dict() for a in case.candidate.actions],
                "candidate_final_state": case.candidate.state.to_dict(),
            }
            messages = [
                {"role": "system", "content": "Audit the candidate exhaustively. Return ONLY JSON {\"accept\":true|false,\"failed_requirements\":[string],\"reason\":string}. Reject any missing, wrong, prohibited, ordered-wrong, or unintended behavior."},
                {"role": "user", "content": json.dumps(payload, sort_keys=True)},
            ]
            context = {"run_id": run_id, "trial_id": case.case_id, "candidate_id": case.candidate.id, "call_id": f"{case.case_id}-{model.model}-audit"}
            result = caller.complete(model, messages, role="auditor", context=context, response_schema={"type": "object"})
            audit = _parse_json(result.text) or {}
            accept = audit.get("accept") if isinstance(audit.get("accept"), bool) else None
            correct = accept is not None and accept == case.oracle_success
            fault = case.candidate.injected_faults[0] if case.candidate.injected_faults else "none"
            rows.append({
                "phase": "auditing", "role": "auditor", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "requirement_count": len(case.task.requirements), "fault": fault,
                "model": model.model, "success": bool(correct), "oracle_success": case.oracle_success,
                "accept": accept,
                "tp": int(case.oracle_success and accept is True),
                "tn": int((not case.oracle_success) and accept is False),
                "fp": int((not case.oracle_success) and accept is True),
                "fn": int(case.oracle_success and accept is False),
            })
            raw_calls.append(_call_row(result, phase="auditing", task_id=case.case_id, model=model.model, role="auditor"))

    top_auditors = _rank_models(rows, "auditor", 2)

    # Phase 4: top two auditors x 10 hardest invalid candidates = 20 calls.
    atomic_cases = [case for case in audit_bank if not case.oracle_success][:10]
    for model_name in top_auditors:
        model = model_by_name[model_name]
        for case in atomic_cases:
            payload = _public_task(case.task) | {
                "candidate_actions": [a.to_dict() for a in case.candidate.actions],
                "candidate_final_state": case.candidate.state.to_dict(),
            }
            messages = [
                {"role": "system", "content": "Evaluate EACH requirement independently before the final decision. Return ONLY JSON {\"requirements\":[{\"id\":string,\"pass\":true|false,\"reason\":string}],\"accept\":true|false}. accept may be true only if every requirement passes and there is no unintended behavior."},
                {"role": "user", "content": json.dumps(payload, sort_keys=True)},
            ]
            context = {"run_id": run_id, "trial_id": case.case_id, "candidate_id": case.candidate.id, "call_id": f"{case.case_id}-{model_name}-atomic"}
            result = caller.complete(model, messages, role="atomic_auditor", context=context, response_schema={"type": "object"})
            audit = _parse_json(result.text) or {}
            accept = audit.get("accept") if isinstance(audit.get("accept"), bool) else None
            correct = accept is not None and accept == case.oracle_success
            rows.append({
                "phase": "atomic_audit", "role": "atomic_auditor", "task_id": case.case_id,
                "family": case.task.family, "complexity": case.task.complexity,
                "fault": case.candidate.injected_faults[0] if case.candidate.injected_faults else "none",
                "model": model_name, "success": bool(correct), "oracle_success": case.oracle_success, "accept": accept,
            })
            raw_calls.append(_call_row(result, phase="atomic_audit", task_id=case.case_id, model=model_name, role="atomic_auditor"))

    # Phase 5: top two executors act as repair candidates. 10 x 2 x 4 = 80 calls.
    top_repair_models = _rank_models(rows, "executor", 2)
    repair_bank = build_repair_candidate_bank()
    for model_name in top_repair_models:
        model = model_by_name[model_name]
        for case in repair_bank:
            original_oracle = evaluate_task(case.task, case.candidate.state, case.candidate.actions)
            original_passed = set(original_oracle.passed_requirement_ids)
            for feedback_style in ("raw", "structured"):
                for strategy in ("regenerate", "targeted"):
                    failed_ids = list(original_oracle.failed_requirement_ids)
                    if feedback_style == "raw":
                        feedback: Any = {"failed_requirements": failed_ids}
                    else:
                        req_by_id = {r.id: r for r in case.task.requirements}
                        feedback = {
                            "failed_requirements": [
                                {
                                    "id": rid,
                                    "path": req_by_id[rid].path,
                                    "observed": case.candidate.state.get(req_by_id[rid].path),
                                    "expected": req_by_id[rid].expected,
                                    "admissible": [req_by_id[rid].expected],
                                }
                                for rid in failed_ids if rid in req_by_id
                            ]
                        }
                    instruction = (
                        "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]}. "
                        + ("Repair only the failed parts and preserve every already-correct requirement." if strategy == "targeted" else "Regenerate the complete action plan from scratch.")
                    )
                    payload = _public_task(case.task) | {
                        "previous_actions": [a.to_dict() for a in case.candidate.actions],
                        "validator_feedback": feedback,
                    }
                    messages = [{"role": "system", "content": instruction}, {"role": "user", "content": json.dumps(payload, sort_keys=True)}]
                    suffix = f"{feedback_style}-{strategy}"
                    context = {"run_id": run_id, "trial_id": case.case_id, "candidate_id": case.candidate.id, "call_id": f"{case.case_id}-{model_name}-{suffix}"}
                    result = caller.complete(model, messages, role="repairer", context=context, response_schema={"type": "object"})
                    actions = _parse_actions(result.text)
                    candidate = _candidate_from_actions(case.task, actions, f"{case.case_id}-{model_name}-{suffix}") if actions is not None else None
                    oracle = evaluate_task(case.task, candidate.state, candidate.actions) if candidate is not None else None
                    new_passed = set(oracle.passed_requirement_ids) if oracle is not None else set()
                    preserved = len(original_passed & new_passed)
                    introduced = len(original_passed - new_passed)
                    repaired = len(set(original_oracle.failed_requirement_ids) & new_passed)
                    row = {
                        "phase": "repair_factorial", "role": "repairer", "task_id": case.case_id,
                        "family": case.task.family, "complexity": case.task.complexity,
                        "fault": case.candidate.injected_faults[0] if case.candidate.injected_faults else "none",
                        "model": model_name, "feedback_style": feedback_style, "strategy": strategy,
                        "success": bool(oracle and oracle.success),
                        "original_passed": len(original_passed), "preserved_passed": preserved,
                        "new_failures_introduced": introduced, "failed_requirements_repaired": repaired,
                        "preservation_rate": preserved / len(original_passed) if original_passed else 1.0,
                    }
                    rows.append(row)
                    repairs.append(row)
                    raw_calls.append(_call_row(result, phase="repair_factorial", task_id=case.case_id, model=model_name, role="repairer"))

    # Phase 6: bounded progressive specialization on 10 untouched holdouts.
    formalizer_champion = (_rank_models(rows, "formalizer", 1) or [LOCAL_MODELS[0]])[0]
    executor_champion = (_rank_models(rows, "executor", 1) or [LOCAL_MODELS[0]])[0]
    auditor_champion = (top_auditors or [LOCAL_MODELS[0]])[0]
    repair_champion = (top_repair_models or [LOCAL_MODELS[0]])[0]
    router = {
        "formalizer": formalizer_champion,
        "executor": executor_champion,
        "auditor": auditor_champion,
        "repairer": repair_champion,
    }

    # Choose best single model by pooled formalizer/executor/auditor correctness.
    pooled: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        if row.get("role") in {"formalizer", "executor", "auditor"}:
            pooled[str(row["model"])].append(bool(row.get("success")))
    best_single = sorted(pooled, key=lambda m: (-(sum(pooled[m]) / len(pooled[m])), m))[0]

    holdouts = build_holdout_cases()[:10]
    for case in holdouts:
        # Control: best single model one-shot executor.
        model = model_by_name[best_single]
        direct_messages = [
            {"role": "system", "content": "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]} satisfying all requirements."},
            {"role": "user", "content": json.dumps(_public_task(case.task), sort_keys=True)},
        ]
        direct = caller.complete(model, direct_messages, role="executor", context={"run_id": run_id, "trial_id": case.case_id, "call_id": f"{case.case_id}-{best_single}-control"}, response_schema={"type": "object"})
        direct_actions = _parse_actions(direct.text)
        direct_candidate = _candidate_from_actions(case.task, direct_actions, f"{case.case_id}-control") if direct_actions is not None else None
        direct_oracle = evaluate_task(case.task, direct_candidate.state, direct_candidate.actions) if direct_candidate is not None else None
        rows.append({"phase": "progressive_holdout", "role": "pipeline", "pipeline": "best_single_one_shot", "task_id": case.case_id, "family": case.task.family, "complexity": case.task.complexity, "model": best_single, "success": bool(direct_oracle and direct_oracle.success)})
        raw_calls.append(_call_row(direct, phase="progressive_holdout", task_id=case.case_id, model=best_single, role="executor"))

        # Specialized stack: formalize -> execute -> validate -> repair if needed -> audit.
        fmodel = model_by_name[formalizer_champion]
        fmessages = [
            {"role": "system", "content": "Return ONLY JSON {\"requirements\":[{\"id\":string,\"kind\":string,\"path\":string,\"expected\":any,\"metadata\":object}]} with no invented requirements."},
            {"role": "user", "content": case.task.goal},
        ]
        fresult = caller.complete(fmodel, fmessages, role="formalizer", context={"run_id": run_id, "trial_id": case.case_id, "call_id": f"{case.case_id}-{formalizer_champion}-stack-formalize"}, response_schema={"type": "object"})
        raw_calls.append(_call_row(fresult, phase="progressive_holdout", task_id=case.case_id, model=formalizer_champion, role="formalizer"))
        ir = _parse_json(fresult.text) or {"requirements": case.task.metadata.get("public_requirements", [])}

        emodel = model_by_name[executor_champion]
        epayload = _public_task(case.task) | {"formalized_ir": ir}
        emessages = [
            {"role": "system", "content": "Return ONLY JSON {\"actions\":[{\"op\":string,\"path\":string,\"value\":any}]} satisfying the formalized requirements."},
            {"role": "user", "content": json.dumps(epayload, sort_keys=True)},
        ]
        eresult = caller.complete(emodel, emessages, role="executor", context={"run_id": run_id, "trial_id": case.case_id, "call_id": f"{case.case_id}-{executor_champion}-stack-exec"}, response_schema={"type": "object"})
        raw_calls.append(_call_row(eresult, phase="progressive_holdout", task_id=case.case_id, model=executor_champion, role="executor"))
        actions = _parse_actions(eresult.text)
        candidate = _candidate_from_actions(case.task, actions, f"{case.case_id}-specialized") if actions is not None else None
        oracle = evaluate_task(case.task, candidate.state, candidate.actions) if candidate is not None else None
        validator_ok = bool(oracle and oracle.success)
        validator_rows.append({"task_id": case.case_id, "pipeline": "specialized", "ok": validator_ok, "failed_requirements": list(oracle.failed_requirement_ids) if oracle else ["parse_or_execution"]})

        if not validator_ok:
            rmodel = model_by_name[repair_champion]
            feedback = {
                "failed_requirements": list(oracle.failed_requirement_ids) if oracle else ["parse_or_execution"],
                "expected_requirements": case.task.metadata.get("public_requirements", []),
            }
            rmessages = [
                {"role": "system", "content": "Return ONLY JSON actions. Patch the failed requirements while preserving already-correct behavior."},
                {"role": "user", "content": json.dumps(epayload | {"previous_actions": [a.to_dict() for a in (actions or ())], "validator_feedback": feedback}, sort_keys=True)},
            ]
            rresult = caller.complete(rmodel, rmessages, role="repairer", context={"run_id": run_id, "trial_id": case.case_id, "call_id": f"{case.case_id}-{repair_champion}-stack-repair"}, response_schema={"type": "object"})
            raw_calls.append(_call_row(rresult, phase="progressive_holdout", task_id=case.case_id, model=repair_champion, role="repairer"))
            repaired_actions = _parse_actions(rresult.text)
            repaired_candidate = _candidate_from_actions(case.task, repaired_actions, f"{case.case_id}-specialized-repaired") if repaired_actions is not None else None
            if repaired_candidate is not None:
                candidate = repaired_candidate
                actions = repaired_actions
                oracle = evaluate_task(case.task, candidate.state, candidate.actions)
                validator_ok = oracle.success

        amodel = model_by_name[auditor_champion]
        apayload = _public_task(case.task) | {
            "candidate_actions": [a.to_dict() for a in (actions or ())],
            "candidate_final_state": candidate.state.to_dict() if candidate is not None else None,
        }
        amessages = [
            {"role": "system", "content": "Audit this candidate. Return ONLY JSON {\"accept\":true|false,\"failed_requirements\":[string],\"reason\":string}."},
            {"role": "user", "content": json.dumps(apayload, sort_keys=True)},
        ]
        aresult = caller.complete(amodel, amessages, role="auditor", context={"run_id": run_id, "trial_id": case.case_id, "call_id": f"{case.case_id}-{auditor_champion}-stack-audit"}, response_schema={"type": "object"})
        raw_calls.append(_call_row(aresult, phase="progressive_holdout", task_id=case.case_id, model=auditor_champion, role="auditor"))
        audit = _parse_json(aresult.text) or {}
        accept = audit.get("accept") is True
        final_success = bool(validator_ok and accept)
        rows.append({"phase": "progressive_holdout", "role": "pipeline", "pipeline": "specialized_stack", "task_id": case.case_id, "family": case.task.family, "complexity": case.task.complexity, "model": "layered", "success": final_success})

        # Alternate order probe: audit the pre-repair/direct specialized candidate.
        alt_payload = _public_task(case.task) | {
            "candidate_actions": [a.to_dict() for a in (actions or ())],
            "candidate_final_state": candidate.state.to_dict() if candidate is not None else None,
            "order_probe": "audit_before_final_validator",
        }
        alt_messages = [
            {"role": "system", "content": "Audit before final deterministic validation. Return ONLY JSON {\"accept\":true|false,\"failed_requirements\":[string],\"reason\":string}."},
            {"role": "user", "content": json.dumps(alt_payload, sort_keys=True)},
        ]
        alt = caller.complete(amodel, alt_messages, role="auditor", context={"run_id": run_id, "trial_id": case.case_id, "call_id": f"{case.case_id}-{auditor_champion}-alt-audit"}, response_schema={"type": "object"})
        raw_calls.append(_call_row(alt, phase="progressive_holdout", task_id=case.case_id, model=auditor_champion, role="auditor"))
        alt_accept = (_parse_json(alt.text) or {}).get("accept") is True
        rows.append({"phase": "progressive_holdout", "role": "pipeline", "pipeline": "alternate_order", "task_id": case.case_id, "family": case.task.family, "complexity": case.task.complexity, "model": "layered", "success": bool(validator_ok and alt_accept)})

    # Phase 7: 8 decision-sensitive fixed audit cells x 5 models = 40 uncached repetitions.
    stability_cases = audit_bank[:8]
    for model in models:
        for case in stability_cases:
            payload = _public_task(case.task) | {
                "candidate_actions": [a.to_dict() for a in case.candidate.actions],
                "candidate_final_state": case.candidate.state.to_dict(),
                "stability_replication": True,
            }
            messages = [
                {"role": "system", "content": "Repeat the audit independently. Return ONLY JSON {\"accept\":true|false,\"failed_requirements\":[string],\"reason\":string}."},
                {"role": "user", "content": json.dumps(payload, sort_keys=True)},
            ]
            context = {"run_id": run_id, "trial_id": case.case_id, "candidate_id": case.candidate.id, "call_id": f"{case.case_id}-{model.model}-stability"}
            result = caller.complete(model, messages, role="auditor", context=context, response_schema={"type": "object"}, allow_cache=False)
            accept = (_parse_json(result.text) or {}).get("accept")
            success = isinstance(accept, bool) and accept == case.oracle_success
            rows.append({"phase": "stability", "role": "auditor", "task_id": case.case_id, "family": case.task.family, "complexity": case.task.complexity, "model": model.model, "success": bool(success), "oracle_success": case.oracle_success, "accept": accept})
            raw_calls.append(_call_row(result, phase="stability", task_id=case.case_id, model=model.model, role="auditor"))

    if budget.physical_calls > hard_limit:
        raise AssertionError("physical call ceiling violated")

    # Derive capability/routing outputs without more model calls.
    router_rows = [row for row in rows if row.get("role") in {"formalizer", "executor", "auditor", "repairer"}]
    layered = derive_layered_router(router_rows)
    outcome_map: dict[str, dict[str, bool]] = defaultdict(dict)
    for row in router_rows:
        outcome_map[str(row["task_id"])][str(row["model"])] = bool(row.get("success"))
    pair_rows = []
    for i, a in enumerate(LOCAL_MODELS):
        for b in LOCAL_MODELS[i + 1:]:
            pair_rows.append(model_complementarity(outcome_map, a, b))

    return {
        "run_id": run_id,
        "physical_model_calls": budget.physical_calls,
        "cache_hits": budget.cache_hits,
        "hard_call_limit": hard_limit,
        "models": list(LOCAL_MODELS),
        "phase_limits": dict(LOCAL_PHASE_LIMITS),
        "records": rows,
        "raw_calls": raw_calls,
        "repairs": repairs,
        "validator_results": validator_rows,
        "role_champions": layered.get("role_champions", {}),
        "layered_router": layered,
        "model_pair_synergy": pair_rows,
        "capability_by_role_model": capability_matrix(router_rows, ("role", "model")),
        "capability_by_family_model": capability_matrix(router_rows, ("family", "model")),
        "capability_by_fault_model": capability_matrix([r for r in router_rows if r.get("fault") is not None], ("fault", "model")),
        "capability_by_complexity_model": capability_matrix(router_rows, ("complexity", "model")),
        "capability_by_representation_model": capability_matrix([r for r in router_rows if r.get("representation") is not None], ("representation", "model")),
    }
