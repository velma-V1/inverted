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
    mechanism_registry,
    pathology_registry,
)
from .coding_tomography_interventions import (
    apply_intervention,
    selected_interventions,
)
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
    task_filter = {str(x) for x in root.get("task_ids") or []}
    selected_tasks = [task for task in tasks if not task_filter or task["task_id"] in task_filter]

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
            for intervention in selected_interventions(task["task_id"], include_common=include_common):
                for repeat in range(intervention_repeats):
                    entries.append({
                        "kind":"CAUSAL_INTERVENTION",
                        "subject":subject,
                        "task_id":task["task_id"],
                        "repeat":repeat + 1,
                        "intervention":intervention,
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
        "planned_sessions":len(entries),
        "max_sessions":max_sessions,
        "entries":entries,
    }


def _trial_key(entry: dict[str, Any]) -> str:
    intervention = entry.get("intervention")
    treatment = intervention.get("id") if isinstance(intervention, dict) else "native"
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
        if intervention is None:
            native[(subject,task_id)].append(summary)
        else:
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
    task_map = {task["task_id"]:task for task in tasks}
    by_mechanism: dict[str, dict[str, Any]] = {}
    paired = list((intervention_results.get("results") or {}).values())

    for mechanism in MECHANISMS:
        mid = mechanism["id"]
        looked_trials = [
            row for row in summaries
            if mid in (task_map.get(row["task_id"],{}).get("candidate_mechanisms") or [])
        ]
        affected = [row for row in paired if mid in (row.get("mechanisms") or [])]
        independent_tasks = {
            row["task_id"] for row in looked_trials
        }
        positive = [row for row in affected if float(row.get("success_delta",0.0)) > 0]
        negative = [row for row in affected if float(row.get("success_delta",0.0)) < 0]
        rescue_rate = (
            sum(max(0.0,float(row["success_delta"])) for row in affected) / len(affected)
            if affected else 0.0
        )
        regression_rate = (
            sum(max(0.0,-float(row["success_delta"])) for row in affected) / len(affected)
            if affected else 0.0
        )
        families = {
            task_map.get(row["task_id"],{}).get("family")
            for row in positive
            if task_map.get(row["task_id"])
        }
        evidence = classify_mechanism_evidence(
            observed_trials=len(looked_trials),
            independent_tasks=len(independent_tasks),
            causal_interventions=len(affected),
            generalized_families=len(families),
            rescue_rate=rescue_rate,
            regression_rate=regression_rate,
            complexity_units=2.0,
        )
        by_mechanism[mid] = {
            "mechanism_id":mid,
            "mechanism_name":mechanism["name"],
            **evidence,
            "looked_at_task_ids":sorted(independent_tasks),
            "intervention_count":len(affected),
            "positive_interventions":len(positive),
            "negative_interventions":len(negative),
        }
    return {"schema_version":1,"mechanisms":by_mechanism}


def _behavior_atlas(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in summaries:
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
        a = _read_jsonl(Path(claude[0]["evidence_root"]) / "normalized-trajectory.jsonl")
        b = _read_jsonl(Path(codex[0]["evidence_root"]) / "normalized-trajectory.jsonl")
        result[task_id] = first_divergence(a,b)
    return {"schema_version":1,"tasks":result}


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
        materialize_workspace(task["workspace_template"],workspace)

        intervention = entry.get("intervention")
        applied = None
        if isinstance(intervention,dict):
            applied = apply_intervention(
                workspace,
                intervention,
                subject=str(entry["subject"]["name"]),
            )
            _git_seal(workspace,f"tomography intervention baseline {intervention['id']}")
            _write_json(evidence / "intervention.json",applied)

        summary = run_subject_trial(
            task=task,
            subject=entry["subject"],
            workspace=workspace,
            evidence_root=evidence,
            timeout_s=timeout_s,
        )
        summary.update({
            "trial_key":key,
            "ordinal":ordinal,
            "kind":entry["kind"],
            "repeat":entry["repeat"],
            "intervention_id":intervention.get("id") if isinstance(intervention,dict) else None,
            "intervention_hypothesis":intervention.get("hypothesis") if isinstance(intervention,dict) else None,
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
    failures = _failure_registry(summaries)
    divergence = _cross_subject_divergence(run_root,summaries)
    known_unknown = _known_unknown(mechanisms)
    blueprint,rejects,next_experiments = _blueprint_and_rejects(mechanisms)

    _write_json(run_root / "native-behavior-atlas.json",behavior)
    _write_json(run_root / "causal-intervention-results.json",paired)
    _write_json(run_root / "mechanism-value-per-cost.json",mechanisms)
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
