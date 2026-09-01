from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


REQUIRED_S2_FILES = (
    "00-MASTER-INDEX.json",
    "preregistration.json",
    "config.json",
    "provenance.json",
    "router_policy_snapshot.json",
    "protocol_failures.json",
    "verdict.json",
    "model_calls.jsonl",
    "events.jsonl",
    "routing_state_snapshots.jsonl",
    "holdout_manifest.csv",
    "trials.csv",
    "validator_results.csv",
    "arm_accounting.csv",
    "arm_summaries.csv",
    "family_summaries.csv",
    "perturbation_summaries.csv",
    "complexity_summaries.csv",
    "execution_position_summaries.csv",
    "action_model_summaries.csv",
    "recovery_efficiency.csv",
    "pairwise_effects.csv",
    "routing_decisions.csv",
    "action_transition_matrix.csv",
    "shadow_counterfactuals.csv",
    "regret_to_oracle.csv",
    "fault_mode_effects.csv",
    "prompt_fingerprints.csv",
    "stochastic_divergence.csv",
    "action_budget.csv",
    "router_policy_hashes.csv",
    "transitions.csv",
    "failures.csv",
    "wins.csv",
    "losses.csv",
    "costs.csv",
    "latency.csv",
    "tokens.csv",
    "cache.csv",
    "edge_cases.csv",
    "instrumentation_anomalies.csv",
    "report.txt",
    "COMPLETE-EVIDENCE.txt",
    "SHA256SUMS.csv",
)


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if hasattr(value, "value"):
        return value.value
    return value


def _json_default(value: Any) -> str:
    return str(value)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_plain(value), indent=2, sort_keys=True, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(_plain(row), sort_keys=True, ensure_ascii=False, default=_json_default, separators=(",", ":")) + "\n")


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(_plain(value), sort_keys=True, ensure_ascii=False, default=_json_default, separators=(",", ":"))
    return value


def _write_csv(path: Path, rows: Iterable[Any]) -> None:
    data = [dict(row) if isinstance(row, dict) else {"value": row} for row in rows]
    fields: list[str] = []
    seen: set[str] = set()
    for row in data:
        for key in row:
            key_s = str(key)
            if key_s not in seen:
                seen.add(key_s)
                fields.append(key_s)
    if not fields:
        fields = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _telemetry_rows(model_calls: list[dict[str, Any]], field: str, output_field: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call in model_calls:
        telemetry = call.get("telemetry") if isinstance(call.get("telemetry"), dict) else {}
        value = telemetry.get(field)
        if value is None:
            continue
        rows.append({
            "arm_id": call.get("arm_id"),
            "task_id": call.get("task_id"),
            "base_task_id": call.get("base_task_id"),
            "perturbation_class": call.get("perturbation_class"),
            "step_index": call.get("step_index"),
            "action_selected": call.get("action_selected"),
            "model": call.get("model"),
            "active_intervention": bool(call.get("active_intervention")),
            "shadow_only": bool(call.get("shadow_only")),
            "call_identity": call.get("call_identity"),
            "prompt_fingerprint": call.get("prompt_fingerprint"),
            output_field: value,
        })
    return rows


def _prompt_fingerprint_rows(model_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "arm_id": row.get("arm_id"),
        "task_id": row.get("task_id"),
        "step_index": row.get("step_index"),
        "action_selected": row.get("action_selected"),
        "model": row.get("model"),
        "role": row.get("role"),
        "prompt_fingerprint": row.get("prompt_fingerprint"),
        "call_identity": row.get("call_identity"),
        "response_digest": row.get("response_digest"),
        "active_intervention": bool(row.get("active_intervention")),
        "shadow_only": bool(row.get("shadow_only")),
    } for row in model_calls]


def _shadow_rows(model_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "arm_id": row.get("arm_id"),
        "task_id": row.get("task_id"),
        "base_task_id": row.get("base_task_id"),
        "perturbation_class": row.get("perturbation_class"),
        "step_index": row.get("step_index"),
        "action_selected": row.get("action_selected"),
        "model": row.get("model"),
        "call_identity": row.get("call_identity"),
        "prompt_fingerprint": row.get("prompt_fingerprint"),
        "response_digest": row.get("response_digest"),
        "candidate_before_id": row.get("candidate_before_id"),
        "candidate_before_state": row.get("candidate_before_state"),
        "candidate_before_actions": row.get("candidate_before_actions"),
        "proposed_candidate_id": row.get("proposed_candidate_id"),
        "proposed_candidate_state": row.get("proposed_candidate_state"),
        "proposed_candidate_actions": row.get("proposed_candidate_actions"),
        "candidate_after_id": row.get("candidate_after_id"),
        "candidate_after_state": row.get("candidate_after_state"),
        "candidate_after_actions": row.get("candidate_after_actions"),
        "success_before": row.get("success_before"),
        "success_after": row.get("success_after"),
        "catastrophic_before": row.get("catastrophic_before"),
        "catastrophic_after": row.get("catastrophic_after"),
        "proposed_success": row.get("proposed_success"),
        "proposed_catastrophic": row.get("proposed_catastrophic"),
        "proposed_passed_requirements": row.get("proposed_passed_requirements"),
        "proposed_failed_requirements": row.get("proposed_failed_requirements"),
        "counterfactual_evaluated": bool(row.get("counterfactual_evaluated")),
        "causal_status": "SHADOW_NON_MUTATING_COUNTERFACTUAL_OBSERVATION",
    } for row in model_calls if bool(row.get("shadow_only"))]


def _action_budget_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [{
        "kind": "combined_total",
        "used": int(snapshot.get("combined_used") or 0),
        "limit": int(snapshot.get("limit") or 0),
        "remaining": int(snapshot.get("remaining") or 0),
    }]
    for kind, count in sorted(dict(snapshot.get("by_kind") or {}).items()):
        rows.append({
            "kind": str(kind),
            "used": int(count),
            "limit": int(snapshot.get("limit") or 0),
            "remaining": int(snapshot.get("remaining") or 0),
        })
    return rows


def _master_index(data: dict[str, Any]) -> dict[str, Any]:
    calls = list(data.get("model_calls") or [])
    trials = list(data.get("trials") or [])
    verdict = dict(data.get("verdict") or {})
    provenance = dict(data.get("provenance") or {})
    prereg = dict(data.get("preregistration") or {})
    action_budget = dict(data.get("action_budget") or {})
    matched = verdict.get("matched_case_count") or data.get("matched_case_count")
    if matched is None:
        matched = len({str(row.get("task_id")) for row in trials if row.get("task_id")})
    return {
        "experiment": "test3-section2-adaptive-routing",
        "section": "S2",
        "mode": "tier-a" if data.get("real_model_inference") else "mock-validation",
        "run_id": provenance.get("run_id") or data.get("run_id"),
        "protocol_revision": verdict.get("protocol_revision") or provenance.get("protocol_revision") or prereg.get("protocol_revision"),
        "holdout": verdict.get("holdout") or provenance.get("execution_holdout") or prereg.get("holdout"),
        "protocol_valid_for_primary_claim": bool(verdict.get("protocol_valid_for_primary_claim", False)),
        "physical_model_calls": int(data.get("physical_model_calls") or len(calls)),
        "combined_external_actions": int(action_budget.get("combined_used") or 0),
        "combined_action_limit": int(action_budget.get("limit") or 0),
        "architecture_claims_authorized": bool(verdict.get("tier_a_architecture_claim", False)),
        "verdict": verdict.get("verdict"),
        "trial_rows": len(trials),
        "matched_case_count": int(matched or 0),
        "arm_count": len({str(row.get("arm_id")) for row in trials if row.get("arm_id")}),
        "family_count": len({str(row.get("family")) for row in trials if row.get("family")}),
        "perturbation_count": len({str(row.get("perturbation_class")) for row in trials if row.get("perturbation_class")}),
        "active_inference_calls": sum(bool(row.get("active_intervention")) for row in calls),
        "shadow_inference_calls": sum(bool(row.get("shadow_only")) for row in calls),
        "stochastic_divergence_count": len(data.get("stochastic_divergence") or []),
        "edge_case_count": len(data.get("edge_cases") or []),
        "instrumentation_anomaly_count": len(data.get("instrumentation_anomalies") or []),
        "protocol_failure_count": len(data.get("protocol_failures") or []),
    }


class Test3S2ArtifactWriter:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_all(self, evidence: dict[str, Any]) -> dict[str, str]:
        data = dict(evidence)
        trials = [dict(row) for row in (data.get("trials") or [])]
        model_calls = [dict(row) for row in (data.get("model_calls") or [])]
        data.setdefault("protocol_failures", [])
        data.setdefault("events", [])
        data.setdefault("routing_state_snapshots", [])
        data.setdefault("holdout_manifest", [])
        data.setdefault("validator_results", [])
        data.setdefault("arm_accounting", [])
        data.setdefault("arm_summaries", [])
        data.setdefault("family_summaries", [])
        data.setdefault("perturbation_summaries", [])
        data.setdefault("complexity_summaries", [])
        data.setdefault("execution_position_summaries", [])
        data.setdefault("action_model_summaries", [])
        data.setdefault("recovery_efficiency", [])
        data.setdefault("pairwise_effects", [])
        data.setdefault("routing_decisions", [])
        data.setdefault("action_transition_matrix", [])
        data.setdefault("regret_to_oracle", [])
        data.setdefault("fault_mode_effects", [])
        data.setdefault("transitions", [])
        data.setdefault("stochastic_divergence", [])
        data.setdefault("router_policy_snapshot", {})
        data.setdefault("router_policy_hashes", [])
        data.setdefault("action_budget", {})
        data.setdefault("edge_cases", [])
        data.setdefault("instrumentation_anomalies", [])
        data.setdefault("failures", [row for row in trials if row.get("success") is False])
        data.setdefault("wins", [row for row in trials if row.get("success") is True])
        data.setdefault("losses", [row for row in trials if row.get("success") is False])
        data.setdefault("costs", _telemetry_rows(model_calls, "cost_usd", "cost_usd"))
        data.setdefault("latency", _telemetry_rows(model_calls, "latency_s", "latency_s"))
        data.setdefault("tokens", _telemetry_rows(model_calls, "total_tokens", "total_tokens"))
        data.setdefault("cache", [{
            "arm_id": row.get("arm_id"),
            "task_id": row.get("task_id"),
            "call_identity": row.get("call_identity"),
            "prompt_fingerprint": row.get("prompt_fingerprint"),
            "active_intervention": bool(row.get("active_intervention")),
            "shadow_only": bool(row.get("shadow_only")),
            "cache_hit": bool(row.get("cache_hit")),
        } for row in model_calls])
        data.setdefault("prompt_fingerprints", _prompt_fingerprint_rows(model_calls))
        data.setdefault("shadow_counterfactuals", _shadow_rows(model_calls))
        data.setdefault("action_budget_rows", _action_budget_rows(dict(data.get("action_budget") or {})))
        data.setdefault("report", "VELMA TEST 3 — SECTION 2 S2-R1 ADAPTIVE ROUTING\nNo report text supplied.\n")
        data.setdefault("master_index", _master_index(data))

        json_files = {
            "00-MASTER-INDEX.json": data["master_index"],
            "preregistration.json": data.get("preregistration", {}),
            "config.json": data.get("config", {}),
            "provenance.json": data.get("provenance", {}),
            "router_policy_snapshot.json": data["router_policy_snapshot"],
            "protocol_failures.json": data["protocol_failures"],
            "verdict.json": data.get("verdict", {}),
        }
        jsonl_files = {
            "model_calls.jsonl": model_calls,
            "events.jsonl": data["events"],
            "routing_state_snapshots.jsonl": data["routing_state_snapshots"],
        }
        csv_files = {
            "holdout_manifest.csv": data["holdout_manifest"],
            "trials.csv": trials,
            "validator_results.csv": data["validator_results"],
            "arm_accounting.csv": data["arm_accounting"],
            "arm_summaries.csv": data["arm_summaries"],
            "family_summaries.csv": data["family_summaries"],
            "perturbation_summaries.csv": data["perturbation_summaries"],
            "complexity_summaries.csv": data["complexity_summaries"],
            "execution_position_summaries.csv": data["execution_position_summaries"],
            "action_model_summaries.csv": data["action_model_summaries"],
            "recovery_efficiency.csv": data["recovery_efficiency"],
            "pairwise_effects.csv": data["pairwise_effects"],
            "routing_decisions.csv": data["routing_decisions"],
            "action_transition_matrix.csv": data["action_transition_matrix"],
            "shadow_counterfactuals.csv": data["shadow_counterfactuals"],
            "regret_to_oracle.csv": data["regret_to_oracle"],
            "fault_mode_effects.csv": data["fault_mode_effects"],
            "prompt_fingerprints.csv": data["prompt_fingerprints"],
            "stochastic_divergence.csv": data["stochastic_divergence"],
            "action_budget.csv": data["action_budget_rows"],
            "router_policy_hashes.csv": data["router_policy_hashes"],
            "transitions.csv": data["transitions"],
            "failures.csv": data["failures"],
            "wins.csv": data["wins"],
            "losses.csv": data["losses"],
            "costs.csv": data["costs"],
            "latency.csv": data["latency"],
            "tokens.csv": data["tokens"],
            "cache.csv": data["cache"],
            "edge_cases.csv": data["edge_cases"],
            "instrumentation_anomalies.csv": data["instrumentation_anomalies"],
        }

        written: list[Path] = []
        for name, value in json_files.items():
            path = self.run_dir / name
            _write_json(path, value)
            written.append(path)
        for name, rows in jsonl_files.items():
            path = self.run_dir / name
            _write_jsonl(path, rows)
            written.append(path)
        for name, rows in csv_files.items():
            path = self.run_dir / name
            _write_csv(path, rows)
            written.append(path)

        report = self.run_dir / "report.txt"
        report.write_text(str(data["report"]), encoding="utf-8")
        written.append(report)

        complete = self.run_dir / "COMPLETE-EVIDENCE.txt"
        with complete.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("VELMA TEST 3 — SECTION 2 S2-R1 COMPLETE EVIDENCE\n")
            handle.write("====================================================\n")
            handle.write(f"PROTOCOL: {data['master_index'].get('protocol_revision')}\n")
            handle.write(f"HOLDOUT: {data['master_index'].get('holdout')}\n")
            handle.write(f"PHYSICAL MODEL CALLS: {data['master_index'].get('physical_model_calls', 0)}\n")
            handle.write(f"COMBINED EXTERNAL ACTIONS: {data['master_index'].get('combined_external_actions', 0)}\n")
            handle.write(f"PROTOCOL VALID FOR PRIMARY CLAIM: {str(bool(data['master_index'].get('protocol_valid_for_primary_claim'))).lower()}\n")
            for path in sorted(written, key=lambda item: item.name):
                handle.write(f"\n===== BEGIN FILE: {path.name} =====\n")
                text = path.read_text(encoding="utf-8")
                handle.write(text)
                if text and not text.endswith("\n"):
                    handle.write("\n")
                handle.write(f"===== END FILE: {path.name} =====\n")
        written.append(complete)

        inventory = self.run_dir / "SHA256SUMS.csv"
        with inventory.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
            writer.writeheader()
            for path in sorted(written, key=lambda item: item.name):
                writer.writerow({"path": path.name, "sha256": _sha(path), "bytes": path.stat().st_size})

        missing = [name for name in REQUIRED_S2_FILES if not (self.run_dir / name).is_file()]
        if missing:
            raise RuntimeError(f"S2 evidence packet incomplete: {missing}")
        return {path.name: str(path) for path in [*written, inventory]}
