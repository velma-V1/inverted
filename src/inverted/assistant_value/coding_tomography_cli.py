from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid
from typing import Any

import yaml

from .coding_tomography_campaign import run_coding_tomography_campaign


def load_tomography_config(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw.get("coding_tomography"), dict):
        raise ValueError("config must define coding_tomography")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Claude Code / Codex coding-system tomography"
    )
    parser.add_argument(
        "--config",
        default="configs/coding-system-tomography.yaml",
    )
    parser.add_argument("--output-dir", default="runs")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Materialize and validate the plan without launching Claude Code or Codex.",
    )
    args = parser.parse_args(argv)

    config = load_tomography_config(args.config)
    run_id = args.run_id or f"coding-tomography-{uuid.uuid4().hex[:12]}"
    result = run_coding_tomography_campaign(
        config,
        output_dir=args.output_dir,
        run_id=run_id,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
