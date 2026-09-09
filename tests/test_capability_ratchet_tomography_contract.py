from __future__ import annotations

import inverted.capability_ratchet as capability_ratchet
from inverted.capability_ratchet.tomography_core import TomographyAxis, TomographyDisposition


def test_tomography_axes_match_corrected_stage7_spec_exactly() -> None:
    assert {item.value for item in TomographyAxis} == {
        "TOOL_AVAILABILITY",
        "TOOL_SELECTION",
        "TOOL_ARGUMENTS",
        "TOOL_EXECUTION_RESULT",
        "TOOL_RESULT_INTERPRETATION",
        "VERIFIER_VISIBILITY",
        "VERIFIER_FEEDBACK",
        "TARGETED_RECOVERY",
        "GENERIC_RETRY_CONTROL",
        "SKILL_PROCEDURE",
        "SKILL_TRIGGER",
        "ESCALATION_REFERENCE",
    }


def test_tomography_dispositions_match_corrected_stage7_spec_exactly() -> None:
    assert {item.value for item in TomographyDisposition} == {
        "TOOL_REQUIRED",
        "TOOL_SELECTION_DEFICIT",
        "TOOL_ARGUMENT_DEFICIT",
        "TOOL_EXECUTION_FAILURE",
        "TOOL_INTERPRETATION_DEFICIT",
        "VERIFIER_SUFFICIENT",
        "RECOVERY_SUFFICIENT",
        "SKILL_CANDIDATE",
        "MODEL_INTERNAL_RESIDUAL",
        "ESCALATION_CANDIDATE",
        "SAFE_STOP_BOUNDARY",
        "UNRESOLVED",
    }


def test_primary_tomography_records_are_public_contracts() -> None:
    for name in (
        "TomographyProbeSpec",
        "TomographyStudy",
        "TomographyOutcome",
        "TomographyAssessment",
        "TomographyPolicy",
    ):
        assert hasattr(capability_ratchet, name), name
        assert name in capability_ratchet.__all__


def test_tomography_disposition_cannot_encode_promotion_or_certification() -> None:
    values = {item.value for item in TomographyDisposition}
    forbidden_fragments = ("CERT", "MOVEMENT", "TIER_CANDIDATE", "PROMOTION")
    assert not any(fragment in value for value in values for fragment in forbidden_fragments)
