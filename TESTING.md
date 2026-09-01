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

Progress output must update in place when practical and flush after every update so the terminal reflects current state during long calls. The renderer must remain bounded enough for split-screen PowerShell use and must finish with exactly one newline.

Elapsed time, estimated time remaining, and ETA are display-only telemetry. They may be estimated from observed completed work/calls, may stabilize as the run proceeds, and must never be used for outcome-dependent early stopping, scheduling changes, arm selection, verdict logic, or any other scientific decision.

Progress reporting must not alter model prompts, call counts, task order, seeds, cache behavior, retry behavior, evidence collection, or scientific accounting. If a future test cannot expose one of the required counters directly, the implementation must add the necessary non-causal instrumentation rather than silently omit the field.

This rule is part of the repository test contract from Test 3 S1-R3 onward. New campaign/test implementations must include a regression test proving the required progress telemetry is present before the implementation is considered ready for local execution.

## Universal per-test external-action ceiling

Every individual test or campaign section may use at most **1000 combined external/AI actions total**. This is one single shared budget across model calls, AI/agent actions, API calls, tool calls, and any other externally executed action counted by the test. It is not 1000 of each category. The combined total must not exceed 1000.

The 1000-action limit is a **ceiling, not a quota**. Its purpose is to permit larger, more varied experiments when that additional breadth materially increases scientific value. Tests should use the budget to maximize **orthogonal variety** and information gain, not to manufacture call volume.

When scientifically relevant, budget should preferentially expand coverage across different failure classes, interventions, models/roles, perturbations, counterfactuals, validators, stress conditions, and other causally distinct probes. Repeated measurements are appropriate when needed for variance, confidence, or reproducibility, but redundant repetition that adds little information must not consume budget merely because capacity remains.

Before execution, each test must declare a preflight action budget and the classes of actions it expects to consume. Runtime accounting must use a single shared budget and fail closed before an action that would exceed the declared budget or the absolute 1000-action ceiling. Evidence must report actual usage by action class and in combined total.

Test design should therefore ask: **what additional distinct evidence can another action buy?** Large budgets are justified when they produce broader causal coverage, stronger discrimination among hypotheses, better variance estimates, or meaningful stress/edge-case coverage. They are not justified by repeated low-value calls that do not materially improve the answer.
