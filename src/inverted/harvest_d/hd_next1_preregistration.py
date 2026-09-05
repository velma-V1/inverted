from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .hd_next1_adequacy import evaluate_prerun_adequacy
from .hd_next1_budget import HDNext1BudgetState
from .hd_next1_cases import CONFIRMATION_FAMILY_MAP, describe_observable_stratum, generate_protected_case_pool
from .hd_next1_randomization import default_confirmation_resolution_policy, freeze_protected_assignments
from .hd_next1_space import build_zero_call_design


@dataclass(frozen=True)
class HDNext1PreregistrationSummary:
    physical_model_calls: int
    ready_for_owner_authorization: bool
    preregistration_manifest_sha256: str


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _write_manifest(root: Path) -> str:
    paths = sorted(path for path in root.iterdir() if path.is_file() and path.name != "SHA256SUMS.csv")
    manifest = root / "SHA256SUMS.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("path", "sha256"), lineterminator="\n")
        writer.writeheader()
        for path in paths:
            writer.writerow({"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


def verify_sha256_manifest(root: str | Path) -> tuple[str, ...]:
    root = Path(root)
    bad: list[str] = []
    with (root / "SHA256SUMS.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            path = root / row["path"]
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                bad.append(row["path"])
    return tuple(bad)


def build_preregistration_package(repo_root: str | Path, output_root: str | Path, config: dict[str, Any]) -> HDNext1PreregistrationSummary:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    design = build_zero_call_design(config)
    protected = generate_protected_case_pool(config)
    policy = default_confirmation_resolution_policy(design)
    assignments = freeze_protected_assignments(protected, design, policy, seed=int(config["randomization_seed"]))
    adequacy = evaluate_prerun_adequacy(config, design, assignments)
    _write_json(
        root / "claim_space_manifest.json",
        {
            "experiment_id": "HD-NEXT-1",
            "question_ids": list(config["question_ids"]),
            "model_visible_support": [*[f"I{i}" for i in range(1, 11)], "A1", "A2", "A3", "A4"],
            "system_owned_not_ablatable": [f"A{i}" for i in range(5, 12)],
            "decision_states": ["REQUIRED", "CONDITIONAL", "REDUNDANT", "HARMFUL", "UNRESOLVED"],
            "physical_model_calls": 0,
        },
    )
    _write_json(
        root / "search_space_manifest.json",
        {
            "experiment_id": "HD-NEXT-1",
            "factor_levels": {key: list(value) for key, value in design.factor_levels.items()},
            "admitted_treatment_count": len(design.treatments),
            "physical_model_calls": 0,
        },
    )
    _write_jsonl(root / "candidate_pruning_ledger.jsonl", design.pruning_ledger)
    _write_json(root / "coverage_report.json", {"pairwise_coverage_ratio": design.pairwise_coverage_ratio, "physical_model_calls": 0})
    _write_json(
        root / "interaction_coverage.json",
        {"required_three_way_coverage_ratio": design.required_three_way_coverage_ratio, "obligations": list(design.required_three_way), "physical_model_calls": 0},
    )
    _write_json(root / "uncovered_space.json", {"regions": list(design.uncovered_regions), "physical_model_calls": 0})
    _write_json(
        root / "frozen_case_manifest.json",
        {
            "case_count": len(protected),
            "required_family_map": CONFIRMATION_FAMILY_MAP,
            "cases": [
                {"case_id": case.case_id, "partition": case.metadata["partition"], "family_id": case.metadata["hd_next1_family_id"], "family": case.family, "stratum": describe_observable_stratum(case)}
                for case in protected
            ],
            "physical_model_calls": 0,
        },
    )
    _write_jsonl(root / "frozen_randomization_assignments.jsonl", (row.to_dict() for row in assignments))
    _write_json(root / "confirmation_resolution_policy.json", policy.to_dict())
    calibration = config["reproducibility_calibration"]
    _write_json(
        root / "cost_calibration_plan.json",
        {
            "cases": calibration["structurally_distinct_cases"],
            "models": ["SMALL_A", "QWEN"],
            "repetitions": calibration["repetitions"],
            "physical_call_ceiling": calibration["physical_call_ceiling"],
            "cost_metric": "inference_wall_time_seconds",
            "physical_model_calls": 0,
        },
    )
    budget = HDNext1BudgetState.default(max_inference_seconds=10**9)
    _write_jsonl(root / "cost_budget_state.jsonl", ({"state": "PREREGISTERED", **budget.to_dict()},))
    _write_json(
        root / "statistical_decision_rule.json",
        {
            "effect_margin": config["effect_margin"],
            "family_alpha": config["family_alpha"],
            "multiplicity": "HOLM_FAMILY_WISE",
            "model_substitution_loss": "QWEN_ONLY_WIN",
            "support_ablation_loss": "FULL_ONLY_WIN",
            "development_can_promote": False,
            "underpowered_cell_state": "UNRESOLVED",
            "physical_model_calls": 0,
        },
    )
    _write_json(root / "claim_adequacy_report.json", adequacy.to_dict())
    _write_json(
        root / "physical_execution_authorization.json",
        {
            "authorization_kind": "HD_NEXT1_PREREGISTRATION",
            "authorized_experiment_id": "HD-NEXT-1",
            "historical_fingerprint": config["historical_fingerprint"],
            "physical_execution_authorized": False,
            "owner_physical_execution_approval_required": True,
            "ready_for_owner_authorization": adequacy.ready_for_owner_authorization,
            "blockers": list(adequacy.blockers),
            "physical_model_calls": 0,
        },
    )
    manifest_sha = _write_manifest(root)
    return HDNext1PreregistrationSummary(0, adequacy.ready_for_owner_authorization, manifest_sha)
