from __future__ import annotations

import hashlib
import random
from typing import Any

from .domain import Action, Requirement, TaskCase, WorldState
from .oracle import apply_actions

_RANGES = {1: (1, 2), 2: (3, 5), 3: (6, 9), 4: (10, 15)}


def _task_id(family: str, complexity: int, seed: int) -> str:
    digest = hashlib.sha256(f"{family}:{complexity}:{seed}".encode()).hexdigest()[:12]
    return f"{family}-L{complexity}-{digest}"


def _state_family(n: int, rng: random.Random):
    initial: dict[str, Any] = {"items": {}, "guard": {"locked": True}}
    requirements: list[Requirement] = []
    actions: list[Action] = []
    for i in range(n):
        path = f"items.item{i}.value"
        initial["items"][f"item{i}"] = {"value": 0}
        expected = rng.randint(1, 9)
        requirements.append(Requirement(f"r{i+1}", "equal", path, expected, critical=(i == n - 1 and n >= 6), metadata={"op": "set"}))
        actions.append(Action("set", path, expected))
    return WorldState(initial), tuple(requirements), tuple(actions), ("set", "delete")


def _policy_family(n: int, rng: random.Random):
    initial: dict[str, Any] = {"workflow": {f"step{i}": False for i in range(max(2, n))}, "protected": {"flag": True}}
    requirements: list[Requirement] = []
    actions: list[Action] = []
    state_count = max(1, n - (2 if n >= 3 else 0))
    for i in range(state_count):
        path = f"workflow.step{i}"
        # Keep the ordinary state changes simple; the explicit ordering rule introduces resolve.
        requirements.append(Requirement(f"r{i+1}", "equal", path, True, critical=(i == state_count - 1 and n >= 10), metadata={"op": "set"}))
        actions.append(Action("set", path, True))
    if len(requirements) < n:
        requirements.append(Requirement(f"r{len(requirements)+1}", "action_absent", "delete", None, critical=True))
    if len(requirements) < n:
        after_action = {"op": "resolve", "path": "workflow.finalized", "value": True}
        requirements.append(Requirement(
            f"r{len(requirements)+1}", "action_before", "set", "resolve",
            metadata={"after_action": after_action}
        ))
        actions.append(Action(**after_action))
    return WorldState(initial), tuple(requirements[:n]), tuple(actions), ("set", "resolve", "delete")


def _reconciliation_family(n: int, rng: random.Random):
    initial: dict[str, Any] = {"sources": {}, "resolved": {}}
    requirements: list[Requirement] = []
    actions: list[Action] = []
    for i in range(n):
        canonical = f"v{rng.randint(10, 999)}"
        stale = f"stale{rng.randint(10, 999)}"
        initial["sources"][f"field{i}"] = {"primary": canonical, "secondary": stale}
        initial["resolved"][f"field{i}"] = None
        path = f"resolved.field{i}"
        requirements.append(Requirement(
            f"r{i+1}", "equal", path, canonical,
            critical=(i == n - 1 and n >= 6),
            metadata={"source_priority": "primary", "op": "resolve"},
        ))
        actions.append(Action("resolve", path, canonical))
    return WorldState(initial), tuple(requirements), tuple(actions), ("resolve", "delete")


def _public_requirements(requirements: tuple[Requirement, ...]) -> list[dict[str, Any]]:
    return [
        {"id": r.id, "kind": r.kind, "path": r.path, "expected": r.expected, "metadata": dict(r.metadata)}
        for r in requirements
    ]


def generate_task(family: str, complexity: int, seed: int) -> TaskCase:
    if complexity not in _RANGES:
        raise ValueError("complexity must be 1..4")
    if family not in {"state", "policy", "reconciliation"}:
        raise ValueError(f"unknown family: {family}")
    rng = random.Random((seed * 1315423911) ^ (complexity * 2654435761) ^ sum(map(ord, family)))
    lo, hi = _RANGES[complexity]
    n = rng.randint(lo, hi)
    if family == "state":
        initial, requirements, actions, allowed = _state_family(n, rng)
    elif family == "policy":
        initial, requirements, actions, allowed = _policy_family(n, rng)
    else:
        initial, requirements, actions, allowed = _reconciliation_family(n, rng)
    target = apply_actions(initial, actions)
    goal_parts = []
    for r in requirements:
        if r.kind == "equal":
            goal_parts.append(f"set {r.path} to {r.expected!r}")
        elif r.kind == "action_absent":
            goal_parts.append(f"never use operation {r.path}")
        elif r.kind == "action_before":
            goal_parts.append(f"perform {r.path} before {r.expected}")
    goal = "; ".join(goal_parts)
    return TaskCase(
        id=_task_id(family, complexity, seed),
        family=family,
        complexity=complexity,
        goal=goal,
        initial_state=initial,
        target_state=target,
        requirements=requirements,
        allowed_ops=allowed,
        metadata={"seed": seed, "public_requirements": _public_requirements(requirements)},
    )
