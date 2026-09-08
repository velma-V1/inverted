from __future__ import annotations

import inspect

import inverted.universal_tuning as tuning
from inverted.universal_tuning.core import FailureClass, Observation, Profile


def _api():
    required = (
        "ThinkingBudgetPoint",
        "ThinkingCurveResult",
        "analyze_thinking_curve",
    )
    for name in required:
        assert hasattr(tuning, name), name
    return tuple(getattr(tuning, name) for name in required)


def _observations(
    budget: int,
    *,
    total: int,
    passed: int,
    quality_pass: float = 1.0,
    quality_fail: float = 0.0,
    latency_s: float = 1.0,
    failure_class: FailureClass = FailureClass.SEMANTIC_FAIL,
) -> tuple[Observation, ...]:
    rows = []
    for index in range(total):
        success = index < passed
        rows.append(
            Observation(
                observation_id=f"obs:{budget}:{index}",
                batch_id=f"batch:{budget}:{index // 5}",
                task_id=f"task:{index}",
                family="LOGIC_CONSTRAINTS",
                stage="budget",
                profile=Profile(budget, 0.7),
                inference_seed=index,
                decision_reason="thinking-curve-contract",
                semantic_pass=success,
                contract_pass=True,
                completed=True,
                semantic_quality=quality_pass if success else quality_fail,
                contract_quality=1.0,
                latency_s=latency_s,
                output_tokens=32,
                thinking_tokens=budget if budget > 0 else 0,
                physical_calls=2 if budget > 0 else 1,
                response_text="ok" if success else "wrong",
                failure_classes=() if success else (failure_class,),
            )
        )
    return tuple(rows)


def test_thinking_curve_is_public_posthoc_analysis_with_no_execution_dependency() -> None:
    _, _, analyze = _api()
    parameters = set(inspect.signature(analyze).parameters)
    assert "observations" in parameters
    assert parameters.isdisjoint({"runner", "adapter", "client"})


def test_curve_finds_minimum_optimum_saturation_degradation_and_overthinking() -> None:
    Point, Result, analyze = _api()
    observations = (
        _observations(0, total=20, passed=8, latency_s=0.2)
        + _observations(256, total=20, passed=16, latency_s=1.0)
        + _observations(512, total=20, passed=20, latency_s=2.0)
        + _observations(1024, total=20, passed=20, latency_s=4.0)
        + _observations(
            2048,
            total=20,
            passed=12,
            latency_s=8.0,
            failure_class=FailureClass.PARAMETER_SENSITIVITY,
        )
    )

    result = analyze(
        observations,
        success_threshold=0.80,
        min_observations_per_budget=20,
        material_delta=0.05,
    )

    assert isinstance(result, Result)
    assert result.status == "CHARACTERIZED"
    assert result.evidence_sufficient is True
    assert result.minimum_effective_budget == 256
    assert result.optimum_budget == 512
    assert result.saturation_budget == 1024
    assert result.degradation_budget == 2048
    assert result.overthinking_detected is True
    assert all(isinstance(point, Point) for point in result.points)
    assert [point.thinking_budget for point in result.points] == [0, 256, 512, 1024, 2048]
    assert result.points[-1].success_rate == 0.60


def test_direct_zero_budget_is_a_real_candidate_and_wins_cost_ties() -> None:
    _, _, analyze = _api()
    observations = (
        _observations(0, total=20, passed=20, latency_s=0.2)
        + _observations(256, total=20, passed=20, latency_s=1.0)
        + _observations(512, total=20, passed=20, latency_s=2.0)
    )

    result = analyze(
        observations,
        success_threshold=0.80,
        min_observations_per_budget=20,
        material_delta=0.05,
    )

    assert result.minimum_effective_budget == 0
    assert result.optimum_budget == 0
    assert result.saturation_budget == 256
    assert result.degradation_budget is None
    assert result.overthinking_detected is False


def test_no_effective_budget_reports_boundary_without_crashing_or_faking_winner() -> None:
    _, _, analyze = _api()
    observations = (
        _observations(0, total=20, passed=4)
        + _observations(256, total=20, passed=8)
        + _observations(512, total=20, passed=12)
    )

    result = analyze(
        observations,
        success_threshold=0.80,
        min_observations_per_budget=20,
        material_delta=0.05,
    )

    assert result.status == "NO_EFFECTIVE_BUDGET"
    assert result.evidence_sufficient is True
    assert result.minimum_effective_budget is None
    assert result.optimum_budget is None
    assert result.saturation_budget is None
    assert result.degradation_budget is None


def test_under_sampled_curve_stays_unresolved_instead_of_certifying() -> None:
    _, _, analyze = _api()
    observations = (
        _observations(0, total=4, passed=4)
        + _observations(256, total=4, passed=4)
        + _observations(512, total=4, passed=4)
    )

    result = analyze(
        observations,
        success_threshold=0.80,
        min_observations_per_budget=20,
        material_delta=0.05,
    )

    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.evidence_sufficient is False
    assert result.minimum_effective_budget is None
    assert result.optimum_budget is None
    assert result.saturation_budget is None
    assert result.degradation_budget is None
    assert [point.n_observations for point in result.points] == [4, 4, 4]


def test_larger_budget_failure_regression_is_exposed_as_overthinking_signal() -> None:
    _, _, analyze = _api()
    observations = (
        _observations(0, total=20, passed=10, latency_s=0.2)
        + _observations(256, total=20, passed=18, latency_s=1.0)
        + _observations(512, total=20, passed=20, latency_s=2.0)
        + _observations(
            1024,
            total=20,
            passed=14,
            latency_s=4.0,
            failure_class=FailureClass.PARAMETER_SENSITIVITY,
        )
    )

    result = analyze(
        observations,
        success_threshold=0.80,
        min_observations_per_budget=20,
        material_delta=0.05,
    )

    assert result.optimum_budget == 512
    assert result.degradation_budget == 1024
    assert result.overthinking_detected is True
    degraded = next(point for point in result.points if point.thinking_budget == 1024)
    assert degraded.failure_rate == 0.30
    assert degraded.failure_classes["PARAMETER_SENSITIVITY"] == 6
