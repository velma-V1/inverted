from inverted.system_harvest.production_readiness import (
    ProductionReadinessInputs,
    evaluate_production_backend_readiness,
)


def _ready(**changes):
    values = dict(
        arm_gate_verified=True,
        driver_registry_verified=True,
        synthetic_all_driver_acceptance=True,
        raw_capture_verified=True,
        idempotency_verified=True,
        escalation_boundary_verified=True,
        no_real_agent_invocation_verified=True,
        harvest_regression_verified=True,
    )
    values.update(changes)
    return ProductionReadinessInputs(**values)


def test_production_backend_can_be_ready_without_live_harvest_authority():
    report = evaluate_production_backend_readiness(_ready())
    assert report.production_backend_ready is True
    assert report.live_harvest_ready is False
    assert report.blockers == ()


def test_any_missing_engineering_gate_blocks_production_readiness():
    report = evaluate_production_backend_readiness(_ready(idempotency_verified=False))
    assert report.production_backend_ready is False
    assert report.live_harvest_ready is False
    assert "idempotency/recovery gate not verified" in report.blockers
