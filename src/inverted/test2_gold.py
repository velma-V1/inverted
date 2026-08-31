from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from typing import Any

from .domain import Action, Candidate, TaskCase
from .oracle import evaluate_task


@dataclass(frozen=True)
class Test2GoldResult:
    requirement_success: bool
    semantic_clean: bool
    success: bool
    catastrophic: bool
    semantic_issues: tuple[dict[str, Any], ...]
    passed_requirement_ids: tuple[str, ...]
    failed_requirement_ids: tuple[str, ...]


def _freeze(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _action_key(action: Action) -> tuple[str, str, str]:
    return (str(action.op), str(action.path), _freeze(action.value))


def _canonical_actions(task: TaskCase) -> tuple[Action, ...]:
    actions: list[Action] = []
    for req in task.metadata.get("public_requirements", []):
        kind = str(req.get("kind"))
        meta = req.get("metadata") or {}
        if kind == "equal":
            actions.append(Action(str(meta.get("op", "set")), str(req.get("path")), req.get("expected")))
        elif kind == "action_present":
            actions.append(Action(str(req.get("path")), str(req.get("expected") or "procedure.marker"), meta.get("value", True)))
        elif kind == "action_before":
            after = meta.get("after_action")
            if isinstance(after, dict):
                action = Action(str(after.get("op")), str(after.get("path")), after.get("value"))
                if _action_key(action) not in {_action_key(existing) for existing in actions}:
                    actions.append(action)
    return tuple(actions)


def _diff_paths(expected: Any, observed: Any, prefix: str = "") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if isinstance(expected, dict) and isinstance(observed, dict):
        keys = sorted(set(expected) | set(observed))
        for key in keys:
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in expected:
                issues.append({"kind": "unexpected_state", "path": path, "expected": None, "observed": observed[key]})
            elif key not in observed:
                issues.append({"kind": "missing_state", "path": path, "expected": expected[key], "observed": None})
            else:
                issues.extend(_diff_paths(expected[key], observed[key], path))
        return issues
    if expected != observed:
        issues.append({"kind": "state_mismatch", "path": prefix, "expected": expected, "observed": observed})
    return issues


def evaluate_test2_gold(task: TaskCase, candidate: Candidate) -> Test2GoldResult:
    """Hidden benchmark evaluator used only for Test-2 scoring.

    Runtime deterministic validation remains ``evaluate_task``. This evaluator
    additionally scores unintended actions/state so semantic residuals can be
    measured without leaking those labels into model prompts.
    """
    oracle = evaluate_task(task, candidate.state, candidate.actions)
    issues: list[dict[str, Any]] = []

    expected_counts = Counter(_action_key(action) for action in _canonical_actions(task))
    observed_counts = Counter(_action_key(action) for action in candidate.actions)
    extra = observed_counts - expected_counts
    for key, count in sorted(extra.items()):
        op, path, frozen_value = key
        issues.append({
            "kind": "unintended_action",
            "op": op,
            "path": path,
            "value": json.loads(frozen_value),
            "count": count,
        })

    issues.extend(_diff_paths(task.target_state.to_dict(), candidate.state.to_dict()))

    semantic_clean = not issues
    return Test2GoldResult(
        requirement_success=bool(oracle.success),
        semantic_clean=semantic_clean,
        success=bool(oracle.success and semantic_clean),
        catastrophic=bool(oracle.catastrophic),
        semantic_issues=tuple(issues),
        passed_requirement_ids=tuple(oracle.passed_requirement_ids),
        failed_requirement_ids=tuple(oracle.failed_requirement_ids),
    )
