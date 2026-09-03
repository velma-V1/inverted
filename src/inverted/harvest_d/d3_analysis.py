from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .d3_recovery import RecoveryTrace, failure_migrated
from .types import SequentialDecision


@dataclass(frozen=True)
class ScoreSummary:
    answer_correct: bool
    disposition_correct: bool
    semantic_correct: bool
    hard_invariant_ok: bool = True


@dataclass(frozen=True)
class MinimumInformationPacket:
    required_fields: tuple[str, ...]
    removed_fields: tuple[str, ...]


@dataclass(frozen=True)
class SupportPoint:
    name: str
    involvement: float
    decision: SequentialDecision
    safe: bool = True


@dataclass(frozen=True)
class MinimumRequiredScaffolding:
    name: str
    involvement: float
    decision: SequentialDecision


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def classify_failure(score: ScoreSummary | Mapping[str, Any]) -> str:
    if not bool(_value(score, "hard_invariant_ok", True)):
        return "HARD_INVARIANT_VIOLATION"
    answer = bool(_value(score, "answer_correct", False))
    disposition = bool(_value(score, "disposition_correct", False))
    semantic = bool(_value(score, "semantic_correct", answer and disposition))
    if answer and disposition and semantic:
        return "CORRECT"
    if answer and not disposition:
        return "ANSWER_RIGHT_DISPOSITION_WRONG"
    if not answer and disposition:
        return "ANSWER_WRONG_DISPOSITION_RIGHT"
    if not semantic:
        return "SEMANTIC_WRONG"
    return "ANSWER_AND_DISPOSITION_WRONG"


def build_recovery_maps(traces: Iterable[RecoveryTrace]) -> dict[str, int]:
    result = {
        "total": 0,
        "recovered_without_migration": 0,
        "migrated": 0,
        "not_recovered": 0,
    }
    for trace in traces:
        result["total"] += 1
        if failure_migrated(trace):
            result["migrated"] += 1
        elif trace.local_recovered and trace.global_invariant_ok:
            result["recovered_without_migration"] += 1
        else:
            result["not_recovered"] += 1
    return result


def _packet_fields(packet: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(packet, str):
        return tuple(part.strip() for part in packet.split("+") if part.strip())
    return tuple(str(x) for x in packet)


def _decision(value: Any) -> SequentialDecision:
    if isinstance(value, SequentialDecision):
        return value
    if hasattr(value, "decision"):
        return _decision(value.decision)
    return SequentialDecision(str(value))


def find_msip(
    packet: str | Iterable[str],
    *,
    ablations: Mapping[str, Any],
) -> MinimumInformationPacket:
    fields = _packet_fields(packet)
    removable = {
        field
        for field in fields
        if field in ablations
        and _decision(ablations[field]) in {SequentialDecision.NONINFERIOR, SequentialDecision.SUPERIOR}
    }
    return MinimumInformationPacket(
        required_fields=tuple(field for field in fields if field not in removable),
        removed_fields=tuple(field for field in fields if field in removable),
    )


def find_mrs(points: Iterable[SupportPoint | Mapping[str, Any]]) -> MinimumRequiredScaffolding:
    eligible: list[SupportPoint] = []
    for point in points:
        normalized = point if isinstance(point, SupportPoint) else SupportPoint(
            name=str(point["name"]),
            involvement=float(point["involvement"]),
            decision=_decision(point["decision"]),
            safe=bool(point.get("safe", True)),
        )
        if normalized.safe and normalized.decision in {
            SequentialDecision.NONINFERIOR,
            SequentialDecision.SUPERIOR,
        }:
            eligible.append(normalized)
    if not eligible:
        raise ValueError("no safe noninferior scaffolding point")
    winner = min(eligible, key=lambda p: (p.involvement, p.name))
    return MinimumRequiredScaffolding(winner.name, winner.involvement, winner.decision)


def build_coverage_matrix(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    matrix: dict[str, str] = {}
    for row in rows:
        cell = str(row["cell"])
        status = str(row["status"])
        if cell in matrix and matrix[cell] != status:
            # Preserve the more cautionary state when a cell has conflicting coverage records.
            rank = {
                "IMPORTANT_UNRESOLVED": 5,
                "BUDGET_DEFERRED": 4,
                "KILLED_BY_EVIDENCE": 3,
                "INAPPLICABLE": 2,
                "LOW_VALUE": 1,
                "TESTED": 0,
            }
            if rank.get(status, 4) > rank.get(matrix[cell], 4):
                matrix[cell] = status
        else:
            matrix[cell] = status
    return matrix


def build_claim_graph(claims: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    claim_rows: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    for claim in claims:
        row = dict(claim)
        claim_id = str(row["claim_id"])
        claim_rows.append(row)
        for call_id in row.get("supporting_call_ids", []) or []:
            edges.append({"claim_id": claim_id, "evidence_id": str(call_id), "kind": "SUPPORTS"})
        for call_id in row.get("contradictory_call_ids", []) or []:
            edges.append({"claim_id": claim_id, "evidence_id": str(call_id), "kind": "CONTRADICTS"})
    return {"claims": claim_rows, "edges": edges}


def derive_structural_features(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "dependency_depth": int(case.get("dependency_depth", 0) or 0),
        "action_space_size": int(case.get("action_space_size", 0) or 0),
        "evidence_complete": bool(case.get("evidence_complete", False)),
        "ambiguity": float(case.get("ambiguity", 0.0) or 0.0),
        "recovery_choice_count": int(case.get("recovery_choice_count", 0) or 0),
        "risk": str(case.get("risk", "UNKNOWN")),
        "reversibility": str(case.get("reversibility", "UNKNOWN")),
    }


def derive_behavior_features(call: Mapping[str, Any]) -> dict[str, Any]:
    parsed = call.get("parsed_response")
    if not isinstance(parsed, Mapping):
        parsed = {}
    return {
        "physical_model_call_id": call.get("physical_model_call_id"),
        "candidate_action_count": len(parsed.get("candidate_actions", []) or []),
        "rejected_alternative_count": len(parsed.get("rejected_alternatives", []) or []),
        "reported_uncertainty": parsed.get("uncertainty"),
        "requested_evidence": parsed.get("requested_evidence"),
        "recovery_choice": parsed.get("recovery_choice"),
    }


def _group_mean(rows: Iterable[Mapping[str, Any]], group_key: str, value_key: str) -> dict[str, float]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(group_key, "UNKNOWN"))
        value = float(row.get(value_key, 0.0) or 0.0)
        sums[key] = sums.get(key, 0.0) + value
        counts[key] = counts.get(key, 0) + 1
    return {key: sums[key] / counts[key] for key in sums}


def build_information_value_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    return _group_mean(rows, "information_condition", "outcome_delta")


def build_assistance_value_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    return _group_mean(rows, "assistance_condition", "outcome_delta")


def build_model_substitution_frontier(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized = [dict(row) for row in rows]
    return sorted(
        normalized,
        key=lambda row: (
            float(row.get("model_size_b", 0.0) or 0.0),
            float(row.get("system_involvement", 0.0) or 0.0),
            -float(row.get("verified_correctness", 0.0) or 0.0),
        ),
    )
