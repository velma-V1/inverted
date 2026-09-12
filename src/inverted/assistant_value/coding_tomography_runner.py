from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any, Iterable

from .coding_subjects import (
    SubjectCommand,
    command_for_subject,
    expand_observable_subject_stream,
    extract_observable_final_text,
    extract_subject_session_id,
    parse_jsonl_stream,
    resume_command_for_subject,
    sanitize_environment_snapshot,
    subject_command_provenance,
)
from .coding_tomography import (
    failure_replay_packet,
    normalize_events,
    trajectory_metrics,
)
from .coding_tomography_observers import (
    codex_rollout_observable_events,
    load_rollout_jsonl,
    locate_codex_rollout_by_thread_id,
    resolve_rollout_path,
)
from .coding_tomography_research import (
    build_compute_cost,
    build_exposure_manifest,
    capture_instruction_surfaces,
    classify_provider_quota_exhaustion,
    load_external_event_files,
    model_harness_identity,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_manifest(root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    files = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root_path)
        except ValueError:
            continue
        if ".git" in relative.parts:
            continue
        files.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = {"root_name": root_path.name, "files": files}
    payload["manifest_sha256"] = hashlib.sha256(
        json.dumps(payload["files"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def manifest_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    left = {row["path"]: row for row in before.get("files", [])}
    right = {row["path"]: row for row in after.get("files", [])}
    created = sorted(set(right) - set(left))
    deleted = sorted(set(left) - set(right))
    modified = sorted(
        path for path in set(left) & set(right)
        if left[path].get("sha256") != right[path].get("sha256")
    )
    unchanged = sorted(
        path for path in set(left) & set(right)
        if left[path].get("sha256") == right[path].get("sha256")
    )
    return {
        "created": created,
        "deleted": deleted,
        "modified": modified,
        "unchanged_count": len(unchanged),
        "changed_count": len(created) + len(deleted) + len(modified),
    }


def _nvidia_snapshot() -> dict[str, float] | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=power.draw,memory.used,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
            shell=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    rows = []
    for raw in completed.stdout.splitlines():
        values = [value.strip() for value in raw.split(",")]
        if len(values) != 4:
            continue
        try:
            rows.append(tuple(float(value) for value in values))
        except ValueError:
            continue
    if not rows:
        return None
    return {
        "power_w": sum(row[0] for row in rows),
        "vram_mib": sum(row[1] for row in rows),
        "utilization_percent": max(row[2] for row in rows),
        "temperature_c": max(row[3] for row in rows),
    }


def _summarize_resource_samples(
    samples: list[dict[str, Any]],
    gpu_samples: list[dict[str, float]],
) -> dict[str, Any]:
    measured = [row for row in samples if row.get("rss_bytes") is not None]
    result: dict[str, Any] = {
        "measurement_status": "MEASURED" if measured else "PARTIAL_OR_UNAVAILABLE",
        "sample_count": len(samples),
        "cpu_seconds": max((float(row.get("cpu_seconds") or 0.0) for row in measured), default=None),
        "peak_rss_bytes": max((int(row.get("rss_bytes") or 0) for row in measured), default=None),
        "read_bytes": max((int(row.get("read_bytes") or 0) for row in measured), default=None),
        "write_bytes": max((int(row.get("write_bytes") or 0) for row in measured), default=None),
    }
    if not gpu_samples:
        result["gpu"] = {
            "status": "NOT_SAMPLED",
            "scope": "HOST_NVIDIA_GLOBAL",
            "sample_count": 0,
        }
        return result
    watt_hours = 0.0
    for left, right in zip(gpu_samples, gpu_samples[1:]):
        dt = max(0.0, float(right["t"]) - float(left["t"]))
        watt_hours += ((float(left["power_w"]) + float(right["power_w"])) / 2.0) * dt / 3600.0
    result["gpu"] = {
        "status": "MEASURED_BEST_EFFORT",
        "scope": "HOST_NVIDIA_GLOBAL",
        "sample_count": len(gpu_samples),
        "peak_vram_mib": max(float(row["vram_mib"]) for row in gpu_samples),
        "peak_utilization_percent": max(float(row["utilization_percent"]) for row in gpu_samples),
        "peak_power_w": max(float(row["power_w"]) for row in gpu_samples),
        "peak_temperature_c": max(float(row["temperature_c"]) for row in gpu_samples),
        "watt_hours": watt_hours,
        "boundary": (
            "Host-global GPU sampling is valid for isolated local-model trials; concurrent GPU workloads "
            "must be treated as contamination."
        ),
    }
    return result


def _run_process(
    argv: Iterable[str],
    *,
    cwd: str | Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
    measure_resources: bool = False,
    sample_gpu: bool = False,
    sample_interval_s: float = 0.5,
) -> dict[str, Any]:
    started = time.monotonic()
    if not measure_resources:
        try:
            completed = subprocess.run(
                [str(x) for x in argv],
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=float(timeout_s),
                shell=False,
            )
            return {
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timeout": False,
                "error": None,
                "elapsed_s": time.monotonic() - started,
                "resources": {"measurement_status": "DISABLED", "sample_count": 0},
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "returncode": None,
                "stdout": exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                "stderr": exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
                "timeout": True,
                "error": "TIMEOUT",
                "elapsed_s": time.monotonic() - started,
                "resources": {"measurement_status": "DISABLED", "sample_count": 0},
            }
        except FileNotFoundError as exc:
            return {
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "timeout": False,
                "error": "EXECUTABLE_NOT_FOUND: " + str(exc),
                "elapsed_s": time.monotonic() - started,
                "resources": {"measurement_status": "DISABLED", "sample_count": 0},
            }

    try:
        process = subprocess.Popen(
            [str(x) for x in argv],
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timeout": False,
            "error": "EXECUTABLE_NOT_FOUND: " + str(exc),
            "elapsed_s": time.monotonic() - started,
            "resources": {"measurement_status": "UNAVAILABLE", "sample_count": 0},
        }

    stop = threading.Event()
    samples: list[dict[str, Any]] = []
    gpu_samples: list[dict[str, float]] = []

    def sample() -> None:
        try:
            import psutil
            root_process = psutil.Process(process.pid)
        except Exception:
            root_process = None
        last_gpu = -10.0
        while not stop.wait(max(0.1, float(sample_interval_s))):
            now = time.monotonic() - started
            row: dict[str, Any] = {"t": now}
            if root_process is not None:
                try:
                    family = [root_process, *root_process.children(recursive=True)]
                    rss = 0
                    cpu = 0.0
                    read_bytes = 0
                    write_bytes = 0
                    for child in family:
                        try:
                            with child.oneshot():
                                rss += int(child.memory_info().rss)
                                times = child.cpu_times()
                                cpu += float(times.user) + float(times.system)
                                io = child.io_counters()
                                read_bytes += int(getattr(io, "read_bytes", 0))
                                write_bytes += int(getattr(io, "write_bytes", 0))
                        except Exception:
                            continue
                    row.update({
                        "rss_bytes": rss,
                        "cpu_seconds": cpu,
                        "read_bytes": read_bytes,
                        "write_bytes": write_bytes,
                    })
                except Exception:
                    pass
            samples.append(row)
            if sample_gpu and now - last_gpu >= 1.0:
                gpu = _nvidia_snapshot()
                last_gpu = now
                if gpu is not None:
                    gpu_samples.append({"t": now, **gpu})

    thread = threading.Thread(target=sample, name="tomography-resource-sampler", daemon=True)
    thread.start()
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=float(timeout_s))
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            import psutil
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                try:
                    child.kill()
                except Exception:
                    pass
        except Exception:
            pass
        process.kill()
        stdout, stderr = process.communicate()
    finally:
        stop.set()
        thread.join(timeout=3.0)

    resources = _summarize_resource_samples(samples, gpu_samples)
    return {
        "ok": process.returncode == 0 and not timed_out,
        "returncode": process.returncode,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "timeout": timed_out,
        "error": "TIMEOUT" if timed_out else None,
        "elapsed_s": time.monotonic() - started,
        "resources": resources,
    }


def git_snapshot(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    def run(*args: str) -> dict[str, Any]:
        return _run_process(("git", *args), cwd=root_path, timeout_s=30)

    head = run("rev-parse", "HEAD")
    status = run("status", "--porcelain=v1", "--untracked-files=all")
    diff = run("diff", "--no-ext-diff", "--binary")
    staged = run("diff", "--cached", "--no-ext-diff", "--binary")
    return {
        "head": head["stdout"].strip() if head["ok"] else None,
        "status": status["stdout"],
        "diff": diff["stdout"],
        "staged_diff": staged["stdout"],
        "git_errors": [
            value["error"] or value["stderr"]
            for value in (head, status, diff, staged)
            if not value["ok"]
        ],
    }


def materialize_workspace(template: str | Path, destination: str | Path) -> Path:
    source = Path(template).resolve()
    target = Path(destination).resolve()
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, symlinks=True)
    return target


def run_check(check: dict[str, Any], *, cwd: str | Path, default_timeout_s: float = 120.0) -> dict[str, Any]:
    argv = check.get("argv")
    if not isinstance(argv, list) or not argv:
        raise ValueError("check.argv must be a non-empty argv list")
    import sys
    expanded = [
        str(x).replace("{workspace}", str(Path(cwd).resolve())).replace("{python}", sys.executable)
        for x in argv
    ]
    result = _run_process(
        expanded,
        cwd=cwd,
        timeout_s=float(check.get("timeout_s", default_timeout_s)),
    )
    return {
        "id": str(check.get("id") or "check"),
        "kind": str(check.get("kind") or "oracle"),
        "argv": expanded,
        **result,
    }


def preservation_results(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    protected_paths: Iterable[str],
) -> list[dict[str, Any]]:
    left = {row["path"]: row for row in before.get("files", [])}
    right = {row["path"]: row for row in after.get("files", [])}
    results = []
    for path in protected_paths:
        p = str(path).replace("\\", "/")
        before_row = left.get(p)
        after_row = right.get(p)
        unchanged = bool(
            before_row is not None
            and after_row is not None
            and before_row.get("sha256") == after_row.get("sha256")
        )
        results.append(
            {
                "path": p,
                "unchanged": unchanged,
                "before_sha256": before_row.get("sha256") if before_row else None,
                "after_sha256": after_row.get("sha256") if after_row else None,
            }
        )
    return results


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def _hash_packet(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(p for p in root.iterdir() if p.is_file() and p.name != "SHA256SUMS.json"):
        rows.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    _write_json(root / "SHA256SUMS.json", {"artifacts": rows})
    return rows


def run_subject_trial(
    *,
    task: dict[str, Any],
    subject: dict[str, Any],
    workspace: str | Path,
    evidence_root: str | Path,
    timeout_s: float = 1800.0,
    observer_event_files: Iterable[str | Path] = (),
    rollout_path_template: str | None = None,
    auto_codex_rollout_lookup: bool = False,
    resume_session_id: str | None = None,
    gateway_event_files: Iterable[str | Path] = (),
) -> dict[str, Any]:
    """Run one clean coding-agent session and preserve all observable evidence."""
    root = Path(evidence_root)
    root.mkdir(parents=True, exist_ok=True)
    workspace_path = Path(workspace).resolve()

    instruction_surfaces = capture_instruction_surfaces(workspace_path)
    _write_json(root / "model-visible-instruction-surfaces.json", instruction_surfaces)

    pre_manifest = workspace_manifest(workspace_path)
    pre_git = git_snapshot(workspace_path)
    _write_json(root / "workspace-before.json", pre_manifest)
    _write_json(root / "git-before.json", pre_git)

    if resume_session_id:
        command = resume_command_for_subject(
            str(subject["name"]),
            session_id=str(resume_session_id),
            prompt=str(task["prompt"]),
            cwd=workspace_path,
            executable=subject.get("executable"),
            extra_args=subject.get("extra_args") or (),
        )
    else:
        command = command_for_subject(
            str(subject["name"]),
            prompt=str(task["prompt"]),
            cwd=workspace_path,
            executable=subject.get("executable"),
            extra_args=subject.get("extra_args") or (),
        )
    _write_json(root / "subject-command.json", subject_command_provenance(command))
    _write_json(root / "environment-shape.json", sanitize_environment_snapshot())

    env = os.environ.copy()
    for key, value in command.environment_overrides.items():
        env[str(key)] = str(value)
    runtime_overrides = dict(subject.get("environment_overrides") or {})
    for key, value in runtime_overrides.items():
        env[str(key)] = str(value)
    _write_json(root / "subject-runtime-routing.json", {
        "identity": model_harness_identity(subject),
        "environment_override_names": sorted(str(key) for key in runtime_overrides),
        "gateway_event_file_count": len(tuple(gateway_event_files)),
        "secret_values_recorded": False,
    })

    run = _run_process(
        command.argv,
        cwd=workspace_path,
        timeout_s=timeout_s,
        env=env,
        measure_resources=True,
        sample_gpu=bool(
            str(subject.get("compute_scope") or "remote") == "local"
            and subject.get("gpu_sampling", False)
        ),
        sample_interval_s=float(subject.get("resource_sample_interval_s", 0.5)),
    )
    (root / "subject-stdout.txt").write_text(str(run["stdout"]), encoding="utf-8")
    (root / "subject-stderr.txt").write_text(str(run["stderr"]), encoding="utf-8")
    _write_json(
        root / "subject-process.json",
        {key: value for key, value in run.items() if key not in {"stdout","stderr"}},
    )

    parsed = parse_jsonl_stream(str(run["stdout"]))
    _write_jsonl(root / "subject-native-events.jsonl", [row["event"] for row in parsed["events"]])
    _write_json(root / "subject-non-json.json", parsed["non_json"])

    raw_events = [row["event"] for row in parsed["events"]]
    session_id = extract_subject_session_id(command.subject, parsed["events"])
    quota_status = classify_provider_quota_exhaustion(
        subject,
        stdout=str(run["stdout"]),
        stderr=str(run["stderr"]),
        raw_events=raw_events,
    )
    _write_json(root / "provider-quota-status.json", quota_status)
    gateway_rows = load_external_event_files(gateway_event_files)
    _write_jsonl(root / "gateway-events.jsonl", gateway_rows)
    observer_rows: list[dict[str, Any]] = []

    rollout_path = resolve_rollout_path(
        rollout_path_template,
        session_id=session_id,
    )
    rollout_lookup: dict[str, Any] | None = None
    if (
        rollout_path is None
        and auto_codex_rollout_lookup
        and command.subject == "codex"
        and session_id
    ):
        rollout_lookup = locate_codex_rollout_by_thread_id(session_id)
        if rollout_lookup.get("status") == "FOUND":
            rollout_path = Path(str(rollout_lookup["path"]))

    rollout_rows: list[dict[str, Any]] = []
    if rollout_path is not None:
        rollout_rows = load_rollout_jsonl(rollout_path)
        _write_jsonl(root / "codex-rollout-events.jsonl", rollout_rows)
        projected_rollout = codex_rollout_observable_events(rollout_rows)
        _write_jsonl(root / "codex-rollout-observable-events.jsonl", projected_rollout)
        _write_json(
            root / "codex-rollout-provenance.json",
            {
                "path": str(rollout_path),
                "session_id": session_id,
                "rows": len(rollout_rows),
                "observable_rows": len(projected_rollout),
                "selection_rule": (
                    "exact user-supplied path template with session_id substitution"
                    if rollout_path_template
                    else "exact emitted thread_id filename lookup inside CODEX_HOME/sessions only"
                ),
                "home_scan_performed": False,
                "lookup": rollout_lookup,
            },
        )
        for value in projected_rollout:
            row = dict(value)
            row.setdefault("observer_source", str(rollout_path))
            observer_rows.append(row)
    elif auto_codex_rollout_lookup and command.subject == "codex":
        _write_json(
            root / "codex-rollout-provenance.json",
            {
                "path": None,
                "session_id": session_id,
                "rows": 0,
                "observable_rows": 0,
                "selection_rule": "exact emitted thread_id filename lookup inside CODEX_HOME/sessions only",
                "home_scan_performed": False,
                "lookup": rollout_lookup,
            },
        )
    for observer_path in observer_event_files:
        path = Path(observer_path)
        if not path.is_file():
            continue
        for line_number, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except Exception:
                value = {
                    "type": "observer_unparsed",
                    "source_path": str(path),
                    "line_number": line_number,
                    "raw_text": raw,
                }
            if isinstance(value, dict):
                value = dict(value)
                value.setdefault("observer_source", str(path))
                observer_rows.append(value)

    _write_jsonl(root / "observer-events.jsonl", observer_rows)

    observable_native = expand_observable_subject_stream(command.subject, raw_events)
    observable_observer = expand_observable_subject_stream(command.subject, observer_rows)
    _write_jsonl(root / "observable-native-events.jsonl", observable_native)
    _write_jsonl(root / "observable-observer-events.jsonl", observable_observer)
    normalized_native = [
        {**row, "channel":"native_stdout", "channel_sequence":index}
        for index, row in enumerate(
            normalize_events(command.subject, observable_native),
            start=1,
        )
    ]
    normalized_observer = [
        {**row, "channel":"observer", "channel_sequence":index}
        for index, row in enumerate(
            normalize_events(command.subject, observable_observer),
            start=1,
        )
    ]
    _write_jsonl(root / "normalized-native-trajectory.jsonl", normalized_native)
    _write_jsonl(root / "normalized-observer-trajectory.jsonl", normalized_observer)
    normalized = []
    for index, row in enumerate([*normalized_native, *normalized_observer], start=1):
        normalized.append({**row, "sequence":index})
    _write_jsonl(root / "normalized-trajectory.jsonl", normalized)

    unknown_native = sum(row.get("event_type") == "UNKNOWN" for row in normalized_native)
    unknown_observer = sum(row.get("event_type") == "UNKNOWN" for row in normalized_observer)
    channel_coverage = {
        "schema_version":1,
        "native_json_event_count":len(raw_events),
        "native_observable_event_count":len(observable_native),
        "native_normalized_event_count":len(normalized_native),
        "native_unknown_event_count":unknown_native,
        "observer_raw_or_projected_event_count":len(observer_rows),
        "observer_observable_event_count":len(observable_observer),
        "observer_normalized_event_count":len(normalized_observer),
        "observer_unknown_event_count":unknown_observer,
        "non_json_stdout_line_count":len(parsed["non_json"]),
        "codex_rollout_rows":len(rollout_rows),
        "session_id":session_id,
        "performance_metric_channel":"native_stdout_only",
    }
    _write_json(root / "channel-coverage.json", channel_coverage)

    post_manifest = workspace_manifest(workspace_path)
    post_git = git_snapshot(workspace_path)
    change_map = manifest_diff(pre_manifest, post_manifest)
    _write_json(root / "workspace-after.json", post_manifest)
    _write_json(root / "workspace-diff.json", change_map)
    _write_json(root / "git-after.json", post_git)

    compute_cost = build_compute_cost(
        subject=subject,
        run=run,
        raw_events=raw_events,
        change_map=change_map,
    )
    _write_json(root / "compute-cost.json", compute_cost)

    if quota_status.get("status") == "PROVIDER_QUOTA_EXHAUSTED":
        exposure = build_exposure_manifest(
            subject=subject,
            quota_status=quota_status,
            compute_cost=compute_cost,
            native_event_count=len(raw_events),
            observer_event_count=len(observer_rows),
            gateway_event_count=len(gateway_rows),
            instruction_surface_count=len(instruction_surfaces.get("surfaces") or []),
        )
        _write_json(root / "exposure-manifest.json", exposure)
        metrics = {
            "subject_exit_ok": bool(run["ok"]),
            "subject_timeout": bool(run["timeout"]),
            "subject_elapsed_s": float(run["elapsed_s"]),
            "session_id": session_id,
            "native_event_count": len(raw_events),
            "observer_event_count": len(observer_rows),
            "quota_terminal": True,
        }
        summary = {
            "schema_version": 1,
            "task_id": task.get("task_id") or task.get("case_id"),
            "subject": subject.get("name"),
            "subject_command": asdict(command),
            "resume_session_id": str(resume_session_id) if resume_session_id else None,
            "scored": False,
            "trial_status": "PROVIDER_QUOTA_EXHAUSTED",
            "oracle_success": None,
            "visible_checks_ok": None,
            "hidden_oracle_ok": None,
            "preservation_ok": None,
            "response_oracle_ok": None,
            "metrics": metrics,
            "workspace_diff": change_map,
            "channel_coverage": channel_coverage,
            "provider_quota_status": quota_status,
            "model_harness": model_harness_identity(subject),
            "failure_replay_id": None,
            "evidence_root": str(root),
        }
        _write_json(root / "trial-summary.json", summary)
        _hash_packet(root)
        return summary

    visible_results = [
        run_check(check, cwd=workspace_path)
        for check in (task.get("visible_checks") or [])
    ]
    hidden_results = [
        run_check(check, cwd=workspace_path)
        for check in (task.get("hidden_oracle_checks") or [])
    ]
    preservation = preservation_results(
        before=pre_manifest,
        after=post_manifest,
        protected_paths=task.get("protected_paths") or (),
    )
    _write_json(root / "visible-check-results.json", visible_results)
    _write_json(root / "hidden-oracle-results.json", hidden_results)
    _write_json(root / "preservation-results.json", preservation)

    hidden_ok = bool(hidden_results) and all(bool(row["ok"]) for row in hidden_results)
    visible_ok = all(bool(row["ok"]) for row in visible_results) if visible_results else None
    preservation_ok = all(bool(row["unchanged"]) for row in preservation) if preservation else True

    final_text = extract_observable_final_text(command.subject, raw_events)
    (root / "observable-final-response.txt").write_text(final_text, encoding="utf-8")
    response_oracle = task.get("response_oracle")
    response_oracle_result = None
    if isinstance(response_oracle, dict):
        import re
        lower = final_text.lower()
        contains_all = [
            str(value).lower() for value in response_oracle.get("must_contain_all") or []
        ]
        contains_any = [
            str(value).lower() for value in response_oracle.get("must_contain_any") or []
        ]
        forbidden = [
            str(value).lower() for value in response_oracle.get("must_not_contain") or []
        ]
        regexes = [str(value) for value in response_oracle.get("regex") or []]
        text_ok = all(value in lower for value in contains_all)
        if contains_any:
            text_ok = text_ok and any(value in lower for value in contains_any)
        text_ok = text_ok and all(value not in lower for value in forbidden)
        text_ok = text_ok and all(re.search(pattern, final_text, re.IGNORECASE | re.MULTILINE) is not None for pattern in regexes)
        no_edit_ok = (
            int(change_map["changed_count"]) == 0
            if bool(response_oracle.get("must_not_modify_files"))
            else True
        )
        response_oracle_result = {
            "text_ok": bool(text_ok),
            "no_edit_ok": bool(no_edit_ok),
            "success": bool(text_ok and no_edit_ok),
            "must_contain_all": contains_all,
            "must_contain_any": contains_any,
            "must_not_contain": forbidden,
            "regex": regexes,
            "must_not_modify_files": bool(response_oracle.get("must_not_modify_files")),
        }
        _write_json(root / "response-oracle-result.json", response_oracle_result)

    response_ok = (
        bool(response_oracle_result["success"])
        if response_oracle_result is not None
        else True
    )
    oracle_success = bool(hidden_ok and preservation_ok and response_ok)

    metrics = trajectory_metrics(normalized_native, oracle_success=oracle_success)
    observer_metrics = trajectory_metrics(normalized_observer, oracle_success=oracle_success) if normalized_observer else None
    metrics.update(
        {
            "subject_exit_ok": bool(run["ok"]),
            "subject_timeout": bool(run["timeout"]),
            "subject_elapsed_s": float(run["elapsed_s"]),
            "visible_checks_ok": visible_ok,
            "hidden_oracle_ok": hidden_ok,
            "preservation_ok": preservation_ok,
            "response_oracle_ok": response_ok,
            "observable_final_response_chars": len(final_text),
            "changed_file_count": int(change_map["changed_count"]),
            "session_id": session_id,
            "native_event_count": len(raw_events),
            "observer_event_count": len(observer_rows),
            "non_json_line_count": len(parsed["non_json"]),
            "observer_metrics_available": observer_metrics is not None,
        }
    )
    _write_json(root / "trajectory-metrics.json", metrics)
    _write_json(root / "observer-trajectory-metrics.json", observer_metrics or {"status":"NO_OBSERVER_EVENTS"})

    candidate_mechanisms = list(task.get("candidate_mechanisms") or [])
    replay = None
    if not oracle_success:
        replay = failure_replay_packet(
            task=task,
            subject=subject,
            workspace_manifest=pre_manifest,
            normalized_events=normalized_native,
            oracle_result={
                "success": oracle_success,
                "visible_results": visible_results,
                "hidden_results": hidden_results,
                "preservation": preservation,
                "response_oracle": response_oracle_result,
            },
            candidate_mechanisms=candidate_mechanisms,
        )
        _write_json(root / "failure-replay.json", replay)

    exposure = build_exposure_manifest(
        subject=subject,
        quota_status=quota_status,
        compute_cost=compute_cost,
        native_event_count=len(raw_events),
        observer_event_count=len(observer_rows),
        gateway_event_count=len(gateway_rows),
        instruction_surface_count=len(instruction_surfaces.get("surfaces") or []),
    )
    _write_json(root / "exposure-manifest.json", exposure)

    summary = {
        "schema_version":1,
        "task_id":task.get("task_id") or task.get("case_id"),
        "subject":subject.get("name"),
        "subject_command":asdict(command),
        "resume_session_id":str(resume_session_id) if resume_session_id else None,
        "scored": True,
        "trial_status": "SCORED",
        "model_harness": model_harness_identity(subject),
        "provider_quota_status": quota_status,
        "oracle_success":oracle_success,
        "visible_checks_ok":visible_ok,
        "hidden_oracle_ok":hidden_ok,
        "preservation_ok":preservation_ok,
        "response_oracle_ok":response_ok,
        "metrics":metrics,
        "workspace_diff":change_map,
        "channel_coverage":channel_coverage,
        "failure_replay_id":replay.get("replay_id") if replay else None,
        "evidence_root":str(root),
    }
    _write_json(root / "trial-summary.json", summary)
    _hash_packet(root)
    return summary
