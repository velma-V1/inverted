from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import inverted.capability_ratchet as cr
from inverted.capability_ratchet.cli import _build_parser
from inverted.capability_ratchet.core import (
    FailureFixture,
    MutationFixture,
    Partition,
    PromotionEvent,
    PromotionState,
    ReplayResult,
    from_payload,
    to_payload,
)
from inverted.capability_ratchet.historical import V2EvidenceSource, preview_v2_failures
from inverted.capability_ratchet.mutation_core import (
    MutationAxis,
    MutationDirection,
    MutationOrigin,
)
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.snapshot import _scan_secrets
from inverted.capability_ratchet.surface_core import SurfaceAxis
from inverted.capability_ratchet.surface_evidence import SurfaceEvidenceCompiler
from inverted.capability_ratchet.surface_interventions import SUPPORTED_SURFACE_AXES


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
    "SurfaceBand", "SurfaceBootstrapPlan", "SurfaceCallGeometry", "SurfaceDisposition",
    "SurfaceEvidenceCompiler", "SurfaceEvidenceKind", "SurfaceEvidenceStore",
    "SurfaceInterventionCompiler", "SurfaceObservation", "SurfacePlan", "SurfacePlanner",
    "SurfacePoint", "SurfaceStepResult", "SurfaceStoreValidation", "SurfaceStudy",
    "plan_eligible_surfaces", "select_surface_study", "semantic_contract_hash",
    "GeneralizationClass", "GeneralizationProfile", "MutationAnalyzer", "MutationAxis",
    "MutationDirection", "MutationEvidenceStore", "MutationFixture", "MutationGenerator",
    "MutationLab", "MutationOrigin", "MutationOutcome", "MutationPlan", "MutationPlanner",
    "MutationPolicy", "MutationReplayCompiler", "MutationSpec", "MutationStepResult",
    "MutationStoreValidation", "MutationStudy", "MutationTemplate",
}

EXPECTED_SURFACE_AXES = {
    SurfaceAxis.REASONING_BUDGET,
    SurfaceAxis.TEMPERATURE,
    SurfaceAxis.CONTEXT_DOSE,
    SurfaceAxis.REPRESENTATION,
    SurfaceAxis.ORDER,
    SurfaceAxis.RECURRENCE,
    SurfaceAxis.TIMING,
    SurfaceAxis.PLACEMENT,
    SurfaceAxis.CONTEXT_POSITION,
    SurfaceAxis.DELIVERY_MODE,
    SurfaceAxis.TRIGGER_MODE,
}

EXPECTED_MUTATION_AXES = {
    MutationAxis.NUMBERS_ENTITIES,
    MutationAxis.DEPENDENCY_DEPTH,
    MutationAxis.REQUIREMENT_COUNT,
    MutationAxis.ACTION_SPACE_SIZE,
    MutationAxis.CRITICAL_INFORMATION_POSITION,
    MutationAxis.DISTRACTORS,
    MutationAxis.EVIDENCE_STATE,
    MutationAxis.AUTHORITY_STATE,
    MutationAxis.REVERSIBILITY_CONSEQUENCE,
    MutationAxis.TOOL_AVAILABILITY,
    MutationAxis.CONTEXT_PRESSURE,
    MutationAxis.ORDER,
    MutationAxis.RECOVERY_OPPORTUNITY,
}

EXPECTED_REPRESENTATION_MODES = {
    "TYPED_FIELDS",
    "ORDERED_LIST",
    "LEDGER",
    "DECISION_TABLE",
    "DEPENDENCY_MATRIX",
    "GRAPH",
    "COMPACT_SUMMARY",
    "EXPLICIT_ALTERNATIVES",
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
    "src/inverted/capability_ratchet/surface_bootstrap.py",
    "src/inverted/capability_ratchet/mutation_core.py",
    "src/inverted/capability_ratchet/mutation_generator.py",
    "src/inverted/capability_ratchet/mutation_store.py",
    "src/inverted/capability_ratchet/mutation_planner.py",
    "src/inverted/capability_ratchet/mutation_replay.py",
    "src/inverted/capability_ratchet/mutation_analysis.py",
    "src/inverted/capability_ratchet/mutation_lab.py",
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
    "tests/test_capability_ratchet_surface_omission_audit.py",
    "tests/test_capability_ratchet_surface_value_modes.py",
    "tests/test_capability_ratchet_surface_completion.py",
    "tests/test_capability_ratchet_mutation_core.py",
    "tests/test_capability_ratchet_mutation_generator.py",
    "tests/test_capability_ratchet_mutation_store.py",
    "tests/test_capability_ratchet_mutation_planner.py",
    "tests/test_capability_ratchet_mutation_replay.py",
    "tests/test_capability_ratchet_mutation_analysis.py",
    "tests/test_capability_ratchet_mutation_lab.py",
    "tests/test_capability_ratchet_mutation_preflight.py",
    ".github/workflows/v3-stage6-completion.yml",
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
            cap = bool(
                isinstance(request, dict)
                and request.get("think") is True
                and isinstance(response, dict)
                and response.get("done_reason") == "length"
            )
        material = (
            cap
            or not observation.completed
            or not observation.semantic_pass
            or not observation.contract_pass
            or bool(observation.failure_classes)
        )
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


def _cli_options(command: str) -> set[str]:
    parser = _build_parser()
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        selected = action.choices.get(command)
        if selected is None:
            return set()
        return {
            option
            for item in selected._actions
            for option in item.option_strings
        }
    return set()


def _staged_run_paths() -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
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


def _stage5_semantic_checks(repo: Path, findings: list[str]) -> None:
    _add(
        findings,
        set(SurfaceAxis) != EXPECTED_SURFACE_AXES,
        "Stage-5 axis contract mismatch: "
        + repr(sorted(item.value for item in set(SurfaceAxis) ^ EXPECTED_SURFACE_AXES)),
    )
    _add(
        findings,
        set(SUPPORTED_SURFACE_AXES) != EXPECTED_SURFACE_AXES,
        "Stage-5 compiler axis coverage mismatch: "
        + repr(sorted(item.value for item in set(SUPPORTED_SURFACE_AXES) ^ EXPECTED_SURFACE_AXES)),
    )
    _add(
        findings,
        not hasattr(SurfaceEvidenceCompiler, "point_physical_calls"),
        "Stage-5 planner lacks exact frozen-fixture call estimator",
    )

    evidence_source = (repo / "src/inverted/capability_ratchet/surface_evidence.py").read_text(encoding="utf-8")
    compiler_source = (repo / "src/inverted/capability_ratchet/surface_interventions.py").read_text(encoding="utf-8")
    store_source = (repo / "src/inverted/capability_ratchet/surface_store.py").read_text(encoding="utf-8")
    planner_source = (repo / "src/inverted/capability_ratchet/surface_planner.py").read_text(encoding="utf-8")
    bootstrap_source = (repo / "src/inverted/capability_ratchet/surface_bootstrap.py").read_text(encoding="utf-8")
    cli_source = (repo / "src/inverted/capability_ratchet/cli.py").read_text(encoding="utf-8")

    _add(findings, "surface-replay-{candidate.surface_point_id}" not in evidence_source,
         "Stage-5 replay observations cannot recover generic surface-point identity")
    _add(findings, "_mechanism_intervention_ids" not in evidence_source or "_registered_baseline" not in evidence_source,
         "Stage-5 cannot reuse the proven Plan-2 mechanism replay as a surface baseline")
    _add(findings, "point_physical_calls" not in planner_source,
         "Stage-5 planner does not consume the frozen-fixture physical-call estimator")
    _add(findings, "registered originating intervention" not in store_source,
         "Stage-5 studies are not gated by their originating causal intervention")
    _add(findings, "requires a registered mechanism baseline value" not in store_source,
         "Stage-5 non-cognition studies can omit their matched mechanism baseline")
    _add(findings, "surface_delivery_events" not in store_source,
         "Stage-5 progressive/trigger studies are not gated by observable delivery events")
    missing_representation_modes = sorted(mode for mode in EXPECTED_REPRESENTATION_MODES if mode not in compiler_source)
    _add(findings, bool(missing_representation_modes),
         f"Stage-5 registered representation modes are incomplete: {missing_representation_modes}")
    _add(findings, "_scaled_context" not in compiler_source or "dose > 32.0" not in compiler_source,
         "Stage-5 context dose cannot safely probe overload above the proven baseline")
    _add(findings, "PRE_DECISION" not in compiler_source or "JUST_IN_TIME" not in compiler_source,
         "Stage-5 timing lacks preregistered pre-decision/just-in-time delivery modes")
    _add(
        findings,
        "progressive delivery requires context divisible" not in compiler_source.lower()
        or "progressive delivery requires registered context divisible" not in store_source.lower(),
        "Stage-5 progressive delivery lacks compile-time and persistence-time divisibility gates",
    )
    bootstrap_requirements = (
        "PromotionState.MOVEMENT",
        "compile_v2_priors",
        "SurfaceEvidenceKind.SAME_STATE_CAUSAL",
        "lab.prepare",
    )
    missing_bootstrap = [token for token in bootstrap_requirements if token not in bootstrap_source]
    _add(findings, bool(missing_bootstrap),
         f"Stage-5 zero-call bootstrap contract is incomplete: {missing_bootstrap}")
    forbidden_bootstrap = [token for token in ("QwenOllamaAdapter", "ReplayExecutor") if token in bootstrap_source]
    _add(findings, bool(forbidden_bootstrap),
         f"Stage-5 bootstrap contains live execution machinery: {forbidden_bootstrap}")
    plan_surface_options = _cli_options("plan-surface")
    missing_auto_options = sorted({"--auto-eligible", "--source"} - plan_surface_options)
    _add(findings, bool(missing_auto_options),
         f"Stage-5 historical auto-planning CLI options missing: {missing_auto_options}")
    _add(findings, "NO_ELIGIBLE_MECHANISMS" not in cli_source or "SURFACE_PLAN_READY" not in cli_source,
         "Stage-5 auto-planning lacks explicit eligibility status contract")
    incomplete = [
        marker
        for marker in ("not implemented", "does not support this surface axis yet")
        if marker in compiler_source.lower()
    ]
    _add(findings, bool(incomplete), f"incomplete Stage-5 execution markers remain: {incomplete}")


def _stage6_semantic_checks(repo: Path, findings: list[str]) -> bool:
    _add(
        findings,
        set(MutationAxis) != EXPECTED_MUTATION_AXES,
        "Stage-6 mutation-axis contract mismatch: "
        + repr(sorted(item.value for item in set(MutationAxis) ^ EXPECTED_MUTATION_AXES)),
    )
    probe = MutationFixture.create(
        failure_snapshot_id="audit-stage6-root",
        source_failure_snapshot_id="audit-stage6-root",
        source_state_hash="a" * 64,
        mechanism_id="audit-stage6-mechanism",
        mutation_axis=MutationAxis.DEPENDENCY_DEPTH,
        mutation_direction=MutationDirection.HARDER,
        mutation_value=4,
        structural_region_id="audit/region",
        model_visible_asset_sha256="b" * 64,
        oracle_asset_sha256="c" * 64,
        semantic_contract_hash="d" * 64,
        partition=Partition.DEVELOPMENT,
        origin=MutationOrigin.SYNTHETIC_NEIGHBORHOOD,
    )
    roundtrip_ok = from_payload(to_payload(probe)) == probe
    _add(findings, not roundtrip_ok, "Stage-6 MUTATION_FIXTURE parser/serializer roundtrip failed")

    plan_options = _cli_options("plan-mutations")
    show_options = _cli_options("show-mutations")
    run_options = _cli_options("run-mutations")
    zero_call_contract = (
        "--allow-model-calls" not in plan_options
        and "--allow-model-calls" not in show_options
        and "--allow-model-calls" in run_options
    )
    _add(findings, not zero_call_contract,
         "Stage-6 zero-call planning/inspection or live-call gate contract is incomplete")

    generator_source = (repo / "src/inverted/capability_ratchet/mutation_generator.py").read_text(encoding="utf-8")
    planner_source = (repo / "src/inverted/capability_ratchet/mutation_planner.py").read_text(encoding="utf-8")
    replay_source = (repo / "src/inverted/capability_ratchet/mutation_replay.py").read_text(encoding="utf-8")
    analyzer_source = (repo / "src/inverted/capability_ratchet/mutation_analysis.py").read_text(encoding="utf-8")
    lab_source = (repo / "src/inverted/capability_ratchet/mutation_lab.py").read_text(encoding="utf-8")

    _add(findings, "NO_MUTATION_TEMPLATE" not in lab_source,
         "Stage-6 lab can fail to expose missing deterministic template status")
    _add(findings, "FRESH" not in generator_source or "SEALED" not in generator_source,
         "Stage-6 generator lacks FRESH/SEALED synthetic-mutation exclusion")
    _add(findings, "protected" not in planner_source or "HARDER" not in planner_source,
         "Stage-6 planner lacks protected/harder challenge logic")
    _add(findings, "ReplayRequest" not in replay_source or "COUNTERFACTUAL" not in replay_source,
         "Stage-6 mutation transfer does not visibly compile through canonical replay requests")
    _add(findings, "Stage 6 permits only MOVEMENT -> TIER_CANDIDATE" not in analyzer_source,
         "Stage-6 promotion ceiling is not explicit")
    forbidden = [
        name for name in ("QwenOllamaAdapter", "httpx", "requests.", "urllib.request")
        if name in generator_source or name in planner_source or name in lab_source
    ]
    _add(findings, bool(forbidden), f"Stage-6 zero-call components contain live transport machinery: {forbidden}")
    return roundtrip_ok and zero_call_contract


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
        "plan-mutations", "show-mutations", "run-mutations",
    }
    _add(findings, _cli_commands() != required_commands,
         f"CLI command surface mismatch: {sorted(_cli_commands())}")
    _stage5_semantic_checks(repo, findings)
    stage6_contract_ok = _stage6_semantic_checks(repo, findings)
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
    _add(
        findings,
        not validation.ok,
        "replay store validation failed: "
        f"missing={validation.missing_assets} hash={validation.hash_mismatches} "
        f"lineage={validation.broken_lineage}",
    )
    records = store.records() if validation.ok else ()
    fixtures = [record for record in records if isinstance(record, FailureFixture)]
    mutation_fixtures = [record for record in records if isinstance(record, MutationFixture)]
    results = [record for record in records if isinstance(record, ReplayResult)]
    promotion_events = [record for record in records if isinstance(record, PromotionEvent)]
    actual_ids = {
        fixture.focus_observation_id
        for fixture in fixtures
        if fixture.parent_failure_snapshot_id is None
    }
    _add(
        findings,
        actual_ids != expected_ids,
        "historical fixture coverage mismatch: "
        f"missing={len(expected_ids - actual_ids)} extra={len(actual_ids - expected_ids)}",
    )
    capped_actual = sum(
        1
        for fixture in fixtures
        if fixture.parent_failure_snapshot_id is None
        and "REASONING_CAP_EXHAUSTION" in fixture.failure_classes
    )
    _add(findings, capped_actual != expected_capped,
         f"reasoning-cap fixture coverage mismatch: actual={capped_actual} expected={expected_capped}")

    synthetic_fresh_sealed = [
        fixture
        for fixture in mutation_fixtures
        if fixture.origin is MutationOrigin.SYNTHETIC_NEIGHBORHOOD
        and fixture.partition in {Partition.FRESH, Partition.SEALED}
    ]
    _add(findings, bool(synthetic_fresh_sealed),
         f"Stage-6 synthetic FRESH/SEALED mutation fixtures: {len(synthetic_fresh_sealed)}")
    stage6_certified = [
        event
        for event in promotion_events
        if event.metadata.get("stage") == "STAGE_6"
        and event.to_state is PromotionState.CERTIFIED
    ]
    _add(findings, bool(stage6_certified),
         f"Stage-6 CERTIFIED promotion events are forbidden: {len(stage6_certified)}")

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
    for fixture in mutation_fixtures:
        referenced_assets.add(fixture.model_visible_asset_sha256)
        referenced_assets.add(fixture.oracle_asset_sha256)
    for result in results:
        referenced_assets.add(result.output_asset_sha256)
        referenced_assets.add(result.raw_call_asset_sha256)
    asset_root = store.asset_root
    asset_files = {path.stem for path in asset_root.glob("*.json")} if asset_root.exists() else set()
    orphan_assets = sorted(asset_files - referenced_assets)
    _add(findings, bool(orphan_assets),
         f"orphan replay assets: count={len(orphan_assets)} sample={orphan_assets[:5]}")

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
        "stage5_axis_count": len(EXPECTED_SURFACE_AXES),
        "stage5_compiler_axis_count": len(SUPPORTED_SURFACE_AXES),
        "stage5_representation_mode_count": len(EXPECTED_REPRESENTATION_MODES),
        "stage5_auto_plan_contract": {"--auto-eligible", "--source"}.issubset(_cli_options("plan-surface")),
        "stage6_axis_count": len(EXPECTED_MUTATION_AXES),
        "stage6_mutation_fixture_roundtrip": stage6_contract_ok,
        "stage6_synthetic_fresh_sealed_count": len(synthetic_fresh_sealed),
        "stage6_certified_event_count": len(stage6_certified),
        "stage6_zero_call_plan_contract": (
            "--allow-model-calls" not in _cli_options("plan-mutations")
            and "--allow-model-calls" not in _cli_options("show-mutations")
            and "--allow-model-calls" in _cli_options("run-mutations")
        ),
        "stage6_registered_mutation_fixtures": len(mutation_fixtures),
    }
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
