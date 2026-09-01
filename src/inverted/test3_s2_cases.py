from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain import Action, Candidate, Requirement, TaskCase
from .oracle import apply_actions, evaluate_task
from .system_executor import generate_candidate
from .tasks import generate_task


S2_PROTOCOL_REVISION = "S2-R1"
S2_HOLDOUT = "B-R1"
S2_HOLDOUT_SEED_BASE = 1_211_000
S2_HOLDOUT_SEED_STRIDE = 239
S2_MAX_SEED_SCAN = 128
S2_FIXTURE_SEED_OFFSET = 1_700_001
S2_FAMILIES = (
    "state",
    "policy",
    "reconciliation",
    "preservation",
    "dependency_order",
    "repair_containment",
)
S2_PERTURBATIONS = ("localized", "compound", "structural")


@dataclass(frozen=True)
class S2ExecutionCase:
    case_id: str
    task: TaskCase
    metadata: dict[str, Any]


def _select_base_task(family: str, complexity: int, base_index: int) -> tuple[TaskCase, int, int]:
    """Choose the first fresh deterministic task with two observable requirements.

    Compound routing evidence is meaningful only when the verifier can expose at
    least two distinct failed public requirements. Seed scanning is deterministic,
    model-free, bounded, and its final seed/offset are retained as provenance.
    """
    first_seed = S2_HOLDOUT_SEED_BASE + base_index * S2_HOLDOUT_SEED_STRIDE
    for offset in range(S2_MAX_SEED_SCAN):
        seed = first_seed + offset
        task = generate_task(family, complexity, seed)
        if len(task.requirements) >= 2:
            return task, seed, offset
    raise AssertionError(
        f"S2 could not find a two-requirement Holdout-B task within {S2_MAX_SEED_SCAN} seeds: "
        f"{family} L{complexity}"
    )


def build_holdout_b() -> list[S2ExecutionCase]:
    """Build fresh 72-case Holdout B as 24 three-way causal-twin groups."""
    cases: list[S2ExecutionCase] = []
    base_index = 0
    for family in S2_FAMILIES:
        for complexity in (1, 2, 3, 4):
            task, selected_seed, seed_scan_offset = _select_base_task(family, complexity, base_index)
            for perturbation in S2_PERTURBATIONS:
                cases.append(S2ExecutionCase(
                    case_id=f"test3-s2-BR1-{family}-L{complexity}-{perturbation}-{task.id}",
                    task=task,
                    metadata={
                        "base_task_id": task.id,
                        "perturbation_class": perturbation,
                        "holdout": S2_HOLDOUT,
                        "protocol_revision": S2_PROTOCOL_REVISION,
                        "selected_seed": selected_seed,
                        "seed_scan_offset": seed_scan_offset,
                        "requirement_count": len(task.requirements),
                    },
                ))
            base_index += 1
    return cases


def _fixture_seed(case: S2ExecutionCase) -> int:
    base = sum(ord(ch) for ch in str(case.metadata["base_task_id"]))
    return S2_FIXTURE_SEED_OFFSET + base


def _valid_candidate(case: S2ExecutionCase) -> Candidate:
    candidate = generate_candidate(case.task, 1.0, _fixture_seed(case))
    result = evaluate_task(case.task, candidate.state, candidate.actions)
    if not result.success:
        raise AssertionError(f"S2 base fixture unexpectedly invalid: {case.case_id}")
    return candidate


def _matches_requirement(action: Action, req: Requirement) -> bool:
    if req.kind == "action_present":
        return action.op == req.path and (req.expected is None or action.path == str(req.expected))
    return False


def _corrupt_requirement(actions: list[Action], req: Requirement, marker: str) -> list[Action]:
    out = list(actions)
    if req.kind in {"equal", "preserve"}:
        out.append(Action("set", req.path, marker))
        return out
    if req.kind == "action_present":
        filtered = [action for action in out if not _matches_requirement(action, req)]
        if len(filtered) == len(out):
            filtered.append(Action("delete", str(req.expected or "s2.missing"), None))
        return filtered
    if req.kind == "action_absent":
        out.append(Action(req.path, str(req.expected or "s2.forbidden"), True))
        return out
    if req.kind == "action_before":
        before_index = next((i for i, action in enumerate(out) if action.op == req.path), None)
        after_index = next((i for i, action in enumerate(out) if action.op == str(req.expected)), None)
        if before_index is not None and after_index is not None:
            out[before_index], out[after_index] = out[after_index], out[before_index]
        else:
            out.append(Action("delete", "s2.order", None))
        return out
    raise ValueError(f"unsupported S2 requirement kind: {req.kind}")


def _localized_actions(task: TaskCase, valid: Candidate) -> tuple[Action, ...]:
    req = task.requirements[0]
    return tuple(_corrupt_requirement(list(valid.actions), req, "__S2_LOCALIZED_FAILURE__"))


def _compound_actions(task: TaskCase, valid: Candidate) -> tuple[Action, ...]:
    if len(task.requirements) < 2:
        raise AssertionError("S2 compound fixture requires two independently observable public requirements")
    actions = list(valid.actions)
    for index, req in enumerate(task.requirements[:2]):
        actions = _corrupt_requirement(actions, req, f"__S2_COMPOUND_FAILURE_{index+1}__")
    return tuple(actions)


def _structural_actions(task: TaskCase, valid: Candidate) -> tuple[Action, ...]:
    actions = list(valid.actions)
    if task.family == "dependency_order":
        grant = next((i for i, action in enumerate(actions) if action.op == "grant"), None)
        start = next((i for i, action in enumerate(actions) if action.op == "start"), None)
        if grant is not None and start is not None:
            actions[grant], actions[start] = actions[start], actions[grant]
            return tuple(actions)
    if task.family == "preservation":
        req = next(req for req in task.requirements if req.kind == "preserve")
        actions.append(Action("set", req.path, "__S2_STRUCTURAL_PRESERVE__"))
        return tuple(actions)
    if task.family == "policy":
        absent = next((req for req in task.requirements if req.kind == "action_absent"), None)
        if absent is not None:
            actions.append(Action(absent.path, str(absent.expected or "s2.forbidden"), True))
            return tuple(actions)
    if task.family == "repair_containment":
        preserve = next((req for req in task.requirements if req.kind == "preserve"), None)
        if preserve is not None:
            actions.append(Action("set", preserve.path, "__S2_STRUCTURAL_CONTAINMENT__"))
            return tuple(actions)
    if actions:
        first = actions[0]
        replacement_op = "delete" if "delete" in task.allowed_ops else first.op
        replacement_value = None if replacement_op == "delete" else "__S2_STRUCTURAL_FAILURE__"
        actions[0] = Action(replacement_op, first.path, replacement_value)
        return tuple(actions)
    req = task.requirements[0]
    return tuple(_corrupt_requirement(actions, req, "__S2_STRUCTURAL_FAILURE__"))


def build_seed_failure_s2(case: S2ExecutionCase) -> Candidate:
    """Construct one deterministic verified failed current state without model inference."""
    valid = _valid_candidate(case)
    perturbation = str(case.metadata["perturbation_class"])
    if perturbation == "localized":
        actions = _localized_actions(case.task, valid)
    elif perturbation == "compound":
        actions = _compound_actions(case.task, valid)
    elif perturbation == "structural":
        actions = _structural_actions(case.task, valid)
    else:
        raise ValueError(f"unknown S2 perturbation: {perturbation}")

    state = apply_actions(case.task.initial_state, actions)
    result = evaluate_task(case.task, state, actions)
    if result.success:
        raise AssertionError(f"S2 seed fixture unexpectedly succeeds: {case.case_id}")
    if perturbation == "compound" and len(set(result.failed_requirement_ids)) < 2:
        raise AssertionError(
            f"S2 compound fixture did not produce two observable failures: "
            f"{case.case_id} -> {result.failed_requirement_ids}"
        )
    requirement_by_id = {req.id: req for req in case.task.requirements}
    public_evidence = {
        "failed_requirement_ids": list(result.failed_requirement_ids),
        "failed_requirement_kinds": [requirement_by_id[item].kind for item in result.failed_requirement_ids],
        "failed_count": len(result.failed_requirement_ids),
        "deterministic_success": False,
        "catastrophic": bool(result.catastrophic),
    }
    return Candidate(
        id=f"s2-seed-{case.case_id}",
        state=state,
        actions=actions,
        injected_faults=(f"s2_fixture:{perturbation}",),
        configured_quality=0.0,
        metadata={
            "s2_seed_failure": True,
            "source_case_id": case.case_id,
            "base_task_id": case.metadata["base_task_id"],
            "private_fixture_label": perturbation,
            "fixture_selected_seed": case.metadata.get("selected_seed"),
            "fixture_seed_scan_offset": case.metadata.get("seed_scan_offset"),
            "public_evidence": public_evidence,
        },
    )
