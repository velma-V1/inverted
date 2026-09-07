# Universal Harvest — Frozen Contract

**Status:** FROZEN DESIGN — implementation not yet approved

This contract freezes the shared laws for all future Universal Harvest templates. It is intentionally separate from the historical Inverted executor/auditor experiment and must not alter that evidence.

## Change control

- This document is the authoritative shared contract for Local Continuation Harvest and Frontier/Cloud Harvest.
- Do not weaken, silently reinterpret, or replace these requirements during implementation.
- Any material change requires explicit operator approval and must be documented as a versioned amendment.
- Raw historical evidence is immutable.
- **Data collection is cheap; retesting is not.** Every expensive run must leave enough evidence for later analysis, replay, comparison, and counterfactual work without rerunning the frontier model whenever possible.
- Never rely on conversational memory as the sole source of experimental requirements. Read these frozen specifications and, when necessary, the source chat that produced them.

## Core experiment laws

1. **Success never ends testing.** Every independently verified success creates a harder descendant challenge.
2. **Failure never ends the campaign.** A wrong answer gets one bounded repair retry for that model; repeated failure freezes the exact state and escalates or queues the case.
3. **Attempt failure != task termination != campaign failure.** Preserve all three separately.
4. **No uncontrolled retry loops.** One repair retry per wrong answer, per model, per challenge. Hard failure, verified stuck state, context/tool/output exhaustion, unsupported capability, repeated-action loop, or infrastructure fault may escalate immediately.
5. **No model should be able to pass the whole test.** Frontier depth is adaptive and budget-bounded, not a finite benchmark ceiling.
6. **Branch the frontier.** Successful tasks may generate deeper, perturbed, compound, transfer, recovery, order-sensitive, and edge-case descendants. The scheduler chooses descendants by expected information value.
7. **Preserve negative evidence.** Wrong answers, malformed outputs, useless searches, false confidence, loops, failed skills, tool misuse, stale verification, negative transfer, regressions, and wasted work are first-class evidence.
8. **Freeze before escalation.** Every handoff preserves the exact checkpoint lineage and state needed for continuation and later fresh-control replay.
9. **Independent verification decides correctness.** Model confidence and self-reported completion are never substitutes for objective evidence.
10. **State-changing actions invalidate prior verification.** Completion is forbidden until current-state verification covers all required contract dimensions.
11. **Mechanisms must earn inclusion.** Source systems, books, documentation, prompt archaeology, and teacher trajectories generate hypotheses. Retained architecture requires causal evidence, boundaries, and fresh transfer.
12. **Assumptions are working state, never truth.** Every assumption remains revisable and must retain provenance and contradiction status.
13. **Experience is not learning until autopsied.** A success or failure becomes reusable learning only after causal attribution, boundary analysis, and promotion through the Learning Compiler.
14. **Structural dissent is required without a permanent critic persona.** Counterhypotheses and disconfirming evidence are invoked when uncertainty, contradiction, or consequence warrants them; they are not blindly appended to every step.
15. **Verification itself must be tested.** Sentinel/known-fault injections are permitted and encouraged to measure verifier sensitivity, false acceptance, and failure-detection coverage.
16. **Tools and mechanisms must target the observed error distribution.** Do not grow a comprehensive toolbox merely because a capability exists.
17. **Executable truth should generate documentation/manifests where practical.** Prefer machine-derived state, schemas, inventories, and manifests over manually duplicated claims.

## Universal fairness contract

Comparable arms must begin from the same frozen experimental specimen whenever the system under study permits it:

- same task/objective and success contract;
- same starting workspace contents and hash;
- same task-visible constraints;
- same blind verifier and scoring rules;
- equivalent permission/capability envelope where comparison requires equality;
- same resource-accounting definitions;
- same seed/sampling configuration when the same underlying model/runtime supports it;
- no access to another arm's answer, trajectory, or hidden labels.

System-native individuality is preserved in native-system arms. A capability that is intrinsic to a system (skills, hooks, compaction, memory, sandboxing, subagents, repository maps, recovery policy, etc.) is not disabled merely for superficial symmetry. Equality applies to the experimental contract; native-system mechanisms remain part of the specimen unless the arm is an explicit ablation.

## Mandatory Systems Harvest Lab

Compatible executable open systems must be run as reproducible experimental specimens in isolated, pinned containers.

The shared Harvest Lab must provide:

- one isolated writable workspace per arm;
- pinned repository commit/version and dependency lock;
- reproducible container/image digest;
- controlled mounts and permissions;
- independent filesystem/process observation;
- common event normalization;
- common blind verifier interface;
- evidence hashing/manifests;
- no cross-arm workspace leakage;
- network policy recorded explicitly.

Docker is the default execution boundary for compatible open systems. If a system cannot validly run inside Docker, the exception must be explicit, justified, and replaced by an equivalently isolated/reproducible sandbox rather than silently weakening the design.

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
- interaction between previously isolated failure modes;
- recovery after partial or poisoned prior work;
- novel compositional absurdity and rare edge cases.

Difficulty generation must preserve the causal structure being tested and record why the child challenge is harder than its parent.

## Required evidence architecture

Every run produces two strictly separated layers:

1. **IMMUTABLE RAW EVIDENCE** — the ground-truth event archive. Never rewritten by later interpretation.
2. **NORMALIZED / TRANSLATED EVIDENCE** — derived analysis that may be regenerated as translators improve.

Every derived claim retains provenance. Never label inferred reasoning as directly observed reasoning.

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

## Canonical Universal Forensic Event schema

Every observer/adapter normalizes events into one common schema while preserving the original raw event alongside it.

Required canonical fields, allowing null when truly unavailable:

```text
event_id
timestamp
run_id
task_id
parent_task_id
system
system_version
model
model_tier
arm
attempt
checkpoint_id
event_type
actor
provenance
input
output
state_before
state_after
context_refs
memory_refs
reasoning_refs
tool
skill
hand
subagent
files_read
files_written
command
verification
error
recovery
system_intervention
queue_time
inference_time
tool_time
verification_time
wall_time
tokens_in
tokens_out
resource_snapshot
evidence_refs
source_code_refs
```

Adapters may add fields but may not silently omit required evidence that is technically available.

## Passive versus instrumented reasoning modes

Reasoning observation is divided into two experimental conditions and must never be mixed:

### `NATIVE_PASSIVE`

Observe only what the native system/runtime naturally exposes. Do not ask the model extra questions about its hypotheses, confidence, or reasoning state.

### `INSTRUMENTED_REASONING`

Explicitly request or elicit structured reasoning-state reports such as current hypothesis, evidence, uncertainty, expected consequence, or verification plan.

Because instrumentation can itself improve reasoning, `NATIVE_PASSIVE` and `INSTRUMENTED_REASONING` are separate arms with separate disposition and timing records. Any benefit from forced externalization is itself a candidate mechanism.

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
- context/output limits;
- hardware/environment;
- workspace/task hashes;
- permissions/sandbox state.

### Complete model-visible state

Preserve what the model could actually see at each important decision:

- system/developer/user instruction hierarchy;
- full active context;
- context ordering and token position;
- skills loaded;
- memory injected;
- tool schemas and available capabilities;
- prior observations/tool outputs;
- summaries/compactions;
- current workspace/system state;
- remaining context/output/resource budgets when observable.

### Prompt and context lineage with stage hashing

Record and hash every transformation stage:

`original task -> system wrapper -> developer/system instructions -> memory injection -> skill injection -> retrieval -> tool schemas -> compression/summary -> final model-visible prompt`

For every stage record:

- exact stage hash;
- source hashes;
- transformation responsible;
- content added/removed/reordered;
- token count/position when measurable.

For every context item record when possible:

- source and source hash;
- retrieval reason/rank;
- admission/rejection decision;
- transformation/compression;
- ordering/position;
- truncation/information loss;
- duplication/conflict/staleness;
- whether later used, ignored, contradicted, or misleading.

### Memory

When exposed or instrumentable, record:

- creation;
- admission/rejection;
- provenance/age;
- retrieval;
- mutation;
- persistence;
- forgetting/deprecation;
- conflict/staleness;
- whether memory changed a hypothesis, action, search path, tool choice, or completion decision;
- information apparently known earlier but lost/ignored later;
- false remembered/generated state contradicted by current evidence.

### Thought, reasoning, meta-reasoning, and instability

When the runtime exposes reasoning/thinking, preserve it raw. Also derive a normalized reasoning state containing when supportable:

- problem representation;
- hypotheses/counterhypotheses;
- assumptions;
- contradictions;
- evidence used/rejected;
- uncertainty/confidence changes;
- candidate decisions;
- expected consequences;
- verification intent;
- repair choice;
- frame change/reset;
- loop/repetition signatures;
- meta-reasoning escalation;
- psychological-set / contradicted-frame persistence.

Record reasoning-instability measures where supportable:

- hypothesis oscillation;
- answer/recommendation reversals;
- confidence swings;
- route/tool-plan changes;
- repeated frame switching;
- repeated self-contradiction;
- reasoning entropy/instability proxies.

When proprietary systems do not expose hidden reasoning, reconstruct only from observable evidence and mark it `INFERRED_ANALYSIS`.

### Decision environment

At important decisions preserve:

- available actions/tools/capabilities;
- candidate actions considered/ranked when exposed;
- rejected alternatives/reasons when exposed;
- selected action;
- evidence that would have changed the decision when measurable;
- counterfactual paths worth replaying later;
- unused capabilities that existed but were not discovered/applied.

### Expectation versus reality

Before actions, capture predicted consequence when exposed or explicitly instrumented. Afterward record:

- actual consequence;
- discrepancy;
- belief/state delta;
- evidence causing the update;
- whether contradictory evidence was resolved, ignored, deferred, or reinterpreted to preserve a failed frame.

### System intervention log

Every harness/system intervention is a first-class event with before/after state and causal owner. Required intervention types include at minimum:

- `BLOCK`
- `REWRITE`
- `RETRY`
- `ROUTE`
- `SUMMARIZE`
- `COMPACT`
- `INJECT`
- `ESCALATE`
- `MUTATION_GATE`
- `PERMISSION_CHANGE`
- `ROLLBACK`
- `CHECKPOINT`
- `RESUME`

The recorder must distinguish model-initiated behavior from system-imposed behavior.

### Tools, skills, hands, and subagents

Capture:

- every tool/capability offered;
- selection/arguments;
- results, stdout/stderr, exit status, duration, retries, cancellation;
- capability discovery attempts;
- hand delegation contract, state, artifacts, cancellation, retrieval, verification;
- subagent lineage, delegated context, withheld context, returned state, parent acceptance/rejection;
- availability versus actual utilization.

#### Skill lifecycle

Every skill should be traceable through:

`discovered -> selected -> loaded -> partially_used -> completed -> verified -> updated/deprecated`

Record skipped stages, failed triggering, partial use, misuse, and whether verification demonstrated that the skill actually helped.

Maintain empirical value ledgers for tools/skills/hands: available, discovered, selected, useful, unnecessary, harmful, unavailable-when-needed, misunderstood, information gain, success/failure association.

### Filesystem, execution, environment, and network

Capture where practical:

- meaningful reads/writes/deletes/renames;
- every important intermediate diff and artifact evolution;
- hashes/state snapshots before/after mutation;
- shell commands, cwd, process tree, exit codes;
- environment changes/observations;
- network destinations/timing/metadata when useful and safe;
- secrets/credentials redacted rather than copied into evidence.

### Verification and completion

Capture:

- frozen verification obligations;
- checks performed/omitted;
- verification coverage;
- stale evidence;
- post-mutation verification;
- blind verifier output;
- model/system belief that work is complete;
- exact evidence permitting/denying `COMPLETE`;
- unverified-success/premature-completion events;
- sentinel/known-fault verifier challenges and whether the verifier detected them.

### Failure and recovery

Record separately:

- first causal error;
- first externally detectable error;
- first model/system recognition;
- detection/recognition latency;
- propagation graph;
- diagnosis;
- repair selection;
- root-cause versus symptom repair;
- failure migration;
- recovery verification;
- recurrence;
- loops/repeated action/tool/reasoning signatures;
- near misses/one-change-away outcomes.

### Search and information efficiency

Track:

- plausible search space versus inspected region;
- relevant/irrelevant branches;
- wrong-file/tool accesses;
- redundant reads/searches;
- backtracking/abandoned branches;
- time to first discriminating evidence;
- information gain per read/search/tool action;
- resource allocation per hypothesis/phase;
- ignored/rejected evidence.

Information-gain labels may include `HIGH`, `MEDIUM`, `LOW`, `ZERO`, and `NEGATIVE`, but raw evidence remains available for re-analysis.

### Performance and local-model telemetry

Capture when available:

- tokens in/out;
- exposed thinking tokens;
- token IDs/timestamps;
- logprobs/top-k/candidate probabilities;
- entropy/uncertainty proxies;
- stop reason and stop probabilities when exposed;
- repetition-pattern telemetry;
- prompt processing/generation rate;
- exact context utilization;
- KV/cache statistics when runtime exposes them;
- generation instability around important decisions;
- queue/inference/tool/verification/total wall time;
- CPU/RAM/GPU/VRAM utilization;
- scheduler assignment, batching, contention.

Wall-clock comparisons separate scheduling/queue effects from model/system execution time.

### Ownership and causal attribution

Every meaningful state change identifies its owner when possible:

- model decision;
- system decision;
- skill instruction;
- memory influence;
- tool/hand output;
- verifier feedback;
- environment event;
- human intervention.

Human intervention is never silently blended into autonomous performance.

### Open-source runtime-to-source mapping

For open systems, connect important observed events to:

`commit -> file -> class/function -> condition/configuration -> runtime event`

Compare documented/self-described behavior with observed behavior. Documentation is not proof.

## Decision-point checkpoints and derivative experiments

Every expensive run should maximize future cheap experiments.

At meaningful checkpoints preserve enough state for later replay. Candidate derivative work includes:

- continuation versus fresh replay;
- alternate action forks;
- same state with one evidence item removed;
- changed context ordering;
- changed tool description/permission;
- changed memory/skill injection;
- repeated checkpoint samples to measure decision stability;
- context-item causal usefulness;
- path-dependence tests;
- mechanism necessity/sufficiency tests;
- local-model reproduction of frontier behavior.

The goal is for one expensive frontier trajectory to generate many cheaper local/deterministic follow-up experiments.

## Mandatory automatic trajectory-autopsy package

Every expensive frontier run must automatically emit a reusable research asset, not merely be capable of producing one later.

Required package shape:

```text
RUN/
  raw/
  checkpoints/
  prompts/
  context/
  reasoning/
  tools/
  skills/
  memory/
  filesystem/
  processes/
  verification/
  metrics/
  source-map/
  decision_graph.json
  evidence_graph.json
  hypothesis_graph.json
  assumption_ledger.json
  contradiction_ledger.json
  failure_graph.json
  verification_graph.json
  context_graph.json
  tool_skill_hand_value.json
  memory_effect.json
  first_divergence.json
  near_misses.json
  precursor_signatures.json
  counterfactual_candidates.json
  replay_points.json
  checkpoint_lineage.json
  manifest.sha256
```

A field/file may explicitly report `unavailable` with reason when the platform cannot expose it; it may not disappear silently.

## Cross-tier concurrent scheduler

The Universal Harvest controller must support concurrent execution across independent workers rather than serializing by design.

It must be able to schedule simultaneously, when resources permit:

- Claude native/resolution workers;
- Codex native/resolution workers;
- ChatGPT reference/native work when operator-driven product execution is available;
- one or more local 1–2B workers;
- Qwen escalation workers;
- independent verifier/analysis workers;
- multiple cloud-GPU Qwen/local-system workers.

Concurrency must never contaminate fairness. Queue time, resource contention, batching, and worker assignment are separately recorded.

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

The adaptive frontier is not completed by passing all questions. A run stops only because a predeclared experimental/resource budget, safety boundary, unavailable required capability, or infrastructure condition requires suspension. Suspension preserves resumable state/evidence rather than discarding the case.
