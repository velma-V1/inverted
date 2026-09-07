import pytest

from inverted_brain.contracts import (
    LearnedArtifact,
    LearningDestination,
    MechanismCandidate,
)
from inverted_brain.learning_compiler import compile_finding


def candidate(status="retained"):
    return MechanismCandidate(
        "m1",
        "when repeated failed reasoning is observed",
        "continue the same reasoning frame",
        "change representation before continuing",
        ["replay:1", "holdout:2"],
        ["debugging"],
        {"extra_steps": 1.0},
        ["no benefit on trivial tasks"],
        status=status,
    )


def test_learning_destinations_are_explicit_and_stable():
    assert [x.value for x in LearningDestination] == [
        "BRAIN", "SYSTEM", "SKILL", "TOOL_HAND", "MEMORY", "NEGATIVE_EVIDENCE"
    ]
    artifact = LearnedArtifact(
        "a", "m1", LearningDestination.BRAIN, "rule", "trigger", "content",
        ["e"], ["scope"], ["boundary"], ["failure"], ["counter"],
        ["verify"], ["source"], "retained", {}
    )
    assert artifact.destination is LearningDestination.BRAIN
    assert artifact.source_candidate_id == "m1"
    assert artifact.counterevidence == ["counter"]


@pytest.mark.parametrize(
    ("kind", "destination"),
    [
        ("reasoning_policy", LearningDestination.BRAIN),
        ("invariant", LearningDestination.SYSTEM),
        ("governance_rule", LearningDestination.SYSTEM),
        ("repeatable_procedure", LearningDestination.SKILL),
        ("executable_capability", LearningDestination.TOOL_HAND),
        ("durable_fact", LearningDestination.MEMORY),
        ("failed_mechanism", LearningDestination.NEGATIVE_EVIDENCE),
    ],
)
def test_compile_finding_routes_to_correct_layer(kind, destination):
    status = "rejected" if kind == "failed_mechanism" else "retained"
    artifact = compile_finding(
        candidate(status=status), finding_kind=kind,
        provenance=["Codex", "Weinberg"],
        boundary_conditions=["only after contradictory evidence"],
        failure_modes=["unnecessary on trivial tasks"],
        verification=["fresh holdout", "independent verifier"],
    )
    assert artifact.destination is destination
    assert artifact.evidence_ids == ["replay:1", "holdout:2"]
    assert artifact.provenance == ["Codex", "Weinberg"]
    assert artifact.source_candidate_id == "m1"
    assert artifact.source_status == status
    assert artifact.counterevidence == ["no benefit on trivial tasks"]


def test_compile_finding_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unsupported finding kind"):
        compile_finding(
            candidate(), "mystery", ["source"], ["boundary"], ["failure"], ["verify"]
        )


def test_compile_finding_requires_evidence_and_provenance():
    empty_evidence = candidate()
    empty_evidence.evidence_ids = []
    with pytest.raises(ValueError, match="evidence"):
        compile_finding(
            empty_evidence, "reasoning_policy", ["source"], ["boundary"], ["failure"], ["verify"]
        )
    with pytest.raises(ValueError, match="provenance"):
        compile_finding(
            candidate(), "reasoning_policy", [], ["boundary"], ["failure"], ["verify"]
        )


def test_positive_learning_requires_retention_boundaries_failures_and_verification():
    with pytest.raises(ValueError, match="retained or bounded"):
        compile_finding(
            candidate(status="causally_supported"), "reasoning_policy",
            ["source"], ["boundary"], ["failure"], ["verify"]
        )
    with pytest.raises(ValueError, match="boundary"):
        compile_finding(candidate(), "reasoning_policy", ["source"], [], ["failure"], ["verify"])
    with pytest.raises(ValueError, match="failure modes"):
        compile_finding(candidate(), "reasoning_policy", ["source"], ["boundary"], [], ["verify"])
    with pytest.raises(ValueError, match="verification"):
        compile_finding(candidate(), "reasoning_policy", ["source"], ["boundary"], ["failure"], [])


def test_negative_evidence_requires_rejected_candidate_but_not_positive_promotion_fields():
    artifact = compile_finding(candidate(status="rejected"), "failed_mechanism", ["source"], [], [], [])
    assert artifact.destination is LearningDestination.NEGATIVE_EVIDENCE
    assert artifact.source_status == "rejected"
    with pytest.raises(ValueError, match="rejected candidate"):
        compile_finding(candidate(status="retained"), "failed_mechanism", ["source"], [], [], [])
