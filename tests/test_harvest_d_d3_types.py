from inverted.harvest_d.d3_config import D3Phase
from inverted.harvest_d.d3_types import (
    AssistanceCondition,
    AssumptionRecord,
    CallCaptureStatus,
    D3Condition,
    D3Event,
    EvidenceAdmissibility,
    InformationField,
    InformationPacket,
    MissingnessReason,
    ProtocolViolation,
    RecoveryChoice,
    RecoveryStage,
    RecoveryTrajectory,
)
from inverted.harvest_d.types import Disposition


def test_missingness_is_reason_coded_not_ambiguous_null():
    assert MissingnessReason.NOT_APPLICABLE.value == "NOT_APPLICABLE"
    assert MissingnessReason.NOT_EXPOSED_BY_RUNTIME.value == "NOT_EXPOSED_BY_RUNTIME"
    assert MissingnessReason.CAPTURE_INCOMPLETE.value == "CAPTURE_INCOMPLETE"


def test_recovery_stages_are_independently_observable():
    assert [x.value for x in RecoveryStage] == [
        "DETECTION",
        "DIAGNOSIS",
        "SELECTION",
        "ADMISSION",
        "EXECUTION",
        "VERIFICATION",
    ]
    assert RecoveryChoice.RECONCILE.value == "RECONCILE"
    assert RecoveryChoice.SAFE_STOP.value == "SAFE_STOP"


def test_event_hashes_model_visible_and_system_known_information_separately():
    event = D3Event.for_test(
        model_visible={"state": 1},
        system_known={"state": 1, "hidden_oracle": 9},
    )
    assert event.model_visible_information_hash != event.system_known_information_hash
    assert event.sequence == 1
    assert event.event_id


def test_information_packet_preserves_raw_fields_and_rendered_payload():
    field = InformationField(
        field_id="I2",
        value={"version": 3},
        source_type="SYSTEM_CANONICAL",
        trust_class="SYSTEM_OWNED",
        model_visible=True,
    )
    packet = InformationPacket(
        packet_id="p1",
        fields=(field,),
        rendered='{"I2":{"version":3}}',
        representation="STRICT_JSON",
        timing="UPFRONT",
    )
    assert packet.fields[0].field_id == "I2"
    assert packet.model_visible_field_ids == ("I2",)


def test_condition_and_assistance_are_explicit_data_not_prompt_flags():
    condition = D3Condition("c1", D3Phase.INFORMATION, "TARGET", "development")
    assistance = AssistanceCondition("A2", "TARGET", reason="restrict to admissible actions")
    assert condition.phase is D3Phase.INFORMATION
    assert assistance.mode == "TARGET"


def test_capture_status_separates_diagnostic_from_promotion_admissible():
    incomplete = CallCaptureStatus("call-1", required_present=False)
    complete = CallCaptureStatus("call-2", required_present=True)
    assert incomplete.admissibility is EvidenceAdmissibility.DIAGNOSTIC_ONLY
    assert complete.admissibility is EvidenceAdmissibility.ADMISSIBLE


def test_recovery_trajectory_keeps_stage_records_and_final_migration_state():
    trajectory = RecoveryTrajectory(
        trajectory_id="r1",
        case_id="c1",
        stages=((RecoveryStage.DETECTION, "stale state"), (RecoveryStage.SELECTION, "RECONCILE")),
        final_state="MIGRATED",
    )
    assert trajectory.stage_value(RecoveryStage.SELECTION) == "RECONCILE"
    assert trajectory.migrated is True


def test_protocol_violation_and_assumption_records_preserve_admissibility_effects():
    violation = ProtocolViolation("v1", "wrong model digest", ("call-1",), "REJECTED")
    assumption = AssumptionRecord("a1", 1, "runtime deterministic", "CONTRADICTED", evidence_ids=("call-2",))
    assert violation.admissibility == "REJECTED"
    assert assumption.state == "CONTRADICTED"
