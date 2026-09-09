"""Capability-ratchet CLI router with isolated zero-call Stage-7/8/9 surfaces."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import cli_legacy as _legacy
from .compilation_cli import COMPILATION_COMMANDS, add_compilation_parsers, handle_compilation_command
from .fine_tuning_cli import FINE_TUNING_COMMANDS, add_fine_tuning_parsers, handle_fine_tuning_command
from .replay_store import ReplayStore
from .tomography_cli import TOMOGRAPHY_COMMANDS, add_tomography_parsers, handle_tomography_command


def __getattr__(name: str):
    """Preserve compatibility for callers that imported legacy CLI helpers."""
    return getattr(_legacy, name)


def _forward_legacy_overrides() -> None:
    for name, value in tuple(globals().items()):
        if name.startswith("_") and not name.startswith("__") and hasattr(_legacy, name):
            setattr(_legacy, name, value)


def _parser(adders) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inverted.capability_ratchet")
    sub = parser.add_subparsers(dest="command", required=True)
    adders(sub)
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
    command = raw[0] if raw else None

    if command in TOMOGRAPHY_COMMANDS:
        args = _parser(add_tomography_parsers).parse_args(raw)
        handler = handle_tomography_command
    elif command in COMPILATION_COMMANDS:
        args = _parser(add_compilation_parsers).parse_args(raw)
        handler = handle_compilation_command
    elif command in FINE_TUNING_COMMANDS:
        args = _parser(add_fine_tuning_parsers).parse_args(raw)
        handler = handle_fine_tuning_command
    else:
        _forward_legacy_overrides()
        return _legacy.main(
            argv,
            live_executor=live_executor,
            live_lab_executor=live_lab_executor,
            live_surface_executor=live_surface_executor,
            live_mutation_executor=live_mutation_executor,
        )

    store = ReplayStore(Path(args.replay_root))
    validation = store.validate()
    if not validation.ok:
        _legacy._print(_legacy._validation_payload(store), stream=sys.stderr)
        return 1
    try:
        payload = handler(store, args)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _legacy._print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
