import pytest

from inverted.system_harvest.escalation import (
    REQUIRED_ESCALATION_SECTIONS,
    EscalationCapsuleError,
    SnapshotSection,
    SnapshotSectionStatus,
    build_escalation_capsule,
    verify_escalation_capsule,
)


def _sections():
    return tuple(
        SnapshotSection(name, SnapshotSectionStatus.CAPTURED, {"value": name}, (f"ev:{name}",), None)
        for name in REQUIRED_ESCALATION_SECTIONS
    )


def test_capsule_requires_complete_reconstructable_failure_boundary():
    capsule = build_escalation_capsule(
        campaign_id="C", system_id="S", example_id="E", escalation_level=1,
        source_model_id="qwen", failure_event_id="ev:failure", sections=_sections(),
    )
    assert capsule.resume_mode == "CONTINUE_FROM_FAILURE_BOUNDARY"
    assert capsule.sections[0].name in REQUIRED_ESCALATION_SECTIONS
    assert verify_escalation_capsule(capsule) is True


def test_capsule_rejects_missing_required_section():
    with pytest.raises(EscalationCapsuleError, match="missing required escalation sections"):
        build_escalation_capsule(
            campaign_id="C", system_id="S", example_id="E", escalation_level=1,
            source_model_id="qwen", failure_event_id="ev:failure", sections=_sections()[:-1],
        )


def test_inaccessible_section_requires_reason_and_lineage():
    broken = list(_sections())
    broken[0] = SnapshotSection(
        broken[0].name, SnapshotSectionStatus.INACCESSIBLE, None, (), None
    )
    with pytest.raises(EscalationCapsuleError, match="INACCESSIBLE"):
        build_escalation_capsule(
            campaign_id="C", system_id="S", example_id="E", escalation_level=1,
            source_model_id="qwen", failure_event_id="ev:failure", sections=tuple(broken),
        )


def test_capsule_preserves_failure_frontier_sections_needed_for_resume():
    names = set(REQUIRED_ESCALATION_SECTIONS)
    assert {
        "ORIGINAL_INSTRUCTIONS", "ACTIVE_INGREDIENTS", "MODEL_VISIBLE_CONTEXT",
        "SYSTEM_VISIBLE_STATE", "ENVIRONMENT_STATE", "FILESYSTEM_STATE", "GIT_STATE",
        "PROCESS_STATE", "PRE_FAILURE_STATE", "FAILING_ACTION", "RAW_FAILURE_RESULT",
        "POST_FAILURE_STATE", "PENDING_WORK", "EVENT_LINEAGE",
    }.issubset(names)


def test_recursive_escalation_links_to_parent_capsule_and_forbids_restart_semantics():
    first = build_escalation_capsule(
        campaign_id="C", system_id="S", example_id="E", escalation_level=1,
        source_model_id="qwen", failure_event_id="ev:f1", sections=_sections(),
    )
    second = build_escalation_capsule(
        campaign_id="C", system_id="S", example_id="E", escalation_level=2,
        source_model_id="frontier-1", failure_event_id="ev:f2", sections=_sections(),
        parent_capsule_id=first.capsule_id,
    )
    assert second.parent_capsule_id == first.capsule_id
    assert "continue" in second.continuation_directive.lower()
    assert "restart" in second.continuation_directive.lower()
    assert "unless" in second.continuation_directive.lower()


def test_second_level_capsule_requires_parent_linkage():
    with pytest.raises(EscalationCapsuleError, match="parent_capsule_id"):
        build_escalation_capsule(
            campaign_id="C", system_id="S", example_id="E", escalation_level=2,
            source_model_id="frontier-1", failure_event_id="ev:f2", sections=_sections(),
        )
