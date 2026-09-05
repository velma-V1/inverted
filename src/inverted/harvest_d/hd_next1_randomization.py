from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import random
from typing import Any, Iterable, Mapping

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
    development_snapshot_hash: str = ""


def default_confirmation_resolution_policy(design: Any) -> ConfirmationResolutionPolicy:
    catalog_hash = stable_hash(sorted(row["treatment_id"] for row in design.treatments))
    return ConfirmationResolutionPolicy(
        policy_id="HD-NEXT-1-CONFIRMATION-SELECTOR-v1",
        candidate_catalog_hash=catalog_hash,
        ranking_rule=("verified_success", "hard_invariant", "completion", "latency", "treatment_id"),
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
    pending: list[tuple[Any, str, str]] = []
    for case in cases:
        pending.append((case, "QWEN", "CONFIRM_PROMOTED_POLICY"))
        for role in _SMALL_A_ROLES:
            pending.append((case, "SMALL_A", role))
    rng = random.Random(int(seed))
    rng.shuffle(pending)
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


def _raw_candidate(treatments: tuple[dict[str, Any], ...]) -> str:
    def score(row: dict[str, Any]) -> tuple[int, int, str]:
        factors = row["factor_vector"]
        support = sum(factors[f"I{i}"] == "ON" for i in range(1, 11)) + sum(factors[f"A{i}"] == "TARGET" for i in range(1, 5))
        complexity = int(factors["amount"] != "MINIMUM") + int(factors["representation"] != "RAW_PROSE")
        return (support, complexity, row["treatment_id"])
    return min(treatments, key=score)["treatment_id"]


def _negative_candidate(treatments: tuple[dict[str, Any], ...], fallback: str) -> str:
    rows = [row for row in treatments if row["factor_vector"]["amount"] == "OVERLOADED"]
    return (sorted(rows, key=lambda row: row["treatment_id"])[0]["treatment_id"] if rows else fallback)


def freeze_confirmation_resolution(
    assignments: Iterable[HDNext1Assignment],
    design: Any,
    development_snapshot: Mapping[str, Any],
) -> tuple[ResolvedConfirmationAssignment, ...]:
    if str(development_snapshot.get("evidence_tier")) != "DEVELOPMENT":
        raise ValueError("protected fresh/sealed evidence is forbidden in confirmation resolution")
    treatments = tuple(design.treatments)
    catalog = {row["treatment_id"]: row for row in treatments}
    winner = str(development_snapshot.get("winner_treatment_id") or "")
    challenger = str(development_snapshot.get("challenger_treatment_id") or "")
    if winner not in catalog:
        raise ValueError("development winner is outside frozen candidate catalog")
    if challenger not in catalog:
        challenger = sorted(catalog)[-1]
    raw = _raw_candidate(treatments)
    negative = _negative_candidate(treatments, challenger)
    role_map = {
        "CONFIRM_PROMOTED_POLICY": winner,
        "CONFIRM_RAW_BASELINE": raw,
        "CONFIRM_STRONGEST_CHALLENGER": challenger,
        "CONFIRM_NEGATIVE_TRANSFER_CONTROL": negative,
    }
    snapshot_hash = stable_hash(dict(development_snapshot))
    rows: list[ResolvedConfirmationAssignment] = []
    for assignment in assignments:
        resolved = role_map.get(assignment.treatment_role)
        if not resolved:
            raise ValueError("unknown protected treatment role")
        rows.append(
            ResolvedConfirmationAssignment(
                **asdict(replace(assignment, resolved_treatment_id=resolved)),
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
