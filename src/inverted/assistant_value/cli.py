from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid
from typing import Any

import yaml

from inverted.cli import _build_models, _expand_env

from . import TEST_NAMES
from .runner import run_assistant_value_test


def load_config(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw = _expand_env(raw)
    if not raw.get("models"):
        raise ValueError("assistant-value config must define at least one model")
    if not raw.get("assistant_value"):
        raise ValueError("assistant-value config must define assistant_value settings")
    return raw


def _progress(done: int, total: int, context: dict[str, Any]) -> None:
    pct = 100.0 * done / total if total else 100.0
    detail = " ".join(f"{k}={v}" for k, v in sorted(context.items()) if k != "test")
    print(f"ASSISTANT_VALUE_PROGRESS test={context.get('test')} {done}/{total} {pct:.1f}% {detail}".rstrip(), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run isolated assistant capability/trust experiments")
    parser.add_argument("--config", required=True)
    parser.add_argument("--test", choices=(*TEST_NAMES, "all"), default="all")
    parser.add_argument("--output-dir", default="runs")
    parser.add_argument("--run-id")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)

    raw = load_config(args.config)
    capture_content = bool((raw.get("assistant_value") or {}).get("capture_content", True))
    if not capture_content:
        raise ValueError("assistant-value experiments require capture_content: true")
    models = _build_models(raw, capture_content=True)
    base_run_id = args.run_id or f"assistant-value-{uuid.uuid4().hex[:12]}"
    tests = TEST_NAMES if args.test == "all" else (args.test,)
    results = []
    try:
        for test_name in tests:
            run_id = f"{base_run_id}-{test_name}" if args.test == "all" else base_run_id
            result = run_assistant_value_test(
                test_name,
                raw,
                models,
                args.output_dir,
                run_id=run_id,
                progress_callback=_progress if args.progress else None,
            )
            results.append(result)
            print(
                json.dumps(
                    {
                        "test_name": test_name,
                        "run_id": run_id,
                        "root": result["root"],
                        "planned_calls": result["planned_calls"],
                        "observed_calls": result["budget"]["used"],
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
                    # The experiment packet is already finalized; model unloading
                    # is resource cleanup, not architecture evidence.
                    pass

    print(json.dumps({"completed": len(results), "tests": [r["test_name"] for r in results]}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
