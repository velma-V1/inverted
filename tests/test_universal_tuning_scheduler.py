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
    direct = vector([1,1,1,1,0])
    same = vector([1,1,1,1,0])
    better = vector([1,1,1,1,1])
    assert select_mode(direct, same).mode == "direct"
    assert select_mode(direct, better).mode == "thinking"


def test_both_weak_routes_to_capability_diagnostic_not_temperature():
    weak = vector([1,0,0,0,0])
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
