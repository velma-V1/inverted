from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Iterable

from inverted.models import MockModelAdapter

from . import ARMS
from .budget import ExternalActionBudget
from .counterfactual import classify_replay
from .evidence import BlackMagicEvidenceStore
from .metamorphic import evaluate_metamorphic_pair
from .model_io import invoke_json_external
from .types import stable_id, stable_int


REQUIRED_CHALLENGES = (
    "shallow_dependency",
    "medium_dependency",
    "deep_dependency",
    "independent_prerequisites",
    "interacting_prerequisites",
    "local_global_trap",
    "stale_state",
    "delayed_state_update",
    "misleading_success",
    "requirement_change",
    "recoverable_wrong_turn",
    "unrecoverable_wrong_turn",
    "preservation_trap",
    "excessive_decomposition",
    "insufficient_decomposition",
    "irrelevant_history",
    "checkpoint_restore",
    "ambiguous_recovery",
    "auditor_false_accept",
    "auditor_false_reject",
)

REQUIRED_METRICS = (
    "case_count",
    "trial_count",
    "external_action_count",
    "correct_action_rate",
    "by_arm_correct_action_rate",
    "first_divergence_count",
    "first_unrecovered_divergence_count",
    "error_propagation_depth_mean",
    "recovery_opportunity_count",
    "recovery_success_count",
    "local_global_conflict_count",
    "auditor_override_value",
    "externalized_correction_probe_count",
    "targeted_replay_count",
    "sham_replay_count",
    "repair_causal_lift_mean",
    "unresolved_high_severity_count",
    "architecture_delta_inverted_vs_direct",
)


def planned_decision_harvest_actions(
    model_count: int,
    case_count: int,
    arm_count: int = 3,
    replay_budget: int = 0,
) -> int:
    return int(model_count) * int(case_count) * int(arm_count) + int(replay_budget)


def _dependency_depth(challenge: str) -> int:
    return {
        "shallow_dependency": 2,
        "medium_dependency": 5,
        "deep_dependency": 10,
        "excessive_decomposition": 14,
        "insufficient_decomposition": 1,
    }.get(challenge, 4)


def generate_decision_harvest_cases(*, seed: int, case_count: int) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index in range(int(case_count)):
        challenge = REQUIRED_CHALLENGES[index % len(REQUIRED_CHALLENGES)]
        value = 10 + (stable_int("decision-harvest-value", seed, index) % 900)
        path = f"workspace.item{index}.value"
        good_id = stable_id("act", seed, index, "exact", length=12)
        wrong_id = stable_id("act", seed, index, "wrong", length=12)
        broad_id = stable_id("act", seed, index, "broad", length=12)
        defer_id = stable_id("act", seed, index, "defer", length=12)
        actions = [
            {
                "action_id": good_id,
                "operation": "set",
                "path": path,
                "value": value,
                "touches_protected": False,
                "scope": "required-only",
            },
            {
                "action_id": wrong_id,
                "operation": "set",
                "path": path,
                "value": value + 1,
                "touches_protected": False,
                "scope": "required-only",
            },
            {
                "action_id": broad_id,
                "operation": "set",
                "path": path,
                "value": value,
                "touches_protected": True,
                "scope": "over-broad",
            },
            {
                "action_id": defer_id,
                "operation": "defer",
                "path": None,
                "value": None,
                "touches_protected": False,
                "scope": "none",
            },
        ]
        depth = _dependency_depth(challenge)
        prerequisite_ids = [f"p{n}" for n in range(depth)]
        public = {
            "case_id": stable_id("dh", seed, index, length=16),
            "goal": f"Set {path} to {value} while preserving protected.intact=true.",
            "required_path": path,
            "required_value": value,
            "preservation": {"protected.intact": True},
            "dependency_depth": depth,
            "prerequisite_ids": prerequisite_ids,
            "prerequisite_mode": "interacting" if challenge == "interacting_prerequisites" else "independent",
            "observed_condition": challenge.replace("_", " "),
            "actions": actions,
        }
        if challenge == "irrelevant_history":
            public["non_authoritative_history"] = [
                "A previous unrelated workflow used value 404.",
                "This note is historical context, not a current requirement.",
            ]
        if challenge == "requirement_change":
            public["requirement_version"] = 2
            public["superseded_value"] = value - 3
        if challenge in {"stale_state", "delayed_state_update"}:
            public["state_version_note"] = "visible state may lag the committed state"
        cases.append(
            {
                "case_id": public["case_id"],
                "seed": int(seed),
                "challenge": challenge,
                "public": public,
                "initial_state": {"values": {}, "protected": {"intact": True}, "version": 0},
                "oracle": {
                    # The hidden canonical ID is intentionally not a public action ID.
                    "correct_action_id": stable_id("gold", seed, index, length=16),
                    "expected_path": path,
                    "expected_value": value,
                    "catastrophic_action_ids": [broad_id],
                },
            }
        )
    return cases


def derive_system_candidate(public: dict[str, Any]) -> dict[str, Any]:
    required_path = public.get("required_path")
    required_value = public.get("required_value")
    candidates = []
    for action in public.get("actions") or []:
        if (
            action.get("operation", "set") == "set"
            and action.get("path") == required_path
            and action.get("value") == required_value
            and not bool(action.get("touches_protected"))
        ):
            candidates.append(deepcopy(action))
    if candidates:
        candidates.sort(key=lambda item: (str(item.get("scope")), str(item.get("action_id"))))
        return candidates[0]
    defer = next((deepcopy(a) for a in public.get("actions") or [] if a.get("operation") == "defer"), None)
    return defer or {"action_id": "NO_VALID_ACTION", "operation": "defer", "path": None, "value": None}


def _fault_candidate(public: dict[str, Any]) -> dict[str, Any]:
    expected = derive_system_candidate(public)
    for action in public.get("actions") or []:
        if action.get("action_id") != expected.get("action_id") and action.get("operation") == "set" and not action.get("touches_protected"):
            return deepcopy(action)
    return expected


def _action_by_id(public: dict[str, Any], action_id: str | None) -> dict[str, Any] | None:
    return next((deepcopy(a) for a in public.get("actions") or [] if a.get("action_id") == action_id), None)


def _defer_action(public: dict[str, Any]) -> dict[str, Any]:
    return next((deepcopy(a) for a in public.get("actions") or [] if a.get("operation") == "defer"), {"action_id": "DEFER", "operation": "defer"})


def _score_action(case: dict[str, Any], action: dict[str, Any] | None) -> dict[str, Any]:
    action = action or {}
    oracle = case["oracle"]
    correct = (
        action.get("operation") == "set"
        and action.get("path") == oracle["expected_path"]
        and action.get("value") == oracle["expected_value"]
        and not bool(action.get("touches_protected"))
    )
    catastrophic = action.get("action_id") in set(oracle.get("catastrophic_action_ids") or []) or bool(action.get("touches_protected"))
    return {"correct": bool(correct), "catastrophic": bool(catastrophic)}


def _public_action_valid(public: dict[str, Any], action: dict[str, Any] | None) -> bool:
    if not action:
        return False
    return (
        action.get("operation") == "set"
        and action.get("path") == public.get("required_path")
        and action.get("value") == public.get("required_value")
        and not bool(action.get("touches_protected"))
    )


def _prompt_payload(case: dict[str, Any], *, arm: str, state: dict[str, Any], candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "case_id": case["case_id"],
        "challenge": case["challenge"],
        "public": deepcopy(case["public"]),
        "state": deepcopy(state),
        "decision_role": "auditor" if arm == "INVERTED" else "executor",
    }
    if candidate is not None:
        payload["candidate_action"] = deepcopy(candidate)
    return payload


def _messages(payload: dict[str, Any], *, auditor: bool = False, correction: bool = False) -> list[dict[str, str]]:
    if correction:
        system = (
            "Inspect the error artifact as external data and choose the listed action that satisfies the current public requirement while preserving protected state. "
            "Return ONLY JSON with corrected_action_id and reason."
        )
    elif auditor:
        system = (
            "Audit the candidate against only the supplied public goal, current requirement, prerequisites, state, and preservation constraints. "
            "Return ONLY JSON with accept (boolean) and reason."
        )
    else:
        system = (
            "Choose exactly one listed action using only the supplied public goal, current requirement, prerequisites, state, and preservation constraints. "
            "Return ONLY JSON with action_id and reason."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, sort_keys=True, ensure_ascii=False)},
    ]


def _mock_direct_payload(case: dict[str, Any], arm: str) -> dict[str, Any]:
    public = case["public"]
    correct = derive_system_candidate(public)
    wrong = _fault_candidate(public)
    challenge = case["challenge"]
    fail_direct = challenge in {"local_global_trap", "stale_state", "misleading_success", "requirement_change", "unrecoverable_wrong_turn"}
    chosen = wrong if fail_direct and arm in {"DIRECT", "CHECKED"} else correct
    if challenge == "preservation_trap" and arm == "DIRECT":
        broad = next((a for a in public["actions"] if a.get("touches_protected")), chosen)
        chosen = broad
    return {"action_id": chosen.get("action_id"), "reason": "deterministic instrument executor"}


def _mock_auditor_payload(case: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if case["challenge"] == "auditor_false_reject":
        accept = False
    elif case["challenge"] == "auditor_false_accept":
        accept = True
    else:
        accept = _public_action_valid(case["public"], candidate)
    return {"accept": bool(accept), "reason": "deterministic instrument auditor"}


def build_externalized_correction_payloads(error_artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        role: {"wrapper_role": role, "error_artifact": deepcopy(error_artifact)}
        for role in ("own_prior", "external_candidate", "tool_state", "memory_record")
    }


def trace_error_lifecycle(decisions: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = list(decisions)
    divergent = [int(row.get("index", index)) for index, row in enumerate(materialized) if not bool(row.get("correct"))]
    unrecovered = [
        int(row.get("index", index))
        for index, row in enumerate(materialized)
        if not bool(row.get("correct")) and not bool(row.get("recovered"))
    ]
    first = divergent[0] if divergent else None
    first_unrecovered = unrecovered[0] if unrecovered else None
    propagation_depth = 0 if first_unrecovered is None else len([x for x in unrecovered if x >= first_unrecovered])
    return {
        "first_divergence": first,
        "first_unrecovered_divergence": first_unrecovered,
        "propagation_depth": propagation_depth,
        "states": [
            {
                "index": int(row.get("index", index)),
                "state": "contained" if not row.get("correct") and row.get("recovered") else ("propagated" if not row.get("correct") else "clean"),
            }
            for index, row in enumerate(materialized)
        ],
    }


def classify_negative_result(
    *,
    severity: str,
    targeted_flip: bool,
    sham_flip: bool,
    generalized: bool,
    regression: bool,
    interaction: bool,
) -> str:
    if targeted_flip and not sham_flip and generalized and not regression:
        return "CONVERTED"
    if interaction and not regression:
        return "COMBINED"
    return "UNRESOLVED"


def evaluate_harvest_completion(
    findings: Iterable[dict[str, Any]],
    *,
    integrity_ok: bool = True,
    budget_ok: bool = True,
) -> dict[str, Any]:
    blocking = [
        str(row.get("finding_id"))
        for row in findings
        if str(row.get("severity")) == "high" and str(row.get("status")) == "UNRESOLVED"
    ]
    return {
        "pass": bool(integrity_ok and budget_ok and not blocking),
        "blocking_findings": blocking,
        "integrity_ok": bool(integrity_ok),
        "budget_ok": bool(budget_ok),
    }


def _apply_action(state: dict[str, Any], action: dict[str, Any] | None) -> dict[str, Any]:
    new_state = deepcopy(state)
    if action and action.get("operation") == "set" and action.get("path"):
        new_state.setdefault("values", {})[str(action["path"])] = action.get("value")
        if action.get("touches_protected"):
            new_state.setdefault("protected", {})["intact"] = False
        new_state["version"] = int(new_state.get("version", 0)) + 1
    return new_state


def _neighbor_generalization(case: dict[str, Any], targeted: dict[str, Any]) -> bool:
    public = deepcopy(case["public"])
    public["actions"] = list(reversed(public["actions"]))
    public["irrelevant_probe_note"] = "non-authoritative"
    candidate = derive_system_candidate(public)
    return _score_action(case, candidate)["correct"] and _score_action(case, targeted)["correct"]


def _run_externalized_correction_probes(
    *,
    model: Any,
    case: dict[str, Any],
    run_id: str,
    budget: ExternalActionBudget,
    store: BlackMagicEvidenceStore,
) -> list[dict[str, Any]]:
    public = case["public"]
    wrong = _fault_candidate(public)
    payloads = build_externalized_correction_payloads(wrong)
    rows: list[dict[str, Any]] = []
    expected = derive_system_candidate(public)
    for role, wrapped in payloads.items():
        trial_id = stable_id("probe", run_id, getattr(model, "model", "model"), case["case_id"], role)
        call_id = stable_id("call", trial_id)
        payload = {**wrapped, "public": deepcopy(public)}
        result = invoke_json_external(
            model,
            _messages(payload, correction=True),
            role="black_magic_corrector",
            run_id=run_id,
            trial_id=trial_id,
            call_id=call_id,
            budget=budget,
            store=store,
            mock_payload={"corrected_action_id": expected.get("action_id"), "reason": "deterministic correction probe"},
        )
        corrected_id = (result.get("parsed") or {}).get("corrected_action_id")
        corrected = _action_by_id(public, corrected_id)
        score = _score_action(case, corrected)
        row = {"trial_id": trial_id, "wrapper_role": role, "correct": score["correct"], "corrected_action_id": corrected_id}
        store.append("decisions", {"type": "externalized_correction_probe", **row})
        rows.append(row)
    return rows


def run_decision_harvest(
    *,
    models: list[Any],
    cases: list[dict[str, Any]],
    arms: tuple[str, ...] = ARMS,
    run_id: str,
    budget: ExternalActionBudget,
    store: BlackMagicEvidenceStore,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    trials: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for case in cases:
        store.append("tasks", {"case_id": case["case_id"], "challenge": case["challenge"], "public": case["public"], "seed": case["seed"]})
        metamorphic_public = deepcopy(case["public"])
        metamorphic_public["actions"] = list(reversed(metamorphic_public["actions"]))
        base_candidate = derive_system_candidate(case["public"])
        transformed_candidate = derive_system_candidate(metamorphic_public)
        relation = evaluate_metamorphic_pair(base_candidate.get("action_id"), transformed_candidate.get("action_id"), "INVARIANT")
        store.append("metamorphic_pairs", {"case_id": case["case_id"], "transformation": "action_order_reverse", **relation})

    for model in models:
        for case in cases:
            for arm in arms:
                if arm not in ARMS:
                    raise ValueError(f"unknown arm: {arm}")
                state_before = deepcopy(case["initial_state"])
                system_candidate = derive_system_candidate(case["public"])
                candidate = _fault_candidate(case["public"]) if arm == "INVERTED" and case["challenge"] == "auditor_false_accept" else system_candidate
                trial_id = stable_id("trial", run_id, getattr(model, "model", "model"), case["case_id"], arm)
                call_id = stable_id("call", trial_id)
                store.append("state_snapshots", {"trial_id": trial_id, "phase": "before", "state": state_before})
                payload = _prompt_payload(case, arm=arm, state=state_before, candidate=candidate if arm == "INVERTED" else None)
                if arm == "INVERTED":
                    mock_payload = _mock_auditor_payload(case, candidate)
                    result = invoke_json_external(
                        model,
                        _messages(payload, auditor=True),
                        role="black_magic_auditor",
                        run_id=run_id,
                        trial_id=trial_id,
                        call_id=call_id,
                        budget=budget,
                        store=store,
                        mock_payload=mock_payload,
                        candidate_id=str(candidate.get("action_id")),
                    )
                    accept = bool((result.get("parsed") or {}).get("accept")) if result.get("ok") else False
                    selected = deepcopy(candidate) if accept else _defer_action(case["public"])
                    decision_detail = {"accept": accept, "candidate_action_id": candidate.get("action_id")}
                else:
                    result = invoke_json_external(
                        model,
                        _messages(payload),
                        role="black_magic_executor",
                        run_id=run_id,
                        trial_id=trial_id,
                        call_id=call_id,
                        budget=budget,
                        store=store,
                        mock_payload=_mock_direct_payload(case, arm),
                    )
                    selected_id = (result.get("parsed") or {}).get("action_id") if result.get("ok") else None
                    proposed = _action_by_id(case["public"], selected_id) or _defer_action(case["public"])
                    if arm == "CHECKED" and not _public_action_valid(case["public"], proposed):
                        selected = _defer_action(case["public"])
                        decision_detail = {"proposed_action_id": proposed.get("action_id"), "deterministic_block": True}
                    else:
                        selected = proposed
                        decision_detail = {"proposed_action_id": proposed.get("action_id"), "deterministic_block": False}

                score = _score_action(case, selected)
                state_after = _apply_action(state_before, selected)
                trace = trace_error_lifecycle([{"index": 0, "correct": score["correct"], "recovered": False}])
                store.append("decisions", {"trial_id": trial_id, "case_id": case["case_id"], "arm": arm, "selected_action_id": selected.get("action_id"), **decision_detail})
                store.append("actions", {"trial_id": trial_id, "action": selected})
                store.append("tool_results", {"trial_id": trial_id, "simulated": True, "state_after": state_after})
                store.append("transitions", {"trial_id": trial_id, "state_before": state_before, "state_after": state_after})
                store.append("state_snapshots", {"trial_id": trial_id, "phase": "after", "state": state_after})
                store.append("oracle_results", {"trial_id": trial_id, "correct": score["correct"], "catastrophic": score["catastrophic"], "oracle": case["oracle"]})
                store.append("error_lifecycle", {"trial_id": trial_id, **trace})

                trial = {
                    "trial_id": trial_id,
                    "case_id": case["case_id"],
                    "challenge": case["challenge"],
                    "model": str(getattr(model, "model", "unknown")),
                    "arm": arm,
                    "selected_action_id": selected.get("action_id"),
                    "system_candidate_id": system_candidate.get("action_id"),
                    "candidate_correct": _score_action(case, candidate if arm == "INVERTED" else system_candidate)["correct"],
                    "correct": score["correct"],
                    "catastrophic": score["catastrophic"],
                    "first_divergence": trace["first_divergence"],
                    "first_unrecovered_divergence": trace["first_unrecovered_divergence"],
                    "propagation_depth": trace["propagation_depth"],
                }

                if not score["correct"]:
                    targeted = derive_system_candidate(case["public"])
                    targeted_score = _score_action(case, targeted)
                    sham = deepcopy(selected)
                    sham["irrelevant_sham_note"] = "changed without semantic effect"
                    sham_score = _score_action(case, sham)
                    classification = classify_replay(
                        original_success=False,
                        targeted_success=targeted_score["correct"],
                        sham_success=sham_score["correct"],
                    )
                    generalized = _neighbor_generalization(case, targeted)
                    regression = False
                    status = classify_negative_result(
                        severity="high" if score["catastrophic"] else "medium",
                        targeted_flip=targeted_score["correct"],
                        sham_flip=sham_score["correct"],
                        generalized=generalized,
                        regression=regression,
                        interaction=False,
                    )
                    finding_id = stable_id("finding", trial_id)
                    store.append("interventions", {"finding_id": finding_id, "trial_id": trial_id, "targeted_action": targeted, "targeted_success": targeted_score["correct"]})
                    store.append("shams", {"finding_id": finding_id, "trial_id": trial_id, "sham_action": sham, "sham_success": sham_score["correct"]})
                    finding = {
                        "finding_id": finding_id,
                        "trial_id": trial_id,
                        "case_id": case["case_id"],
                        "challenge": case["challenge"],
                        "model": str(getattr(model, "model", "unknown")),
                        "arm": arm,
                        "severity": "high" if score["catastrophic"] else "medium",
                        "status": status,
                        "first_divergence": 0,
                        "targeted_success": targeted_score["correct"],
                        "sham_success": sham_score["correct"],
                        "causal_classification": classification,
                        "causal_lift": int(targeted_score["correct"]) - int(sham_score["correct"]),
                        "generalized": generalized,
                        "regression": regression,
                        "architecture_instruction": "FIX" if status == "CONVERTED" else "CONDITIONAL",
                    }
                    findings.append(finding)
                    trial["repair_status"] = status
                    trial["repair_causal_lift"] = finding["causal_lift"]
                else:
                    trial["repair_status"] = None
                    trial["repair_causal_lift"] = 0
                trials.append(trial)

        if cases:
            _run_externalized_correction_probes(
                model=model,
                case=cases[0],
                run_id=run_id,
                budget=budget,
                store=store,
            )

    challenge_counts = defaultdict(int)
    for case in cases:
        challenge_counts[case["challenge"]] += 1
    store.append(
        "coverage",
        {
            "coverage_type": "required_challenges",
            "required": list(REQUIRED_CHALLENGES),
            "observed": dict(challenge_counts),
            "complete": all(challenge_counts[name] > 0 for name in REQUIRED_CHALLENGES),
        },
    )

    by_arm: dict[str, float] = {}
    for arm in arms:
        rows = [row for row in trials if row["arm"] == arm]
        by_arm[arm] = sum(bool(row["correct"]) for row in rows) / len(rows) if rows else 0.0
    failures = [row for row in trials if not row["correct"]]
    causal_lifts = [float(row.get("causal_lift", 0)) for row in findings]
    inverted_rate = by_arm.get("INVERTED", 0.0)
    direct_rate = by_arm.get("DIRECT", 0.0)
    metrics = {
        "case_count": len(cases),
        "trial_count": len(trials),
        "external_action_count": budget.used,
        "correct_action_rate": sum(bool(row["correct"]) for row in trials) / len(trials) if trials else 0.0,
        "by_arm_correct_action_rate": by_arm,
        "first_divergence_count": len(failures),
        "first_unrecovered_divergence_count": len(failures),
        "error_propagation_depth_mean": sum(int(row["propagation_depth"]) for row in failures) / len(failures) if failures else 0.0,
        "recovery_opportunity_count": len(failures),
        "recovery_success_count": sum(1 for row in findings if row["status"] == "CONVERTED"),
        "local_global_conflict_count": sum(1 for row in trials if row["challenge"] == "local_global_trap"),
        "auditor_override_value": sum(1 if row["correct"] else -1 for row in trials if row["arm"] == "INVERTED" and row["challenge"] in {"auditor_false_accept", "auditor_false_reject"}),
        "externalized_correction_probe_count": 4 * len(models) if cases else 0,
        "targeted_replay_count": len(findings),
        "sham_replay_count": len(findings),
        "repair_causal_lift_mean": sum(causal_lifts) / len(causal_lifts) if causal_lifts else 0.0,
        "unresolved_high_severity_count": sum(1 for row in findings if row["severity"] == "high" and row["status"] == "UNRESOLVED"),
        "architecture_delta_inverted_vs_direct": inverted_rate - direct_rate,
    }
    return trials, metrics, findings


def run_decision_harvest_smoke(output_dir: str | Path, *, run_id: str = "smoke") -> dict[str, Any]:
    root = Path(output_dir) / "black-magic" / "decision_harvest" / str(run_id)
    store = BlackMagicEvidenceStore(root, experiment_name="decision_harvest", run_id=str(run_id))
    budget = ExternalActionBudget("decision_harvest", 1200)
    model = MockModelAdapter(model="black-magic-mock", seed=20260901, capture_content=True)
    cases = generate_decision_harvest_cases(seed=20260901, case_count=len(REQUIRED_CHALLENGES))
    trials, metrics, findings = run_decision_harvest(
        models=[model],
        cases=cases,
        arms=ARMS,
        run_id=str(run_id),
        budget=budget,
        store=store,
    )
    completion = evaluate_harvest_completion(findings, integrity_ok=True, budget_ok=budget.used <= budget.cap)
    metrics["completion"] = completion
    store.event("run_completed", {"trials": len(trials), "findings": len(findings), "budget_used": budget.used})
    finalized = store.finalize(
        preregistration={
            "experiment": "decision_harvest",
            "status": "INSTRUMENT VALIDATION — NOT ARCHITECTURE EVIDENCE",
            "hard_external_action_cap": 1200,
            "deterministic_oracle_is_authority": True,
            "hidden_oracle_model_visible": False,
        },
        config={"seed": 20260901, "case_count": len(cases), "arms": list(ARMS)},
        provenance={"instrument_validation": True, "provider": "mock", "model": model.model},
        metrics=metrics,
        budget=budget.to_dict(),
        trials=trials,
        findings=findings,
    )
    if finalized["integrity"]["status"] != "OK":
        raise RuntimeError(f"decision harvest smoke integrity failed: {finalized['integrity']}")
    return {
        "root": str(root),
        "instrument_validation": True,
        "budget": budget.to_dict(),
        "metrics": metrics,
        "findings": findings,
    }
