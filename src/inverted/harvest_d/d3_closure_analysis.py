from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


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
    "closure_system_events.jsonl",
    "closure_sequential_decisions.jsonl",
    "closure_raw_model_requests.jsonl",
    "closure_raw_model_responses.jsonl",
    "closure_normalized_model_calls.jsonl",
    "closure_runtime_telemetry.jsonl",
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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

    plan_rows = [experiment.to_dict() for experiment in plan.experiments]
    _write_json(
        root / "closure_plan.json",
        {
            "protocol": "D3-CLOSURE-v2",
            "planned_physical_calls": plan.planned_physical_calls,
            "max_calls": plan.max_calls,
            "sealed_reserve": plan.sealed_reserve,
            "experiments": plan_rows,
        },
    )

    report = {
        "protocol": "D3-CLOSURE-v2",
        "mode": "MODEL_FREE" if model_free else "REAL_LOCAL",
        "physical_model_calls": int(physical_calls),
        "final_state": final_state,
        "claims_promoted": False,
        "note": "Model-free validation proves harness structure only; scientific claims require fresh physical evidence.",
    }
    _write_json(root / "closure_final_report.json", report)
    _write_json(
        root / "test5_handoff.json",
        {
            "ready_for_test5": False,
            "protocol": "D3-CLOSURE-v2",
            "reason": "Test 5 is unlocked only after D3-Closure fresh evidence closes material architecture gaps.",
        },
    )

    master = {
        "protocol": "D3-CLOSURE-v2",
        "mode": report["mode"],
        "physical_model_calls": int(physical_calls),
        "planned_physical_calls": int(plan.planned_physical_calls),
        "max_calls": int(plan.max_calls),
        "sealed_reserve": int(plan.sealed_reserve),
        "final_state": final_state,
        "blind_retries_allowed": False,
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
