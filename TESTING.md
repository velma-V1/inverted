# Testing Policy

`REPO_LAWS_AND_REGULATIONS.md` is the canonical governance source. This file defines the concrete testing-policy contract and may not weaken or override the repository laws.

## Universal test-automation rule

Every test, benchmark, experiment, campaign, validation run, regression run, stress test, red-team run, and other repeatable verification workflow must be automated wherever technically and scientifically possible.

Automation is the default. A future implementation must not require the user to manually perform repeatable mechanical steps that the test harness can perform reliably itself.

Where applicable, automation should cover:

- preflight and dependency/runtime checks;
- model/runtime availability checks;
- case and arm scheduling;
- deterministic randomization and seed capture;
- action/call budget accounting;
- test execution;
- model/tool/API invocation;
- evidence capture and append-only journaling;
- scoring and deterministic oracle evaluation;
- deterministic replay and counterfactual analysis;
- failure classification;
- recovery classification and safe recovery execution when the active protocol permits it;
- sequential stopping / continuation decisions when preregistered;
- crash-safe checkpoint/resume;
- artifact generation, checksums, provenance, and summaries;
- regression checks;
- final completeness/quality validation.

Human intervention should be reserved for actions that cannot safely or validly be automated, such as an explicit hard-stop condition, an owner-only authority decision, a genuinely ambiguous external effect requiring adjudication, or another protocol-defined human gate.

Automation must never silently change the scientific design. It may execute the frozen protocol; it may not rewrite the oracle, success criteria, sealed evidence, authority boundary, action budget, or preregistered decision logic because the current results are inconvenient.

A test is not considered operationally complete merely because its scientific logic works manually. If the repeatable execution path can reasonably be automated, automation is part of the test's completion criterion.

## Universal campaign progress rule

Every user-invoked test or campaign with measurable work must provide a live progress display automatically on launch. The caller must not need a special flag to enable it for a normal local run.

### Same-terminal requirement

The progress display must run in the **same terminal session in which the test was launched**.

It must not require:

- a second terminal window;
- a browser dashboard;
- localhost UI;
- a GUI process;
- a separate monitoring program;
- or manual attachment after launch.

It must be usable while ChatGPT and the terminal are open side-by-side in a narrow split-window layout.

### Required progress information

The live display must include, at minimum:

- a visible progress bar;
- percent completed;
- work/tasks completed;
- work/tasks remaining;
- completed/total work units when a meaningful total exists;
- physical model calls used/available when model inference is part of the test;
- current phase/arm/task when that information is useful and can fit without breaking the compact display;
- elapsed time when space allows;
- estimated time to completion / time remaining;
- ETA clock time for expected completion.

A normal compact form should be approximately:

```text
[#######---] 70% | done 140/200 | left 60 | 18m left | ETA 09:41
```

For very narrow terminals, the renderer must automatically reduce nonessential labels while preserving the required information, for example:

```text
[####---] 70% 140/200 L60 18m ETA09:41
```

The bar width must be dynamic rather than assuming a wide console. The renderer should detect terminal width when practical and maintain a deliberately small minimum-width mode.

### Adaptive tests

For adaptive or sequential tests where the final amount of executed work is not fixed in advance, progress must not pretend that the maximum call ceiling is the planned workload.

Report progress against the **currently committed/scheduled executable work** and separately expose the remaining call/action ceiling when useful. If the scheduler legitimately changes the committed workload, recompute the denominator and preserve the scheduling change in test telemetry.

A call/action ceiling remains a ceiling, not a promise that the run will consume the entire budget.

### Split-window / repaint bug tolerance

The expected operating environment may occasionally cause terminal repaint behavior to emit a new line instead of rewriting the previous progress line, especially in a narrow split-window terminal used beside ChatGPT.

The progress renderer must therefore:

1. prefer a single-line in-place update using carriage-return/terminal-safe repaint behavior when the terminal supports it;
2. avoid full-screen terminal control, cursor-addressing dashboards, or multi-line animated interfaces;
3. keep every rendered update independently understandable if an overwrite is converted into a new line;
4. throttle updates so a repaint bug cannot flood the terminal with thousands of nearly identical lines;
5. fall back automatically to periodic compact status lines when in-place repaint is unreliable or output is non-interactive;
6. emit exactly one final completed status line/newline at test termination.

A repaint/display failure is an observability defect, not a reason to corrupt or stop the underlying scientific run unless the active protocol explicitly requires live progress as a safety control.

### ETA semantics

Estimated time remaining and ETA are display-only operational telemetry. They should be computed from observed completed work using a stable estimator that becomes less volatile as the run proceeds.

They are estimates, not scientific evidence. ETA/progress estimates must never affect:

- model prompts;
- case ordering unless scheduling logic independently requires it;
- arm selection;
- early stopping;
- verdicts;
- call budgets;
- retries;
- evidence admissibility;
- or any other experimental conclusion.

### Progress regression requirement

Every new test runner must include automated regression coverage proving that its progress interface exposes the required counters and can render in a deliberately narrow terminal width before the runner is considered ready for local use.

Where practical, regression coverage should include:

- normal-width rendering;
- narrow-width rendering;
- non-interactive/fallback rendering;
- completion at 100%;
- zero-completed initial state;
- adaptive-denominator updates when applicable;
- long ETA values;
- unknown/not-yet-stable ETA state;
- and prevention of divide-by-zero or negative remaining-work displays.

Progress reporting must not alter model calls, seeds, prompts, cache behavior, retry behavior, test order, scientific accounting, or evidence collection.

## Universal per-test external-action ceiling

Every individual test or campaign section may use at most **1000 combined external/AI actions total** unless an explicit owner-approved frozen specification sets a different stricter limit. This is one single shared budget across model calls, AI/agent actions, API calls, tool calls, and any other externally executed action counted by the test. It is not 1000 of each category. The combined total must not exceed the applicable frozen ceiling.

The 1000-action limit is a **ceiling, not a quota**. Its purpose is to permit larger, more varied experiments when that additional breadth materially increases scientific value. Tests should use the budget to maximize **orthogonal variety** and information gain, not to manufacture call volume.

When scientifically relevant, budget should preferentially expand coverage across different failure classes, interventions, models/roles, perturbations, counterfactuals, validators, stress conditions, and other causally distinct probes. Repeated measurements are appropriate when needed for variance, confidence, or reproducibility, but redundant repetition that adds little information must not consume budget merely because capacity remains.

Before execution, each test must declare a preflight action budget and the classes of actions it expects to consume. Runtime accounting must use a single shared budget and fail closed before an action that would exceed the declared budget or the absolute applicable action ceiling. Evidence must report actual usage by action class and in combined total.

Test design should therefore ask: **what additional distinct evidence can another action buy?** Large budgets are justified when they produce broader causal coverage, stronger discrimination among hypotheses, better variance estimates, or meaningful stress/edge-case coverage. They are not justified by repeated low-value calls that do not materially improve the answer.
