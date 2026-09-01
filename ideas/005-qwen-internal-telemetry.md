# Idea 005 — Live Internal Telemetry + Compressed Brain-State Recording

**Status:** Seed

## Core hypothesis

For selected experiments, recording synchronized token-level and layer-level telemetry while Qwen generates can reveal repeatable pre-failure signatures that are invisible from final outputs alone.

## Recording strategy

Use three levels:

1. **Black-box:** prompt/output, tokens, logprobs, entropy, latency, stop reason, runtime metadata.
2. **MRI:** compressed layer/state statistics such as activation norms, state deltas, recurrent-state metrics, gating/decay signals, and selected attention statistics.
3. **Brain scan:** full-resolution activations/state only around anomalous or failed windows.

## Compression rule

Lossy by default, lossless around interesting events. Maintain a rolling raw buffer and dump it only when a trigger occurs.

## Primary questions

- Do stable internal signatures precede visible failures?
- How early can they be detected?
- Can those signatures predict failure on held-out tasks?
- Can an intervention at the detected point causally rescue the trajectory?

## Important constraint

Qwen's emitted reasoning text is a self-report, not a guaranteed faithful representation of the underlying computation. Keep semantic reasoning and machine telemetry as separate evidence streams.
