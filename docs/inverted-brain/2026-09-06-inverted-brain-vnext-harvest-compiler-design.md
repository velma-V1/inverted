# Inverted Brain vNext — Systems Harvest and Learning Compiler

## Status
This document defines the direction after the original Frontier Mechanism Harvest preregistration. The earlier design and all historical evidence remain immutable. This document supersedes it only for future architecture work.

## Objective
Build the smallest justified architecture that makes a fixed local model substantially more capable by combining:
- an evidence-driven internal cognitive policy (`Inverted Brain`);
- an independent execution/governance plane (`Inverted System`);
- selectively loaded skills and knowledge;
- tools and specialized hands;
- causal learning from success and failure;
- later, weight-level fine-tuning using only validated learning artifacts.

The goal is not to reproduce Codex, Claude Code, Prime Agent, Pi, SWE-agent, or another framework. Existing systems are experimental organisms: harvest what makes them special, prove why it works, and compile only the useful mechanism into the correct Inverted layer.

## Core Research Question
Which mechanisms measurably change the capability frontier of the same model, why do they work, where do they fail, how do they interact, and where should each validated mechanism live in the final architecture?

A system-level win is evidence for investigation, not evidence that the whole system should be copied.

## Hard Research Law
No new experiment is created unless an existing result leaves a specific architectural decision unresolved. Interesting observations become hypotheses; hypotheses become architecture only after boundary, causal, and fresh-transfer evidence.
## Architecture Boundary

### Inverted Brain
Owns cognition, not authority:
- exact problem-state construction;
- unknown/contradiction identification;
- causal hypotheses and counterhypotheses;
- evidence selection and relevance gating;
- reasoning-mode and skill selection;
- dependency inspection before commitment;
- repair selection;
- verification planning;
- meta-reasoning escalation when the current reasoning frame becomes unreliable.

### Inverted System
Owns execution authority and independent truth checks:
- permissions and sandbox boundaries;
- action admission and mutation gating;
- state/event ledger;
- deterministic verification;
- post-mutation verification invalidation;
- rollback/reconciliation;
- evidence preservation and provenance;
- budgets, retries, cancellation, promotion, and recovery;
- separation of the self-improvement plane from the governance plane.

The Brain may propose. The System decides whether an action is admissible and whether the observed result satisfies the contract.
## Capability Layers
The final system must expose capability without forcing the model to memorize every procedure.

### Skills
Reusable procedural knowledge loaded on demand. A mature skill should declare:
- applicability/trigger conditions;
- required inputs and prerequisites;
- adjustable parameters;
- procedure and decision rules;
- anti-patterns and known failure modes;
- verification obligations;
- provenance/version;
- model-specific adaptations only when demonstrated necessary.

### Tools
Atomic capabilities with narrow contracts: search, file operations, APIs, deterministic computation, retrieval, or external services. Tool selection should follow capability routing rather than free-form improvisation.

### Hands
Execution specialists that can perform multi-step work behind a bounded contract. Examples include terminal/code hands, intelligent browser hands such as Comet, media-generation hands, future CAD/simulation hands, and other domain executors.

A Hand is never the authority on its own success. It returns observations/artifacts to the System, which verifies them against the original task contract.

## Progressive Disclosure
Prefer `capability index -> relevant skill/tool/hand -> required detail -> raw evidence when needed`. Do not dump the complete skill library, archive, or source material into Qwen context.
## Meta-Reasoning and Psychological Set
The Brain may reason about its own reasoning, but recursion is bounded. Escalate one meta-level only when there is evidence that the lower level is unreliable:
- unresolved contradiction;
- repeated failed hypothesis or repeated action pattern;
- external evidence disagreement;
- unexplained failure migration;
- inability to account for a verifier result;
- low-confidence causal attribution at a consequential decision.

`PSYCHOLOGICAL_SET` is a required failure class for future harvests: the model continues preserving a failed frame by reinterpreting new evidence instead of changing representation or hypothesis family.

Required response to detected lock-in:
1. invalidate the current search frame as privileged;
2. reconstruct state from observable evidence;
3. generate materially different hypotheses or representation;
4. acquire discriminating evidence;
5. stop recursive introspection and escalate externally if the contradiction remains unresolved.

Meta-reasoning is not an excuse for unlimited thinking. It must pay complexity rent and has a hard escalation/stop path.

## Epistemic State and Provenance
Durable knowledge must retain type and origin. Recommended provenance labels include `observed`, `measured`, `verified`, `teacher-derived`, `causally-supported`, `inferred`, `hypothesis`, `contradicted`, `failed`, and `deprecated`.

Retrieval may be broad; application is narrow. Retrieved material does not gain authority merely because it is relevant.
## Production Path vs Learning Path
A live task failure must split into two lanes.

### Production lane
Use the safest known repair, verify the current task, finish the user objective, and do not turn the live job into an open-ended experiment.

### Learning lane
Preserve the failed state and trajectory, construct an isolated reproduction, localize the first critical divergence, test causal interventions, derive the minimal mechanism, and validate it on fresh tasks.

The production lane may finish before the learning lane. The learning lane may conclude that no reusable mechanism exists. Neither result rewrites the other's evidence.

## Learning Compiler
Every retained lesson must be classified before installation:

`reasoning_policy -> BRAIN`

`invariant/governance_rule -> SYSTEM`

`repeatable_procedure -> SKILL`

`executable_capability -> TOOL_HAND`

`durable_fact -> MEMORY`

`failed/rejected mechanism -> NEGATIVE_EVIDENCE`

Every compiled artifact carries evidence IDs, provenance, scope, boundary conditions, known failure modes, verification obligations, and complexity cost. A source cannot promote itself; promotion requires independent experimental evidence.
## Harvest Fest Method
Systems are not ranked as monoliths. The primary unit of discovery is a mechanism.

1. Hold the underlying model constant when possible, especially Qwen3.5-9B.
2. Find tasks near the model's mixed pass/fail frontier.
3. Compare observable trajectories across systems.
4. Locate the earliest critical divergence, not merely the final visible error.
5. Propose a concrete mechanism and predicted causal pathway.
6. Test necessity by removing/delaying/replacing the mechanism in a successful system.
7. Test sufficiency by forcing the minimal mechanism into a failing Qwen/Inverted arm.
8. Verify that predicted intermediate process changes occur, not only the final pass/fail.
9. Test scope, negative transfer, ordering, and interactions.
10. Compile the result into the correct destination only after fresh transfer.

Preferred causal pattern:
- teacher normal: PASS;
- teacher minus X: FAIL/degrades;
- Qwen normal: FAIL;
- Qwen plus X: PASS/improves.

If X helps only with Y, record an interaction bundle instead of falsely assigning the gain to X alone.

## Interaction and Ordering
More support is not assumed better. Test `A`, `B`, `A+B`, and order-sensitive variants only when evidence indicates interaction. Prefer targeted/fractional interaction tests over combinatorial brute force. Redundant Brain/System mechanisms should be simplified until each layer has one clear responsibility.
## Source Roles
Primary executable teachers/chassis: Codex, Claude Code/Agent SDK, Prime Agent, Pi, oh-my-cli, mini-SWE-agent, and Aider. Mechanism references include SWE-agent and AegisEvo. Specialized hands include Comet MCP and media workers. Book-to-Skill and Taste Skill are skill-architecture references. Hyperspace AGI is reserved for later distributed learning. Prime Verifiers/prime-rl are reserved for later post-training.

Prompt dumps such as CL4R1T4S are hypothesis generators only. They can suggest mechanisms to test but cannot establish that a mechanism is present, effective, or causal in a current proprietary system.

Weinberg's *The Psychology of Computer Programming* is a durable research reference for psychological set, egoless review, independent evaluation, regression discipline, precommitted testing, and separation of production repair from learning experiments. Book-derived principles still require operational definitions before they become executable Brain/System rules.

## Build Before Fine-Tune
Harvest Fest ends when the retained architecture has justified components with known purpose, causal evidence, boundaries, placement, and fresh-transfer results. At that point architecture freezes.

Only then run the factorial interaction test:
- A: Qwen RAW;
- B: Qwen + Brain vNext;
- C: Qwen + Inverted System vNext;
- D: Qwen + Brain vNext + Inverted System vNext.

Use the 2x2 to estimate Brain effect, System effect, and Brain x System interaction. It is a tuning/interaction experiment, not another broad discovery campaign.

After the architecture freezes, tune meta-reasoning threshold, verification depth, state refresh frequency, context amount, search compression, inspection depth, recovery/escalation thresholds, router thresholds, module order, tool-result representation, planning depth, compute allocation, and finally Qwen sampling.

Weight-level SFT/RL/distillation comes last, using validated positive and negative trajectories rather than generic successful answers.
## Target Architecture

```text
INPUT
  -> INVERTED BRAIN
       state / hypotheses / counterhypotheses / evidence / meta-reasoning
  -> INVERTED SYSTEM
       admission / permissions / execution / verification / rollback
  -> CAPABILITY ROUTER
       -> SKILLS
       -> TOOLS
       -> HANDS
  -> OBSERVABLE RESULT
  -> independent verification
  -> structured discrepancy or verified completion
```

Learning runs beside production:

```text
SUCCESS / FAILURE
  -> preserve trajectory and evidence
  -> autopsy + causal replay
  -> boundary / interaction tests
  -> LEARNING COMPILER
       Brain | System | Skill | Tool-Hand | Memory | Negative Evidence
  -> fresh transfer
  -> retained registry or rejected archive
```

## Stop Conditions
Harvest discovery stops for a component when its purpose, causal pathway, failure boundary, placement, interactions, and fresh-transfer effect are known well enough to make an implementation decision. Zero retained mechanisms is valid evidence.

A new external system is added only to answer an unresolved question that current sources cannot discriminate. A mechanism that does not pay complexity rent is removed even if it sounds sophisticated.

## Claim Boundary
The vNext architecture is a research program, not evidence that Inverted has already achieved general intelligence or replaced a model's native reasoning. Claims remain bounded to measured tasks, frozen configurations, and independently verified experiments.