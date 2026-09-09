from __future__ import annotations

import pytest

from inverted.capability_ratchet.compilation_core import (
    COMPILATION_KIND_ORDER,
    CompilationCandidate,
    CompilationDisposition,
    CompilationKind,
    CompilationPolicy,
)
from inverted.capability_ratchet.compilation_planner import CompilationPlanner
from inverted.capability_ratchet.core import Partition
from inverted.capability_ratchet.mutation_core import GeneralizationClass


def _exclusions_before(kind: CompilationKind, *, omit: CompilationKind | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for candidate_kind in COMPILATION_KIND_ORDER:
        if candidate_kind is kind:
            break
        if candidate_kind is omit:
            continue
        result[candidate_kind.value] = f"canonical evidence rules out {candidate_kind.value}"
    return result


def _candidate(
    *kinds: CompilationKind,
    exclusions: dict[str, str] | None = None,
    surface: str | None = None,
    tomography: str | None = "assessment-1",
    model_internal: bool = False,
) -> CompilationCandidate:
    return CompilationCandidate.create(
        failure_snapshot_id="failure-1",
        mechanism_id="mechanism-1",
        generalization_profile_id="profile-1",
        prior_generalized_evidence_ref=None,
        generalization_class=GeneralizationClass.REGION_MECHANISM,
        mechanism_label_ids=("label-1",),
        evidence_refs=("result-1", "profile-1"),
        source_hashes={"profile-1": "a" * 64},
        supported_kinds=tuple(kinds),
        excluded_cheaper_kinds={} if exclusions is None else exclusions,
        trigger_contract={"tool_eligible": True},
        compiled_payload={"policy": "synthetic"},
        verifier_contract={"postcondition": "pass"},
        negative_transfer_boundary=("direct-solved region",),
        tested_region="synthetic region",
        rollback_action="DISABLE",
        partition=Partition.HISTORICAL,
        operating_surface_profile_id=surface,
        tomography_assessment_id=tomography,
        model_internal_residual=model_internal,
    )


def test_deterministic_rule_beats_tool_when_both_are_supported() -> None:
    planner = CompilationPlanner()
    plan = planner.plan(
        _candidate(CompilationKind.TOOL_POLICY, CompilationKind.DETERMINISTIC_RULE)
    )
    assert plan.selected_kind is CompilationKind.DETERMINISTIC_RULE
    assert plan.expected_disposition is CompilationDisposition.COMPILED
    assert plan.projected_model_calls == 0


def test_state_representation_beats_skill_when_deterministic_is_ruled_out() -> None:
    planner = CompilationPlanner()
    plan = planner.plan(
        _candidate(
            CompilationKind.SKILL_POLICY,
            CompilationKind.STATE_REPRESENTATION,
            exclusions=_exclusions_before(CompilationKind.STATE_REPRESENTATION),
        )
    )
    assert plan.selected_kind is CompilationKind.STATE_REPRESENTATION
    assert tuple(plan.rejected_cheaper_kinds) == (CompilationKind.DETERMINISTIC_RULE.value,)


def test_tool_policy_requires_explicit_exclusion_of_every_cheaper_owner() -> None:
    planner = CompilationPlanner()
    tool = CompilationKind.TOOL_POLICY
    valid = _candidate(tool, exclusions=_exclusions_before(tool))
    assert planner.plan(valid).selected_kind is tool

    missing = _candidate(
        tool,
        exclusions=_exclusions_before(tool, omit=CompilationKind.STATE_REPRESENTATION),
    )
    with pytest.raises(ValueError, match="cheaper|STATE_REPRESENTATION"):
        planner.plan(missing)


def test_planner_ignores_exclusion_for_a_supported_cheaper_owner_and_selects_it() -> None:
    planner = CompilationPlanner()
    candidate = _candidate(
        CompilationKind.TOOL_POLICY,
        CompilationKind.FORMATTER_PARSER_VALIDATOR,
        exclusions={
            CompilationKind.DETERMINISTIC_RULE.value: "ruled out",
            CompilationKind.STATE_REPRESENTATION.value: "ruled out",
            CompilationKind.FORMATTER_PARSER_VALIDATOR.value: "stale exclusion",
        },
    )
    plan = planner.plan(candidate)
    assert plan.selected_kind is CompilationKind.FORMATTER_PARSER_VALIDATOR
    assert CompilationKind.FORMATTER_PARSER_VALIDATOR.value not in plan.rejected_cheaper_kinds


def test_reasoning_policy_requires_operating_surface_evidence() -> None:
    planner = CompilationPlanner()
    kind = CompilationKind.REASONING_POLICY
    no_surface = _candidate(kind, exclusions=_exclusions_before(kind), surface=None)
    with pytest.raises(ValueError, match="operating.surface|surface"):
        planner.plan(no_surface)

    with_surface = _candidate(
        kind,
        exclusions=_exclusions_before(kind),
        surface="surface-profile-1",
    )
    assert planner.plan(with_surface).selected_kind is kind


def test_fine_tune_requires_model_internal_residual_and_stage7_assessment() -> None:
    planner = CompilationPlanner()
    kind = CompilationKind.FINE_TUNE_CANDIDATE
    exclusions = _exclusions_before(kind)

    with pytest.raises(ValueError, match="model.internal|residual"):
        planner.plan(_candidate(kind, exclusions=exclusions, model_internal=False))

    with pytest.raises(ValueError, match="tomography|Stage-7"):
        planner.plan(
            _candidate(
                kind,
                exclusions=exclusions,
                model_internal=True,
                tomography=None,
            )
        )

    plan = planner.plan(
        _candidate(
            kind,
            exclusions=exclusions,
            model_internal=True,
            tomography="assessment-model-limit",
        )
    )
    assert plan.expected_disposition is CompilationDisposition.FINE_TUNE_CANDIDATE


def test_escalation_and_safe_stop_keep_distinct_terminal_handoffs() -> None:
    planner = CompilationPlanner()

    escalation = CompilationKind.ESCALATION_POLICY
    escalation_plan = planner.plan(
        _candidate(
            escalation,
            exclusions=_exclusions_before(escalation),
            model_internal=True,
        )
    )
    assert escalation_plan.expected_disposition is CompilationDisposition.ESCALATION_CANDIDATE

    safe_stop = CompilationKind.SAFE_STOP_BOUNDARY
    safe_stop_plan = planner.plan(
        _candidate(
            safe_stop,
            exclusions=_exclusions_before(safe_stop),
            model_internal=True,
        )
    )
    assert safe_stop_plan.expected_disposition is CompilationDisposition.SAFE_STOP_BOUNDARY


def test_planning_is_deterministic_zero_call_and_does_not_mutate_candidate() -> None:
    planner = CompilationPlanner(CompilationPolicy())
    candidate = _candidate(
        CompilationKind.TOOL_POLICY,
        exclusions=_exclusions_before(CompilationKind.TOOL_POLICY),
    )
    first = planner.plan(candidate)
    second = planner.plan(candidate)
    assert first == second
    assert first.plan_id == second.plan_id
    assert first.projected_model_calls == 0
    assert candidate.supported_kinds == (CompilationKind.TOOL_POLICY,)
