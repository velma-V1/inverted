from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .contracts import InterventionSpec, ReplayResult


def replay_from_snapshot(task: dict, snapshot: Path, intervention: InterventionSpec, adapter, repetitions: int = 3, seed: int = 0) -> ReplayResult:
    passes = 0
    evidence_ids: list[str] = []
    for rep in range(repetitions):
        with tempfile.TemporaryDirectory(prefix="brain-replay-") as temp:
            workspace = Path(temp) / "workspace"
            shutil.copytree(Path(snapshot), workspace)
            result = adapter.run_intervention(
                workspace=workspace,
                task=task,
                intervention=intervention,
                seed=seed + rep,
            )
            passed = bool(result.outcome_passed and result.process_passed and result.status == "COMPLETE")
            passes += int(passed)
            evidence_ids.append(f"{intervention.intervention_id}:{rep}:{result.status}:{int(passed)}")
    failures = repetitions - passes
    return ReplayResult(
        intervention_id=intervention.intervention_id,
        repetitions=repetitions,
        passes=passes,
        failures=failures,
        effect=(passes / repetitions) if repetitions else 0.0,
        evidence_ids=evidence_ids,
    )


def causal_support(baseline: ReplayResult, intervention: ReplayResult, minimum_effect: float = 0.34) -> bool:
    return intervention.effect - baseline.effect >= minimum_effect
