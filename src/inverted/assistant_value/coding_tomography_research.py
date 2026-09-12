from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Iterable

import httpx


_QUOTA_PATTERNS: dict[str, tuple[str, ...]] = {
    "claude_code": (
        r"you(?:'|’)ve hit your (?:usage |session |weekly )?limit",
        r"you(?:'|’)ve hit your monthly spend limit",
        r"usage limit (?:has been )?reached",
        r"limit reached.{0,120}reset",
        r"out of (?:included )?usage",
        r"usage exhausted",
    ),
    "codex": (
        r"you(?:'|’)ve hit your usage limit",
        r"usage[_ ]limit[_ ]reached",
        r"usage limit (?:has been )?reached",
        r"limit reached.{0,120}(?:reset|try again)",
        r"insufficient_quota",
        r"quota exhausted",
        r"you have 0 (?:weighted )?tokens left",
    ),
}


def model_harness_identity(subject: dict[str, Any]) -> dict[str, Any]:
    name = str(subject.get("name") or "unknown")
    return {
        "subject": name,
        "harness": str(subject.get("harness") or name),
        "model_backend": str(subject.get("model_backend") or "native_unspecified"),
        "provider_mode": str(subject.get("provider_mode") or "native"),
        "compute_scope": str(subject.get("compute_scope") or "remote"),
        "quota_limited": bool(subject.get("quota_limited", name in {"claude_code", "codex"})),
        "gateway": str(subject.get("gateway") or "NONE"),
    }


def quota_limited_subject_names(subjects: Iterable[dict[str, Any]]) -> set[str]:
    out = set()
    for subject in subjects:
        identity = model_harness_identity(subject)
        if identity["quota_limited"]:
            out.add(str(identity["subject"]))
    return out


def all_quota_limited_exhausted(
    provider_status: dict[str, str],
    subjects: Iterable[dict[str, Any]],
) -> bool:
    names = quota_limited_subject_names(subjects)
    return bool(names) and all(provider_status.get(name) == "QUOTA_EXHAUSTED" for name in names)


def classify_provider_quota_exhaustion(
    subject: dict[str, Any] | str,
    *,
    stdout: str,
    stderr: str,
    raw_events: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    if isinstance(subject, dict):
        identity = model_harness_identity(subject)
        name = str(identity["subject"])
        quota_limited = bool(identity["quota_limited"])
        extra_patterns = tuple(str(x) for x in subject.get("quota_patterns") or ())
    else:
        name = str(subject)
        quota_limited = name in {"claude_code", "codex"}
        extra_patterns = ()
    if not quota_limited:
        return {
            "schema_version": 1,
            "status": "NOT_QUOTA_LIMITED",
            "subject": name,
            "matched_pattern": None,
            "evidence_sha256": None,
        }

    event_text = "\n".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
        for row in raw_events
    )
    haystack = (str(stderr) + "\n" + str(stdout) + "\n" + event_text)[-500_000:]
    patterns = tuple(_QUOTA_PATTERNS.get(name, ())) + extra_patterns
    matched = None
    for pattern in patterns:
        if re.search(pattern, haystack, re.IGNORECASE | re.DOTALL):
            matched = pattern
            break
    digest = hashlib.sha256(haystack.encode("utf-8", errors="replace")).hexdigest()
    return {
        "schema_version": 1,
        "status": "PROVIDER_QUOTA_EXHAUSTED" if matched else "AVAILABLE_OR_OTHER_ERROR",
        "subject": name,
        "matched_pattern": matched,
        "evidence_sha256": digest,
        "generic_rate_limit_alone_is_terminal": False,
    }


_TOKEN_KEYS = {
    "input_tokens": "input_tokens",
    "prompt_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "completion_tokens": "output_tokens",
    "cached_input_tokens": "cached_input_tokens",
    "cache_read_input_tokens": "cached_input_tokens",
    "cache_creation_input_tokens": "cache_creation_input_tokens",
    "total_tokens": "total_tokens",
}


def _walk_dicts(value: Any, path: str = "$") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from _walk_dicts(child, path + "." + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_dicts(child, path + "[" + str(index) + "]")


def extract_observed_usage(raw_events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event_index, event in enumerate(raw_events, start=1):
        for path, candidate in _walk_dicts(event):
            normalized: dict[str, int] = {}
            for key, canonical in _TOKEN_KEYS.items():
                value = candidate.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    normalized[canonical] = normalized.get(canonical, 0) + int(value)
            if not normalized:
                continue
            fingerprint = hashlib.sha256(
                json.dumps({"path": path, "value": candidate}, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            records.append({
                "event_index": event_index,
                "path": path,
                "normalized": normalized,
                "raw": candidate,
            })
    totals: dict[str, int] = defaultdict(int)
    for record in records:
        for key, value in record["normalized"].items():
            totals[key] += int(value)
    return {
        "schema_version": 1,
        "classification": "OBSERVED_BEST_EFFORT",
        "record_count": len(records),
        "observed_totals": dict(totals),
        "records": records,
        "aggregation_rule": (
            "Exact duplicate usage objects are deduplicated, then emitted usage records are summed. "
            "Provider semantics may be cumulative; raw records are retained for audit."
        ),
    }


def capture_instruction_surfaces(workspace: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    candidates: list[Path] = []
    direct = ("CLAUDE.md", "AGENTS.md")
    for name in direct:
        path = root / name
        if path.is_file():
            candidates.append(path)
    for dirname in (".claude", ".codex", ".agents"):
        base = root / dirname
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".json", ".yaml", ".yml", ".txt"}:
                candidates.append(path)
    rows = []
    total_text_bytes = 0
    for path in sorted(set(candidates)):
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        encoded = text.encode("utf-8")
        remaining = max(0, 262_144 - total_text_bytes)
        retained = encoded[:remaining].decode("utf-8", errors="ignore") if remaining else ""
        total_text_bytes += len(retained.encode("utf-8"))
        rows.append({
            "path": relative,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "text": retained,
            "text_truncated": len(retained.encode("utf-8")) < len(encoded),
        })
    return {
        "schema_version": 1,
        "surfaces": rows,
        "captured_text_bytes": total_text_bytes,
        "rule": "Only user-owned repository instruction/config surfaces are captured; credentials are not searched or copied.",
    }


def load_external_event_files(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            continue
        for line_number, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except Exception:
                value = {"type": "gateway_unparsed", "raw_text": raw}
            if not isinstance(value, dict):
                value = {"type": "gateway_non_object", "value": value}
            value = dict(value)
            value.setdefault("source_path", str(path))
            value.setdefault("line_number", line_number)
            rows.append(value)
    return rows


def build_compute_cost(
    *,
    subject: dict[str, Any],
    run: dict[str, Any],
    raw_events: Iterable[dict[str, Any]],
    change_map: dict[str, Any],
) -> dict[str, Any]:
    identity = model_harness_identity(subject)
    resources = dict(run.get("resources") or {})
    gpu = dict(resources.get("gpu") or {})
    scope = str(identity["compute_scope"])
    return {
        "schema_version": 1,
        "identity": identity,
        "subject_compute": {
            "wall_seconds": float(run.get("elapsed_s") or 0.0),
            "cpu_seconds": resources.get("cpu_seconds"),
            "peak_rss_bytes": resources.get("peak_rss_bytes"),
            "read_bytes": resources.get("read_bytes"),
            "write_bytes": resources.get("write_bytes"),
            "resource_sample_count": resources.get("sample_count", 0),
            "measurement_status": resources.get("measurement_status", "UNKNOWN"),
        },
        "gpu_compute": {
            "status": gpu.get("status", "NOT_SAMPLED"),
            "scope": gpu.get("scope"),
            "sample_count": gpu.get("sample_count", 0),
            "peak_vram_mib": gpu.get("peak_vram_mib"),
            "peak_utilization_percent": gpu.get("peak_utilization_percent"),
            "peak_power_w": gpu.get("peak_power_w"),
            "peak_temperature_c": gpu.get("peak_temperature_c"),
            "watt_hours": gpu.get("watt_hours"),
        },
        "model_usage": extract_observed_usage(raw_events),
        "workspace_cost": {
            "changed_file_count": int(change_map.get("changed_count") or 0),
        },
        "remote_provider_compute": {
            "status": "UNOBSERVABLE" if scope == "remote" else "NOT_APPLICABLE_LOCAL_BACKEND",
            "rule": (
                "Anthropic/OpenAI server GPU, RAM, energy, and internal inference compute are never estimated "
                "without provider-exposed measurements."
            ),
        },
        "observer_cost_included": False,
    }


def _execution_boundary() -> dict[str, Any]:
    docker = Path("/.dockerenv").exists() or bool(os.environ.get("CONTAINER"))
    return {
        "docker_detected": docker,
        "container_id_hint": os.environ.get("HOSTNAME") if docker else None,
        "mcp_environment_names": sorted(
            key for key in os.environ
            if key.upper().startswith(("MCP_", "DOCKER_", "CONTAINER_"))
        ),
    }


def build_exposure_manifest(
    *,
    subject: dict[str, Any],
    quota_status: dict[str, Any],
    compute_cost: dict[str, Any],
    native_event_count: int,
    observer_event_count: int,
    gateway_event_count: int,
    instruction_surface_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "identity": model_harness_identity(subject),
        "execution_boundary": _execution_boundary(),
        "channels": {
            "native_events": native_event_count,
            "passive_observer_events": observer_event_count,
            "gateway_events": gateway_event_count,
            "instruction_surfaces": instruction_surface_count,
        },
        "quota_status": quota_status,
        "compute_cost_path": "compute-cost.json",
        "evidence_boundaries": {
            "hidden_chain_of_thought": "NOT_CLAIMED",
            "secret_system_prompts": "NOT_CLAIMED",
            "provider_private_implementation": "NOT_CLAIMED",
            "native_exposed_reasoning_summaries": "PRESERVE_WHEN_EXPOSED",
            "synthetic_reasoning": "SEPARATE_NON_AUTHORITATIVE_CHANNEL",
        },
        "remote_compute_status": compute_cost["remote_provider_compute"]["status"],
    }


def research_contract(config: dict[str, Any]) -> dict[str, Any]:
    root = dict(config.get("coding_tomography") or {})
    observer = dict(root.get("shadow_observer") or {})
    return {
        "schema_version": 1,
        "primary_test_changed": False,
        "subject_schedule_changed": False,
        "scoring_changed": False,
        "additive_layers": [
            "PASSIVE_EXPOSURE",
            "MODEL_HARNESS_PROVENANCE",
            "PROVIDER_QUOTA_TERMINATION",
            "COMPUTE_COST",
            "POST_CAMPAIGN_SHADOW_OBSERVER",
            "GATEWAY_EVIDENCE",
        ],
        "shadow_observer": {
            "enabled": bool(observer.get("enabled", False)),
            "mode": str(observer.get("mode") or "post_campaign"),
            "model": str(observer.get("model") or "gpt-oss:20b"),
            "authoritative": False,
            "may_change_primary_score": False,
        },
        "quota_rule": (
            "A provider quota terminal event is unscored, is not a model failure, disables future trials for that "
            "quota-limited subject, and ends the campaign successfully when all quota-limited subjects are exhausted."
        ),
        "compute_rule": (
            "Local harness/process resources are measured where observable. Remote provider server compute remains "
            "UNOBSERVABLE. Shadow-observer compute is accounted separately."
        ),
    }


def build_shadow_observer_payload(
    *,
    trial_root: str | Path,
    task_prompt: str,
    subject: dict[str, Any],
    max_events: int = 180,
) -> dict[str, Any]:
    root = Path(trial_root)
    trajectory = []
    path = root / "normalized-native-trajectory.jsonl"
    if path.is_file():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if raw.strip():
                try:
                    trajectory.append(json.loads(raw))
                except Exception:
                    pass
    if len(trajectory) > max_events:
        head = max_events // 2
        trajectory = trajectory[:head] + trajectory[-(max_events - head):]
    def load_json(name: str) -> Any:
        p = root / name
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    final_path = root / "observable-final-response.txt"
    return {
        "evidence_class": "SYNTHETIC_INFERENCE_INPUT",
        "task_prompt": task_prompt,
        "identity": model_harness_identity(subject),
        "native_trajectory": trajectory,
        "workspace_diff": load_json("workspace-diff.json"),
        "channel_coverage": load_json("channel-coverage.json"),
        "instruction_surfaces": load_json("model-visible-instruction-surfaces.json"),
        "observable_final_response": (
            final_path.read_text(encoding="utf-8", errors="replace")[:12_000]
            if final_path.is_file() else ""
        ),
        "explicitly_excluded": [
            "hidden-oracle-results.json",
            "failure-replay hidden acceptance material",
            "secret credentials",
            "unexposed chain-of-thought",
        ],
    }


def run_shadow_observer(
    *,
    trial_root: str | Path,
    output_root: str | Path,
    trial_key: str,
    task_prompt: str,
    subject: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    cfg = dict(config or {})
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    evidence_path = out / (trial_key + ".json")
    cost_path = out / (trial_key + ".compute-cost.json")
    if not bool(cfg.get("enabled", False)):
        row = {"schema_version": 1, "trial_key": trial_key, "status": "DISABLED"}
        evidence_path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return row

    payload = build_shadow_observer_payload(
        trial_root=trial_root,
        task_prompt=task_prompt,
        subject=subject,
        max_events=int(cfg.get("max_events", 180)),
    )
    model = str(cfg.get("model") or "gpt-oss:20b")
    base_url = str(
        os.environ.get("INVERTED_OBSERVER_BASE_URL")
        or cfg.get("base_url")
        or "http://127.0.0.1:11434"
    ).rstrip("/")
    instruction = (
        "You are a passive forensic observer. Analyze only the supplied observable evidence. "
        "Do not claim hidden chain-of-thought, secret prompts, or private implementation. "
        "Return JSON with keys: phase_trace, decision_notes, hypothesis_updates, anomalies, "
        "missing_expected_actions, high_surprise_decisions, unexplained_decisions, alternatives, "
        "confidence, evidence_refs. Every inference must cite observable sequence/event references. "
        "Use UNKNOWN when evidence is insufficient."
    )
    started = time.monotonic()
    try:
        with httpx.Client(timeout=float(cfg.get("timeout_s", 180.0))) as client:
            response = client.post(
                base_url + "/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": instruction},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
                    ],
                    "options": {"temperature": float(cfg.get("temperature", 0.0))},
                },
            )
            response.raise_for_status()
            body = response.json()
        content = ((body.get("message") or {}).get("content") or "{}")
        try:
            annotation = json.loads(content)
        except Exception:
            annotation = {"status": "UNPARSEABLE_MODEL_OUTPUT", "raw_text": str(content)[:50_000]}
        row = {
            "schema_version": 1,
            "trial_key": trial_key,
            "status": "SUCCESS",
            "evidence_class": "SYNTHETIC_INFERENCE",
            "authoritative": False,
            "may_change_primary_score": False,
            "model": model,
            "annotation": annotation,
        }
        cost = {
            "schema_version": 1,
            "trial_key": trial_key,
            "observer_model": model,
            "wall_seconds": time.monotonic() - started,
            "prompt_eval_count": body.get("prompt_eval_count"),
            "eval_count": body.get("eval_count"),
            "prompt_eval_duration_ns": body.get("prompt_eval_duration"),
            "eval_duration_ns": body.get("eval_duration"),
            "load_duration_ns": body.get("load_duration"),
            "subject_compute_included": False,
        }
    except Exception as exc:
        row = {
            "schema_version": 1,
            "trial_key": trial_key,
            "status": "OBSERVER_UNAVAILABLE",
            "evidence_class": "SYNTHETIC_INFERENCE",
            "authoritative": False,
            "may_change_primary_score": False,
            "model": model,
            "error": type(exc).__name__ + ": " + str(exc),
        }
        cost = {
            "schema_version": 1,
            "trial_key": trial_key,
            "observer_model": model,
            "wall_seconds": time.monotonic() - started,
            "status": "UNAVAILABLE",
            "subject_compute_included": False,
        }
    evidence_path.write_text(json.dumps(row, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    cost_path.write_text(json.dumps(cost, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return {**row, "evidence_path": str(evidence_path), "compute_cost_path": str(cost_path)}


def aggregate_compute_cost(
    summaries: Iterable[dict[str, Any]],
    *,
    shadow_observer_rows: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    trials = []
    for summary in summaries:
        root = Path(str(summary["evidence_root"]))
        path = root / "compute-cost.json"
        if not path.is_file():
            continue
        cost = json.loads(path.read_text(encoding="utf-8"))
        identity = dict(cost.get("identity") or {})
        key = "|".join([
            str(identity.get("harness") or summary.get("subject")),
            str(identity.get("model_backend") or "unknown"),
        ])
        group = groups.setdefault(key, {
            "harness": identity.get("harness"),
            "model_backend": identity.get("model_backend"),
            "provider_mode": identity.get("provider_mode"),
            "compute_scope": identity.get("compute_scope"),
            "trials": 0,
            "verified_successes": 0,
            "subject_wall_seconds": 0.0,
            "cpu_seconds": 0.0,
            "read_bytes": 0,
            "write_bytes": 0,
            "gpu_watt_hours": 0.0,
            "input_tokens_observed": 0,
            "output_tokens_observed": 0,
            "remote_compute_unobservable_trials": 0,
        })
        group["trials"] += 1
        group["verified_successes"] += int(summary.get("oracle_success") is True)
        sc = dict(cost.get("subject_compute") or {})
        group["subject_wall_seconds"] += float(sc.get("wall_seconds") or 0.0)
        group["cpu_seconds"] += float(sc.get("cpu_seconds") or 0.0)
        group["read_bytes"] += int(sc.get("read_bytes") or 0)
        group["write_bytes"] += int(sc.get("write_bytes") or 0)
        gpu = dict(cost.get("gpu_compute") or {})
        group["gpu_watt_hours"] += float(gpu.get("watt_hours") or 0.0)
        usage = ((cost.get("model_usage") or {}).get("observed_totals") or {})
        group["input_tokens_observed"] += int(usage.get("input_tokens") or 0)
        group["output_tokens_observed"] += int(usage.get("output_tokens") or 0)
        if ((cost.get("remote_provider_compute") or {}).get("status") == "UNOBSERVABLE"):
            group["remote_compute_unobservable_trials"] += 1
        trials.append({
            "trial_key": summary.get("trial_key"),
            "task_id": summary.get("task_id"),
            "subject": summary.get("subject"),
            "oracle_success": summary.get("oracle_success"),
            "cost_path": str(path),
            "identity": identity,
        })
    for group in groups.values():
        successes = int(group["verified_successes"])
        group["wall_seconds_per_verified_success"] = (
            group["subject_wall_seconds"] / successes if successes else None
        )
        group["gpu_wh_per_verified_success"] = (
            group["gpu_watt_hours"] / successes
            if successes and group["gpu_watt_hours"] > 0 else None
        )

    observer = {
        "trials_attempted": 0,
        "successful": 0,
        "wall_seconds": 0.0,
        "prompt_tokens_observed": 0,
        "output_tokens_observed": 0,
    }
    for row in shadow_observer_rows:
        observer["trials_attempted"] += 1
        observer["successful"] += int(row.get("status") == "SUCCESS")
        cost_path = row.get("compute_cost_path")
        if not cost_path or not Path(str(cost_path)).is_file():
            continue
        cost = json.loads(Path(str(cost_path)).read_text(encoding="utf-8"))
        observer["wall_seconds"] += float(cost.get("wall_seconds") or 0.0)
        observer["prompt_tokens_observed"] += int(cost.get("prompt_eval_count") or 0)
        observer["output_tokens_observed"] += int(cost.get("eval_count") or 0)

    return {
        "schema_version": 1,
        "groups": groups,
        "trials": trials,
        "shadow_observer_compute": observer,
        "separation_rule": "Subject compute and shadow-observer compute are never merged into the same performance metric.",
    }


def build_exposure_index(summaries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for summary in summaries:
        root = Path(str(summary["evidence_root"]))
        rows.append({
            "trial_key": summary.get("trial_key"),
            "task_id": summary.get("task_id"),
            "subject": summary.get("subject"),
            "identity": summary.get("model_harness"),
            "trial_status": summary.get("trial_status"),
            "exposure_manifest": str(root / "exposure-manifest.json"),
            "compute_cost": str(root / "compute-cost.json"),
            "native_events": str(root / "subject-native-events.jsonl"),
            "gateway_events": str(root / "gateway-events.jsonl"),
            "instruction_surfaces": str(root / "model-visible-instruction-surfaces.json"),
        })
    return {"schema_version": 1, "trials": rows}


def campaign_completion_record(
    *,
    planned_sessions: int,
    completed_scored_sessions: int,
    provider_status: dict[str, str],
    remaining_entries: list[dict[str, Any]],
    quota_terminal_trials: int,
    all_quota_exhausted: bool,
) -> dict[str, Any]:
    if all_quota_exhausted and quota_terminal_trials:
        reason = "PROVIDER_USAGE_EXHAUSTED"
    elif quota_terminal_trials:
        reason = "PARTIAL_PROVIDER_USAGE_EXHAUSTION"
    else:
        reason = "PLANNED_WORK_COMPLETE"
    partial = bool(remaining_entries or quota_terminal_trials)
    return {
        "schema_version": 1,
        "campaign_status": "COMPLETE",
        "status_text": "COMPLETE — " + reason.replace("_", " "),
        "completion_reason": reason,
        "scientific_coverage": "PARTIAL" if partial else "COMPLETE",
        "planned_sessions": int(planned_sessions),
        "completed_scored_sessions": int(completed_scored_sessions),
        "quota_terminal_trials": int(quota_terminal_trials),
        "provider_status": provider_status,
        "remaining_scheduled_sessions": len(remaining_entries),
        "remaining_queue_preserved": True,
        "quota_terminal_is_model_failure": False,
    }
