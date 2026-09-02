from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .types import json_safe


JSONL_LEDGERS = (
    "tasks",
    "state_snapshots",
    "external_actions",
    "model_calls",
    "prompts",
    "responses",
    "decisions",
    "actions",
    "tool_results",
    "oracle_results",
    "transitions",
    "interventions",
    "shams",
    "error_lifecycle",
    "metamorphic_pairs",
    "coverage",
    "events",
    "anomalies",
)

CORE_REQUIRED = tuple(f"{name}.jsonl" for name in JSONL_LEDGERS) + (
    "preregistration.json",
    "config.json",
    "provenance.json",
    "trials.jsonl",
    "findings.jsonl",
    "metrics.json",
    "budget.json",
)


class BlackMagicEvidenceStore:
    def __init__(self, root: str | Path, *, experiment_name: str, run_id: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.experiment_name = str(experiment_name)
        self.run_id = str(run_id)
        self._sequence = 0
        for ledger in JSONL_LEDGERS:
            (self.root / f"{ledger}.jsonl").touch(exist_ok=True)

    def append(self, ledger: str, payload: dict[str, Any]) -> Path:
        if ledger not in JSONL_LEDGERS:
            raise ValueError(f"unknown black-magic ledger: {ledger}")
        path = self.root / f"{ledger}.jsonl"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(json_safe(payload), sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return path

    def event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self._sequence += 1
        self.append(
            "events",
            {
                "sequence": self._sequence,
                "event_type": str(event_type),
                "experiment": self.experiment_name,
                "run_id": self.run_id,
                **json_safe(payload or {}),
            },
        )

    def write_json(self, name: str, value: Any) -> Path:
        path = self.root / name
        path.write_text(
            json.dumps(json_safe(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def write_jsonl(self, name: str, rows: Iterable[dict[str, Any]]) -> Path:
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(json_safe(row), sort_keys=True, ensure_ascii=False) + "\n")
        return path

    @staticmethod
    def _parse_jsonl(path: Path) -> tuple[int, list[str]]:
        count = 0
        errors: list[str] = []
        if not path.exists():
            return 0, ["missing"]
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
                count += 1
            except Exception as exc:
                errors.append(f"line {number}: {type(exc).__name__}: {exc}")
        return count, errors

    def _integrity(self, budget: dict[str, Any], expected_trials: int) -> dict[str, Any]:
        counts: dict[str, int] = {}
        parse_errors: dict[str, list[str]] = {}
        for name in JSONL_LEDGERS:
            filename = f"{name}.jsonl"
            count, errors = self._parse_jsonl(self.root / filename)
            counts[filename] = count
            if errors:
                parse_errors[filename] = errors
        trial_count, trial_errors = self._parse_jsonl(self.root / "trials.jsonl")
        finding_count, finding_errors = self._parse_jsonl(self.root / "findings.jsonl")
        counts["trials.jsonl"] = trial_count
        counts["findings.jsonl"] = finding_count
        if trial_errors:
            parse_errors["trials.jsonl"] = trial_errors
        if finding_errors:
            parse_errors["findings.jsonl"] = finding_errors
        missing = [name for name in CORE_REQUIRED if not (self.root / name).exists()]
        used = int(budget.get("used", 0))
        cap = int(budget.get("cap", 0))
        call_rows = counts.get("model_calls.jsonl", 0)
        prompt_rows = counts.get("prompts.jsonl", 0)
        response_rows = counts.get("responses.jsonl", 0)
        external_rows = counts.get("external_actions.jsonl", 0)
        parity = call_rows == prompt_rows == response_rows == external_rows == used
        trial_ok = trial_count == int(expected_trials)
        ok = not parse_errors and not missing and used <= cap and parity and trial_ok
        return {
            "status": "OK" if ok else "FAILED",
            "experiment": self.experiment_name,
            "run_id": self.run_id,
            "missing": missing,
            "parse_errors": parse_errors,
            "counts": counts,
            "budget_used": used,
            "budget_cap": cap,
            "call_prompt_response_external_parity": parity,
            "expected_trials": int(expected_trials),
            "trial_count": trial_count,
            "trial_count_ok": trial_ok,
        }

    def _master_index(self) -> None:
        excluded = {"00-MASTER-INDEX.json", "COMPLETE-EVIDENCE.txt", "SHA256SUMS.csv"}
        entries = []
        for path in sorted(p for p in self.root.iterdir() if p.is_file() and p.name not in excluded):
            data = path.read_bytes()
            entries.append({"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.write_json("00-MASTER-INDEX.json", {"artifacts": entries, "artifact_count": len(entries)})

    def _complete_evidence(self) -> None:
        excluded = {"COMPLETE-EVIDENCE.txt", "SHA256SUMS.csv"}
        paths = sorted(
            p for p in self.root.iterdir()
            if p.is_file() and p.name not in excluded and p.suffix.lower() in {".json", ".jsonl", ".csv", ".txt"}
        )
        out = self.root / "COMPLETE-EVIDENCE.txt"
        with out.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(f"BLACK MAGIC COMPLETE EVIDENCE\nEXPERIMENT={self.experiment_name}\nRUN={self.run_id}\n")
            for path in paths:
                text = path.read_text(encoding="utf-8")
                handle.write(f"\n===== BEGIN {path.name} =====\n{text}")
                if text and not text.endswith("\n"):
                    handle.write("\n")
                handle.write(f"===== END {path.name} =====\n")

    def _hashes(self) -> None:
        out = self.root / "SHA256SUMS.csv"
        with out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
            writer.writeheader()
            for path in sorted(p for p in self.root.iterdir() if p.is_file() and p.name != out.name):
                data = path.read_bytes()
                writer.writerow({"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    def finalize(
        self,
        *,
        preregistration: dict[str, Any],
        config: dict[str, Any],
        provenance: dict[str, Any],
        metrics: dict[str, Any],
        budget: dict[str, Any],
        trials: list[dict[str, Any]],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.write_json("preregistration.json", preregistration)
        self.write_json("config.json", config)
        self.write_json("provenance.json", provenance)
        self.write_json("metrics.json", metrics)
        self.write_json("budget.json", budget)
        self.write_jsonl("trials.jsonl", trials)
        self.write_jsonl("findings.jsonl", findings)
        integrity = self._integrity(budget, len(trials))
        self.write_json("integrity.json", integrity)
        self._master_index()
        self._complete_evidence()
        self._hashes()
        return {"integrity": integrity, "root": str(self.root)}
