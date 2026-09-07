from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .constraint_ledger import build_constraint_ledger
from .contracts import AgentEvent


@dataclass
class OutcomeScore:
    passed: bool
    exit_code: int
    details: dict = field(default_factory=dict)


@dataclass
class ProcessScore:
    passed: bool
    violations: list[str] = field(default_factory=list)
    infrastructure_failure: bool = False


def verify_outcome(task: dict, workspace: Path) -> OutcomeScore:
    verifier = Path(task["_task_root"]) / task["verifier"]
    completed = subprocess.run([sys.executable, str(verifier), str(Path(workspace).resolve())], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    details = {}
    try:
        lines = [x for x in completed.stdout.splitlines() if x.strip()]
        details = json.loads(lines[-1]) if lines else {}
    except Exception:
        details = {"stdout": completed.stdout, "stderr": completed.stderr}
    return OutcomeScore(completed.returncode == 0 and details.get("passed") is True, completed.returncode, details)


def evaluate_process(task: dict, events: list[AgentEvent], trial_status: str = "COMPLETE") -> ProcessScore:
    if trial_status in {"ABORTED_INFRASTRUCTURE", "INVALID_EVIDENCE"}:
        return ProcessScore(False, [], infrastructure_failure=True)
    ledger = build_constraint_ledger(task, events)
    violations = [x.constraint_id for x in ledger if x.status == "violated"]
    return ProcessScore(not violations, violations, infrastructure_failure=False)


def clean_success(outcome: OutcomeScore, process: ProcessScore) -> bool:
    return bool(outcome.passed and process.passed and not process.infrastructure_failure)
