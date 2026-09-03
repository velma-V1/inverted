from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import Disposition


ASSISTANCE_MECHANISMS: tuple[str, ...] = tuple(f"A{i}" for i in range(1, 12))


@dataclass(frozen=True)
class SystemSemantics:
    missing_required_evidence: bool = False
    external_effect_status: str = "NOT_COMMITTED"
    hard_invariant_ok: bool = True


@dataclass(frozen=True)
class CompilerResult:
    disposition: Disposition
    recovery: str | None
    inputs_used: tuple[str, ...]


class DispositionCompiler:
    """Compile system-owned semantics into an admissible disposition/recovery.

    The compiler intentionally consumes semantic state only. Case identifiers and
    oracle labels are not inputs, which keeps the mechanism replayable without
    memorizing development cases.
    """

    def compile(self, semantics: SystemSemantics) -> CompilerResult:
        inputs_used = (
            "hard_invariant_ok",
            "external_effect_status",
            "missing_required_evidence",
        )

        if not semantics.hard_invariant_ok:
            return CompilerResult(
                disposition=Disposition.SAFE_STOP,
                recovery="SAFE_STOP",
                inputs_used=inputs_used,
            )

        if semantics.external_effect_status == "UNKNOWN":
            return CompilerResult(
                disposition=Disposition.ESCALATE,
                recovery="RECONCILE",
                inputs_used=inputs_used,
            )

        if semantics.missing_required_evidence:
            return CompilerResult(
                disposition=Disposition.ACQUIRE_EVIDENCE,
                recovery="ACQUIRE_EVIDENCE",
                inputs_used=inputs_used,
            )

        return CompilerResult(
            disposition=Disposition.EXECUTE,
            recovery=None,
            inputs_used=inputs_used,
        )


@dataclass(frozen=True)
class AssistanceEvaluation:
    mechanism_id: str
    mode: str
    output: dict[str, Any]
    reason: str = ""


@dataclass(frozen=True)
class AssistanceOpportunity:
    mechanism_id: str
    eligible: bool
    triggered: bool
    status: str
    reason: str


def _copy_context(context: dict[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, value in context.items():
        if isinstance(value, list):
            copied[key] = list(value)
        elif isinstance(value, dict):
            copied[key] = dict(value)
        else:
            copied[key] = value
    return copied


def evaluate_assistance(mechanism_id: str, mode: str, context: dict[str, Any]) -> AssistanceEvaluation:
    if mechanism_id not in ASSISTANCE_MECHANISMS:
        raise ValueError(f"unknown D3 assistance mechanism: {mechanism_id}")
    if mode not in {"TARGET", "OFF", "SHAM"}:
        raise ValueError(f"unknown D3 assistance mode: {mode}")

    output = _copy_context(context)

    # A2 = admissible-action restriction. TARGET enforces the system-owned
    # admissible set; OFF and SHAM preserve the candidate set so matched
    # comparisons can distinguish the active restriction from mere presence.
    if mechanism_id == "A2" and mode == "TARGET":
        candidates = list(context.get("candidate_actions", []))
        admissible = set(context.get("admissible_actions", []))
        output["candidate_actions"] = [action for action in candidates if action in admissible]

    reason = {
        "TARGET": "active deterministic assistance",
        "OFF": "mechanism disabled",
        "SHAM": "matched inactive sham",
    }[mode]
    return AssistanceEvaluation(
        mechanism_id=mechanism_id,
        mode=mode,
        output=output,
        reason=reason,
    )


def assistance_opportunity(
    mechanism_id: str,
    *,
    eligible: bool,
    triggered: bool,
    reason: str,
) -> AssistanceOpportunity:
    if mechanism_id not in ASSISTANCE_MECHANISMS:
        raise ValueError(f"unknown D3 assistance mechanism: {mechanism_id}")
    if triggered and not eligible:
        raise ValueError("an ineligible assistance opportunity cannot be triggered")

    if triggered:
        status = "TRIGGERED"
    elif eligible:
        status = "ELIGIBLE_NOT_TRIGGERED"
    else:
        status = "INELIGIBLE"

    return AssistanceOpportunity(
        mechanism_id=mechanism_id,
        eligible=eligible,
        triggered=triggered,
        status=status,
        reason=reason,
    )
