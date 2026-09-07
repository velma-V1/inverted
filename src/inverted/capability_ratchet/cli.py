"""Inspection-first CLI for TEST_REPLAY. Live model execution is hard-gated."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .core import Partition, PromotionState, ReplayRequest, ReplayResult, to_payload
from .historical import V2EvidenceSource, preview_v2_failures, seed_v2_failures
from .query import ReplaySelector, select_failures
from .replay_store import ReplayStore

_SENSITIVE_DISPLAY_KEYS = {"authorization", "api_key", "apikey", "token", "password", "secret"}


def _print(payload: Any, *, stream=None) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
          file=sys.stdout if stream is None else stream)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("<REDACTED>" if str(key).lower().replace("-", "_") in _SENSITIVE_DISPLAY_KEYS else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _selector(args: argparse.Namespace) -> ReplaySelector:
    snapshots = tuple(getattr(args, "snapshot_ids", ()) or ())
    one = getattr(args, "snapshot_id", None)
    if one:
        snapshots = snapshots + (one,)
    return ReplaySelector(
        source_model=getattr(args, "source_model", None),
        target_model=getattr(args, "target_model", None),
        family=getattr(args, "family", None),
        difficulty=getattr(args, "difficulty", None),
        failure_class=getattr(args, "failure_class", None),
        campaign=getattr(args, "campaign", None),
        partition=getattr(args, "partition", None),
        promotion_state=getattr(args, "promotion_state", None),
        snapshot_ids=snapshots,
    )


def _validation_payload(store: ReplayStore) -> dict[str, Any]:
    result = store.validate()
    return {
        "ok": result.ok, "row_count": result.row_count,
        "unique_record_count": result.unique_record_count,
        "missing_assets": list(result.missing_assets),
        "hash_mismatches": list(result.hash_mismatches),
        "broken_lineage": list(result.broken_lineage),
        "duplicate_record_ids": list(result.duplicate_record_ids),
        "MODEL_CALLS": 0,
    }


def _add_selector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-model")
    parser.add_argument("--target-model")
    parser.add_argument("--family")
    parser.add_argument("--difficulty", type=int)
    parser.add_argument("--failure-class")
    parser.add_argument("--campaign")
    parser.add_argument("--partition", choices=[item.value for item in Partition])
    parser.add_argument("--promotion-state", choices=[item.value for item in PromotionState])
    parser.add_argument("--snapshot-id", action="append", dest="snapshot_ids")


def _replay_counts(store: ReplayStore) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in store.records():
        if isinstance(record, (ReplayRequest, ReplayResult)):
            root = record.failure_snapshot_id
            counts[root] = counts.get(root, 0) + 1
    return counts


def _list_rows(store: ReplayStore, selector: ReplaySelector) -> list[dict[str, Any]]:
    counts = _replay_counts(store)
    return [{
        "failure_snapshot_id": fixture.failure_snapshot_id,
        "source_model": fixture.source_model_id, "family": fixture.family,
        "failure_classes": list(fixture.failure_classes),
        "campaign": fixture.source_campaign_id, "partition": fixture.partition.value,
        "promotion_state": fixture.promotion_state.value,
        "replay_count": counts.get(fixture.failure_snapshot_id, 0),
    } for fixture in select_failures(store, selector)]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inverted.capability_ratchet")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--replay-root", required=True)

    listing = sub.add_parser("list")
    listing.add_argument("--replay-root", required=True)
    _add_selector_args(listing)

    show = sub.add_parser("show")
    show.add_argument("--replay-root", required=True)
    show.add_argument("--snapshot-id", required=True)

    seed = sub.add_parser("seed-v2")
    seed.add_argument("--source", required=True)
    seed.add_argument("--replay-root")
    seed.add_argument("--dry-run", action="store_true")

    plan = sub.add_parser("plan-replay")
    plan.add_argument("--replay-root", required=True)
    _add_selector_args(plan)
    plan.add_argument("--limit", type=int, default=20)
    plan.add_argument("--target-digest")

    execute = sub.add_parser("execute-replay")
    execute.add_argument("--replay-root", required=True)
    execute.add_argument("--snapshot-id", required=True)
    execute.add_argument("--target-model")
    execute.add_argument("--target-digest")
    execute.add_argument("--decision-id", default="D-REPLAY")
    execute.add_argument("--hypothesis-id", default="H-REPRODUCIBILITY")
    execute.add_argument("--allow-model-calls", action="store_true")
    return parser


def _plan_rows(store: ReplayStore, args: argparse.Namespace) -> list[dict[str, Any]]:
    selector = _selector(args)
    selector = ReplaySelector(
        source_model=selector.source_model, family=selector.family, difficulty=selector.difficulty,
        failure_class=selector.failure_class, campaign=selector.campaign,
        partition=selector.partition, promotion_state=selector.promotion_state,
        snapshot_ids=selector.snapshot_ids,
    )
    selected = select_failures(store, selector)
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")
    rows: list[dict[str, Any]] = []
    for fixture in selected[:args.limit]:
        visible = store.read_asset(fixture.model_visible_asset_sha256)
        envelopes = visible.get("request_envelopes") if isinstance(visible, dict) else None
        if not isinstance(envelopes, list) or not envelopes:
            raise ValueError(f"fixture {fixture.failure_snapshot_id} lacks request envelopes")
        cross_model = args.target_model is not None and args.target_model != fixture.source_model_id
        if cross_model and not args.target_digest:
            raise ValueError("cross-model plan requires explicit target digest")
        if not cross_model and args.target_digest is not None and args.target_digest != fixture.source_model_digest:
            raise ValueError("same-model target digest conflicts with source digest")
        rows.append({
            "failure_snapshot_id": fixture.failure_snapshot_id,
            "mode": "CROSS_MODEL" if cross_model else "EXACT",
            "source_model": fixture.source_model_id,
            "source_digest": fixture.source_model_digest,
            "target_model": args.target_model or fixture.source_model_id,
            "target_digest": args.target_digest or (None if cross_model else fixture.source_model_digest),
            "changed_dimensions": ["target_model"] if cross_model else [],
            "projected_physical_calls": len(envelopes),
        })
    return rows



def _execute_qwen_replay(store: ReplayStore, args: argparse.Namespace) -> dict[str, Any]:
    """Construct live model machinery only after the explicit CLI safety gate."""
    try:
        fixture = store.get_failure(args.snapshot_id)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
    if fixture.oracle_asset_sha256 is None:
        raise ValueError("fixture has no self-contained oracle asset; refusing unscored replay")
    store.read_asset(fixture.oracle_asset_sha256)

    target_model = args.target_model or fixture.source_model_id
    if target_model == fixture.source_model_id:
        if args.target_digest is not None and args.target_digest != fixture.source_model_digest:
            raise ValueError("same-model target digest conflicts with source digest")
        request = ReplayRequest.for_exact(
            fixture, decision_id=args.decision_id, hypothesis_id=args.hypothesis_id,
        )
    else:
        if not args.target_digest:
            raise ValueError("cross-model execution requires explicit target digest")
        from .core import ReplayMode
        request = ReplayRequest(
            replay_request_id=f"replay-cli-{fixture.failure_snapshot_id}-{target_model}",
            failure_snapshot_id=fixture.failure_snapshot_id,
            parent_failure_snapshot_id=fixture.failure_snapshot_id,
            parent_state_hash=fixture.state_hash,
            decision_id=args.decision_id, hypothesis_id=args.hypothesis_id,
            expected_causal_implication="compare the frozen failure state on a compatible target model",
            mode=ReplayMode.CROSS_MODEL, source_model_id=fixture.source_model_id,
            source_model_digest=fixture.source_model_digest, target_model_id=target_model,
            target_model_digest=args.target_digest, partition=fixture.partition,
            changed_dimensions=("target_model",), overrides={},
        )

    from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter
    from .qwen_replay import QwenReplayAdapter, V2ReplayScorer
    from .replay import ReplayExecutor

    qwen = QwenOllamaAdapter(model_id=target_model)
    adapter = QwenReplayAdapter(qwen, scorer=V2ReplayScorer(store))
    result = ReplayExecutor(store, {target_model: adapter}).execute(request)
    payload = to_payload(result)
    payload["MODEL_CALLS"] = int(result.metrics.get("physical_calls", 0) or 0)
    return payload

def main(argv: list[str] | None = None, *, live_executor=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "execute-replay" and not args.allow_model_calls:
        print("execute-replay requires explicit --allow-model-calls", file=sys.stderr)
        return 2

    if args.command == "validate":
        payload = _validation_payload(ReplayStore(Path(args.replay_root)))
        _print(payload)
        return 0 if payload["ok"] else 1

    if args.command == "seed-v2":
        source = V2EvidenceSource(Path(args.source))
        if args.dry_run:
            payload = asdict(preview_v2_failures(source))
            payload["MODEL_CALLS"] = 0
            _print(payload)
            return 0
        if not args.replay_root:
            print("seed-v2 requires --replay-root unless --dry-run is used", file=sys.stderr)
            return 2
        payload = asdict(seed_v2_failures(source, ReplayStore(Path(args.replay_root))))
        payload["MODEL_CALLS"] = 0
        _print(payload)
        return 0

    store = ReplayStore(Path(args.replay_root))
    validation = store.validate()
    if not validation.ok:
        _print(_validation_payload(store), stream=sys.stderr)
        return 1

    if args.command == "list":
        _print({"failures": _list_rows(store, _selector(args)), "MODEL_CALLS": 0})
        return 0
    if args.command == "show":
        try:
            fixture = store.get_failure(args.snapshot_id)
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        _print({
            "fixture": to_payload(fixture),
            "visible_asset": _redact(store.read_asset(fixture.model_visible_asset_sha256)),
            "MODEL_CALLS": 0,
        })
        return 0
    if args.command == "plan-replay":
        try:
            plans = _plan_rows(store, args)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        _print({"plans": plans, "MODEL_CALLS": 0})
        return 0
    if args.command == "execute-replay":
        runner = _execute_qwen_replay if live_executor is None else live_executor
        try:
            payload = runner(store, args)
        except (TypeError, ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        _print(payload)
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
