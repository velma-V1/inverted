from __future__ import annotations

import pytest

from inverted.harvest_d.hd_next1_cases import generate_protected_case_pool
from inverted.harvest_d.hd_next1_config import load_hd_next1_config
from inverted.harvest_d.hd_next1_randomization import (
    ProtectedEvidenceState,
    default_confirmation_resolution_policy,
    freeze_confirmation_resolution,
    freeze_protected_assignments,
)
from inverted.harvest_d.hd_next1_space import build_zero_call_design


CONFIG = "configs/harvest-d-hd-next-1.json"


def test_protected_assignment_manifest_is_deterministic_and_preserves_qwen_reserve():
    cfg = load_hd_next1_config(CONFIG)
    pool = generate_protected_case_pool(cfg)
    design = build_zero_call_design(cfg)
    policy = default_confirmation_resolution_policy(design)
    a = freeze_protected_assignments(pool, design, policy, seed=cfg["randomization_seed"])
    b = freeze_protected_assignments(pool, design, policy, seed=cfg["randomization_seed"])
    assert [row.to_dict() for row in a] == [row.to_dict() for row in b]
    qwen = [row for row in a if row.model_key == "QWEN"]
    small = [row for row in a if row.model_key == "SMALL_A"]
    assert len(qwen) == 63
    assert all(row.treatment_role == "CONFIRM_PROMOTED_POLICY" for row in qwen)
    assert len(small) == 63 * 4
    assert all(row.resolved_treatment_id is None for row in a)


def test_confirmation_resolution_accepts_development_only_and_sealed_opens_after_fresh():
    cfg = load_hd_next1_config(CONFIG)
    design = build_zero_call_design(cfg)
    assignments = freeze_protected_assignments(
        generate_protected_case_pool(cfg), design, default_confirmation_resolution_policy(design), seed=cfg["randomization_seed"]
    )
    snapshot = {"evidence_tier": "DEVELOPMENT", "winner_treatment_id": design.treatments[0]["treatment_id"], "challenger_treatment_id": design.treatments[-1]["treatment_id"]}
    resolved = freeze_confirmation_resolution(assignments, design, snapshot)
    assert all(row.resolved_treatment_id for row in resolved)
    state = ProtectedEvidenceState(resolved)
    with pytest.raises(ValueError, match="sealed"):
        state.open_partition("hd-next1-sealed")
    state.open_partition("hd-next1-fresh")
    state.mark_fresh_gate_passed()
    state.open_partition("hd-next1-sealed")

    with pytest.raises(ValueError, match="protected"):
        freeze_confirmation_resolution(assignments, design, {"evidence_tier": "FRESH", "winner_treatment_id": design.treatments[0]["treatment_id"]})
