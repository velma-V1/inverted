from __future__ import annotations

from pathlib import Path

import pytest

from inverted.harvest_d.hd_next1_budget import HDNext1BudgetState
from inverted.harvest_d.hd_next1_cases import CONFIRMATION_FAMILY_MAP, describe_observable_stratum, generate_protected_case_pool
from inverted.harvest_d.hd_next1_config import load_hd_next1_config
from inverted.harvest_d.hd_next1_space import build_zero_call_design
from inverted.harvest_d.hd_next1_statistics import clopper_pearson_upper, noninferiority_family_decisions
from inverted.harvest_d.types import SequentialDecision


CONFIG = Path("configs/harvest-d-hd-next-1.json")


def test_config_freezes_approved_budget_and_scope():
    cfg = load_hd_next1_config(CONFIG)
    assert cfg["experiment_id"] == "HD-NEXT-1"
    assert cfg["max_calls"] == 672
    assert cfg["model_call_caps"] == {"SMALL_A": 576, "QWEN": 96}
    assert cfg["qwen_pools"] == {"calibration": 12, "development": 21, "confirmation": 63}
    assert cfg["effect_margin"] == 0.05
    assert cfg["blind_retries_allowed"] is False
    assert cfg["protected_pool_size"] == 63
    assert len(set(cfg["seeds"].values())) == 3


def test_exact_noninferiority_requires_real_confirmation_depth():
    assert clopper_pearson_upper(0, 36, 0.05) > 0.05
    assert clopper_pearson_upper(0, 63, 0.05) < 0.05
    assert noninferiority_family_decisions([0], [63], margin=0.05) == (SequentialDecision.NONINFERIOR,)
    assert noninferiority_family_decisions([0, 0], [32, 31], margin=0.05) == (
        SequentialDecision.UNRESOLVED,
        SequentialDecision.UNRESOLVED,
    )


def test_protected_pool_is_63_and_retains_f1_f9_coverage():
    cfg = load_hd_next1_config(CONFIG)
    pool = generate_protected_case_pool(cfg)
    assert len(pool) == 63
    assert {row.metadata["hd_next1_family_id"] for row in pool} == set(CONFIRMATION_FAMILY_MAP)
    assert {row.metadata["partition"] for row in pool} == {"hd-next1-fresh", "hd-next1-sealed"}
    descriptor = describe_observable_stratum(pool[0])
    assert {
        "family_id", "family", "evidence_missing", "risk", "irreversible",
        "invariant_sensitive", "dependency_depth", "action_space_size",
        "novelty", "boundary_exceeded", "recovery_state",
    } <= set(descriptor)


def test_zero_call_design_has_full_pairwise_plan_and_no_progressive_fake():
    cfg = load_hd_next1_config(CONFIG)
    design = build_zero_call_design(cfg)
    assert design.physical_model_calls == 0
    assert design.pairwise_coverage_ratio == 1.0
    assert design.required_three_way_coverage_ratio == 1.0
    assert "PROGRESSIVE" not in design.factor_levels["timing"]
    assert any(row["region"] == "PROGRESSIVE_REAL_MULTI_STEP_DELIVERY" for row in design.uncovered_regions)
    assert len(design.treatments) == len({row["treatment_id"] for row in design.treatments})


def test_qwen_development_cannot_borrow_confirmation_reserve():
    budget = HDNext1BudgetState.default(max_inference_seconds=100000.0)
    for _ in range(21):
        budget.reserve("QWEN", "development", expected_seconds=1.0)
    with pytest.raises(ValueError, match="development"):
        budget.reserve("QWEN", "development", expected_seconds=1.0)
    assert budget.remaining("QWEN", "confirmation") == 63
    assert budget.total_cap == 672
