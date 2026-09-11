from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from .coding_tomography import (
    MECHANISMS,
    classify_mechanism_evidence,
    first_divergence,
    mechanism_observable_signal,
    mechanism_registry,
    pathology_registry,
)
from .coding_tomography_interventions import (
    apply_intervention,
    selected_interventions,
)
from .coding_tomography_observers import prepare_claude_hook_observer
from .coding_tomography_runner import (
    materialize_workspace,
    run_subject_trial,
    sha256_file,
)
from .coding_tomography_tasks import build_builtin_task_bank


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.is_file():
        return rows
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(value))


def _git_seal(root: Path, message: str) -> None:
    subprocess.run(["git","add","-A"], cwd=root, check=True, capture_output=True, text=True)
    status = subprocess.run(
        ["git","status","--porcelain=v1"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        subprocess.run(
            ["git","commit","-m",message],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )


def _subject_version(subject: dict[str, Any]) -> dict[str, Any]:
    executable = str(subject.get("executable") or ("claude" if subject["name"] == "claude_code" else "codex"))
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            shell=False,
        )
        return {
            "name":subject["name"],
            "executable":executable,
            "returncode":result.returncode,
            "stdout":result.stdout.strip(),
            "stderr":result.stderr.strip(),
            "available":result.returncode == 0,
        }
    except Exception as exc:
        return {
            "name":subject["name"],
            "executable":executable,
            "returncode":None,
            "stdout":"",
            "stderr":"",
            "available":False,
            "error":f"{type(exc).__name__}: {exc}",
        }


def _config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_campaign_plan(config: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    root = dict(config.get("coding_tomography") or {})
    subjects = [dict(row) for row in root.get("subjects") or []]
    if not subjects:
        subjects = [
            {"name":"claude_code","executable":"claude","extra_args":[]},
            {"name":"codex","executable":"codex","extra_args":[]},
        ]
    native_repeats = int(root.get("native_repeats", 2))
    intervention_repeats = int(root.get("intervention_repeats", 1))
    include_common = bool(root.get("include_common_interventions", True))
    common_task_ids = {
        str(x) for x in root.get("common_intervention_task_ids") or []
    }
    task_filter = {str(x) for x in root.get("task_ids") or []}
    selected_tasks = [task for task in tasks if not task_filter or task["task_id"] in task_filter]
    observability_task_ids = {
        str(x) for x in root.get("observability_task_ids") or []
    }
    observability_subjects = {
        str(x) for x in root.get("observability_subjects") or ["claude_code"]
    }
    observability_repeats = int(root.get("observability_repeats", 1))
    resume_task_ids = {str(x) for x in root.get("resume_task_ids") or []}

    entries = []
    for subject in subjects:
        for task in selected_tasks:
            for repeat in range(native_repeats):
                entries.append({
                    "kind":"NATIVE_OBSERVATION",
                    "subject":subject,
                    "task_id":task["task_id"],
                    "repeat":repeat + 1,
                    "intervention":None,
                })
            include_common_for_task = (
                include_common
                and (not common_task_ids or task["task_id"] in common_task_ids)
            )
            for intervention in selected_interventions(
                task["task_id"],
                include_common=include_common_for_task,
            ):
                for repeat in range(intervention_repeats):
                    entries.append({
                        "kind":"CAUSAL_INTERVENTION",
                        "subject":subject,
                        "task_id":task["task_id"],
                        "repeat":repeat + 1,
                        "intervention":intervention,
                    })
            if (
                task["task_id"] in observability_task_ids
                and str(subject["name"]) in observability_subjects
            ):
                for repeat in range(observability_repeats):
                    entries.append({
                        "kind":"OBSERVABILITY_AUGMENTED",
                        "subject":subject,
                        "task_id":task["task_id"],
                        "repeat":repeat + 1,
                        "intervention":None,
                    })

    for subject in subjects:
        for task in selected_tasks:
            if task["task_id"] not in resume_task_ids:
                continue
            if not isinstance(task.get("resume_spec"), dict):
                raise ValueError(f"resume task lacks resume_spec: {task['task_id']}")
            entries.append({
                "kind":"RESUME_FRESH_CONTROL",
                "subject":subject,
                "task_id":task["task_id"],
                "repeat":1,
                "source_repeat":1,
                "intervention":None,
            })
            entries.append({
                "kind":"RESUME_CONTINUE",
                "subject":subject,
                "task_id":task["task_id"],
                "repeat":1,
                "source_repeat":1,
                "intervention":None,
            })

    max_sessions = int(root.get("max_sessions", 250))
    if len(entries) > max_sessions:
        raise ValueError(
            f"planned coding-tomography sessions {len(entries)} exceed max_sessions={max_sessions}"
        )
    return {
        "schema_version":1,
        "config_hash":_config_hash(config),
        "subjects":subjects,
        "task_count":len(selected_tasks),
        "task_ids":[task["task_id"] for task in selected_tasks],
        "native_repeats":native_repeats,
        "intervention_repeats":intervention_repeats,
        "include_common_interventions":include_common,
        "common_intervention_task_ids":sorted(common_task_ids),
        "observability_task_ids":sorted(observability_task_ids),
        "observability_subjects":sorted(observability_subjects),
        "observability_repeats":observability_repeats,
        "resume_task_ids":sorted(resume_task_ids),
        "planned_sessions":len(entries),
        "max_sessions":max_sessions,
        "entries":entries,
    }


def _trial_key(entry: dict[str, Any]) -> str:
    intervention = entry.get("intervention")
    if isinstance(intervention, dict):
        treatment = intervention.get("id")
    elif entry.get("kind") == "OBSERVABILITY_AUGMENTED":
        treatment = "observability"
    elif entry.get("kind") == "RESUME_FRESH_CONTROL":
        treatment = "resume-fresh"
    elif entry.get("kind") == "RESUME_CONTINUE":
        treatment = "resume-continue"
    else:
        treatment = "native"
    return (
        f"{_slug(entry['subject']['name'])}__{_slug(entry['task_id'])}"
        f"__{_slug(treatment)}__r{int(entry['repeat']):02d}"
    )


def _paired_intervention_results(
    plan: dict[str, Any],
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    by_key = {row["trial_key"]:row for row in summaries}
    native: dict[tuple[str,str], list[dict[str, Any]]] = defaultdict(list)
    treated: dict[tuple[str,str,str], list[dict[str, Any]]] = defaultdict(list)

    for entry in plan["entries"]:
        key = _trial_key(entry)
        summary = by_key.get(key)
        if summary is None:
            continue
        subject = str(entry["subject"]["name"])
        task_id = str(entry["task_id"])
        intervention = entry.get("intervention")
        if entry.get("kind") == "NATIVE_OBSERVATION":
            native[(subject,task_id)].append(summary)
        elif entry.get("kind") == "CAUSAL_INTERVENTION" and isinstance(intervention, dict):
            treated[(subject,task_id,str(intervention["id"]))].append(summary)

    results = {}
    for (subject,task_id,intervention_id), rows in sorted(treated.items()):
        controls = native.get((subject,task_id), [])
        if not controls:
            continue
        baseline_success = sum(bool(row["oracle_success"]) for row in controls) / len(controls)
        treatment_success = sum(bool(row["oracle_success"]) for row in rows) / len(rows)

        def mean_metric(group: list[dict[str, Any]], name: str) -> float | None:
            values = [
                row["metrics"].get(name)
                for row in group
                if isinstance(row.get("metrics",{}).get(name),(int,float))
                and not isinstance(row["metrics"].get(name),bool)
            ]
            return sum(float(v) for v in values) / len(values) if values else None

        entry = next(
            value for value in plan["entries"]
            if value["subject"]["name"] == subject
            and value["task_id"] == task_id
            and isinstance(value.get("intervention"),dict)
            and value["intervention"]["id"] == intervention_id
        )
        intervention = entry["intervention"]
        results[f"{subject}|{task_id}|{intervention_id}"] = {
            "subject":subject,
            "task_id":task_id,
            "intervention_id":intervention_id,
            "hypothesis":intervention.get("hypothesis"),
            "mechanisms":list(intervention.get("mechanisms") or []),
            "baseline_n":len(controls),
            "treatment_n":len(rows),
            "baseline_success_rate":baseline_success,
            "treatment_success_rate":treatment_success,
            "success_delta":treatment_success - baseline_success,
            "event_count_delta":(
                (mean_metric(rows,"event_count") or 0.0)
                - (mean_metric(controls,"event_count") or 0.0)
            ),
            "elapsed_s_delta":(
                (mean_metric(rows,"subject_elapsed_s") or 0.0)
                - (mean_metric(controls,"subject_elapsed_s") or 0.0)
            ),
            "verification_after_last_edit_baseline":sum(
                row["metrics"].get("verification_after_last_edit") is True for row in controls
            ) / len(controls),
            "verification_after_last_edit_treatment":sum(
                row["metrics"].get("verification_after_last_edit") is True for row in rows
            ) / len(rows),
        }
    return {"schema_version":1,"results":results}


def _mechanism_results(
    tasks: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    intervention_results: dict[str, Any],
) -> dict[str, Any]:
    task_map = {task["task_id"]: task for task in tasks}
    paired = list((intervention_results.get("results") or {}).values())
    subjects = sorted({
        str(row.get("subject"))
        for row in summaries
        if row.get("subject")
    })
    trajectory_cache: dict[str, list[dict[str, Any]]] = {}

    def events_for(summary: dict[str, Any]) -> list[dict[str, Any]]:
        key = str(summary["trial_key"])
        if key not in trajectory_cache:
            trajectory_cache[key] = _read_jsonl(
                Path(summary["evidence_root"]) / "normalized-native-trajectory.jsonl"
            )
        return trajectory_cache[key]

    def analyze(mid: str, subject: str | None) -> dict[str, Any]:
        native = [
            row for row in summaries
            if row.get("kind") == "NATIVE_OBSERVATION"
            and (subject is None or str(row.get("subject")) == subject)
        ]
        opportunities = [
            row for row in native
            if mid in (task_map.get(row["task_id"], {}).get("candidate_mechanisms") or [])
        ]
        signaled = [
            row for row in opportunities
            if mechanism_observable_signal(
                mid,
                events_for(row),
                dict(row.get("metrics") or {}),
            )
        ]
        signal_tasks = {str(row["task_id"]) for row in signaled}

        bundle_affected = [
            row for row in paired
            if mid in (row.get("mechanisms") or [])
            and (subject is None or str(row.get("subject")) == subject)
        ]
        identifiable = [
            row for row in bundle_affected
            if list(row.get("mechanisms") or []) == [mid]
            or (
                str(row.get("primary_mechanism") or "") == mid
                and bool(row.get("mechanism_isolation_confirmed"))
            )
        ]
        independent_identifiable = {
            (str(row.get("task_id")), str(row.get("intervention_id")))
            for row in identifiable
        }

        positive = [
            row for row in identifiable
            if float(row.get("success_delta", 0.0)) > 0.0
        ]
        negative = [
            row for row in identifiable
            if float(row.get("success_delta", 0.0)) < 0.0
        ]
        rescue_rate = (
            sum(max(0.0, float(row.get("success_delta", 0.0))) for row in identifiable)
            / len(identifiable)
            if identifiable else 0.0
        )
        regression_rate = (
            sum(max(0.0, -float(row.get("success_delta", 0.0))) for row in identifiable)
            / len(identifiable)
            if identifiable else 0.0
        )
        positive_families = {
            str(task_map.get(row["task_id"], {}).get("family"))
            for row in positive
            if task_map.get(row["task_id"])
        }
        evidence = classify_mechanism_evidence(
            opportunity_trials=len(opportunities),
            observed_trials=len(signaled),
            independent_tasks=len(signal_tasks),
            causal_interventions=len(independent_identifiable),
            generalized_families=len(positive_families),
            rescue_rate=rescue_rate,
            regression_rate=regression_rate,
            complexity_units=None,
        )

        def mean(rows: list[dict[str, Any]], name: str) -> float | None:
            values = [
                float(row[name])
                for row in rows
                if isinstance(row.get(name), (int, float))
                and not isinstance(row.get(name), bool)
            ]
            return sum(values) / len(values) if values else None

        verification_delta = (
            sum(
                float(row.get("verification_after_last_edit_treatment", 0.0))
                - float(row.get("verification_after_last_edit_baseline", 0.0))
                for row in identifiable
            ) / len(identifiable)
            if identifiable else None
        )
        bundle_directional = [
            row for row in bundle_affected
            if float(row.get("success_delta", 0.0)) != 0.0
        ]
        return {
            **evidence,
            "subject": subject or "combined",
            "opportunity_task_ids": sorted({
                str(row["task_id"]) for row in opportunities
            }),
            "observed_signal_task_ids": sorted(signal_tasks),
            "bundle_intervention_task_ids": sorted({
                str(row.get("task_id")) for row in bundle_affected
            }),
            "bundle_intervention_count": len({
                (str(row.get("task_id")), str(row.get("intervention_id")))
                for row in bundle_affected
            }),
            "bundle_directional_intervention_count": len(bundle_directional),
            "bundle_mean_success_delta": (
                sum(float(row.get("success_delta", 0.0)) for row in bundle_affected)
                / len(bundle_affected)
                if bundle_affected else None
            ),
            "identifiable_intervention_task_ids": sorted({
                str(row.get("task_id")) for row in identifiable
            }),
            "identifiable_intervention_count": len(independent_identifiable),
            "positive_identifiable_interventions": len(positive),
            "negative_identifiable_interventions": len(negative),
            "measured_mean_elapsed_delta_s": mean(identifiable, "elapsed_s_delta"),
            "measured_mean_event_count_delta": mean(identifiable, "event_count_delta"),
            "measured_verification_after_last_edit_delta": verification_delta,
            "inverted_implementation_complexity": "UNKNOWN_UNTIL_IMPLEMENTATION_PROTOTYPE",
            "attribution_rule": (
                "Multi-mechanism interventions contribute bundle evidence only. "
                "Individual causal promotion requires a single-mechanism or explicitly "
                "validated isolated intervention."
            ),
        }

    by_mechanism: dict[str, dict[str, Any]] = {}
    for mechanism in MECHANISMS:
        mid = mechanism["id"]
        by_subject = {
            subject: analyze(mid, subject)
            for subject in subjects
        }
        combined = analyze(mid, None)
        subject_net = {
            subject: float(row.get("net_effect", 0.0))
            for subject, row in by_subject.items()
        }
        positive_subjects = [
            subject for subject, value in subject_net.items() if value > 0.0
        ]
        negative_subjects = [
            subject for subject, value in subject_net.items() if value < 0.0
        ]
        if len(positive_subjects) >= 2 and not negative_subjects:
            source_pattern = "SHARED_POSITIVE"
        elif len(positive_subjects) == 1 and not negative_subjects:
            source_pattern = f"{positive_subjects[0].upper()}_POSITIVE_ONLY"
        elif positive_subjects and negative_subjects:
            source_pattern = "SUBJECTS_DIVERGE"
        elif negative_subjects and not positive_subjects:
            source_pattern = "SHARED_OR_SOURCE_SPECIFIC_NEGATIVE"
        else:
            source_pattern = "NO_IDENTIFIABLE_DIRECTIONAL_SIGNAL"

        by_mechanism[mid] = {
            "mechanism_id": mid,
            "mechanism_name": mechanism["name"],
            **combined,
            "combined": combined,
            "by_subject": by_subject,
            "source_pattern": source_pattern,
            "subject_net_effects": subject_net,
        }
    return {
        "schema_version": 3,
        "subjects": subjects,
        "mechanisms": by_mechanism,
        "causal_attribution_rule": (
            "Bundle-level interventions are not decomposed into individual mechanism "
            "causal claims without an isolating intervention."
        ),
    }


def _bundle_results(
    tasks: list[dict[str, Any]],
    intervention_results: dict[str, Any],
) -> dict[str, Any]:
    task_map = {task["task_id"]: task for task in tasks}
    grouped: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for row in (intervention_results.get("results") or {}).values():
        mechanisms = tuple(sorted(set(str(x) for x in (row.get("mechanisms") or []))))
        if not mechanisms:
            continue
        factor = str(row.get("intervention_id") or "unknown")
        grouped[(factor, mechanisms)].append(row)

    bundles = {}
    for (factor, mechanisms), rows in sorted(grouped.items()):
        positive = [row for row in rows if float(row.get("success_delta", 0.0)) > 0]
        negative = [row for row in rows if float(row.get("success_delta", 0.0)) < 0]
        subjects = sorted({str(row.get("subject")) for row in rows})
        task_ids = sorted({str(row.get("task_id")) for row in rows})
        families = sorted({
            str(task_map.get(str(row.get("task_id")), {}).get("family"))
            for row in rows
            if task_map.get(str(row.get("task_id")))
        })
        mean_delta = sum(float(row.get("success_delta", 0.0)) for row in rows) / len(rows)
        positive_tasks = {
            str(row.get("task_id"))
            for row in positive
        }
        negative_tasks = {
            str(row.get("task_id"))
            for row in negative
        }
        replicated = len(task_ids) >= 2 or len(subjects) >= 2
        generalized = len(families) >= 2 and len(positive_tasks) >= 2
        if mean_delta > 0 and generalized:
            status = "GENERALIZED_BUNDLE_GAIN"
            decision = "CLONE_BUNDLE_CANDIDATE"
        elif mean_delta > 0 and replicated:
            status = "REPLICATED_BUNDLE_GAIN"
            decision = "MODIFY_OR_CONFIRM_BUNDLE"
        elif mean_delta < 0 and replicated:
            status = "REPLICATED_BUNDLE_HARM"
            decision = "REJECT_BUNDLE"
        elif mean_delta != 0:
            status = "DIRECTIONAL_BUNDLE_SIGNAL"
            decision = "CONFIRM_BUNDLE"
        else:
            status = "BUNDLE_NULL_OR_MIXED"
            decision = "UNKNOWN"
        bundle_id = "BUNDLE-" + hashlib.sha256(
            json.dumps(
                {"factor": factor, "mechanisms": mechanisms},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:12]
        bundles[bundle_id] = {
            "bundle_id": bundle_id,
            "factor": factor,
            "mechanisms": list(mechanisms),
            "subjects": subjects,
            "task_ids": task_ids,
            "families": families,
            "n": len(rows),
            "positive_rows": len(positive),
            "negative_rows": len(negative),
            "positive_task_ids": sorted(positive_tasks),
            "negative_task_ids": sorted(negative_tasks),
            "mean_success_delta": mean_delta,
            "status": status,
            "implementation_decision": decision,
            "claim_boundary": (
                "Causal claim applies to the intervention bundle as a whole, not "
                "to each listed mechanism individually."
            ),
        }
    return {"schema_version": 1, "bundles": bundles}


def _behavior_atlas(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in summaries:
        if row.get("kind") != "NATIVE_OBSERVATION":
            continue
        groups[str(row["subject"])].append(row)

    result = {}
    for subject, rows in groups.items():
        success = [row for row in rows if row["oracle_success"]]
        result[subject] = {
            "trials":len(rows),
            "success_rate":len(success)/len(rows) if rows else 0.0,
            "mean_elapsed_s":sum(float(row["metrics"]["subject_elapsed_s"]) for row in rows)/len(rows) if rows else 0.0,
            "mean_event_count":sum(int(row["metrics"]["event_count"]) for row in rows)/len(rows) if rows else 0.0,
            "verification_after_last_edit_rate":sum(
                row["metrics"].get("verification_after_last_edit") is True for row in rows
            )/len(rows) if rows else 0.0,
            "stuck_loop_trial_rate":sum(
                int(row["metrics"].get("stuck_loop_count",0)) > 0 for row in rows
            )/len(rows) if rows else 0.0,
            "mean_subagent_count":sum(
                int(row["metrics"].get("subagent_count",0)) for row in rows
            )/len(rows) if rows else 0.0,
            "mean_context_compactions":sum(
                int(row["metrics"].get("context_compaction_count",0)) for row in rows
            )/len(rows) if rows else 0.0,
        }
    return {"schema_version":1,"subjects":result}


def _cross_subject_divergence(run_root: Path, summaries: list[dict[str, Any]]) -> dict[str, Any]:
    native = [
        row for row in summaries
        if row.get("kind") == "NATIVE_OBSERVATION"
    ]
    by_task_subject: dict[tuple[str,str], list[dict[str, Any]]] = defaultdict(list)
    for row in native:
        by_task_subject[(row["task_id"],row["subject"])].append(row)

    task_ids = sorted({row["task_id"] for row in native})
    result = {}
    for task_id in task_ids:
        claude = by_task_subject.get((task_id,"claude_code"),[])
        codex = by_task_subject.get((task_id,"codex"),[])
        if not claude or not codex:
            continue
        a = _read_jsonl(Path(claude[0]["evidence_root"]) / "normalized-native-trajectory.jsonl")
        b = _read_jsonl(Path(codex[0]["evidence_root"]) / "normalized-native-trajectory.jsonl")
        result[task_id] = first_divergence(a,b)
    return {"schema_version":1,"tasks":result}


def _causal_factor_registry(paired: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for key, result in sorted((paired.get("results") or {}).items()):
        mechanisms = list(result.get("mechanisms") or [])
        rows.append({
            "factor_key": key,
            **result,
            "mechanism_identifiability": (
                "SINGLE_MECHANISM_IDENTIFIABLE"
                if len(mechanisms) == 1
                else "MECHANISM_BUNDLE_NOT_INDIVIDUALLY_IDENTIFIABLE"
            ),
        })
    return {"schema_version":1,"factors":rows}


def _normalized_trajectory_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        root = Path(summary["evidence_root"])
        events = _read_jsonl(root / "normalized-trajectory.jsonl")
        for event in events:
            rows.append({
                "trial_key": summary["trial_key"],
                "task_id": summary["task_id"],
                "subject": summary["subject"],
                "kind": summary.get("kind"),
                "intervention_id": summary.get("intervention_id"),
                "repeat": summary.get("repeat"),
                "oracle_success": summary.get("oracle_success"),
                **event,
            })
    return rows


def _strategy_atlas(
    summaries: list[dict[str, Any]],
    event_types: set[str],
    *,
    native_only: bool = True,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for summary in summaries:
        if native_only and summary.get("kind") != "NATIVE_OBSERVATION":
            continue
        trajectory_name = (
            "normalized-native-trajectory.jsonl"
            if native_only
            else "normalized-trajectory.jsonl"
        )
        events = _read_jsonl(Path(summary["evidence_root"]) / trajectory_name)
        selected = [
            event for event in events
            if str(event.get("event_type") or "") in event_types
        ]
        result[summary["trial_key"]] = {
            "task_id": summary["task_id"],
            "subject": summary["subject"],
            "kind": summary.get("kind"),
            "intervention_id": summary.get("intervention_id"),
            "repeat": summary.get("repeat"),
            "oracle_success": summary.get("oracle_success"),
            "signature": [event.get("event_type") for event in selected],
            "events": selected,
        }
    return {
        "schema_version": 1,
        "native_only": native_only,
        "event_types": sorted(event_types),
        "trajectories": result,
    }


def _within_subject_failure_divergence(
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in summaries:
        groups[(str(row["subject"]), str(row["task_id"]))].append(row)

    results: dict[str, Any] = {}
    for (subject, task_id), rows in sorted(groups.items()):
        success = [row for row in rows if bool(row.get("oracle_success"))]
        failures = [row for row in rows if not bool(row.get("oracle_success"))]
        for failed in failures:
            same_kind = [
                row for row in success
                if row.get("kind") == failed.get("kind")
            ]
            sibling = same_kind[0] if same_kind else (success[0] if success else None)
            if sibling is None:
                results[failed["trial_key"]] = {
                    "subject": subject,
                    "task_id": task_id,
                    "failed_trial_key": failed["trial_key"],
                    "status": "NO_SUCCESSFUL_SIBLING",
                    "first_divergence": None,
                }
                continue
            successful_events = _read_jsonl(
                Path(sibling["evidence_root"]) / "normalized-native-trajectory.jsonl"
            )
            failed_events = _read_jsonl(
                Path(failed["evidence_root"]) / "normalized-native-trajectory.jsonl"
            )
            results[failed["trial_key"]] = {
                "subject": subject,
                "task_id": task_id,
                "failed_trial_key": failed["trial_key"],
                "successful_sibling_trial_key": sibling["trial_key"],
                "status": "COMPARED",
                "first_divergence": first_divergence(
                    successful_events,
                    failed_events,
                ),
            }
    return {"schema_version": 1, "failures": results}


def _false_success_registry(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for summary in summaries:
        metrics = summary.get("metrics") or {}
        visible_green = metrics.get("visible_checks_ok") is True
        hidden_bad = metrics.get("hidden_oracle_ok") is False
        response_bad = metrics.get("response_oracle_ok") is False
        if visible_green and (hidden_bad or response_bad):
            rows.append({
                "trial_key": summary["trial_key"],
                "task_id": summary["task_id"],
                "subject": summary["subject"],
                "kind": summary.get("kind"),
                "intervention_id": summary.get("intervention_id"),
                "visible_checks_ok": True,
                "hidden_oracle_ok": metrics.get("hidden_oracle_ok"),
                "response_oracle_ok": metrics.get("response_oracle_ok"),
                "oracle_success": summary.get("oracle_success"),
            })
    return {"schema_version": 1, "false_successes": rows}


def _pathology_ablation_results(
    tasks: list[dict[str, Any]],
    paired: dict[str, Any],
) -> dict[str, Any]:
    task_map = {str(task["task_id"]): task for task in tasks}
    rows = []
    for key, result in sorted((paired.get("results") or {}).items()):
        task = task_map.get(str(result.get("task_id")))
        if not task:
            continue
        if str(task.get("level")) != "P10":
            continue
        rows.append({
            "key": key,
            "task_id": task["task_id"],
            "pathology_ids": list(task.get("pathology_ids") or []),
            **result,
        })
    return {"schema_version": 1, "p10_ablation_results": rows}


def _mechanism_interaction_graph(
    tasks: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    paired: dict[str, Any],
) -> dict[str, Any]:
    native = [
        row for row in summaries
        if row.get("kind") == "NATIVE_OBSERVATION"
    ]
    nodes = {row["id"]: row["name"] for row in MECHANISMS}
    edge_rows: dict[tuple[str, str], dict[str, Any]] = {}

    for task in tasks:
        mechanisms = sorted(set(task.get("candidate_mechanisms") or []))
        if len(mechanisms) < 2:
            continue
        task_native = [
            row for row in native
            if row["task_id"] == task["task_id"]
        ]
        success_rate = (
            sum(bool(row["oracle_success"]) for row in task_native) / len(task_native)
            if task_native else None
        )
        for index, left in enumerate(mechanisms):
            for right in mechanisms[index + 1:]:
                key = (left, right)
                edge = edge_rows.setdefault(
                    key,
                    {
                        "left": left,
                        "right": right,
                        "cooccurring_task_ids": [],
                        "p10_task_ids": [],
                        "native_success_rates": [],
                        "directional_ablation_evidence": [],
                    },
                )
                edge["cooccurring_task_ids"].append(task["task_id"])
                if task.get("level") == "P10":
                    edge["p10_task_ids"].append(task["task_id"])
                if success_rate is not None:
                    edge["native_success_rates"].append({
                        "task_id": task["task_id"],
                        "success_rate": success_rate,
                    })

    for result in (paired.get("results") or {}).values():
        mechanisms = sorted(set(result.get("mechanisms") or []))
        if len(mechanisms) < 2:
            continue
        for index, left in enumerate(mechanisms):
            for right in mechanisms[index + 1:]:
                edge = edge_rows.get((left, right))
                if edge is None:
                    continue
                edge["directional_ablation_evidence"].append({
                    "task_id": result.get("task_id"),
                    "intervention_id": result.get("intervention_id"),
                    "success_delta": result.get("success_delta"),
                })

    edges = []
    for key, edge in sorted(edge_rows.items()):
        directional = [
            row for row in edge["directional_ablation_evidence"]
            if float(row.get("success_delta", 0.0)) != 0.0
        ]
        edges.append({
            **edge,
            "evidence_status": (
                "DIRECTIONAL_ABLATION_SIGNAL"
                if directional
                else "COOCCURRENCE_ONLY_NOT_SYNERGY_PROOF"
            ),
        })
    return {
        "schema_version": 1,
        "nodes": [{"id": mid, "name": name} for mid, name in sorted(nodes.items())],
        "edges": edges,
    }


def _behavioral_inference_registry(
    mechanisms: dict[str, Any],
) -> dict[str, Any]:
    rows = []
    for mid, row in sorted((mechanisms.get("mechanisms") or {}).items()):
        rows.append({
            "mechanism_id": mid,
            "mechanism_name": row.get("mechanism_name"),
            "status": row.get("status"),
            "implementation_decision": row.get("implementation_decision"),
            "net_effect": row.get("net_effect"),
            "looked_at_task_ids": row.get("looked_at_task_ids"),
            "intervention_count": row.get("intervention_count"),
            "claim_boundary": (
                "observable_or_causally_inferred_behavior_only; "
                "not hidden chain-of-thought or proprietary implementation"
            ),
        })
    return {"schema_version": 1, "inferences": rows}


def _observability_coverage(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for summary in summaries:
        coverage = dict(summary.get("channel_coverage") or {})
        rows.append({
            "trial_key":summary.get("trial_key"),
            "task_id":summary.get("task_id"),
            "subject":summary.get("subject"),
            "kind":summary.get("kind"),
            **coverage,
        })
    by_subject: dict[str, dict[str, Any]] = {}
    for subject in sorted({str(row.get("subject")) for row in rows if row.get("subject")}):
        group = [row for row in rows if str(row.get("subject")) == subject]
        native_total = sum(int(row.get("native_normalized_event_count",0)) for row in group)
        native_unknown = sum(int(row.get("native_unknown_event_count",0)) for row in group)
        observer_total = sum(int(row.get("observer_normalized_event_count",0)) for row in group)
        observer_unknown = sum(int(row.get("observer_unknown_event_count",0)) for row in group)
        by_subject[subject] = {
            "trials":len(group),
            "native_normalized_events":native_total,
            "native_unknown_events":native_unknown,
            "native_unknown_rate":native_unknown/native_total if native_total else None,
            "observer_normalized_events":observer_total,
            "observer_unknown_events":observer_unknown,
            "observer_unknown_rate":observer_unknown/observer_total if observer_total else None,
            "codex_rollout_rows":sum(int(row.get("codex_rollout_rows",0)) for row in group),
        }
    return {
        "schema_version":1,
        "trials":rows,
        "by_subject":by_subject,
        "rule":"Missing/unknown event coverage is evidence about instrumentation limits, not evidence that the subject omitted the behavior.",
    }


def _failure_registry(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for summary in summaries:
        replay_id = summary.get("failure_replay_id")
        if not replay_id:
            continue
        path = Path(summary["evidence_root"]) / "failure-replay.json"
        if not path.is_file():
            continue
        replay = _read_json(path)
        rows.append({
            "replay_id":replay_id,
            "task_id":summary["task_id"],
            "subject":summary["subject"],
            "kind":summary.get("kind"),
            "intervention_id":summary.get("intervention_id"),
            "trajectory_hash":replay.get("trajectory_hash"),
            "candidate_mechanisms":replay.get("candidate_mechanisms"),
            "evidence_path":str(path),
        })
    return {"schema_version":1,"failures":rows}


def _known_unknown(mechanisms: dict[str, Any]) -> dict[str, Any]:
    known, unknown, not_looked = [], [], []
    for mid,row in (mechanisms.get("mechanisms") or {}).items():
        status = row.get("status")
        if status in {"CAUSAL","GENERALIZED","HIGH_VALUE"}:
            known.append(mid)
        elif status == "NOT_LOOKED_AT":
            not_looked.append(mid)
        else:
            unknown.append(mid)
    return {
        "schema_version":1,
        "known":sorted(known),
        "unknown":sorted(unknown),
        "not_looked_at":sorted(not_looked),
        "rule":"Only causal/generalized/high-value mechanism evidence is promoted to KNOWN.",
    }


def _blueprint_and_rejects(mechanisms: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    clone, modify, reject, next_experiments = [], [], [], []
    for mid,row in sorted((mechanisms.get("mechanisms") or {}).items()):
        decision = row.get("implementation_decision")
        entry = {
            "mechanism_id":mid,
            "mechanism_name":row.get("mechanism_name"),
            "evidence_status":row.get("status"),
            "rescue_rate":row.get("rescue_rate"),
            "regression_rate":row.get("regression_rate"),
            "intervention_count":row.get("intervention_count"),
            "looked_at_task_ids":row.get("looked_at_task_ids"),
        }
        if decision == "CLONE_CANDIDATE":
            clone.append({
                **entry,
                "implementation_contract_status":"REQUIRES_EVIDENCE_DERIVED_PARAMETERIZATION",
                "rule":"Implement the observable mechanism, not proprietary internals; preserve trigger/action/verification/recovery/stop evidence.",
            })
        elif decision == "MODIFY_CANDIDATE":
            modify.append(entry)
            next_experiments.append({
                "mechanism_id":mid,
                "reason":"signal exists but evidence is not yet sufficient for direct cloning",
                "next_action":"replicate or ablate on additional independent task families",
            })
        elif decision == "REJECT":
            reject.append(entry)
        else:
            next_experiments.append({
                "mechanism_id":mid,
                "reason":"insufficient evidence",
                "next_action":"collect a targeted native observation or matched intervention",
            })
    return (
        {"schema_version":1,"clone_candidates":clone,"modify_candidates":modify},
        {"schema_version":1,"rejected":reject},
        {"schema_version":1,"experiments":next_experiments},
    )


def _privacy_scan_names(root: Path) -> dict[str, Any]:
    suspicious_names = []
    forbidden = {"auth.json",".env","credentials","credentials.json","id_rsa","id_ed25519"}
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower() in forbidden:
            suspicious_names.append(str(path))
    return {
        "schema_version":1,
        "forbidden_filename_hits":suspicious_names,
        "status":"CLEAN" if not suspicious_names else "REVIEW_REQUIRED",
    }


def run_coding_tomography_campaign(
    config: dict[str, Any],
    *,
    output_dir: str | Path,
    run_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    run_root = Path(output_dir).resolve() / "coding-tomography" / str(run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    fixture_root = run_root / "_sealed_task_bank"
    tasks = build_builtin_task_bank(fixture_root)
    task_map = {task["task_id"]:task for task in tasks}
    plan = build_campaign_plan(config,tasks)
    _write_json(run_root / "campaign-plan.json",plan)
    _write_json(run_root / "mechanism-registry.json",mechanism_registry())
    _write_json(run_root / "pathology-registry.json",pathology_registry())

    versions = [_subject_version(subject) for subject in plan["subjects"]]
    _write_json(run_root / "subject-versions.json",versions)

    if dry_run:
        result = {
            "schema_version":1,
            "run_id":run_id,
            "dry_run":True,
            "run_root":str(run_root),
            "planned_sessions":plan["planned_sessions"],
            "subjects":versions,
            "task_count":plan["task_count"],
        }
        _write_json(run_root / "dry-run.json",result)
        return result

    unavailable = [row for row in versions if not row.get("available")]
    if unavailable:
        raise RuntimeError(f"coding subjects unavailable: {unavailable}")

    root_config = dict(config.get("coding_tomography") or {})
    timeout_s = float(root_config.get("timeout_s",1800))
    summaries: list[dict[str, Any]] = []

    for ordinal, entry in enumerate(plan["entries"],start=1):
        task = task_map[entry["task_id"]]
        key = _trial_key(entry)
        workspace = run_root / "workspaces" / key
        evidence = run_root / "trials" / key
        kind = str(entry.get("kind") or "")
        resume_session_id = None
        trial_task = task

        if kind in {"RESUME_FRESH_CONTROL", "RESUME_CONTINUE"}:
            source = next(
                (
                    row for row in summaries
                    if row.get("kind") == "NATIVE_OBSERVATION"
                    and row.get("task_id") == task["task_id"]
                    and row.get("subject") == entry["subject"]["name"]
                    and int(row.get("repeat", 0)) == int(entry.get("source_repeat", 1))
                ),
                None,
            )
            if source is None:
                raise RuntimeError(f"resume source trial missing for {entry['subject']['name']} {task['task_id']}")
            source_workspace = run_root / "workspaces" / source["trial_key"]
            if kind == "RESUME_FRESH_CONTROL":
                materialize_workspace(source_workspace, workspace)
            else:
                workspace = source_workspace
                resume_session_id = str((source.get("metrics") or {}).get("session_id") or "")
                if not resume_session_id:
                    raise RuntimeError(f"source session id missing for resume trial {source['trial_key']}")

            resume_spec = dict(task.get("resume_spec") or {})
            mutation = {
                "id":"RESUME_PHASE2_MUTATION",
                "hypothesis":"matched phase-two state change for resume-vs-fresh continuity test",
                "mechanisms":list(resume_spec.get("candidate_mechanisms") or ["M20"]),
                "operations":list(resume_spec.get("operations") or []),
            }
            evidence.mkdir(parents=True, exist_ok=True)
            applied_resume = apply_intervention(
                workspace,
                mutation,
                subject=str(entry["subject"]["name"]),
            )
            _git_seal(workspace, "tomography phase-two resume baseline")
            _write_json(evidence / "resume-phase2-mutation.json", applied_resume)
            trial_task = deepcopy(task)
            trial_task["prompt"] = str(resume_spec["prompt"])
            trial_task["visible_checks"] = list(resume_spec.get("visible_checks") or [])
            trial_task["hidden_oracle_checks"] = list(resume_spec.get("hidden_oracle_checks") or [])
            trial_task["candidate_mechanisms"] = list(resume_spec.get("candidate_mechanisms") or ["M20"])
        else:
            materialize_workspace(task["workspace_template"],workspace)

        intervention = entry.get("intervention")
        applied = None
        observer_files: list[str] = []
        if isinstance(intervention,dict):
            applied = apply_intervention(
                workspace,
                intervention,
                subject=str(entry["subject"]["name"]),
            )
            _git_seal(workspace,f"tomography intervention baseline {intervention['id']}")
            _write_json(evidence / "intervention.json",applied)

        observer_record = None
        if (
            entry.get("kind") == "OBSERVABILITY_AUGMENTED"
            and str(entry["subject"]["name"]) == "claude_code"
        ):
            observer_record = prepare_claude_hook_observer(
                workspace=workspace,
                evidence_root=evidence,
            )
            observer_files.append(observer_record["event_log_path"])
            _git_seal(workspace, "tomography logging-only observer baseline")
            _write_json(evidence / "observer-provenance.json", observer_record)

        summary = run_subject_trial(
            task=trial_task,
            subject=entry["subject"],
            workspace=workspace,
            evidence_root=evidence,
            timeout_s=timeout_s,
            observer_event_files=observer_files,
            rollout_path_template=entry["subject"].get("rollout_path_template"),
            auto_codex_rollout_lookup=(
                entry.get("kind") == "OBSERVABILITY_AUGMENTED"
                and str(entry["subject"]["name"]) == "codex"
            ),
            resume_session_id=resume_session_id,
        )
        summary.update({
            "trial_key":key,
            "ordinal":ordinal,
            "kind":entry["kind"],
            "repeat":entry["repeat"],
            "intervention_id":intervention.get("id") if isinstance(intervention,dict) else None,
            "intervention_hypothesis":intervention.get("hypothesis") if isinstance(intervention,dict) else None,
            "observer_mode": observer_record.get("mode") if isinstance(observer_record, dict) else None,
            "source_trial_key": source.get("trial_key") if kind in {"RESUME_FRESH_CONTROL","RESUME_CONTINUE"} else None,
        })
        _write_json(evidence / "trial-summary.json",summary)
        summaries.append(summary)
        _write_json(run_root / "progress.json",{
            "completed":ordinal,
            "total":plan["planned_sessions"],
            "last_trial_key":key,
        })

    _write_json(run_root / "trial-index.json",{"schema_version":1,"trials":summaries})
    behavior = _behavior_atlas(summaries)
    paired = _paired_intervention_results(plan,summaries)
    mechanisms = _mechanism_results(tasks,summaries,paired)
    bundles = _bundle_results(tasks, paired)
    failures = _failure_registry(summaries)
    divergence = _cross_subject_divergence(run_root,summaries)
    known_unknown = _known_unknown(mechanisms)
    blueprint,rejects,next_experiments = _blueprint_and_rejects(mechanisms)

    normalized_rows = _normalized_trajectory_rows(summaries)
    _write_jsonl(run_root / "normalized-trajectories.jsonl", normalized_rows)
    _write_json(run_root / "native-behavior-atlas.json",behavior)
    _write_json(run_root / "search-strategy-atlas.json", _strategy_atlas(summaries, {"SEARCH","FILE_READ"}))
    _write_json(run_root / "edit-strategy-atlas.json", _strategy_atlas(summaries, {"FILE_WRITE","FILE_EDIT","REVERT"}))
    _write_json(run_root / "verification-strategy-atlas.json", _strategy_atlas(summaries, {"TEST","LINT","BUILD","VERIFY"}))
    _write_json(run_root / "failure-recovery-atlas.json", _strategy_atlas(summaries, {"TOOL_ERROR","REPAIR","REVERT","TEST","VERIFY"}))
    _write_json(run_root / "stop-rule-atlas.json", _strategy_atlas(summaries, {"FINAL_RESPONSE","SESSION_STOP","TEST","VERIFY"}))
    _write_json(run_root / "context-memory-atlas.json", _strategy_atlas(summaries, {"CONTEXT_LOAD","CONTEXT_COMPACT","RESUME","CHECKPOINT","REASONING_SUMMARY"}))
    _write_json(run_root / "delegation-parallelism-atlas.json", _strategy_atlas(summaries, {"SUBAGENT_START","SUBAGENT_RESULT"}))
    _write_json(run_root / "permissions-sandbox-atlas.json", _strategy_atlas(summaries, {"PERMISSION_REQUEST","PERMISSION_DENIED","APPROVAL"}))
    _write_json(run_root / "instruction-precedence-atlas.json", _strategy_atlas(summaries, {"CONTEXT_LOAD","SEARCH","FILE_READ"}))
    _write_json(run_root / "causal-intervention-results.json",paired)
    _write_json(run_root / "causal-factor-registry.json", _causal_factor_registry(paired))
    _write_json(run_root / "pathology-ablation-results.json", _pathology_ablation_results(tasks, paired))
    _write_json(run_root / "mechanism-value-per-cost.json",mechanisms)
    _write_json(run_root / "mechanism-bundle-value.json",bundles)
    _write_json(run_root / "mechanism-interaction-graph.json", _mechanism_interaction_graph(tasks, summaries, paired))
    _write_json(run_root / "behavioral-inference-registry.json", _behavioral_inference_registry(mechanisms))
    _write_json(run_root / "observability-coverage.json", _observability_coverage(summaries))
    _write_json(run_root / "observer-strategy-atlas.json", _strategy_atlas(summaries, {
        "CONTEXT_LOAD","CONTEXT_COMPACT","SEARCH","FILE_READ","FILE_WRITE","FILE_EDIT",
        "COMMAND","TEST","LINT","BUILD","WEB","MCP","SUBAGENT_START","SUBAGENT_RESULT",
        "PERMISSION_REQUEST","PERMISSION_DENIED","TOOL_ERROR","TOOL_RESULT",
        "REASONING_SUMMARY","FINAL_RESPONSE","SESSION_STOP"
    }, native_only=False))
    _write_json(run_root / "failure-first-divergence-atlas.json", _within_subject_failure_divergence(summaries))
    _write_json(run_root / "false-success-registry.json", _false_success_registry(summaries))
    _write_json(run_root / "failure-replay-registry.json",failures)
    _write_json(run_root / "first-divergence-atlas.json",divergence)
    _write_json(run_root / "known-unknown-not-looked-at.json",known_unknown)
    _write_json(run_root / "inverted-clone-blueprint.json",blueprint)
    _write_json(run_root / "inverted-reject-list.json",rejects)
    _write_json(run_root / "next-tier-experiments.json",next_experiments)
    privacy = _privacy_scan_names(run_root)
    _write_json(run_root / "privacy-scan.json",privacy)

    final_files = [
        path for path in run_root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS.json"
    ]
    hashes = [
        {"path":path.name,"bytes":path.stat().st_size,"sha256":sha256_file(path)}
        for path in sorted(final_files)
    ]
    _write_json(run_root / "SHA256SUMS.json",{"artifacts":hashes})

    result = {
        "schema_version":1,
        "run_id":run_id,
        "dry_run":False,
        "run_root":str(run_root),
        "planned_sessions":plan["planned_sessions"],
        "completed_sessions":len(summaries),
        "native_behavior_atlas":str(run_root / "native-behavior-atlas.json"),
        "causal_intervention_results":str(run_root / "causal-intervention-results.json"),
        "clone_blueprint":str(run_root / "inverted-clone-blueprint.json"),
        "failure_replay_registry":str(run_root / "failure-replay-registry.json"),
        "privacy_status":privacy["status"],
    }
    _write_json(run_root / "campaign-summary.json",result)
    return result
