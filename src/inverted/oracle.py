from __future__ import annotations

from typing import Any
import copy

from .domain import Action, OracleResult, TaskCase, WorldState


def _parts(path: str) -> list[str]:
    return [p for p in path.split(".") if p]


def get_path(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in _parts(path):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _ensure_parent(data: dict[str, Any], path: str) -> tuple[dict[str, Any], str]:
    parts = _parts(path)
    if not parts:
        raise ValueError("path must not be empty")
    cur = data
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    return cur, parts[-1]


def apply_actions(initial_state: WorldState, actions: tuple[Action, ...] | list[Action]) -> WorldState:
    data = copy.deepcopy(initial_state.data)
    for action in actions:
        parent, leaf = _ensure_parent(data, action.path)
        if action.op in {"set", "move", "grant", "revoke", "start", "stop", "add", "resolve"}:
            parent[leaf] = copy.deepcopy(action.value)
        elif action.op in {"delete", "remove"}:
            parent.pop(leaf, None)
        else:
            raise ValueError(f"unsupported action op: {action.op}")
    return WorldState(data)


def evaluate_task(task: TaskCase, state: WorldState, actions: tuple[Action, ...] | list[Action]) -> OracleResult:
    results: dict[str, bool] = {}
    action_list = list(actions)
    for req in task.requirements:
        if req.kind == "equal":
            ok = get_path(state.data, req.path) == req.expected
        elif req.kind == "preserve":
            ok = get_path(state.data, req.path) == req.expected
        elif req.kind == "action_present":
            ok = any(a.op == req.path and (req.expected is None or a.path == req.expected) for a in action_list)
        elif req.kind == "action_absent":
            ok = not any(a.op == req.path and (req.expected is None or a.path == req.expected) for a in action_list)
        elif req.kind == "action_before":
            before_op = req.path
            after_op = str(req.expected)
            before_idx = next((i for i, a in enumerate(action_list) if a.op == before_op), None)
            after_idx = next((i for i, a in enumerate(action_list) if a.op == after_op), None)
            ok = before_idx is not None and after_idx is not None and before_idx < after_idx
        else:
            raise ValueError(f"unsupported requirement kind: {req.kind}")
        results[req.id] = ok
    failed = tuple(r.id for r in task.requirements if not results[r.id])
    passed = tuple(r.id for r in task.requirements if results[r.id])
    catastrophic = any(r.critical and not results[r.id] for r in task.requirements)
    return OracleResult(not failed, passed, failed, catastrophic, results)
