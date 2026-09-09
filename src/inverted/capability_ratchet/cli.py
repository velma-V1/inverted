"""Capability-ratchet CLI router with isolated zero-call Stage-7 tomography surfaces."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import cli_legacy as _legacy
from .replay_store import ReplayStore
from .tomography_cli import (
    TOMOGRAPHY_COMMANDS,
    add_tomography_parsers,
    handle_tomography_command,
)


def __getattr__(name: str):
    """Preserve compatibility for callers that imported legacy CLI helpers."""
    return getattr(_legacy, name)


def _build_tomography_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inverted.capability_ratchet")
    sub = parser.add_subparsers(dest="command", required=True)
    add_tomography_parsers(sub)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    live_executor=None,
    live_lab_executor=None,
    live_surface_executor=None,
    live_mutation_executor=None,
) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw or raw[0] not in TOMOGRAPHY_COMMANDS:
        return _legacy.main(
            argv,
            live_executor=live_executor,
            live_lab_executor=live_lab_executor,
            live_surface_executor=live_surface_executor,
            live_mutation_executor=live_mutation_executor,
        )

    args = _build_tomography_parser().parse_args(raw)
    store = ReplayStore(Path(args.replay_root))
    validation = store.validate()
    if not validation.ok:
        _legacy._print(_legacy._validation_payload(store), stream=sys.stderr)
        return 1
    try:
        payload = handle_tomography_command(store, args)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _legacy._print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
