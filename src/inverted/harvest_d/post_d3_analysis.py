from __future__ import annotations

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


def analyze_d3_v1(root: Path, output: Path) -> dict[str, object]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if root == output:
        raise ValueError("post-D3 analysis output must not overwrite frozen D3-v1 evidence")

    output.mkdir(parents=True, exist_ok=True)
    calls = _read_jsonl(root / "d3_normalized_model_calls.jsonl")
    runtime = _read_jsonl(root / "d3_runtime_telemetry.jsonl")

    disposition_correct = sum(
        1
        for row in calls
        if isinstance(row.get("score"), dict)
        and bool(row["score"].get("disposition_correct", False))
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

    empty_required = [
        name
        for name in _REQUIRED_ZERO_CALL_ARTIFACTS
        if not (root / name).exists() or (root / name).stat().st_size == 0
    ]

    findings: dict[str, object] = {
        "protocol": "D3-V1-POSTHOC-SALVAGE",
        "source_root": str(root),
        "physical_calls_observed": len(calls),
        "disposition_correct_calls": disposition_correct,
        "qwen_context_exhausted": qwen_context_exhausted,
        "empty_required_artifacts": empty_required,
        "input_mutated": False,
    }

    gaps = [
        {
            "gap_id": "GAP-QWEN-DELIBERATION",
            "class": "MEASUREMENT_OR_ORACLE_RISK",
            "destination": "D4",
            "observed_signal": {"context_exhausted": qwen_context_exhausted},
            "decision": "freeze a Qwen call policy before closure confirmation",
        },
        {
            "gap_id": "GAP-DISPOSITION-CONTRACT",
            "class": "MEASUREMENT_OR_ORACLE_RISK",
            "destination": "D3-CLOSURE-v2",
            "observed_signal": {"disposition_correct_calls": disposition_correct},
            "decision": "move disposition to deterministic system semantics",
        },
        {
            "gap_id": "GAP-ASSISTANCE-CAUSALITY",
            "class": "UNRESOLVED_DISCRIMINATE",
            "destination": "D3-CLOSURE-v2",
            "decision": "measure pre-decision assistance against matched controls",
        },
        {
            "gap_id": "GAP-RECOVERY-TRAJECTORIES",
            "class": "COVERAGE_HOLE",
            "destination": "D3-CLOSURE-v2",
            "decision": "measure prevention and recovery trajectories separately",
        },
        {
            "gap_id": "GAP-MINIMUM-SUPPORT",
            "class": "MINIMUM_SUPPORT_UNKNOWN",
            "destination": "D3-CLOSURE-v2",
            "decision": "localize MSIP/MRS and model-substitution boundary",
        },
    ]

    decision_map = {
        "freeze_d3_v1": True,
        "repair_measurement_harness": True,
        "run_d4_before_qwen_confirmation": True,
        "run_d3_closure_v2": True,
        "max_d4_calls": 48,
        "max_closure_calls": 200,
        "protected_confirmation_calls": 48,
    }
    lineage = {
        "source_protocol": "D3-v1",
        "derived_protocol": "D3-V1-POSTHOC-SALVAGE",
        "claims_are_recomputed": True,
        "claims_are_original_d3_v1": False,
    }
    routing = {gap["gap_id"]: gap["destination"] for gap in gaps}
    budget = {
        "physical_call_ceiling": 200,
        "protected_confirmation_calls": 48,
        "rule": "calls are ceilings, not quotas; zero-call analysis precedes inference",
    }

    _write_json(output / "post_d3_zero_call_findings.json", findings)
    _write_json(output / "post_d3_gap_registry.json", gaps)
    _write_json(output / "post_d3_decision_impact_map.json", decision_map)
    _write_json(output / "post_d3_hypothesis_lineage.json", lineage)
    _write_json(output / "post_d3_followup_routing.json", routing)
    _write_json(output / "post_d3_followup_budget_justification.json", budget)
    (output / "post_d3_followup_test_spec.md").write_text(
        "# Post-D3 Follow-up Test Spec\n\n"
        "Freeze D3-v1. Repair the measurement boundary, resolve Qwen call policy in D4, "
        "then run D3-CLOSURE-v2 only against decision-relevant unresolved gaps.\n",
        encoding="utf-8",
    )
    return findings
