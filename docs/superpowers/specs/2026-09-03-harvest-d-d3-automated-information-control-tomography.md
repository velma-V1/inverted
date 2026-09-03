# Harvest D D3 — Automated Causal Information + Control Tomography

## Status

APPROVED ARCHITECTURAL REVISION FOR FINAL REVIEW.

This document defines the revised D3 stage of Harvest D on branch `implementation/harvest-d-identifiability-model-substitution`.

D3 retains its original architecture-substitution mission and combines it with causal information-delivery tomography, broad deterministic-assistance tomography, explicit failure/recovery tomography, and event-sourced whole-system observability.

D3 is automated as far as sensibly possible, may consume up to 600 admissible physical model calls, and must stop early whenever remaining uncertainty no longer justifies additional calls. The 600-call value is an absolute ceiling, not a quota.

## 1. Primary D3 question

D3 must answer:

> What information, delivered in what form, at what time, to which component, combined with what deterministic assistance and recovery support, allows the smallest model to produce the highest verified correctness with the least model dependence?

D3 separates eight causal questions:

1. WHAT information changes outcomes.
2. HOW that information should be represented.
3. WHERE it should live: model-visible, system-only, or both.
4. WHEN it should arrive: upfront, progressive, immediately before decision, or just-in-time.
5. HOW MUCH information is minimally sufficient.
6. WHAT deterministic assistance changes outcomes independently of information quality.
7. HOW failure detection and recovery choices change the trajectory.
8. WHO benefits: 1.5B, transition models, Qwen9B, and later the CPU sentinel.

## 2. D2 evidence motivating D3

D2 established that a simple model-size ladder is insufficient to explain the remaining failure surface.

Observed development results included:

- SMALL_A 1.5B: 2/18 semantic successes.
- Qwen3.5 9B: 10/18 semantic successes.
- Ministral 3B recovered 5/8 cases that SMALL_A failed and Qwen9B solved.
- Phi 3.8B recovered 2/3 remaining 3B-to-9B residual cases.
- Qwen3 8B solved the final F7 residual case.
- Qwen3 14B recovered only 1/8 cases that Qwen9B failed.
- On five persistent 14B failures, the semantic answer was correct while the disposition was wrong.

A zero-call disposition-compiler screen then showed:

- SMALL_A residual bank: RAW 0/8, TARGET 4/8, SHAM 1/8.
- Qwen9B residual bank: RAW 0/8, TARGET 1/8, SHAM 0/8.
- Qwen14B residual bank: RAW 1/8, TARGET 6/8, SHAM 1/8.

This justifies testing information delivery, deterministic assistance, and recovery control as separable and interacting mechanisms.

## 3. Architecture under test

Conceptual flow:

```text
                    INFORMATION
                         |
              +----------+----------+
              |                     |
        MODEL-VISIBLE          SYSTEM-ONLY
              |                     |
              v                     v
       1.5B / 3B / 9B       deterministic INVERTED
              |              state / evidence /
              |              authority / invariants /
              |              admissible actions /
              |              recovery constraints
              v                     |
      semantic proposal             |
              +----------+----------+
                         v
             ASSISTANCE / CONTROL
      state scaffold / evidence / verifier /
      compiler / recovery / authority guard
                         |
                TARGET / SHAM / OFF
                         |
                         v
                VERIFIED OUTCOME
```

The four central physical-model conditions remain:

1. RAW.
2. INFORMATION only.
3. ASSISTANCE only.
4. INFORMATION + ASSISTANCE.

Where causally valid, deterministic OFF/TARGET/SHAM replays use the exact same physical model response and consume no additional model calls.

## 4. Information tomography

### 4.1 Information content classes

Initial candidate classes are:

- I1: original objective and current subgoal.
- I2: canonical state and state version.
- I3: allowed scope and current authority.
- I4: available evidence and explicitly missing evidence.
- I5: consequence and reversibility.
- I6: global invariants and required postcondition.
- I7: currently admissible actions.
- I8: dependency and ordering structure.
- I9: previous verified outcome and current recovery state.
- I10: uncertainty, novelty, and unresolved alternatives.

No candidate survives by design intuition alone.

### 4.2 Information quality variants

D3 must represent, where applicable:

- correct and complete;
- correct but incomplete;
- missing;
- stale;
- contradictory;
- noisy;
- irrelevant;
- redundant;
- misleading but non-authoritative;
- internally consistent but insufficient.

### 4.3 Information source and trust

Information provenance must be explicit:

- system-owned canonical state;
- deterministic tool-derived evidence;
- model-derived claim;
- external/untrusted metadata;
- mixed-trust packet.

The model-visible packet and the system-known packet must be separately recorded so information leakage and system/model responsibility can be distinguished.

### 4.4 Information amount

Test:

- minimum candidate packet;
- compressed packet;
- moderate packet;
- full packet;
- overloaded/full-history context.

### 4.5 Representation

For semantically equivalent information, test only representations that can materially change usability:

- raw prose;
- compact typed fields;
- strict JSON/schema;
- decision table;
- priority-ordered block;
- explicit alternatives;
- decomposition into subproblems;
- minimal ledger plus current state;
- compressed summary;
- admissible-action matrix.

### 4.6 Ordering

Where order is meaningful, compare:

- safety/state/evidence first;
- task/objective first;
- state first;
- evidence first;
- shuffled order control.

### 4.7 Placement and timing

Test:

- system context;
- task context;
- structured state packet;
- tool/evidence result;
- immediately before decision;
- all-upfront;
- progressive reveal;
- ACQUIRE_EVIDENCE / just-in-time delivery.

The experiment must distinguish information gain from representation gain, ordering gain, placement gain, timing gain, token-volume effects, and checkpoint/deliberation effects.

## 5. Deterministic-assistance tomography

ASSISTANCE is not a single mechanism. D3 must test the following classes independently where applicable:

- A1: canonical-state scaffold / version anchoring;
- A2: admissible-action restriction;
- A3: evidence requirement / missing-evidence support;
- A4: decomposition / dependency scaffold;
- A5: deterministic verifier / postcondition check;
- A6: disposition compiler;
- A7: authority / least-privilege guard;
- A8: consequence / reversibility guard;
- A9: recovery supervisor;
- A10: failure signature / guard;
- A11: routing/escalation support where decision-time observables justify it.

Each mechanism must have TARGET, OFF, and matched SHAM/negative control where possible.

No mechanism may use hidden case IDs, oracle labels, sealed annotations, expected-answer lookup tables, or future outcome information.

## 6. Disposition compiler

The disposition compiler remains a first-class D3 intervention but is only one assistance mechanism.

It may derive control decisions only from system-owned semantics such as:

- missing required evidence -> ACQUIRE_EVIDENCE;
- unknown irreversible external effect -> reconcile / escalate, never blind retry;
- global invariant violation -> SAFE_STOP;
- valid retryable no-effect failure -> authorized recovery path;
- insufficient causal discrimination -> ACQUIRE_EVIDENCE or ESCALATE;
- committed external effect with missing local update -> reconcile local state without replay.

Its exact inputs and output reason codes must be recorded.

## 7. Failure and recovery tomography

D3 must test not only whether failure occurs, but how it is detected, diagnosed, contained, and recovered.

### 7.1 Failure families

Use the existing Harvest D fault layers and case families, including:

- state;
- evidence;
- context;
- topology/dependency;
- authority;
- transaction;
- verifier/oracle-model mismatch;
- recovery;
- routing;
- global interaction/invariant;
- novelty/uncertainty.

### 7.2 Recovery choices

Where admissible, distinguish:

- retry;
- alternate action;
- reconcile;
- rollback;
- compensate;
- replan;
- decompose;
- acquire evidence;
- reroute/escalate;
- safe stop.

### 7.3 Recovery-failure variants

Test failures of the recovery path itself, including:

- failed retry;
- repeated retry when retry is unsafe;
- partial compensation;
- failed compensation;
- stale canonical state after recovery;
- consumed or resurrected authority;
- unknown external effect;
- duplicate-effect risk;
- recovery that introduces a new failure;
- recovery that fixes the local symptom but violates a global invariant;
- recovery that migrates failure into another subsystem.

### 7.4 Recovery trajectory record

Every applicable recovery case must preserve:

```text
first meaningful divergence
 -> first detection
 -> diagnosis
 -> available recovery choices
 -> chosen recovery
 -> system admission/rejection
 -> recovery execution
 -> resulting canonical state
 -> verification/postcondition
 -> recovered / migrated / worsened / escalated / safe-stopped
```

Unknown external effect always requires reconciliation before any retry that could duplicate an irreversible effect.

## 8. Compound and interaction testing

D3 must not attempt the full Cartesian product of all variants. Instead it uses adaptive, information-gain-driven testing.

Mandatory interaction classes are:

- information content x representation;
- information quality x trust/source;
- information x assistance;
- information x recovery;
- assistance x recovery;
- model size x information packet;
- model size x assistance;
- compound information + assistance + recovery failures where prior evidence predicts interaction.

Only interactions with causal plausibility or observed evidence receive additional calls.

## 9. Automation requirement

D3 operates as one resumable campaign rather than a sequence of manually launched experiments.

Target operator flow:

```text
run-harvest-d-d3.ps1
        |
        v
preflight
        |
        v
adaptive experiment scheduling
        |
        v
physical model call
        |
        v
atomic event/journal commit
        |
        v
scoring + OFF/TARGET/SHAM replay
        |
        v
failure/recovery classification
        |
        v
causal analysis
        |
        v
continue / stop / promote / reject / allocate more evidence
        |
        v
sealed confirmation
        |
        v
final evidence package
```

Normal model failures become evidence and must not stop the campaign.

## 10. Automated controller responsibilities

### 10.1 Preflight

Before the first admissible call, verify and record:

- repository commit and branch;
- case-bank hashes;
- system-prompt and information-packet hashes;
- Ollama endpoint availability;
- exact model IDs and digests where available;
- runtime version;
- generation options and context configuration;
- measurement version;
- call budget and prior journal state;
- physical-call identity registry;
- holdout/sealed-bank integrity;
- obvious oracle leakage checks;
- output-directory integrity and write permissions.

Preflight failure spends zero calls.

### 10.2 Adaptive scheduling

The scheduler allocates calls toward the highest-value unresolved causal question.

Normative priority:

1. hard safety/invariant uncertainty;
2. semantic correctness uncertainty;
3. silent wrong action;
4. failure/recovery correctness;
5. information x assistance interaction;
6. model-size substitution;
7. information marginal value;
8. assistance marginal value;
9. minimum sufficient support;
10. efficiency and cost.

A clearly harmful or futile mechanism stops receiving calls except for a preregistered contradiction check.

### 10.3 Sequential decisions

After preregistered evidence blocks, classify comparisons as:

- SUPERIOR;
- NONINFERIOR;
- HARMFUL;
- FUTILE;
- UNRESOLVED.

Use sequentially valid inference. Naive repeated fixed-horizon confidence checks are not admissible.

### 10.4 Failure mining

Automatically classify at minimum:

- format-only;
- schema-only;
- answer wrong / disposition correct;
- answer correct / disposition wrong;
- both wrong;
- state/evidence/authority/topology/transaction/recovery/invariant/routing/novelty failure;
- context/representation failure;
- suspected instrumentation/oracle issue;
- failure migration after attempted recovery.

These classifications may select the next preregistered experiment but may never alter hidden truth.

### 10.5 Minimum-support searches

Perform adaptive ablation on both information and assistance:

- Minimum Sufficient Information Packet (MSIP).
- Minimum Required Scaffolding (MRS).

Remove one supported field/mechanism at a time, preserve it only if removal causes a reproducible degradation or hard-invariant loss.

## 11. Whole-system event-sourced observability

D3 must record enough externally observable state to reconstruct every causal trajectory without hidden chain-of-thought.

### 11.1 Event record

Every meaningful system event receives at minimum:

- run_id;
- experiment_id;
- case_id;
- arm_id;
- event_id;
- parent_event_id / causal predecessor;
- monotonic sequence number;
- timestamp;
- component;
- event_type;
- pre-state hash/version;
- post-state hash/version where applicable;
- model-visible information hash;
- system-known information hash;
- authority/scope snapshot hash;
- evidence-set hash;
- proposed action/disposition;
- admitted/rejected action and reason;
- recovery decision and reason where applicable;
- verifier result;
- effect status;
- physical_model_call_id where applicable;
- tokens/latency/runtime provenance where applicable;
- hard-invariant status;
- semantic-oracle result when revealed for scoring;
- artifact/checksum references.

### 11.2 Required reconstructable views

The final evidence must allow reconstruction of:

```text
WHAT THE MODEL SAW
WHAT THE SYSTEM KNEW
WHAT THE MODEL PROPOSED
WHAT THE SYSTEM ALLOWED
WHAT EXECUTED / WAS SIMULATED
WHAT STATE CHANGED
WHAT FAILED
WHAT DETECTED IT
WHAT RECOVERY WAS AVAILABLE
WHAT RECOVERY WAS CHOSEN
WHAT THE VERIFIED OUTCOME WAS
```

### 11.3 No hidden reasoning requirement

Do not require or store private chain-of-thought. Observable prompts, responses, structured outputs, reason codes, candidate actions when explicitly emitted, deterministic decisions, state transitions, and verification evidence are sufficient.

### 11.4 Event integrity

Events are append-only within a run. Corrections create new events; they do not silently overwrite prior evidence. Event IDs and physical model call IDs must be globally unique within the campaign.

## 12. Crash / resume semantics

Every physical call and every committed system transition must be journaled atomically enough to prevent accidental replay or double counting.

After interruption:

1. reload the journal/event log;
2. verify hashes, call identities, and last committed state;
3. verify runtime/model provenance still matches;
4. resume at the first uncommitted scheduled action;
5. never silently rerun a committed physical call;
6. never repeat an irreversible or simulated-irreversible action solely because the controller restarted.

A provenance change requires evidence segmentation or campaign halt according to preregistered rules.

## 13. Call budget

D3 has an adaptive hard ceiling of 600 admissible physical model calls.

Revised envelope:

| Phase | Purpose | Maximum calls |
|---|---|---:|
| D3.0 | D2 closure + zero-call compiler screen | 0 |
| D3.1 | fresh baseline / failure bank | 48 |
| D3.2 | information content + quality + source | 88 |
| D3.3 | representation + order + amount + timing | 64 |
| D3.4 | assistance-mechanism tomography | 80 |
| D3.5 | failure/recovery tomography | 72 |
| D3.6 | information x assistance combined substitution | 96 |
| D3.7 | negative transfer + compound failures | 56 |
| D3.8 | sealed confirmation | 96 |
| **Absolute maximum** | | **600** |

These are ceilings, not quotas. Calls may move among unsealed discovery phases when the scheduler records why expected information gain is higher elsewhere. Sealed-confirmation capacity may not be consumed for development tuning.

The campaign may terminate materially below 600 calls.

## 14. Four-condition causal test

The central combined comparison remains:

```text
RAW
INFORMATION only
ASSISTANCE only
INFORMATION + ASSISTANCE
```

The combined phase receives up to 96 calls, with sequential reallocation toward unresolved high-value comparisons.

Where deterministic assistance can replay the exact same physical response, OFF/TARGET/SHAM comparisons do not consume extra calls.

The highest-value claim is whether SMALL_A + minimum information + minimum required deterministic assistance can match or exceed Qwen9B RAW while preserving hard invariants.

## 15. Primary model roles

### SMALL_A

`qwen2.5:1.5b-instruct-q8_0`

Primary model for discovering model-capacity substitution.

### QWEN

`qwen3.5:9b-q8_0`

Primary strong local comparison anchor.

### Transition controls

3B/3.8B/8B models are used only where they materially localize a transition.

### Stronger residual ceiling

14B/24B models are used only to distinguish model-capacity limits from architecture/information/verifier/task-specification limits. They are not production dependencies.

## 16. Negative-transfer and adversarial information tests

Promising information/assistance configurations must be attacked using:

- token-matched irrelevant information;
- stale-but-plausible state;
- internally conflicting evidence;
- untrusted metadata;
- redundant history;
- full-history/context overload;
- unnecessary decomposition;
- superficially plausible but wrong recovery suggestion;
- misleading routing hint;
- correct information in a deliberately poor representation.

Measure distraction, stale-state susceptibility, context poisoning, structural erosion, unnecessary escalation, silent wrong actions, bad recovery, and failure migration.

## 17. Hard-stop conditions requiring operator review

Halt on:

- unauthorized irreversible action or equivalent simulated hard-invariant violation;
- duplicate irreversible effect;
- resurrected authority;
- oracle leakage;
- ambiguous/duplicated physical model call identity;
- holdout tuning or sealed-case contamination;
- corrupted journal/event log/evidence artifact;
- provenance mismatch that invalidates comparability;
- promoted rule bypassing authority;
- all preregistered experiment moves exhausted while a high-value causal question remains unresolved.

Ordinary model failure, low score, malformed output, failed recovery, and mechanism failure are evidence and do not require manual intervention by themselves.

## 18. Automation may not change experimental truth

The controller may select among preregistered experiment moves but may not autonomously:

- rewrite hidden oracles;
- alter success criteria;
- change sealed confirmation cases;
- synthesize favorable replacements for failed holdouts;
- expand authority;
- retry failed model calls until success;
- promote from development evidence alone;
- treat model explanation as truth;
- rewrite prior events;
- add a new mechanism family solely because the current one lost.

A genuinely new mechanism implied by results becomes a new hypothesis under existing Harvest D causal-promotion rules.

## 19. CPU sentinel relationship

The approved CPU Sentinel remains part of Harvest D and is not replaced.

D3 determines which information fields and representations are worth testing in the sentinel input contract. The sentinel still requires separate S0/S1/S2 + sham causal validation and verified CPU residency before any promotion claim.

## 20. Promotion gates

A D3 mechanism, information packet, assistance mechanism, or recovery policy is promotable only if:

1. TARGET materially exceeds RAW where superiority is required;
2. TARGET materially exceeds SHAM;
3. hard invariants remain clean;
4. no unacceptable semantic regression occurs;
5. neighboring generalization succeeds;
6. fresh-family generalization succeeds where applicable;
7. negative-transfer controls are acceptable;
8. MSIP/MRS ablation identifies required support;
9. recovery does not merely migrate failure;
10. sealed confirmation succeeds;
11. provenance, event integrity, and call identity remain admissible.

Mechanism states remain REQUIRED, CONDITIONAL, REDUNDANT, HARMFUL, or UNRESOLVED.

## 21. Required D3 outputs

The automated final package must include at minimum:

- `information_value_map.json`;
- `information_quality_map.json`;
- `delivery_map.json`;
- `information_location_map.json`;
- `minimum_sufficient_information_packet.json`;
- `assistance_value_map.json`;
- `minimum_required_scaffolding.json`;
- `disposition_compiler_evidence.json`;
- `recovery_policy_map.json`;
- `recovery_failure_map.json`;
- `information_assistance_interaction.json`;
- `model_substitution_frontier.json`;
- `negative_transfer_map.json`;
- `failure_migration_map.json`;
- `sequential_decisions.jsonl`;
- `d3_system_events.jsonl`;
- `d3_campaign_journal.jsonl`;
- `d3_call_ledger.jsonl`;
- `d3_resume_state.json`;
- `d3_provenance.json`;
- `d3_final_report.md`;
- `d4_handoff.json`.

The final dataset must support retrospective queries that were not hard-coded into the original report, including:

- cases where semantic answer was correct but disposition/action was wrong;
- which information class most reduced each failure family;
- which representation improved or harmed each model size;
- which component first detected each failure;
- which recovery choices fixed, migrated, or worsened failures;
- minimum state/evidence/authority support required for safe retry/recovery;
- whether information or deterministic assistance substituted for model size.

## 22. Primary success criterion

D3 does not succeed merely by increasing benchmark accuracy.

D3 succeeds if it causally identifies whether and how:

> better information improves cognition, deterministic assistance converts cognition into correct system behavior, recovery control prevents or repairs failures without migration, and the combination allows a smaller local model to match or exceed a larger raw model while preserving hard invariants and reducing model dependence.

The whole system must be reconstructable from recorded observable evidence well enough to determine not only whether an outcome changed, but what information, system intervention, decision, state transition, and recovery event caused the change.
