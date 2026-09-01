from __future__ import annotations

from .domain import Candidate
from .system_executor import generate_candidate
from .test2_cases import ExecutionCase
from .tasks import generate_task


S1_HOLDOUT_A_SEED_BASE = 211000
S1_HOLDOUT_A_SEED_STRIDE = 223
S1_HOLDOUT_AR1_SEED_BASE = 411000
S1_HOLDOUT_AR1_SEED_STRIDE = 227
S1_HOLDOUT_AR1_FAULT_SEED_OFFSET = 700_001


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
    """Build the fresh ten-case corrective S1-R1 Holdout A-R1.

    Seeds are disjoint from Test-2 and the original S1 Holdout A. The schedule
    intentionally spans all three task families and all four complexity levels
    without using model outcomes to select cases.
    """
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


def build_seed_failure(case: ExecutionCase) -> Candidate:
    """Create the zero-call deterministic failed starting state for S1-R1.

    ``generate_candidate(..., 0.0, ...)`` deterministically injects at least one
    benchmark fault and guarantees the resulting candidate does not satisfy the
    task. Fault metadata is retained for forensic evidence but is never rendered
    into S1 model prompts.
    """
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
