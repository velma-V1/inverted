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
- The retry records precisely what feedback was added and what state changed between attempts.
- A hard runtime/model failure, unsupported operation, verified stuck state, repeated loop, exhausted context/tool/output budget, or infrastructure condition may bypass the retry when retrying would add no valid information.
- No repeated uncontrolled external retries.

## Failure semantics

Maintain distinct states:

- `ATTEMPT_FAILED`
- `TASK_UNRESOLVED_AT_MODEL_TIER`
- `LOCAL_LADDER_EXHAUSTED`
- `CAMPAIGN_SUSPENDED_INFRASTRUCTURE`
- `CAMPAIGN_COMPLETE_BY_BUDGET`

A failed attempt is valuable evidence and is never rewritten as success because a stronger model later resolves the task.

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

## Mandatory local Systems Harvest Lab

Every compatible open system in the local comparison pool must run through the shared pinned/isolated Harvest Lab defined by the Universal contract.

For each system arm:

- create an isolated writable workspace clone from the same frozen task specimen;
- pin system repository/version/dependencies;
- record container/image digest;
- deny cross-arm workspace access;
- route all filesystem/process/tool observations through the common observer when technically possible;
- use the same blind verifier contract;
- normalize all events into the Universal Forensic Event schema while preserving raw native logs;
- record any system that cannot validly run in Docker as an explicit exception with an equivalent reproducible sandbox.

System-native features remain enabled in native-system arms unless intentionally ablated.

## Freeze/checkpoint requirements

### FREEZE A — micro-model handoff to Qwen

Preserve at minimum:

- original task and contract;
- original workspace hash and current workspace snapshot;
- every intermediate artifact and important diff;
- model identity/configuration/seed/context limits;
- exact prompt/context construction and stage hashes;
- full model-visible state where observable;
- raw exposed reasoning/thought where available;
- normalized reasoning state and provenance;
- hypotheses, counterhypotheses, assumptions, contradictions;
- memory/skill/tool/hand state and skill lifecycle;
- commands, reads, writes, tool outputs, errors;
- every system intervention (`BLOCK`, `REWRITE`, `RETRY`, `ROUTE`, `SUMMARIZE`, `COMPACT`, `INJECT`, `ESCALATE`, `MUTATION_GATE`, `PERMISSION_CHANGE`, `ROLLBACK`, `CHECKPOINT`, `RESUME`);
- expected versus actual consequences;
- verification obligations and coverage;
- stale verification;
- failure signature and loop signature;
- reasoning-instability/oscillation record where measurable;
- first causal/detectable/recognized failure times;
- queue/inference/tool/verification/wall time;
- local-model telemetry supported by the runtime;
- complete raw event stream;
- hashes for checkpoint contents.

### FREEZE B

FREEZE A plus the complete Qwen continuation and retry history.

### FREEZE C

FREEZE B plus the complete Devstral continuation and retry history, suitable for Claude/Codex continuation or later deterministic/local replay.

## Continuation versus fresh controls

Continuation can help or poison the next model. Therefore selected escalations fork into controlled comparison:

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

## Passive and instrumented local reasoning modes

The Universal `NATIVE_PASSIVE` versus `INSTRUMENTED_REASONING` separation applies to all local models and systems.

- Native/passive evidence is the default system-comparison evidence.
- Instrumented reasoning may explicitly request hypothesis/evidence/uncertainty/expected-result state reports.
- Instrumented results are never merged into native results.
- If externalizing reasoning improves performance, that improvement becomes a candidate mechanism rather than being hidden as instrumentation noise.

## Adaptive frontier behavior

Each independently verified success generates a harder descendant. The local campaign is intentionally unfinishable by capability alone.

A child challenge records:

- parent task ID;
- capability/failure dimension being increased;
- exact transformation;
- why the descendant is harder;
- what previously demonstrated capability is being preserved;
- what new boundary is being probed.

The scheduler may produce deeper, perturbed, compound, cross-domain, recovery, order-sensitive, or edge-case descendants.

## Model-threshold evidence

The ladder is not only a cost optimization. It classifies mechanism/model interactions such as:

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

## Local-system comparison pool

The same Universal Harvest template supports the open/general systems selected for Harvest Fest, including at minimum:

- Pi;
- Prime Agent;
- oh-my-cli;
- SWE-agent;
- mini-SWE-agent;
- Aider;
- AegisEvo;
- OpenHands;
- Goose;
- other compatible open systems admitted under source-catalog rules.

Together with Claude and Codex native/reference treatment, this preserves the originally selected eleven general systems without pretending all eleven share the same model substrate.

Claude and Codex are not forced onto the local substrate; they serve separate native/frontier roles defined in the Frontier/Cloud specification. ChatGPT is a separate high-value native/reference specimen.

## Specialized/non-general components

The same chassis supports targeted testing of:

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

## Compute-aware concurrent scheduler

The template supports arbitrary worker fan-out rather than hardcoding two-way or eleven-way execution.

Typical execution:

```text
CPU-resident 1–2B workers -> cheap primary queue
GPU-resident Qwen 9B      -> escalation queue
CPU verifier/analysis      -> independent evidence/verification
Devstral 24B               -> end-of-sweep unresolved tail
Claude/Codex               -> remote frontier resolution/native queues
cloud GPU replicas         -> optional parallel local-system arms
```

The scheduler may run Claude, Codex, local workers, verifiers, and independent system arms concurrently when resources permit. Queue time, batching, resource contention, and worker assignment are recorded separately from model/system execution time.

## Local forensic evidence standard

Local runs use the full Universal Forensic Recorder and canonical event schema. The desired posture is high-volume forensic collection (the previously described **7/10** level), never summary-only logging.

Especially preserve:

- raw and translated reasoning/thought when exposed;
- exact retry deltas;
- memory effects;
- prompt/context stage hashes;
- system interventions;
- tool/skill/hand utilization and full skill lifecycle;
- first meaningful divergence;
- failure propagation/recovery;
- verification coverage;
- complete checkpoint lineage;
- positive/negative transfer;
- reasoning instability/oscillation;
- queue/inference/tool/verification/wall timing;
- token/logprob/top-k/entropy/stop/context/KV/repetition telemetry when supported;
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
