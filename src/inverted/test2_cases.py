from __future__ import annotations

from dataclasses import dataclass
import json

from .domain import Action, Candidate, TaskCase
from .oracle import apply_actions, evaluate_task
from .system_executor import generate_candidate
from .tasks import generate_task


REPRESENTATIONS = (
    "structured",
    "natural",
    "paraphrased",
    "implicit",
    "perceptual_like",
)


@dataclass
class FormalizationCase:
    case_id: str
    task: TaskCase
    representation: str
    prompt_text: str


@dataclass
class ExecutionCase:
    case_id: str
    task: TaskCase


@dataclass
class CandidateProbe:
    case_id: str
    task: TaskCase
    candidate: Candidate
    oracle_success: bool


def _render_representation(task: TaskCase, representation: str) -> str:
    public = task.metadata.get("public_requirements", [])
    if representation == "structured":
        return json.dumps({"goal": task.goal, "requirements": public}, sort_keys=True)
    if representation == "natural":
        return f"Goal: {task.goal}. Starting state: {json.dumps(task.initial_state.to_dict(), sort_keys=True)}"
    if representation == "paraphrased":
        clauses = []
        for req in public:
            if req["kind"] == "equal":
                clauses.append(f"make {req['path']} end up as {req.get('expected')!r}")
            elif req["kind"] == "action_absent":
                clauses.append(f"avoid the {req['path']} operation entirely")
            elif req["kind"] == "action_before":
                clauses.append(f"finish {req['path']} before {req.get('expected')}")
        return "Please accomplish the following without unintended changes: " + "; ".join(clauses)
    if representation == "implicit":
        return (
            "Infer the intended constraints from this before/desired-state comparison. "
            f"BEFORE={json.dumps(task.initial_state.to_dict(), sort_keys=True)} "
            f"DESIRED={json.dumps(task.target_state.to_dict(), sort_keys=True)} "
            f"ALLOWED_OPS={json.dumps(list(task.allowed_ops))}"
        )
    if representation == "perceptual_like":
        observations = [
            {"slot": i + 1, "kind": r["kind"], "path": r["path"], "target": r.get("expected")}
            for i, r in enumerate(public)
        ]
        return "OBSERVATION_FRAME=" + json.dumps(observations, sort_keys=True) + "\nInfer the machine-checkable requirements."
    raise ValueError(f"unknown representation: {representation}")


def build_formalization_cases() -> list[FormalizationCase]:
    cases: list[FormalizationCase] = []
    families = ("state", "policy", "reconciliation")
    reps = (
        "structured", "natural", "paraphrased", "implicit",
        "perceptual_like", "structured", "natural", "paraphrased",
        "implicit", "perceptual_like", "structured", "natural",
    )
    for index in range(12):
        family = families[index % len(families)]
        complexity = (index % 4) + 1
        seed = 12000 + index * 97
        task = generate_task(family, complexity, seed)
        rep = reps[index]
        cases.append(FormalizationCase(
            case_id=f"formalize-{index+1:02d}-{task.id}-{rep}",
            task=task,
            representation=rep,
            prompt_text=_render_representation(task, rep),
        ))
    return cases


def build_execution_cases() -> list[ExecutionCase]:
    cases: list[ExecutionCase] = []
    index = 0
    for family in ("state", "policy", "reconciliation"):
        for complexity in (1, 2, 3, 4):
            task = generate_task(family, complexity, 30000 + index * 131)
            cases.append(ExecutionCase(f"execute-{family}-L{complexity}-{task.id}", task))
            index += 1
    return cases


def _find_fault_candidate(task: TaskCase, desired_fault: str, seed_start: int) -> Candidate:
    for candidate_seed in range(seed_start, seed_start + 10000):
        candidate = generate_candidate(task, 0.0, candidate_seed)
        base_faults = {fault.split("+")[0] for fault in candidate.injected_faults}
        if desired_fault in base_faults:
            oracle = evaluate_task(task, candidate.state, candidate.actions)
            if not oracle.success and all("+forced_requirement_violation" not in fault for fault in candidate.injected_faults):
                return candidate
    raise RuntimeError(f"could not deterministically generate clean fault {desired_fault!r} for {task.id}")


def _pure_side_effect_candidate(task: TaskCase, seed: int) -> Candidate:
    clean = generate_candidate(task, 1.0, seed)
    op = "set" if "set" in task.allowed_ops else task.allowed_ops[0]
    if task.family == "state":
        path = "guard.unexpected"
    elif task.family == "reconciliation":
        path = "resolved.unexpected"
    else:
        path = "workflow.unexpected"
    actions = tuple(clean.actions) + (Action(op, path, "side-effect"),)
    state = apply_actions(task.initial_state, actions)
    if not evaluate_task(task, state, actions).success:
        raise AssertionError("pure side-effect diagnostic unexpectedly violates explicit oracle requirements")
    return Candidate(
        id=f"semantic-side-effect-{task.id}",
        state=state,
        actions=actions,
        injected_faults=("unintended_side_effect",),
        configured_quality=0.0,
        metadata={"seed": seed, "semantic_probe": True},
    )


def build_audit_candidate_bank() -> list[CandidateProbe]:
    bank: list[CandidateProbe] = []
    for index in range(10):
        family = ("state", "policy", "reconciliation")[index % 3]
        complexity = (index % 4) + 1
        task = generate_task(family, complexity, 41000 + index * 173)
        candidate = generate_candidate(task, 1.0, 51000 + index)
        oracle = evaluate_task(task, candidate.state, candidate.actions)
        if not oracle.success:
            raise AssertionError("quality=1 candidate unexpectedly failed oracle")
        bank.append(CandidateProbe(f"audit-valid-{index+1:02d}-{task.id}", task, candidate, True))

    desired = (
        "omitted_requirement", "wrong_value", "unintended_side_effect",
        "ordering_violation", "forbidden_procedure",
        "wrong_value", "omitted_requirement", "unintended_side_effect",
        "ordering_violation", "forbidden_procedure",
    )
    for index, fault in enumerate(desired):
        family = "policy" if fault in {"ordering_violation", "forbidden_procedure"} else ("state", "reconciliation")[index % 2]
        complexity = 4 if fault in {"ordering_violation", "forbidden_procedure"} else ((index % 4) + 1)
        task = generate_task(family, complexity, 61000 + index * 181)
        if fault == "unintended_side_effect":
            candidate = _pure_side_effect_candidate(task, 71000 + index)
        else:
            candidate = _find_fault_candidate(task, fault, 71000 + index * 10000)
        oracle = evaluate_task(task, candidate.state, candidate.actions)
        bank.append(CandidateProbe(f"audit-invalid-{index+1:02d}-{task.id}-{fault}", task, candidate, oracle.success))
    return bank


def build_repair_candidate_bank() -> list[CandidateProbe]:
    desired = (
        "omitted_requirement", "wrong_value", "ordering_violation",
        "forbidden_procedure", "wrong_value", "omitted_requirement",
        "ordering_violation", "forbidden_procedure", "wrong_value",
        "omitted_requirement",
    )
    out: list[CandidateProbe] = []
    for index, fault in enumerate(desired):
        family = "policy" if fault in {"ordering_violation", "forbidden_procedure"} else ("state", "reconciliation")[index % 2]
        complexity = 4 if fault in {"ordering_violation", "forbidden_procedure"} else ((index % 4) + 1)
        task = generate_task(family, complexity, 81000 + index * 193)
        candidate = _find_fault_candidate(task, fault, 91000 + index * 10000)
        oracle = evaluate_task(task, candidate.state, candidate.actions)
        out.append(CandidateProbe(f"repair-{index+1:02d}-{task.id}-{fault}", task, candidate, oracle.success))
    return out


def build_holdout_cases() -> list[ExecutionCase]:
    out: list[ExecutionCase] = []
    index = 0
    for family in ("state", "policy", "reconciliation"):
        for complexity in (1, 2, 3, 4):
            task = generate_task(family, complexity, 111000 + index * 211)
            out.append(ExecutionCase(f"holdout-{family}-L{complexity}-{task.id}", task))
            index += 1
    return out
