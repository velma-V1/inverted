from __future__ import annotations

from .contracts import AgentEvent, ConstraintEvaluation, CriticalDivergence

SEMANTIC_KINDS = {
    "observation", "dependency_inspection", "mutation", "state_reread",
    "verification", "repair", "rollback", "failure", "final",
}


def _semantic(events: list[AgentEvent]) -> list[AgentEvent]:
    return [e for e in events if e.kind in SEMANTIC_KINDS]


def localize_critical_divergence(qwen_events, teacher_events, ledger, task) -> CriticalDivergence:
    hard = sorted((x for x in ledger if x.status == "violated" and not x.recoverable), key=lambda x: x.event_index)
    if hard:
        hit = hard[0]
        return CriticalDivergence(
            task_id=task["id"], qwen_index=hit.event_index, teacher_index=None,
            failure_class=f"constraint_violation:{hit.constraint_id}", evidence=hit.evidence,
            candidate_behavior=f"avoid_{hit.constraint_id}", confidence=1.0,
        )
    q = _semantic(qwen_events); t = _semantic(teacher_events)
    limit = min(len(q), len(t))
    for i in range(limit):
        if q[i].kind != t[i].kind:
            failure_class = f"qwen_{q[i].kind}_instead_of_{t[i].kind}"
            evidence = [q[i].source_id or str(q[i].index), t[i].source_id or str(t[i].index)]
            return CriticalDivergence(task["id"], q[i].index, t[i].index, failure_class, evidence, t[i].kind, 0.75)
    if len(q) != len(t):
        qi = q[limit].index if len(q) > limit else (q[-1].index if q else 0)
        ti = t[limit].index if len(t) > limit else (t[-1].index if t else None)
        behavior = t[limit].kind if len(t) > limit else "stop_extra_steps"
        return CriticalDivergence(task["id"], qi, ti, "missing_or_extra_step", [], behavior, 0.6)
    return CriticalDivergence(
        task["id"], q[-1].index if q else 0,
        t[-1].index if t else None,
        "no_supported_divergence", [], None, 0.0,
    )
