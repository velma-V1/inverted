"""Zero-call CLI adapter for Stage-7 tomography planning and inspection."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from .autopsy import FailureAutopsy
from .causal_core import DivergenceClass
from .causal_store import CausalEvidenceStore
from .core import FailureFixture, Partition
from .interventions import InterventionGenerator
from .query import ReplaySelector, select_failures
from .replay_store import ReplayStore
from .tomography_core import TomographyAxis, TomographyAssessment, TomographyProbeSpec, TomographyStudy
from .tomography_eligibility import (
    TomographyEligibilityStatus,
    classify_tomography_eligibility,
    plan_eligible_tomography,
)
from .tomography_store import TomographyEvidenceStore

TOMOGRAPHY_COMMANDS = frozenset({
    "scan-tomography-eligibility",
    "plan-tomography",
    "show-tomography-study",
    "show-tomography-assessment",
})

_DECISIONS: dict[DivergenceClass, tuple[str, ...]] = {
    DivergenceClass.TOOL_CAPABILITY: ("D2", "D6"),
    DivergenceClass.TOOL_SELECTION: ("D2", "D6"),
    DivergenceClass.TOOL_ARGUMENTS: ("D2", "D6"),
    DivergenceClass.TOOL_INTERPRETATION: ("D2", "D6", "D8"),
    DivergenceClass.VERIFIER_FEEDBACK: ("D2", "D8"),
    DivergenceClass.RECOVERY_POLICY: ("D2", "D8"),
    DivergenceClass.SKILL_DEFICIT: ("D2", "D7", "D12"),
    DivergenceClass.MODEL_CAPABILITY_LIMIT: ("D2", "D11", "D12"),
}

_TARGET_AXIS: dict[DivergenceClass, TomographyAxis] = {
    DivergenceClass.TOOL_CAPABILITY: TomographyAxis.TOOL_AVAILABILITY,
    DivergenceClass.TOOL_SELECTION: TomographyAxis.TOOL_SELECTION,
    DivergenceClass.TOOL_ARGUMENTS: TomographyAxis.TOOL_ARGUMENTS,
    DivergenceClass.TOOL_INTERPRETATION: TomographyAxis.TOOL_RESULT_INTERPRETATION,
    DivergenceClass.VERIFIER_FEEDBACK: TomographyAxis.VERIFIER_FEEDBACK,
    DivergenceClass.RECOVERY_POLICY: TomographyAxis.TARGETED_RECOVERY,
    DivergenceClass.SKILL_DEFICIT: TomographyAxis.SKILL_PROCEDURE,
}


def add_tomography_parsers(sub: argparse._SubParsersAction) -> None:
    """Register only query/planning surfaces; Stage 7 exposes no execute command."""

    scan = sub.add_parser("scan-tomography-eligibility")
    _add_roots(scan)

    plan = sub.add_parser("plan-tomography")
    _add_roots(plan)
    selector = plan.add_mutually_exclusive_group(required=True)
    selector.add_argument("--study-id")
    selector.add_argument("--auto-eligible", action="store_true")

    show_study = sub.add_parser("show-tomography-study")
    _add_roots(show_study)
    show_study.add_argument("--study-id", required=True)

    show_assessment = sub.add_parser("show-tomography-assessment")
    _add_roots(show_assessment)
    show_assessment.add_argument("--study-id", required=True)


def _add_roots(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--replay-root", required=True)
    parser.add_argument("--causal-root", required=True)
    parser.add_argument("--tomography-root", required=True)


def _stage7_evidence(fixture: FailureFixture) -> Mapping[str, Any]:
    value = fixture.metadata.get("stage7_evidence")
    return value if isinstance(value, Mapping) else {}


def _explicit_divergence(fixture: FailureFixture) -> DivergenceClass | None:
    evidence = _stage7_evidence(fixture)
    explicit = evidence.get("divergence_class")
    if isinstance(explicit, str):
        try:
            kind = DivergenceClass(explicit)
        except ValueError:
            kind = None
        if kind in _DECISIONS:
            return kind
    rules = (
        (bool(evidence.get("required_tool_absent")), DivergenceClass.TOOL_CAPABILITY),
        (evidence.get("tool_available") is True and evidence.get("tool_selected") is False, DivergenceClass.TOOL_SELECTION),
        (evidence.get("tool_selected_correct") is True and evidence.get("tool_arguments_correct") is False, DivergenceClass.TOOL_ARGUMENTS),
        (evidence.get("tool_result_available") is True and evidence.get("tool_result_interpreted_correctly") is False, DivergenceClass.TOOL_INTERPRETATION),
        (bool(evidence.get("verifier_would_detect")), DivergenceClass.VERIFIER_FEEDBACK),
        (bool(evidence.get("targeted_recovery_defined")), DivergenceClass.RECOVERY_POLICY),
        (bool(evidence.get("reusable_skill_required")), DivergenceClass.SKILL_DEFICIT),
        (bool(evidence.get("external_supports_exhausted")), DivergenceClass.MODEL_CAPABILITY_LIMIT),
    )
    return next((kind for matched, kind in rules if matched), None)


def _resolved_axes(fixture: FailureFixture, kind: DivergenceClass) -> tuple[TomographyAxis, ...]:
    evidence = _stage7_evidence(fixture)
    resolved: list[TomographyAxis] = []
    if evidence.get("tool_available") is True:
        resolved.append(TomographyAxis.TOOL_AVAILABILITY)
    if evidence.get("tool_selected_correct") is True:
        resolved.extend((TomographyAxis.TOOL_AVAILABILITY, TomographyAxis.TOOL_SELECTION))
    if evidence.get("tool_arguments_correct") is True:
        resolved.extend((TomographyAxis.TOOL_AVAILABILITY, TomographyAxis.TOOL_SELECTION, TomographyAxis.TOOL_ARGUMENTS))
    if evidence.get("tool_result_available") is True:
        resolved.extend((
            TomographyAxis.TOOL_AVAILABILITY,
            TomographyAxis.TOOL_SELECTION,
            TomographyAxis.TOOL_ARGUMENTS,
            TomographyAxis.TOOL_EXECUTION_RESULT,
        ))
    if kind is DivergenceClass.VERIFIER_FEEDBACK and evidence.get("verifier_would_detect") is True:
        resolved.append(TomographyAxis.VERIFIER_VISIBILITY)
    if kind is DivergenceClass.SKILL_DEFICIT and isinstance(evidence.get("skill_trigger"), str):
        resolved.append(TomographyAxis.SKILL_TRIGGER)
    return tuple(dict.fromkeys(resolved))


def _eligibility_row(fixture: FailureFixture) -> dict[str, Any] | None:
    kind = _explicit_divergence(fixture)
    if kind is None:
        return None
    result = classify_tomography_eligibility(
        failure_snapshot_id=fixture.failure_snapshot_id,
        partition=fixture.partition,
        divergence=kind,
        decision_ids=_DECISIONS[kind],
        reconstructable_state=bool(fixture.model_visible_asset_sha256 and fixture.state_hash),
        historical_contrast=fixture.partition is Partition.HISTORICAL,
    )
    reason = {
        TomographyEligibilityStatus.ELIGIBLE: "failure has a reconstructable Stage-7 ownership question",
        TomographyEligibilityStatus.PROTECTED_PARTITION: "protected partition cannot enter development tomography",
        TomographyEligibilityStatus.INSUFFICIENT_REPLAY_STATE: "failure lacks reconstructable replay state",
        TomographyEligibilityStatus.ANSWERED_BY_EXISTING_EVIDENCE: "canonical evidence already resolves the ownership question",
        TomographyEligibilityStatus.NO_DECISION_CHANGING_PROBE: "no Stage-7 decision can be changed by another probe",
        TomographyEligibilityStatus.REQUIRES_PRIOR_LOCALIZATION: "failure requires earlier causal localization before tomography",
    }[result.status]
    return {
        "failure_snapshot_id": fixture.failure_snapshot_id,
        "divergence": kind.value,
        "eligibility": result.status.value,
        "decision_ids": list(result.active_decision_ids),
        "reason": reason,
    }


def _scan(store: ReplayStore) -> dict[str, Any]:
    rows = [
        row
        for fixture in select_failures(store, ReplaySelector())
        if (row := _eligibility_row(fixture)) is not None
    ]
    return {"status": "TOMOGRAPHY_ELIGIBILITY_SCAN", "rows": rows, "MODEL_CALLS": 0}


def _study_payload(study: TomographyStudy) -> dict[str, Any]:
    payload = study.to_record()
    payload.pop("record_type", None)
    return payload


def _probe_payload(probe: TomographyProbeSpec) -> dict[str, Any]:
    payload = probe.to_record()
    payload.pop("record_type", None)
    return payload


def _assessment_payload(value: TomographyAssessment) -> dict[str, Any]:
    payload = value.to_record()
    payload.pop("record_type", None)
    return payload


def _stored_plan(tomography: TomographyEvidenceStore, study_id: str) -> dict[str, Any]:
    studies = tuple(item for item in tomography.studies() if item.study_id == study_id)
    if len(studies) != 1:
        raise ValueError("tomography study must resolve to exactly one stored study")
    study = studies[0]
    probes = tuple(item for item in tomography.probes() if item.study_id == study_id)
    if tuple(item.probe_id for item in probes) != study.probe_ids:
        raise ValueError("stored tomography probe order does not match study contract")
    return {"study": _study_payload(study), "probes": [_probe_payload(item) for item in probes]}


def _append_plan_once(tomography: TomographyEvidenceStore, study: TomographyStudy, probes: tuple[TomographyProbeSpec, ...]) -> None:
    existing_studies = {item.study_id: item for item in tomography.studies()}
    prior = existing_studies.get(study.study_id)
    if prior is None:
        tomography.append_study(study)
    elif prior != study:
        raise ValueError("stored tomography study ID has different scientific content")
    existing_probes = {item.probe_id: item for item in tomography.probes()}
    for probe in probes:
        prior_probe = existing_probes.get(probe.probe_id)
        if prior_probe is None:
            tomography.append_probe(probe)
        elif prior_probe != probe:
            raise ValueError("stored tomography probe ID has different scientific content")


def _auto_plan(store: ReplayStore, causal_root: Path, tomography: TomographyEvidenceStore) -> dict[str, Any]:
    causal = CausalEvidenceStore(causal_root, replay_store=store)
    autopsy = FailureAutopsy(store, causal)
    interventions = InterventionGenerator(store, causal)
    plans: list[dict[str, Any]] = []

    for fixture in select_failures(store, ReplaySelector()):
        kind = _explicit_divergence(fixture)
        if kind is None or fixture.partition in {Partition.FRESH, Partition.SEALED}:
            continue
        report = autopsy.analyze(fixture)
        if report.first_divergence.divergence_class is not kind:
            continue
        target_axis = _TARGET_AXIS.get(kind)
        if target_axis is None:
            # A model-internal boundary is a valid zero-call stop until a real,
            # separately registered escalation reference exists.
            result = plan_eligible_tomography(
                failure_snapshot_id=fixture.failure_snapshot_id,
                parent_state_hash=fixture.state_hash,
                partition=fixture.partition,
                divergence=kind,
                decision_ids=_DECISIONS[kind],
                baseline_evidence_refs=tuple(fixture.source_evidence_refs or report.evidence_refs),
                intervention_ids={},
                changed_dimensions={},
                resolved_axes=_resolved_axes(fixture, kind),
                external_supports_exhausted=_stage7_evidence(fixture).get("external_supports_exhausted") is True,
                historical_contrast=fixture.partition is Partition.HISTORICAL,
            )
        else:
            hypothesis = report.hypotheses[0]
            generated = interventions.generate(fixture, hypothesis)
            target = next((item for item in generated if item.projected_physical_calls > 0), generated[0])
            result = plan_eligible_tomography(
                failure_snapshot_id=fixture.failure_snapshot_id,
                parent_state_hash=fixture.state_hash,
                partition=fixture.partition,
                divergence=kind,
                decision_ids=_DECISIONS[kind],
                baseline_evidence_refs=tuple(fixture.source_evidence_refs or report.evidence_refs),
                intervention_ids={target_axis: target.intervention_id},
                changed_dimensions={target_axis: tuple(target.changed_dimensions)},
                resolved_axes=_resolved_axes(fixture, kind),
                external_supports_exhausted=_stage7_evidence(fixture).get("external_supports_exhausted") is True,
                historical_contrast=fixture.partition is Partition.HISTORICAL,
            )
        if result.plan is None:
            continue
        _append_plan_once(tomography, result.plan.study, result.plan.probes)
        plans.append({
            "study": _study_payload(result.plan.study),
            "probes": [_probe_payload(item) for item in result.plan.probes],
        })

    if not plans:
        return {"status": "NO_ELIGIBLE_TOMOGRAPHY_STUDIES", "plans": [], "MODEL_CALLS": 0}
    return {"status": "TOMOGRAPHY_PLAN_READY", "plans": plans, "MODEL_CALLS": 0}


def handle_tomography_command(store: ReplayStore, args: argparse.Namespace) -> dict[str, Any]:
    """Execute a safe Stage-7 query/plan command. Never constructs live transports."""

    if args.command not in TOMOGRAPHY_COMMANDS:
        raise ValueError("unsupported tomography CLI command")
    tomography = TomographyEvidenceStore(Path(args.tomography_root))

    if args.command == "scan-tomography-eligibility":
        return _scan(store)
    if args.command == "plan-tomography":
        if getattr(args, "auto_eligible", False):
            return _auto_plan(store, Path(args.causal_root), tomography)
        payload = _stored_plan(tomography, args.study_id)
        payload["MODEL_CALLS"] = 0
        return payload
    if args.command == "show-tomography-study":
        payload = _stored_plan(tomography, args.study_id)
        payload["tomography_store_valid"] = tomography.validate().ok
        payload["MODEL_CALLS"] = 0
        return payload

    assessments = tuple(item for item in tomography.assessments() if item.study_id == args.study_id)
    if not assessments:
        raise ValueError("no tomography assessment exists for study")
    return {"assessment": _assessment_payload(assessments[-1]), "MODEL_CALLS": 0}
