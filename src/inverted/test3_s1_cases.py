from __future__ import annotations

from .domain import Action, Candidate
from .oracle import apply_actions, evaluate_task
from .system_executor import generate_candidate
from .test2_cases import ExecutionCase
from .tasks import generate_task


S1_HOLDOUT_A_SEED_BASE = 211000
S1_HOLDOUT_A_SEED_STRIDE = 223
S1_HOLDOUT_AR1_SEED_BASE = 411000
S1_HOLDOUT_AR1_SEED_STRIDE = 227
S1_HOLDOUT_AR1_FAULT_SEED_OFFSET = 700_001
S1_HOLDOUT_AR2_SEED_BASE = 611000
S1_HOLDOUT_AR2_SEED_STRIDE = 229
S1_HOLDOUT_AR2_FAULT_SEED_OFFSET = 900_001

_R2_FAMILIES = (
    "state",
    "policy",
    "reconciliation",
    "preservation",
    "dependency_order",
    "repair_containment",
)
_R2_ARMS = ("S1-A0", "S1-A1", "S1-A2", "S1-A3")


def build_holdout_a() -> list[ExecutionCase]:
    """Build the original deterministic Test-3 S1 holdout.

    This holdout is preserved for forensic reproducibility of the invalid first
    S1 execution. Corrective protocol S1-R1 uses ``build_holdout_a_r1``.
    """
    out: list[ExecutionCase] = []
    index = 0
    for family in ("state", "policy", "reconciliation"):
        for complexity in (1, 2, 3, 4):
            seed = S1_HOLDOUT_A_SEED_BASE + index * S1_HOLDOUT_A_SEED_STRIDE
            task = generate_task(family, complexity, seed)
            out.append(ExecutionCase(
                case_id=f"test3-s1-A-{family}-L{complexity}-{task.id}",
                task=task,
            ))
            index += 1
    return out


def build_holdout_a_r1() -> list[ExecutionCase]:
    """Build the fresh ten-case corrective S1-R1 Holdout A-R1."""
    schedule = (
        ("state", 1),
        ("policy", 2),
        ("reconciliation", 3),
        ("state", 4),
        ("policy", 1),
        ("reconciliation", 2),
        ("state", 3),
        ("policy", 4),
        ("reconciliation", 1),
        ("state", 2),
    )
    out: list[ExecutionCase] = []
    for index, (family, complexity) in enumerate(schedule):
        seed = S1_HOLDOUT_AR1_SEED_BASE + index * S1_HOLDOUT_AR1_SEED_STRIDE
        task = generate_task(family, complexity, seed)
        out.append(ExecutionCase(
            case_id=f"test3-s1-AR1-{family}-L{complexity}-{task.id}",
            task=task,
        ))
    return out


def build_holdout_a_r2() -> list[ExecutionCase]:
    """Build the preregistered 25-case S1-R2 Holdout A-R2."""
    schedule: list[tuple[str, int, bool]] = []
    for complexity in (1, 2, 3, 4):
        schedule.extend((family, complexity, False) for family in _R2_FAMILIES)
    schedule.append(("repair_containment", 4, True))

    out: list[ExecutionCase] = []
    for index, (family, complexity, stress) in enumerate(schedule):
        seed = S1_HOLDOUT_AR2_SEED_BASE + index * S1_HOLDOUT_AR2_SEED_STRIDE
        task = generate_task(family, complexity, seed)
        suffix = "-stress" if stress else ""
        out.append(ExecutionCase(
            case_id=f"test3-s1-AR2-{family}-L{complexity}{suffix}-{task.id}",
            task=task,
        ))
    return out


def build_seed_failure(case: ExecutionCase) -> Candidate:
    """Create the zero-call deterministic failed starting state for S1-R1."""
    seed = S1_HOLDOUT_AR1_FAULT_SEED_OFFSET + sum(ord(ch) for ch in case.case_id)
    candidate = generate_candidate(case.task, 0.0, seed)
    return Candidate(
        id=f"{candidate.id}-s1-r1-seed-failure",
        state=candidate.state,
        actions=candidate.actions,
        injected_faults=candidate.injected_faults,
        configured_quality=candidate.configured_quality,
        metadata={
            **candidate.metadata,
            "s1_r1_seed_failure": True,
            "source_case_id": case.case_id,
        },
    )


def _r2_fault_seed(case: ExecutionCase) -> int:
    return S1_HOLDOUT_AR2_FAULT_SEED_OFFSET + sum(ord(ch) for ch in case.case_id)


def _r2_candidate(case: ExecutionCase, actions: tuple[Action, ...], faults: tuple[str, ...], seed: int) -> Candidate:
    state = apply_actions(case.task.initial_state, actions)
    candidate = Candidate(
        id=f"s1-r2-seed-{case.task.id}",
        state=state,
        actions=actions,
        injected_faults=faults,
        configured_quality=0.0,
        metadata={
            "seed": seed,
            "s1_r2_seed_failure": True,
            "source_case_id": case.case_id,
            "stress_case": "stress" in case.case_id,
        },
    )
    if evaluate_task(case.task, candidate.state, candidate.actions).success:
        raise AssertionError(f"S1-R2 seed fixture unexpectedly succeeds: {case.case_id}")
    return candidate


def build_seed_failure_r2(case: ExecutionCase) -> Candidate:
    """Create the preregistered public-safe deterministic failed start for R2."""
    seed = _r2_fault_seed(case)
    family = case.task.family

    if family in {"state", "policy", "reconciliation"}:
        base = generate_candidate(case.task, 0.0, seed)
        candidate = Candidate(
            id=f"{base.id}-s1-r2-seed-failure",
            state=base.state,
            actions=base.actions,
            injected_faults=base.injected_faults,
            configured_quality=base.configured_quality,
            metadata={
                **base.metadata,
                "s1_r2_seed_failure": True,
                "source_case_id": case.case_id,
                "stress_case": False,
            },
        )
        if evaluate_task(case.task, candidate.state, candidate.actions).success:
            raise AssertionError(f"S1-R2 ordinary seed fixture unexpectedly succeeds: {case.case_id}")
        return candidate

    valid = generate_candidate(case.task, 1.0, seed)
    valid_result = evaluate_task(case.task, valid.state, valid.actions)
    if not valid_result.success:
        raise AssertionError(f"S1-R2 public task cannot produce a valid pre-fault candidate: {case.case_id}")

    if family == "preservation":
        preserve = next(req for req in case.task.requirements if req.kind == "preserve")
        actions = tuple(valid.actions) + (Action("set", preserve.path, "__S1_R2_PRESERVATION_FAULT__"),)
        return _r2_candidate(case, actions, ("preservation_violation",), seed)

    if family == "dependency_order":
        actions = list(valid.actions)
        grant_index = next(i for i, action in enumerate(actions) if action.op == "grant")
        start_index = next(i for i, action in enumerate(actions) if action.op == "start")
        actions[grant_index], actions[start_index] = actions[start_index], actions[grant_index]
        return _r2_candidate(case, tuple(actions), ("dependency_order_violation",), seed)

    if family == "repair_containment":
        actions = list(valid.actions)
        equal_requirements = [req for req in case.task.requirements if req.kind == "equal"]
        faults_to_inject = 2 if "stress" in case.case_id else 1
        faulted_paths: list[str] = []
        for fault_index, req in enumerate(equal_requirements[:faults_to_inject]):
            action_index = next(i for i, action in enumerate(actions) if action.path == req.path)
            original = actions[action_index]
            actions[action_index] = Action(original.op, original.path, f"__S1_R2_CONTAINMENT_FAULT_{fault_index+1}__")
            faulted_paths.append(req.path)
        return _r2_candidate(
            case,
            tuple(actions),
            tuple(f"localized_wrong_value:{path}" for path in faulted_paths),
            seed,
        )

    raise ValueError(f"S1-R2 unsupported family: {family}")


def r2_arm_order(task_index: int) -> tuple[str, ...]:
    """Return the preregistered balanced execution order for one R2 task."""
    if not 0 <= task_index <= 24:
        raise ValueError("S1-R2 task_index must be 0..24")
    if task_index == 24:
        return ("S1-A2", "S1-A0", "S1-A3", "S1-A1")
    shift = task_index % 4
    return _R2_ARMS[shift:] + _R2_ARMS[:shift]
