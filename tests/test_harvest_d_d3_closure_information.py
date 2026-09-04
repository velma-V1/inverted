from inverted.harvest_d.cases import HarvestCase, OracleKind, OracleSpec
from inverted.harvest_d.d3_closure_information import (
    ClosureAmount,
    ClosureInformationPlan,
    ClosureOrdering,
    render_closure_packet,
)
from inverted.harvest_d.types import Disposition


def _case() -> HarvestCase:
    return HarvestCase(
        "closure-c1",
        "STATE",
        "closure_state",
        2,
        "Choose the safe action.",
        Disposition.EXECUTE,
        OracleSpec(OracleKind.JSON_EQUALS, {"answer": "USE_CURRENT"}),
        {
            "d3_information": {
                "I1": {"objective": "use canonical state"},
                "I2": {"canonical_version": 7, "stale_version": 6},
                "I3": {"scope": ["res-1"]},
                "I4": {"required": ["receipt"], "available": ["receipt"], "missing": []},
                "I5": {"risk": "MEDIUM", "reversible": True},
                "I6": {"must_use_current": True},
                "I7": {"admissible_actions": ["USE_CURRENT", "USE_STALE"]},
                "I8": {"order": "STATE_BEFORE_ACTION"},
                "I9": {"previous_verified": "state loaded"},
                "I10": {"novelty": "LOW"},
            }
        },
    )


def test_amount_levels_render_distinct_burdens():
    case = _case()
    packets = [
        render_closure_packet(case, ClosureInformationPlan(amount=amount))
        for amount in ClosureAmount
    ]
    assert len({p.rendered_hash for p in packets}) == len(ClosureAmount)
    counts = {p.amount: p.approx_token_count for p in packets}
    assert counts[ClosureAmount.MINIMUM.value] < counts[ClosureAmount.FULL.value]
    assert counts[ClosureAmount.FULL.value] < counts[ClosureAmount.OVERLOADED.value]


def test_ordering_changes_order_without_changing_semantic_field_hash():
    case = _case()
    default = render_closure_packet(case, ClosureInformationPlan())
    evidence = render_closure_packet(case, ClosureInformationPlan(ordering=ClosureOrdering.EVIDENCE_FIRST))
    safety = render_closure_packet(case, ClosureInformationPlan(ordering=ClosureOrdering.SAFETY_STATE_EVIDENCE_FIRST))
    assert default.semantic_field_hash == evidence.semantic_field_hash == safety.semantic_field_hash
    assert evidence.field_order[0] == "I4"
    assert safety.field_order[:3] == ("I6", "I2", "I4")


def test_seeded_shuffle_is_real_and_reproducible():
    case = _case()
    a = render_closure_packet(case, ClosureInformationPlan(ordering=ClosureOrdering.SHUFFLED_CONTROL, shuffle_seed=77))
    b = render_closure_packet(case, ClosureInformationPlan(ordering=ClosureOrdering.SHUFFLED_CONTROL, shuffle_seed=77))
    default = render_closure_packet(case, ClosureInformationPlan())
    assert a.field_order == b.field_order
    assert a.field_order != default.field_order
    assert a.semantic_field_hash == default.semantic_field_hash
