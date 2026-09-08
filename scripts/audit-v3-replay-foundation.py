from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import inverted.capability_ratchet as cr
from inverted.capability_ratchet.cli import _build_parser
from inverted.capability_ratchet.core import FailureFixture, Partition, ReplayResult
from inverted.capability_ratchet.historical import V2EvidenceSource, preview_v2_failures
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.snapshot import _scan_secrets


REQUIRED_EXPORTS = {
    "ArchitectureOwner", "AutopsyReport", "CausalEvidenceStore", "CausalHypothesis",
    "DivergenceClass", "FailureAutopsy", "FailureFixture", "FailureLab",
    "FailureResearchProgram", "FailureResearchResult", "FirstDivergence",
    "HistoricalSeedResult", "HypothesisStatus", "InterventionDefinition",
    "InterventionGenerator", "InterventionKind", "MechanismAssessment",
    "MechanismLabel", "MechanismLocalizer", "MechanismRole", "Partition",
    "PromotionEvent", "PromotionState", "QwenReplayAdapter", "ReplayAdapter",
    "ReplayCompletion", "ReplayExecutor", "ReplayMode", "ReplayPlan", "ReplayRecord",
    "ReplayRecordType", "ReplayRequest", "ReplayResult", "ReplaySelector",
    "ReplayStore", "ReplayValidation", "SupersessionRecord",
    "TailoredInterventionGenerator", "TournamentBranch", "TournamentPlan",
    "TournamentPlanner", "V2EvidenceSource", "V2ReplayScorer", "build_ablations",
    "build_failure_fixture", "from_payload", "preview_v2_failures",
    "seed_v2_failures", "select_failures", "to_payload",
    "OperatingSurfaceLab", "OperatingSurfaceProfile", "SurfaceAnalyzer", "SurfaceAxis",
    "SurfaceBand", "SurfaceCallGeometry", "SurfaceDisposition", "SurfaceEvidenceCompiler",
    "SurfaceEvidenceKind", "SurfaceEvidenceStore", "SurfaceInterventionCompiler",
    "SurfaceObservation", "SurfacePlan", "SurfacePlanner", "SurfacePoint",
    "SurfaceStepResult", "SurfaceStoreValidation", "SurfaceStudy", "select_surface_study",
    "semantic_contract_hash",
}
REQUIRED_FILES = (
    "src/inverted/capability_ratchet/core.py",
    "src/inverted/capability_ratchet/replay_store.py",
    "src/inverted/capability_ratchet/snapshot.py",
    "src/inverted/capability_ratchet/replay.py",
    "src/inverted/capability_ratchet/qwen_replay.py",
    "src/inverted/capability_ratchet/historical.py",
    "src/inverted/capability_ratchet/query.py",
    "src/inverted/capability_ratchet/causal_core.py",
    "src/inverted/capability_ratchet/causal_store.py",
    "src/inverted/capability_ratchet/autopsy.py",
    "src/inverted/capability_ratchet/interventions.py",
    "src/inverted/capability_ratchet/tournament.py",
    "src/inverted/capability_ratchet/mechanisms.py",
    "src/inverted/capability_ratchet/lab.py",
    "src/inverted/capability_ratchet/surface_core.py",
    "src/inverted/capability_ratchet/surface_store.py",
    "src/inverted/capability_ratchet/surface_evidence.py",
    "src/inverted/capability_ratchet/surface_planner.py",
    "src/inverted/capability_ratchet/surface_interventions.py",
    "src/inverted/capability_ratchet/surface_analysis.py",
    "src/inverted/capability_ratchet/surface_lab.py",
    "src/inverted/capability_ratchet/cli.py",
    "scripts/run-test-replay.ps1",
    "tests/test_capability_ratchet_core.py",
    "tests/test_capability_ratchet_replay_store.py",
    "tests/test_capability_ratchet_snapshot.py",
    "tests/test_capability_ratchet_replay.py",
    "tests/test_capability_ratchet_qwen_replay.py",
    "tests/test_capability_ratchet_historical.py",
    "tests/test_capability_ratchet_query_cli.py",
    "tests/test_capability_ratchet_autopsy.py",
    "tests/test_capability_ratchet_interventions.py",
    "tests/test_capability_ratchet_tournament.py",
    "tests/test_capability_ratchet_mechanisms.py",
    "tests/test_capability_ratchet_lab.py",
    "tests/test_capability_ratchet_lab_cli.py",
    "tests/test_capability_ratchet_causal_preflight.py",
    "tests/test_capability_ratchet_surface_core.py",
    "tests/test_capability_ratchet_surface_store.py",
    "tests/test_capability_ratchet_surface_evidence.py",
    "tests/test_capability_ratchet_surface_planner.py",
    "tests/test_capability_ratchet_surface_interventions.py",
    "tests/test_capability_ratchet_surface_analysis.py",
    "tests/test_capability_ratchet_surface_lab.py",
    "tests/test_capability_ratchet_surface_cli.py",
    "tests/test_capability_ratchet_surface_preflight.py",
)


def _add(findings: list[str], condition: bool, message: str) -> None:
    if condition:
        findings.append(message)


def _material_observation_ids(source) -> tuple[set[str], int]:
    expected: set[str] = set()
    capped = 0
    for observation, row in zip(source.observations, source.observation_rows, strict=True):
        trial_id = row.get("trial_id") or dict(observation.metadata).get("trial_id")
        raw_trial = source.raw_trials.get(trial_id)
        raw_calls = raw_trial.get("raw_calls", []) if isinstance(raw_trial, dict) else []
        cap = False
        if raw_calls and isinstance(raw_calls[0], dict):
            request = raw_calls[0].get("request", {})
            response = raw_calls[0].get("response", {})
            cap = bool(isinstance(request, dict) and request.get("think") is True
                       and isinstance(response, dict) and response.get("done_reason") == "length")
        material = (cap or not observation.completed or not observation.semantic_pass
                    or not observation.contract_pass or bool(observation.failure_classes))
        if material:
            expected.add(observation.observation_id)
            if cap:
                capped += 1
    return expected, capped


def _cli_commands() -> set[str]:
    parser = _build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def _staged_run_paths() -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True,
    )
    return [line for line in completed.stdout.splitlines() if line.startswith("runs/")]


def _placeholder_hits(repo: Path) -> list[str]:
    paths = list((repo / "src/inverted/capability_ratchet").glob("*.py"))
    paths += list((repo / "tests").glob("test_capability_ratchet_*.py"))
    paths += [repo / "scripts/run-test-replay.ps1"]
    hits: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            upper = line.upper()
            if any(marker in upper for marker in ("TODO", "TBD", "FIXME")):
                hits.append(f"{path.as_posix()}:{number}:{line.strip()}")
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--replay-root", required=True)
    args = parser.parse_args(argv)
    repo = Path.cwd()
    findings: list[str] = []

    _add(findings, not REQUIRED_EXPORTS.issubset(set(cr.__all__)),
         f"missing public exports: {sorted(REQUIRED_EXPORTS - set(cr.__all__))}")
    missing_files = [path for path in REQUIRED_FILES if not (repo / path).is_file()]
    _add(findings, bool(missing_files), f"missing required replay files: {missing_files}")
    required_commands = {
        "validate", "list", "show", "seed-v2", "plan-replay", "execute-replay",
        "autopsy", "plan-lab", "show-lab", "run-lab",
        "plan-surface", "show-surface", "run-surface",
    }
    _add(findings, _cli_commands() != required_commands,
         f"CLI command surface mismatch: {sorted(_cli_commands())}")
    placeholder_hits = _placeholder_hits(repo)
    _add(findings, bool(placeholder_hits), f"placeholder markers remain: {placeholder_hits[:10]}")
    staged_runs = _staged_run_paths()
    _add(findings, bool(staged_runs), f"generated runs are staged: {staged_runs}")

    source = V2EvidenceSource(Path(args.source))
    preview = preview_v2_failures(source)
    loaded = source.load()
    expected_ids, expected_capped = _material_observation_ids(loaded)
    _add(findings, preview.invalid_rows != 0,
         f"historical preview has invalid rows: {preview.invalid_rows}")
    _add(findings, preview.material_failures != len(expected_ids),
         f"preview/material-set mismatch: preview={preview.material_failures} expected={len(expected_ids)}")

    store = ReplayStore(Path(args.replay_root))
    validation = store.validate()
    _add(findings, not validation.ok,
         f"replay store validation failed: missing={validation.missing_assets} hash={validation.hash_mismatches} lineage={validation.broken_lineage}")
    records = store.records() if validation.ok else ()
    fixtures = [record for record in records if isinstance(record, FailureFixture)]
    results = [record for record in records if isinstance(record, ReplayResult)]
    actual_ids = {fixture.focus_observation_id for fixture in fixtures if fixture.parent_failure_snapshot_id is None}
    _add(findings, actual_ids != expected_ids,
         f"historical fixture coverage mismatch: missing={len(expected_ids-actual_ids)} extra={len(actual_ids-expected_ids)}")
    capped_actual = sum(
        1 for fixture in fixtures
        if fixture.parent_failure_snapshot_id is None and "REASONING_CAP_EXHAUSTION" in fixture.failure_classes
    )
    _add(findings, capped_actual != expected_capped,
         f"reasoning-cap fixture coverage mismatch: actual={capped_actual} expected={expected_capped}")

    referenced_assets: set[str] = set()
    malformed_fixture_count = 0
    for fixture in fixtures:
        if fixture.model_visible_asset_sha256:
            referenced_assets.add(fixture.model_visible_asset_sha256)
        if fixture.forensic_asset_sha256:
            referenced_assets.add(fixture.forensic_asset_sha256)
        if fixture.oracle_asset_sha256:
            referenced_assets.add(fixture.oracle_asset_sha256)
        if fixture.parent_failure_snapshot_id is not None:
            continue
        if fixture.partition is not Partition.HISTORICAL or len(fixture.batch_task_ids) != 5:
            malformed_fixture_count += 1
            continue
        if fixture.forensic_asset_sha256 is None or fixture.oracle_asset_sha256 is None:
            malformed_fixture_count += 1
            continue
        try:
            visible = store.read_asset(fixture.model_visible_asset_sha256)
            forensic = store.read_asset(fixture.forensic_asset_sha256)
            oracle = store.read_asset(fixture.oracle_asset_sha256)
            _scan_secrets(visible, label="audit visible asset")
            _scan_secrets(forensic, label="audit forensic asset")
            _scan_secrets(oracle, label="audit oracle asset")
        except Exception:
            malformed_fixture_count += 1
            continue
        try:
            requests = visible["request_envelopes"]
            raw_trial = forensic["raw_trial"]
            focus_observation = forensic["focus_observation"]
            oracle_tasks = oracle["tasks"]
            raw_requests = [call["request"] for call in raw_trial["raw_calls"]]
            if requests != raw_requests:
                raise ValueError("model-visible requests differ from original forensic requests")
            if raw_trial["trial_id"] != fixture.source_trial_id:
                raise ValueError("forensic trial identity mismatch")
            if focus_observation["observation_id"] != fixture.focus_observation_id:
                raise ValueError("forensic focus observation mismatch")
            if oracle["focus_task_id"] != fixture.focus_task_id:
                raise ValueError("oracle focus task mismatch")
            if [row["task_id"] for row in oracle_tasks] != list(fixture.batch_task_ids):
                raise ValueError("oracle batch order mismatch")
            if not isinstance(fixture.metadata.get("difficulty"), int):
                raise ValueError("difficulty was collected but not preserved")
            rendered_visible = json.dumps(visible, sort_keys=True, separators=(",", ":"))
            if '"expected":' in rendered_visible or '"oracle_ref":' in rendered_visible:
                raise ValueError("oracle data leaked into model-visible replay state")
        except (KeyError, TypeError, ValueError, IndexError):
            malformed_fixture_count += 1

    _add(findings, malformed_fixture_count != 0,
         f"malformed/incomplete historical fixtures: {malformed_fixture_count}")
    for result in results:
        referenced_assets.add(result.output_asset_sha256)
        referenced_assets.add(result.raw_call_asset_sha256)
    asset_root = store.asset_root
    asset_files = {path.stem for path in asset_root.glob("*.json")} if asset_root.exists() else set()
    orphan_assets = sorted(asset_files - referenced_assets)
    _add(findings, bool(orphan_assets), f"orphan replay assets: count={len(orphan_assets)} sample={orphan_assets[:5]}")

    payload = {
        "forgotten_count": len(findings),
        "forgotten_items": findings,
        "MODEL_CALLS": 0,
        "source_observations": preview.total_observations,
        "expected_material_failures": preview.material_failures,
        "registered_failure_fixtures": len(fixtures),
        "expected_reasoning_cap_fixtures": expected_capped,
        "registered_reasoning_cap_fixtures": capped_actual,
        "replay_asset_files": len(asset_files),
        "orphan_asset_count": len(orphan_assets),
        "registry_rows": validation.row_count,
        "registry_ok": validation.ok,
    }
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
