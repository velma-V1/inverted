from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid
from typing import Any

import yaml

from inverted.cli import _build_models, _expand_env
from .epistemic_runner import run_epistemic_from_config


def load_config(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw = _expand_env(raw)
    if not raw.get("models") or not raw.get("black_magic"):
        raise ValueError("models and black_magic config required")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Epistemic Mechanics Harvest")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default="runs")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    raw = load_config(args.config)
    if not bool((raw.get("black_magic") or {}).get("capture_content", True)):
        raise ValueError("capture_content=true required")
    models = _build_models(raw, capture_content=True)
    run_id = args.run_id or f"epistemic-{uuid.uuid4().hex[:12]}"
    result = run_epistemic_from_config(raw, models, args.output_dir, run_id=run_id)
    print(json.dumps({"run_id": run_id, "root": result["root"], "planned_external_actions": result["planned_external_actions"], "observed_external_actions": result["budget"]["used"], "instrument_validation": result["instrument_validation"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
