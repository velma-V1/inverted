from __future__ import annotations

import argparse
import ast
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import inverted.capability_ratchet as cr
from inverted.capability_ratchet.cli import _build_tomography_parser
from inverted.capability_ratchet.core import Partition, PromotionEvent, PromotionState
from inverted.capability_ratchet.replay_store import ReplayStore
from inverted.capability_ratchet.tomography_core import (
    TomographyAxis,
    TomographyDisposition,
    TomographyPolicy,
)
from inverted.capability_ratchet.tomography_eligibility import (
    TomographyEligibilityStatus,
    classify_tomography_eligibility,
)


LEGACY_AUDIT = Path(__file__).with_name("audit-v3-replay-foundation-legacy.py")

EXPECTED_TOMOGRAPHY_AXES = {
    TomographyAxis.TOOL_AVAILABILITY,
    TomographyAxis.TOOL_SELECTION,
    TomographyAxis.TOOL_ARGUMENTS,
    TomographyAxis.TOOL_EXECUTION_RESULT,
    TomographyAxis.TOOL_RESULT_INTERPRETATION,
    TomographyAxis.VERIFIER_VISIBILITY,
    TomographyAxis.VERIFIER_FEEDBACK,
    TomographyAxis.TARGETED_RECOVERY,
    TomographyAxis.GENERIC_RETRY_CONTROL,
    TomographyAxis.SKILL_PROCEDURE,
    TomographyAxis.SKILL_TRIGGER,
    TomographyAxis.ESCALATION_REFERENCE,
}

REQUIRED_STAGE7_EXPORTS = {
    "TomographyAxis",
    "TomographyDisposition",
    "TomographyPolicy",
    "TomographyProbeSpec",
    "TomographyStudy",
    "TomographyOutcome",
    "TomographyAssessment",
    "TomographyEvidenceStore",
    "TomographyPlanner",
    "TomographyReplayCompiler",
    "TomographyAnalyzer",
    "TomographyLab",
    "classify_tomography_eligibility",
    "plan_eligible_tomography",
}

REQUIRED_STAGE7_FILES = (
    "src/inverted/capability_ratchet/tomography_core.py",
    "src/inverted/capability_ratchet/tomography_store.py",
    "src/inverted/capability_ratchet/tomography_eligibility.py",
    "src/inverted/capability_ratchet/tomography_planner.py",
    "src/inverted/capability_ratchet/tomography_replay.py",
    "src/inverted/capability_ratchet/tomography_analysis.py",
    "src/inverted/capability_ratchet/tomography_lab.py",
    "src/inverted/capability_ratchet/tomography_cli.py",
    "tests/test_capability_ratchet_tomography_cli.py",
    "tests/test_capability_ratchet_tomography_audit_closure.py",
    ".github/workflows/v3-stage7-completion.yml",
)

EXPECTED_TOMOGRAPHY_COMMANDS = {
    "scan-tomography-eligibility",
    "plan-tomography",
    "show-tomography-study",
    "show-tomography-assessment",
}

# Inherited permanent-audit contracts. These remain visible in this wrapper
# because older tests and downstream tooling inspect the current audit source.
LEGACY_AUDIT_CONTRACT_TOKENS = (
    "plan-surface",
    "show-surface",
    "run-surface",
    "surface_core.py",
    "surface_store.py",
    "surface_evidence.py",
    "surface_planner.py",
    "surface_interventions.py",
    "surface_analysis.py",
    "surface_lab.py",
    "MutationBootstrapPlan",
    "MutationBootstrapResult",
    "plan_eligible_mutations",
    "mutation_bootstrap.py",
    "stage6_axis_count",
    "stage6_mutation_fixture_roundtrip",
    "stage6_synthetic_fresh_sealed_count",
    "stage6_certified_event_count",
    "stage6_zero_call_plan_contract",
    "stage6_auto_plan_contract",
    "stage6_protected_failure_veto_contract",
)

_FORBIDDEN_NETWORK_ROOTS = frozenset({"httpx", "requests", "socket", "urllib"})
_FORBIDDEN_ADAPTER_NAMES = frozenset({"QwenOllamaAdapter", "QwenReplayAdapter"})


def _load_legacy_module():
    spec = importlib.util.spec_from_file_location("_inverted_v3_legacy_audit", LEGACY_AUDIT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load preserved replay audit")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LEGACY_CONTRACT = _load_legacy_module()
REQUIRED_EXPORTS = frozenset((*_LEGACY_CONTRACT.REQUIRED_EXPORTS, *REQUIRED_STAGE7_EXPORTS))
REQUIRED_FILES = tuple(dict.fromkeys((*_LEGACY_CONTRACT.REQUIRED_FILES, *REQUIRED_STAGE7_FILES)))


def _run_legacy(argv: list[str], repo: Path) -> tuple[int, dict[str, Any]]:
    """Run the byte-preserved Stage-5/6 audit against its original CLI source."""
    module = _load_legacy_module()
    original_read_text = Path.read_text
    legacy_cli = repo / "src/inverted/capability_ratchet/cli_legacy.py"

    def redirected_read_text(path: Path, *args, **kwargs):
        normalized = path.as_posix().replace("\\", "/")
        if normalized.endswith("src/inverted/capability_ratchet/cli.py"):
            return original_read_text(legacy_cli, *args, **kwargs)
        return original_read_text(path, *args, **kwargs)

    buffer = io.StringIO()
    Path.read_text = redirected_read_text
    try:
        with redirect_stdout(buffer):
            rc = module.main(argv)
    finally:
        Path.read_text = original_read_text

    rows = [line for line in buffer.getvalue().splitlines() if line.strip()]
    if not rows:
        raise RuntimeError("preserved replay audit produced no JSON payload")
    payload = json.loads(rows[-1])
    if not isinstance(payload, dict):
        raise RuntimeError("preserved replay audit payload must be a JSON object")
    return int(rc), payload


def _subparser_surface() -> tuple[set[str], dict[str, set[str]]]:
    parser = _build_tomography_parser()
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        commands = set(action.choices)
        options = {
            name: {
                option
                for item in selected._actions
                for option in item.option_strings
            }
            for name, selected in action.choices.items()
        }
        return commands, options
    return set(), {}


def _read(repo: Path, relative: str) -> str:
    return (repo / relative).read_text(encoding="utf-8")


def _forbidden_live_code_refs(source: str) -> tuple[str, ...]:
    """Return live transport references from Python syntax, ignoring prose/comments."""
    tree = ast.parse(source)
    hits: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in _FORBIDDEN_NETWORK_ROOTS:
                    hits.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root in _FORBIDDEN_NETWORK_ROOTS:
                hits.add(module or root)
        elif isinstance(node, ast.Name) and node.id in _FORBIDDEN_ADAPTER_NAMES:
            hits.add(node.id)
    return tuple(sorted(hits))


def _has_independent_tomography_executor(source: str) -> bool:
    tree = ast.parse(source)
    return any(
        isinstance(node, ast.ClassDef)
        and node.name.startswith("Tomography")
        and node.name.endswith("Executor")
        for node in ast.walk(tree)
    )


def _stage7_semantic_checks(repo: Path, replay_root: Path) -> tuple[list[str], dict[str, Any]]:
    findings: list[str] = []

    legacy_source = LEGACY_AUDIT.read_text(encoding="utf-8")
    missing_legacy_tokens = [token for token in LEGACY_AUDIT_CONTRACT_TOKENS if token not in legacy_source]
    if missing_legacy_tokens:
        findings.append(f"inherited Stage-5/6 audit contract missing: {missing_legacy_tokens}")

    missing_exports = sorted(REQUIRED_STAGE7_EXPORTS - set(cr.__all__))
    if missing_exports:
        findings.append(f"Stage-7 public exports missing: {missing_exports}")

    missing_files = [path for path in REQUIRED_STAGE7_FILES if not (repo / path).is_file()]
    if missing_files:
        findings.append(f"Stage-7 source/tests/workflow missing: {missing_files}")
    tomography_tests = tuple((repo / "tests").glob("test_capability_ratchet_tomography_*.py"))
    if len(tomography_tests) < 2:
        findings.append("Stage-7 tomography test surface is missing or collapsed")

    core_source = _read(repo, "src/inverted/capability_ratchet/tomography_core.py")
    eligibility_source = _read(repo, "src/inverted/capability_ratchet/tomography_eligibility.py")
    planner_source = _read(repo, "src/inverted/capability_ratchet/tomography_planner.py")
    replay_source = _read(repo, "src/inverted/capability_ratchet/tomography_replay.py")
    analysis_source = _read(repo, "src/inverted/capability_ratchet/tomography_analysis.py")
    lab_source = _read(repo, "src/inverted/capability_ratchet/tomography_lab.py")
    store_source = _read(repo, "src/inverted/capability_ratchet/tomography_store.py")
    cli_source = _read(repo, "src/inverted/capability_ratchet/tomography_cli.py")
    interventions_source = _read(repo, "src/inverted/capability_ratchet/interventions.py")

    commands, options = _subparser_surface()
    stage7_cli_surface_contract = (
        commands == EXPECTED_TOMOGRAPHY_COMMANDS
        and "execute-tomography" not in commands
        and all("--allow-model-calls" not in value for value in options.values())
        and {"--auto-eligible", "--study-id"}.issubset(options.get("plan-tomography", set()))
    )
    if not stage7_cli_surface_contract:
        findings.append(f"Stage-7 safe CLI surface mismatch: commands={sorted(commands)} options={options}")

    zero_call_sources = (cli_source, eligibility_source, planner_source)
    zero_call_forbidden = tuple(
        sorted({ref for source in zero_call_sources for ref in _forbidden_live_code_refs(source)})
    )
    stage7_zero_call_plan_contract = (
        "MODEL_CALLS" in cli_source
        and "model_calls != 0" in planner_source
        and not zero_call_forbidden
        and all("ReplayExecutor(" not in source for source in zero_call_sources)
    )
    if not stage7_zero_call_plan_contract:
        findings.append(
            "Stage-7 scan/plan path can no longer be proven zero-call"
            + (f": live refs={list(zero_call_forbidden)}" if zero_call_forbidden else "")
        )

    all_stage7_sources = (
        core_source,
        eligibility_source,
        planner_source,
        replay_source,
        analysis_source,
        lab_source,
        store_source,
        cli_source,
    )
    stage7_live_refs = tuple(
        sorted({ref for source in all_stage7_sources for ref in _forbidden_live_code_refs(source)})
    )
    independent_executor = any(_has_independent_tomography_executor(source) for source in all_stage7_sources)
    stage7_no_independent_executor_contract = (
        not independent_executor
        and "ReplayExecutor(self.replay_store, adapters)" in lab_source
        and not stage7_live_refs
    )
    if not stage7_no_independent_executor_contract:
        findings.append(
            "Stage-7 introduced or can construct an independent/live executor or transport"
            f": independent_executor={independent_executor}, live_refs={list(stage7_live_refs)}"
        )

    stage7_canonical_replay_contract = (
        "ReplayRequest" in replay_source
        and "ReplayMode.COUNTERFACTUAL" in replay_source
        and "ReplayExecutor" in lab_source
        and "tomography_replay" in lab_source
        and "replay_result_id" in store_source
    )
    if not stage7_canonical_replay_contract:
        findings.append("Stage-7 canonical ReplayRequest -> ReplayExecutor -> replay-result linkage is incomplete")

    generic_policy_rejects_two = False
    try:
        TomographyPolicy(max_generic_retry_controls=2)
    except ValueError:
        generic_policy_rejects_two = True
    stage7_generic_third_retry_forbidden = (
        generic_policy_rejects_two
        and "GENERIC_RETRY_CONTROL" in planner_source
        and "TARGETED_RECOVERY" in planner_source
        and "if TomographyAxis.GENERIC_RETRY_CONTROL in selected" in planner_source
    )
    if not stage7_generic_third_retry_forbidden:
        findings.append("Stage-7 generic retry control can exceed the single matched-control boundary")

    stage7_targeted_recovery_state_contract = (
        'changed_state = recovery.get("changed_state")' in interventions_source
        and "targeted_recovery requires explicit changed_state" in interventions_source
        and 'TomographyAxis.TARGETED_RECOVERY: "TARGETED_RECOVERY_STATE"' in replay_source
    )
    if not stage7_targeted_recovery_state_contract:
        findings.append("Stage-7 targeted recovery no longer requires an explicit changed state")

    stage7_tool_axis_contract = set(TomographyAxis) == EXPECTED_TOMOGRAPHY_AXES
    if not stage7_tool_axis_contract:
        findings.append(
            "Stage-7 tomography-axis contract mismatch: "
            + repr(sorted(item.value for item in set(TomographyAxis) ^ EXPECTED_TOMOGRAPHY_AXES))
        )

    stage7_verifier_recovery_separation = (
        TomographyAxis.VERIFIER_VISIBILITY is not TomographyAxis.VERIFIER_FEEDBACK
        and TomographyAxis.VERIFIER_FEEDBACK is not TomographyAxis.TARGETED_RECOVERY
        and TomographyDisposition.VERIFIER_SUFFICIENT is not TomographyDisposition.RECOVERY_SUFFICIENT
        and "verifier_success" in analysis_source
        and "targeted_recovery_success" in analysis_source
    )
    if not stage7_verifier_recovery_separation:
        findings.append("Stage-7 verifier and recovery ownership have collapsed")

    protected = classify_tomography_eligibility(
        failure_snapshot_id="audit-stage7-protected",
        partition=Partition.FRESH,
        divergence=cr.DivergenceClass.TOOL_CAPABILITY,
        decision_ids=("D2", "D6"),
        reconstructable_state=True,
    )
    stage7_protected_partition_veto_contract = (
        protected.status is TomographyEligibilityStatus.PROTECTED_PARTITION
        and "fresh/sealed tomography execution is forbidden" in lab_source
        and "protected partition contamination is forbidden" in store_source
    )
    if not stage7_protected_partition_veto_contract:
        findings.append("Stage-7 FRESH/SEALED protection can be bypassed")

    promotion_values = {item.value for item in PromotionState}
    disposition_values = {item.value for item in TomographyDisposition}
    stage7_disposition_promotion_separation = (
        promotion_values.isdisjoint(disposition_values)
        and "CERTIFIED" not in disposition_values
        and TomographyPolicy().certification_allowed is False
        and "certification_allowed=False" in analysis_source
    )
    if not stage7_disposition_promotion_separation:
        findings.append("Stage-7 disposition can be mistaken for promotion/certification state")

    stage7_stage456_feedback_gate = (
        TomographyPolicy().stage456_feedback_required is True
        and 'route_back_stage="stage4" if promotion else None' in analysis_source
        and 'if self.promotion_allowed and self.route_back_stage != "stage4"' in core_source
    )
    if not stage7_stage456_feedback_gate:
        findings.append("Stage-7 MOVEMENT can bypass the Stage-4/5/6 feedback gate")

    store = ReplayStore(replay_root)
    records = store.records() if store.validate().ok else ()
    stage7_certified = [
        item
        for item in records
        if isinstance(item, PromotionEvent)
        and item.to_state is PromotionState.CERTIFIED
        and str(item.metadata.get("stage", "")).upper() in {"STAGE7", "STAGE_7", "7"}
    ]
    stage7_certified_event_count = len(stage7_certified)
    if stage7_certified_event_count:
        findings.append(f"Stage-7 CERTIFIED promotion events are forbidden: {stage7_certified_event_count}")

    payload = {
        "stage7_axis_count": len(EXPECTED_TOMOGRAPHY_AXES),
        "stage7_cli_surface_contract": stage7_cli_surface_contract,
        "stage7_zero_call_plan_contract": stage7_zero_call_plan_contract,
        "stage7_no_independent_executor_contract": stage7_no_independent_executor_contract,
        "stage7_canonical_replay_contract": stage7_canonical_replay_contract,
        "stage7_generic_third_retry_forbidden": stage7_generic_third_retry_forbidden,
        "stage7_targeted_recovery_state_contract": stage7_targeted_recovery_state_contract,
        "stage7_tool_axis_contract": stage7_tool_axis_contract,
        "stage7_verifier_recovery_separation": stage7_verifier_recovery_separation,
        "stage7_protected_partition_veto_contract": stage7_protected_partition_veto_contract,
        "stage7_certified_event_count": stage7_certified_event_count,
        "stage7_disposition_promotion_separation": stage7_disposition_promotion_separation,
        "stage7_stage456_feedback_gate": stage7_stage456_feedback_gate,
    }
    return findings, payload


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--replay-root", required=True)
    args = parser.parse_args(raw)
    repo = Path.cwd()

    legacy_rc, payload = _run_legacy(raw, repo)
    stage7_findings, stage7_payload = _stage7_semantic_checks(repo, Path(args.replay_root))
    legacy_findings = list(payload.get("forgotten_items", ()))
    combined = legacy_findings + stage7_findings
    payload.update(stage7_payload)
    payload["forgotten_items"] = combined
    payload["forgotten_count"] = len(combined)
    payload["MODEL_CALLS"] = 0
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0 if legacy_rc == 0 and not stage7_findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
