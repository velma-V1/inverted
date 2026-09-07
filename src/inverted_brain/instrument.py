from __future__ import annotations

import json
from pathlib import Path

from .contracts import AgentEvent, TrialResult

LABEL = "INSTRUMENT VALIDATION — NOT BRAIN EVIDENCE"


class MockInstrumentAdapter:
    def __init__(self, arm: str, mode: str = "baseline", addendum: str | None = None):
        self.arm = arm
        self.mode = mode
        self.addendum = addendum

    def _should_pass(self, task: dict) -> bool:
        if self.mode in {"teacher", "candidate", "forced"}:
            return True
        if self.mode == "removed":
            return False
        return int(task["seed"]) % 4 == 0

    @staticmethod
    def _apply_gold(task: dict, workspace: Path) -> None:
        gold = json.loads((Path(task["_task_root"]) / "verify" / "gold.json").read_text(encoding="utf-8"))
        for rel, content in gold["expected_files"].items():
            path = Path(workspace) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def run(self, workspace, task, evidence_dir, seed=None):
        passed = self._should_pass(task)
        if passed:
            self._apply_gold(task, Path(workspace))
        events = [
            AgentEvent(0, "dependency_inspection" if passed else "mutation", self.arm, {"mock":True}, source_id=f"{self.arm}-0"),
            AgentEvent(1, "verification" if passed else "failure", self.arm, {"mock":True}, source_id=f"{self.arm}-1"),
        ]
        return TrialResult(
            trial_id=task["id"], arm=self.arm, status="COMPLETE",
            outcome_passed=passed, process_passed=True, events=events,
            workspace=str(workspace), metadata={"grammar":task["grammar"],"instrument_label":LABEL},
        )

    def normalize_evidence(self, evidence_dir):
        return []

    def run_intervention(self, workspace, task, intervention, seed):
        mode = "removed" if intervention.kind == "remove" and self.mode == "teacher" else "forced"
        adapter = MockInstrumentAdapter(self.arm, mode=mode)
        return adapter.run(workspace, task, Path(workspace).parent / "mock_intervention", seed)


def instrument_adapters():
    return {
        "qwen": MockInstrumentAdapter("QWEN_BRAIN", "baseline"),
        "claude": MockInstrumentAdapter("CLAUDE_RAW", "teacher"),
        "codex": MockInstrumentAdapter("CODEX_RAW", "teacher"),
        "candidate_factory": lambda addendum: MockInstrumentAdapter("QWEN_BRAIN_CANDIDATE", "candidate", addendum),
    }
