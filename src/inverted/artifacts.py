from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

from .report import render_report


def collect_provenance() -> dict[str, Any]:
    git_commit = None
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True, timeout=2).strip()
    except Exception:
        pass
    deps = {}
    for name in ("httpx", "PyYAML", "pytest"):
        try:
            deps[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            deps[name] = None
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "git_commit": git_commit,
        "dependencies": deps,
        "cwd": os.getcwd(),
    }


def _json_default(value: Any):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, default=_json_default) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, default=_json_default) + "\n")


def _csv_safe(v: Any) -> Any:
    if isinstance(v, (dict, list, tuple)):
        return json.dumps(v, sort_keys=True, default=_json_default)
    return v


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        keys = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key); keys.append(key)
        fieldnames = keys or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_safe(row.get(k)) for k in fieldnames})


class ArtifactWriter:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_all(self, result: Any, summary: dict[str, Any], verdict: dict[str, Any], provenance: dict[str, Any], include_raw_rows: bool = True) -> dict[str, str]:
        paths = {
            "events": self.run_dir / "events.jsonl",
            "model_calls": self.run_dir / "model_calls.jsonl",
            "trials_csv": self.run_dir / "trials.csv",
            "trials_jsonl": self.run_dir / "trials.jsonl",
            "failures": self.run_dir / "failures.csv",
            "summary_json": self.run_dir / "summary.json",
            "summary_csv": self.run_dir / "summary.csv",
            "report": self.run_dir / "report.txt",
            "config": self.run_dir / "config.json",
            "provenance": self.run_dir / "provenance.json",
        }
        path_strings = {k: str(v) for k, v in paths.items()}

        trial_rows = [t.to_dict(include_calls=False) for t in result.trials]
        call_rows = [c.to_dict() for c in result.model_calls]
        events: list[dict[str, Any]] = [
            {"event": "run_started", "run_id": result.run_id, "timestamp": result.started_at},
        ]
        for t in result.trials:
            for event in t.candidate_events:
                events.append({"event": "candidate", "run_id": result.run_id, "trial_id": t.trial_id, "arm": t.arm, **event})
            events.append({"event": "trial_terminal", "run_id": result.run_id, **t.to_dict(include_calls=False)})
        events.append({"event": "run_ended", "run_id": result.run_id, "timestamp": result.ended_at})

        _write_jsonl(paths["events"], events)
        _write_jsonl(paths["model_calls"], call_rows)
        _write_jsonl(paths["trials_jsonl"], trial_rows)
        _write_csv(paths["trials_csv"], trial_rows)
        failed = [row for row in trial_rows if not row.get("success")]
        _write_csv(paths["failures"], failed, fieldnames=list(trial_rows[0].keys()) if trial_rows else ["trial_id"])
        _write_json(paths["summary_json"], {"verdict": verdict, "summary": summary})

        summary_rows: list[dict[str, Any]] = []
        for arm, metrics in summary.get("by_arm", {}).items():
            summary_rows.append({"dimension": "arm", "key": arm, **{k: v for k, v in metrics.items() if not isinstance(v, dict)}})
        for dimension, groups in summary.get("slices", {}).items():
            for key, metrics in groups.items():
                summary_rows.append({"dimension": dimension, "key": key, **{k: v for k, v in metrics.items() if not isinstance(v, dict)}})
        _write_csv(paths["summary_csv"], summary_rows)
        _write_json(paths["config"], asdict(result.config))
        _write_json(paths["provenance"], provenance)
        paths["report"].write_text(render_report(summary, verdict, result, provenance, path_strings, include_raw_rows=include_raw_rows), encoding="utf-8")
        return path_strings
