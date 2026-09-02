from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def _fingerprint(view: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(view).encode("utf-8")).hexdigest()


def _truth_key(manifest_row: dict[str, Any]) -> str:
    truth = {
        "perturbation_class": manifest_row.get("perturbation_class"),
        "fixture_injected_faults": manifest_row.get("fixture_injected_faults") or [],
    }
    return _canonical(truth)


def router_observability_analysis(runtime: dict[str, Any]) -> dict[str, Any]:
    """Measure hidden-fault aliasing in router-visible evidence after execution.

    This function is intentionally pure and post hoc. It never calls routing
    policy functions and never mutates the supplied runtime structure.
    """
    manifest = {
        str(row.get("task_id")): dict(row)
        for row in (runtime.get("holdout_manifest") or [])
        if row.get("task_id") is not None
    }
    decisions = {
        (str(row.get("arm_id")), str(row.get("task_id")), int(row.get("step_index") or 0)): dict(row)
        for row in (runtime.get("routing_decisions") or [])
    }
    outcomes = {
        (str(row.get("arm_id")), str(row.get("task_id"))): {
            "success": bool(row.get("success")),
            "catastrophic": bool(row.get("catastrophic")),
        }
        for row in (runtime.get("trials") or [])
    }

    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    observation_by_task: dict[tuple[str, int, str], str] = {}
    for raw in runtime.get("routing_state_snapshots") or []:
        row = dict(raw)
        arm_id = str(row.get("arm_id"))
        task_id = str(row.get("task_id"))
        step_index = int(row.get("step_index") or 0)
        view = dict(row.get("router_view") or {})
        fp = _fingerprint(view)
        grouped[(arm_id, step_index, fp)].append({
            "task_id": task_id,
            "router_view": view,
        })
        observation_by_task[(arm_id, step_index, task_id)] = fp

    rows: list[dict[str, Any]] = []
    for (arm_id, step_index, fp), group in sorted(grouped.items(), key=lambda item: item[0]):
        task_ids = sorted({item["task_id"] for item in group})
        hidden_truths: dict[str, dict[str, Any]] = {}
        perturbations: set[str] = set()
        injected_faults: set[str] = set()
        action_selected: set[str] = set()
        observed_outcomes: list[dict[str, Any]] = []
        for task_id in task_ids:
            private = manifest.get(task_id, {})
            truth_key = _truth_key(private)
            hidden_truths[truth_key] = {
                "perturbation_class": private.get("perturbation_class"),
                "fixture_injected_faults": list(private.get("fixture_injected_faults") or []),
            }
            if private.get("perturbation_class") is not None:
                perturbations.add(str(private.get("perturbation_class")))
            injected_faults.update(str(value) for value in (private.get("fixture_injected_faults") or []))
            decision = decisions.get((arm_id, task_id, step_index), {})
            if decision.get("action_selected") is not None:
                action_selected.add(str(decision.get("action_selected")))
            outcome = outcomes.get((arm_id, task_id))
            if outcome is not None:
                observed_outcomes.append({"task_id": task_id, **outcome})
        distinct_truths = len(hidden_truths)
        rows.append({
            "arm_id": arm_id,
            "step_index": step_index,
            "observation_fingerprint": fp,
            "router_view": group[0]["router_view"],
            "case_count": len(task_ids),
            "task_ids": task_ids,
            "distinct_hidden_fault_truths": distinct_truths,
            "hidden_fault_truths": list(hidden_truths.values()),
            "hidden_perturbation_classes": sorted(perturbations),
            "hidden_injected_faults": sorted(injected_faults),
            "collision": distinct_truths > 1,
            "actions_selected": sorted(action_selected),
            "observed_outcomes": observed_outcomes,
        })

    collision_rows = [row for row in rows if row["collision"]]
    ambiguous_task_ids = {
        str(task_id)
        for row in collision_rows
        for task_id in (row.get("task_ids") or [])
    }
    unique_task_ids = {
        str(row.get("task_id"))
        for row in (runtime.get("routing_state_snapshots") or [])
        if row.get("task_id") is not None
    }

    resolved_b2 = 0
    for row in collision_rows:
        if row.get("arm_id") != "S2-B2":
            continue
        step_index = int(row.get("step_index") or 0)
        b3_fingerprints = {
            observation_by_task.get(("S2-B3", step_index, str(task_id)))
            for task_id in (row.get("task_ids") or [])
        }
        b3_fingerprints.discard(None)
        if len(b3_fingerprints) > 1:
            resolved_b2 += 1

    b3_remaining = sum(1 for row in collision_rows if row.get("arm_id") == "S2-B3")
    total_groups = len(rows)
    summary = {
        "observation_group_count": total_groups,
        "collision_count": len(collision_rows),
        "collision_rate": len(collision_rows) / total_groups if total_groups else 0.0,
        "ambiguous_case_count": len(ambiguous_task_ids),
        "ambiguous_case_rate": len(ambiguous_task_ids) / len(unique_task_ids) if unique_task_ids else 0.0,
        "largest_collision_group_size": max((int(row.get("case_count") or 0) for row in collision_rows), default=0),
        "b2_to_b3_collisions_resolved": resolved_b2,
        "b3_collisions_remaining": b3_remaining,
    }
    return {"rows": rows, "summary": summary}
