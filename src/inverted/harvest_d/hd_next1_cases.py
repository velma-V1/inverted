from __future__ import annotations

from dataclasses import replace
import random
from typing import Any

from .cases import HarvestCase
from .d3_cases import generate_d3_cases


CONFIRMATION_FAMILY_MAP: dict[str, str] = {
    "F1": "STATE",
    "F2": "EVIDENCE",
    "F3": "TOPOLOGY",
    "F4": "AUTHORITY",
    "F5": "TRANSACTION",
    "F6": "VERIFIER_ORACLE",
    "F7": "RECOVERY",
    "F8": "ROUTING",
    "F9": "GLOBAL_INTERACTION",
}
_FAMILY_TO_ID = {family: family_id for family_id, family in CONFIRMATION_FAMILY_MAP.items()}
_PARTITION_MAP = {
    "hd-next1-development": "development",
    "hd-next1-fresh": "fresh",
    "hd-next1-sealed": "sealed",
}
_PREFIX_MAP = {
    "development": "hd-next1-dev",
    "fresh": "hd-next1-fresh",
    "sealed": "hd-next1-sealed",
}


def generate_hd_next1_cases(partition: str, *, seed: int, per_family: int = 4) -> tuple[HarvestCase, ...]:
    if partition not in _PARTITION_MAP:
        raise ValueError("unknown HD-NEXT-1 partition")
    base_partition = _PARTITION_MAP[partition]
    rows: list[HarvestCase] = []
    for case in generate_d3_cases(partition=base_partition, seed=int(seed), per_family=int(per_family)):
        metadata = dict(case.metadata or {})
        metadata.update(
            {
                "partition": partition,
                "hd_next1_protocol": "HD-NEXT-1",
                "source_case_id": case.case_id,
                "hd_next1_family_id": _FAMILY_TO_ID.get(case.family, "DEVELOPMENT_ONLY"),
            }
        )
        prefix = _PREFIX_MAP[base_partition]
        suffix = case.case_id.split("-", 2)[-1]
        rows.append(replace(case, case_id=f"{prefix}-{suffix}", metadata=metadata))
    return tuple(rows)


def _nested_depth(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + max((_nested_depth(item) for item in value.values()), default=0)
    if isinstance(value, (list, tuple)):
        return 1 + max((_nested_depth(item) for item in value), default=0)
    return 0


def describe_observable_stratum(case: HarvestCase) -> dict[str, object]:
    metadata = dict(case.metadata or {})
    info = dict(metadata.get("d3_information", {}))
    evidence = dict(info.get("I4", {}))
    consequence = dict(info.get("I5", {}))
    uncertainty = dict(info.get("I10", {}))
    recovery = dict(info.get("I9", {}))
    actions = dict(info.get("I7", {}))
    features = dict(metadata.get("structural_features", {}))
    return {
        "family_id": metadata.get("hd_next1_family_id", "DEVELOPMENT_ONLY"),
        "family": case.family,
        "evidence_missing": bool(evidence.get("missing")),
        "risk": str(consequence.get("risk", features.get("risk", "UNKNOWN"))),
        "irreversible": consequence.get("reversible") is False,
        "invariant_sensitive": bool(info.get("I6")),
        "dependency_depth": int(features.get("dependency_depth", _nested_depth(info.get("I8", {})))),
        "action_space_size": int(features.get("action_space_size", len(actions.get("admissible_actions", [])))),
        "novelty": str(uncertainty.get("novelty", uncertainty.get("known_policy_coverage", ""))),
        "boundary_exceeded": bool(
            uncertainty.get("boundary_exceeded", False)
            or uncertainty.get("known_policy_coverage") is False
            or uncertainty.get("novelty") == "HIGH"
        ),
        "recovery_state": str(recovery.get("recovery_state", "")),
    }


def generate_protected_case_pool(config: dict[str, Any]) -> tuple[HarvestCase, ...]:
    size = int(config["protected_pool_size"])
    if size != 63:
        raise ValueError("HD-NEXT-1 protected pool must remain 63")
    per_family = max(8, (size // len(CONFIRMATION_FAMILY_MAP)) + 2)
    fresh = [
        row for row in generate_hd_next1_cases("hd-next1-fresh", seed=int(config["seeds"]["fresh"]), per_family=per_family)
        if row.family in _FAMILY_TO_ID
    ]
    sealed = [
        row for row in generate_hd_next1_cases("hd-next1-sealed", seed=int(config["seeds"]["sealed"]), per_family=per_family)
        if row.family in _FAMILY_TO_ID
    ]
    candidates = fresh + sealed
    random.Random(int(config["randomization_seed"])).shuffle(candidates)
    selected: list[HarvestCase] = []
    used: set[str] = set()
    for family_id in CONFIRMATION_FAMILY_MAP:
        match = next(row for row in candidates if row.metadata["hd_next1_family_id"] == family_id)
        selected.append(match)
        used.add(match.case_id)
    for row in candidates:
        if len(selected) >= size:
            break
        if row.case_id not in used:
            selected.append(row)
            used.add(row.case_id)
    if len(selected) != size:
        raise ValueError("unable to construct 63 unique protected cases")
    partitions = {row.metadata["partition"] for row in selected}
    if partitions != {"hd-next1-fresh", "hd-next1-sealed"}:
        missing = ({"hd-next1-fresh", "hd-next1-sealed"} - partitions).pop()
        replacement = next(row for row in candidates if row.metadata["partition"] == missing and row.case_id not in used)
        selected[-1] = replacement
    return tuple(selected)
