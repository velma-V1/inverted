from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import Disposition, stable_hash


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
    """Compile system-owned semantics into an admissible disposition/recovery."""

    def compile(self, semantics: SystemSemantics) -> CompilerResult:
        inputs_used = (
            "hard_invariant_ok",
            "external_effect_status",
            "missing_required_evidence",
        )
        if not semantics.hard_invariant_ok:
            return CompilerResult(Disposition.SAFE_STOP, "SAFE_STOP", inputs_used)
        if semantics.external_effect_status == "UNKNOWN":
            return CompilerResult(Disposition.ESCALATE, "RECONCILE", inputs_used)
        if semantics.missing_required_evidence:
            return CompilerResult(Disposition.ACQUIRE_EVIDENCE, "ACQUIRE_EVIDENCE", inputs_used)
        return CompilerResult(Disposition.EXECUTE, None, inputs_used)


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


def _target_assistance(mechanism_id: str, context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    output = _copy_context(context)

    if mechanism_id == "A1":
        output["effective_state"] = _copy_context(dict(context.get("canonical_state", {})))
        output["state_anchor"] = "CANONICAL_STATE_VERSION_ENFORCED"
        return output, "canonical state/version anchoring applied"

    if mechanism_id == "A2":
        candidates = list(context.get("candidate_actions", []))
        admissible = set(context.get("admissible_actions", []))
        output["candidate_actions"] = [action for action in candidates if action in admissible]
        output["action_restriction"] = "ADMISSIBLE_ONLY"
        return output, "candidate action set restricted to system-admissible actions"

    if mechanism_id == "A3":
        missing = list(context.get("missing_evidence", []))
        output["evidence_gate"] = {
            "required": list(context.get("required_evidence", [])),
            "available": list(context.get("available_evidence", [])),
            "missing": missing,
            "sufficient": not missing,
        }
        if missing:
            output["compiled_disposition"] = Disposition.ACQUIRE_EVIDENCE.value
        return output, "required/missing evidence made explicit"

    if mechanism_id == "A4":
        output["dependency_scaffold"] = _copy_context(dict(context.get("dependencies", {})))
        output["dependency_order_enforced"] = True
        return output, "dependency/decomposition scaffold applied"

    if mechanism_id == "A5":
        met = bool(context.get("postcondition_met", False))
        output["verifier_gate"] = "PASS" if met else "FAIL"
        output["verification_required_before_success"] = True
        return output, "deterministic postcondition verifier applied"

    if mechanism_id == "A6":
        compiled = DispositionCompiler().compile(
            SystemSemantics(
                missing_required_evidence=bool(context.get("missing_required_evidence", False)),
                external_effect_status=str(context.get("external_effect_status", "NOT_COMMITTED")),
                hard_invariant_ok=bool(context.get("hard_invariant_ok", True)),
            )
        )
        output["compiled_disposition"] = compiled.disposition.value
        output["compiled_recovery"] = compiled.recovery
        output["compiler_inputs_used"] = list(compiled.inputs_used)
        return output, "system-semantic disposition compiler applied"

    if mechanism_id == "A7":
        allowed = bool(context.get("authority_allows", False))
        output["authority_gate"] = "ALLOW" if allowed else "DENY"
        output["least_privilege_enforced"] = True
        if not allowed:
            output["candidate_actions"] = []
            output["compiled_disposition"] = Disposition.ESCALATE.value
        return output, "least-privilege authority guard applied"

    if mechanism_id == "A8":
        irreversible = bool(context.get("irreversible", False))
        risk = str(context.get("risk", "UNKNOWN")).upper()
        missing = bool(context.get("missing_evidence", []))
        unknown_effect = str(context.get("external_effect_status", "NOT_COMMITTED")) == "UNKNOWN"
        blocked = irreversible and (risk in {"HIGH", "UNKNOWN"}) and (missing or unknown_effect)
        output["consequence_guard"] = "BLOCK" if blocked else "ALLOW"
        output["reversibility_checked"] = True
        if blocked:
            output["compiled_disposition"] = Disposition.ESCALATE.value
        return output, "consequence/reversibility guard applied"

    if mechanism_id == "A9":
        effect = str(context.get("external_effect_status", "NOT_COMMITTED"))
        missing = bool(context.get("missing_evidence", []))
        signature = str(context.get("failure_signature", ""))
        if effect == "UNKNOWN":
            recovery = "RECONCILE"
        elif missing:
            recovery = "ACQUIRE_EVIDENCE"
        elif signature:
            recovery = "REPLAN"
        else:
            recovery = "ALTERNATE_ACTION"
        output["recovery_supervisor"] = recovery
        output["retry_permitted"] = effect != "UNKNOWN"
        return output, "recovery supervisor selected a bounded recovery path"

    if mechanism_id == "A10":
        canonical = dict(context.get("canonical_state", {}))
        claimed = dict(context.get("model_state_claim", {}))
        stale = bool(canonical and claimed and canonical.get("version") != claimed.get("version"))
        signature = str(context.get("failure_signature", "")) or ("STALE_STATE" if stale else "NONE")
        output["failure_signature_detected"] = signature
        output["failure_guard_triggered"] = signature != "NONE" or not bool(context.get("hard_invariant_ok", True))
        return output, "failure signature/guard evaluated"

    if mechanism_id == "A11":
        novelty = str(context.get("novelty", "")).upper()
        boundary = bool(context.get("boundary_exceeded", False))
        missing = bool(context.get("missing_evidence", []))
        if novelty in {"HIGH", "UNKNOWN"}:
            route = "NOVELTY_INVESTIGATION"
        elif missing:
            route = "ACQUIRE_EVIDENCE"
        elif boundary:
            route = "QWEN_STANDARD"
        else:
            route = "ROUTINE_LOCAL"
        output["route_decision"] = route
        output["routing_reason"] = "deterministic decision-time features"
        return output, "routing/escalation support applied"

    raise ValueError(f"unknown D3 assistance mechanism: {mechanism_id}")


def evaluate_assistance(mechanism_id: str, mode: str, context: dict[str, Any]) -> AssistanceEvaluation:
    if mechanism_id not in ASSISTANCE_MECHANISMS:
        raise ValueError(f"unknown D3 assistance mechanism: {mechanism_id}")
    if mode not in {"TARGET", "OFF", "SHAM"}:
        raise ValueError(f"unknown D3 assistance mode: {mode}")

    if mode == "TARGET":
        output, reason = _target_assistance(mechanism_id, context)
    elif mode == "OFF":
        output = _copy_context(context)
        reason = "mechanism disabled"
    else:
        output = _copy_context(context)
        reason = "matched inactive sham; semantic state unchanged"

    return AssistanceEvaluation(mechanism_id, mode, output, reason)


def replay_assistance_suite(
    *,
    source_physical_model_call_id: str,
    context: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Replay all A1-A11 OFF/TARGET/SHAM conditions without model inference."""

    if not source_physical_model_call_id:
        raise ValueError("source physical model call id is required")
    source_hash = stable_hash(context)
    rows: list[dict[str, Any]] = []
    for mechanism_id in ASSISTANCE_MECHANISMS:
        for mode in ("OFF", "TARGET", "SHAM"):
            evaluation = evaluate_assistance(mechanism_id, mode, context)
            rows.append(
                {
                    "source_physical_model_call_id": source_physical_model_call_id,
                    "mechanism_id": mechanism_id,
                    "mode": mode,
                    "physical_model_calls_used": 0,
                    "source_context_hash": source_hash,
                    "output_context_hash": stable_hash(evaluation.output),
                    "changed_semantic_state": evaluation.output != context,
                    "reason": evaluation.reason,
                    "output": evaluation.output,
                }
            )
    return tuple(rows)


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

    return AssistanceOpportunity(mechanism_id, eligible, triggered, status, reason)
