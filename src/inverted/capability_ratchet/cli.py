"""Inspection-first CLI for TEST_REPLAY. Live model execution is hard-gated."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .autopsy import FailureAutopsy
from .causal_store import CausalEvidenceStore
from .core import Partition, PromotionState, ReplayRequest, ReplayResult, to_payload
from .historical import V2EvidenceSource, preview_v2_failures, seed_v2_failures
from .interventions import InterventionGenerator
from .lab import FailureLab, FailureResearchProgram
from .mechanisms import MechanismLocalizer
from .query import ReplaySelector, select_failures, select_surface_study
from .replay_store import ReplayStore
from .surface_analysis import SurfaceAnalyzer
from .surface_bootstrap import plan_eligible_surfaces
from .surface_evidence import SurfaceEvidenceCompiler
from .surface_interventions import SurfaceInterventionCompiler
from .surface_lab import OperatingSurfaceLab
from .surface_planner import SurfacePlanner
from .surface_store import SurfaceEvidenceStore
from .tournament import TournamentPlanner

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
        mechanism=getattr(args, "mechanism", None),
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
    parser.add_argument("--mechanism")
    parser.add_argument("--snapshot-id", action="append", dest="snapshot_ids")


def _add_lab_args(parser: argparse.ArgumentParser, *, executable: bool = False) -> None:
    parser.add_argument("--replay-root", required=True)
    parser.add_argument("--causal-root", required=True)
    parser.add_argument("--snapshot-id", required=True)
    if executable:
        parser.add_argument("--allow-model-calls", action="store_true")


def _add_surface_args(
    parser: argparse.ArgumentParser,
    *,
    executable: bool = False,
    auto_eligible: bool = False,
) -> None:
    parser.add_argument("--replay-root", required=True)
    parser.add_argument("--causal-root", required=True)
    parser.add_argument("--surface-root", required=True)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--study-id")
    selector.add_argument("--mechanism-id")
    if auto_eligible:
        selector.add_argument("--auto-eligible", action="store_true")
    if executable:
        parser.add_argument("--allow-model-calls", action="store_true")


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

    autopsy = sub.add_parser("autopsy")
    _add_lab_args(autopsy)

    plan_lab = sub.add_parser("plan-lab")
    _add_lab_args(plan_lab)

    show_lab = sub.add_parser("show-lab")
    _add_lab_args(show_lab)

    run_lab = sub.add_parser("run-lab")
    _add_lab_args(run_lab, executable=True)

    plan_surface = sub.add_parser("plan-surface")
    _add_surface_args(plan_surface, auto_eligible=True)
    plan_surface.add_argument("--source")

    show_surface = sub.add_parser("show-surface")
    _add_surface_args(show_surface)

    run_surface = sub.add_parser("run-surface")
    _add_surface_args(run_surface, executable=True)
    return parser


def _plan_rows(store: ReplayStore, args: argparse.Namespace) -> list[dict[str, Any]]:
    selector = _selector(args)
    selector = ReplaySelector(
        source_model=selector.source_model, family=selector.family, difficulty=selector.difficulty,
        failure_class=selector.failure_class, campaign=selector.campaign,
        partition=selector.partition, promotion_state=selector.promotion_state,
        mechanism=selector.mechanism, snapshot_ids=selector.snapshot_ids,
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


def _build_lab(store: ReplayStore, causal_root: Path) -> FailureLab:
    causal = CausalEvidenceStore(causal_root, replay_store=store)
    return FailureLab(
        store,
        causal,
        FailureAutopsy(store, causal),
        InterventionGenerator(store, causal),
        TournamentPlanner(causal),
        MechanismLocalizer(store, causal),
    )


def _build_surface_lab(store: ReplayStore, causal_root: Path, surface_root: Path) -> OperatingSurfaceLab:
    causal = CausalEvidenceStore(causal_root, replay_store=store)
    surface = SurfaceEvidenceStore(surface_root, replay_store=store, causal_store=causal)
    evidence = SurfaceEvidenceCompiler(store, causal, surface)
    return OperatingSurfaceLab(
        store,
        causal,
        surface,
        evidence,
        SurfacePlanner(surface, evidence),
        SurfaceInterventionCompiler(store, causal),
        SurfaceAnalyzer(surface),
    )


def _divergence_payload(divergence) -> dict[str, Any]:
    return {
        "divergence_class": divergence.divergence_class.value,
        "observable_path": divergence.observable_path,
        "event_index": divergence.event_index,
        "evidence_refs": list(divergence.evidence_refs),
        "confidence": divergence.confidence,
    }


def _hypothesis_payload(hypothesis) -> dict[str, Any]:
    return {
        "hypothesis_id": hypothesis.hypothesis_id,
        "owner_candidate": hypothesis.owner_candidate.value,
        "claim": hypothesis.claim,
        "expected_if_true": hypothesis.expected_if_true,
        "falsifier": hypothesis.falsifier,
        "status": hypothesis.status.value,
        "protected_exploration": hypothesis.protected_exploration,
    }


def _intervention_payload(intervention) -> dict[str, Any]:
    return {
        "intervention_id": intervention.intervention_id,
        "hypothesis_id": intervention.hypothesis_id,
        "kind": intervention.kind.value,
        "label": intervention.label,
        "changed_dimensions": list(intervention.changed_dimensions),
        "expected_causal_implication": intervention.expected_causal_implication,
        "projected_physical_calls": intervention.projected_physical_calls,
        "composition": list(intervention.composition),
        "sham_for": intervention.sham_for,
        "ablates": list(intervention.ablates),
        "protected_exploration": intervention.protected_exploration,
    }


def _branch_payload(branch) -> dict[str, Any]:
    return {
        "branch_id": branch.branch_id,
        "hypothesis_id": branch.hypothesis_id,
        "intervention_ids": list(branch.intervention_ids),
        "mode": branch.mode,
        "decision_reason": branch.decision_reason,
        "unresolved_decision": branch.unresolved_decision,
        "protected_exploration": branch.protected_exploration,
        "projected_physical_calls": branch.projected_physical_calls,
    }


def _autopsy_payload(program: FailureResearchProgram) -> dict[str, Any]:
    return {
        "failure_snapshot_id": program.failure_snapshot_id,
        "root_failure_snapshot_id": program.root_failure_snapshot_id,
        "first_divergence": _divergence_payload(program.autopsy.first_divergence),
        "hypotheses": [_hypothesis_payload(item) for item in program.autopsy.hypotheses],
        "evidence_refs": list(program.autopsy.evidence_refs),
        "unresolved_questions": list(program.autopsy.unresolved_questions),
        "MODEL_CALLS": 0,
    }


def _program_payload(program: FailureResearchProgram) -> dict[str, Any]:
    return {
        "failure_snapshot_id": program.failure_snapshot_id,
        "root_failure_snapshot_id": program.root_failure_snapshot_id,
        "first_divergence": _divergence_payload(program.autopsy.first_divergence),
        "hypothesis_ids": [item.hypothesis_id for item in program.autopsy.hypotheses],
        "interventions": [_intervention_payload(item) for item in program.interventions],
        "branches": [_branch_payload(item) for item in program.tournament.branches],
        "call_geometry": {
            "minimum": program.tournament.minimum_physical_calls,
            "expected": program.tournament.expected_physical_calls,
            "worst_case": program.tournament.worst_case_physical_calls,
        },
        "replay_request_ids": [item.replay_request_id for item in program.replay_requests],
        "projected_physical_calls": program.projected_physical_calls,
        "MODEL_CALLS": 0,
    }


def _surface_study_payload(study) -> dict[str, Any]:
    return {
        "study_id": study.study_id,
        "failure_snapshot_id": study.failure_snapshot_id,
        "mechanism_id": study.mechanism_id,
        "parent_state_hash": study.parent_state_hash,
        "partition": study.partition.value,
        "promotion_state": study.promotion_state.value,
        "decision_id": study.decision_id,
        "axes": [item.value for item in study.axes],
        "axis_values": {key: list(values) for key, values in study.axis_values.items()},
        "decision_critical_reason": study.decision_critical_reason,
    }


def _surface_point_payload(point) -> dict[str, Any]:
    return {
        "surface_point_id": point.surface_point_id,
        "axis": point.axis.value,
        "value": point.value,
        "decision_id": point.decision_id,
        "protected_exploration": point.protected_exploration,
    }


def _surface_plan_payload(study, plan) -> dict[str, Any]:
    return {
        "study_id": study.study_id,
        "failure_snapshot_id": study.failure_snapshot_id,
        "mechanism_id": study.mechanism_id,
        "points": [_surface_point_payload(point) for point in plan.points],
        "decision_reason": plan.decision_reason,
        "stop_reason": plan.stop_reason,
        "call_geometry": {
            "minimum": plan.minimum_physical_calls,
            "expected": plan.expected_physical_calls,
            "worst_case": plan.worst_case_physical_calls,
            "protected_exploration": plan.protected_exploration_calls,
        },
        "MODEL_CALLS": 0,
    }


def _auto_surface_payload(lab: OperatingSurfaceLab, args: argparse.Namespace) -> dict[str, Any]:
    source = V2EvidenceSource(Path(args.source)) if getattr(args, "source", None) else None
    planned = plan_eligible_surfaces(lab, source=source)
    if not planned:
        return {
            "MODEL_CALLS": 0,
            "eligible_mechanisms": [],
            "plans": [],
            "status": "NO_ELIGIBLE_MECHANISMS",
        }
    return {
        "status": "SURFACE_PLAN_READY",
        "eligible_mechanisms": sorted({item.study.mechanism_id for item in planned}),
        "plans": [
            {
                "study": _surface_study_payload(item.study),
                "reused_points": [_surface_point_payload(point) for point in item.reused_points],
                "unresolved_points": [_surface_point_payload(point) for point in item.unresolved_points],
                "historical_prior_count": item.historical_prior_count,
                "plan": _surface_plan_payload(item.study, item.plan),
            }
            for item in planned
        ],
        "MODEL_CALLS": 0,
    }


def _surface_observation_payload(row) -> dict[str, Any]:
    return {
        "observation_id": row.observation_id,
        "surface_point_id": row.surface_point_id,
        "axis": row.axis.value,
        "value": row.value,
        "evidence_kind": row.evidence_kind.value,
        "replay_result_ids": list(row.replay_result_ids),
        "source_evidence_refs": list(row.source_evidence_refs),
        "metrics": dict(row.metrics),
    }


def _surface_profile_payload(profile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "axis": profile.axis.value,
        "disposition": profile.disposition.value,
        "lower_useful": profile.lower_useful,
        "upper_useful": profile.upper_useful,
        "recommended_region": list(profile.recommended_region),
        "harm_onset": profile.harm_onset,
        "evidence_refs": list(profile.evidence_refs),
        "unresolved_edges": list(profile.unresolved_edges),
        "promotion_ceiling": profile.promotion_ceiling.value,
    }


def _surface_study(lab: OperatingSurfaceLab, args: argparse.Namespace):
    return select_surface_study(
        lab.surface_store,
        study_id=getattr(args, "study_id", None),
        mechanism_id=getattr(args, "mechanism_id", None),
    )


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


def _execute_qwen_lab(
    store: ReplayStore,
    causal_root: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Construct live lab adapters only after ``run-lab`` passes its gate."""
    lab = _build_lab(store, causal_root)
    program = lab.prepare(args.snapshot_id)
    fixture = program.fixture
    if fixture.oracle_asset_sha256 is None:
        raise ValueError("fixture has no self-contained oracle asset; refusing unscored lab execution")
    store.read_asset(fixture.oracle_asset_sha256)

    from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter
    from .qwen_replay import QwenReplayAdapter, V2ReplayScorer

    qwen = QwenOllamaAdapter(model_id=fixture.source_model_id)
    adapter = QwenReplayAdapter(qwen, scorer=V2ReplayScorer(store))
    result = lab.execute(program, adapters={fixture.source_model_id: adapter})
    physical_calls = sum(int(item.metrics.get("physical_calls", 0) or 0) for item in result.replay_results)
    return {
        "failure_snapshot_id": program.failure_snapshot_id,
        "root_failure_snapshot_id": program.root_failure_snapshot_id,
        "replay_result_ids": [item.replay_result_id for item in result.replay_results],
        "child_failure_snapshot_ids": list(result.child_failure_snapshot_ids),
        "supported_hypotheses": list(result.assessment.supported_hypotheses),
        "falsified_hypotheses": list(result.assessment.falsified_hypotheses),
        "movement_events": [item.promotion_event_id for item in result.assessment.promotion_events],
        "MODEL_CALLS": physical_calls,
    }


def _execute_qwen_surface(
    store: ReplayStore,
    causal_root: Path,
    surface_root: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Construct live surface adapter only after ``run-surface`` passes its gate."""
    lab = _build_surface_lab(store, causal_root, surface_root)
    study = _surface_study(lab, args)
    plan = lab.prepare(study.study_id)
    if not plan.points:
        return _surface_plan_payload(study, plan)
    fixture = store.get_failure(study.failure_snapshot_id)
    if fixture.oracle_asset_sha256 is None:
        raise ValueError("fixture has no self-contained oracle asset; refusing unscored surface execution")
    store.read_asset(fixture.oracle_asset_sha256)

    from inverted.universal_tuning.qwen_ollama import QwenOllamaAdapter
    from .qwen_replay import QwenReplayAdapter, V2ReplayScorer

    qwen = QwenOllamaAdapter(model_id=fixture.source_model_id)
    adapter = QwenReplayAdapter(qwen, scorer=V2ReplayScorer(store))
    result = lab.execute(plan, adapters={fixture.source_model_id: adapter})
    physical_calls = sum(int(item.metrics.get("physical_calls", 0) or 0) for item in result.replay_results)
    return {
        "study_id": study.study_id,
        "mechanism_id": study.mechanism_id,
        "replay_result_ids": [item.replay_result_id for item in result.replay_results],
        "child_failure_snapshot_ids": list(result.child_failure_snapshot_ids),
        "profile": _surface_profile_payload(result.profile),
        "next_plan": _surface_plan_payload(study, result.next_plan),
        "MODEL_CALLS": physical_calls,
    }


def main(
    argv: list[str] | None = None,
    *,
    live_executor=None,
    live_lab_executor=None,
    live_surface_executor=None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "execute-replay" and not args.allow_model_calls:
        print("execute-replay requires explicit --allow-model-calls", file=sys.stderr)
        return 2
    if args.command == "run-lab" and not args.allow_model_calls:
        print("run-lab requires explicit --allow-model-calls", file=sys.stderr)
        return 2
    if args.command == "run-surface" and not args.allow_model_calls:
        print("run-surface requires explicit --allow-model-calls", file=sys.stderr)
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
    if args.command in {"autopsy", "plan-lab", "show-lab"}:
        causal_root = Path(args.causal_root)
        try:
            lab = _build_lab(store, causal_root)
            program = lab.prepare(args.snapshot_id)
            if args.command == "autopsy":
                payload = _autopsy_payload(program)
            elif args.command == "plan-lab":
                payload = _program_payload(program)
            else:
                payload = {
                    **_program_payload(program),
                    "replay_store_valid": store.validate().ok,
                    "causal_store_valid": lab.causal_store.validate().ok,
                    "mechanism_graph_present": lab.localizer.mechanism_graph_path.exists(),
                }
        except (KeyError, TypeError, ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        _print(payload)
        return 0
    if args.command == "run-lab":
        causal_root = Path(args.causal_root)
        runner = _execute_qwen_lab if live_lab_executor is None else live_lab_executor
        try:
            payload = runner(store, causal_root, args)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        _print(payload)
        return 0
    if args.command in {"plan-surface", "show-surface"}:
        causal_root = Path(args.causal_root)
        surface_root = Path(args.surface_root)
        try:
            lab = _build_surface_lab(store, causal_root, surface_root)
            if args.command == "plan-surface" and getattr(args, "auto_eligible", False):
                payload = _auto_surface_payload(lab, args)
            else:
                study = _surface_study(lab, args)
                if args.command == "plan-surface":
                    payload = _surface_plan_payload(study, lab.prepare(study.study_id))
                else:
                    payload = {
                        "study": _surface_study_payload(study),
                        "observations": [
                            _surface_observation_payload(row)
                            for row in lab.surface_store.observations(study.study_id)
                        ],
                        "profiles": [
                            _surface_profile_payload(row)
                            for row in lab.surface_store.profiles(study.mechanism_id)
                            if row.study_id == study.study_id
                        ],
                        "replay_store_valid": store.validate().ok,
                        "causal_store_valid": lab.causal_store.validate().ok,
                        "surface_store_valid": lab.surface_store.validate().ok,
                        "MODEL_CALLS": 0,
                    }
        except (KeyError, TypeError, ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        _print(payload)
        return 0
    if args.command == "run-surface":
        causal_root = Path(args.causal_root)
        surface_root = Path(args.surface_root)
        runner = _execute_qwen_surface if live_surface_executor is None else live_surface_executor
        try:
            payload = runner(store, causal_root, surface_root, args)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        _print(payload)
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
