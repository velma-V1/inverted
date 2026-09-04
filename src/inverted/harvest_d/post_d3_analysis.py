from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


_REQUIRED_ZERO_CALL_ARTIFACTS = (
    "d3_causal_claim_graph.jsonl",
    "d3_claim_evidence_edges.jsonl",
    "d3_decision_boundary_telemetry.jsonl",
    "d3_evidence_saturation.jsonl",
    "d3_model_behavior_features.jsonl",
    "d3_recovery_trajectories.jsonl",
    "d3_sequential_analysis_state.jsonl",
    "d3_uncovered_space.jsonl",
)

_REQUIRED_FROZEN_SOURCE = (
    "00-HARVEST-D-D3-MASTER-INDEX.json",
    "d3_final_report.json",
    "d3_call_ledger.jsonl",
    "d3_normalized_model_calls.jsonl",
    "d3_runtime_telemetry.jsonl",
    "SHA256SUMS.csv",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_manifest(root: Path) -> int:
    manifest_path = root / "SHA256SUMS.csv"
    try:
        with manifest_path.open("r", encoding="utf-8", newline="") as handle:
            manifest_rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise ValueError("frozen D3-v1 checksum manifest is unreadable") from exc
    if not manifest_rows or set(manifest_rows[0]) != {"file", "bytes", "sha256"}:
        raise ValueError("frozen D3-v1 checksum manifest has an invalid schema")
    manifest = {str(row["file"]): row for row in manifest_rows}
    for name in _REQUIRED_FROZEN_SOURCE:
        if name == "SHA256SUMS.csv":
            continue
        if name not in manifest:
            raise ValueError(f"frozen D3-v1 checksum manifest does not cover required artifact: {name}")
    for name, row in manifest.items():
        path = root / name
        if not path.is_file():
            raise ValueError(f"frozen D3-v1 checksum artifact is missing: {name}")
        actual_bytes = path.stat().st_size
        actual_sha = _sha256(path)
        if actual_bytes != int(row["bytes"]) or actual_sha != str(row["sha256"]):
            raise ValueError(f"frozen D3-v1 checksum mismatch: {name}")
    return len(manifest_rows)


def validate_frozen_d3_v1(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    missing = [name for name in _REQUIRED_FROZEN_SOURCE if not (root / name).is_file()]
    if missing:
        raise ValueError(f"frozen D3-v1 evidence package is incomplete; missing: {missing}")

    # Integrity is the first gate: never parse or reason over a package whose
    # frozen bytes no longer match the manifest that closed D3-v1.
    manifest_entries = _verify_manifest(root)

    try:
        master = json.loads((root / "00-HARVEST-D-D3-MASTER-INDEX.json").read_text(encoding="utf-8"))
        report = json.loads((root / "d3_final_report.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("frozen D3-v1 master/report is unreadable") from exc

    if str(master.get("mode")) != "REAL_LOCAL" or str(report.get("mode")) != "REAL_LOCAL":
        raise ValueError("frozen D3-v1 source must be a REAL_LOCAL empirical run")
    if not bool(master.get("audit_passed")) or not bool(report.get("audit_passed")):
        raise ValueError("frozen D3-v1 source did not pass its recorded audit")
    if not bool(master.get("empirical_claims_authorized")) or not bool(report.get("empirical_claims_authorized")):
        raise ValueError("frozen D3-v1 source did not authorize empirical claims")

    ledger = _read_jsonl(root / "d3_call_ledger.jsonl")
    calls = _read_jsonl(root / "d3_normalized_model_calls.jsonl")
    runtime = _read_jsonl(root / "d3_runtime_telemetry.jsonl")
    expected_calls = int(master.get("physical_model_calls", -1))
    if expected_calls <= 0:
        raise ValueError("frozen D3-v1 source has no physical calls")
    if int(report.get("physical_model_calls", -1)) != expected_calls:
        raise ValueError("frozen D3-v1 master/report physical-call counts disagree")
    if len(ledger) != expected_calls or len(calls) != expected_calls or len(runtime) != expected_calls:
        raise ValueError(
            "frozen D3-v1 call artifacts are incomplete: "
            f"expected={expected_calls} ledger={len(ledger)} normalized={len(calls)} runtime={len(runtime)}"
        )
    if any(not bool(row.get("capture_complete", False)) for row in ledger):
        raise ValueError("frozen D3-v1 ledger contains incomplete captures")

    return {
        "physical_model_calls": expected_calls,
        "master": master,
        "report": report,
        "manifest_entries": manifest_entries,
        "source_verified": True,
    }


def analyze_d3_v1(root: Path, output: Path) -> dict[str, object]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if root == output:
        raise ValueError("post-D3 analysis output must not overwrite frozen D3-v1 evidence")

    validation = validate_frozen_d3_v1(root)
    output.mkdir(parents=True, exist_ok=True)
    calls = _read_jsonl(root / "d3_normalized_model_calls.jsonl")
    runtime = _read_jsonl(root / "d3_runtime_telemetry.jsonl")

    disposition_correct = sum(
        1 for row in calls
        if isinstance(row.get("score"), dict) and bool(row["score"].get("disposition_correct", False))
    )
    qwen_context_exhausted = 0
    for row in runtime:
        model = str(row.get("model", "")).lower()
        if "qwen3.5" not in model:
            continue
        done_reason = str(row.get("done_reason", "")).lower()
        prompt_tokens = int(row.get("prompt_eval_count", 0) or 0)
        eval_tokens = int(row.get("eval_count", 0) or 0)
        if done_reason == "length" or (prompt_tokens + eval_tokens >= 4096 and eval_tokens > 0):
            qwen_context_exhausted += 1

    empty_required = [name for name in _REQUIRED_ZERO_CALL_ARTIFACTS
                      if not (root / name).exists() or (root / name).stat().st_size == 0]
    findings: dict[str, object] = {
        "protocol": "D3-V1-POSTHOC-SALVAGE", "source_root": str(root),
        "source_verified": bool(validation["source_verified"]), "physical_calls_observed": len(calls),
        "disposition_correct_calls": disposition_correct, "qwen_context_exhausted": qwen_context_exhausted,
        "empty_required_artifacts": empty_required, "input_mutated": False,
    }
    gaps = [
        {"gap_id": "GAP-QWEN-DELIBERATION", "class": "MEASUREMENT_OR_ORACLE_RISK", "destination": "D4",
         "observed_signal": {"context_exhausted": qwen_context_exhausted},
         "decision": "freeze a Qwen call policy before closure confirmation"},
        {"gap_id": "GAP-DISPOSITION-CONTRACT", "class": "MEASUREMENT_OR_ORACLE_RISK", "destination": "D3-CLOSURE-v2",
         "observed_signal": {"disposition_correct_calls": disposition_correct},
         "decision": "move disposition to deterministic system semantics"},
        {"gap_id": "GAP-ASSISTANCE-CAUSALITY", "class": "UNRESOLVED_DISCRIMINATE", "destination": "D3-CLOSURE-v2",
         "decision": "measure pre-decision assistance against matched controls"},
        {"gap_id": "GAP-RECOVERY-TRAJECTORIES", "class": "COVERAGE_HOLE", "destination": "D3-CLOSURE-v2",
         "decision": "measure prevention and recovery trajectories separately"},
        {"gap_id": "GAP-MINIMUM-SUPPORT", "class": "MINIMUM_SUPPORT_UNKNOWN", "destination": "D3-CLOSURE-v2",
         "decision": "localize MSIP/MRS and model-substitution boundary"},
    ]
    decision_map = {
        "freeze_d3_v1": True, "source_checksum_verified": True, "repair_measurement_harness": True,
        "run_d4_before_qwen_confirmation": True, "run_d3_closure_v2": True,
        "max_d4_calls": 48, "max_closure_calls": 200, "protected_confirmation_calls": 48,
    }
    lineage = {"source_protocol": "D3-v1", "derived_protocol": "D3-V1-POSTHOC-SALVAGE",
               "claims_are_recomputed": True, "claims_are_original_d3_v1": False}
    routing = {gap["gap_id"]: gap["destination"] for gap in gaps}
    budget = {"physical_call_ceiling": 200, "protected_confirmation_calls": 48,
              "rule": "calls are ceilings, not quotas; zero-call analysis precedes inference"}

    _write_json(output / "post_d3_zero_call_findings.json", findings)
    _write_json(output / "post_d3_gap_registry.json", gaps)
    _write_json(output / "post_d3_decision_impact_map.json", decision_map)
    _write_json(output / "post_d3_hypothesis_lineage.json", lineage)
    _write_json(output / "post_d3_followup_routing.json", routing)
    _write_json(output / "post_d3_followup_budget_justification.json", budget)
    (output / "post_d3_followup_test_spec.md").write_text(
        "# Post-D3 Follow-up Test Spec\n\n"
        "Freeze D3-v1. Verify its manifest. Repair the measurement boundary, resolve Qwen call policy in D4, "
        "then run D3-CLOSURE-v2 only against decision-relevant unresolved gaps.\n", encoding="utf-8")
    return findings
