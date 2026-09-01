from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .types import flatten_scalars, json_safe


JSONL_LEDGERS = (
    "tasks",
    "state_snapshots",
    "model_calls",
    "prompts",
    "responses",
    "actions",
    "tool_results",
    "oracle_results",
    "transitions",
    "events",
    "anomalies",
)

REQUIRED_ARTIFACTS = (
    "00-MASTER-INDEX.json",
    "preregistration.json",
    "config.json",
    "provenance.json",
    "tasks.jsonl",
    "state_snapshots.jsonl",
    "model_calls.jsonl",
    "prompts.jsonl",
    "responses.jsonl",
    "actions.jsonl",
    "tool_results.jsonl",
    "oracle_results.jsonl",
    "transitions.jsonl",
    "events.jsonl",
    "trials.jsonl",
    "trials.csv",
    "failures.csv",
    "metrics.json",
    "metrics.csv",
    "budget.json",
    "anomalies.jsonl",
    "integrity.json",
    "COMPLETE-EVIDENCE.txt",
    "SHA256SUMS.csv",
)


class EvidenceStore:
    """Append-only raw ledgers plus deterministic finalized evidence artifacts."""

    def __init__(self, root: str | Path, *, test_name: str, run_id: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.test_name = str(test_name)
        self.run_id = str(run_id)
        self._event_sequence = 0
        for ledger in JSONL_LEDGERS:
            (self.root / f"{ledger}.jsonl").touch(exist_ok=True)

    def append(self, ledger: str, payload: dict[str, Any]) -> Path:
        if ledger not in JSONL_LEDGERS:
            raise ValueError(f"unknown append-only ledger: {ledger}")
        path = self.root / f"{ledger}.jsonl"
        record = json_safe(payload)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return path

    def event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self._event_sequence += 1
        self.append(
            "events",
            {
                "sequence": self._event_sequence,
                "event_type": str(event_type),
                "test_name": self.test_name,
                "run_id": self.run_id,
                **json_safe(payload or {}),
            },
        )

    def _write_json(self, name: str, value: Any) -> Path:
        path = self.root / name
        path.write_text(
            json.dumps(json_safe(value), indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        return path

    def _write_jsonl(self, name: str, rows: Iterable[dict[str, Any]]) -> Path:
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(json_safe(row), sort_keys=True, ensure_ascii=False, default=str) + "\n")
        return path

    @staticmethod
    def _csv_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return json.dumps(json_safe(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def _write_csv(
        self,
        name: str,
        rows: Iterable[dict[str, Any]],
        *,
        default_fields: tuple[str, ...],
    ) -> Path:
        materialized = [json_safe(row) for row in rows]
        fields = list(default_fields)
        seen = set(fields)
        for row in materialized:
            for key in row:
                if key not in seen:
                    fields.append(str(key))
                    seen.add(str(key))
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in materialized:
                writer.writerow({key: self._csv_value(row.get(key)) for key in fields})
        return path

    @staticmethod
    def _parse_jsonl(path: Path) -> tuple[int, list[str]]:
        count = 0
        errors: list[str] = []
        if not path.exists():
            return 0, ["missing"]
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
                count += 1
            except Exception as exc:
                errors.append(f"line {line_number}: {type(exc).__name__}: {exc}")
        return count, errors

    def _integrity_report(self, budget: dict[str, Any], expected_trials: int) -> dict[str, Any]:
        jsonl_counts: dict[str, int] = {}
        parse_errors: dict[str, list[str]] = {}
        for ledger in JSONL_LEDGERS:
            name = f"{ledger}.jsonl"
            count, errors = self._parse_jsonl(self.root / name)
            jsonl_counts[name] = count
            if errors:
                parse_errors[name] = errors
        trial_count, trial_errors = self._parse_jsonl(self.root / "trials.jsonl")
        jsonl_counts["trials.jsonl"] = trial_count
        if trial_errors:
            parse_errors["trials.jsonl"] = trial_errors

        used = int(budget.get("used", 0))
        cap = int(budget.get("cap", 0))
        model_call_rows = jsonl_counts.get("model_calls.jsonl", 0)
        prompt_rows = jsonl_counts.get("prompts.jsonl", 0)
        response_rows = jsonl_counts.get("responses.jsonl", 0)
        budget_violation = used > cap
        call_ledger_mismatch = not (
            model_call_rows == used
            and prompt_rows == used
            and response_rows == used
        )
        trial_ledger_mismatch = trial_count != int(expected_trials)
        missing = [name for name in REQUIRED_ARTIFACTS if not (self.root / name).exists()]

        ok = not (
            parse_errors
            or budget_violation
            or call_ledger_mismatch
            or trial_ledger_mismatch
            or missing
        )
        return {
            "status": "OK" if ok else "FAILED",
            "test_name": self.test_name,
            "run_id": self.run_id,
            "missing_required_artifacts": missing,
            "jsonl_counts": jsonl_counts,
            "jsonl_parse_errors": parse_errors,
            "model_call_rows": model_call_rows,
            "prompt_rows": prompt_rows,
            "response_rows": response_rows,
            "trial_rows": trial_count,
            "expected_trial_rows": int(expected_trials),
            "budget_cap": cap,
            "budget_used": used,
            "budget_violation": budget_violation,
            "call_ledger_mismatch": call_ledger_mismatch,
            "trial_ledger_mismatch": trial_ledger_mismatch,
        }

    def _write_master_index(self) -> Path:
        # COMPLETE-EVIDENCE and SHA256SUMS are intentionally excluded here:
        # both are finalized after this index and including their placeholders
        # would create stale hashes. SHA256SUMS.csv is the final whole-packet
        # integrity authority and hashes this master index plus COMPLETE-EVIDENCE.
        excluded = {"00-MASTER-INDEX.json", "COMPLETE-EVIDENCE.txt", "SHA256SUMS.csv"}
        entries = []
        for path in sorted(p for p in self.root.iterdir() if p.is_file() and p.name not in excluded):
            entries.append(
                {
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        return self._write_json(
            "00-MASTER-INDEX.json",
            {
                "test_name": self.test_name,
                "run_id": self.run_id,
                "artifact_count_excluding_index": len(entries),
                "artifacts": entries,
            },
        )

    def _write_complete_evidence(self) -> Path:
        excluded = {"COMPLETE-EVIDENCE.txt", "SHA256SUMS.csv"}
        paths = sorted(
            p for p in self.root.iterdir()
            if p.is_file() and p.name not in excluded and p.suffix.lower() in {".json", ".jsonl", ".csv", ".txt"}
        )
        out = self.root / "COMPLETE-EVIDENCE.txt"
        with out.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(f"ASSISTANT VALUE COMPLETE EVIDENCE\nTEST={self.test_name}\nRUN={self.run_id}\n")
            for path in paths:
                handle.write(f"\n===== BEGIN {path.name} =====\n")
                handle.write(path.read_text(encoding="utf-8"))
                if path.stat().st_size and not path.read_text(encoding="utf-8").endswith("\n"):
                    handle.write("\n")
                handle.write(f"===== END {path.name} =====\n")
        return out

    def _write_hashes(self) -> Path:
        paths = sorted(p for p in self.root.iterdir() if p.is_file() and p.name != "SHA256SUMS.csv")
        out = self.root / "SHA256SUMS.csv"
        with out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
            writer.writeheader()
            for path in paths:
                data = path.read_bytes()
                writer.writerow(
                    {
                        "path": path.name,
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
        return out

    def finalize(
        self,
        *,
        preregistration: dict[str, Any],
        config: dict[str, Any],
        provenance: dict[str, Any],
        metrics: dict[str, Any],
        budget: dict[str, Any],
        trials: list[dict[str, Any]],
        failures: list[dict[str, Any]],
    ) -> dict[str, str]:
        for ledger in JSONL_LEDGERS:
            (self.root / f"{ledger}.jsonl").touch(exist_ok=True)

        self._write_json("preregistration.json", preregistration)
        self._write_json("config.json", config)
        self._write_json("provenance.json", provenance)
        self._write_json("metrics.json", metrics)
        self._write_json("budget.json", budget)
        self._write_jsonl("trials.jsonl", trials)
        self._write_csv(
            "trials.csv",
            trials,
            default_fields=("trial_id", "test_name", "arm", "model", "provider", "success", "catastrophic", "model_calls"),
        )
        self._write_csv(
            "failures.csv",
            failures,
            default_fields=("trial_id", "failure_type", "detail"),
        )
        metric_rows = [{"metric": key, "value": value} for key, value in flatten_scalars(metrics)]
        self._write_csv("metrics.csv", metric_rows, default_fields=("metric", "value"))

        # Create final-artifact placeholders before the integrity check so a clean
        # run can validate the complete required-file contract in one pass.
        for name in ("00-MASTER-INDEX.json", "integrity.json", "COMPLETE-EVIDENCE.txt", "SHA256SUMS.csv"):
            (self.root / name).touch(exist_ok=True)

        integrity = self._integrity_report(budget, len(trials))
        self._write_json("integrity.json", integrity)
        self._write_master_index()
        self._write_complete_evidence()
        self._write_hashes()

        return {name: str(self.root / name) for name in REQUIRED_ARTIFACTS}
