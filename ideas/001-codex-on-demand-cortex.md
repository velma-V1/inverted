# Idea 001 — Codex as an On-Demand Cortex for Qwen

**Status:** Seed

## Core hypothesis

Qwen handles normal work locally. When it reaches a bounded unresolved state, it escalates the task, its current attempt, and failure metadata to Codex. Codex diagnoses or solves the hard case and returns the smallest useful correction.

## Why test it

The goal is to increase useful task completion while minimizing dependence on the stronger model.

## Initial experiment

Compare:

1. Qwen alone.
2. Qwen with post-failure Codex consultation.
3. Qwen with a learned escalation policy.

Measure task success, Codex-call rate, added latency/tokens, repeated failure rate, and regressions.

## Open design questions

- What exact conditions trigger escalation?
- How long should Qwen deliberate before escalating?
- What minimum context should Codex receive?
- Can successful Codex corrections later be compressed or learned by Qwen?
