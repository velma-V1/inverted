"""Immutable preregistration for the canonical static 2A-0 campaign."""

from __future__ import annotations

import csv
from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from .config import canonical_a0_planner_config, validate_a0_planner_config
from .ingredients import initial_ingredient_registry
from .stages import build_canonical_a0_plan
from .types import StageId, StagePlan


FROZEN_INPUT_FILES = (
    "config.json", "ingredient_registry.json", "frozen_case_manifest.json",
    "frozen_schedule.jsonl", "selection_rule.json", "action_budget.json",
    "runtime_plan.json", "statistical_rule.json",
    "physical_execution_authorization.json",
)


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _source_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _bound_python_sources(root: Path) -> tuple[str, ...]:
    harvest = root / "src" / "inverted" / "harvest_d"
    live = list(harvest.glob("*.py")) + list((harvest / "hd_next2").glob("*.py"))
    return tuple(sorted(path.relative_to(root).as_posix() for path in live))


def _git_text(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, timeout=10,
    )
    return completed.stdout.strip()


def _assert_recorded_commit_source(commit: str) -> None:
    root = _source_repo_root()
    try:
        resolved = _git_text(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
        head = _git_text(root, "rev-parse", "--verify", "HEAD^{commit}")
        if resolved != head:
            raise ValueError("recorded commit is not the current executing repository commit")
        live = set(_bound_python_sources(root))
        committed = {
            line for line in _git_text(
                root, "ls-tree", "-r", "--name-only", resolved, "--", "src/inverted/harvest_d"
            ).splitlines()
            if line.endswith(".py") and (
                Path(line).parent.as_posix() == "src/inverted/harvest_d"
                or Path(line).parent.as_posix() == "src/inverted/harvest_d/hd_next2"
            )
        }
        if live != committed or not live:
            raise ValueError("executing Test-1 source set does not match recorded commit")
        for relative in sorted(live):
            committed_blob = _git_text(root, "rev-parse", f"{resolved}:{relative}")
            live_blob = subprocess.run(
                ["git", "-C", str(root), "hash-object", "--stdin", f"--path={relative}"],
                input=(root / relative).read_bytes(), check=True, capture_output=True, timeout=10,
            ).stdout.decode("ascii").strip()
            if live_blob != committed_blob:
                raise ValueError("executing Test-1 source bytes differ from recorded commit")
        status = _git_text(root, "status", "--porcelain=v1", "--untracked-files=all", "--", *sorted(live))
        if status:
            raise ValueError("executing Test-1 source tree is dirty relative to recorded commit")
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("recorded repository commit/source binding could not be verified") from exc


def _repo_commit(repo: object) -> str:
    if not isinstance(repo, (str, Path)):
        raise ValueError("repository commit identity is required")
    path = Path(repo)
    try:
        commit = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--verify", "HEAD^{commit}"], check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("repository commit identity could not be resolved") from exc
    if len(commit) not in {40, 64} or any(character not in "0123456789abcdef" for character in commit.lower()):
        raise ValueError("repository commit identity is invalid")
    return commit


def _payloads_for_commit(commit: str, config: Mapping[str, Any], plan: StagePlan) -> dict[str, bytes]:
    if len(commit) not in {40, 64} or any(character not in "0123456789abcdef" for character in commit.lower()):
        raise ValueError("repository commit identity is invalid")
    units = [_plain(unit) for unit in plan.units]
    cases = {}
    for unit in units:
        cases[unit["case_id"]] = {
            "case_id": unit["case_id"], "partition": unit["partition"],
            "operating_region": unit["operating_region"],
        }
    registry = initial_ingredient_registry()
    config_payload = dict(_plain(config))
    config_payload["repo_commit"] = commit
    schedule = b"".join(_json_bytes(unit) for unit in units)
    return {
        "config.json": _json_bytes(config_payload),
        "ingredient_registry.json": _json_bytes({key: _plain(value) for key, value in sorted(registry.items())}),
        "frozen_case_manifest.json": _json_bytes({"stage_id": plan.stage.value, "cases": [cases[key] for key in sorted(cases)]}),
        "frozen_schedule.jsonl": schedule,
        "selection_rule.json": _json_bytes({"stage_id": plan.stage.value, "rule": "CANONICAL_A0_STATIC_ORDER", "adaptive": False}),
        "action_budget.json": _json_bytes({"combined_action_ceiling": config["combined_action_ceiling"], "forecast_combined_actions": plan.forecast_combined_actions, "model_calls": len(units), "blind_retries_allowed": False}),
        "runtime_plan.json": _json_bytes({"model_order": ["SMALL_A", "QWEN", "DEVSTRAL_24B"], "residency_blocks": True, "physical_execution": False}),
        "statistical_rule.json": _json_bytes({"stage_id": plan.stage.value, "purpose": "noise_baseline_runtime_calibration", "paired_by": ["model_key", "case_id", "replicate"], "promotion_allowed": False}),
        "physical_execution_authorization.json": _json_bytes({"stage_id": plan.stage.value, "execution": False, "owner_approved": False}),
    }


def canonical_a0_payloads_for_commit(commit: str) -> dict[str, bytes]:
    """Reconstruct A0 bytes only when executing source is exactly the recorded commit."""
    _assert_recorded_commit_source(commit)
    return _payloads_for_commit(
        commit, canonical_a0_planner_config(), build_canonical_a0_plan(),
    )


def _package_payloads(repo: object, config: Mapping[str, Any], plan: StagePlan) -> dict[str, bytes]:
    commit = _repo_commit(repo)
    _assert_recorded_commit_source(commit)
    return _payloads_for_commit(commit, config, plan)


def build_stage_preregistration(
    repo: object, output: str | Path, config: Mapping[str, Any], stage: StageId,
    plan: StagePlan,
) -> dict[str, Any]:
    """Freeze the exact canonical A0 inputs without enabling execution."""
    try:
        stage = StageId(stage)
    except ValueError as exc:
        raise ValueError("only canonical A0 preregistration is supported") from exc
    if stage is not StageId.A0 or plan.stage is not StageId.A0:
        raise ValueError("only canonical A0 preregistration is supported")
    validate_a0_planner_config(config)
    if _plain(config) != canonical_a0_planner_config():
        raise ValueError("config must be the exact canonical A0 config")
    if plan != build_canonical_a0_plan():
        raise ValueError("plan must be the exact canonical A0 StagePlan")
    target = Path(output)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError(f"preregistration package already exists: {target}")
    payloads = _package_payloads(repo, config, plan)
    target.mkdir(parents=True, exist_ok=True)
    for name in FROZEN_INPUT_FILES:
        (target / name).write_bytes(payloads[name])
    with (target / "SHA256SUMS.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("filename", "sha256"), lineterminator="\n")
        writer.writeheader()
        for name in FROZEN_INPUT_FILES:
            writer.writerow({"filename": name, "sha256": hashlib.sha256(payloads[name]).hexdigest()})
    return {"stage_id": stage.value, "output": str(target), "frozen_files": list(FROZEN_INPUT_FILES)}
