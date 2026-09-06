from inverted.harvest_d.d3_cases import generate_d3_cases
from inverted.harvest_d.hd_next2.ingredients import (
    INITIAL_IDS,
    SemanticIngredient,
    extract_ingredient_payload,
    initial_ingredient_registry,
)


class _Case:
    def __init__(self, d3_information):
        self.metadata = {"d3_information": d3_information}


def test_initial_registry_has_exactly_40_distinct_semantic_families():
    registry = initial_ingredient_registry()

    assert len(registry) == 40
    assert len(set(registry)) == 40
    assert {"OBJECTIVE", "CANONICAL_STATE", "EVIDENCE_PROVENANCE", "DEPENDENCIES", "RECOVERY_OPTIONS", "EDGE_CASES"} <= set(registry)
    assert tuple(registry) == INITIAL_IDS
    assert all(isinstance(ingredient, SemanticIngredient) for ingredient in registry.values())


def test_core_and_full_payloads_are_semantically_distinct():
    case = generate_d3_cases(partition="development", seed=20260921, per_family=1)[0]

    core = extract_ingredient_payload(case, "CANONICAL_STATE", "CORE")
    full = extract_ingredient_payload(case, "CANONICAL_STATE", "FULL")

    assert core is not None
    assert full is not None
    assert core.semantic_atoms < full.semantic_atoms
    assert core.payload != full.payload


def test_payload_lineage_identifies_public_source_and_deterministic_transform():
    case = generate_d3_cases(partition="development", seed=20260921, per_family=1)[0]

    payload = extract_ingredient_payload(case, "OBJECTIVE", "CORE")

    assert payload is not None
    assert payload.source_lineage == (
        "metadata:d3_information:I1.objective",
        "transform:select:objective",
        "dose:CORE",
    )


def test_inapplicable_ingredient_returns_none_without_fabricated_content():
    case = generate_d3_cases(partition="development", seed=20260921, per_family=1)[0]

    assert extract_ingredient_payload(case, "EDGE_CASES", "CORE") is None


def test_agreeing_evidence_is_not_labeled_as_contradiction():
    case = _Case({"I4": {"deterministic_verifier": "PASS", "model_claim": "PASS"}})

    assert extract_ingredient_payload(case, "EVIDENCE_CONTRADICTION", "CORE") is None


def test_contradiction_requires_disagreeing_comparable_claims():
    case = _Case({"I4": {"deterministic_verifier": "FAIL", "model_claim": "PASS"}})

    payload = extract_ingredient_payload(case, "EVIDENCE_CONTRADICTION", "CORE")

    assert payload is not None
    assert payload.semantic_atoms == frozenset({"I4.deterministic_verifier"})


def test_recovery_state_substring_does_not_create_failure_mode():
    case = _Case({"I9": {"previous_verified": "failure had no external effect", "recovery_state": "REPLAN_ALLOWED"}})

    assert extract_ingredient_payload(case, "LIKELY_FAILURE_MODE", "CORE") is None


def test_explicit_failure_mode_is_extracted_from_visible_content():
    case = _Case({"I9": {"failure_mode": "STALE_PLAN", "recovery_state": "REPLAN_ALLOWED"}})

    payload = extract_ingredient_payload(case, "LIKELY_FAILURE_MODE", "CORE")

    assert payload is not None
    assert payload.semantic_atoms == frozenset({"I9.failure_mode"})
    assert payload.source_lineage == (
        "metadata:d3_information:I9.failure_mode",
        "transform:select:likely_failure_mode",
        "dose:CORE",
    )


def test_tool_constraints_have_truthful_case_specific_extraction():
    case = _Case({
        "I3": {"scope": ["res-123"], "lease_state": "VALID"},
        "I6": {"tool_use": "read_only", "tool_target": "approved"},
    })

    payload = extract_ingredient_payload(case, "TOOL_CONSTRAINTS", "CORE")

    assert payload is not None
    assert payload.semantic_atoms == frozenset({"I6.tool_use"})
    assert payload.source_lineage == (
        "metadata:d3_information:I6.tool_use",
        "transform:select:tool_constraints",
        "dose:CORE",
    )


def test_lineage_contains_only_selected_source_atoms():
    case = _Case({"I1": {"objective": "do work", "subgoal": "verify result"}})

    payload = extract_ingredient_payload(case, "OBJECTIVE", "CORE")

    assert payload is not None
    assert payload.source_lineage == (
        "metadata:d3_information:I1.objective",
        "transform:select:objective",
        "dose:CORE",
    )
