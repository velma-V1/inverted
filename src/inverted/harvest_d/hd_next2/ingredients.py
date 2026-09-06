"""Semantic ingredient definitions and deterministic D3 payload extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


INITIAL_IDS = (
    "OBJECTIVE", "SUBGOAL", "CANONICAL_STATE", "STATE_DELTA", "AUTHORITY", "SCOPE", "APPROVAL_STATE",
    "EVIDENCE_SUFFICIENCY", "EVIDENCE_PROVENANCE", "EVIDENCE_FRESHNESS", "EVIDENCE_CONTRADICTION",
    "UNCERTAINTY", "MISSING_INFORMATION", "RISK", "CONSEQUENCE", "REVERSIBILITY", "PRESERVATION_CONSTRAINTS",
    "INVARIANTS", "PREREQUISITES", "DEPENDENCIES", "CAUSAL_STRUCTURE", "ADMISSIBLE_ACTIONS", "FORBIDDEN_ACTIONS",
    "ACTION_CONSEQUENCES", "PRIOR_VERIFIED_STATE", "PRIOR_FAILURES", "RECOVERY_OPTIONS", "ALTERNATIVES",
    "COUNTEREXAMPLE", "POSITIVE_EXAMPLE", "NEGATIVE_EXAMPLE", "DECOMPOSITION", "PLAN", "SUCCESS_CRITERIA",
    "FAILURE_CRITERIA", "VERIFIER_EXPECTATIONS", "TOOL_CONSTRAINTS", "LIKELY_FAILURE_MODE", "EDGE_CASES",
    "HISTORY_COMPRESSED_MEMORY",
)


@dataclass(frozen=True)
class SemanticIngredient:
    """Stable semantic contract, independent of any case's concrete content."""

    ingredient_id: str
    meaning: str
    source_fields: tuple[str, ...]
    prohibited_sources: tuple[str, ...] = ("case.oracle", "case.expected_disposition")


@dataclass(frozen=True)
class IngredientPayload:
    ingredient_id: str
    dose_id: str
    payload: dict[str, object]
    semantic_atoms: frozenset[str]
    source_lineage: tuple[str, ...]


_SPECS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "OBJECTIVE": ("the requested system outcome and immediate subgoal", ("I1",), "objective"),
    "SUBGOAL": ("an explicitly stated intermediate outcome", ("I1",), "subgoal"),
    "CANONICAL_STATE": ("authoritative current case state", ("I2",), "canonical_state"),
    "STATE_DELTA": ("explicit state change or version contrast", ("I2",), "state_delta"),
    "AUTHORITY": ("authority granted for the case", ("I3",), "authority"),
    "SCOPE": ("resources within the granted authority boundary", ("I3",), "scope"),
    "APPROVAL_STATE": ("approval or lease status", ("I3",), "approval_state"),
    "EVIDENCE_SUFFICIENCY": ("whether required evidence is available", ("I4",), "evidence_sufficiency"),
    "EVIDENCE_PROVENANCE": ("visible origin labels for supplied evidence", ("I4",), "evidence_provenance"),
    "EVIDENCE_FRESHNESS": ("explicit freshness information for evidence", ("I4",), "evidence_freshness"),
    "EVIDENCE_CONTRADICTION": ("visible disagreement among evidence claims", ("I4",), "evidence_contradiction"),
    "UNCERTAINTY": ("remaining stated uncertainty", ("I10",), "uncertainty"),
    "MISSING_INFORMATION": ("information explicitly identified as missing", ("I4", "I10"), "missing_information"),
    "RISK": ("stated risk level", ("I5",), "risk"),
    "CONSEQUENCE": ("stated consequences of the contemplated action", ("I5",), "consequence"),
    "REVERSIBILITY": ("whether effects can be reversed", ("I5",), "reversibility"),
    "PRESERVATION_CONSTRAINTS": ("constraints that preserve safe system behavior", ("I6",), "preservation_constraints"),
    "INVARIANTS": ("conditions that must remain true", ("I6",), "invariants"),
    "PREREQUISITES": ("conditions required before action", ("I8",), "prerequisites"),
    "DEPENDENCIES": ("declared dependency relationships", ("I8",), "dependencies"),
    "CAUSAL_STRUCTURE": ("visible causal or ordering structure", ("I8", "I6"), "causal_structure"),
    "ADMISSIBLE_ACTIONS": ("actions explicitly available to the model", ("I7",), "admissible_actions"),
    "FORBIDDEN_ACTIONS": ("actions explicitly prohibited by visible constraints", ("I6",), "forbidden_actions"),
    "ACTION_CONSEQUENCES": ("visible action-effect constraints", ("I5", "I6"), "action_consequences"),
    "PRIOR_VERIFIED_STATE": ("previously verified case state", ("I9",), "prior_verified_state"),
    "PRIOR_FAILURES": ("visible prior failure information", ("I9", "I2"), "prior_failures"),
    "RECOVERY_OPTIONS": ("declared recovery state and options", ("I9",), "recovery_options"),
    "ALTERNATIVES": ("explicitly visible action alternatives", ("I7",), "alternatives"),
    "COUNTEREXAMPLE": ("a visible case-specific counterexample", (), "counterexample"),
    "POSITIVE_EXAMPLE": ("a visible case-specific positive example", (), "positive_example"),
    "NEGATIVE_EXAMPLE": ("a visible case-specific negative example", (), "negative_example"),
    "DECOMPOSITION": ("an explicit visible task decomposition", (), "decomposition"),
    "PLAN": ("an explicit visible execution plan", (), "plan"),
    "SUCCESS_CRITERIA": ("visible success criteria", ("I6",), "success_criteria"),
    "FAILURE_CRITERIA": ("visible failure criteria", ("I6", "I9"), "failure_criteria"),
    "VERIFIER_EXPECTATIONS": ("visible independent-verifier expectations", ("I4", "I6"), "verifier_expectations"),
    "TOOL_CONSTRAINTS": ("visible constraints on tool or action use", ("I3", "I6"), "tool_constraints"),
    "LIKELY_FAILURE_MODE": ("visible likely failure mode", ("I9", "I10"), "likely_failure_mode"),
    "EDGE_CASES": ("explicitly supplied edge cases", (), "edge_cases"),
    "HISTORY_COMPRESSED_MEMORY": ("visible compressed historical state", (), "history_compressed_memory"),
}


def initial_ingredient_registry() -> dict[str, SemanticIngredient]:
    """Return the fixed initial semantic vocabulary (not the historical I1-I10 labels)."""
    return {
        ingredient_id: SemanticIngredient(ingredient_id, meaning, source_fields)
        for ingredient_id, (meaning, source_fields, _) in _SPECS.items()
    }


def _atoms_for(value: Any, *, prefix: str) -> list[tuple[str, Any]]:
    if isinstance(value, Mapping):
        return [(f"{prefix}.{key}", item) for key, item in value.items()]
    if isinstance(value, (list, tuple)):
        return [(f"{prefix}[{index}]", item) for index, item in enumerate(value)]
    return [(prefix, value)]


def _visible_atoms(source: Mapping[str, Any], field_ids: tuple[str, ...]) -> list[tuple[str, Any]]:
    atoms: list[tuple[str, Any]] = []
    for field_id in field_ids:
        value = source.get(field_id)
        if value is not None:
            atoms.extend(_atoms_for(value, prefix=field_id))
    return atoms


def _select_atoms(ingredient_id: str, source: Mapping[str, Any], field_ids: tuple[str, ...]) -> list[tuple[str, Any]]:
    """Select only source content that actually satisfies the semantic contract."""
    if ingredient_id in {
        "COUNTEREXAMPLE", "POSITIVE_EXAMPLE", "NEGATIVE_EXAMPLE", "DECOMPOSITION", "PLAN",
        "TOOL_CONSTRAINTS", "EDGE_CASES", "HISTORY_COMPRESSED_MEMORY",
    }:
        return []
    if ingredient_id == "STATE_DELTA":
        state = source.get("I2")
        if not isinstance(state, Mapping) or not {"canonical_version", "stale_candidate_version"} <= set(state):
            return []
        return _atoms_for({key: state[key] for key in ("canonical_version", "stale_candidate_version")}, prefix="I2")
    if ingredient_id == "EVIDENCE_SUFFICIENCY":
        evidence = source.get("I4")
        if not isinstance(evidence, Mapping) or "required" not in evidence:
            return []
        return _atoms_for({key: evidence[key] for key in ("required", "available", "missing") if key in evidence}, prefix="I4")
    if ingredient_id == "EVIDENCE_CONTRADICTION":
        evidence = source.get("I4")
        if not isinstance(evidence, Mapping):
            return []
        pairs = (("deterministic_verifier", "model_claim"), ("canonical_source", "untrusted_note"))
        for left, right in pairs:
            if left in evidence and right in evidence:
                return _atoms_for({left: evidence[left], right: evidence[right]}, prefix="I4")
        return []
    if ingredient_id == "RECOVERY_OPTIONS":
        recovery = source.get("I9")
        if not isinstance(recovery, Mapping) or recovery.get("recovery_state") in {None, "NONE"}:
            return []
    if ingredient_id == "VERIFIER_EXPECTATIONS":
        evidence = source.get("I4")
        if not isinstance(evidence, Mapping) or "deterministic_verifier" not in evidence:
            return []
        return _atoms_for({key: evidence[key] for key in ("deterministic_verifier", "model_claim", "missing") if key in evidence}, prefix="I4")
    if ingredient_id == "LIKELY_FAILURE_MODE":
        recovery = source.get("I9")
        if not isinstance(recovery, Mapping) or not any("FAIL" in str(value) for value in recovery.values()):
            return []
    supported_whole_field_contracts = {
        "OBJECTIVE", "CANONICAL_STATE", "AUTHORITY", "CONSEQUENCE", "PRESERVATION_CONSTRAINTS",
        "INVARIANTS", "DEPENDENCIES", "CAUSAL_STRUCTURE", "ADMISSIBLE_ACTIONS", "ALTERNATIVES",
        "ACTION_CONSEQUENCES", "PRIOR_VERIFIED_STATE", "UNCERTAINTY",
    }
    if ingredient_id not in supported_whole_field_contracts:
        return []
    return _visible_atoms(source, field_ids)


def extract_ingredient_payload(case: object, ingredient_id: str, dose_id: str) -> IngredientPayload | None:
    """Extract an auditable semantic dose using only model-visible D3 metadata.

    A dose is unsupported when the case provides fewer than two independent
    semantic atoms: there is then no truthful CORE/FULL distinction to make.
    """
    if ingredient_id not in _SPECS:
        raise ValueError(f"unknown semantic ingredient: {ingredient_id}")
    if dose_id not in {"CORE", "FULL"}:
        raise ValueError(f"unknown dose: {dose_id}")

    metadata = getattr(case, "metadata", None)
    if not isinstance(metadata, Mapping):
        return None
    source = metadata.get("d3_information")
    if not isinstance(source, Mapping):
        return None

    _, field_ids, transform = _SPECS[ingredient_id]
    atoms = _select_atoms(ingredient_id, source, field_ids)
    if len(atoms) < 2:
        return None
    selected = atoms[:1] if dose_id == "CORE" else atoms
    payload = {transform: {atom: value for atom, value in selected}}
    lineage = tuple(f"metadata:d3_information:{field_id}" for field_id in field_ids) + (
        f"transform:select:{transform}",
        f"dose:{dose_id}",
    )
    return IngredientPayload(
        ingredient_id=ingredient_id,
        dose_id=dose_id,
        payload=payload,
        semantic_atoms=frozenset(atom for atom, _ in selected),
        source_lineage=lineage,
    )
