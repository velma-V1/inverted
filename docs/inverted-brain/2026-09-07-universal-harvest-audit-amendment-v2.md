# Universal Harvest — Audit Amendment v2

**Status:** FROZEN DESIGN AMENDMENT — implementation not yet approved

This versioned amendment is part of the authoritative Universal Harvest specification set. It resolves ambiguities found during the post-amendment audit. Where wording here is more specific than the shared contract or Local/Frontier specs, this amendment controls. It does not authorize implementation.

## 1. Frontier-climbing ownership is explicit

For each adaptive task family, the current model tier keeps climbing the descendants it earns until that tier reaches its verified frontier.

```text
1–2B
  PASS -> harder child -> 1–2B continues on that child
  WRONG -> one retry
  RETRY PASS -> harder child -> 1–2B continues
  RETRY FAIL/STUCK -> FREEZE A -> Qwen takes over this lineage

Qwen 9B
  PASS -> harder child -> Qwen continues on that child
  WRONG -> one retry
  RETRY PASS -> harder child -> Qwen continues
  RETRY FAIL/STUCK -> FREEZE B -> lineage enters Devstral tail queue
  controller immediately frees local sweep capacity for the 1–2B worker to continue another independent/root lineage

Devstral 24B (end-of-sweep tail)
  resume FREEZE B
  PASS -> harder child -> Devstral continues on that lineage
  WRONG -> one retry
  RETRY PASS -> harder child -> Devstral continues
  RETRY FAIL/STUCK -> FREEZE C -> Frontier Resolution

Claude/Codex resolution
  continue independently from identical FREEZE C copies
  preserve local failures and resolver outcomes separately
```

A harder child is never silently reassigned to a weaker tier merely because a stronger tier solved its parent. The scheduler may launch separate fresh/control branches, but continuation lineage ownership remains explicit in evidence.

## 2. Authoritative Harvest source inventory

`configs/inverted_brain/harvest_sources.yaml` is the authoritative source catalog for Systems Harvest admission and source role. The frozen test templates must consume or validate against it rather than relying on a hard-coded partial list.

The current eleven general systems/reference systems are explicitly preserved:

1. Codex
2. Claude Code / Claude Agent SDK instrumentation surface
3. Prime Agent
4. Pi
5. oh-my-cli
6. SWE-agent
7. mini-SWE-agent
8. Aider
9. AegisEvo
10. OpenHands
11. Goose

ChatGPT is an additional high-value frontier-native/reference specimen and is not counted as a twelfth interchangeable local harness because normal ChatGPT subscription sessions are not the same automation surface as the local/open systems.

Specialized/non-general sources are also explicitly preserved for targeted mechanism harvest rather than forced full-agent ranking:

- Book-to-Skill;
- Taste Skill;
- Comet MCP;
- media-inference-worker;
- Hyperspace AGI (later distributed-learning reference);
- Prime Verifiers;
- prime-rl;
- CL4R1T4S / Claude-Fable prompt archaeology as hypothesis source only;
- Gerald Weinberg, *The Psychology of Computer Programming*;
- failure-attribution/observability references in the source catalog such as Who-and-When and PandaProbe when they answer a specific unresolved instrumentation/attribution question.

Mixture-of-Kittens and a broad framework zoo remain excluded unless a future explicit unresolved question justifies admission.

## 3. Teacher-trajectory preservation versus copying

The source-catalog rule `full_teacher_trajectory_copy_forbidden` means **do not install or imitate a complete frontier trajectory as architecture/training truth merely because it succeeded**. It does **not** mean discard evidence.

For every permitted frontier run:

- preserve the complete observable raw trajectory as immutable research evidence;
- do not expose one teacher's answer/trajectory to another native comparison arm;
- do not promote a whole trajectory wholesale into Brain/System/Skill/Memory;
- extract candidate mechanisms and require causal/boundary/fresh-transfer evidence before promotion.

## 4. Frozen Weinberg-derived hypothesis inventory

The following book-derived principles are explicitly retained as hypotheses/rules to operationalize and test; none becomes architecture merely because it came from the book:

- quality is contextual; no universal single notion of a good solution;
- assumptions are necessary working state, never privileged truth;
- psychological set / frame lock-in requires representation reset rather than another identical retry;
- egoless reasoning: the first candidate/hypothesis has no privileged status;
- structural dissent/counterhypotheses must be available without imposing a permanent critic persona on every step;
- execution and evaluation should be separable so the System can independently verify Brain/model claims;
- tasks/programming work are heterogeneous, supporting role/routing specialization rather than one universal reasoning procedure;
- experience becomes learning only after reflection/causal autopsy;
- production recovery and research learning are separate lanes;
- verification obligations should be frozen/precommitted before seeing the outcome when feasible;
- inject known/sentinel faults to verify that the verifier detects them;
- regression checks should be cheap and automatic;
- tools should target the observed error distribution rather than accumulate as a comprehensive toolbox;
- progressive disclosure should keep irrelevant knowledge out of active context;
- formal unambiguity is not the same as model unambiguity;
- confidence should be proportional to evidence and verification coverage;
- executable state should generate manifests/documentation where practical;
- whole systems should be studied by mechanisms and interactions rather than monolithic rankings.

## 5. Additional mandatory high-value evidence

The Universal recorder must explicitly derive/preserve the following in addition to the already frozen channels.

### Knowledge/claim provenance graph

Every consequential claim or belief should link, where recoverable, to one or more of:

- prompt/instruction;
- file/repository state;
- tool/hand output;
- memory;
- skill;
- teacher/reference evidence;
- prior failed attempt;
- explicit assumption;
- model inference;
- verifier result;
- human intervention.

Presence in context and causal use are separate facts.

### State-ownership ledger

For every consequential current belief/state element, record which layer presently owns or asserts it when recoverable:

- model;
- Brain/reasoning policy;
- System/harness;
- memory;
- skill;
- tool/hand;
- subagent;
- verifier;
- environment;
- human/operator.

Ownership can change over time. Preserve ownership transitions and disagreements between layers rather than collapsing them into one global truth state.

### Attention/resource-allocation proxy

Do not call this neural attention unless actual model internals expose it. Record the observable allocation of scarce resources across hypotheses/files/tools/branches:

- tokens/context devoted;
- reads/searches;
- tool calls;
- wall/inference time;
- revisits;
- mutations;
- verification effort.

This proxy studies where the system spent cognition/compute, not hidden attention weights.

### Optional deep local neural telemetry

For open/local models, selected high-value checkpoints may additionally capture model-internal telemetry when the runtime/framework exposes it without invalidating the comparison arm, including:

- selected hidden-state/activation summaries or probes;
- attention diagnostics;
- layer-level measurements;
- cache/KV diagnostics;
- token-level uncertainty distributions.

These are neural telemetry, **not** a readable transcript of hidden thought. If obtaining them changes runtime behavior materially, they belong in a separately labeled instrumented arm.

### Redundancy and overlap ledger

Record when two mechanisms appear to perform the same function, when one adds no measurable value, and when combined use is harmful or merely redundant. Candidate architecture must make every retained component pay complexity rent.

### Order and interaction ledger

When evidence suggests interaction, preserve state/outcome for targeted variants such as `A`, `B`, `A+B`, `B+A`, and order-sensitive `A->B`, `B->A`, or sandwich variants such as `A->B->A`. Do not brute-force interactions without a causal reason.

## 6. Mandatory per-task/system comparison artifact

Every task/challenge and adaptive descendant must produce a normalized comparison artifact after eligible arms are available. At minimum it records:

- task and parent IDs;
- exact frozen specimen hash;
- systems/models/tiers attempted;
- native versus instrumented condition;
- attempt/retry/escalation lineage;
- pass/fail/unresolved disposition per arm;
- frontier depth reached;
- first meaningful divergence when comparable;
- major context/tool/skill/memory differences;
- verification coverage;
- failure/recovery class;
- queue/inference/tool/verifier/wall time;
- resource use;
- links to raw evidence/checkpoints;
- candidate mechanisms/counterfactuals.

This artifact is for comparison/navigation only; it never replaces raw arm evidence.

## 7. Frontier-data maximization law

A frontier run is an expensive research specimen. Collection must err toward preserving observable data when safe/legal rather than deciding during the run that a datum appears unimportant.

The recorder must therefore preserve:

- raw positive and negative behavior;
- malformed and partial outputs;
- abandoned plans/searches;
- useless/redundant tool use;
- every checkpoint needed for later counterfactual replay;
- all observable memory/thought/reasoning and system state;
- native plus independent external telemetry;
- metadata sufficient to reconstruct timing, resource use, and model-visible state.

Filtering/compression may occur only in derived analysis layers. The immutable raw archive remains the research source of truth.

## 8. Implementation gate remains closed

This amendment changes documentation only. Local and Frontier/Cloud template implementation remains prohibited until the operator explicitly approves the complete frozen specification set after audit.
