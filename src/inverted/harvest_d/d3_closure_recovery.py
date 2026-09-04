from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class RecoveryOutcome(str, Enum):
    RECOVERED = "RECOVERED"
    MIGRATED = "MIGRATED"
    WORSENED = "WORSENED"
    ESCALATED = "ESCALATED"
    SAFE_STOPPED = "SAFE_STOPPED"


_REQUIRED_STAGES = (
    "initial_state",
    "first_divergence",
    "first_detection",
    "failure_class",
    "available_recovery_frontier",
    "selected_recovery",
    "system_admission",
    "resulting_state",
    "verifier_postcondition",
    "external_effect_status",
    "final_status",
)


def validate_recovery_trajectory(row: Mapping[str, Any]) -> None:
    missing = [key for key in _REQUIRED_STAGES if key not in row]
    if missing:
        raise ValueError(f"recovery trajectory missing required stages: {missing}")

    effect = str(row.get("external_effect_status", "")).upper()
    recovery = str(row.get("selected_recovery", "")).upper()
    if effect == "UNKNOWN" and recovery == "RETRY":
        raise ValueError("blind retry is forbidden when external effect is unknown")

    status = str(row.get("final_status", "")).upper()
    if status not in {item.value for item in RecoveryOutcome}:
        raise ValueError(f"unknown recovery final status: {status}")


def classify_recovery_outcome(row: Mapping[str, Any]) -> RecoveryOutcome:
    validate_recovery_trajectory(row)
    return RecoveryOutcome(str(row["final_status"]).upper())
