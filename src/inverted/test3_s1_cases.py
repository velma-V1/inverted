from __future__ import annotations

from .test2_cases import ExecutionCase
from .tasks import generate_task


S1_HOLDOUT_A_SEED_BASE = 211000
S1_HOLDOUT_A_SEED_STRIDE = 223


def build_holdout_a() -> list[ExecutionCase]:
    """Build the dedicated deterministic Test-3 S1 holdout.

    These seeds are disjoint from Test-2 discovery and holdout seeds. Hidden
    target state remains inside TaskCase for scoring only and is never rendered
    into model prompts by the S1 runtime.
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
