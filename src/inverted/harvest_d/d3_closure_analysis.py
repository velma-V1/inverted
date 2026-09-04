from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .d3_closure_r0 import build_r0_package


_DERIVED_JSON_OUTPUTS = (
    "closure_information_value_map.json",
    "closure_minimum_sufficient_information_packet.json",
    "closure_assistance_value_map.json",
    "closure_minimum_required_scaffolding.json",
    "closure_disposition_compiler_evidence.json",
    "closure_recovery_policy_map.json",
    "closure_model_substitution_frontier.json",
    "closure_negative_transfer_map.json",
    "closure_routing_policy_evidence.json",
)

_EVENT_OUTPUTS = (
    "closure_call_ledger.jsonl",
    "closure_campaign_journal.jsonl",
    "closure_system_events.jsonl",
    "closure_sequential_decisions.jsonl",
    "closure_recovery_trajectories.jsonl",
    "closure_raw_model_requests.jsonl",
    "closure_raw_model_responses.jsonl",
    "closure_normalized_model_calls.jsonl",
    "closure_runtime_telemetry.jsonl",
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return dict(value) if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ensure_closure_output_skeleton(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in _EVENT_OUTPUTS:
        path = root / name
        if not path.exists():
            path.write_text("", encoding="utf-8")
    for name in _DERIVED_JSON_OUTPUTS:
        path = root / name
        if not path.exists():
            _write_json(path, {"state": "UNRESOLVED", "protocol": "D3-CLOSURE-v2", "evidence": []})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _paired_counts(rows: list[dict[str, Any]], arm_a: str, arm_b: str) -> dict[str, int]:
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        arm = str(row.get("arm", ""))
        if arm not in {arm_a, arm_b}:
            continue
        grouped[(str(row.get("model_key")), str(row.get("case_id")))][arm] = row
    both = a_only = b_only = neither = 0
    for pair in grouped.values():
        if arm_a not in pair or arm_b not in pair:
            continue
        a = bool(pair[arm_a].get("verified_outcome_correct"))
        b = bool(pair[arm_b].get("verified_outcome_correct"))
        if a and b:
            both += 1
        elif a:
            a_only += 1
        elif b:
            b_only += 1
        else:
            neither += 1
    return {"both_correct": both, f"{arm_a}_only": a_only, f"{arm_b}_only": b_only, "neither": neither}


def _derive_outputs(root: Path) -> dict[str, Any]:
    rows = _read_jsonl(root / "closure_normalized_model_calls.jsonl")
    recovery = _read_jsonl(root / "closure_recovery_trajectories.jsonl")

    info = _paired_counts(rows, "INFO_MINIMUM", "INFO_FULL")
    info_pairs = sum(info.values())
    min_wins = info.get("INFO_MINIMUM_only", 0)
    full_wins = info.get("INFO_FULL_only", 0)
    info_state = "CANDIDATE_MINIMUM" if info_pairs and min_wins >= full_wins else "UNRESOLVED"
    _write_json(root / "closure_information_value_map.json", {
        "protocol": "D3-CLOSURE-v2", "state": info_state, "paired_observations": info_pairs, "evidence": info
    })
    _write_json(root / "closure_minimum_sufficient_information_packet.json", {
        "protocol": "D3-CLOSURE-v2",
        "state": "CANDIDATE" if info_state == "CANDIDATE_MINIMUM" else "UNRESOLVED",
        "candidate": "MINIMUM" if info_state == "CANDIDATE_MINIMUM" else None,
        "note": "candidate only; promotion requires the applicable fresh/generalization decision gate",
        "evidence": info,
    })

    assistance_by_mechanism: dict[str, dict[str, int]] = {}
    mechanisms = sorted({
        str(row.get("arm", "")).split("_")[1]
        for row in rows
        if str(row.get("arm", "")).startswith("ASSIST_A")
    })
    for mechanism in mechanisms:
        assistance_by_mechanism[mechanism] = _paired_counts(
            rows, f"ASSIST_{mechanism}_TARGET", f"ASSIST_{mechanism}_SHAM"
        )
    _write_json(root / "closure_assistance_value_map.json", {
        "protocol": "D3-CLOSURE-v2", "state": "MEASURED" if assistance_by_mechanism else "UNRESOLVED", "mechanisms": assistance_by_mechanism
    })
    required = []
    for mechanism, counts in assistance_by_mechanism.items():
        if counts.get(f"ASSIST_{mechanism}_TARGET_only", 0) > counts.get(f"ASSIST_{mechanism}_SHAM_only", 0):
            required.append(mechanism)
    _write_json(root / "closure_minimum_required_scaffolding.json", {
        "protocol": "D3-CLOSURE-v2", "state": "CANDIDATE" if required else "UNRESOLVED", "candidate_mechanisms": required,
        "note": "candidate set from matched TARGET/SHAM direction; not promoted by this summary alone"
    })

    disposition_total = len(rows)
    disposition_correct = sum(bool(row.get("compiled_disposition_correct")) for row in rows)
    by_family: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "correct": 0})
    for row in rows:
        family = str(row.get("family", "UNKNOWN"))
        by_family[family]["n"] += 1
        by_family[family]["correct"] += int(bool(row.get("compiled_disposition_correct")))
    _write_json(root / "closure_disposition_compiler_evidence.json", {
        "protocol": "D3-CLOSURE-v2", "state": "MEASURED" if rows else "UNRESOLVED",
        "total": disposition_total, "correct": disposition_correct, "by_family": dict(by_family)
    })

    recovery_status = Counter(str(row.get("final_status", "UNKNOWN")) for row in recovery)
    _write_json(root / "closure_recovery_policy_map.json", {
        "protocol": "D3-CLOSURE-v2", "state": "MEASURED" if recovery else "UNRESOLVED",
        "trajectory_count": len(recovery), "status_counts": dict(sorted(recovery_status.items()))
    })

    sealed: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if str(row.get("block")) != "C7":
            continue
        sealed[(str(row.get("model_key")), str(row.get("case_id")))][str(row.get("arm"))] = row
    small_supported = [p["SEALED_SUPPORTED"] for (model, _), p in sealed.items() if model == "SMALL_A" and "SEALED_SUPPORTED" in p]
    qwen_raw = [p["SEALED_RAW"] for (model, _), p in sealed.items() if model == "QWEN" and "SEALED_RAW" in p]
    small_rate = None if not small_supported else sum(bool(r.get("verified_outcome_correct")) for r in small_supported) / len(small_supported)
    qwen_rate = None if not qwen_raw else sum(bool(r.get("verified_outcome_correct")) for r in qwen_raw) / len(qwen_raw)
    _write_json(root / "closure_model_substitution_frontier.json", {
        "protocol": "D3-CLOSURE-v2", "state": "MEASURED" if small_rate is not None and qwen_rate is not None else "UNRESOLVED",
        "small_a_supported_rate": small_rate, "qwen_raw_rate": qwen_rate,
        "small_a_supported_n": len(small_supported), "qwen_raw_n": len(qwen_raw)
    })

    negative: dict[str, dict[str, int]] = {}
    for model in ("SMALL_A", "QWEN"):
        transitions = {"raw_fail_to_supported_success": 0, "raw_success_to_supported_fail": 0, "both_success": 0, "both_fail": 0}
        for (key_model, _), pair in sealed.items():
            if key_model != model or not {"SEALED_RAW", "SEALED_SUPPORTED"} <= set(pair):
                continue
            raw = bool(pair["SEALED_RAW"].get("verified_outcome_correct"))
            supported = bool(pair["SEALED_SUPPORTED"].get("verified_outcome_correct"))
            if not raw and supported:
                transitions["raw_fail_to_supported_success"] += 1
            elif raw and not supported:
                transitions["raw_success_to_supported_fail"] += 1
            elif raw:
                transitions["both_success"] += 1
            else:
                transitions["both_fail"] += 1
        negative[model] = transitions
    _write_json(root / "closure_negative_transfer_map.json", {
        "protocol": "D3-CLOSURE-v2", "state": "MEASURED" if sealed else "UNRESOLVED", "by_model": negative
    })

    routing: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"n": 0, "correct": 0}))
    for row in rows:
        if str(row.get("block")) != "C1":
            continue
        family = str(row.get("family", "UNKNOWN"))
        model = str(row.get("model_key", "UNKNOWN"))
        routing[family][model]["n"] += 1
        routing[family][model]["correct"] += int(bool(row.get("verified_outcome_correct")))
    _write_json(root / "closure_routing_policy_evidence.json", {
        "protocol": "D3-CLOSURE-v2", "state": "MEASURED" if routing else "UNRESOLVED",
        "by_family": {family: dict(models) for family, models in routing.items()}
    })

    return {
        "normalized_calls": len(rows),
        "recovery_trajectories": len(recovery),
        "infrastructure_failures": sum(row.get("completion_class") == "INFRASTRUCTURE_OR_ADAPTER" for row in rows),
    }


def _r0_status(root: Path) -> dict[str, Any]:
    readiness = _read_json(root / "closure_r0_readiness_report.json")
    adequacy = _read_json(root / "closure_claim_adequacy_report.json")
    required = readiness.get("required_artifacts", [])
    artifact_count = sum(1 for name in required if (root / str(name)).is_file())
    if (root / "closure_r0_readiness_report.json").is_file():
        artifact_count += 1
    return {
        "r0_state": str(readiness.get("final_state", "NOT_RUN")),
        "r0_readiness": bool(readiness.get("r0_ready", False)),
        "r0_artifact_count": artifact_count,
        "physical_execution_authorized": bool(adequacy.get("physical_execution_authorized", False)),
    }


def finalize_closure_package(
    root: Path,
    *,
    plan: Any,
    config: dict[str, Any],
    physical_calls: int,
    final_state: str,
    model_free: bool,
) -> dict[str, Any]:
    root = Path(root)
    ensure_closure_output_skeleton(root)

    if model_free:
        repo_root = Path(__file__).resolve().parents[3]
        r0_summary = build_r0_package(repo_root, root, config)
        if r0_summary.physical_model_calls != 0:
            raise ValueError("R0 model-free finalization attempted physical model calls")
        if r0_summary.physical_execution_authorized:
            raise ValueError("R0 may not authorize physical Closure inference")

    plan_rows = [experiment.to_dict() for experiment in plan.experiments]
    _write_json(root / "closure_plan.json", {
        "protocol": "D3-CLOSURE-v2", "planned_physical_calls": plan.planned_physical_calls,
        "max_calls": plan.max_calls, "sealed_reserve": plan.sealed_reserve, "experiments": plan_rows,
    })

    derived = _derive_outputs(root)
    normalized = _read_jsonl(root / "closure_normalized_model_calls.jsonl")
    completed_ids = {str(row.get("experiment_id")) for row in normalized if row.get("experiment_id")}
    planned_ids = {str(experiment.experiment_id) for experiment in plan.experiments}
    missing_ids = sorted(planned_ids - completed_ids)
    planned_recovery = sum(1 for experiment in plan.experiments if experiment.block == "C4")
    recovery_complete = derived["recovery_trajectories"] == planned_recovery
    scientific_complete = (
        not model_free
        and not missing_ids
        and len(completed_ids) == len(planned_ids)
        and derived["infrastructure_failures"] == 0
        and recovery_complete
    )
    r0 = _r0_status(root)

    report = {
        "protocol": "D3-CLOSURE-v2",
        "mode": "MODEL_FREE" if model_free else "REAL_LOCAL",
        "physical_model_calls": int(physical_calls),
        "planned_physical_calls": int(plan.planned_physical_calls),
        "completed_experiments": len(completed_ids),
        "missing_experiments": len(missing_ids),
        "missing_experiment_ids": missing_ids,
        "planned_recovery_trajectories": planned_recovery,
        "observed_recovery_trajectories": derived["recovery_trajectories"],
        "infrastructure_failures": derived["infrastructure_failures"],
        "scientific_complete": scientific_complete,
        "final_state": final_state,
        "claims_promoted": False,
        **r0,
        "note": "Completion authorizes analysis/handoff, not automatic mechanism promotion.",
    }
    _write_json(root / "closure_final_report.json", report)
    _write_json(root / "test5_handoff.json", {
        "ready_for_test5": scientific_complete,
        "protocol": "D3-CLOSURE-v2",
        "reason": "fixed-core closure evidence complete" if scientific_complete else "closure evidence incomplete or contaminated",
        "required_inputs": list(_DERIVED_JSON_OUTPUTS),
        "r0_state": r0["r0_state"],
        "physical_execution_authorized": r0["physical_execution_authorized"],
    })

    master = {
        "protocol": "D3-CLOSURE-v2", "mode": report["mode"], "physical_model_calls": int(physical_calls),
        "planned_physical_calls": int(plan.planned_physical_calls), "max_calls": int(plan.max_calls),
        "sealed_reserve": int(plan.sealed_reserve), "final_state": final_state,
        "scientific_complete": scientific_complete, "blind_retries_allowed": False,
        **r0,
    }
    _write_json(root / "00-HARVEST-D-D3-CLOSURE-V2-MASTER-INDEX.json", master)

    checksum_path = root / "SHA256SUMS.csv"
    files = sorted(path for path in root.iterdir() if path.is_file() and path.name != checksum_path.name)
    with checksum_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sha256", "file"])
        for path in files:
            writer.writerow([_sha256(path), path.name])
    return master
