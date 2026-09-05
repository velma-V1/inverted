from __future__ import annotations

from inverted.harvest_d.hd_next1_decisions import (
    compile_model_ownership,
    compile_negative_transfer,
    compile_support_component,
    router_is_promotable,
)


def test_small_a_owns_only_when_qwen_only_loss_bound_clears_margin():
    winner = compile_model_ownership(qwen_only_wins=0, matched_n=63)
    assert winner.state == "REDUNDANT"
    assert winner.action == "SMALL_A_OWNS"
    unresolved = compile_model_ownership(qwen_only_wins=1, matched_n=20)
    assert unresolved.state == "UNRESOLVED"
    assert unresolved.action == "RETAIN_BOUNDED_QWEN_ESCALATION"


def test_support_removal_and_negative_transfer_compile_mechanically():
    support = compile_support_component(component_id="I8", full_only_wins=0, matched_n=63)
    assert support.state == "REDUNDANT"
    assert support.action == "DELETE"
    harmful = compile_negative_transfer(extra_only_wins=0, minimal_only_wins=12, matched_n=100)
    assert harmful.state in {"HARMFUL", "UNRESOLVED"}


def test_router_requires_pre_outcome_fresh_and_sealed_confirmation():
    assert router_is_promotable(
        predicate_is_pre_outcome=True,
        frozen_before_confirmation=True,
        fresh_reproduced=True,
        sealed_reproduced=True,
        absolute_improvement=0.06,
        prevents_material_safety_regression=False,
    ) is True
    assert router_is_promotable(
        predicate_is_pre_outcome=False,
        frozen_before_confirmation=True,
        fresh_reproduced=True,
        sealed_reproduced=True,
        absolute_improvement=0.20,
        prevents_material_safety_regression=False,
    ) is False
