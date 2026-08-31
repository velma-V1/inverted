from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


_JSONL_FILES = {
    "trials": "raw/every-trial.jsonl",
    "model_calls": "raw/every-model-call.jsonl",
    "prompts": "raw/every-prompt.jsonl",
    "responses": "raw/every-response.jsonl",
    "candidates": "raw/every-candidate.jsonl",
    "events": "raw/every-event.jsonl",
    "validator_results": "raw/every-validator-result.jsonl",
    "repairs": "raw/every-repair.jsonl",
}

_CSV_FILES = {
    "effects": {
        "outcome_transitions": "effects/outcome-transitions.csv",
        "standalone_effects": "effects/standalone-effects.csv",
        "progressive_effects": "effects/progressive-effects.csv",
        "ablation_effects": "effects/ablation-effects.csv",
        "pairwise_interactions": "effects/pairwise-interactions.csv",
        "failure_kill_matrix": "effects/failure-kill-matrix.csv",
        "synergy_matrix": "effects/synergy-matrix.csv",
    },
    "order": {
        "every_valid_order": "order/every-valid-order.csv",
        "order_ranking": "order/order-ranking.csv",
        "saturation": "order/saturation.csv",
    },
    "models": {
        "model_task_capability_matrix": "models/model-task-capability-matrix.csv",
        "model_family_matrix": "models/model-family-matrix.csv",
        "model_fault_matrix": "models/model-fault-matrix.csv",
        "model_complexity_curves": "models/model-complexity-curves.csv",
        "model_representation_matrix": "models/model-representation-matrix.csv",
        "model_pair_synergy": "models/model-pair-synergy.csv",
        "model_correlated_failures": "models/model-correlated-failures.csv",
        "model_unique_wins": "models/model-unique-wins.csv",
        "router_holdout_results": "models/router-holdout-results.csv",
        "router_regret": "models/router-regret.csv",
    },
    "thresholds": {
        "break_even": "thresholds/break-even.csv",
        "plus_1pp": "thresholds/plus-1pp.csv",
        "plus_3pp": "thresholds/plus-3pp.csv",
        "plus_5pp": "thresholds/plus-5pp.csv",
        "plus_10pp": "thresholds/plus-10pp.csv",
    },
}

_JSON_FILES = {
    "models": {
        "role_champions": "models/role-champions.json",
        "router_policy": "models/router-policy.json",
    },
    "provenance": {
        "config": "provenance/config.json",
        "environment": "provenance/environment.json",
        "git": "provenance/git.json",
        "models": "provenance/models.json",
    },
}


def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=_json_default) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=_json_default) + "\n")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=_json_default)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(str(key))
    if not fields:
        fields = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_next_stride_report(evidence: dict[str, Any]) -> str:
    if evidence.get("next_stride_report"):
        return str(evidence["next_stride_report"])
    index = evidence.get("master_index", {})
    residual = list(index.get("residual_bottlenecks") or [])
    lines = [
        "VELMA TEST 2 — NEXT STRIDE REPORT",
        "=================================",
        f"Run ID: {index.get('run_id', 'unknown')}",
        f"Physical model calls: {index.get('physical_model_calls', 0)}",
        "",
        "REMAINING BOTTLENECKS",
    ]
    if residual:
        for i, row in enumerate(residual[:10], start=1):
            lines.append(
                f"{i}. {row.get('failure_class', 'unknown')}: count={row.get('count', 0)} "
                f"perfect-component ceiling gain={row.get('perfect_component_ceiling_gain', 0):.6f}"
            )
    else:
        lines.append("No residual bottleneck rows were supplied.")
    lines.extend([
        "",
        "NEXT EXPERIMENT",
        "Attack the highest remaining recoverable bottleneck that is not already saturated by the proven stack.",
        "",
    ])
    return "\n".join(lines)


class Test2ArtifactWriter:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_all(self, evidence: dict[str, Any]) -> dict[str, str]:
        written: dict[str, Path] = {}

        master_index = self.run_dir / "00-MASTER-INDEX.json"
        _write_json(master_index, evidence.get("master_index", {}))
        written["master_index"] = master_index

        raw = evidence.get("raw", {})
        for key, relative in _JSONL_FILES.items():
            path = self.run_dir / relative
            _write_jsonl(path, list(raw.get(key, []) or []))
            written[f"raw_{key}"] = path

        for section, mapping in _CSV_FILES.items():
            data = evidence.get(section, {})
            for key, relative in mapping.items():
                path = self.run_dir / relative
                _write_csv(path, list(data.get(key, []) or []))
                written[f"{section}_{key}"] = path

        for section, mapping in _JSON_FILES.items():
            data = evidence.get(section, {})
            for key, relative in mapping.items():
                path = self.run_dir / relative
                _write_json(path, data.get(key, {}))
                written[f"{section}_{key}"] = path

        next_stride = self.run_dir / "TEST2-NEXT-STRIDE-REPORT.txt"
        next_stride.write_text(build_next_stride_report(evidence), encoding="utf-8")
        written["next_stride_report"] = next_stride

        # Build the authoritative master only from already-generated text files.
        # It includes exact bytes decoded as UTF-8 in deterministic path order.
        master = self.run_dir / "TEST2-COMPLETE-EVIDENCE.txt"
        source_paths = sorted(
            [path for path in written.values() if path.suffix.lower() in {".txt", ".csv", ".json", ".jsonl"}],
            key=lambda path: path.relative_to(self.run_dir).as_posix(),
        )
        with master.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("VELMA TEST 2 — COMPLETE EVIDENCE\n")
            handle.write("================================\n")
            for path in source_paths:
                rel = path.relative_to(self.run_dir).as_posix()
                handle.write(f"\n\n===== BEGIN FILE: {rel} =====\n")
                text = path.read_text(encoding="utf-8")
                handle.write(text)
                if text and not text.endswith("\n"):
                    handle.write("\n")
                handle.write(f"===== END FILE: {rel} =====\n")
        written["master_evidence"] = master

        # Hash everything except the inventory itself, including the master.
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
        return {key: str(path) for key, path in written.items()}
