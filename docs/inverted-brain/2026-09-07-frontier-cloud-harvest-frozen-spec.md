# Frontier / Cloud Harvest — Frozen Specification

**Status:** FROZEN DESIGN — template implementation requires explicit operator approval

This specification is subordinate to `2026-09-07-universal-harvest-frozen-contract.md`. It defines the higher-depth native-harvest and frontier-resolution treatment of Claude, Codex, ChatGPT, and other admitted frontier systems.

## Purpose

Frontier runs are expensive and unusually information-rich. They are not treated as ordinary benchmark calls. Each run is a reusable experimental specimen designed to reveal as much as possible about:

- model behavior;
- system architecture;
- context construction;
- memory;
- reasoning/thought when exposed;
- tools, skills, hands, subagents, and capability discovery;
- planning and state management;
- verification and completion rules;
- failure recognition and recovery;
- search and information efficiency;
- system-versus-model contribution;
- transferable mechanisms;
- negative evidence and failure precursors.

The required evidence posture is the previously defined **11/10 collection level**: lower run volume than local tests, but substantially deeper, redundant, and replay-oriented observation.

## Two distinct frontier roles

### A. Frontier Native Harvest

Claude, Codex, and ChatGPT run **independently from the original frozen task/workspace**. They do not receive answers or trajectories from one another or from the local ladder.

```text
SAME FROZEN TASK
  -> Claude native system
  -> Codex native system
  -> ChatGPT native system
```

Each system retains its native strengths and architecture where permitted. The purpose is to discover what makes the complete system special, not flatten every system into the same minimal harness.

### B. Frontier Resolution

Claude and Codex also receive local cases that exhaust 1–2B -> Qwen 9B -> Devstral 24B.

```text
FREEZE C
  -> Claude continuation
  -> Codex continuation
  -> selected Claude fresh control
  -> selected Codex fresh control
  -> blind verifier
```

Continuation and native-harvest evidence must never be mixed as if they were the same condition.

ChatGPT may also be used as a high-value reference/resolution specimen when the operator explicitly runs the case through the ChatGPT environment and connected tools.

## Native-system individuality

Do not disable a frontier system's distinctive native mechanisms merely to make it look like another system. Preserve and observe, when applicable:

- context-management and compaction;
- memory;
- skills;
- hooks;
- subagents;
- tool discovery;
- sandboxing and permission gates;
- planning/state machinery;
- retries/recovery;
- verification;
- session persistence;
- capability discovery;
- system-generated prompts and state visible through supported interfaces.

Separate ablation arms may disable one mechanism at a time after the native trajectory identifies a causal question.

## 11/10 evidence standard

Frontier collection uses the full Universal Forensic Recorder plus redundant observation and derivative-experiment requirements.

### Observation layer 1 — native telemetry

Capture everything the supported interface exposes, including where available:

- structured event streams;
- messages and intermediate messages;
- visible/exposed reasoning or reasoning summaries;
- tool calls and arguments;
- tool results;
- subagents;
- skills;
- hooks;
- permissions and approvals;
- sandbox decisions;
- memory/context events;
- compaction;
- retries/recovery;
- errors and stop/completion events;
- timing/token information.

For Claude Code, Codex CLI, and other systems with machine-readable streams, prefer raw structured events over terminal-only summaries.

For ChatGPT, preserve all observable conversation/tool activity available through the product and connected tools. Do not claim access to hidden internal reasoning or server-side instructions that are not exposed.

### Observation layer 2 — independent external observer

Corroborate native claims with outside evidence where possible:

- filesystem operations;
- every mutation and important intermediate diff;
- commands/processes;
- stdout/stderr/exit status;
- workspace snapshots and hashes;
- git state;
- tests and verifier execution;
- environment changes;
- timing;
- network metadata where useful and safe.

Example: an agent claiming success is not sufficient. The blind verifier and final workspace state independently establish disposition.

### Observation layer 3 — reasoning/cognitive reconstruction

Build a normalized state graph from directly exposed reasoning and observable behavior:

`problem representation -> hypothesis -> evidence search -> action/tool -> observation -> belief change -> contradiction -> repair -> verification -> completion`

Every node must carry provenance such as `EXPOSED_MODEL_REASONING`, `SYSTEM_EVENT`, `OBSERVED_TOOL_BEHAVIOR`, or `INFERRED_ANALYSIS`.

## Memory / thought / reasoning capture

Capture when technically exposed or instrumentable:

- memory creation, retrieval, mutation, persistence, conflicts, forgetting/deprecation;
- memory provenance and age;
- whether a memory changed a hypothesis, action, search path, tool choice, or completion decision;
- lost state and stale/false memory;
- raw exposed thought/reasoning streams;
- reasoning summaries;
- reflection/replanning;
- confidence/uncertainty shifts;
- hypothesis changes;
- meta-reasoning and frame resets;
- reasoning persistence across tools, compaction, failures, and long trajectories.

When internal chain-of-thought is not exposed, record observable decision traces and explicitly label reconstruction as inferred. Never invent hidden reasoning.

## Complete model-visible state snapshots

At each meaningful frontier decision checkpoint, preserve as much as the interface allows of exactly what the system/model could see:

- active instruction hierarchy;
- complete active context;
- context item order and position;
- memory and skills injected;
- tool schemas/capabilities;
- prior observations;
- summaries/compactions;
- workspace/system state;
- remaining budgets when visible.

The purpose is to separate **better model cognition** from **better information/system presentation**.

## High-value checkpointing and replay

Every meaningful decision point should become a potential replay checkpoint. Preserve enough state to later test cheaper counterfactuals without rerunning the whole frontier trajectory.

For selected checkpoints derive or schedule:

- observed action versus alternate action;
- continuation versus fresh start;
- same checkpoint without one memory item;
- same checkpoint without one skill;
- same checkpoint without one evidence item;
- changed context order;
- changed tool description/permission;
- local-model replay from frontier checkpoint;
- repeated checkpoint samples where stochastic stability matters.

One expensive frontier run should seed many cheaper local/deterministic experiments.

## Decision sensitivity and stochastic stability

At selected high-information checkpoints, measure whether small changes alter the decision:

- one evidence item;
- one wording change;
- context ordering;
- memory/skill injection;
- tool description;
- permission;
- misleading observation.

Where the platform permits repeated comparable calls, selected checkpoint repeats may estimate decision distributions and rare catastrophic branches. Do not mechanically repeat entire expensive tests when checkpoint replay answers the question.

## Self-assessment calibration

When exposed or explicitly instrumented without contaminating the native arm, record:

- whether the system believes it succeeded;
- confidence/uncertainty;
- what it believes remains unverified;
- what could still be wrong.

Compare against blind verification to measure false confidence, appropriate uncertainty, and failure-awareness quality.

## Failure awareness gap

Track separately:

- time of first causal error;
- time error becomes externally detectable;
- time model/system recognizes it.

Measure detection and recognition latency. A system's ability to know it is wrong is a first-class capability.

## Recovery quality

A repaired task is not simply labeled recovered. Classify whether recovery was:

- root-cause repair;
- symptom patch;
- temporary workaround;
- lucky correction;
- failure migration;
- regression-producing repair.

Record whether the true invariant was verified afterward.

## Search and information-value graph

For every frontier trajectory reconstruct when possible:

- search tree/graph;
- relevant versus irrelevant branches;
- redundant reads/searches;
- wrong-file/tool accesses;
- backtracking;
- abandoned paths;
- time to first discriminating evidence;
- information gain per read/search/tool action;
- context/evidence actually used versus merely present.

This is intended to expose differences in search strategy and evidence efficiency, not only final correctness.

## Tool / skill / hand / capability value

Maintain empirical ledgers for frontier systems:

- available;
- discovered;
- selected;
- useful;
- unnecessary;
- harmful;
- unavailable when needed;
- misunderstood;
- information gain;
- association with success/failure;
- cases where the capability existed but the system failed to use it.

Capability possession and capability utilization are separate measurements.

## System-versus-model ownership

Tag meaningful state changes by owner where possible:

- model;
- agent harness/system;
- memory;
- skill;
- tool/hand;
- subagent;
- verifier;
- environment;
- human/operator.

The objective is to identify whether success came from the frontier model itself, the surrounding system, a tool/skill, or their interaction.

## Source/runtime reconciliation

For open or inspectable frontier harnesses, map observed events to implementation:

`repo commit -> source file -> class/function -> rule/threshold -> runtime event`

Compare system documentation/self-description against actual runtime behavior. Marketing/documentation claims are hypotheses until observed.

## Failure and success precursor mining

For every difficult failure and recovery, preserve windows before the outcome so offline analysis can search for recurring precursors such as:

- context saturation;
- repeated low-information search;
- assumption accumulation;
- confidence rising without new evidence;
- narrowing hypotheses too early;
- repeated tool errors;
- verification disappearing;
- contradiction detection;
- hypothesis reset;
- targeted discriminating search;
- minimal repair followed by complete verification.

The objective is to discover predictors that Inverted can use before failure occurs.

## Shadow/offline analysis

Do not waste frontier calls on analysis that can be done later.

```text
frontier run
  -> immutable forensic archive
  -> freeze
  -> local/deterministic shadow analysis
  -> candidate checkpoints/mechanisms/counterfactuals
```

Local models and deterministic analysis may later extract graphs, classify trajectories, identify first divergence, generate replay candidates, and measure tool/context value. Derived output never replaces the raw frontier evidence.

## Mandatory trajectory-autopsy package

Each expensive frontier run must be capable of yielding:

- raw event archive;
- checkpoint archive;
- prompt/context lineage;
- memory record;
- exposed reasoning archive where available;
- normalized reasoning graph;
- decision graph;
- evidence graph;
- assumption ledger;
- contradiction ledger;
- context graph;
- filesystem/process history;
- verification graph;
- failure propagation graph;
- tool/skill/hand value ledger;
- memory-effect record;
- first meaningful divergence record;
- near misses;
- success/failure precursor candidates;
- counterfactual candidates;
- replay points;
- immutable manifest/hashes.

## First meaningful divergence is mandatory

For useful cross-system comparisons, align trajectories and identify the first meaningful point where they differ.

The target statement is not:

> Claude passed and Qwen failed.

The target statement is closer to:

> At decision event N, both systems possessed evidence A/B. System X inspected dependency C before mutation; System Y edited immediately. C exposed constraint D, changing the hypothesis and preventing the downstream failure.

That divergence becomes a mechanism hypothesis for local causal replay.

## Seven mandatory frontier edge-case families

Every frontier model/system native test receives **seven edge-case families** in addition to the normal adaptive frontier. Five families are common across systems for direct comparison; two may be tailored to the system's claimed/native strengths.

### 1. Extreme compositional absurdity

Canonical family marker:

> **A purple unicorn riding an orange hippo swimming in pudding while playing medieval-style chess.**

The absurd surface must hide a rigorous, objectively verifiable problem containing interacting constraints, causal dependencies, tool requirements, or contradictions. The purpose is to test preservation of real problem structure under bizarre composition, not creative-writing ability.

### 2. Contradiction minefield

Multiple plausible/authoritative-looking sources conflict. The system must detect the contradiction, avoid premature closure, seek discriminating evidence, revise state, and verify.

### 3. Success-that-is-actually-failure

An obvious check passes while a second-order invariant remains broken, stale, unreachable, nonpersistent, or inconsistent. Tests completion gates and verification depth.

### 4. Poisoned rescue

Prior work contains useful discoveries mixed with an incorrect assumption, misleading notes, stale verification, and partially correct mutation. Tests continuation hygiene, negative evidence, and state repair.

### 5. Cross-domain structural transfer

The same causal structure appears under a substantially different surface domain. Tests mechanism transfer rather than wording/pattern recognition.

### 6. System-specific capability trap

Tailored to a distinctive claimed/native capability such as skills, hooks, subagents, compaction, persistence, repository search, connected-tool orchestration, recovery, or sandboxing. The task should reveal whether the capability is actually discovered and used correctly.

### 7. Meta-edge / reasoning-procedure failure

The current reasoning procedure itself becomes the problem: evidence contradicts the working frame, ordinary repair fails, retry reinforces the wrong representation, and success requires a frame reset or higher-level reasoning-policy change.

## Edge cases also become adaptive frontiers

The seven edge cases are **families, not seven static questions**. A verified success creates a harder descendant by adding controlled difficulty such as hidden dependency, misleading evidence, tool failure, stale verification, delayed state, or compound interactions.

No frontier system should be able to "pass all edge cases" and finish the benchmark; the family continues until the predeclared experimental budget or a verified frontier boundary is reached.

## Frontier native comparison pool

At minimum maintain separate native/reference treatment for:

- Claude Code / Agent SDK observable system behavior;
- Codex CLI/system behavior;
- ChatGPT with its available connected tools and observable product behavior.

Additional systems may be admitted only when they introduce a unique mechanism class or resolve a specific architectural question.

Do not treat Claude Agent SDK as an independent model architecture from Claude Code when the underlying system is substantially the same; use it where it improves instrumentation/ablation.

## Relationship to the local ladder

Frontier systems serve two purposes:

1. **Independent native teachers/research specimens** on untouched tasks.
2. **Resolvers** for local FREEZE C cases.

Candidate frontier mechanisms flow back into cheap causal work:

`frontier behavior -> first divergence -> local reproduction -> necessity/sufficiency -> boundary/negative transfer -> interaction/order if justified -> fresh transfer -> Learning Compiler`

## Maximum derivative-value law

A frontier call is considered under-instrumented if its archived state cannot support later questions beyond the original scoring decision.

Design every expensive run so that months later it can still support new questions through archived checkpoints, raw events, source/context provenance, and local replay.

**Data collection is cheap; retesting is not.**

## Implementation gate

Do not build or modify the Frontier/Cloud Harvest template until the operator explicitly approves this frozen specification and the shared Universal Harvest contract.
