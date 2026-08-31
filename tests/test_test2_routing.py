from inverted.test2_analysis import derive_layered_router


def test_layered_router_can_outperform_best_single_model_when_roles_are_specialized():
    rows = [
        {"task_id": "t1", "role": "formalizer", "family": "state", "model": "A", "success": True},
        {"task_id": "t1", "role": "formalizer", "family": "state", "model": "B", "success": False},
        {"task_id": "t2", "role": "executor", "family": "state", "model": "A", "success": False},
        {"task_id": "t2", "role": "executor", "family": "state", "model": "B", "success": True},
        {"task_id": "t3", "role": "auditor", "family": "policy", "model": "A", "success": False},
        {"task_id": "t3", "role": "auditor", "family": "policy", "model": "B", "success": True},
        {"task_id": "t4", "role": "repairer", "family": "reconciliation", "model": "A", "success": True},
        {"task_id": "t4", "role": "repairer", "family": "reconciliation", "model": "B", "success": False},
    ]
    result = derive_layered_router(rows)
    assert result["best_single_model"]["successes"] == 2
    assert result["best_static_role_assignment"]["successes"] == 4
    assert result["oracle_per_task"]["successes"] == 4
    assert result["role_champions"]["formalizer"] == "A"
    assert result["role_champions"]["executor"] == "B"
    assert result["role_champions"]["auditor"] == "B"
    assert result["role_champions"]["repairer"] == "A"
