from __future__ import annotations

import hashlib
import random
from typing import Any

from .domain import Action, Requirement, TaskCase, WorldState
from .oracle import apply_actions

_RANGES = {1: (1, 2), 2: (3, 5), 3: (6, 9), 4: (10, 15)}
_FAMILIES = {
    "state",
    "policy",
    "reconciliation",
    "preservation",
    "dependency_order",
    "repair_containment",
}


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


def _preservation_family(n: int, rng: random.Random, complexity: int):
    total = max(2, n)
    preserve_count = max(1, total // 3)
    mutable_count = total - preserve_count
    initial: dict[str, Any] = {"mutable": {}, "protected": {}}
    requirements: list[Requirement] = []
    actions: list[Action] = []

    for i in range(mutable_count):
        path = f"mutable.item{i}.value"
        initial["mutable"][f"item{i}"] = {"value": 0}
        expected = rng.randint(10, 99)
        requirements.append(Requirement(
            f"r{len(requirements)+1}", "equal", path, expected,
            metadata={"op": "set"},
        ))
        actions.append(Action("set", path, expected))

    for i in range(preserve_count):
        path = f"protected.item{i}.value"
        expected = f"keep-{rng.randint(100, 999)}"
        initial["protected"][f"item{i}"] = {"value": expected}
        requirements.append(Requirement(
            f"r{len(requirements)+1}", "preserve", path, expected,
            critical=(complexity == 4 and i == preserve_count - 1),
        ))

    return WorldState(initial), tuple(requirements), tuple(actions), ("set", "delete")


def _dependency_order_family(n: int, rng: random.Random):
    total = max(3, n)
    initial: dict[str, Any] = {
        "config": {},
        "access": {"token": False},
        "workflow": {"job": False},
    }
    requirements: list[Requirement] = []
    actions: list[Action] = []

    extra_count = total - 3
    for i in range(extra_count):
        path = f"config.step{i}"
        initial["config"][f"step{i}"] = False
        requirements.append(Requirement(
            f"r{len(requirements)+1}", "equal", path, True,
            metadata={"op": "set"},
        ))
        actions.append(Action("set", path, True))

    grant_action = {"op": "grant", "path": "access.token", "value": True}
    start_action = {"op": "start", "path": "workflow.job", "value": True}
    requirements.append(Requirement(
        f"r{len(requirements)+1}", "action_present", "grant", "access.token",
        metadata={"value": True},
    ))
    requirements.append(Requirement(
        f"r{len(requirements)+1}", "action_present", "start", "workflow.job",
        metadata={"value": True},
    ))
    requirements.append(Requirement(
        f"r{len(requirements)+1}", "action_before", "grant", "start",
        critical=(total >= 10),
        metadata={"before_action": grant_action, "after_action": start_action},
    ))
    actions.extend((Action(**grant_action), Action(**start_action)))
    return WorldState(initial), tuple(requirements), tuple(actions), ("set", "grant", "start", "delete")


def _repair_containment_family(n: int, rng: random.Random, complexity: int):
    total = max(3, n)
    mutable_count = max(2, total - 1)
    preserve_count = total - mutable_count
    initial: dict[str, Any] = {"work": {}, "protected": {}}
    requirements: list[Requirement] = []
    actions: list[Action] = []

    for i in range(mutable_count):
        path = f"work.item{i}.value"
        initial["work"][f"item{i}"] = {"value": 0}
        expected = rng.randint(100, 999)
        requirements.append(Requirement(
            f"r{len(requirements)+1}", "equal", path, expected,
            metadata={"op": "set"},
        ))
        actions.append(Action("set", path, expected))

    for i in range(preserve_count):
        path = f"protected.item{i}.value"
        expected = f"stable-{rng.randint(1000, 9999)}"
        initial["protected"][f"item{i}"] = {"value": expected}
        requirements.append(Requirement(
            f"r{len(requirements)+1}", "preserve", path, expected,
            critical=(complexity == 4 and i == preserve_count - 1),
        ))

    return WorldState(initial), tuple(requirements), tuple(actions), ("set", "delete")


def _public_requirements(requirements: tuple[Requirement, ...]) -> list[dict[str, Any]]:
    return [
        {"id": r.id, "kind": r.kind, "path": r.path, "expected": r.expected, "metadata": dict(r.metadata)}
        for r in requirements
    ]


def generate_task(family: str, complexity: int, seed: int) -> TaskCase:
    if complexity not in _RANGES:
        raise ValueError("complexity must be 1..4")
    if family not in _FAMILIES:
        raise ValueError(f"unknown family: {family}")
    rng = random.Random((seed * 1315423911) ^ (complexity * 2654435761) ^ sum(map(ord, family)))
    lo, hi = _RANGES[complexity]
    n = rng.randint(lo, hi)
    if family == "state":
        initial, requirements, actions, allowed = _state_family(n, rng)
    elif family == "policy":
        initial, requirements, actions, allowed = _policy_family(n, rng)
    elif family == "reconciliation":
        initial, requirements, actions, allowed = _reconciliation_family(n, rng)
    elif family == "preservation":
        initial, requirements, actions, allowed = _preservation_family(n, rng, complexity)
    elif family == "dependency_order":
        initial, requirements, actions, allowed = _dependency_order_family(n, rng)
    else:
        initial, requirements, actions, allowed = _repair_containment_family(n, rng, complexity)
    target = apply_actions(initial, actions)
    goal_parts = []
    for r in requirements:
        if r.kind == "equal":
            goal_parts.append(f"set {r.path} to {r.expected!r}")
        elif r.kind == "preserve":
            goal_parts.append(f"preserve {r.path} as {r.expected!r}")
        elif r.kind == "action_present":
            goal_parts.append(f"perform operation {r.path} on {r.expected}")
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
