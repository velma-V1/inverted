from __future__ import annotations

from itertools import combinations

from inverted.harvest_d.d3_closure_covering import (
    CoveringRequirement,
    generate_covering_design,
    measure_pairwise_coverage,
)
from inverted.harvest_d.d3_closure_search_space import (
    build_primary_search_space,
    treatment_equivalence_key,
)


def test_primary_search_space_is_derived_and_exposes_large_combinatorial_claim_space():
    space = build_primary_search_space()

    assert len(space.content_fields) == 10
    assert len(space.representations) == 10
    assert len(space.orderings) >= 6
    assert len(space.amounts) == 5
    assert len(space.timings) >= 4
    assert len(space.placements) >= 2
    assert len(space.assistance_factors) == 4

    expected = (
        (2 ** len(space.content_fields) - 1)
        * len(space.representations)
        * len(space.orderings)
        * len(space.amounts)
        * len(space.timings)
        * len(space.placements)
        * (2 ** len(space.assistance_factors))
    )
    assert space.raw_theoretical_candidate_count == expected
    assert space.raw_theoretical_candidate_count > 50_000_000


def test_equivalence_key_collapses_different_labels_when_model_visible_treatment_is_identical():
    a = treatment_equivalence_key(
        semantic_field_hash="sem",
        rendered_hash="rendered",
        system_message_hash="sys",
        user_message_hash="usr",
        field_order=("I1", "I2"),
        assistance_hash="assist",
    )
    b = treatment_equivalence_key(
        semantic_field_hash="sem",
        rendered_hash="rendered",
        system_message_hash="sys",
        user_message_hash="usr",
        field_order=("I1", "I2"),
        assistance_hash="assist",
    )
    assert a == b


def _all_pairs_covered(rows: tuple[dict[str, str], ...], factors: dict[str, tuple[str, ...]]) -> bool:
    for left, right in combinations(factors, 2):
        observed = {(row[left], row[right]) for row in rows}
        expected = {(lv, rv) for lv in factors[left] for rv in factors[right]}
        if observed != expected:
            return False
    return True


def test_mixed_level_covering_design_covers_every_coverable_two_way_pair_without_cartesian_execution():
    factors = {
        "representation": ("TYPED", "JSON", "LEDGER"),
        "amount": ("MIN", "FULL"),
        "timing": ("UPFRONT", "JIT"),
        "a2": ("OFF", "TARGET"),
    }
    design = generate_covering_design(factors, seed=20260903)

    assert _all_pairs_covered(design.rows, factors)
    assert len(design.rows) < 3 * 2 * 2 * 2
    coverage = measure_pairwise_coverage(design.rows, factors)
    assert coverage.coverable_pairs > 0
    assert coverage.covered_pairs == coverage.coverable_pairs
    assert coverage.ratio == 1.0


def test_covering_design_is_deterministic_and_can_require_targeted_three_way_tuple():
    factors = {
        "content": ("I2", "I4"),
        "model": ("SMALL_A", "QWEN"),
        "amount": ("MIN", "FULL"),
    }
    requirement = CoveringRequirement(
        factors=("content", "model", "amount"),
        levels=("I4", "QWEN", "FULL"),
    )
    first = generate_covering_design(factors, seed=17, required_tuples=(requirement,))
    second = generate_covering_design(factors, seed=17, required_tuples=(requirement,))

    assert first.rows == second.rows
    assert any(
        row["content"] == "I4" and row["model"] == "QWEN" and row["amount"] == "FULL"
        for row in first.rows
    )
