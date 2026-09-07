from __future__ import annotations

import re

from .contracts import CriticalDivergence, MechanismCandidate, ReplayResult

FORBIDDEN_LITERAL_RE = re.compile(r"brain2-|ANS_[0-9a-f]+|gold\.json|verify/verify\.py", re.I)


def extract_candidate(divergence: CriticalDivergence, replay_results: list[ReplayResult]) -> MechanismCandidate:
    removals = [r for r in replay_results if "remove" in r.intervention_id]
    forces = [r for r in replay_results if "force" in r.intervention_id or "replace" in r.intervention_id]
    necessary = any(r.effect <= 0.5 for r in removals)
    sufficient = any(r.effect >= 0.5 for r in forces)
    supported = necessary and sufficient
    replacement = divergence.candidate_behavior or "perform the evidence-supported alternative before committing"
    evidence = list(divergence.evidence)
    for replay in replay_results:
        evidence.extend(replay.evidence_ids)
    return MechanismCandidate(
        candidate_id=f"mechanism-{abs(hash((divergence.failure_class, replacement))) & 0xffffffff:08x}",
        trigger=f"when {divergence.failure_class} is detected at the first critical divergence",
        baseline_behavior=f"continue with {divergence.failure_class}",
        replacement_behavior=replacement,
        evidence_ids=evidence,
        scope=[divergence.failure_class],
        cost={"extra_steps": 1.0 if "teacher:" in replacement else 0.0},
        counterevidence=[],
        status="causally_supported" if supported else "proposed",
    )


def validate_candidate(candidate: MechanismCandidate) -> list[str]:
    problems: list[str] = []
    joined = "\n".join([candidate.trigger, candidate.baseline_behavior, candidate.replacement_behavior, *candidate.scope])
    if FORBIDDEN_LITERAL_RE.search(joined):
        problems.append("benchmark_encoding")
    if len(candidate.replacement_behavior) > 500:
        problems.append("replacement_too_large")
    if "trajectory" in candidate.replacement_behavior.lower() and len(candidate.replacement_behavior.splitlines()) > 4:
        problems.append("teacher_trajectory_copy")
    if not candidate.evidence_ids:
        problems.append("missing_evidence")
    if not candidate.trigger.strip() or not candidate.replacement_behavior.strip():
        problems.append("missing_mechanism_fields")
    return problems
