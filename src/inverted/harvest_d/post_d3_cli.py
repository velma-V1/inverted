from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .post_d3_analysis import analyze_d3_v1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run zero-call post-D3-v1 salvage analysis")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = analyze_d3_v1(Path(args.input), Path(args.output))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"POST-D3 ANALYSIS ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
