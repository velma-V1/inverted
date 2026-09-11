from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Iterable

from .coding_subjects import (
    SubjectCommand,
    command_for_subject,
    extract_subject_session_id,
    parse_jsonl_stream,
    sanitize_environment_snapshot,
    subject_command_provenance,
)
from .coding_tomography import (
    failure_replay_packet,
    normalize_events,
    trajectory_metrics,
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


def _run_process(
    argv: Iterable[str],
    *,
    cwd: str | Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
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
        }
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "timeout": False,
            "error": f"EXECUTABLE_NOT_FOUND: {exc}",
            "elapsed_s": time.monotonic() - started,
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
) -> dict[str, Any]:
    """Run one clean coding-agent session and preserve all observable evidence."""
    root = Path(evidence_root)
    root.mkdir(parents=True, exist_ok=True)
    workspace_path = Path(workspace).resolve()

    pre_manifest = workspace_manifest(workspace_path)
    pre_git = git_snapshot(workspace_path)
    _write_json(root / "workspace-before.json", pre_manifest)
    _write_json(root / "git-before.json", pre_git)

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

    run = _run_process(command.argv, cwd=workspace_path, timeout_s=timeout_s, env=env)
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
    observer_rows: list[dict[str, Any]] = []
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

    normalized_native = normalize_events(command.subject, raw_events)
    normalized_observer = normalize_events(command.subject, observer_rows)
    normalized = []
    for row in normalized_native:
        normalized.append({**row, "channel":"native_stdout"})
    offset = len(normalized)
    for index, row in enumerate(normalized_observer, start=1):
        normalized.append({**row, "sequence":offset + index, "channel":"observer"})
    _write_jsonl(root / "normalized-trajectory.jsonl", normalized)

    post_manifest = workspace_manifest(workspace_path)
    post_git = git_snapshot(workspace_path)
    change_map = manifest_diff(pre_manifest, post_manifest)
    _write_json(root / "workspace-after.json", post_manifest)
    _write_json(root / "workspace-diff.json", change_map)
    _write_json(root / "git-after.json", post_git)

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
    oracle_success = bool(hidden_ok and preservation_ok)

    metrics = trajectory_metrics(normalized, oracle_success=oracle_success)
    metrics.update(
        {
            "subject_exit_ok": bool(run["ok"]),
            "subject_timeout": bool(run["timeout"]),
            "subject_elapsed_s": float(run["elapsed_s"]),
            "visible_checks_ok": visible_ok,
            "hidden_oracle_ok": hidden_ok,
            "preservation_ok": preservation_ok,
            "changed_file_count": int(change_map["changed_count"]),
            "session_id": extract_subject_session_id(command.subject, parsed["events"]),
            "native_event_count": len(raw_events),
            "observer_event_count": len(observer_rows),
            "non_json_line_count": len(parsed["non_json"]),
        }
    )
    _write_json(root / "trajectory-metrics.json", metrics)

    candidate_mechanisms = list(task.get("candidate_mechanisms") or [])
    replay = None
    if not oracle_success:
        replay = failure_replay_packet(
            task=task,
            subject=subject,
            workspace_manifest=pre_manifest,
            normalized_events=normalized,
            oracle_result={
                "success": oracle_success,
                "visible_results": visible_results,
                "hidden_results": hidden_results,
                "preservation": preservation,
            },
            candidate_mechanisms=candidate_mechanisms,
        )
        _write_json(root / "failure-replay.json", replay)

    summary = {
        "schema_version":1,
        "task_id":task.get("task_id") or task.get("case_id"),
        "subject":subject.get("name"),
        "subject_command":asdict(command),
        "oracle_success":oracle_success,
        "visible_checks_ok":visible_ok,
        "hidden_oracle_ok":hidden_ok,
        "preservation_ok":preservation_ok,
        "metrics":metrics,
        "workspace_diff":change_map,
        "failure_replay_id":replay.get("replay_id") if replay else None,
        "evidence_root":str(root),
    }
    _write_json(root / "trial-summary.json", summary)
    _hash_packet(root)
    return summary
