from inverted.harvest_d.d3_analysis import (
    ScoreSummary,
    SupportPoint,
    build_claim_graph,
    build_coverage_matrix,
    build_recovery_maps,
    classify_failure,
    find_mrs,
    find_msip,
)
from inverted.harvest_d.d3_recovery import trajectory
from inverted.harvest_d.types import SequentialDecision


def test_answer_correct_disposition_wrong_is_its_own_failure_class():
    score = ScoreSummary(answer_correct=True, disposition_correct=False, semantic_correct=True)
    assert classify_failure(score) == "ANSWER_RIGHT_DISPOSITION_WRONG"


def test_recovery_migration_is_not_counted_as_recovery_success():
    summary = build_recovery_maps([
        trajectory(local_recovered=True, global_invariant_ok=False),
        trajectory(local_recovered=True, global_invariant_ok=True),
    ])
    assert summary["recovered_without_migration"] == 1
    assert summary["migrated"] == 1


def test_msip_removes_fields_that_do_not_pay_complexity_rent():
    result = find_msip(
        packet="I1+I2+I3",
        ablations={
            "I3": SequentialDecision.NONINFERIOR,
            "I2": SequentialDecision.HARMFUL,
            "I1": SequentialDecision.HARMFUL,
        },
    )
    assert result.required_fields == ("I1", "I2")
    assert result.removed_fields == ("I3",)


def test_mrs_prefers_least_involved_safe_noninferior_configuration():
    result = find_mrs([
        SupportPoint("heavy", involvement=5.0, decision=SequentialDecision.SUPERIOR, safe=True),
        SupportPoint("light", involvement=1.0, decision=SequentialDecision.NONINFERIOR, safe=True),
        SupportPoint("unsafe", involvement=0.0, decision=SequentialDecision.SUPERIOR, safe=False),
    ])
    assert result.name == "light"


def test_coverage_matrix_preserves_important_unresolved_cells():
    matrix = build_coverage_matrix([
        {"cell": "I1xA2", "status": "TESTED"},
        {"cell": "I7xA9", "status": "IMPORTANT_UNRESOLVED"},
    ])
    assert matrix["I7xA9"] == "IMPORTANT_UNRESOLVED"


def test_claim_graph_links_support_and_contradiction_evidence():
    graph = build_claim_graph([
        {
            "claim_id": "c1",
            "statement": "A2 helps on scope failures",
            "supporting_call_ids": ["call-1", "call-2"],
            "contradictory_call_ids": ["call-3"],
            "state": "CAUSALLY_VERIFIED",
        }
    ])
    assert graph["claims"][0]["claim_id"] == "c1"
    edge_kinds = {edge["kind"] for edge in graph["edges"]}
    assert edge_kinds == {"SUPPORTS", "CONTRADICTS"}
