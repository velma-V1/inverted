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
from .coding_tomography_mcp import (
    mcp_server_readiness,
    mcp_tool_was_called,
    prepare_mcp_probe,
)
from .coding_tomography_observers import prepare_claude_hook_observer
from .coding_tomography_runner import (
    finalize_trial_evidence,
    materialize_workspace,
    run_subject_trial,
    sha256_file,
)
from .coding_tomography_research import (
    aggregate_compute_cost,
    all_quota_limited_exhausted,
    build_exposure_index,
    build_shadow_escalation_queue,
    campaign_completion_record,
    quota_limited_subject_names,
    research_contract,
    run_shadow_observer,
)
from .coding_tomography_tasks import build_builtin_task_bank


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
                + "\n"
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
    name = str(subject["name"])
    adapter = str(subject.get("adapter") or subject.get("harness") or name)
    executable = str(
        subject.get("executable")
        or ("claude" if adapter == "claude_code" else "codex")
    )

    def probe(*args: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [executable, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                shell=False,
            )
            return {
                "returncode":result.returncode,
                "stdout":result.stdout,
                "stderr":result.stderr,
                "ok":result.returncode == 0,
            }
        except Exception as exc:
            return {
                "returncode":None,
                "stdout":"",
                "stderr":"",
                "ok":False,
                "error":f"{type(exc).__name__}: {exc}",
            }

    version = probe("--version")
    row: dict[str, Any] = {
        "name":name,
        "adapter":adapter,
        "executable":executable,
        "returncode":version.get("returncode"),
        "stdout":str(version.get("stdout") or "").strip(),
        "stderr":str(version.get("stderr") or "").strip(),
        "available":bool(version.get("ok")),
        "required_missing":[],
        "capabilities":{},
    }
    if not row["available"]:
        if version.get("error"):
            row["error"] = version["error"]
        return row

    missing: list[str] = []
    if adapter == "claude_code":
        help_result = probe("--help")
        text = (
            str(help_result.get("stdout") or "")
            + "\n"
            + str(help_result.get("stderr") or "")
        ).lower()
        requirements = {
            "stream_json":"--output-format",
            "verbose":"--verbose",
            "resume":"--resume",
            "mcp_config":"--mcp-config",
        }
        capabilities = {
            key: token in text
            for key, token in requirements.items()
        }
        missing.extend(key for key, ok in capabilities.items() if not ok)
        row["capabilities"] = capabilities
        row["help_returncode"] = help_result.get("returncode")
    elif adapter == "codex":
        exec_help = probe("exec", "--help")
        resume_help = probe("exec", "resume", "--help")
        text = (
            str(exec_help.get("stdout") or "")
            + "\n"
            + str(exec_help.get("stderr") or "")
        ).lower()
        capabilities = {
            "json_events":"--json" in text,
            "cwd":("--cd" in text or "-c" in text),
            "config_override":"--config" in text,
            "resume":bool(resume_help.get("ok")),
        }
        missing.extend(key for key, ok in capabilities.items() if not ok)
        row["capabilities"] = capabilities
        row["help_returncode"] = exec_help.get("returncode")
        row["resume_help_returncode"] = resume_help.get("returncode")
    else:
        missing.append("unsupported_subject")

    row["required_missing"] = sorted(missing)
    return row


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
    mcp_task_ids = {str(x) for x in root.get("mcp_task_ids") or []}
    replay_reserve_slots = max(0, int(root.get("replay_reserve_slots", 0)))

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

    for subject in subjects:
        for task in selected_tasks:
            if task["task_id"] not in mcp_task_ids:
                continue
            entries.append({
                "kind":"MCP_TREATMENT",
                "subject":subject,
                "task_id":task["task_id"],
                "repeat":1,
                "intervention":None,
            })

    max_sessions = int(root.get("max_sessions", 250))
    scheduled_sessions = len(entries)
    planned_sessions = scheduled_sessions + replay_reserve_slots
    if planned_sessions > max_sessions:
        raise ValueError(
            f"planned coding-tomography sessions {planned_sessions} exceed max_sessions={max_sessions}"
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
        "mcp_task_ids":sorted(mcp_task_ids),
        "replay_reserve_slots":replay_reserve_slots,
        "scheduled_sessions":scheduled_sessions,
        "planned_sessions":planned_sessions,
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
    elif entry.get("kind") == "MCP_TREATMENT":
        treatment = "mcp-treatment"
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


def _resume_continuity_results(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in summaries:
        kind = str(row.get("kind") or "")
        if kind not in {"RESUME_FRESH_CONTROL", "RESUME_CONTINUE"}:
            continue
        groups[(str(row.get("subject")), str(row.get("task_id")))][kind] = row

    results: dict[str, Any] = {}
    for (subject, task_id), arms in sorted(groups.items()):
        fresh = arms.get("RESUME_FRESH_CONTROL")
        resumed = arms.get("RESUME_CONTINUE")
        if fresh is None or resumed is None:
            continue

        fresh_before = _read_json(Path(fresh["evidence_root"]) / "workspace-before.json")
        resumed_before = _read_json(Path(resumed["evidence_root"]) / "workspace-before.json")
        fresh_hash = str(fresh_before.get("manifest_sha256") or "")
        resumed_hash = str(resumed_before.get("manifest_sha256") or "")
        identical_state = bool(fresh_hash and fresh_hash == resumed_hash)

        def metric(row: dict[str, Any], name: str) -> float:
            value = (row.get("metrics") or {}).get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            return 0.0

        key = f"{subject}|{task_id}|SESSION_CONTINUITY"
        results[key] = {
            "subject": subject,
            "task_id": task_id,
            "intervention_id": "SESSION_CONTINUITY",
            "hypothesis": (
                "Persisted session context changes phase-two capability or efficiency "
                "relative to a fresh session given identical post-phase-one repository state."
            ),
            "mechanisms": ["M20"],
            "primary_mechanism": "M20",
            "mechanism_isolation_confirmed": identical_state,
            "baseline_arm": "RESUME_FRESH_CONTROL",
            "treatment_arm": "RESUME_CONTINUE",
            "baseline_n": 1,
            "treatment_n": 1,
            "baseline_success_rate": float(bool(fresh.get("oracle_success"))),
            "treatment_success_rate": float(bool(resumed.get("oracle_success"))),
            "success_delta": (
                float(bool(resumed.get("oracle_success")))
                - float(bool(fresh.get("oracle_success")))
            ),
            "event_count_delta": metric(resumed, "event_count") - metric(fresh, "event_count"),
            "elapsed_s_delta": metric(resumed, "subject_elapsed_s") - metric(fresh, "subject_elapsed_s"),
            "verification_after_last_edit_baseline": float(
                (fresh.get("metrics") or {}).get("verification_after_last_edit") is True
            ),
            "verification_after_last_edit_treatment": float(
                (resumed.get("metrics") or {}).get("verification_after_last_edit") is True
            ),
            "fresh_start_manifest_sha256": fresh_hash,
            "resumed_start_manifest_sha256": resumed_hash,
            "matched_start_state": identical_state,
            "fresh_trial_key": fresh.get("trial_key"),
            "resumed_trial_key": resumed.get("trial_key"),
            "source_trial_key": resumed.get("source_trial_key"),
        }
    return {
        "schema_version": 1,
        "results": results,
        "causal_claim_gate": "matched_start_state must be true for M20 isolation",
    }


def _mcp_escalation_results(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    native: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    treatments: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in summaries:
        key = (str(row.get("subject")), str(row.get("task_id")))
        if row.get("kind") == "NATIVE_OBSERVATION":
            native[key].append(row)
        elif row.get("kind") == "MCP_TREATMENT":
            treatments[key].append(row)

    results: dict[str, Any] = {}
    for key, treated in sorted(treatments.items()):
        controls = native.get(key) or []
        if not controls or not treated:
            continue
        subject, task_id = key
        treatment = treated[0]
        treatment_probe = dict(treatment.get("mcp_probe") or {})
        native_manifest = _read_json(
            Path(controls[0]["evidence_root"]) / "workspace-before.json"
        ).get("manifest_sha256")
        treatment_manifest = _read_json(
            Path(treatment["evidence_root"]) / "workspace-before.json"
        ).get("manifest_sha256")
        matched_state = bool(native_manifest and native_manifest == treatment_manifest)
        ready = bool(treatment_probe.get("ready"))
        isolation = bool(matched_state and ready)

        baseline_success = (
            sum(bool(row.get("oracle_success")) for row in controls) / len(controls)
        )
        treatment_success = float(bool(treatment.get("oracle_success")))

        def mean_metric(rows: list[dict[str, Any]], name: str) -> float:
            values = [
                float((row.get("metrics") or {}).get(name))
                for row in rows
                if isinstance((row.get("metrics") or {}).get(name), (int, float))
                and not isinstance((row.get("metrics") or {}).get(name), bool)
            ]
            return sum(values) / len(values) if values else 0.0

        row_key = f"{subject}|{task_id}|MCP_AVAILABILITY"
        results[row_key] = {
            "subject":subject,
            "task_id":task_id,
            "intervention_id":"MCP_AVAILABILITY",
            "hypothesis":"Availability of a deterministic authoritative MCP reference tool changes tool-escalation behavior and task success.",
            "mechanisms":["M27"],
            "primary_mechanism":"M27",
            "mechanism_isolation_confirmed":isolation,
            "baseline_n":len(controls),
            "treatment_n":1,
            "baseline_success_rate":baseline_success,
            "treatment_success_rate":treatment_success,
            "success_delta":treatment_success - baseline_success,
            "event_count_delta":(
                float((treatment.get("metrics") or {}).get("event_count", 0.0))
                - mean_metric(controls, "event_count")
            ),
            "elapsed_s_delta":(
                float((treatment.get("metrics") or {}).get("subject_elapsed_s", 0.0))
                - mean_metric(controls, "subject_elapsed_s")
            ),
            "verification_after_last_edit_baseline":(
                sum((row.get("metrics") or {}).get("verification_after_last_edit") is True for row in controls)
                / len(controls)
            ),
            "verification_after_last_edit_treatment":float(
                (treatment.get("metrics") or {}).get("verification_after_last_edit") is True
            ),
            "matched_start_state":matched_state,
            "mcp_ready":ready,
            "mcp_tool_called":bool(treatment_probe.get("tool_called")),
            "mcp_observed_methods":list(treatment_probe.get("observed_methods") or []),
            "attribution_gate":"M27 isolation requires identical start manifest and observable MCP initialization plus tools/list.",
        }
    return {"schema_version":1,"results":results}


def _safe_replay_context(source: dict[str, Any]) -> dict[str, Any]:
    root = Path(source["evidence_root"])
    visible = _read_json(root / "visible-check-results.json") if (root / "visible-check-results.json").is_file() else []
    git_after = _read_json(root / "git-after.json") if (root / "git-after.json").is_file() else {}
    events = _read_jsonl(root / "normalized-native-trajectory.jsonl")
    final_path = root / "observable-final-response.txt"
    final_text = final_path.read_text(encoding="utf-8", errors="replace") if final_path.is_file() else ""

    safe_events = [
        {
            "sequence":row.get("sequence"),
            "event_type":row.get("event_type"),
            "observable_fields":row.get("observable_fields") or {},
        }
        for row in events
    ]
    safe_visible = [
        {
            "id":row.get("id"),
            "ok":row.get("ok"),
            "returncode":row.get("returncode"),
            "stdout":str(row.get("stdout") or "")[:4000],
            "stderr":str(row.get("stderr") or "")[:4000],
            "timeout":row.get("timeout"),
            "error":row.get("error"),
        }
        for row in visible
    ]
    return {
        "prior_acceptance_status":"FAILED",
        "visible_checks":safe_visible,
        "observable_trajectory":safe_events[:250],
        "prior_git_status":str(git_after.get("status") or "")[:4000],
        "prior_git_diff":str(git_after.get("diff") or "")[:10000],
        "prior_final_response":final_text[:6000],
        "hidden_oracle_content_included":False,
    }


def _replay_prompt(task: dict[str, Any], source: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    context = _safe_replay_context(source)
    payload = json.dumps(context, indent=2, sort_keys=True, ensure_ascii=False)
    prompt = (
        str(task["prompt"])
        + "\n\n<prior_attempt_evidence>\n"
        + "A previous attempt on this exact initial repository state did not pass acceptance verification. "
        + "Use the observable evidence below to avoid repeating the same failure. "
        + "No hidden expected answer or hidden-oracle content is included.\n"
        + payload
        + "\n</prior_attempt_evidence>\n"
    )
    return prompt, context


def _select_replay_sources(
    summaries: list[dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    slots: int,
) -> list[dict[str, Any]]:
    failed = [
        row for row in summaries
        if row.get("kind") == "NATIVE_OBSERVATION"
        and not bool(row.get("oracle_success"))
        and bool(
            (tasks.get(str(row.get("task_id"))) or {}).get(
                "replay_eligible",
                True,
            )
        )
    ]
    def score(row: dict[str, Any]) -> tuple[int, int, str, str]:
        task = tasks.get(str(row.get("task_id"))) or {}
        p10 = 1 if str(task.get("level")) == "P10" else 0
        visible_green = 1 if (row.get("metrics") or {}).get("visible_checks_ok") is True else 0
        return (-p10, -visible_green, str(row.get("task_id")), str(row.get("subject")))

    selected: list[dict[str, Any]] = []
    used_tasks: set[str] = set()
    used_pairs: set[tuple[str, str]] = set()
    for row in sorted(failed, key=score):
        pair = (str(row.get("task_id")), str(row.get("subject")))
        if pair in used_pairs:
            continue
        if str(row.get("task_id")) in used_tasks and len(used_tasks) < slots:
            continue
        selected.append(row)
        used_pairs.add(pair)
        used_tasks.add(str(row.get("task_id")))
        if len(selected) >= slots:
            break
    if len(selected) < slots:
        for row in sorted(failed, key=score):
            pair = (str(row.get("task_id")), str(row.get("subject")))
            if pair in used_pairs:
                continue
            selected.append(row)
            used_pairs.add(pair)
            if len(selected) >= slots:
                break
    return selected


def _run_replay_reserve(
    *,
    summaries: list[dict[str, Any]],
    task_map: dict[str, dict[str, Any]],
    subjects: list[dict[str, Any]],
    run_root: Path,
    timeout_s: float,
    slots: int,
    ordinal_start: int,
    planned_total: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected = _select_replay_sources(summaries, task_map, slots)
    subject_map = {str(row["name"]):row for row in subjects}
    replay_rows: list[dict[str, Any]] = []
    effects: dict[str, Any] = {}
    quota_terminal_rows: list[dict[str, Any]] = []
    quota_exhausted_subjects: set[str] = set()

    for offset, source in enumerate(selected, start=1):
        if str(source.get("subject")) in quota_exhausted_subjects:
            continue
        task = task_map[str(source["task_id"])]
        subject = deepcopy(subject_map[str(source["subject"])])
        key = (
            f"{_slug(str(source['subject']))}__{_slug(str(source['task_id']))}"
            f"__failure-replay__s{offset:02d}"
        )
        workspace = run_root / "workspaces" / key
        evidence = run_root / "trials" / key
        materialize_workspace(task["workspace_template"], workspace)

        prompt, replay_context = _replay_prompt(task, source)
        replay_task = deepcopy(task)
        replay_task["prompt"] = prompt
        replay_task["candidate_mechanisms"] = ["M36"]
        evidence.mkdir(parents=True, exist_ok=True)
        _write_json(evidence / "replay-source.json", {
            "source_trial_key":source.get("trial_key"),
            "source_task_id":source.get("task_id"),
            "source_subject":source.get("subject"),
            "context":replay_context,
        })

        summary = run_subject_trial(
            task=replay_task,
            subject=subject,
            workspace=workspace,
            evidence_root=evidence,
            timeout_s=timeout_s,
        )
        ordinal = ordinal_start + offset
        summary.update({
            "trial_key":key,
            "ordinal":ordinal,
            "kind":"FAILURE_REPLAY_TREATMENT",
            "repeat":1,
            "intervention_id":"EXACT_FAILURE_REPLAY",
            "intervention_hypothesis":"Observable prior-failure evidence improves recovery when replayed from the exact original initial state.",
            "source_trial_key":source.get("trial_key"),
        })
        _write_json(evidence / "trial-summary.json", summary)
        finalize_trial_evidence(evidence)
        if summary.get("trial_status") == "PROVIDER_QUOTA_EXHAUSTED":
            quota_exhausted_subjects.add(str(source.get("subject")))
            quota_terminal_rows.append(summary)
            continue
        replay_rows.append(summary)

        source_before = _read_json(Path(source["evidence_root"]) / "workspace-before.json")
        replay_before = _read_json(evidence / "workspace-before.json")
        matched = (
            source_before.get("manifest_sha256")
            and source_before.get("manifest_sha256") == replay_before.get("manifest_sha256")
        )
        effect_key = f"{source['subject']}|{source['task_id']}|EXACT_FAILURE_REPLAY|{offset}"
        effects[effect_key] = {
            "subject":source["subject"],
            "task_id":source["task_id"],
            "intervention_id":f"EXACT_FAILURE_REPLAY_{offset:02d}",
            "hypothesis":"Failure snapshot/replay can recover a previously failed exact task from the same initial state.",
            "mechanisms":["M36"],
            "primary_mechanism":"M36",
            "mechanism_isolation_confirmed":bool(matched),
            "baseline_n":1,
            "treatment_n":1,
            "baseline_success_rate":0.0,
            "treatment_success_rate":float(bool(summary.get("oracle_success"))),
            "success_delta":float(bool(summary.get("oracle_success"))),
            "event_count_delta":(
                float((summary.get("metrics") or {}).get("event_count",0.0))
                - float((source.get("metrics") or {}).get("event_count",0.0))
            ),
            "elapsed_s_delta":(
                float((summary.get("metrics") or {}).get("subject_elapsed_s",0.0))
                - float((source.get("metrics") or {}).get("subject_elapsed_s",0.0))
            ),
            "verification_after_last_edit_baseline":float(
                (source.get("metrics") or {}).get("verification_after_last_edit") is True
            ),
            "verification_after_last_edit_treatment":float(
                (summary.get("metrics") or {}).get("verification_after_last_edit") is True
            ),
            "matched_start_state":bool(matched),
            "source_trial_key":source.get("trial_key"),
            "replay_trial_key":key,
            "hidden_oracle_content_included":False,
        }
        _write_json(run_root / "progress.json", {
            "completed":ordinal,
            "total":planned_total,
            "last_trial_key":key,
        })

    return replay_rows, {
        "schema_version":1,
        "reserved_slots":slots,
        "used_slots":len(replay_rows),
        "unused_slots":max(0, slots - len(replay_rows)),
        "results":effects,
        "selection_rule":"failed native trials; prioritize P10 and visible-green false-success; distinct tasks first",
        "hidden_oracle_content_in_replay_prompt":False,
        "quota_exhausted_subjects":sorted(quota_exhausted_subjects),
        "quota_terminal_trials":quota_terminal_rows,
    }


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


def _pathology_compounds_artifact() -> dict[str, Any]:
    registry = pathology_registry()
    compounds = list(registry.get("compounds") or [])
    rows = []
    for compound in compounds:
        components = list(compound.get("components") or [])
        rows.append({
            **compound,
            "component_count":len(components),
            "ablation_plan":[
                {
                    "ablation_id":f"{compound['id']}-A{index + 1:02d}",
                    "removed_component":component,
                    "active_components":[x for x in components if x != component],
                }
                for index, component in enumerate(components)
            ],
        })
    return {
        "schema_version":1,
        "compounds":rows,
        "rule":"Compound difficulty never licenses component-level causal attribution without ablation evidence.",
    }


def _last_recoverable_state_atlas(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for summary in summaries:
        replay_path = Path(summary["evidence_root"]) / "failure-replay.json"
        if not replay_path.is_file():
            continue
        replay = _read_json(replay_path)
        rows.append({
            "trial_key":summary.get("trial_key"),
            "task_id":summary.get("task_id"),
            "subject":summary.get("subject"),
            "kind":summary.get("kind"),
            "oracle_success":summary.get("oracle_success"),
            "replay_id":replay.get("replay_id"),
            "last_recoverable_state":replay.get("last_recoverable_state"),
            "trajectory_hash":replay.get("trajectory_hash"),
        })
    known = [
        row for row in rows
        if isinstance(row.get("last_recoverable_state"), dict)
        and row["last_recoverable_state"].get("status") == "KNOWN"
    ]
    return {
        "schema_version":1,
        "failure_trials":rows,
        "known_count":len(known),
        "unknown_or_none_count":len(rows) - len(known),
        "rule":"Recoverability is reported only from deterministic oracle markers; absent markers remain UNKNOWN.",
    }


def _strategy_reset_events(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Observable reset signals only; never infer private strategy changes."""
    rows: list[dict[str, Any]] = []
    reset_types = {"REVERT","RESUME","CHECKPOINT","PLAN_UPDATE"}
    failure_types = {"TOOL_ERROR","TEST"}
    for summary in summaries:
        events = _read_jsonl(
            Path(summary["evidence_root"]) / "normalized-native-trajectory.jsonl"
        )
        recent_failure = False
        for event in events:
            event_type = str(event.get("event_type") or "")
            if event_type == "TOOL_ERROR":
                recent_failure = True
            elif event_type == "TEST":
                fields = dict(event.get("observable_fields") or {})
                exit_code = fields.get("exit_code")
                if isinstance(exit_code, int) and exit_code != 0:
                    recent_failure = True
            if event_type in reset_types and recent_failure:
                rows.append({
                    "trial_key":summary.get("trial_key"),
                    "task_id":summary.get("task_id"),
                    "subject":summary.get("subject"),
                    "kind":summary.get("kind"),
                    "sequence":event.get("sequence"),
                    "event_type":event_type,
                    "raw_ref":event.get("raw_ref"),
                    "observable_fields":event.get("observable_fields"),
                    "evidence_status":"OBSERVED_RESET_SIGNAL_AFTER_FAILURE",
                })
                recent_failure = False
    return rows


def _stuck_loop_registry(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for summary in summaries:
        metrics = dict(summary.get("metrics") or {})
        loops = list(metrics.get("stuck_loops") or [])
        if not loops:
            continue
        rows.append({
            "trial_key":summary.get("trial_key"),
            "task_id":summary.get("task_id"),
            "subject":summary.get("subject"),
            "kind":summary.get("kind"),
            "oracle_success":summary.get("oracle_success"),
            "loop_count":len(loops),
            "loops":loops,
        })
    return {
        "schema_version":1,
        "trials_with_stuck_loops":rows,
        "trial_count":len(rows),
        "rule":"Loops are repeated observable action signatures; they are not claims about hidden intent.",
    }


def _context_failure_atlas(
    tasks: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    context_mechanisms = {"M17","M18","M19","M20","M37"}
    task_map = {str(task["task_id"]):task for task in tasks}
    rows = []
    for summary in summaries:
        task = task_map.get(str(summary.get("task_id")))
        if not task:
            continue
        relevant = sorted(
            context_mechanisms.intersection(task.get("candidate_mechanisms") or [])
        )
        if not relevant:
            continue
        metrics = dict(summary.get("metrics") or {})
        rows.append({
            "trial_key":summary.get("trial_key"),
            "task_id":summary.get("task_id"),
            "subject":summary.get("subject"),
            "kind":summary.get("kind"),
            "candidate_context_mechanisms":relevant,
            "oracle_success":bool(summary.get("oracle_success")),
            "context_compaction_count":int(metrics.get("context_compaction_count",0)),
            "session_id_present":bool(metrics.get("session_id")),
            "observer_mode":summary.get("observer_mode"),
            "response_oracle_ok":metrics.get("response_oracle_ok"),
        })
    failures = [row for row in rows if not row["oracle_success"]]
    return {
        "schema_version":1,
        "trials":rows,
        "failure_trials":failures,
        "failure_count":len(failures),
        "claim_boundary":"Association with a context-sensitive task is not causal proof; matched resume/observability interventions provide the causal layer.",
    }


def _frontier_failure_replay_queue(
    tasks: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    task_map = {str(task["task_id"]):task for task in tasks}
    rows = []
    for summary in summaries:
        if bool(summary.get("oracle_success")):
            continue
        task = task_map.get(str(summary.get("task_id")))
        if not task:
            continue
        level = str(task.get("level") or "")
        if level not in {"P9","P10"}:
            continue
        if not bool(task.get("replay_eligible", True)):
            continue
        replay_path = Path(summary["evidence_root"]) / "failure-replay.json"
        replay = _read_json(replay_path) if replay_path.is_file() else {}
        priority = 0
        if level == "P10":
            priority += 100
        priority += 10 * len(task.get("pathology_ids") or [])
        metrics = dict(summary.get("metrics") or {})
        priority += min(9, int(metrics.get("stuck_loop_count",0)) * 3)
        rows.append({
            "priority":priority,
            "trial_key":summary.get("trial_key"),
            "task_id":summary.get("task_id"),
            "subject":summary.get("subject"),
            "kind":summary.get("kind"),
            "level":level,
            "pathology_ids":list(task.get("pathology_ids") or []),
            "candidate_mechanisms":list(task.get("candidate_mechanisms") or []),
            "replay_id":replay.get("replay_id"),
            "trajectory_hash":replay.get("trajectory_hash"),
            "evidence_root":summary.get("evidence_root"),
        })
    rows.sort(key=lambda row: (-int(row["priority"]), str(row["task_id"]), str(row["subject"])))
    return {
        "schema_version":1,
        "queue":rows,
        "count":len(rows),
        "rule":"Queue ordering is deterministic engineering triage, not a model-capability verdict.",
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
    _write_json(run_root / "research-contract.json", research_contract(config))

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
    incompatible = [
        row for row in versions
        if row.get("available") and row.get("required_missing")
    ]
    if unavailable:
        raise RuntimeError(f"coding subjects unavailable: {unavailable}")
    if incompatible:
        raise RuntimeError(
            "coding subject CLI capabilities incompatible with tomography: "
            f"{incompatible}"
        )

    root_config = dict(config.get("coding_tomography") or {})
    timeout_s = float(root_config.get("timeout_s",1800))
    summaries: list[dict[str, Any]] = []
    quota_trials: list[dict[str, Any]] = []
    deferred_entries: list[dict[str, Any]] = []
    quota_subjects = quota_limited_subject_names(plan["subjects"])
    provider_status = {
        str(subject["name"]): (
            "AVAILABLE" if str(subject["name"]) in quota_subjects else "NOT_QUOTA_LIMITED"
        )
        for subject in plan["subjects"]
    }
    terminated_for_all_provider_quota = False

    for entry_index, entry in enumerate(plan["entries"]):
        ordinal = entry_index + 1
        subject_name = str(entry["subject"]["name"])
        if provider_status.get(subject_name) == "QUOTA_EXHAUSTED":
            deferred_entries.append(entry)
            continue

        task = task_map[entry["task_id"]]
        key = _trial_key(entry)
        workspace = run_root / "workspaces" / key
        evidence = run_root / "trials" / key
        kind = str(entry.get("kind") or "")
        resume_session_id = None
        trial_task = task
        trial_subject = deepcopy(entry["subject"])
        mcp_probe = None
        source = None

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
                raise RuntimeError(
                    "resume source trial missing for "
                    + str(entry["subject"]["name"])
                    + " "
                    + str(task["task_id"])
                )
            source_workspace = run_root / "workspaces" / source["trial_key"]
            if kind == "RESUME_FRESH_CONTROL":
                materialize_workspace(source_workspace, workspace)
            else:
                workspace = source_workspace
                resume_session_id = str((source.get("metrics") or {}).get("session_id") or "")
                if not resume_session_id:
                    raise RuntimeError("source session id missing for resume trial " + str(source["trial_key"]))

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

        if kind == "MCP_TREATMENT":
            mcp_probe = prepare_mcp_probe(
                workspace=workspace,
                evidence_root=evidence,
                subject=str(
                    entry["subject"].get("adapter")
                    or entry["subject"].get("harness")
                    or entry["subject"]["name"]
                ),
            )
            trial_subject["extra_args"] = (
                list(trial_subject.get("extra_args") or [])
                + list(mcp_probe.get("extra_args") or [])
            )
            _write_json(evidence / "mcp-probe-provenance.json", mcp_probe)

        intervention = entry.get("intervention")
        applied = None
        observer_files: list[str] = []
        if isinstance(intervention,dict):
            applied = apply_intervention(
                workspace,
                intervention,
                subject=str(
                    entry["subject"].get("adapter")
                    or entry["subject"].get("harness")
                    or entry["subject"]["name"]
                ),
            )
            _git_seal(workspace,f"tomography intervention baseline {intervention['id']}")
            _write_json(evidence / "intervention.json",applied)

        observer_record = None
        if (
            entry.get("kind") == "OBSERVABILITY_AUGMENTED"
            and str(
                entry["subject"].get("adapter")
                or entry["subject"].get("harness")
                or entry["subject"]["name"]
            ) == "claude_code"
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
            subject=trial_subject,
            workspace=workspace,
            evidence_root=evidence,
            timeout_s=timeout_s,
            observer_event_files=observer_files,
            rollout_path_template=entry["subject"].get("rollout_path_template"),
            auto_codex_rollout_lookup=(
                entry.get("kind") == "OBSERVABILITY_AUGMENTED"
                and str(
                    entry["subject"].get("adapter")
                    or entry["subject"].get("harness")
                    or entry["subject"]["name"]
                ) == "codex"
            ),
            resume_session_id=resume_session_id,
            gateway_event_files=trial_subject.get("gateway_event_files") or (),
        )
        if mcp_probe is not None and summary.get("trial_status") != "PROVIDER_QUOTA_EXHAUSTED":
            readiness = mcp_server_readiness(mcp_probe["event_log_path"])
            mcp_result = {
                **readiness,
                "tool_called":mcp_tool_was_called(mcp_probe["event_log_path"]),
                "server_name":mcp_probe["server_name"],
                "tool_name":mcp_probe["tool_name"],
                "permission_bypass_added":False,
            }
            _write_json(evidence / "mcp-probe-result.json", mcp_result)
            summary["mcp_probe"] = mcp_result

        summary.update({
            "trial_key":key,
            "ordinal":ordinal,
            "kind":entry["kind"],
            "repeat":entry["repeat"],
            "intervention_id":intervention.get("id") if isinstance(intervention,dict) else None,
            "intervention_hypothesis":intervention.get("hypothesis") if isinstance(intervention,dict) else None,
            "observer_mode": observer_record.get("mode") if isinstance(observer_record, dict) else None,
            "source_trial_key": source.get("trial_key") if isinstance(source, dict) else None,
        })
        _write_json(evidence / "trial-summary.json",summary)
        finalize_trial_evidence(evidence)

        if summary.get("trial_status") == "PROVIDER_QUOTA_EXHAUSTED":
            provider_status[subject_name] = "QUOTA_EXHAUSTED"
            quota_trials.append(summary)
            deferred_entries.append(entry)
            _write_json(run_root / "provider-usage-status.json", {
                "schema_version": 1,
                "provider_status": provider_status,
                "quota_terminal_trials": [
                    {
                        "trial_key": row.get("trial_key"),
                        "task_id": row.get("task_id"),
                        "subject": row.get("subject"),
                        "evidence_root": row.get("evidence_root"),
                    }
                    for row in quota_trials
                ],
            })
            if all_quota_limited_exhausted(provider_status, plan["subjects"]):
                deferred_entries.extend(plan["entries"][entry_index + 1:])
                terminated_for_all_provider_quota = True
                break
            continue

        summaries.append(summary)
        _write_json(run_root / "progress.json",{
            "completed_scored":len(summaries),
            "attempted_through_ordinal":ordinal,
            "total_planned_subject_sessions":plan["planned_sessions"],
            "last_trial_key":key,
            "provider_status":provider_status,
        })

    def safe_queue_entry(entry: dict[str, Any]) -> dict[str, Any]:
        intervention = entry.get("intervention")
        return {
            "trial_key": _trial_key(entry),
            "kind": entry.get("kind"),
            "task_id": entry.get("task_id"),
            "repeat": entry.get("repeat"),
            "subject": (entry.get("subject") or {}).get("name"),
            "intervention_id": (
                intervention.get("id") if isinstance(intervention, dict) else None
            ),
        }

    deduped_remaining = []
    seen_remaining: set[str] = set()
    for entry in deferred_entries:
        row = safe_queue_entry(entry)
        if row["trial_key"] in seen_remaining:
            continue
        seen_remaining.add(row["trial_key"])
        deduped_remaining.append(row)
    _write_json(run_root / "remaining-scheduled-queue.json", {
        "schema_version": 1,
        "entries": deduped_remaining,
        "count": len(deduped_remaining),
        "secret_values_recorded": False,
    })
    _write_json(run_root / "remaining-native-queue.json", {
        "schema_version": 1,
        "entries": deduped_remaining,
        "count": len(deduped_remaining),
        "compatibility_alias": "remaining-scheduled-queue.json",
    })
    _write_json(run_root / "quota-terminal-trials.json", {
        "schema_version": 1,
        "trials": quota_trials,
    })
    _write_json(run_root / "provider-usage-status.json", {
        "schema_version": 1,
        "provider_status": provider_status,
        "all_quota_limited_exhausted": all_quota_limited_exhausted(
            provider_status, plan["subjects"]
        ),
        "quota_terminal_trial_count": len(quota_trials),
    })

    if terminated_for_all_provider_quota:
        replay_rows = []
        replay_effectiveness = {
            "schema_version": 1,
            "reserved_slots": int(plan.get("replay_reserve_slots", 0)),
            "used_slots": 0,
            "unused_slots": int(plan.get("replay_reserve_slots", 0)),
            "results": {},
            "status": "SKIPPED_PROVIDER_USAGE_EXHAUSTED",
            "hidden_oracle_content_in_replay_prompt": False,
        }
    else:
        active_subjects = [
            subject for subject in plan["subjects"]
            if provider_status.get(str(subject["name"])) != "QUOTA_EXHAUSTED"
        ]
        active_names = {str(subject["name"]) for subject in active_subjects}
        replay_source_summaries = [
            row for row in summaries
            if str(row.get("subject")) in active_names
        ]
        replay_rows, replay_effectiveness = _run_replay_reserve(
            summaries=replay_source_summaries,
            task_map=task_map,
            subjects=active_subjects,
            run_root=run_root,
            timeout_s=timeout_s,
            slots=int(plan.get("replay_reserve_slots", 0)),
            ordinal_start=len(summaries),
            planned_total=int(plan["planned_sessions"]),
        )
        summaries.extend(replay_rows)
        for exhausted_subject in replay_effectiveness.get("quota_exhausted_subjects") or []:
            provider_status[str(exhausted_subject)] = "QUOTA_EXHAUSTED"
        for quota_row in replay_effectiveness.get("quota_terminal_trials") or []:
            quota_trials.append(quota_row)

    _write_json(run_root / "trial-index.json",{"schema_version":1,"trials":summaries})
    _write_json(run_root / "quota-terminal-trials.json", {
        "schema_version": 1,
        "trials": quota_trials,
    })
    _write_json(run_root / "provider-usage-status.json", {
        "schema_version": 1,
        "provider_status": provider_status,
        "all_quota_limited_exhausted": all_quota_limited_exhausted(
            provider_status, plan["subjects"]
        ),
        "quota_terminal_trial_count": len(quota_trials),
        "replay_quota_exhausted_subjects": (
            replay_effectiveness.get("quota_exhausted_subjects") or []
        ),
    })

    shadow_cfg = dict(root_config.get("shadow_observer") or {})
    shadow_rows: list[dict[str, Any]] = []
    if bool(shadow_cfg.get("enabled", False)):
        subject_map = {str(row["name"]): row for row in plan["subjects"]}
        shadow_root = run_root / "shadow-observer"
        for summary in summaries:
            subject = subject_map.get(str(summary.get("subject"))) or {
                "name": summary.get("subject")
            }
            task = task_map.get(str(summary.get("task_id"))) or {}
            shadow_rows.append(
                run_shadow_observer(
                    trial_root=summary["evidence_root"],
                    output_root=shadow_root,
                    trial_key=str(summary["trial_key"]),
                    task_prompt=str(task.get("prompt") or ""),
                    subject=subject,
                    config=shadow_cfg,
                )
            )
    _write_json(run_root / "shadow-observer-index.json", {
        "schema_version": 1,
        "mode": str(shadow_cfg.get("mode") or "post_campaign"),
        "authoritative": False,
        "may_change_primary_score": False,
        "rows": shadow_rows,
    })
    escalation_artifact = build_shadow_escalation_queue(
        shadow_rows,
        confidence_threshold=float(
            shadow_cfg.get("escalation_confidence_threshold", 0.65)
        ),
    )
    _write_json(
        run_root / "shadow-observer-escalation-queue.json",
        escalation_artifact,
    )

    compute_summary = aggregate_compute_cost(
        summaries,
        shadow_observer_rows=shadow_rows,
    )
    _write_json(run_root / "compute-cost-summary.json", compute_summary)
    _write_json(run_root / "model-harness-matrix.json", {
        "schema_version": 1,
        "groups": compute_summary.get("groups") or {},
        "rule": (
            "Compare same model across harnesses for harness effect and different models under the same "
            "harness for model effect; model-harness interaction remains a separate effect."
        ),
    })
    _write_json(run_root / "research-exposure-index.json", build_exposure_index(summaries))


    _write_json(run_root / "trial-index.json",{"schema_version":1,"trials":summaries})
    behavior = _behavior_atlas(summaries)
    paired = _paired_intervention_results(plan,summaries)
    resume_continuity = _resume_continuity_results(summaries)
    mcp_escalation = _mcp_escalation_results(summaries)
    causal_evidence = deepcopy(paired)
    causal_evidence.setdefault("results", {}).update(resume_continuity.get("results") or {})
    causal_evidence.setdefault("results", {}).update(mcp_escalation.get("results") or {})
    causal_evidence.setdefault("results", {}).update(replay_effectiveness.get("results") or {})
    mechanisms = _mechanism_results(tasks,summaries,causal_evidence)
    bundles = _bundle_results(tasks, causal_evidence)
    failures = _failure_registry(summaries)
    divergence = _cross_subject_divergence(run_root,summaries)
    known_unknown = _known_unknown(mechanisms)
    blueprint,rejects,next_experiments = _blueprint_and_rejects(mechanisms)
    pathology_compounds = _pathology_compounds_artifact()
    recoverable_atlas = _last_recoverable_state_atlas(summaries)
    strategy_resets = _strategy_reset_events(summaries)
    stuck_loops = _stuck_loop_registry(summaries)
    context_failures = _context_failure_atlas(tasks, summaries)
    frontier_replay_queue = _frontier_failure_replay_queue(tasks, summaries)

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
    _write_json(run_root / "causal-intervention-results.json",causal_evidence)
    _write_json(run_root / "resume-continuity-results.json",resume_continuity)
    _write_json(run_root / "mcp-escalation-results.json",mcp_escalation)
    _write_json(run_root / "failure-replay-effectiveness.json",replay_effectiveness)
    _write_json(run_root / "causal-factor-registry.json", _causal_factor_registry(causal_evidence))
    _write_json(run_root / "pathology-ablation-results.json", _pathology_ablation_results(tasks, paired))
    _write_json(run_root / "pathology-compounds.json", pathology_compounds)
    _write_json(run_root / "last-recoverable-state-atlas.json", recoverable_atlas)
    _write_jsonl(run_root / "strategy-reset-events.jsonl", strategy_resets)
    _write_json(run_root / "stuck-loop-registry.json", stuck_loops)
    _write_json(run_root / "context-failure-atlas.json", context_failures)
    _write_json(run_root / "frontier-failure-replay-queue.json", frontier_replay_queue)
    _write_json(run_root / "mechanism-value-per-cost.json",mechanisms)
    _write_json(run_root / "mechanism-bundle-value.json",bundles)
    _write_json(run_root / "mechanism-interaction-graph.json", _mechanism_interaction_graph(tasks, summaries, causal_evidence))
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

    completion = campaign_completion_record(
        planned_sessions=int(plan["planned_sessions"]),
        completed_scored_sessions=len(summaries),
        provider_status=provider_status,
        remaining_entries=deduped_remaining,
        quota_terminal_trials=len(quota_trials),
        all_quota_exhausted=all_quota_limited_exhausted(
            provider_status, plan["subjects"]
        ),
    )
    _write_json(run_root / "campaign-status.json", completion)

    result = {
        "schema_version":2,
        "run_id":run_id,
        "dry_run":False,
        "run_root":str(run_root),
        "campaign_status":completion["campaign_status"],
        "status_text":completion["status_text"],
        "completion_reason":completion["completion_reason"],
        "scientific_coverage":completion["scientific_coverage"],
        "planned_sessions":plan["planned_sessions"],
        "completed_sessions":len(summaries),
        "quota_terminal_trials":len(quota_trials),
        "remaining_scheduled_sessions":len(deduped_remaining),
        "compute_cost_summary":str(run_root / "compute-cost-summary.json"),
        "shadow_observer_index":str(run_root / "shadow-observer-index.json"),
        "research_exposure_index":str(run_root / "research-exposure-index.json"),
        "native_behavior_atlas":str(run_root / "native-behavior-atlas.json"),
        "causal_intervention_results":str(run_root / "causal-intervention-results.json"),
        "clone_blueprint":str(run_root / "inverted-clone-blueprint.json"),
        "failure_replay_registry":str(run_root / "failure-replay-registry.json"),
        "privacy_status":privacy["status"],
    }
    _write_json(run_root / "campaign-summary.json",result)
    return result
