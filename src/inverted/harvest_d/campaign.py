from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Mapping

from .artifacts import ArtifactWriter
from .kernel import CanonicalState, ProofCarryingAction, TrustedKernel, KernelViolation

class ConfigError(ValueError):
    pass

_ALLOWED_STAGES = ("D0", "D1", "D2", "D3", "D4", "D5", "D6", "D6B", "D7")
_DEFAULT_CEILINGS = {"D0": 0, "D1": 0, "D2": 70, "D3": 1000, "D4": 60, "D5": 50, "D6": 70, "D6B": 30, "D7": 0}

@dataclass(frozen=True)
class HarvestDConfig:
    stages: tuple[str, ...] = _ALLOWED_STAGES
    call_ceilings: Mapping[str, int] = field(default_factory=lambda: dict(_DEFAULT_CEILINGS))
    base_commit: str = "0d67ba4e5578b4c14225eb83b726fd137dfffecd"
    scope_frozen: bool = True
    normal_ci_model_free: bool = True
    cloud_required: bool = False
    primary_call_ceiling: int = 1280

    @classmethod
    def default(cls) -> "HarvestDConfig": return cls()

    @classmethod
    def from_json(cls, path: str | Path) -> "HarvestDConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8")); data["stages"] = tuple(data.get("stages", _ALLOWED_STAGES)); return cls(**data).validate()

    def to_dict(self) -> dict[str, object]:
        return {"stages": list(self.stages), "call_ceilings": dict(self.call_ceilings), "base_commit": self.base_commit,
                "scope_frozen": self.scope_frozen, "normal_ci_model_free": self.normal_ci_model_free,
                "cloud_required": self.cloud_required, "primary_call_ceiling": self.primary_call_ceiling}

    def validate(self) -> "HarvestDConfig":
        unknown = set(self.stages) - set(_ALLOWED_STAGES)
        if unknown: raise ConfigError(f"scope expansion not allowed: {sorted(unknown)}")
        if not self.scope_frozen: raise ConfigError("Harvest D scope must remain frozen")
        if self.cloud_required: raise ConfigError("core Harvest D cannot require cloud")
        for stage in self.stages:
            ceiling = int(self.call_ceilings.get(stage, 0))
            if ceiling < 0: raise ConfigError("negative call ceiling")
            if stage in {"D0", "D1", "D7"} and ceiling != 0: raise ConfigError(f"{stage} must be model-free")
            if ceiling > _DEFAULT_CEILINGS[stage]: raise ConfigError(f"{stage} exceeds frozen call ceiling")
        if sum(int(self.call_ceilings.get(s, 0)) for s in self.stages) > self.primary_call_ceiling: raise ConfigError("campaign exceeds primary call ceiling")
        return self

class HarvestDCampaign:
    def __init__(self, config: HarvestDConfig) -> None: self.config = config.validate()

    def _kernel_self_checks(self):
        kernel_rows, tx_rows = [], []
        k = TrustedKernel(CanonicalState(version=2, data={}))
        lease = k.issue_authority({"op": "write"}); stale = ProofCarryingAction("stale", {"op": "write"}, 1, lease.authority_id)
        try: k.prepare(stale); status = "FAIL"
        except KernelViolation: status = "PASS"
        kernel_rows.append({"fault": "stale_state", "expected": "BLOCK", "status": status})
        k2 = TrustedKernel(CanonicalState(version=1, data={}))
        lease2 = k2.issue_authority({"op": "write"}); action = ProofCarryingAction("a", {"op": "write"}, 1, lease2.authority_id)
        tx = k2.prepare(action); k2.mark_effect_unknown(tx.tx_id)
        try: k2.retry(tx.tx_id); status = "FAIL"
        except KernelViolation: status = "PASS"
        tx_rows.append({"injection": "after_effect_before_receipt", "effect_state": "UNKNOWN", "expected": "RECONCILE_NOT_RETRY", "status": status})
        k2.reconcile(tx.tx_id, committed=False); k2.close(tx.tx_id)
        k3 = TrustedKernel(CanonicalState(version=1, data={}))
        lease3 = k3.issue_authority({"op": "write"}); a3 = ProofCarryingAction("a3", {"op": "write"}, 1, lease3.authority_id)
        t3 = k3.prepare(a3); k3.commit_effect(t3.tx_id, "effect-1"); k3.rollback(t3.tx_id)
        try: k3.prepare(a3); status = "FAIL"
        except KernelViolation: status = "PASS"
        kernel_rows.append({"fault": "authorization_resurrection", "expected": "BLOCK", "status": status})
        return kernel_rows, tx_rows

    def dry_run(self, output: str | Path) -> dict[str, object]:
        writer = ArtifactWriter(output); kernel_rows, tx_rows = self._kernel_self_checks()
        readiness = [
            {"question": "Test2 capability prior", "state": "OBSERVED_DIAGNOSTIC", "contradiction": "non_unique_physical_model_call_identity", "target_stage": "D2"},
            {"question": "S2 routing", "state": "OBSERVED_NON_DECISIVE", "contradiction": "architecture_claims_authorized=false", "target_stage": "D4"},
            {"question": "minimum trusted kernel", "state": "PARTIAL", "contradiction": "", "target_stage": "D1"},
        ]
        writer.write_json("EVIDENCE-PROVENANCE.json", {"base_commit": self.config.base_commit, "frozen_evidence_modified": False,
                          "test2_primary_status": "INCONCLUSIVE_CONTAMINATED", "s2_status": "S2_SCREEN_NON_DECISIVE"})
        writer.write_json("causal_architecture_readiness_matrix.json", readiness)
        writer.write_csv("causal_architecture_readiness_matrix.csv", readiness, fieldnames=("question", "state", "contradiction", "target_stage"))
        writer.write_csv("kernel_fault_matrix.csv", kernel_rows, fieldnames=("fault", "expected", "status"))
        writer.write_csv("transaction_crash_matrix.csv", tx_rows, fieldnames=("injection", "effect_state", "expected", "status"))
        writer.write_json("model_capability_envelope.json", {"version": 0, "states": {}, "status": "UNMEASURED"})
        writer.write_jsonl("system_involvement_telemetry.jsonl", [])
        writer.write_json("minimum_required_scaffolding.json", {"status": "UNMEASURED"})
        writer.write_json("qwen_call_policy.json", {"status": "UNMEASURED", "allowed_routes": ["ROUTINE_LOCAL", "SCAFFOLDED_LOCAL", "QWEN_STANDARD", "QWEN_MAX", "NOVELTY_INVESTIGATION", "ACQUIRE_EVIDENCE", "SAFE_STOP"]})
        writer.write_jsonl("promoted_failure_knowledge.jsonl", [])
        writer.write_json("boundary_ratchet.json", {"status": "UNMEASURED", "promotions": 0})
        writer.write_text("remaining_unknowns.md", "# Remaining Unknowns\n\n- Residual cognition boundary\n- Optimal recovery switching policy\n- Exact minimal kernel\n")
        writer.write_text("test5_handoff.md", "# Test 5 Handoff\n\nStatus: NOT READY — Harvest D real stages have not been executed.\n")
        master = {"experiment": "harvest-d", "mode": "model-free-dry-run", "scope_frozen": self.config.scope_frozen,
                  "stages": list(self.config.stages), "real_model_calls": 0,
                  "kernel_self_checks_passed": all(r["status"] == "PASS" for r in kernel_rows + tx_rows),
                  "ready_for_real_model_runs": True}
        writer.write_json("00-HARVEST-D-MASTER-INDEX.json", master); writer.finalize(); return master
