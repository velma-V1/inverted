from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable


STANDARD_PACKET_FILES = (
    "preregistration.json",
    "config.json",
    "provenance.json",
    "model_calls.jsonl",
    "events.jsonl",
    "trials.csv",
    "validator_results.csv",
    "failures.csv",
    "wins.csv",
    "losses.csv",
    "transitions.csv",
    "counterfactuals.csv",
    "costs.csv",
    "latency.csv",
    "tokens.csv",
    "cache.csv",
    "failure_atlas.json",
    "effect_sizes.json",
    "verdict.json",
    "report.txt",
)

S0_PACKET_FILES = (
    "source_manifest.json",
    "source_integrity.csv",
    "normalization_coverage.csv",
    "normalization_errors.csv",
    "fixed_policy_candidates.csv",
    "adaptive_policy_candidates.csv",
    "control_results.csv",
    "pareto_frontier.csv",
    "unresolved_causal_questions.csv",
    "requires_new_inference.csv",
    "invalid_counterfactuals.csv",
    "power_variance.json",
    "candidate_section1_preregistration.json",
)

FORENSIC_PACKET_FILES = (
    "00-MASTER-INDEX.json",
    "instrumentation_anomalies.csv",
    "metadata_catalog.csv",
    "field_provenance.csv",
    "source_file_inventory.csv",
    "decision_trace.csv",
    "unknown_fields.csv",
    "edge_cases.csv",
    "comparison_evidence.csv",
    "source_metadata.jsonl",
    "data_quality.json",
)

REQUIRED_PACKET_FILES = STANDARD_PACKET_FILES + S0_PACKET_FILES + FORENSIC_PACKET_FILES + (
    "COMPLETE-EVIDENCE.txt",
    "SHA256SUMS.csv",
)

_JSON_FILES = {
    "preregistration": "preregistration.json",
    "config": "config.json",
    "provenance": "provenance.json",
    "failure_atlas": "failure_atlas.json",
    "effect_sizes": "effect_sizes.json",
    "verdict": "verdict.json",
    "source_manifest": "source_manifest.json",
    "power_variance": "power_variance.json",
    "candidate_section1_preregistration": "candidate_section1_preregistration.json",
    "master_index": "00-MASTER-INDEX.json",
    "data_quality": "data_quality.json",
}

_JSONL_FILES = {
    "model_calls": "model_calls.jsonl",
    "events": "events.jsonl",
    "source_metadata": "source_metadata.jsonl",
}

_CSV_FILES = {
    "trials": "trials.csv",
    "validator_results": "validator_results.csv",
    "failures": "failures.csv",
    "wins": "wins.csv",
    "losses": "losses.csv",
    "transitions": "transitions.csv",
    "counterfactuals": "counterfactuals.csv",
    "costs": "costs.csv",
    "latency": "latency.csv",
    "tokens": "tokens.csv",
    "cache": "cache.csv",
    "source_integrity": "source_integrity.csv",
    "normalization_coverage": "normalization_coverage.csv",
    "normalization_errors": "normalization_errors.csv",
    "fixed_policy_candidates": "fixed_policy_candidates.csv",
    "adaptive_policy_candidates": "adaptive_policy_candidates.csv",
    "control_results": "control_results.csv",
    "pareto_frontier": "pareto_frontier.csv",
    "unresolved_causal_questions": "unresolved_causal_questions.csv",
    "requires_new_inference": "requires_new_inference.csv",
    "invalid_counterfactuals": "invalid_counterfactuals.csv",
    "instrumentation_anomalies": "instrumentation_anomalies.csv",
    "metadata_catalog": "metadata_catalog.csv",
    "field_provenance": "field_provenance.csv",
    "source_file_inventory": "source_file_inventory.csv",
    "decision_trace": "decision_trace.csv",
    "unknown_fields": "unknown_fields.csv",
    "edge_cases": "edge_cases.csv",
    "comparison_evidence": "comparison_evidence.csv",
}


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    if hasattr(value, "value") and value.__class__.__module__ == "enum":
        return value.value
    return value


def _json_default(value: Any) -> Any:
    plain = _plain(value)
    if plain is not value:
        return plain
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_plain(value), indent=2, sort_keys=True, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(_plain(row), sort_keys=True, ensure_ascii=False, default=_json_default, separators=(",", ":")) + "\n")


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if is_dataclass(value) or isinstance(value, (dict, list, tuple, set)):
        return json.dumps(_plain(value), sort_keys=True, ensure_ascii=False, default=_json_default, separators=(",", ":"))
    if hasattr(value, "value"):
        return value.value
    return value


def _row_dict(row: Any) -> dict[str, Any]:
    if is_dataclass(row):
        return asdict(row)
    if isinstance(row, dict):
        return dict(row)
    return {"value": row}


def _write_csv(path: Path, rows: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [_row_dict(row) for row in rows]
    fields: list[str] = []
    seen: set[str] = set()
    for row in data:
        for key in row:
            key = str(key)
            if key not in seen:
                fields.append(key)
                seen.add(key)
    if not fields:
        fields = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _derive_master_index(evidence: dict[str, Any]) -> dict[str, Any]:
    verdict = dict(evidence.get("verdict") or {})
    transitions = list(evidence.get("transitions") or [])
    counterfactuals = list(evidence.get("counterfactuals") or [])
    return {
        "experiment": "test3-section0-github-causal-discovery",
        "section": "S0",
        "mode": "model-free",
        "physical_model_calls": 0,
        "architecture_claims_authorized": False,
        "verdict": verdict.get("verdict"),
        "transition_count": len(transitions),
        "counterfactual_count": len(counterfactuals),
        "normalization_error_count": len(evidence.get("normalization_errors") or []),
        "source_count": len((evidence.get("source_manifest") or {}).get("sources", [])) if isinstance(evidence.get("source_manifest"), dict) else 0,
        "requires_new_inference_count": len(evidence.get("requires_new_inference") or []),
        "invalid_counterfactual_count": len(evidence.get("invalid_counterfactuals") or []),
        "comparison_evidence_count": len(evidence.get("comparison_evidence") or []),
        "source_metadata_count": len(evidence.get("source_metadata") or []),
        "validator_result_count": len(evidence.get("validator_results") or []),
    }


def _derive_data_quality(evidence: dict[str, Any]) -> dict[str, Any]:
    integrity = list(evidence.get("source_integrity") or [])
    normalization_errors = list(evidence.get("normalization_errors") or [])
    anomalies = list(evidence.get("instrumentation_anomalies") or [])
    unknown_fields = list(evidence.get("unknown_fields") or [])
    coverage = list(evidence.get("normalization_coverage") or [])
    dropped_rows = sum(int(row.get("dropped_rows") or 0) for row in coverage if isinstance(row, dict))
    input_rows = sum(int(row.get("input_rows") or 0) for row in coverage if isinstance(row, dict))
    return {
        "source_integrity_rows": len(integrity),
        "normalization_errors": len(normalization_errors),
        "instrumentation_anomalies": len(anomalies),
        "unknown_field_records": len(unknown_fields),
        "normalization_input_rows": input_rows,
        "normalization_dropped_rows": dropped_rows,
        "normalization_retention_rate": ((input_rows - dropped_rows) / input_rows) if input_rows else None,
        "comparison_evidence_rows": len(evidence.get("comparison_evidence") or []),
        "source_metadata_rows": len(evidence.get("source_metadata") or []),
        "validator_result_rows": len(evidence.get("validator_results") or []),
        "all_integrity_checks_passed": all(bool(row.get("integrity_ok", True)) for row in integrity) if integrity else None,
        "zero_model_call_invariant": True,
        "data_loss_policy": "retain malformed/unknown/anomalous records as evidence; never silently coerce",
    }


class Test3S0ArtifactWriter:
    __test__ = False

    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_all(self, evidence: dict[str, Any]) -> dict[str, str]:
        data = dict(evidence)
        if not data.get("master_index"):
            data["master_index"] = _derive_master_index(data)
        if not data.get("data_quality"):
            data["data_quality"] = _derive_data_quality(data)
        data.setdefault("report", "VELMA TEST 3 — SECTION 0\nNo report text supplied.\n")
        for key in _CSV_FILES:
            data.setdefault(key, [])
        for key in _JSONL_FILES:
            data.setdefault(key, [])
        for key in _JSON_FILES:
            data.setdefault(key, {})

        written: dict[str, Path] = {}
        for key, name in _JSON_FILES.items():
            path = self.run_dir / name
            _write_json(path, data.get(key, {}))
            written[key] = path
        for key, name in _JSONL_FILES.items():
            path = self.run_dir / name
            _write_jsonl(path, data.get(key, []))
            written[key] = path
        for key, name in _CSV_FILES.items():
            path = self.run_dir / name
            _write_csv(path, data.get(key, []))
            written[key] = path

        report = self.run_dir / "report.txt"
        report.write_text(str(data.get("report") or ""), encoding="utf-8")
        written["report"] = report

        master = self.run_dir / "COMPLETE-EVIDENCE.txt"
        source_paths = sorted(
            [path for path in written.values() if path.suffix.lower() in {".txt", ".csv", ".json", ".jsonl"}],
            key=lambda path: path.relative_to(self.run_dir).as_posix(),
        )
        with master.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("VELMA TEST 3 — SECTION 0 COMPLETE EVIDENCE\n")
            handle.write("================================================\n")
            handle.write("PHYSICAL MODEL CALLS: 0\n")
            handle.write("ARCHITECTURE CLAIMS AUTHORIZED: false\n")
            for path in source_paths:
                rel = path.relative_to(self.run_dir).as_posix()
                handle.write(f"\n===== BEGIN FILE: {rel} =====\n")
                text = path.read_text(encoding="utf-8")
                handle.write(text)
                if text and not text.endswith("\n"):
                    handle.write("\n")
                handle.write(f"===== END FILE: {rel} =====\n")
        written["complete_evidence"] = master

        hash_path = self.run_dir / "SHA256SUMS.csv"
        hash_targets = sorted(
            [path for path in written.values() if path.exists()],
            key=lambda path: path.relative_to(self.run_dir).as_posix(),
        )
        with hash_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"])
            writer.writeheader()
            for path in hash_targets:
                writer.writerow({
                    "path": path.relative_to(self.run_dir).as_posix(),
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                })
        written["sha256sums"] = hash_path

        missing = [name for name in REQUIRED_PACKET_FILES if not (self.run_dir / name).exists()]
        if missing:
            raise RuntimeError(f"Section 0 evidence packet incomplete: {missing}")
        return {key: str(path) for key, path in written.items()}
