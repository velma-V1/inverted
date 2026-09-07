from __future__ import annotations

from .contracts import CriticalDivergence, AgentEvent, InterventionSpec


def plan_interventions(divergence: CriticalDivergence, teacher_events: list[AgentEvent]) -> list[InterventionSpec]:
    behavior = divergence.candidate_behavior or "unknown"
    specs = [
        InterventionSpec(f"{divergence.task_id}-remove", "remove", behavior),
        InterventionSpec(f"{divergence.task_id}-force", "force", behavior),
    ]
    teacher_kind = None
    if divergence.teacher_index is not None:
        for event in teacher_events:
            if event.index == divergence.teacher_index:
                teacher_kind = event.kind
                break
    if teacher_kind:
        specs.append(InterventionSpec(f"{divergence.task_id}-replace", "replace", behavior, replacement=teacher_kind))
        specs.append(InterventionSpec(f"{divergence.task_id}-delay", "delay", behavior, replacement=teacher_kind))
    if teacher_kind in {"state_reread", "verification", "dependency_inspection"}:
        specs.append(InterventionSpec(f"{divergence.task_id}-interaction", "interaction", behavior, replacement=teacher_kind, metadata={"paired": True}))
    return specs
