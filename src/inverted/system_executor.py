from __future__ import annotations

import hashlib
import random

from .domain import Action, Candidate, TaskCase
from .oracle import apply_actions, evaluate_task


def _public_actions(task: TaskCase) -> tuple[Action, ...]:
    actions: list[Action] = []
    for req in task.metadata["public_requirements"]:
        kind = req["kind"]
        meta = req.get("metadata") or {}
        if kind == "equal":
            actions.append(Action(str(meta.get("op", "set")), str(req["path"]), req.get("expected")))
        elif kind == "action_present":
            actions.append(Action(str(req["path"]), str(req.get("expected") or "procedure.marker"), meta.get("value", True)))
        elif kind == "action_before":
            after = meta.get("after_action")
            if after and not any(a.op == after.get("op") for a in actions):
                actions.append(Action(str(after["op"]), str(after["path"]), after.get("value")))
    return tuple(actions)


def _candidate_id(task: TaskCase, quality: float, seed: int) -> str:
    h = hashlib.sha256(f"{task.id}:{quality:.4f}:{seed}".encode()).hexdigest()[:12]
    return f"cand-{h}"


def _inject_fault(task: TaskCase, actions: tuple[Action, ...], rng: random.Random) -> tuple[tuple[Action, ...], tuple[str, ...]]:
    candidates = list(actions)
    modes = ["omitted_requirement", "wrong_value", "unintended_side_effect"]
    if task.family == "policy":
        modes += ["ordering_violation", "forbidden_procedure"]
    mode = rng.choice(modes)

    if mode == "omitted_requirement" and candidates:
        del candidates[rng.randrange(len(candidates))]
    elif mode == "wrong_value" and candidates:
        idx = rng.randrange(len(candidates))
        a = candidates[idx]
        candidates[idx] = Action(a.op, a.path, "__WRONG__" if not isinstance(a.value, bool) else not a.value)
    elif mode == "ordering_violation" and len(candidates) >= 2:
        candidates = list(reversed(candidates))
    elif mode == "forbidden_procedure":
        candidates.append(Action("delete", "protected.flag", None))
    else:
        op = "set" if "set" in task.allowed_ops else task.allowed_ops[0]
        candidates.append(Action(op, "guard.unexpected" if task.family == "state" else "resolved.unexpected", "side-effect"))

    state = apply_actions(task.initial_state, tuple(candidates))
    if evaluate_task(task, state, tuple(candidates)).success:
        # Guarantee the configured bad class is actually oracle-bad while staying structurally legal.
        req = next((r for r in task.metadata["public_requirements"] if r["kind"] == "equal"), None)
        if req is not None:
            op = str((req.get("metadata") or {}).get("op", "set"))
            candidates.append(Action(op, str(req["path"]), "__FORCED_FAULT__"))
            mode = f"{mode}+forced_requirement_violation"
    return tuple(candidates), (mode,)


def generate_candidate(task: TaskCase, target_quality: float, seed: int) -> Candidate:
    if not 0.0 <= target_quality <= 1.0:
        raise ValueError("target_quality must be between 0 and 1")
    rng = random.Random((seed * 2246822519) ^ int(target_quality * 1_000_000))
    actions = _public_actions(task)
    faults: tuple[str, ...] = ()
    if rng.random() >= target_quality:
        actions, faults = _inject_fault(task, actions, rng)
    state = apply_actions(task.initial_state, actions)
    return Candidate(
        id=_candidate_id(task, target_quality, seed),
        state=state,
        actions=actions,
        injected_faults=faults,
        configured_quality=target_quality,
        metadata={"seed": seed},
    )
