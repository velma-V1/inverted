from __future__ import annotations

from typing import Any, Iterable

from .test3_s1_analysis import derive_s1_verdict, summarize_s1
from .test3_s1_r3_runtime import causal_order_signature


S1_R3_PROTOCOL = "S1-R3"
S1_R3_HOLDOUT = "A-R3"
S1_R2_PROTOCOL = "S1-R2"
S1_R2_HOLDOUT = "A-R2"
_FIXED_ARMS = ("S1-A1", "S1-A2", "S1-A3")


def _r2_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project R3 trial rows onto the frozen R2 statistical contract only.

    R3 intentionally reuses the preregistered R2 sample size, matched-task,
    equal-compute, family metric, and verdict thresholds. Protocol identity and
    the new causal-order uniqueness requirement are validated separately here.
    """
    return [
        {**row, "protocol_revision": S1_R2_PROTOCOL, "holdout": S1_R2_HOLDOUT}
        for row in rows
    ]


def _causal_signatures(rows: list[dict[str, Any]]) -> tuple[dict[str, tuple[str, ...]], list[str]]:
    failures: list[str] = []
    signatures: dict[str, tuple[str, ...]] = {}
    for arm_id in _FIXED_ARMS:
        orders = {
            str(row.get("order") or "")
            for row in rows
            if str(row.get("arm_id") or "") == arm_id
        }
        orders.discard("")
        if len(orders) != 1:
            failures.append(f"single_frozen_order_{arm_id.lower().replace('-', '_')}")
            continue
        order = next(iter(orders))
        signatures[arm_id] = causal_order_signature({"order": order})
    if len(signatures) != 3 or len(set(signatures.values())) != 3:
        failures.append("causal_order_signatures_unique")
    return signatures, failures


def summarize_s1_r3(
    rows: Iterable[dict[str, Any]],
    *,
    baseline_arm: str = "S1-A0",
    random_control_arm: str = "S1-A3",
) -> dict[str, Any]:
    source = [dict(row) for row in rows]
    base = summarize_s1(
        _r2_projection(source),
        baseline_arm=baseline_arm,
        random_control_arm=random_control_arm,
    )
    failures = list(base.get("protocol_failures") or [])

    revisions = {str(row.get("protocol_revision") or "") for row in source if row.get("complete") is True}
    holdouts = {str(row.get("holdout") or "") for row in source if row.get("complete") is True}
    if revisions != {S1_R3_PROTOCOL}:
        failures.append("protocol_revision_s1_r3")
    if holdouts != {S1_R3_HOLDOUT}:
        failures.append("holdout_a_r3")

    signatures, signature_failures = _causal_signatures(source)
    failures.extend(signature_failures)
    failures = list(dict.fromkeys(failures))
    valid = not failures

    exposure = dict(base.get("intervention_exposure") or {})
    exposure.update({
        "causal_order_signatures_unique": len(signatures) == 3 and len(set(signatures.values())) == 3,
        "causal_order_signatures": {arm_id: list(signature) for arm_id, signature in signatures.items()},
    })
    return {
        **base,
        "protocol_revision": S1_R3_PROTOCOL if valid else None,
        "holdout": S1_R3_HOLDOUT if valid else None,
        "detected_protocol_contract": S1_R3_PROTOCOL,
        "protocol_valid_for_primary_claim": valid,
        "protocol_failures": failures,
        "intervention_exposure": exposure,
    }


def derive_s1_r3_verdict(summary: dict[str, Any], *, full_power_clusters: int | None) -> dict[str, Any]:
    if summary.get("protocol_valid_for_primary_claim") is not True:
        failures = list(summary.get("protocol_failures") or [])
        return {
            "verdict": "S1_R3_INVALID_PROTOCOL",
            "reason": "S1-R3 primary causal claim withheld because the protocol gate failed: " + ", ".join(failures),
            "winning_arm_id": None,
            "matched_task_count": int(summary.get("matched_task_count") or 0),
            "tier_a_architecture_claim": False,
            "protocol_valid_for_primary_claim": False,
            "protocol_failures": failures,
            "protocol_revision": S1_R3_PROTOCOL,
            "holdout": S1_R3_HOLDOUT,
            "full_power_cluster_requirement": full_power_clusters,
            "cannot_rule_out_target_effect": True,
        }

    projected = {
        **summary,
        "protocol_revision": S1_R2_PROTOCOL,
        "holdout": S1_R2_HOLDOUT,
        "detected_protocol_contract": S1_R2_PROTOCOL,
        "protocol_valid_for_primary_claim": True,
        "protocol_failures": [],
    }
    verdict = dict(derive_s1_verdict(projected, full_power_clusters=full_power_clusters))
    names = {
        "S1_R2_FIXED_ORDER_LARGE_SIGNAL": "S1_R3_FIXED_ORDER_LARGE_SIGNAL",
        "S1_R2_FIXED_ORDER_CATEGORY_CONDITIONAL_SIGNAL": "S1_R3_FIXED_ORDER_CATEGORY_CONDITIONAL_SIGNAL",
        "S1_R2_FIXED_ORDER_NEGATIVE_OR_HARMFUL": "S1_R3_FIXED_ORDER_NEGATIVE_OR_HARMFUL",
        "S1_R2_SCREEN_NON_DECISIVE": "S1_R3_SCREEN_NON_DECISIVE",
        "S1_R2_INVALID_PROTOCOL": "S1_R3_INVALID_PROTOCOL",
    }
    verdict["verdict"] = names.get(str(verdict.get("verdict")), str(verdict.get("verdict")))
    verdict["reason"] = str(verdict.get("reason") or "").replace("S1-R2", "S1-R3").replace("A-R2", "A-R3")
    if verdict.get("claim_scope"):
        verdict["claim_scope"] = str(verdict["claim_scope"]).replace("S1-R2", "S1-R3").replace("A-R2", "A-R3")
    verdict["protocol_revision"] = S1_R3_PROTOCOL
    verdict["holdout"] = S1_R3_HOLDOUT
    verdict["protocol_valid_for_primary_claim"] = True
    return verdict
