# Idea 002 — Portable Cognitive Workspace

**Build order:** 2 of 6  
**Status:** Ready for detailed test design

## Hypothesis

Qwen3.5-9B will complete long and interrupted tasks more reliably if it carries a compact external task-state file through the whole task and promotes only verified improvements into reusable skills, patterns, edge cases, and tools.

## Architecture

```text
WORKSPACE/
├── TASK_STATE.yaml
├── JOURNAL.jsonl
├── candidates/
├── skills/
├── patterns/
├── edge-cases/
├── tools/
└── evidence/
```

`TASK_STATE.yaml` is the current projection. `JOURNAL.jsonl` is append-only history. The mutable state can always be reconstructed from the journal.

## TASK_STATE schema

```yaml
goal:
current_phase:
plan:
completed:
next:
constraints:
known_facts:
open_questions:
failed_approaches:
artifacts:
confidence:
```

Do not store a full chain of thought. Store only state necessary to continue the task correctly.

## Runtime

```text
task starts
  ↓
initialize TASK_STATE
  ↓
Qwen works
  ↓
important state transition
  ↓
append JOURNAL event
  ↓
update TASK_STATE projection
  ↓
retrieve only relevant proven skills/files
  ↓
continue until completion
```

## Promotion pipeline

Qwen may create candidate lessons, but cannot write directly into permanent reusable memory.

```text
candidate lesson
  ↓
Codex/Claude or deterministic verifier
  ↓
replay on related and counterexample cases
  ↓
PASS
  ↓
promote to skills/ patterns/ edge-cases/ or tools/
```

Use an open skill-folder format where practical: one concise skill description plus optional scripts, references, tests, and evidence.

## Guardrails

- Journal is immutable.
- State snapshots are bounded in size.
- Failed approaches are explicit so Qwen does not loop.
- Permanent memories require provenance and replay evidence.
- Retrieval has a strict token budget.
- Old task state is archived rather than injected by default.

## First experiment

Compare:

1. Qwen alone.
2. Qwen + traveling task state only.
3. Qwen + traveling task state + verified reusable skill library.

Include long tasks, interruptions/resume, plan changes, and later tasks that can reuse an earlier verified procedure.

## Primary metrics

- Task completion
- Plan drift
- Repeated work
- Recovery after interruption
- Cross-task reuse
- Token cost
- Retrieval precision

## Success gate

Proceed if the workspace materially reduces plan loss/repeated work and later tasks measurably benefit from verified reusable artifacts without increasing hallucinated retrieval.

## Research basis

This design draws on persistent project-memory patterns, append-only/event-sourced state, Voyager-style skill libraries, agent skill folders, and filesystem-backed agent memory. The experiment isolates portable state before adding graph complexity.
