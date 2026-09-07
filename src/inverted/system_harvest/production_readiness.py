from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionReadinessInputs:
    arm_gate_verified: bool
    driver_registry_verified: bool
    synthetic_all_driver_acceptance: bool
    raw_capture_verified: bool
    idempotency_verified: bool
    escalation_boundary_verified: bool
    no_real_agent_invocation_verified: bool
    harvest_regression_verified: bool


@dataclass(frozen=True)
class ProductionReadinessReport:
    production_backend_ready: bool
    live_harvest_ready: bool
    blockers: tuple[str, ...]


def evaluate_production_backend_readiness(
    inputs: ProductionReadinessInputs,
) -> ProductionReadinessReport:
    blockers: list[str] = []
    gates = (
        (inputs.arm_gate_verified, "arm-state gate not verified"),
        (inputs.driver_registry_verified, "driver registry not verified"),
        (inputs.synthetic_all_driver_acceptance, "synthetic all-driver acceptance not verified"),
        (inputs.raw_capture_verified, "raw capture gate not verified"),
        (inputs.idempotency_verified, "idempotency/recovery gate not verified"),
        (inputs.escalation_boundary_verified, "escalation boundary gate not verified"),
        (inputs.no_real_agent_invocation_verified, "no-real-agent invocation evidence not verified"),
        (inputs.harvest_regression_verified, "harvest regression not verified"),
    )
    for passed, blocker in gates:
        if not passed:
            blockers.append(blocker)
    return ProductionReadinessReport(
        production_backend_ready=not blockers,
        live_harvest_ready=False,
        blockers=tuple(blockers),
    )
