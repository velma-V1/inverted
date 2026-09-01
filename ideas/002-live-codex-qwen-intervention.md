# Idea 002 — Live Codex Observation + Real-Time Qwen Intervention

**Status:** Seed

## Core hypothesis

Codex watches Qwen's streamed reasoning/telemetry during a task and can rescue an emerging failure before Qwen finishes the wrong trajectory.

## Initial experiment

Three matched arms:

- **A — Baseline:** Qwen solves alone.
- **B — Post-hoc:** Qwen finishes, Codex critiques, Qwen retries.
- **C — Real-time:** Codex observes the live stream, may interrupt once, inject a short correction, and Qwen resumes.

Start with 30–50 difficult tasks and permit at most one intervention per task.

## Primary metric

Of tasks Qwen would otherwise fail, what fraction are rescued by real-time intervention beyond the post-hoc arm?

## Secondary metrics

- Harmful/interfering intervention rate
- Added latency
- Added tokens
- Codex usage
- Whether specific intervention points repeatedly predict successful rescue

## Decision rule

Keep this idea only if real-time intervention provides a meaningful gain over simpler post-hoc correction.
