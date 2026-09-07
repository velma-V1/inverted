from inverted.universal_tuning.core import Profile
from inverted.universal_tuning.scheduler import (
    AdaptiveScheduler,
    ModelMetadata,
    discover_temperature_surface,
    select_minimum_budget,
    select_mode,
)
from inverted.universal_tuning.tasks import build_qwen_task_pool


def vector(pattern, batches=8):
    return tuple(pattern * batches)


def test_gate_scheduler_pairs_same_tasks_and_seed():
    pool = build_qwen_task_pool(seed=4, per_family=120)
    scheduler = AdaptiveScheduler(pool, ModelMetadata())
    trials = scheduler.paired_trials(
        family="ARITHMETIC", stage="gate",
        baseline=Profile(0, 0.7), candidate=Profile(1024, 1.0),
        atomic_count=40, task_offset=0, decision_reason="ESTABLISH_DIRECT_VS_THINKING",
    )
    assert len(trials) == 16
    for i in range(0, len(trials), 2):
        left, right = trials[i:i+2]
        assert left.batch_id == right.batch_id
        assert left.task_ids == right.task_ids
        assert left.inference_seed == right.inference_seed
        assert len(left.task_ids) == 5
        assert left.decision_reason == right.decision_reason == "ESTABLISH_DIRECT_VS_THINKING"


def test_direct_sufficient_and_thinking_superior_are_distinct():
    direct = tuple(([1] * 9 + [0]) * 12)
    same = direct
    better = tuple([1] * 120)
    assert select_mode(direct, same).mode == "direct"
    assert select_mode(direct, better).mode == "thinking"


def test_both_weak_routes_to_capability_diagnostic_not_temperature():
    weak = vector([1,0,0,0,0], batches=24)
    result = select_mode(weak, weak)
    assert result.mode == "unresolved"
    assert result.status == "CAPABILITY_UNRESOLVED"
    assert result.next_stage == "capability_diagnostic"


def test_minimum_budget_is_smallest_noninferior_to_best():
    outcomes = {
        256: vector([1,1,1,1,0]),
        512: vector([1,1,1,1,1]),
        1024: vector([1,1,1,1,1]),
        2048: vector([1,1,1,1,1]),
    }
    result = select_minimum_budget(outcomes, bootstrap_seed=9)
    assert result.selected_budget == 512
    assert result.reference_budget in {512, 1024, 2048}
    assert 256 in result.inferior_budgets


def test_broad_temperature_plateau_refuses_decimal_winner():
    outcomes = {temp: vector([1,1,1,1,0]) for temp in (0.4, 0.6, 0.8, 1.0)}
    surface = discover_temperature_surface(outcomes, bootstrap_seed=11)
    assert surface.kind == "PLATEAU"
    assert surface.lower == 0.4 and surface.upper == 1.0
    assert surface.optimum is None
    assert surface.recommended in {0.6, 0.8}


def test_narrow_temperature_optimum_requires_semantic_resolution():
    good = vector([1,1,1,1,1])
    worse = vector([1,1,1,1,0])
    outcomes = {0.599: worse, 0.600: good, 0.601: worse}
    surface = discover_temperature_surface(outcomes, bootstrap_seed=12)
    assert surface.kind == "OPTIMUM"
    assert surface.optimum == 0.6
    assert surface.resolution <= 0.0011


def test_coarse_single_best_requests_refinement_instead_of_false_optimum():
    good = vector([1,1,1,1,1])
    worse = vector([1,1,1,1,0])
    surface = discover_temperature_surface({0.4: worse, 0.6: good, 0.8: worse}, bootstrap_seed=12)
    assert surface.kind == "UNRESOLVED_POINT"
    assert surface.optimum is None
    assert surface.needs_refinement is True


def test_contract_only_failure_does_not_trigger_more_reasoning():
    direct = vector([1,1,1,1,1])
    result = select_mode(direct, direct, direct_contract_rate=0.45, thinking_contract_rate=0.45)
    assert result.mode == "direct"
    assert result.status == "CONTRACT_LIMITED"
    assert result.next_stage == "holdout"


def test_stage_partitions_are_disjoint_when_pool_has_full_geometry():
    pool = build_qwen_task_pool(seed=9, per_family=600)
    scheduler = AdaptiveScheduler(pool, ModelMetadata())
    partitions = [set(scheduler.partition_task_ids("ARITHMETIC", name, 120)) for name in (
        "gate", "budget", "temperature", "interaction", "holdout"
    )]
    assert all(len(part) == 120 for part in partitions)
    assert len(set().union(*partitions)) == 600


def test_projected_calls_counts_direct_and_thinking_physical_calls():
    pool = build_qwen_task_pool(seed=4, per_family=120)
    scheduler = AdaptiveScheduler(pool, ModelMetadata())
    trials = scheduler.paired_trials(
        family="ARITHMETIC", stage="gate", baseline=Profile(0,0.7),
        candidate=Profile(1024,1.0), atomic_count=40, task_offset=0,
        decision_reason="GATE",
    )
    assert scheduler.projected_physical_calls(trials) == 24


def test_holdout_cannot_certify_before_forty_fresh_atomic_tasks():
    from inverted.universal_tuning.scheduler import evaluate_holdout
    small = tuple([1,1,1,1,1] * 4)
    decision = evaluate_holdout(small, small, bootstrap_seed=21)
    assert decision.status == "INSUFFICIENT"
    assert decision.certified is False
    assert decision.next_atomic_count == 40


def test_interaction_selector_can_change_budget_temperature_pair():
    from inverted.universal_tuning.scheduler import select_interaction_profile
    profiles = {
        Profile(256, 0.6): vector([1,1,1,1,0]),
        Profile(256, 0.8): vector([1,1,1,1,0]),
        Profile(512, 0.6): vector([1,1,1,1,0]),
        Profile(512, 0.8): vector([1,1,1,1,1]),
    }
    result = select_interaction_profile(profiles, bootstrap_seed=30)
    assert result.profile == Profile(512, 0.8)
    assert result.changed_by_interaction is True
    assert result.status == "INTERACTION_RESOLVED"


def test_close_gate_requests_more_evidence_instead_of_choosing_direct():
    direct = tuple([1] * 32 + [0] * 8)
    thinking = list(direct)
    thinking[-1] = 1
    result = select_mode(direct, tuple(thinking), bootstrap_seed=1)
    assert result.mode == "unresolved"
    assert result.status == "EVIDENCE_CLOSE"
    assert result.next_stage == "gate"


def test_close_budget_boundary_is_not_marked_inferior_early():
    base = tuple([1] * 32 + [0] * 8)
    slightly_better = list(base)
    slightly_better[-1] = 1
    result = select_minimum_budget({256: base, 512: tuple(slightly_better)}, bootstrap_seed=1)
    assert result.selected_budget == 512
    assert 256 in result.unresolved_budgets
    assert 256 not in result.inferior_budgets
    assert result.status == "EVIDENCE_CLOSE"


def test_noisy_temperature_tie_requests_more_evidence_before_plateau():
    base = tuple([1] * 32 + [0] * 8)
    slightly_better = list(base)
    slightly_better[-1] = 1
    surface = discover_temperature_surface({0.6: base, 0.8: tuple(slightly_better)}, bootstrap_seed=1)
    assert surface.kind == "EVIDENCE_CLOSE"
    assert surface.needs_refinement is False


def test_gate_uses_deployable_semantic_floor_and_expands_weak_profiles_to_final_checkpoint():
    direct40 = tuple([1] * 32 + [0] * 8)
    think40 = tuple([1] * 34 + [0] * 6)
    early = select_mode(direct40, think40, bootstrap_seed=3)
    assert early.mode == "unresolved"
    assert early.status == "EVIDENCE_CLOSE"
    direct120 = direct40 * 3
    think120 = think40 * 3
    final = select_mode(direct120, think120, bootstrap_seed=3)
    assert final.mode == "unresolved"
    assert final.status == "CAPABILITY_UNRESOLVED"
    assert final.next_stage == "capability_diagnostic"


def test_paired_trial_execution_order_rotates_deterministically_by_batch():
    pool = build_qwen_task_pool(seed=4, per_family=120)
    scheduler = AdaptiveScheduler(pool, ModelMetadata())
    trials = scheduler.paired_trials(
        family="ARITHMETIC", stage="gate",
        baseline=Profile(0, 0.7), candidate=Profile(1024, 1.0),
        atomic_count=10, task_offset=0, decision_reason="ORDER_ROTATION",
    )
    first_pair = trials[:2]
    second_pair = trials[2:4]
    assert first_pair[0].profile != second_pair[0].profile
    assert {row.profile for row in first_pair} == {row.profile for row in second_pair}


def test_semantic_tie_can_promote_thinking_for_material_contract_or_completion_gain():
    semantic = tuple([1] * 40)
    contract_gain = select_mode(
        semantic, semantic,
        direct_contract_rate=0.70, thinking_contract_rate=1.0,
        direct_completion_rate=1.0, thinking_completion_rate=1.0,
    )
    assert contract_gain.mode == "thinking"
    assert contract_gain.status == "THINKING_RELIABILITY_SUPERIOR"
    completion_gain = select_mode(
        semantic, semantic,
        direct_contract_rate=1.0, thinking_contract_rate=1.0,
        direct_completion_rate=0.80, thinking_completion_rate=1.0,
    )
    assert completion_gain.mode == "thinking"
