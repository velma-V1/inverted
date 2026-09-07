# Local Continuation Harvest — Frozen Specification

**Status:** FROZEN DESIGN — template implementation requires explicit operator approval

This specification is subordinate to `2026-09-07-universal-harvest-frozen-contract.md`. If a requirement appears in the shared contract and is not repeated here, it still applies.

## Purpose

Use a cheap-to-expensive local model ladder to harvest system behavior, failure/recovery boundaries, model thresholds, and mechanism evidence while minimizing wasted compute. The primary experimental object is the **system**, but model capability is treated as a controlled interacting variable rather than ignored.

The local campaign must not terminate because an individual model or task attempt fails.

## Locked continuation ladder

For every compatible system and challenge:

```text
1–2B PRIMARY
  attempt 1
    PASS -> independently verify -> create harder child challenge
    WRONG -> exactly one repair retry with exact verifier/failure feedback
      PASS -> verify -> create harder child
      FAIL/STUCK/HARD LIMIT -> FREEZE A -> QWEN 9B

QWEN 9B RESCUE
  continue from FREEZE A
  attempt 1
    PASS -> verify -> create harder child
    WRONG -> exactly one repair retry
      PASS -> verify -> create harder child
      FAIL/STUCK/HARD LIMIT -> FREEZE B -> defer to Devstral queue

MAIN SWEEP CONTINUES
  1–2B proceeds to other work; Qwen services escalations as resources permit.

END-OF-SWEEP DEVSTRAL TAIL
  load Devstral 24B
  resume each FREEZE B case
  attempt 1
    PASS -> verify -> create/record appropriate harder descendant
    WRONG -> exactly one repair retry
      PASS -> verify
      FAIL/STUCK/HARD LIMIT -> FREEZE C -> Frontier Resolution Queue

FRONTIER RESOLUTION
  Claude and Codex receive the unresolved FREEZE C case independently.
  Selected cases also receive fresh-from-original controls.
```

## Retry law

- Exactly **one repair retry per wrong answer, per model, per challenge**.
- The retry must record precisely what feedback was added and what state changed between attempts.
- A hard runtime/model failure, unsupported operation, verified stuck state, repeated loop, exhausted context/tool/output budget, or infrastructure condition may bypass the retry when retrying would add no valid information.
- No repeated uncontrolled external retries.

## Failure semantics

Maintain distinct states:

- `ATTEMPT_FAILED`
- `TASK_UNRESOLVED_AT_MODEL_TIER`
- `LOCAL_LADDER_EXHAUSTED`
- `CAMPAIGN_SUSPENDED_INFRASTRUCTURE`
- `CAMPAIGN_COMPLETE_BY_BUDGET`

A failed attempt is valuable evidence and never rewritten as success because a stronger model later resolves the task.

Example:

```text
1–2B: FAIL
Qwen 9B: FAIL
Devstral 24B: FAIL
Codex: PASS

Task eventual disposition: RESOLVED_BY_FRONTIER
Local ladder disposition: UNRESOLVED
All local failures remain intact evidence.
```

## Freeze/checkpoint requirements

### FREEZE A — micro-model handoff to Qwen

Preserve at minimum:

- original task and contract;
- original workspace hash and current workspace snapshot;
- every intermediate artifact and important diff;
- model identity/configuration/seed/context limits;
- exact prompt/context construction;
- raw exposed reasoning/thought where available;
- normalized reasoning state;
- hypotheses, counterhypotheses, assumptions, contradictions;
- memory/skill/tool state;
- commands, reads, writes, tool outputs, errors;
- expected versus actual consequences;
- verification obligations and coverage;
- stale verification;
- failure signature and loop signature;
- first causal/detectable/recognized failure times;
- resource telemetry;
- complete raw event stream;
- hashes for checkpoint contents.

### FREEZE B

FREEZE A plus the complete Qwen continuation and retry history.

### FREEZE C

FREEZE B plus the complete Devstral continuation and retry history, suitable for Claude/Codex continuation or later deterministic/local replay.

## Continuation versus fresh controls

Continuation can help or poison the next model. Therefore selected escalations must fork into controlled comparison:

```text
QWEN_CONTINUATION  <- failed 1–2B checkpoint
QWEN_FRESH         <- original untouched task/workspace
```

Likewise selected Devstral and frontier-resolution cases may compare continuation, fresh start, and distilled-negative-evidence-only conditions.

These controls estimate:

- intrinsic stronger-model capability;
- useful groundwork from the weaker model;
- useful negative evidence;
- inherited-state poisoning;
- handoff benefit/damage;
- system benefit versus model benefit.

Fresh controls are sampled where they have high information value rather than mechanically doubling every run.

## Adaptive frontier behavior

Each independently verified success generates a harder descendant. The local campaign is intentionally unfinishable by capability alone.

A child challenge must record:

- parent task ID;
- capability/failure dimension being increased;
- exact transformation;
- why the descendant is harder;
- what previously demonstrated capability is being preserved;
- what new boundary is being probed.

The scheduler may produce deeper, perturbed, compound, cross-domain, recovery, order-sensitive, or edge-case descendants.

## Model-threshold evidence

The ladder is not only a cost optimization. It must classify mechanism/model interactions such as:

- `MICRO_COMPATIBLE`
- `MICRO_SELF_REPAIRABLE`
- `QWEN_THRESHOLD`
- `DEVSTRAL_THRESHOLD`
- `MODEL_INDEPENDENT`
- `WEAK_MODEL_COMPENSATOR`
- `STRONG_MODEL_ONLY`
- `NEGATIVE_TRANSFER_AT_HIGH_CAPABILITY`
- `SYSTEM_LIMIT`
- `MODEL_LIMIT`
- `TOOL_LIMIT`
- `CONTEXT_LIMIT`
- `VERIFICATION_LIMIT`
- `REPRESENTATION_LIMIT`
- `PSYCHOLOGICAL_SET`

Do not conclude a system mechanism is useless merely because a 1–2B substrate is below the minimum capability needed to exploit it.

## Local-system comparison

The same Universal Harvest template must support the open/general systems selected for Harvest Fest, including at minimum the current pool:

- Pi;
- Prime Agent;
- oh-my-cli;
- SWE-agent;
- mini-SWE-agent;
- Aider;
- AegisEvo;
- OpenHands;
- Goose;
- other compatible open systems admitted under the source-catalog rules.

Claude and Codex are not forced onto the local substrate; they serve separate native/frontier roles defined in the Frontier/Cloud specification.

System-native advantages must not be flattened away. Skills, context management, extensions, hooks, recovery policies, sandboxing, memory, verification, and other native mechanisms remain enabled in the native-system arm unless the experiment is explicitly an ablation.

## Specialized/non-general components

The same chassis must support targeted testing of:

- Book-to-Skill / knowledge-to-skill compilation;
- Taste Skill / portable skill architecture;
- Comet MCP / specialist browser hand;
- media inference worker / asynchronous hand pattern;
- memory systems;
- context management;
- verifiers;
- routers;
- skills;
- tools/hands;
- recovery policies;
- validated book-derived hypotheses;
- later distributed/training mechanisms when separately admitted.

Specialized components are not forced into a misleading full-agent leaderboard. They are evaluated for the mechanism they contribute.

## Compute-aware scheduler

The template must support arbitrary worker fan-out rather than hardcoding two-way or eleven-way execution.

Typical local execution:

```text
CPU-resident 1–2B workers -> cheap primary queue
GPU-resident Qwen 9B      -> escalation queue
CPU verifier/analysis      -> independent evidence/verification
Devstral 24B               -> end-of-sweep unresolved tail
Claude/Codex               -> remote frontier resolution queue
```

When multiple harnesses share a GPU, record queue time separately from inference/tool/system time so resource contention does not masquerade as system latency.

## Local forensic evidence standard

Local runs use the full Universal Forensic Recorder. The desired operating posture is high-volume forensic collection (the previously described "7/10" level), not summary-only logging.

Especially preserve:

- raw and translated reasoning/thought when exposed;
- exact retry deltas;
- memory effects;
- system interventions;
- tool/skill/hand utilization;
- first meaningful divergence;
- failure propagation and recovery;
- verification coverage;
- complete checkpoint lineage;
- positive and negative transfer;
- timing/resource telemetry;
- raw malformed/failed/looping trajectories.

## Retry autopsy

Every wrong-answer retry is a first-class experiment. Compare attempt 1 and attempt 2:

- belief/representation before failure;
- evidence available;
- verifier feedback added;
- state retained/discarded;
- changed hypothesis;
- changed action/tool/search behavior;
- reused bad behavior;
- ignored failure evidence;
- repair type;
- result.

This distinguishes in-episode repair/learning from simple second-sample luck.

## Frontier Resolution interface

When the local ladder exhausts:

```text
FREEZE C
  -> Claude continuation
  -> Codex continuation
  -> selected Claude fresh control
  -> selected Codex fresh control
  -> blind verifier
```

Claude/Codex resolution never erases local failure. Their trajectories become teacher/reference evidence and candidate mechanism sources.

## Non-abort guarantee

"The tests cannot fail or stop" is implemented as **persistent continuation**, not falsified outcomes or infinite retries.

The controller must:

- checkpoint before any suspension;
- resume completed/unresolved work without repeating valid evidence;
- move unresolved tasks to the next permitted tier;
- continue other independent tasks while one case waits;
- preserve infrastructure failures separately from cognitive failures;
- never discard a task because its current model cannot solve it.

If all available tiers fail, the case remains a resumable unresolved frontier specimen rather than terminating the campaign.

## Implementation gate

Do not build or modify the Local Continuation Harvest template until the operator explicitly approves this frozen specification and the shared Universal Harvest contract.
