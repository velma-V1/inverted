# Testing Policy

## Universal campaign progress rule

Every future campaign section and every user-invoked benchmark/test run with a planned workload must provide a live progress display. The progress display is enabled by default; a caller should not need a special flag to see it during a real local run.

The live display must include, at minimum:

- a visible progress bar;
- percent complete;
- completed/total work units;
- physical model calls used/total when model inference is part of the test;
- current arm/phase when the test has arms or phases;
- elapsed time;
- estimated time remaining (time left);
- ETA clock time for expected completion.

Progress output must update in place when practical and flush after every update so the terminal reflects current state during long calls. The renderer must remain bounded enough for a normal PowerShell terminal and must finish with exactly one newline.

Elapsed time, estimated time remaining, and ETA are display-only telemetry. They may be estimated from observed completed work/calls, may stabilize as the run proceeds, and must never be used for outcome-dependent early stopping, scheduling changes, arm selection, verdict logic, or any other scientific decision.

Progress reporting must not alter model prompts, call counts, task order, seeds, cache behavior, retry behavior, evidence collection, or scientific accounting. If a future test cannot expose one of the required counters directly, the implementation must add the necessary non-causal instrumentation rather than silently omit the field.

This rule is part of the repository test contract from Test 3 S1-R3 onward. New campaign/test implementations must include a regression test proving the required progress telemetry is present before the implementation is considered ready for local execution.
