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
S1_HOLDOUT_AR3_SEED_BASE = 811000
S1_HOLDOUT_AR3_SEED_STRIDE = 233
S1_HOLDOUT_AR3_FAULT_SEED_OFFSET = 1_100_001

_R2_FAMILIES = (
    "state",
    "policy",
    "reconciliation",
    "preservation",
    "dependency_order",
    "repair_containment",
)
_R2_ARMS = ("S1-A0", "S1-A1", "S1-A2", "S1-A3")
_R3_FAMILIES = _R2_FAMILIES
_R3_ARMS = _R2_ARMS


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


def _expanded_holdout(
    *,
    prefix: str,
    seed_base: int,
    seed_stride: int,
    families: tuple[str, ...],
) -> list[ExecutionCase]:
    schedule: list[tuple[str, int, bool]] = []
    for complexity in (1, 2, 3, 4):
        schedule.extend((family, complexity, False) for family in families)
    schedule.append(("repair_containment", 4, True))

    out: list[ExecutionCase] = []
    for index, (family, complexity, stress) in enumerate(schedule):
        seed = seed_base + index * seed_stride
        task = generate_task(family, complexity, seed)
        suffix = "-stress" if stress else ""
        out.append(ExecutionCase(
            case_id=f"test3-s1-{prefix}-{family}-L{complexity}{suffix}-{task.id}",
            task=task,
        ))
    return out


def build_holdout_a_r2() -> list[ExecutionCase]:
    """Build the preregistered 25-case S1-R2 Holdout A-R2."""
    return _expanded_holdout(
        prefix="AR2",
        seed_base=S1_HOLDOUT_AR2_SEED_BASE,
        seed_stride=S1_HOLDOUT_AR2_SEED_STRIDE,
        families=_R2_FAMILIES,
    )


def build_holdout_a_r3() -> list[ExecutionCase]:
    """Build fresh corrective S1-R3 Holdout A-R3 after R2 measurement defects."""
    return _expanded_holdout(
        prefix="AR3",
        seed_base=S1_HOLDOUT_AR3_SEED_BASE,
        seed_stride=S1_HOLDOUT_AR3_SEED_STRIDE,
        families=_R3_FAMILIES,
    )


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


def _r3_fault_seed(case: ExecutionCase) -> int:
    return S1_HOLDOUT_AR3_FAULT_SEED_OFFSET + sum(ord(ch) for ch in case.case_id)


def _expanded_candidate(
    case: ExecutionCase,
    actions: tuple[Action, ...],
    faults: tuple[str, ...],
    seed: int,
    *,
    revision: str,
) -> Candidate:
    key = revision.lower().replace("-", "_") + "_seed_failure"
    state = apply_actions(case.task.initial_state, actions)
    candidate = Candidate(
        id=f"{revision.lower()}-seed-{case.task.id}",
        state=state,
        actions=actions,
        injected_faults=faults,
        configured_quality=0.0,
        metadata={
            "seed": seed,
            key: True,
            "source_case_id": case.case_id,
            "stress_case": "stress" in case.case_id,
        },
    )
    if evaluate_task(case.task, candidate.state, candidate.actions).success:
        raise AssertionError(f"{revision} seed fixture unexpectedly succeeds: {case.case_id}")
    return candidate


def _r2_candidate(case: ExecutionCase, actions: tuple[Action, ...], faults: tuple[str, ...], seed: int) -> Candidate:
    return _expanded_candidate(case, actions, faults, seed, revision="S1-R2")


def _build_expanded_seed_failure(
    case: ExecutionCase,
    *,
    seed: int,
    revision: str,
) -> Candidate:
    metadata_key = revision.lower().replace("-", "_") + "_seed_failure"
    family = case.task.family

    if family in {"state", "policy", "reconciliation"}:
        base = generate_candidate(case.task, 0.0, seed)
        candidate = Candidate(
            id=f"{base.id}-{revision.lower()}-seed-failure",
            state=base.state,
            actions=base.actions,
            injected_faults=base.injected_faults,
            configured_quality=base.configured_quality,
            metadata={
                **base.metadata,
                metadata_key: True,
                "source_case_id": case.case_id,
                "stress_case": False,
            },
        )
        if evaluate_task(case.task, candidate.state, candidate.actions).success:
            raise AssertionError(f"{revision} ordinary seed fixture unexpectedly succeeds: {case.case_id}")
        return candidate

    valid = generate_candidate(case.task, 1.0, seed)
    valid_result = evaluate_task(case.task, valid.state, valid.actions)
    if not valid_result.success:
        raise AssertionError(f"{revision} public task cannot produce a valid pre-fault candidate: {case.case_id}")

    if family == "preservation":
        preserve = next(req for req in case.task.requirements if req.kind == "preserve")
        actions = tuple(valid.actions) + (Action("set", preserve.path, f"__{revision.replace('-', '_')}_PRESERVATION_FAULT__"),)
        return _expanded_candidate(case, actions, ("preservation_violation",), seed, revision=revision)

    if family == "dependency_order":
        actions = list(valid.actions)
        grant_index = next(i for i, action in enumerate(actions) if action.op == "grant")
        start_index = next(i for i, action in enumerate(actions) if action.op == "start")
        actions[grant_index], actions[start_index] = actions[start_index], actions[grant_index]
        return _expanded_candidate(case, tuple(actions), ("dependency_order_violation",), seed, revision=revision)

    if family == "repair_containment":
        actions = list(valid.actions)
        equal_requirements = [req for req in case.task.requirements if req.kind == "equal"]
        faults_to_inject = 2 if "stress" in case.case_id else 1
        faulted_paths: list[str] = []
        for fault_index, req in enumerate(equal_requirements[:faults_to_inject]):
            action_index = next(i for i, action in enumerate(actions) if action.path == req.path)
            original = actions[action_index]
            actions[action_index] = Action(
                original.op,
                original.path,
                f"__{revision.replace('-', '_')}_CONTAINMENT_FAULT_{fault_index+1}__",
            )
            faulted_paths.append(req.path)
        return _expanded_candidate(
            case,
            tuple(actions),
            tuple(f"localized_wrong_value:{path}" for path in faulted_paths),
            seed,
            revision=revision,
        )

    raise ValueError(f"{revision} unsupported family: {family}")


def build_seed_failure_r2(case: ExecutionCase) -> Candidate:
    """Create the preregistered public-safe deterministic failed start for R2."""
    return _build_expanded_seed_failure(case, seed=_r2_fault_seed(case), revision="S1-R2")


def build_seed_failure_r3(case: ExecutionCase) -> Candidate:
    """Create fresh deterministic failed starts for corrective R3."""
    return _build_expanded_seed_failure(case, seed=_r3_fault_seed(case), revision="S1-R3")


def _balanced_arm_order(task_index: int, *, revision: str) -> tuple[str, ...]:
    if not 0 <= task_index <= 24:
        raise ValueError(f"{revision} task_index must be 0..24")
    if task_index == 24:
        return ("S1-A2", "S1-A0", "S1-A3", "S1-A1")
    shift = task_index % 4
    return _R2_ARMS[shift:] + _R2_ARMS[:shift]


def r2_arm_order(task_index: int) -> tuple[str, ...]:
    """Return the preregistered balanced execution order for one R2 task."""
    return _balanced_arm_order(task_index, revision="S1-R2")


def r3_arm_order(task_index: int) -> tuple[str, ...]:
    """Return the fresh R3 balanced execution order, independent of outcomes."""
    return _balanced_arm_order(task_index, revision="S1-R3")
