from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimAdequacyInputs:
    claim_space_manifest_present: bool
    search_space_manifest_present: bool
    pairwise_coverage_ratio: float
    required_three_way_coverage_ratio: float
    cost_calibration_complete: bool
    reproducibility_calibration_complete: bool
    cost_scaled_scheduler_ready: bool
    protected_discovery_ready: bool
    local_minimality_ready: bool
    real_recovery_ready: bool
    sealed_confirmation_protected: bool
    blocker_audit_green: bool
    launcher_path_green: bool
    unresolved_hard_blockers: int
    unresolved_scientific_risks: int


@dataclass(frozen=True)
class ClaimAdequacyReport:
    physical_execution_authorized: bool
    claim_ceiling: str
    minimum_sufficient_claim_eligible: bool
    recovery_claim_eligible: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "physical_execution_authorized": self.physical_execution_authorized,
            "claim_ceiling": self.claim_ceiling,
            "minimum_sufficient_claim_eligible": self.minimum_sufficient_claim_eligible,
            "recovery_claim_eligible": self.recovery_claim_eligible,
            "blockers": list(self.blockers),
        }


def evaluate_claim_adequacy(inputs: ClaimAdequacyInputs) -> ClaimAdequacyReport:
    blockers: list[str] = []

    if not inputs.claim_space_manifest_present:
        blockers.append("claim-space manifest missing")
    if not inputs.search_space_manifest_present:
        blockers.append("search-space manifest missing")
    if inputs.pairwise_coverage_ratio < 1.0:
        blockers.append(f"pairwise coverage incomplete: {inputs.pairwise_coverage_ratio:.6f}")
    if inputs.required_three_way_coverage_ratio < 1.0:
        blockers.append(f"required three-way coverage incomplete: {inputs.required_three_way_coverage_ratio:.6f}")
    if not inputs.cost_calibration_complete:
        blockers.append("cost calibration incomplete")
    if not inputs.reproducibility_calibration_complete:
        blockers.append("reproducibility calibration incomplete")
    if not inputs.cost_scaled_scheduler_ready:
        blockers.append("cost-scaled scheduler not ready")
    if not inputs.protected_discovery_ready:
        blockers.append("protected discovery/challenger stream not ready")
    if not inputs.local_minimality_ready:
        blockers.append("local minimality/ablation engine not ready")
    if not inputs.real_recovery_ready:
        blockers.append("real multi-step recovery evidence path not ready")
    if not inputs.sealed_confirmation_protected:
        blockers.append("sealed confirmation reserve not protected")
    if not inputs.blocker_audit_green:
        blockers.append("Law 28 blocker audit not green")
    if not inputs.launcher_path_green:
        blockers.append("real launcher/model-free path not green")
    if inputs.unresolved_hard_blockers:
        blockers.append(f"unresolved hard blockers: {inputs.unresolved_hard_blockers}")
    if inputs.unresolved_scientific_risks:
        blockers.append(f"unresolved scientific risks: {inputs.unresolved_scientific_risks}")

    minimum_eligible = inputs.local_minimality_ready and inputs.pairwise_coverage_ratio >= 1.0
    recovery_eligible = inputs.real_recovery_ready

    if inputs.pairwise_coverage_ratio < 1.0 or inputs.required_three_way_coverage_ratio < 1.0:
        claim_ceiling = "SCREEN"
    elif not minimum_eligible or not recovery_eligible:
        claim_ceiling = "BEST_OF_TESTED"
    else:
        claim_ceiling = "OPTIMIZATION_ELIGIBLE"

    return ClaimAdequacyReport(
        physical_execution_authorized=not blockers,
        claim_ceiling=claim_ceiling,
        minimum_sufficient_claim_eligible=minimum_eligible,
        recovery_claim_eligible=recovery_eligible,
        blockers=tuple(blockers),
    )
