from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from typing import Any, Iterable


NORMALIZED_EVENT_TYPES = (
    "SESSION_START",
    "CONTEXT_LOAD",
    "CONTEXT_COMPACT",
    "PLAN_CREATE",
    "PLAN_UPDATE",
    "SEARCH",
    "FILE_READ",
    "FILE_WRITE",
    "FILE_EDIT",
    "COMMAND",
    "TEST",
    "LINT",
    "BUILD",
    "WEB",
    "MCP",
    "SUBAGENT_START",
    "SUBAGENT_RESULT",
    "PERMISSION_REQUEST",
    "PERMISSION_DENIED",
    "APPROVAL",
    "TOOL_ERROR",
    "TOOL_RESULT",
    "VERIFY",
    "REPAIR",
    "REVERT",
    "CHECKPOINT",
    "RESUME",
    "FINAL_RESPONSE",
    "SESSION_STOP",
    "UNKNOWN",
)

MECHANISMS: tuple[dict[str, str], ...] = (
    {"id":"M01","name":"instruction_discovery_precedence"},
    {"id":"M02","name":"repo_orientation_search_strategy"},
    {"id":"M03","name":"planning_todo_strategy"},
    {"id":"M04","name":"decomposition_granularity"},
    {"id":"M05","name":"tool_selection"},
    {"id":"M06","name":"tool_batching_parallelism"},
    {"id":"M07","name":"file_read_breadth"},
    {"id":"M08","name":"edit_granularity"},
    {"id":"M09","name":"patch_vs_rewrite"},
    {"id":"M10","name":"test_selection"},
    {"id":"M11","name":"verification_cadence"},
    {"id":"M12","name":"verification_before_stop"},
    {"id":"M13","name":"response_to_test_failure"},
    {"id":"M14","name":"retry_repair_threshold"},
    {"id":"M15","name":"rollback_revert"},
    {"id":"M16","name":"state_postcondition_verification"},
    {"id":"M17","name":"context_compaction_response"},
    {"id":"M18","name":"context_rehydration"},
    {"id":"M19","name":"persistent_project_memory"},
    {"id":"M20","name":"resume_checkpoint"},
    {"id":"M21","name":"subagent_spawning"},
    {"id":"M22","name":"delegation_target_selection"},
    {"id":"M23","name":"subagent_result_verification"},
    {"id":"M24","name":"parallel_work_coordination"},
    {"id":"M25","name":"permission_approval_escalation"},
    {"id":"M26","name":"sandbox_boundary_handling"},
    {"id":"M27","name":"network_mcp_escalation"},
    {"id":"M28","name":"ambiguity_ask_threshold"},
    {"id":"M29","name":"confidence_action_threshold"},
    {"id":"M30","name":"dependency_install_behavior"},
    {"id":"M31","name":"diff_review_cleanup"},
    {"id":"M32","name":"stop_condition"},
    {"id":"M33","name":"unfinished_work_detection"},
    {"id":"M34","name":"self_correction_after_challenge"},
    {"id":"M35","name":"instruction_injection_resistance"},
    {"id":"M36","name":"failure_snapshot_replay"},
    {"id":"M37","name":"token_context_economy"},
    {"id":"M38","name":"time_call_economy"},
    {"id":"M39","name":"deterministic_guardrail_interaction"},
    {"id":"M40","name":"mechanism_combinations_synergy"},
)

PATHOLOGIES: tuple[dict[str, Any], ...] = (
    {"id":"PU-01","name":"passing_tests_wrong_system","level":"P7","mechanisms":["M11","M12","M32"]},
    {"id":"PU-02","name":"two_correct_fixes_break_each_other","level":"P8","mechanisms":["M04","M11","M40"]},
    {"id":"PU-03","name":"stale_truth_newer_truth","level":"P8","mechanisms":["M01","M19","M34"]},
    {"id":"PU-04","name":"tool_success_state_unchanged","level":"P8","mechanisms":["M16","M39"]},
    {"id":"PU-05","name":"correct_patch_wrong_file","level":"P8","mechanisms":["M02","M07","M09"]},
    {"id":"PU-06","name":"hidden_contract_four_files","level":"P8","mechanisms":["M02","M04","M07"]},
    {"id":"PU-07","name":"false_minimal_diff","level":"P8","mechanisms":["M08","M09","M31"]},
    {"id":"PU-08","name":"generated_file_decoy","level":"P8","mechanisms":["M02","M09","M30"]},
    {"id":"PU-09","name":"test_is_wrong","level":"P9","mechanisms":["M10","M11","M34"]},
    {"id":"PU-10","name":"fixture_is_wrong","level":"P9","mechanisms":["M10","M13","M34"]},
    {"id":"PU-11","name":"delayed_regression","level":"P8","mechanisms":["M10","M11","M12"]},
    {"id":"PU-12","name":"retry_trap","level":"P8","mechanisms":["M13","M14"]},
    {"id":"PU-13","name":"repair_loop_trap","level":"P9","mechanisms":["M13","M14","M34"]},
    {"id":"PU-14","name":"context_poisoned_by_old_assumption","level":"P9","mechanisms":["M17","M18","M19"]},
    {"id":"PU-15","name":"requirement_mutation_mid_task","level":"P9","mechanisms":["M03","M20","M34"]},
    {"id":"PU-16","name":"ambiguous_request_unequal_risk","level":"P8","mechanisms":["M25","M28","M29"]},
    {"id":"PU-17","name":"multi_repo_ownership_trap","level":"P9","mechanisms":["M02","M26","M31"]},
    {"id":"PU-18","name":"dependency_upgrade_domino","level":"P9","mechanisms":["M03","M30","M38"]},
    {"id":"PU-19","name":"circular_evidence","level":"P9","mechanisms":["M01","M02","M35"]},
    {"id":"PU-20","name":"parallelism_hazard","level":"P9","mechanisms":["M06","M21","M24"]},
    {"id":"PU-21","name":"parallelism_opportunity","level":"P8","mechanisms":["M06","M21","M24"]},
    {"id":"PU-22","name":"search_ranking_adversary","level":"P9","mechanisms":["M02","M07"]},
    {"id":"PU-23","name":"near_miss_api","level":"P9","mechanisms":["M05","M11"]},
    {"id":"PU-24","name":"state_split_brain","level":"P9","mechanisms":["M16","M19","M34"]},
    {"id":"PU-25","name":"green_units_broken_packaging","level":"P8","mechanisms":["M10","M11","M12"]},
    {"id":"PU-26","name":"green_build_broken_runtime","level":"P8","mechanisms":["M10","M11","M12"]},
    {"id":"PU-27","name":"negative_space_requirement","level":"P8","mechanisms":["M01","M31"]},
    {"id":"PU-28","name":"overengineering_trap","level":"P8","mechanisms":["M03","M08","M31","M38"]},
    {"id":"PU-29","name":"underengineering_trap","level":"P9","mechanisms":["M03","M04","M09"]},
    {"id":"PU-30","name":"conflicting_success_metrics","level":"P9","mechanisms":["M01","M03","M29"]},
    {"id":"PU-31","name":"hidden_edge_case_family","level":"P9","mechanisms":["M10","M34","M40"]},
    {"id":"PU-32","name":"self_generated_regression","level":"P9","mechanisms":["M11","M31","M34"]},
    {"id":"PU-33","name":"interrupted_ambiguous_partial_state","level":"P9","mechanisms":["M20","M33"]},
    {"id":"PU-34","name":"compaction_boundary_trap","level":"P10","mechanisms":["M17","M18","M19"]},
    {"id":"PU-35","name":"permission_escalation_decoy","level":"P8","mechanisms":["M25","M26"]},
    {"id":"PU-36","name":"necessary_escalation","level":"P8","mechanisms":["M25","M28"]},
    {"id":"PU-37","name":"misleading_failure_attribution","level":"P9","mechanisms":["M02","M13","M34"]},
    {"id":"PU-38","name":"non_monotonic_progress","level":"P10","mechanisms":["M03","M13","M32"]},
    {"id":"PU-39","name":"locally_impossible_globally_solvable","level":"P10","mechanisms":["M04","M07","M40"]},
    {"id":"PU-40","name":"globally_ambiguous_correctly_unsolvable","level":"P10","mechanisms":["M28","M29","M32"]},
)

COMPOUNDS: tuple[dict[str, Any], ...] = (
    {"id":"PU-C01","level":"P10","name":"false_green_stale_generated_context","components":["PU-03","PU-08","PU-11","PU-12","PU-34"]},
    {"id":"PU-C02","level":"P10","name":"parallel_cross_repo_split_brain","components":["PU-17","PU-20","PU-24","PU-33"]},
    {"id":"PU-C03","level":"P10","name":"repair_loop_hidden_family_nonmonotonic","components":["PU-13","PU-31","PU-38"]},
    {"id":"PU-C04","level":"P10","name":"authority_ambiguity_near_miss_api","components":["PU-16","PU-23","PU-35","PU-36"]},
    {"id":"PU-C05","level":"P10","name":"evidence_independence_context_mutation","components":["PU-14","PU-15","PU-19","PU-39","PU-40"]},
)

EVENT_ALIASES = {
    "session_started":"SESSION_START",
    "thread.started":"SESSION_START",
    "sessionstart":"SESSION_START",
    "compact":"CONTEXT_COMPACT",
    "postcompact":"CONTEXT_COMPACT",
    "plan":"PLAN_CREATE",
    "plan_update":"PLAN_UPDATE",
    "search":"SEARCH",
    "grep":"SEARCH",
    "ripgrep":"SEARCH",
    "read":"FILE_READ",
    "file_read":"FILE_READ",
    "write":"FILE_WRITE",
    "file_write":"FILE_WRITE",
    "edit":"FILE_EDIT",
    "patch":"FILE_EDIT",
    "command":"COMMAND",
    "command_execution":"COMMAND",
    "exec_command":"COMMAND",
    "test":"TEST",
    "pytest":"TEST",
    "lint":"LINT",
    "build":"BUILD",
    "web":"WEB",
    "mcp":"MCP",
    "spawn_agent":"SUBAGENT_START",
    "subagent_start":"SUBAGENT_START",
    "subagent_stop":"SUBAGENT_RESULT",
    "permissionrequest":"PERMISSION_REQUEST",
    "permissiondenied":"PERMISSION_DENIED",
    "tool_error":"TOOL_ERROR",
    "tool_result":"TOOL_RESULT",
    "verify":"VERIFY",
    "repair":"REPAIR",
    "revert":"REVERT",
    "checkpoint":"CHECKPOINT",
    "resume":"RESUME",
    "agent_message":"FINAL_RESPONSE",
    "turn.completed":"SESSION_STOP",
    "stop":"SESSION_STOP",
}


def _canon(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def mechanism_registry() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mechanisms": deepcopy(list(MECHANISMS)),
        "status_levels": [
            "OBSERVED","REPLICATED","CAUSAL","GENERALIZED","HIGH_VALUE",
            "CLONE_CANDIDATE","MODIFY_CANDIDATE","REJECT","UNKNOWN","NOT_LOOKED_AT",
        ],
    }


def pathology_registry() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "pathologies": deepcopy(list(PATHOLOGIES)),
        "compounds": deepcopy(list(COMPOUNDS)),
        "ladder": [f"P{i}" for i in range(11)],
    }


def compound_ablations(compound: dict[str, Any]) -> list[dict[str, Any]]:
    components = list(compound.get("components") or [])
    return [
        {
            "compound_id": compound["id"],
            "ablation_id": f"{compound['id']}-A{index + 1:02d}",
            "removed_component": component,
            "active_components": [x for x in components if x != component],
        }
        for index, component in enumerate(components)
    ]


def normalize_event(subject: str, raw_event: dict[str, Any], *, sequence: int, raw_ref: str | None = None) -> dict[str, Any]:
    """Map one observable subject event into the common event vocabulary.

    Unknown structures remain UNKNOWN; this function never invents a tool/action.
    """
    candidates: list[str] = []
    for key in ("type","event_type","name","hook_event_name","subtype"):
        if key in raw_event:
            candidates.append(str(raw_event.get(key)))
    item = raw_event.get("item")
    if isinstance(item, dict):
        for key in ("type","name"):
            if key in item:
                candidates.append(str(item.get(key)))
    payload = raw_event.get("payload")
    if isinstance(payload, dict):
        for key in ("type","name"):
            if key in payload:
                candidates.append(str(payload.get(key)))

    normalized = "UNKNOWN"
    for candidate in candidates:
        raw = candidate.strip()
        canon = _canon(raw)
        dotted = raw.strip().lower()
        for alias, event_type in EVENT_ALIASES.items():
            alias_canon = _canon(alias)
            if canon == alias_canon or dotted == alias.lower():
                normalized = event_type
                break
        if normalized != "UNKNOWN":
            break

    text = json.dumps(raw_event, sort_keys=True, default=str).lower()
    if normalized == "COMMAND":
        if any(x in text for x in ("pytest", "unittest", "npm test", "cargo test", "go test")):
            normalized = "TEST"
        elif any(x in text for x in ("ruff ", "eslint", "flake8", "mypy", "clippy")):
            normalized = "LINT"
        elif any(x in text for x in ("npm run build", "cargo build", "python -m build", "go build")):
            normalized = "BUILD"

    return {
        "schema_version": 1,
        "sequence": int(sequence),
        "subject": str(subject),
        "event_type": normalized,
        "raw_ref": raw_ref,
        "raw_hash": _stable_hash(raw_event),
        "observable": True,
        "raw_type_candidates": candidates,
    }


def normalize_events(subject: str, raw_events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        normalize_event(subject, event, sequence=index + 1, raw_ref=f"raw:{index + 1}")
        for index, event in enumerate(raw_events)
    ]


def trajectory_signature(events: Iterable[dict[str, Any]]) -> list[str]:
    return [str(event.get("event_type") or "UNKNOWN") for event in events]


def first_divergence(success_events: list[dict[str, Any]], failed_events: list[dict[str, Any]]) -> dict[str, Any]:
    success_sig = trajectory_signature(success_events)
    failed_sig = trajectory_signature(failed_events)
    limit = min(len(success_sig), len(failed_sig))
    for index in range(limit):
        if success_sig[index] != failed_sig[index]:
            return {
                "diverged": True,
                "index": index,
                "success_event": success_sig[index],
                "failed_event": failed_sig[index],
                "success_raw_ref": success_events[index].get("raw_ref"),
                "failed_raw_ref": failed_events[index].get("raw_ref"),
            }
    if len(success_sig) != len(failed_sig):
        return {
            "diverged": True,
            "index": limit,
            "success_event": success_sig[limit] if limit < len(success_sig) else None,
            "failed_event": failed_sig[limit] if limit < len(failed_sig) else None,
            "success_raw_ref": success_events[limit].get("raw_ref") if limit < len(success_events) else None,
            "failed_raw_ref": failed_events[limit].get("raw_ref") if limit < len(failed_events) else None,
        }
    return {"diverged": False, "index": None}


def detect_stuck_loops(events: list[dict[str, Any]], *, repeat_threshold: int = 3) -> list[dict[str, Any]]:
    """Detect repeated observable action patterns without claiming hidden intent."""
    sig = trajectory_signature(events)
    loops: list[dict[str, Any]] = []
    for width in (1, 2, 3, 4):
        index = 0
        while index + width * repeat_threshold <= len(sig):
            chunk = sig[index:index + width]
            repeats = 1
            cursor = index + width
            while cursor + width <= len(sig) and sig[cursor:cursor + width] == chunk:
                repeats += 1
                cursor += width
            if repeats >= repeat_threshold and any(x in chunk for x in ("COMMAND","TEST","TOOL_ERROR","REPAIR","FILE_EDIT")):
                loops.append({
                    "start_sequence": index + 1,
                    "end_sequence": cursor,
                    "pattern": chunk,
                    "repeats": repeats,
                    "width": width,
                })
                index = cursor
            else:
                index += 1
    unique = {}
    for loop in loops:
        key = (loop["start_sequence"], loop["end_sequence"], tuple(loop["pattern"]))
        unique[key] = loop
    return list(unique.values())


def trajectory_metrics(events: list[dict[str, Any]], *, oracle_success: bool | None = None) -> dict[str, Any]:
    sig = trajectory_signature(events)
    counts = Counter(sig)

    def first(event_type: str) -> int | None:
        try:
            return sig.index(event_type) + 1
        except ValueError:
            return None

    def last(event_type: str) -> int | None:
        try:
            return len(sig) - 1 - sig[::-1].index(event_type) + 1
        except ValueError:
            return None

    last_edit = max([x for x in (last("FILE_EDIT"), last("FILE_WRITE")) if x is not None], default=None)
    last_verify = max([x for x in (last("TEST"), last("LINT"), last("BUILD"), last("VERIFY")) if x is not None], default=None)
    verification_after_last_edit = (
        bool(last_edit is not None and last_verify is not None and last_verify > last_edit)
        if last_edit is not None else None
    )
    loops = detect_stuck_loops(events)
    return {
        "event_count": len(events),
        "counts": dict(counts),
        "first_search": first("SEARCH"),
        "first_read": first("FILE_READ"),
        "first_edit": min([x for x in (first("FILE_EDIT"), first("FILE_WRITE")) if x is not None], default=None),
        "first_test": first("TEST"),
        "first_verify": min([x for x in (first("TEST"), first("LINT"), first("BUILD"), first("VERIFY")) if x is not None], default=None),
        "last_edit": last_edit,
        "last_verify": last_verify,
        "verification_after_last_edit": verification_after_last_edit,
        "subagent_count": counts.get("SUBAGENT_START", 0),
        "permission_request_count": counts.get("PERMISSION_REQUEST", 0),
        "permission_denied_count": counts.get("PERMISSION_DENIED", 0),
        "context_compaction_count": counts.get("CONTEXT_COMPACT", 0),
        "repair_count": counts.get("REPAIR", 0),
        "revert_count": counts.get("REVERT", 0),
        "tool_error_count": counts.get("TOOL_ERROR", 0),
        "stuck_loop_count": len(loops),
        "stuck_loops": loops,
        "oracle_success": oracle_success,
    }


def last_recoverable_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Use explicit deterministic recoverability markers only.

    Event records may carry a recoverable_after boolean from the hidden task
    oracle. Without such markers this remains UNKNOWN rather than guessed.
    """
    marked = [event for event in events if "recoverable_after" in event]
    if not marked:
        return {"status":"UNKNOWN","sequence":None,"reason":"no deterministic recoverability markers"}
    recoverable = [event for event in marked if bool(event.get("recoverable_after"))]
    if not recoverable:
        return {"status":"NONE","sequence":None,"reason":"oracle marked no recoverable state"}
    last = max(recoverable, key=lambda event: int(event.get("sequence", 0)))
    return {"status":"KNOWN","sequence":int(last["sequence"]),"raw_ref":last.get("raw_ref")}


def failure_replay_packet(
    *,
    task: dict[str, Any],
    subject: dict[str, Any],
    workspace_manifest: dict[str, Any],
    normalized_events: list[dict[str, Any]],
    oracle_result: dict[str, Any],
    candidate_mechanisms: list[str],
    successful_sibling_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    divergence = (
        first_divergence(successful_sibling_events, normalized_events)
        if successful_sibling_events is not None
        else {"diverged":None,"index":None}
    )
    packet = {
        "schema_version":1,
        "task_id":task.get("task_id") or task.get("case_id"),
        "task_hash":_stable_hash(task),
        "subject":deepcopy(subject),
        "workspace_manifest_hash":_stable_hash(workspace_manifest),
        "workspace_manifest":deepcopy(workspace_manifest),
        "trajectory_hash":_stable_hash(normalized_events),
        "normalized_events":deepcopy(normalized_events),
        "oracle_result":deepcopy(oracle_result),
        "candidate_mechanisms":list(candidate_mechanisms),
        "first_divergence":divergence,
        "last_recoverable_state":last_recoverable_state(normalized_events),
        "stuck_loops":detect_stuck_loops(normalized_events),
    }
    packet["replay_id"]="REPLAY-"+_stable_hash(packet)[:20]
    return packet


def classify_mechanism_evidence(
    *,
    observed_trials: int,
    independent_tasks: int,
    causal_interventions: int,
    generalized_families: int,
    rescue_rate: float,
    regression_rate: float,
    complexity_units: float,
) -> dict[str, Any]:
    if observed_trials <= 0:
        status="NOT_LOOKED_AT"
    elif independent_tasks < 2:
        status="OBSERVED"
    elif causal_interventions <= 0:
        status="REPLICATED"
    elif generalized_families < 2:
        status="CAUSAL"
    elif rescue_rate <= regression_rate:
        status="REJECT"
    elif rescue_rate - regression_rate >= 0.20 and complexity_units <= 3:
        status="HIGH_VALUE"
    else:
        status="GENERALIZED"
    clone_status = (
        "CLONE_CANDIDATE" if status in {"HIGH_VALUE","GENERALIZED","CAUSAL"} and rescue_rate > regression_rate
        else "MODIFY_CANDIDATE" if observed_trials > 0 and rescue_rate > 0
        else "REJECT" if status=="REJECT"
        else "UNKNOWN"
    )
    return {
        "status":status,
        "implementation_decision":clone_status,
        "observed_trials":int(observed_trials),
        "independent_tasks":int(independent_tasks),
        "causal_interventions":int(causal_interventions),
        "generalized_families":int(generalized_families),
        "rescue_rate":float(rescue_rate),
        "regression_rate":float(regression_rate),
        "complexity_units":float(complexity_units),
    }


def clone_blueprint_entry(
    mechanism: dict[str, Any],
    *,
    evidence: dict[str, Any],
    trigger: str,
    required_observable_state: str,
    selection_rule: str,
    action_policy: str,
    verification_rule: str,
    recovery_rule: str,
    stop_rule: str,
    evidence_to_retain: list[str],
) -> dict[str, Any]:
    return {
        "mechanism_id":mechanism["id"],
        "mechanism_name":mechanism["name"],
        "evidence":deepcopy(evidence),
        "contract":{
            "trigger":trigger,
            "required_observable_state":required_observable_state,
            "selection_routing_rule":selection_rule,
            "action_tool_policy":action_policy,
            "verification_rule":verification_rule,
            "recovery_rule":recovery_rule,
            "stop_rule":stop_rule,
            "evidence_to_retain":list(evidence_to_retain),
        },
    }
