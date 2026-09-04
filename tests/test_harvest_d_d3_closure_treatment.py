from __future__ import annotations

import pytest

from inverted.harvest_d.d3_closure_cases import generate_closure_cases
from inverted.harvest_d.d3_closure_treatment import (
    ClosureTreatmentPlan,
    UnsupportedTreatment,
    render_treatment,
)


def _case():
    return generate_closure_cases("closure-development", seed=20260923, per_family=1)[0]


def test_content_subset_controls_semantics_while_amount_only_changes_burden_encoding():
    case = _case()
    common = dict(
        field_ids=("I1", "I2", "I4", "I7"),
        representation="TYPED_FIELDS",
        ordering="DEFAULT",
        timing="UPFRONT",
        placement="TASK_CONTEXT",
    )
    minimum = render_treatment(case, ClosureTreatmentPlan(amount="MINIMUM", **common))
    full = render_treatment(case, ClosureTreatmentPlan(amount="FULL", **common))

    assert minimum.semantic_field_hash == full.semantic_field_hash
    assert minimum.rendered_hash != full.rendered_hash
    assert minimum.approx_token_count < full.approx_token_count


def test_representation_and_order_change_delivery_not_semantic_field_set():
    case = _case()
    base = ClosureTreatmentPlan(
        field_ids=("I1", "I2", "I4", "I6", "I7"),
        amount="MODERATE",
        timing="UPFRONT",
        placement="TASK_CONTEXT",
    )
    typed = render_treatment(case, base.replace(representation="TYPED_FIELDS", ordering="DEFAULT"))
    ledger = render_treatment(case, base.replace(representation="MINIMAL_LEDGER", ordering="EVIDENCE_FIRST"))

    assert typed.semantic_field_hash == ledger.semantic_field_hash
    assert typed.rendered_hash != ledger.rendered_hash
    assert typed.field_order != ledger.field_order


def test_placement_changes_actual_outbound_channel_hashes():
    case = _case()
    base = ClosureTreatmentPlan(
        field_ids=("I1", "I2", "I4", "I7"),
        representation="STRICT_JSON",
        amount="MODERATE",
        ordering="DEFAULT",
        timing="UPFRONT",
    )
    user = render_treatment(case, base.replace(placement="TASK_CONTEXT"))
    system = render_treatment(case, base.replace(placement="SYSTEM_CONTEXT"))

    assert user.semantic_field_hash == system.semantic_field_hash
    assert user.system_message_hash != system.system_message_hash
    assert user.user_message_hash != system.user_message_hash


def test_a1_a4_assistance_is_model_visible_before_decision_and_part_of_treatment_identity():
    case = _case()
    without = render_treatment(case, ClosureTreatmentPlan(field_ids=("I1", "I2")))
    with_a2 = render_treatment(case, ClosureTreatmentPlan(field_ids=("I1", "I2"), assistance=("A2",)))

    assert without.assistance_hash != with_a2.assistance_hash
    assert "PREDECISION_ASSISTANCE" in with_a2.user_message


def test_progressive_is_rejected_until_it_is_a_real_multi_step_delivery_treatment():
    with pytest.raises(UnsupportedTreatment):
        render_treatment(_case(), ClosureTreatmentPlan(field_ids=("I1", "I2"), timing="PROGRESSIVE"))


def test_renderer_never_exposes_hidden_oracle_labels():
    rendered = render_treatment(_case(), ClosureTreatmentPlan(field_ids=tuple(f"I{i}" for i in range(1, 11))))
    visible = (rendered.system_message + "\n" + rendered.user_message).lower()
    assert "expected_disposition" not in visible
    assert "hidden_oracle" not in visible
