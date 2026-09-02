from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid
from typing import Any

import yaml

from inverted.cli import _build_models, _expand_env

from .runner import run_decision_harvest_from_config


def load_config(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw = _expand_env(raw)
    if not raw.get("models"):
        raise ValueError("black-magic config must define at least one model")
    if not raw.get("black_magic"):
        raise ValueError("black-magic config must define black_magic settings")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run additive black-magic evidence experiments")
    parser.add_argument("--config", required=True)
    parser.add_argument("--stage", choices=("decision_harvest",), default="decision_harvest")
    parser.add_argument("--output-dir", default="runs")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)

    raw = load_config(args.config)
    capture = bool((raw.get("black_magic") or {}).get("capture_content", True))
    if not capture:
        raise ValueError("black-magic experiments require capture_content: true")
    models = _build_models(raw, capture_content=True)
    run_id = args.run_id or f"black-magic-{uuid.uuid4().hex[:12]}"
    try:
        result = run_decision_harvest_from_config(raw, models, args.output_dir, run_id=run_id)
        print(
            json.dumps(
                {
                    "stage": result["stage"],
                    "run_id": run_id,
                    "root": result["root"],
                    "planned_external_actions": result["planned_external_actions"],
                    "observed_external_actions": result["budget"]["used"],
                    "instrument_validation": result["instrument_validation"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    finally:
        for model in models:
            unload = getattr(model, "unload", None)
            if callable(unload):
                try:
                    unload()
                except Exception:
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
