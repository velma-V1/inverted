from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AttemptOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    STALL = "STALL"
    INFRA_INTERRUPTION = "INFRA_INTERRUPTION"


@dataclass(frozen=True)
class ExecutionDecision:
    action: str
    execution_id: str
    current_escalation_level: int
    next_escalation_level: int | None = None
    snapshot_required: bool = False
    terminal_status: str | None = None


def _execution_id(campaign_id: str, system_id: str, example_id: str,
                  escalation_level: int) -> str:
    return f"{campaign_id}:{system_id}:{example_id}:L{escalation_level}"


def advance_example(campaign_id: str, system_id: str, example_id: str,
                    escalation_level: int, outcome: AttemptOutcome) -> ExecutionDecision:
    if escalation_level < 0:
        raise ValueError("escalation_level must be zero or greater")
    execution_id = _execution_id(campaign_id, system_id, example_id, escalation_level)
    if outcome is AttemptOutcome.INFRA_INTERRUPTION:
        return ExecutionDecision(
            "RESUME", execution_id, escalation_level,
            next_escalation_level=escalation_level,
        )
    if outcome is AttemptOutcome.COMPLETED:
        return ExecutionDecision("VERIFY", execution_id, escalation_level)
    if outcome is AttemptOutcome.CORRECT:
        status = "PASS" if escalation_level == 0 else "RECOVERED_BY_ESCALATION"
        return ExecutionDecision(
            "ADVANCE", execution_id, escalation_level,
            terminal_status=status,
        )
    return ExecutionDecision(
        "CAPTURE_AND_ESCALATE", execution_id, escalation_level,
        next_escalation_level=escalation_level + 1,
        snapshot_required=True,
    )
