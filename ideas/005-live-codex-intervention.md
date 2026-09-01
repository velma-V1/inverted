# Idea 005 — Live Codex Intervention

**Build order:** 5 of 6  
**Status:** Small controlled side experiment after memory/state architectures

## Hypothesis

A stronger model observing Qwen's live streamed reasoning can rescue some failures before completion, and may outperform simpler post-hoc critique enough to justify the added orchestration.

## Architecture

```text
Qwen/Ollama
   │ streamed thinking + output + telemetry
   ▼
ring buffer
   ├────────────► recorder
   ▼
chunker
(32–128 tokens or bounded time window)
   ▼
Codex observer
   ▼
intervention decision
   │
   ├─ NO → Qwen continues
   │
   └─ YES → stop generation
             save exact partial trajectory
             inject one short hint
             resume Qwen
```

## Experimental arms

```text
A — Qwen alone

B — Qwen finishes
    → Codex critiques
    → Qwen retries once

C — Codex watches live
    → at most one intervention
    → Qwen continues
```

## Intervention contract

Codex is not allowed to solve the task or provide a final answer. It may only identify the suspected reasoning defect and give a bounded correction hint.

```json
{
  "problem_detected": "...",
  "location": "...",
  "hint": "...",
  "confidence": 0.0
}
```

Set a strict maximum hint size and one intervention per task in the first experiment.

## Observation stream

Capture separately:

- Qwen emitted reasoning/thinking text
- output chunks
- timestamps
- token/logprob data when available
- tool calls
- stop/limit events
- Codex observer decisions

Do not treat emitted reasoning as ground-truth internal computation.

## Guardrails

- Same task and Qwen settings across arms.
- Codex sees no hidden answer key.
- Codex cannot directly answer.
- One intervention maximum initially.
- Every interrupted trajectory is preserved.
- Measure intervention harm, not just rescue.

## Primary metrics

```text
Rescue Rate =
baseline failures converted to success
──────────────────────────────────────
baseline failures receiving intervention

Damage Rate =
baseline successes converted to failure
───────────────────────────────────────
baseline successes receiving intervention
```

Also measure latency, Codex tokens/calls, false alarms, and improvement over post-hoc critique.

## Success gate

Keep live intervention only if it materially outperforms post-hoc correction at an acceptable damage/cost rate. Otherwise reject the real-time architecture and retain the simpler mentor pattern.

## Research basis

The experiment builds on iterative feedback/refinement, process-level verification, streaming local-model APIs, and persistent Codex sessions. The unproven variable is whether intervention timing itself adds enough value to justify the machinery.
