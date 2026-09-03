# INVERTED Agent Instructions

All agents working in this repository must read and obey [`INVERTED_CONSTITUTION.md`](INVERTED_CONSTITUTION.md) first, then [`MODEL_OPERATING_RULES.md`](MODEL_OPERATING_RULES.md), before meaningful design, testing, analysis, or implementation work.

The Constitution defines the highest-level project objectives. The operating rules define the detailed discipline beneath them.

Two permanent operating rules are especially important:

> **Your requirements define the minimum. I am responsible for identifying higher-value options, missing experiments, better architecture, better telemetry, and failure modes you did not explicitly name.**

> **Do not merely satisfy the requested experiment. Ask what we will wish we had recorded six months later, and capture it now when it is cheap.**

These are project-wide requirements, not suggestions. Literal task completion is insufficient when a materially better design, missing failure mode, higher-value experiment, safer architecture, cheaper deterministic alternative, or future-critical evidence capture opportunity is identifiable.

Additional rule: **something has to prove it belongs.** Do not add mechanisms or complexity without causal evidence or a clearly defined experiment that can earn their place.

For long-term optimization, model uplift, experiment decision value, decision-ready project memory, and shipping discipline, the canonical source is [`INVERTED_CONSTITUTION.md`](INVERTED_CONSTITUTION.md). For evidence capture, failure causality, retesting avoidance, promotion gates, and scope, use [`MODEL_OPERATING_RULES.md`](MODEL_OPERATING_RULES.md).
