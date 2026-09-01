from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


REQUIRED_S1_FILES = (
    "00-MASTER-INDEX.json",
    "preregistration.json",
    "config.json",
    "provenance.json",
    "model_calls.jsonl",
    "events.jsonl",
    "trials.csv",
    "validator_results.csv",
    "arm_accounting.csv",
    "arm_summaries.csv",
    "pairwise_effects.csv",
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
    "verdict.json",
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


def _json_default(value: Any) -> Any:
    return str(value)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(_plain(value), indent=2, sort_keys=True, ensure_ascii=False, default=_json_default) + "\n", encoding="utf-8")


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
            if key not in seen:
                seen.add(key)
                fields.append(str(key))
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
            "component": call.get("component"),
            "model": call.get("model"),
            "call_identity": call.get("call_identity"),
            output_field: value,
        })
    return rows


def _derive_master_index(data: dict[str, Any]) -> dict[str, Any]:
    calls = list(data.get("model_calls") or [])
    physical = sum(not bool(row.get("cache_hit")) for row in calls)
    verdict = dict(data.get("verdict") or {})
    provenance = dict(data.get("provenance") or {})
    return {
        "experiment": "test3-section1-fixed-stack-order",
        "section": "S1",
        "mode": "tier-a" if data.get("real_model_inference") else "mock-validation",
        "run_id": provenance.get("run_id"),
        "physical_model_calls": int(verdict.get("physical_model_calls", physical) or 0),
        "architecture_claims_authorized": bool(verdict.get("tier_a_architecture_claim", False)),
        "verdict": verdict.get("verdict"),
        "trial_rows": len(data.get("trials") or []),
        "matched_task_count": verdict.get("matched_task_count"),
        "edge_case_count": len(data.get("edge_cases") or []),
        "instrumentation_anomaly_count": len(data.get("instrumentation_anomalies") or []),
    }


class Test3S1ArtifactWriter:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_all(self, evidence: dict[str, Any]) -> dict[str, str]:
        data = dict(evidence)
        trials = [dict(row) for row in (data.get("trials") or [])]
        model_calls = [dict(row) for row in (data.get("model_calls") or [])]
        data.setdefault("failures", [row for row in trials if row.get("success") is False])
        data.setdefault("wins", [row for row in trials if row.get("success") is True])
        data.setdefault("losses", [row for row in trials if row.get("success") is False])
        data.setdefault("costs", _telemetry_rows(model_calls, "cost_usd", "cost_usd"))
        data.setdefault("latency", _telemetry_rows(model_calls, "latency_s", "latency_s"))
        data.setdefault("tokens", _telemetry_rows(model_calls, "total_tokens", "total_tokens"))
        data.setdefault("cache", [{
            "arm_id": row.get("arm_id"), "task_id": row.get("task_id"),
            "call_identity": row.get("call_identity"), "cache_hit": bool(row.get("cache_hit")),
        } for row in model_calls])
        data.setdefault("edge_cases", [])
        data.setdefault("instrumentation_anomalies", [])
        data.setdefault("arm_accounting", [])
        data.setdefault("arm_summaries", [])
        data.setdefault("pairwise_effects", [])
        data.setdefault("transitions", [])
        data.setdefault("validator_results", [])
        data.setdefault("events", [])
        data.setdefault("report", "VELMA TEST 3 — SECTION 1\nNo report text supplied.\n")
        data.setdefault("master_index", _derive_master_index(data))

        json_files = {
            "00-MASTER-INDEX.json": data["master_index"],
            "preregistration.json": data.get("preregistration", {}),
            "config.json": data.get("config", {}),
            "provenance.json": data.get("provenance", {}),
            "verdict.json": data.get("verdict", {}),
        }
        jsonl_files = {
            "model_calls.jsonl": model_calls,
            "events.jsonl": data["events"],
        }
        csv_files = {
            "trials.csv": trials,
            "validator_results.csv": data["validator_results"],
            "arm_accounting.csv": data["arm_accounting"],
            "arm_summaries.csv": data["arm_summaries"],
            "pairwise_effects.csv": data["pairwise_effects"],
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

        master = self.run_dir / "COMPLETE-EVIDENCE.txt"
        with master.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("VELMA TEST 3 — SECTION 1 COMPLETE EVIDENCE\n")
            handle.write("================================================\n")
            handle.write(f"PHYSICAL MODEL CALLS: {data['master_index'].get('physical_model_calls', 0)}\n")
            handle.write(f"ARCHITECTURE CLAIMS AUTHORIZED: {str(bool(data['master_index'].get('architecture_claims_authorized'))).lower()}\n")
            for path in sorted(written, key=lambda item: item.name):
                handle.write(f"\n===== BEGIN FILE: {path.name} =====\n")
                text = path.read_text(encoding="utf-8")
                handle.write(text)
                if text and not text.endswith("\n"):
                    handle.write("\n")
                handle.write(f"===== END FILE: {path.name} =====\n")
        written.append(master)

        inventory = self.run_dir / "SHA256SUMS.csv"
        with inventory.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
            writer.writeheader()
            for path in sorted(written, key=lambda item: item.name):
                writer.writerow({"path": path.name, "sha256": _sha(path), "bytes": path.stat().st_size})
        missing = [name for name in REQUIRED_S1_FILES if not (self.run_dir / name).is_file()]
        if missing:
            raise RuntimeError(f"S1 evidence packet incomplete: {missing}")
        return {path.name: str(path) for path in [*written, inventory]}
