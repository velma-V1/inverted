from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _information(case: Any) -> dict[str, Any]:
    return dict((case.metadata or {}).get("d3_information", {}))


def _nested_depth(value: Any) -> int:
    if isinstance(value, dict):
        if not value:
            return 1
        return 1 + max(_nested_depth(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        if not value:
            return 1
        return 1 + max(_nested_depth(item) for item in value)
    return 0


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    return (str(value),)


@dataclass(frozen=True)
class PreStateDescriptor:
    pre_state_id: str
    case_id: str
    family: str
    partition: str
    objective: str
    canonical_state: dict[str, Any]
    state_version: str | int | None
    available_evidence: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    authority_scope: tuple[str, ...]
    irreversible: bool
    risk: str
    invariant_sensitive: bool
    dependency_depth: int
    novelty: str
    boundary_exceeded: bool
    previous_verified_state: str
    recovery_state: str
    action_space_size: int

    def to_dict(self) -> dict[str, object]:
        return {
            "pre_state_id": self.pre_state_id,
            "case_id": self.case_id,
            "family": self.family,
            "partition": self.partition,
            "objective": self.objective,
            "canonical_state": self.canonical_state,
            "state_version": self.state_version,
            "available_evidence": list(self.available_evidence),
            "missing_evidence": list(self.missing_evidence),
            "authority_scope": list(self.authority_scope),
            "irreversible": self.irreversible,
            "risk": self.risk,
            "invariant_sensitive": self.invariant_sensitive,
            "dependency_depth": self.dependency_depth,
            "novelty": self.novelty,
            "boundary_exceeded": self.boundary_exceeded,
            "previous_verified_state": self.previous_verified_state,
            "recovery_state": self.recovery_state,
            "action_space_size": self.action_space_size,
        }


@dataclass(frozen=True)
class ActionFrontierDescriptor:
    frontier_id: str
    case_id: str
    candidate_actions: tuple[str, ...]
    admissible_actions: tuple[str, ...]
    removed_actions: tuple[str, ...]
    removal_reasons: tuple[str, ...]
    candidate_count: int
    action_count: int
    irreversible_action_count: int
    authority_sensitive_action_count: int
    evidence_gated_action_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "frontier_id": self.frontier_id,
            "case_id": self.case_id,
            "candidate_actions": list(self.candidate_actions),
            "admissible_actions": list(self.admissible_actions),
            "removed_actions": list(self.removed_actions),
            "removal_reasons": list(self.removal_reasons),
            "candidate_count": self.candidate_count,
            "action_count": self.action_count,
            "irreversible_action_count": self.irreversible_action_count,
            "authority_sensitive_action_count": self.authority_sensitive_action_count,
            "evidence_gated_action_count": self.evidence_gated_action_count,
        }


def derive_pre_state(case: Any) -> PreStateDescriptor:
    info = _information(case)
    objective = dict(info.get("I1", {}))
    state = dict(info.get("I2", {}))
    authority = dict(info.get("I3", {}))
    evidence = dict(info.get("I4", {}))
    consequence = dict(info.get("I5", {}))
    invariants = dict(info.get("I6", {}))
    actions = dict(info.get("I7", {}))
    dependencies = info.get("I8", {})
    recovery = dict(info.get("I9", {}))
    uncertainty = dict(info.get("I10", {}))

    available = _as_tuple(evidence.get("available"))
    if not available:
        available = tuple(
            sorted(
                str(key)
                for key, value in evidence.items()
                if key not in {"missing", "required"} and value not in {None, False, ""}
            )
        )
    missing = _as_tuple(evidence.get("missing"))
    scope = _as_tuple(authority.get("allowed_resources", authority.get("scope", ())))
    admissible = _as_tuple(actions.get("admissible_actions"))
    state_version = state.get("canonical_version", state.get("version"))
    novelty_raw = uncertainty.get("novelty", uncertainty.get("known_policy_coverage", ""))
    novelty = str(novelty_raw)
    boundary_exceeded = bool(
        uncertainty.get("boundary_exceeded", False)
        or uncertainty.get("known_policy_coverage") is False
        or uncertainty.get("novelty") == "HIGH"
    )

    payload = {
        "case_id": str(case.case_id),
        "family": str(case.family),
        "partition": str((case.metadata or {}).get("partition", "")),
        "objective": str(objective.get("objective", "")),
        "canonical_state": state,
        "state_version": state_version,
        "available_evidence": available,
        "missing_evidence": missing,
        "authority_scope": scope,
        "irreversible": consequence.get("reversible") is False,
        "risk": str(consequence.get("risk", "UNKNOWN")),
        "invariant_sensitive": bool(invariants),
        "dependency_depth": _nested_depth(dependencies),
        "novelty": novelty,
        "boundary_exceeded": boundary_exceeded,
        "previous_verified_state": str(recovery.get("previous_verified", "")),
        "recovery_state": str(recovery.get("recovery_state", "")),
        "action_space_size": len(admissible),
    }
    return PreStateDescriptor(pre_state_id=_stable_hash(payload), **payload)


def derive_action_frontier(case: Any) -> ActionFrontierDescriptor:
    info = _information(case)
    authority = dict(info.get("I3", {}))
    evidence = dict(info.get("I4", {}))
    consequence = dict(info.get("I5", {}))
    actions = dict(info.get("I7", {}))

    admissible = _as_tuple(actions.get("admissible_actions"))
    candidates = _as_tuple(actions.get("candidate_actions", admissible))
    admitted = set(admissible)
    removed = tuple(action for action in candidates if action not in admitted)
    removal_reasons = _as_tuple(actions.get("removal_reasons"))
    irreversible = consequence.get("reversible") is False
    authority_sensitive = bool(authority.get("requested_resource") or authority.get("allowed_resources"))
    evidence_gated = bool(evidence.get("required") or evidence.get("missing"))

    payload = {
        "case_id": str(case.case_id),
        "candidate_actions": candidates,
        "admissible_actions": admissible,
        "removed_actions": removed,
        "removal_reasons": removal_reasons,
        "candidate_count": len(candidates),
        "action_count": len(admissible),
        "irreversible_action_count": len(admissible) if irreversible else 0,
        "authority_sensitive_action_count": len(admissible) if authority_sensitive else 0,
        "evidence_gated_action_count": len(admissible) if evidence_gated else 0,
    }
    return ActionFrontierDescriptor(frontier_id=_stable_hash(payload), **payload)
