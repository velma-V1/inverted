"""Qwen tuning entrypoint with Test1B-v3 universal-campaign defaults."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import qwen_thinking_tuning_base as _base

# Preserve the established V1/public surface while replacing only the V2 campaign entrypoint.
for _name, _value in vars(_base).items():
    if not _name.startswith("__"):
        globals().setdefault(_name, _value)


def _v2_dry_run_payload() -> dict[str, Any]:
    from .universal_tuning.campaign import ExperimentSpec, call_geometry
    from .universal_tuning.statistics import CHECKPOINTS

    spec = ExperimentSpec()
    geometry = call_geometry(
        len(TASK_FAMILIES),
        parameter_screen_enabled=spec.parameter_screen_enabled,
    )
    return {
        "protocol_version": 2,
        "model": MODEL_ID,
        "task_families": len(TASK_FAMILIES),
        "tasks_per_family": spec.tasks_per_family,
        "frozen_atomic_tasks": len(TASK_FAMILIES) * spec.tasks_per_family,
        "atomic_batch_size": 5,
        "checkpoints": list(CHECKPOINTS),
        "minimum_certification_atomic": CHECKPOINTS[0],
        "parameter_screen_enabled": spec.parameter_screen_enabled,
        "call_geometry": geometry,
        "hard_call_ceiling": geometry["worst_case"],
    }


def _main_v2(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run universal V2 Qwen operating-surface tuner."
    )
    parser.add_argument("--run-root")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    from .universal_tuning.campaign import ExperimentSpec, call_geometry

    default_spec = ExperimentSpec()
    parser.add_argument(
        "--max-calls",
        type=int,
        default=call_geometry(
            len(TASK_FAMILIES),
            parameter_screen_enabled=default_spec.parameter_screen_enabled,
        )["worst_case"],
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps(_v2_dry_run_payload(), sort_keys=True))
        return 0
    from .universal_tuning.campaign import run_qwen_v2_cli

    return run_qwen_v2_cli(args)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    protocol = "v2"
    if "--protocol" in args:
        index = args.index("--protocol")
        if index + 1 >= len(args):
            raise ValueError("--protocol requires v1 or v2")
        protocol = args[index + 1].lower()
        del args[index : index + 2]
    if protocol == "v1":
        return _base._main_v1(args)
    if protocol == "v2":
        return _main_v2(args)
    raise ValueError("--protocol must be v1 or v2")


if __name__ == "__main__":
    raise SystemExit(main())
