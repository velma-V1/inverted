from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import random
from typing import Any, Iterable, Mapping

from .hd_next1_local_search import LOCAL_SEARCH_RULE_HASH, validate_generated_treatment
from .types import stable_hash


_SMALL_A_ROLES = (
    "CONFIRM_PROMOTED_POLICY",
    "CONFIRM_RAW_BASELINE",
    "CONFIRM_STRONGEST_CHALLENGER",
    "CONFIRM_NEGATIVE_TRANSFER_CONTROL",
)


@dataclass(frozen=True)
class ConfirmationResolutionPolicy:
    policy_id: str
    candidate_catalog_hash: str
    local_search_rule_hash: str
    ranking_rule: tuple[str, ...]
    tie_break_seed: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HDNext1Assignment:
    assignment_id: str
    partition: str
    case_id: str
    treatment_role: str
    support_selector_hash: str
    model_key: str
    pool: str
    execution_position: int
    observable_stratum_hash: str
    randomization_seed: int
    resolved_treatment_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedConfirmationAssignment(HDNext1Assignment):
    resolved_factor_vector: dict[str, str] | None = None
    development_snapshot_hash: str = ""


def default_confirmation_resolution_policy(design: Any) -> ConfirmationResolutionPolicy:
    catalog_hash = stable_hash(sorted(row["treatment_id"] for row in design.treatments))
    return ConfirmationResolutionPolicy(
        policy_id="HD-NEXT-1-CONFIRMATION-SELECTOR-v2",
        candidate_catalog_hash=catalog_hash,
        local_search_rule_hash=LOCAL_SEARCH_RULE_HASH,
        ranking_rule=(
            "verified_success",
            "hard_invariant",
            "minimum_support_complexity",
            "completion",
            "latency",
            "treatment_id",
        ),
        tie_break_seed=20260905,
    )


def freeze_protected_assignments(
    cases: Iterable[Any],
    design: Any,
    policy: ConfirmationResolutionPolicy,
    *,
    seed: int,
) -> tuple[HDNext1Assignment, ...]:
    if policy.candidate_catalog_hash != stable_hash(sorted(row["treatment_id"] for row in design.treatments)):
        raise ValueError("confirmation policy candidate catalog is stale")
    if policy.local_search_rule_hash != LOCAL_SEARCH_RULE_HASH:
        raise ValueError("confirmation policy local-search rule is stale")

    by_partition: dict[str, list[tuple[Any, str, str]]] = {
        "hd-next1-fresh": [],
        "hd-next1-sealed": [],
    }
    for case in cases:
        partition = str((case.metadata or {}).get("partition"))
        if partition not in by_partition:
            raise ValueError("protected case has invalid partition")
        by_partition[partition].append((case, "QWEN", "CONFIRM_PROMOTED_POLICY"))
        for role in _SMALL_A_ROLES:
            by_partition[partition].append((case, "SMALL_A", role))

    rng = random.Random(int(seed))
    pending: list[tuple[Any, str, str]] = []
    for partition in ("hd-next1-fresh", "hd-next1-sealed"):
        block = list(by_partition[partition])
        rng.shuffle(block)
        pending.extend(block)

    rows: list[HDNext1Assignment] = []
    for position, (case, model_key, role) in enumerate(pending):
        selector_hash = stable_hash({"policy": policy.to_dict(), "role": role})
        stratum = {
            "family_id": (case.metadata or {}).get("hd_next1_family_id"),
            "family": case.family,
            "structural_features": (case.metadata or {}).get("structural_features", {}),
        }
        core = {
            "partition": (case.metadata or {}).get("partition"),
            "case_id": case.case_id,
            "treatment_role": role,
            "support_selector_hash": selector_hash,
            "model_key": model_key,
            "pool": "confirmation",
            "execution_position": position,
            "observable_stratum_hash": stable_hash(stratum),
            "randomization_seed": int(seed),
        }
        rows.append(HDNext1Assignment(assignment_id=stable_hash(core), **core))
    return tuple(rows)


def _raw_candidate(treatments: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    def score(row: dict[str, Any]) -> tuple[int, int, str]:
        factors = row["factor_vector"]
        support = sum(factors[f"I{i}"] == "ON" for i in range(1, 11)) + sum(
            factors[f"A{i}"] == "TARGET" for i in range(1, 5)
        )
        complexity = (
            int(factors["amount"] != "MINIMUM")
            + int(factors["representation"] != "RAW_PROSE")
            + int(factors["ordering"] != "DEFAULT")
            + int(factors["timing"] != "UPFRONT")
            + int(factors["placement"] != "TASK_CONTEXT")
        )
        return (support, complexity, row["treatment_id"])
    return min(treatments, key=score)


def _negative_candidate(treatments: tuple[dict[str, Any], ...], fallback: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in treatments if row["factor_vector"]["amount"] == "OVERLOADED"]
    return sorted(rows, key=lambda row: row["treatment_id"])[0] if rows else fallback


def _resolve_spec(
    role: str,
    *,
    design_catalog: Mapping[str, dict[str, Any]],
    development_snapshot: Mapping[str, Any],
) -> tuple[str, dict[str, str]]:
    protected = development_snapshot.get("protected_treatments")
    if isinstance(protected, dict) and role in protected:
        spec = protected[role]
        if not isinstance(spec, dict):
            raise ValueError("protected treatment specification must be an object")
        treatment_id = str(spec.get("treatment_id") or "")
        vector = spec.get("factor_vector")
        if treatment_id in design_catalog:
            expected = dict(design_catalog[treatment_id]["factor_vector"])
            if vector is not None and dict(vector) != expected:
                raise ValueError("protected catalog treatment vector mismatch")
            return treatment_id, expected
        if str(development_snapshot.get("local_search_rule_hash") or "") != LOCAL_SEARCH_RULE_HASH:
            raise ValueError("development snapshot local-search rule is stale")
        if not validate_generated_treatment(spec):
            raise ValueError("generated protected treatment is outside the frozen local-search rule")
        return treatment_id, {str(key): str(value) for key, value in dict(vector).items()}

    treatments = tuple(design_catalog.values())
    winner = str(development_snapshot.get("winner_treatment_id") or "")
    challenger = str(development_snapshot.get("challenger_treatment_id") or "")
    if winner not in design_catalog:
        raise ValueError("development winner is outside frozen candidate catalog")
    winner_row = design_catalog[winner]
    challenger_row = design_catalog.get(challenger) or sorted(treatments, key=lambda row: row["treatment_id"])[-1]
    raw_row = _raw_candidate(treatments)
    negative_row = _negative_candidate(treatments, challenger_row)
    role_map = {
        "CONFIRM_PROMOTED_POLICY": winner_row,
        "CONFIRM_RAW_BASELINE": raw_row,
        "CONFIRM_STRONGEST_CHALLENGER": challenger_row,
        "CONFIRM_NEGATIVE_TRANSFER_CONTROL": negative_row,
    }
    row = role_map[role]
    return str(row["treatment_id"]), dict(row["factor_vector"])


def freeze_confirmation_resolution(
    assignments: Iterable[HDNext1Assignment],
    design: Any,
    development_snapshot: Mapping[str, Any],
) -> tuple[ResolvedConfirmationAssignment, ...]:
    if str(development_snapshot.get("evidence_tier")) != "DEVELOPMENT":
        raise ValueError("protected fresh/sealed evidence is forbidden in confirmation resolution")
    catalog = {str(row["treatment_id"]): dict(row) for row in design.treatments}
    snapshot_hash = stable_hash(dict(development_snapshot))
    rows: list[ResolvedConfirmationAssignment] = []
    for assignment in assignments:
        resolved_id, vector = _resolve_spec(
            assignment.treatment_role,
            design_catalog=catalog,
            development_snapshot=development_snapshot,
        )
        base = asdict(replace(assignment, resolved_treatment_id=resolved_id))
        rows.append(
            ResolvedConfirmationAssignment(
                **base,
                resolved_factor_vector=vector,
                development_snapshot_hash=snapshot_hash,
            )
        )
    return tuple(rows)


class ProtectedEvidenceState:
    def __init__(self, assignments: Iterable[HDNext1Assignment]) -> None:
        self.assignments = tuple(assignments)
        self.fresh_gate_passed = False
        self.opened: set[str] = set()

    def open_partition(self, partition: str) -> None:
        if partition not in {"hd-next1-fresh", "hd-next1-sealed"}:
            raise ValueError("unknown protected partition")
        if partition == "hd-next1-sealed" and not self.fresh_gate_passed:
            raise ValueError("sealed confirmation cannot open before the fresh gate passes")
        self.opened.add(partition)

    def mark_fresh_gate_passed(self) -> None:
        if "hd-next1-fresh" not in self.opened:
            raise ValueError("fresh protected partition must be opened before its gate can pass")
        self.fresh_gate_passed = True
