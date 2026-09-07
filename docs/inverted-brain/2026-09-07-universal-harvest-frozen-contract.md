# Universal Harvest — Frozen Contract

**Status:** FROZEN DESIGN — implementation not yet approved

This contract freezes the shared laws for all future Universal Harvest templates. It is intentionally separate from the historical Inverted executor/auditor experiment and must not alter that evidence.

## Change control

- This document is the authoritative shared contract for Local Continuation Harvest and Frontier/Cloud Harvest.
- Do not weaken, silently reinterpret, or replace these requirements during implementation.
- Any material change requires explicit operator approval and must be documented as a versioned amendment.
- Raw historical evidence is immutable.
- Data collection is cheap; retesting is not. Every expensive run must leave enough evidence for later analysis, replay, comparison, and counterfactual work without rerunning the frontier model whenever possible.
- Never rely on conversational memory as the sole source of experimental requirements. Read the frozen repository specifications and, when necessary, the source chat that produced them.

## Core experiment laws

1. **Success never ends testing.** Every verified success creates a harder descendant challenge.
2. **Failure never ends the campaign.** A wrong answer gets one bounded repair retry for that model; repeated failure freezes the exact state and escalates or queues the case.
3. **Attempt failure != task termination != campaign failure.** Preserve all three separately.
4. **No uncontrolled retry loops.** One repair retry per wrong answer, per model, per challenge. Hard failure, verified stuck state, context/tool/output exhaustion, unsupported capability, repeated-action loop, or infrastructure fault may escalate immediately.
5. **No model should be able to pass the whole test.** Frontier depth is adaptive and budget-bounded, not a finite benchmark ceiling.
6. **Every verified answer generates a harder challenge.** Difficulty must rise along controlled dimensions rather than merely changing wording.
7. **Branch the frontier.** Successful tasks may generate deeper, perturbed, compound, transfer, and edge-case descendants. The scheduler chooses descendants by expected information value.
8. **Preserve negative evidence.** Wrong answers, malformed outputs, useless searches, false confidence, loops, failed skills, tool misuse, stale verification, negative transfer, and regressions are first-class evidence.
9. **Freeze before escalation.** Every handoff preserves the exact checkpoint lineage and state needed for continuation and later fresh-control replay.
10. **Independent verification decides correctness.** Model confidence and self-reported completion are never substitutes for objective evidence.
11. **State-changing actions invalidate prior verification.** Completion is forbidden until current-state verification covers all required contract dimensions.
12. **Mechanisms must earn inclusion.** Source systems, books, documentation, prompt archaeology, and teacher trajectories generate hypotheses. Retained architecture requires causal evidence, boundaries, and fresh transfer.

## Adaptive difficulty dimensions

Challenge descendants may increase or combine:

- ambiguity and underspecification;
- dependency depth and breadth;
- hidden or delayed state;
- contradictory evidence;
- misleading but plausible evidence;
- incomplete evidence;
- larger search space;
- tool or environment failure;
- changed environment after an earlier observation;
- stale verification after mutation;
- conflicting requirements;
- causal-chain length;
- verification depth;
- cross-domain transfer;
- order dependence;
- interaction between two previously isolated failure modes;
- recovery after partial or poisoned prior work;
- novel compositional absurdity and rare edge cases.

Difficulty generation must preserve the causal structure being tested and record why the child challenge is harder than its parent.

## Required evidence architecture

Every run produces two strictly separated layers:

1. **IMMUTABLE RAW EVIDENCE** — the ground-truth event archive. Never rewritten by later interpretation.
2. **NORMALIZED / TRANSLATED EVIDENCE** — derived analysis that may be regenerated as translators improve.

Every derived claim must retain provenance. Never label inferred reasoning as directly observed reasoning.

### Required provenance labels

At minimum:

- `EXPOSED_MODEL_REASONING`
- `DIRECTLY_EXPOSED`
- `OBSERVED_SYSTEM_STATE`
- `OBSERVED_TOOL_BEHAVIOR`
- `SYSTEM_EVENT`
- `EXTERNAL_MEASUREMENT`
- `SOURCE_CODE_TRACE`
- `INFERRED_ANALYSIS`
- `HUMAN_INTERVENTION`

## Universal forensic recorder

Capture, when technically available and permitted, the following at every meaningful decision point and state transition.

### Identity and reproducibility

- system/product/repository;
- exact repository commit SHA;
- dependency lock and runtime versions;
- container/image digest;
- model name/version;
- quantization;
- inference engine;
- sampling configuration and seed when supported;
- context and output limits;
- hardware and environment;
- workspace/task hashes;
- permissions and sandbox state.

### Complete model-visible state

Preserve what the model could actually see at each important decision:

- system/developer/user instruction hierarchy;
- full active context;
- context ordering and token position;
- skills loaded;
- memory injected;
- tool schemas and available capabilities;
- prior observations and tool outputs;
- summaries and compactions;
- current workspace/system state;
- remaining context/output/resource budgets when observable.

### Prompt and context lineage

Record the transformation chain:

`task -> system wrapper -> memory -> skill -> tool schema -> retrieval -> compression/summary -> final model-visible request`

For every context item, record when possible:

- source and source hash;
- retrieval reason/rank;
- admission/rejection decision;
- transformation/compression;
- ordering/position;
- truncation or information loss;
- duplication/conflict/staleness;
- whether it was later used, ignored, contradicted, or misleading.

### Memory

When exposed or instrumentable, record:

- memory creation;
- admission/rejection;
- provenance;
- retrieval;
- mutation;
- persistence;
- forgetting/deprecation;
- conflict and stale memory;
- whether recalled state changed a hypothesis, action, search path, tool choice, or completion decision;
- information apparently known earlier but lost or ignored later;
- false remembered/generated state contradicted by current evidence.

### Thought, reasoning, and meta-reasoning

When the runtime exposes reasoning/thinking, preserve it raw. Also derive a normalized reasoning state containing when supportable:

- problem representation;
- hypotheses and counterhypotheses;
- assumptions;
- contradictions;
- evidence used or rejected;
- uncertainty/confidence changes;
- candidate decisions;
- expected consequences;
- verification intent;
- repair choice;
- frame change/reset;
- loop/repetition signatures;
- meta-reasoning escalation;
- psychological-set / contradicted-frame persistence.

When proprietary systems do not expose hidden reasoning, reconstruct only from observable evidence and mark it `INFERRED_ANALYSIS`.

### Decision environment

At important decisions preserve:

- available actions/tools/capabilities;
- candidate actions considered or ranked when exposed;
- rejected alternatives and reasons when exposed;
- selected action;
- evidence that would have changed the decision when measurable;
- counterfactual paths worth replaying later;
- unused capabilities that existed but were not discovered or applied.

### Expectation versus reality

Before actions, capture predicted consequence when exposed or explicitly instrumented. Afterward record:

- actual consequence;
- discrepancy;
- belief/state delta;
- what evidence caused the update;
- whether contradictory evidence was resolved, ignored, or deferred.

### Tools, skills, hands, and subagents

Capture:

- every tool/capability offered;
- selection and arguments;
- results, stdout/stderr, exit status, duration, retries, cancellation;
- skill discovery/routing/loading/use and effectiveness;
- hand delegation contract, state, artifacts, cancellation, retrieval, verification;
- subagent lineage, delegated context, withheld context, returned state, and parent acceptance/rejection;
- capability discovery attempts;
- tool/skill availability versus actual utilization.

Maintain empirical value ledgers for tools/skills/hands: available, selected, useful, unnecessary, harmful, unavailable-when-needed, misunderstood, information gain, success/failure association.

### Filesystem, execution, environment, and network

Capture where practical:

- meaningful file reads/writes/deletes/renames;
- every important intermediate diff and artifact evolution;
- hashes/state snapshots before and after mutation;
- shell commands, cwd, process tree, exit codes;
- environment changes;
- environment observations before action;
- network destinations/timing/metadata when useful and safe;
- secrets and credentials must be redacted rather than copied into evidence.

### Verification and completion

Capture:

- frozen verification obligations;
- checks performed and omitted;
- verification coverage;
- stale evidence;
- post-mutation verification;
- blind verifier output;
- model/system belief that work is complete;
- exact evidence that permitted or denied `COMPLETE`;
- unverified-success and premature-completion events.

### Failure and recovery

Record separately:

- first causal error;
- first externally detectable error;
- first model/system recognition of the error;
- detection/recognition latency;
- propagation graph from first error to dependent errors;
- diagnosis;
- repair selection;
- root-cause versus symptom repair;
- failure migration;
- recovery verification;
- recurrence;
- loops and repeated action/tool/reasoning signatures;
- near misses and one-change-away outcomes.

### Search and information efficiency

Track:

- plausible search space versus inspected region;
- relevant and irrelevant branches;
- wrong-file/tool accesses;
- redundant reads/searches;
- backtracking and abandoned branches;
- time to first discriminating evidence;
- information gain per read/search/tool action;
- resource allocation per hypothesis or phase;
- ignored evidence and rejected evidence.

Information-gain labels may include `HIGH`, `MEDIUM`, `LOW`, `ZERO`, and `NEGATIVE`, but raw evidence must remain available for re-analysis.

### Performance and resource telemetry

Capture when available:

- tokens in/out;
- exposed thinking tokens;
- token timestamps/logprobs/top-k/entropy for local models when supported;
- prompt processing and generation rate;
- queue time;
- inference time;
- tool time;
- verification time;
- total wall clock;
- CPU/RAM/GPU/VRAM utilization;
- scheduler assignment, batching, and contention.

Wall-clock comparisons must separate scheduling/queue effects from model and system execution time.

### Ownership and causal attribution

Every meaningful state change should identify its owner when possible:

- model decision;
- system decision;
- skill instruction;
- memory influence;
- tool/hand output;
- verifier feedback;
- environment event;
- human intervention.

Human intervention must never be silently blended into autonomous performance.

### Open-source runtime-to-source mapping

For open systems, connect important observed events to:

`commit -> file -> class/function -> condition/configuration -> runtime event`

Compare documented/self-described behavior with observed behavior. Documentation is not treated as proof.

## Decision-point checkpoints and derivative experiments

Every expensive run should maximize future cheap experiments.

At meaningful checkpoints preserve enough state for later replay. Candidate derivative work includes:

- continuation versus fresh replay;
- alternate action forks;
- same state with one evidence item removed;
- changed context ordering;
- changed tool description or permission;
- changed memory/skill injection;
- repeated checkpoint samples to measure decision stability;
- context-item causal usefulness;
- path-dependence tests;
- mechanism necessity/sufficiency tests;
- local-model reproduction of a frontier behavior.

The goal is for a single expensive frontier trajectory to generate many cheaper local and deterministic follow-up experiments.

## Required trajectory-autopsy outputs

Each run should be capable of producing, directly or offline:

- decision graph;
- evidence graph;
- hypothesis/reasoning graph;
- assumption ledger;
- contradiction ledger;
- failure propagation graph;
- verification coverage graph;
- context provenance graph;
- memory-effect record;
- tool/skill/hand value ledger;
- first meaningful divergence;
- near-miss list;
- failure and success precursor signatures;
- counterfactual candidates;
- replay points;
- checkpoint lineage;
- immutable evidence manifest/hashes.

## Mechanism harvesting

The objective is not a leaderboard. For each useful divergence:

`trajectory comparison -> first meaningful divergence -> candidate mechanism -> necessity test -> sufficiency test -> boundary/negative-transfer test -> interaction/order test when justified -> fresh transfer -> Learning Compiler`

Learning Compiler destinations remain:

- `BRAIN`
- `SYSTEM`
- `SKILL`
- `TOOL_HAND`
- `MEMORY`
- `NEGATIVE_EVIDENCE`

## Edge-case law

Rare, absurd, adversarial, compound, and cross-domain cases are mandatory because ordinary tasks often hide the true frontier. Edge-case descendants must still have objective contracts and blind verification. Absurd surface form is useful only when the underlying causal/constraint structure remains rigorous.

## Stop condition

The adaptive frontier is not completed by passing all questions. A run stops only because a predeclared experimental/resource budget, safety boundary, unavailable required capability, or infrastructure condition requires suspension. Suspension must preserve resumable state and evidence rather than discard the case.
