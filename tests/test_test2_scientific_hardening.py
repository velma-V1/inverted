from __future__ import annotations

from inverted.domain import Action, Candidate
from inverted.models import MockModelAdapter
from inverted.oracle import apply_actions, evaluate_task
from inverted.system_executor import generate_candidate
from inverted.tasks import generate_task
from inverted.test2_local_impl import LOCAL_MODELS, build_executor_payload, run_local_campaign
from inverted.test2_local_analysis import (
    audit_confusion_by_model,
    balanced_role_model_scores,
    build_layered_capability_outputs,
    progressive_compounding_effects,
    rank_auditors,
    repair_factorial_effects,
    select_stability_task_ids,
    structured_failure_feedback,
)
from inverted.test2_gold import evaluate_test2_gold


def test_progressive_executor_cannot_bypass_formalizer_with_goal_or_oracle_requirements():
    task = generate_task("state", 3, 9991)
    ir = {"requirements": [{"id": "x", "kind": "equal", "path": "items.fake.value", "expected": 7}]}
    layered = build_executor_payload(task, ir=ir, direct=False)
    assert layered["formalized_ir"] == ir
    assert "goal" not in layered
    assert "requirements" not in layered
    assert layered["initial_state"] == task.initial_state.to_dict()
    assert layered["allowed_ops"] == list(task.allowed_ops)
    direct = build_executor_payload(task, ir=None, direct=True)
    assert direct["goal"] == task.goal
    assert direct["requirements"] == task.metadata["public_requirements"]


def test_hidden_gold_detects_pure_unintended_side_effect_without_changing_test1_oracle():
    task = generate_task("state", 2, 9992)
    clean = generate_candidate(task, 1.0, 9993)
    extra_actions = tuple(clean.actions) + (Action("set", "guard.unexpected", "side-effect"),)
    contaminated = Candidate(id="semantic-side-effect", state=apply_actions(task.initial_state, extra_actions), actions=extra_actions, configured_quality=1.0)
    assert evaluate_task(task, contaminated.state, contaminated.actions).success is True
    gold = evaluate_test2_gold(task, contaminated)
    assert gold.requirement_success is True
    assert gold.semantic_clean is False
    assert gold.success is False
    assert any(issue["kind"] == "unintended_action" for issue in gold.semantic_issues)


def test_structured_feedback_uses_action_evidence_for_policy_requirements_not_state_lookup():
    task = generate_task("policy", 4, 9994)
    clean = generate_candidate(task, 1.0, 9995)
    actions = list(reversed(list(clean.actions) + [Action("delete", "protected.flag", None)]))
    candidate = Candidate(id="policy-bad", state=apply_actions(task.initial_state, tuple(actions)), actions=tuple(actions), configured_quality=0.0)
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    feedback = structured_failure_feedback(task, candidate, list(oracle.failed_requirement_ids))
    by_kind = {row["kind"]: row for row in feedback["failed_requirements"]}
    if "action_absent" in by_kind:
        assert isinstance(by_kind["action_absent"]["observed"].get("matching_actions"), list)
    if "action_before" in by_kind:
        observed = by_kind["action_before"]["observed"]
        assert "before_indices" in observed and "after_indices" in observed


def test_auditor_ranking_penalizes_reject_all_and_prioritizes_false_accept_control():
    rows = []
    for i in range(10):
        rows.append({"model": "reject-all", "oracle_success": False, "accept": False, "success": True, "task_id": f"b{i}"})
        rows.append({"model": "reject-all", "oracle_success": True, "accept": False, "success": False, "task_id": f"g{i}"})
    for i in range(10):
        rows.append({"model": "balanced", "oracle_success": False, "accept": i == 0, "success": i != 0, "task_id": f"b{i}"})
        rows.append({"model": "balanced", "oracle_success": True, "accept": i < 8, "success": i < 8, "task_id": f"g{i}"})
    ranking = rank_auditors(rows)
    assert ranking[0]["model"] == "balanced"
    confusion = {row["model"]: row for row in audit_confusion_by_model(rows)}
    assert confusion["reject-all"]["specificity"] == 1.0
    assert confusion["reject-all"]["valid_accept_recall"] == 0.0
    assert confusion["balanced"]["false_accept_rate"] == 0.1


def test_best_single_score_weights_roles_equally_instead_of_row_volume():
    rows = []
    rows.extend({"model": "A", "role": "auditor", "success": True} for _ in range(100))
    rows.extend({"model": "A", "role": role, "success": False} for role in ("formalizer", "executor", "repairer"))
    for role in ("formalizer", "executor", "repairer", "auditor"):
        rows.extend({"model": "B", "role": role, "success": True} for _ in range(3))
        rows.append({"model": "B", "role": role, "success": False})
    scores = balanced_role_model_scores(rows)
    assert scores[0]["model"] == "B"
    assert scores[0]["roles_scored"] == 4


def test_stability_selection_is_decision_sensitive_and_contains_valid_and_invalid_cases():
    rows = []
    for case_id, truth in [(f"valid-{i}", True) for i in range(6)] + [(f"bad-{i}", False) for i in range(6)]:
        for model_index, model in enumerate(LOCAL_MODELS):
            accept = (model_index % 2 == 0) if case_id.endswith(("0", "1")) else truth
            rows.append({"task_id": case_id, "model": model, "oracle_success": truth, "accept": accept})
    selected = select_stability_task_ids(rows, max_cases=8)
    assert len(selected) == 8
    assert {row["oracle_success"] for row in selected} == {True, False}
    assert any(row["disagreement_rate"] > 0 for row in selected)


def test_repair_factorial_exports_main_effects_interaction_and_preservation():
    rows = []
    for feedback in ("raw", "structured"):
        for strategy in ("regenerate", "targeted"):
            for i in range(4):
                success = (feedback == "structured") or (strategy == "targeted" and i < 2)
                rows.append({"model": "m", "task_id": f"t{i}", "feedback_style": feedback, "strategy": strategy, "success": success, "preservation_rate": 1.0 if strategy == "targeted" else 0.5, "new_failures_introduced": 0 if strategy == "targeted" else 1})
    result = repair_factorial_effects(rows)
    assert result["condition_rows"]
    assert result["feedback_main_effect_pp"] > 0
    assert result["strategy_main_effect_pp"] > 0
    assert "interaction_pp" in result
    assert result["targeted_preservation_advantage"] > 0


def test_progressive_effects_preserve_incremental_compounding_and_regressions():
    rows = [
        {"task_id": "a", "pipeline": "S0_BEST_SINGLE_ALL_ROLES", "success": False},
        {"task_id": "a", "pipeline": "S1_SPECIALIZE_FORMALIZER", "success": True},
        {"task_id": "a", "pipeline": "S2_SPECIALIZE_FORMALIZER_EXECUTOR", "success": True},
        {"task_id": "b", "pipeline": "S0_BEST_SINGLE_ALL_ROLES", "success": True},
        {"task_id": "b", "pipeline": "S1_SPECIALIZE_FORMALIZER", "success": True},
        {"task_id": "b", "pipeline": "S2_SPECIALIZE_FORMALIZER_EXECUTOR", "success": False},
    ]
    effects = progressive_compounding_effects(rows)
    assert effects[0]["wins_created"] == 1
    assert effects[0]["wins_destroyed"] == 0
    assert effects[1]["wins_destroyed"] == 1


def test_layered_capability_outputs_keep_role_dimension_in_every_router_relevant_slice():
    rows = [
        {"role": "executor", "family": "policy", "complexity": 4, "fault": None, "representation": None, "model": "m", "success": True},
        {"role": "auditor", "family": "policy", "complexity": 4, "fault": "wrong_value", "representation": None, "model": "m", "success": False},
    ]
    outputs = build_layered_capability_outputs(rows)
    assert all("role" in row for row in outputs["family"])
    assert all("role" in row for row in outputs["complexity"])
    assert all("role" in row for row in outputs["fault"])


def test_mock_campaign_uses_condition_safe_evaluation_ids_and_preserves_nonempty_validator_ledger():
    models = [MockModelAdapter(model=name) for name in LOCAL_MODELS]
    result = run_local_campaign(models, run_id="hardening-mock", hard_limit=480)
    assert all(row.get("evaluation_id") for row in result["records"])
    repair_rows = [row for row in result["records"] if row.get("phase") == "repair_factorial"]
    keys = [(row["evaluation_id"], row["model"]) for row in repair_rows]
    assert len(keys) == len(set(keys))
    assert len({row["evaluation_id"] for row in repair_rows}) > len({row["task_id"] for row in repair_rows})
    assert result["validator_results"]
    assert any(row.get("stage") == "final_deterministic_authority" for row in result["validator_results"])


def test_local_config_disables_internal_transport_retries_so_physical_call_budget_is_exact():
    import yaml
    with open("configs/test2-local.yaml", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    assert cfg["local"]["ollama"]["transport_retries"] == 0
    assert sum(cfg["local"]["phase_limits"].values()) == 480
    assert cfg["local"]["phase_limits"]["repair_factorial"] == 100
    assert cfg["local"]["phase_limits"]["progressive_holdout"] == 100
