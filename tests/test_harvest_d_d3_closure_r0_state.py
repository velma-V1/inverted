from __future__ import annotations

import importlib
import importlib.util

from inverted.harvest_d.d3_closure_cases import generate_closure_cases
from inverted.harvest_d.d3_closure_treatment import ClosureTreatmentPlan, render_treatment


def _case():
    return generate_closure_cases("closure-development", seed=20260923, per_family=1)[0]


def _load_state_module():
    name = "inverted.harvest_d.d3_closure_r0_state"
    spec = importlib.util.find_spec(name)
    assert spec is not None, "R0 state/action-frontier module is missing"
    return importlib.import_module(name)


def test_treatment_exposure_records_channel_order_and_position_for_visible_fields():
    treatment_module = importlib.import_module("inverted.harvest_d.d3_closure_treatment")
    assert hasattr(treatment_module, "derive_treatment_exposure"), "treatment exposure derivation is missing"
    case = _case()
    rendered = render_treatment(
        case,
        ClosureTreatmentPlan(
            field_ids=("I1", "I2", "I4"),
            representation="TYPED_FIELDS",
            ordering="DEFAULT",
            amount="MODERATE",
            timing="UPFRONT",
            placement="TASK_CONTEXT",
            assistance=("A2",),
        ),
    )

    exposure = treatment_module.derive_treatment_exposure(rendered, case)
    components = {segment.component_id for segment in exposure.segments}

    assert {"I1", "I2", "I4", "A2"} <= components
    assert all(segment.channel in {"SYSTEM", "TASK", "ASSISTANCE"} for segment in exposure.segments)
    assert all(segment.order_index >= 0 for segment in exposure.segments)
    assert all(0.0 <= segment.position_fraction <= 1.0 for segment in exposure.segments)
    assert all(segment.byte_start <= segment.byte_end for segment in exposure.segments)
    assert exposure.exposure_id


def test_same_actual_outbound_treatment_has_stable_exposure_identity():
    treatment_module = importlib.import_module("inverted.harvest_d.d3_closure_treatment")
    assert hasattr(treatment_module, "derive_treatment_exposure")
    case = _case()
    plan = ClosureTreatmentPlan(field_ids=("I1", "I2", "I4"), placement="TASK_CONTEXT")

    first = treatment_module.derive_treatment_exposure(render_treatment(case, plan), case)
    second = treatment_module.derive_treatment_exposure(render_treatment(case, plan), case)

    assert first.exposure_id == second.exposure_id
    assert first.to_dict() == second.to_dict()


def test_pre_state_descriptor_is_stable_and_contains_architecture_routing_features():
    module = _load_state_module()
    case = _case()

    first = module.derive_pre_state(case)
    second = module.derive_pre_state(case)

    assert first.pre_state_id == second.pre_state_id
    assert first.family == case.family
    assert isinstance(first.missing_evidence, tuple)
    assert isinstance(first.dependency_depth, int)
    assert first.dependency_depth >= 0
    assert first.pre_state_id


def test_action_frontier_distinguishes_candidates_from_admissible_actions_and_is_stable():
    module = _load_state_module()
    case = _case()

    first = module.derive_action_frontier(case)
    second = module.derive_action_frontier(case)

    assert first.frontier_id == second.frontier_id
    assert first.action_count == len(first.admissible_actions)
    assert first.candidate_count == len(first.candidate_actions)
    assert first.frontier_id
    assert first.to_dict() == second.to_dict()
