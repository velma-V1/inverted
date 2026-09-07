from __future__ import annotations

import hashlib

from .contracts import LearnedArtifact, LearningDestination, MechanismCandidate


DESTINATIONS = {
    "reasoning_policy": LearningDestination.BRAIN,
    "invariant": LearningDestination.SYSTEM,
    "governance_rule": LearningDestination.SYSTEM,
    "repeatable_procedure": LearningDestination.SKILL,
    "executable_capability": LearningDestination.TOOL_HAND,
    "durable_fact": LearningDestination.MEMORY,
    "failed_mechanism": LearningDestination.NEGATIVE_EVIDENCE,
}

POSITIVE_DESTINATIONS = {
    LearningDestination.BRAIN,
    LearningDestination.SYSTEM,
    LearningDestination.SKILL,
    LearningDestination.TOOL_HAND,
    LearningDestination.MEMORY,
}

PROMOTED_STATUSES = {"retained", "bounded"}


def _artifact_id(candidate: MechanismCandidate, kind: str) -> str:
    raw = f"{candidate.candidate_id}\n{kind}\n{candidate.replacement_behavior}"
    return "learned-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compile_finding(
    candidate: MechanismCandidate,
    finding_kind: str,
    provenance: list[str],
    boundary_conditions: list[str],
    failure_modes: list[str],
    verification: list[str],
) -> LearnedArtifact:
    if finding_kind not in DESTINATIONS:
        raise ValueError(f"unsupported finding kind: {finding_kind}")
    if not candidate.evidence_ids:
        raise ValueError("learning artifact requires evidence")
    if not provenance:
        raise ValueError("learning artifact requires provenance")

    destination = DESTINATIONS[finding_kind]
    if destination in POSITIVE_DESTINATIONS:
        if candidate.status not in PROMOTED_STATUSES:
            raise ValueError("positive learning requires retained or bounded candidate")
        if not boundary_conditions:
            raise ValueError("positive learning requires boundary conditions")
        if not failure_modes:
            raise ValueError("positive learning requires known failure modes")
        if not verification:
            raise ValueError("positive learning requires verification obligations")
    elif candidate.status != "rejected":
        raise ValueError("negative evidence requires rejected candidate")

    content = candidate.replacement_behavior
    if destination is LearningDestination.NEGATIVE_EVIDENCE:
        content = candidate.baseline_behavior + " -> " + candidate.replacement_behavior

    return LearnedArtifact(
        artifact_id=_artifact_id(candidate, finding_kind),
        source_candidate_id=candidate.candidate_id,
        destination=destination,
        artifact_kind=finding_kind,
        trigger=candidate.trigger,
        content=content,
        evidence_ids=list(candidate.evidence_ids),
        scope=list(candidate.scope),
        boundary_conditions=list(boundary_conditions),
        failure_modes=list(failure_modes),
        counterevidence=list(candidate.counterevidence),
        verification=list(verification),
        provenance=list(provenance),
        source_status=candidate.status,
        cost=dict(candidate.cost),
    )
