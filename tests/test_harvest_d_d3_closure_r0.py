from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path


_REQUIRED_R0_ARTIFACTS = {
    "closure_claim_space_manifest.json",
    "closure_search_space_manifest.json",
    "closure_candidate_equivalence_classes.jsonl",
    "closure_candidate_pruning_ledger.jsonl",
    "closure_prior_evidence_ledger.jsonl",
    "closure_treatment_catalog.jsonl",
    "closure_treatment_exposure.jsonl",
    "closure_pre_state_catalog.jsonl",
    "closure_action_frontier_catalog.jsonl",
    "closure_combinatorial_coverage.json",
    "closure_interaction_coverage.json",
    "closure_uncovered_space.json",
    "closure_r0_readiness_report.json",
    "closure_claim_adequacy_report.json",
}


def _load_module():
    name = "inverted.harvest_d.d3_closure_r0"
    spec = importlib.util.find_spec(name)
    assert spec is not None, "R0 package builder module is missing"
    return importlib.import_module(name)


def _config(repo_root: Path) -> dict:
    return json.loads((repo_root / "configs" / "harvest-d-d3-closure-v2.json").read_text(encoding="utf-8"))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_build_r0_package_emits_complete_zero_call_artifact_contract(tmp_path: Path):
    module = _load_module()
    repo_root = Path.cwd()

    summary = module.build_r0_package(repo_root, tmp_path, _config(repo_root))

    assert summary.final_state == "R0_MODEL_FREE_COMPLETE"
    assert summary.physical_model_calls == 0
    assert summary.physical_execution_authorized is False
    assert _REQUIRED_R0_ARTIFACTS <= {path.name for path in tmp_path.iterdir() if path.is_file()}

    readiness = _read_json(tmp_path / "closure_r0_readiness_report.json")
    assert readiness["r0_ready"] is True
    assert readiness["physical_model_calls"] == 0
    assert readiness["physical_execution_authorized"] is False


def test_r0_catalogs_are_nonempty_and_link_treatment_exposure_state_and_frontier(tmp_path: Path):
    module = _load_module()
    repo_root = Path.cwd()
    module.build_r0_package(repo_root, tmp_path, _config(repo_root))

    treatments = _read_jsonl(tmp_path / "closure_treatment_catalog.jsonl")
    exposures = _read_jsonl(tmp_path / "closure_treatment_exposure.jsonl")
    pre_states = _read_jsonl(tmp_path / "closure_pre_state_catalog.jsonl")
    frontiers = _read_jsonl(tmp_path / "closure_action_frontier_catalog.jsonl")

    assert treatments
    assert exposures
    assert pre_states
    assert frontiers

    exposure_ids = {row["exposure_id"] for row in exposures}
    pre_state_ids = {row["pre_state_id"] for row in pre_states}
    frontier_ids = {row["frontier_id"] for row in frontiers}
    assert all(row["exposure_id"] in exposure_ids for row in treatments)
    assert all(row["pre_state_id"] in pre_state_ids for row in treatments)
    assert all(row["action_frontier_id"] in frontier_ids for row in treatments)
    assert all(row["treatment_id"] for row in treatments)


def test_historical_priors_add_scheduler_value_without_directly_pruning_legal_candidates(tmp_path: Path):
    module = _load_module()
    repo_root = Path.cwd()
    module.build_r0_package(repo_root, tmp_path, _config(repo_root))

    priors = _read_jsonl(tmp_path / "closure_prior_evidence_ledger.jsonl")
    treatments = _read_jsonl(tmp_path / "closure_treatment_catalog.jsonl")
    pruning = _read_jsonl(tmp_path / "closure_candidate_pruning_ledger.jsonl")

    assert priors
    assert any(row["present"] and row["scheduler_prior_weight"] > 0 for row in priors)
    assert any(row["prior_evidence_value"] >= 0 for row in treatments)
    forbidden_prior_prunes = {
        "WEAK_HISTORICAL_PRIOR",
        "SMALL_SAMPLE_PRIOR",
        "HISTORICAL_FAILURE",
        "PRIOR_LOW_SCORE",
    }
    assert not any(row.get("reason_code") in forbidden_prior_prunes for row in pruning)
    assert all(row["evidence_tier"] == "E1_HISTORICAL_PRIOR" for row in priors)


def test_r0_coverage_reports_pairwise_and_targeted_three_way_obligations_without_claiming_they_are_physically_observed(tmp_path: Path):
    module = _load_module()
    repo_root = Path.cwd()
    module.build_r0_package(repo_root, tmp_path, _config(repo_root))

    pairwise = _read_json(tmp_path / "closure_combinatorial_coverage.json")
    interactions = _read_json(tmp_path / "closure_interaction_coverage.json")
    uncovered = _read_json(tmp_path / "closure_uncovered_space.json")

    assert pairwise["planned_pairwise_coverage_ratio"] == 1.0
    assert pairwise["physical_observations"] == 0
    assert pairwise["coverable_pairs"] > 0
    assert interactions["required_three_way_obligations"]
    assert interactions["physical_observations"] == 0
    assert uncovered["physical_model_calls"] == 0
    assert uncovered["fresh_evidence_collected"] is False


def test_r0_claim_adequacy_remains_fail_closed_for_physical_inference(tmp_path: Path):
    module = _load_module()
    repo_root = Path.cwd()
    module.build_r0_package(repo_root, tmp_path, _config(repo_root))

    adequacy = _read_json(tmp_path / "closure_claim_adequacy_report.json")
    assert adequacy["physical_execution_authorized"] is False
    assert adequacy["claim_ceiling"] in {"SCREEN", "BEST_OF_TESTED"}
    blocker_text = " ".join(adequacy["blockers"]).lower()
    assert "calibration" in blocker_text
    assert "recovery" in blocker_text or "minimality" in blocker_text
