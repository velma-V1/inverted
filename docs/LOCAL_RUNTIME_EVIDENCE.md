# INVERTED Local Runtime Evidence

**Status:** CURRENT LOCAL HARDWARE PLANNING EVIDENCE — 2026-09-05
**Purpose:** Use measured execution behavior from this machine to plan experiment duration and scheduling without sacrificing scientific coverage.

This file records runtime measurements recovered from preserved raw data dumps and local run telemetry. It is planning evidence, not a benchmark of general model speed and not a reason to terminate a scientifically valuable campaign early.

## Campaign-level measurements

| Campaign | Model-call evidence | Measured local duration | Interpretation |
|---|---:|---:|---|
| Test 2 Tier-A | 396 physical calls; 452 logical model-call rows | ~18m 26s model-call window | Mixed-model historical run; contaminated scientifically for call identity, still useful for hardware timing. |
| Test 3 S2 Tier-A | 720 model calls | 1h 11m 49s wall-clock | Strong mixed-model runtime anchor. |
| Harvest A | 912 calls | 1h 09m 59s wall-clock | Mixed 3B / Qwen / 24B run. |
| Harvest B | 900 calls | 58m 54s wall-clock | Mixed 3B / Qwen / 24B run. |
| Harvest C | 900 calls | 6h 02m 44s wall-clock | Model reload behavior dominated much of the slowdown. |
| D3 | 632 calls | 8.24h summed inference latency | Not a campaign wall-clock figure; long Qwen generations dominated. |
| HD-NEXT-1 | 467 calls | 31.7m summed inference latency | Best current Small-A/Qwen planning anchor. |
| D4 | 48 calls | 26.6m summed inference latency | Qwen-heavy calibration anchor. |
| R1 | 24 calls | 13.4m summed inference latency | Qwen reproducibility/runtime anchor. |
## Model-specific measurements

### Small-A — `qwen2.5:1.5b-instruct-q8_0`

HD-NEXT-1 recorded 412 calls at approximately **0.09 seconds average latency per call**. Small-A inference is therefore effectively cheap in wall-clock terms relative to the larger local models and can carry broad discovery coverage.

### Qwen — `qwen3.5:9b-q8_0`

HD-NEXT-1 recorded 55 calls at approximately **33.97 seconds average latency per call**. Independent D4 and R1 evidence is consistent at approximately 33.19 and 33.52 seconds average latency per call.

D3 is an important stress case: 383 Qwen calls averaged approximately **77.22 seconds** and produced about 1.40 million output tokens. Future runtime estimates must therefore include a long-output stress scenario rather than assume the ~34 second regime always holds.

### Devstral Small 2 — `devstral-small-2:24b`

The Harvest A/B/C dumps provide **904 measured 24B calls**:

| Run | Calls | Avg latency | Median latency |
|---|---:|---:|---:|
| Harvest A | 304 | 9.54s | 8.89s |
| Harvest B | 300 | 8.29s | 8.20s |
| Harvest C | 300 | 49.40s | 39.27s |

Across all 904 calls, pooled median latency was **9.21s**. Among 609 warm/resident calls, average latency was **12.4s**, median **8.75s**, and p90 **10.84s**.
Harvest C's 24B slowdown was primarily residency/loading behavior: median model load duration was approximately **30.57s**, while median generation/eval duration remained near the ~8s regime seen in Harvest A/B.

## Scheduling implications

1. **Runtime is a planning variable, not a scientific early-stop rule.** Do not reduce coverage merely to make a campaign finish sooner.
2. **Batch large-model work when scientifically safe.** Keep same-model calls contiguous enough to preserve residency, especially for Devstral 24B.
3. **Randomize within model blocks.** Treatment, case, sequence, and execution-position order must still be randomized or balanced inside each model block so warm-loading does not become treatment bias.
4. **Capture residency telemetry.** Every model call should preserve load duration, eval duration, prompt-eval duration, input/output tokens, total latency, execution position, and previous model identity when available.
5. **Report warm and cold latency separately.** Cross-model or cross-treatment timing claims must not silently mix model-load penalties with inference cost.
6. **Use conservative forecasts.** Qwen planning should include both the recent ~34s/call regime and a long-output stress regime near the D3 ~77s/call observation.
7. **The 24B model is practical as a diagnostic probe.** Its warm median is under 9s on this machine; poor scheduling can make it several times slower.

## Example planning envelope

Using HD-NEXT-1 averages only, a 1000-call campaign with Small-A at ~0.09s/call and Qwen at ~34s/call has approximate inference time of:

- 10% Qwen / 90% Small-A: ~58 minutes;
- 20% Qwen / 80% Small-A: ~1h 54m;
- 30% Qwen / 70% Small-A: ~2h 51m;
- 50% Qwen / 50% Small-A: ~4h 44m.

These are planning estimates, not promises. They exclude orchestration overhead, cold loads, unusually long outputs, and any additional 24B diagnostic block.
