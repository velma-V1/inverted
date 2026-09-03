# Harvest D D3 — Automated Causal Information + Control Tomography

## Status

APPROVED ARCHITECTURAL DESIGN FOR REVIEW.

This document defines the revised D3 stage of Harvest D on branch `implementation/harvest-d-identifiability-model-substitution`.

D3 retains its original architecture-substitution mission and adds a causal information-delivery discovery layer. The stage is automated as far as sensibly possible, may consume up to 600 admissible physical model calls, and must stop early whenever the remaining uncertainty no longer justifies additional calls.

The 600-call value is an absolute ceiling, not a target.

## 1. Primary D3 question

D3 must answer:

> What information, delivered in what form, at what time, to which component, allows the smallest model plus deterministic INVERTED assistance to produce the highest verified correctness with the least model dependence?

D3 therefore separates six experimental axes:

1. WHAT information changes outcomes.
2. HOW that information should be represented.
3. WHERE it should live: model-visible, system-only, or both.
4. WHEN it should arrive: upfront, immediately before decision, or just-in-time through evidence acquisition.
5. HOW MUCH information is minimally sufficient.
6. WHO benefits: 1.5B, 3B transition models, 9B Qwen, and later the CPU sentinel.

## 2. D2 evidence motivating D3

D2 established that a simple model-size ladder is insufficient to explain the remaining failure surface.

Observed development results included:

- SMALL_A 1.5B: 2/18 semantic successes.
- Qwen3.5 9B: 10/18 semantic successes.
- Ministral 3B recovered 5/8 cases that SMALL_A failed and Qwen9B solved.
- Phi 3.8B recovered 2/3 remaining 3B-to-9B residual cases.
- Qwen3 8B solved the final F7 residual case.
- Qwen3 14B recovered only 1/8 cases that Qwen9B failed.
- On five persistent 14B failures, the answer was correct while the disposition was wrong.

A zero-call disposition-compiler screen then showed:

- SMALL_A residual bank: RAW 0/8, TARGET 4/8, SHAM 1/8.
- Qwen9B residual bank: RAW 0/8, TARGET 1/8, SHAM 0/8.
- Qwen14B residual bank: RAW 1/8, TARGET 6/8, SHAM 1/8.

This justifies testing both information delivery and deterministic post-model assistance as independent and interacting mechanisms.

## 3. D3 architecture under test

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
              |              authority / invariants
              v                     |
      semantic proposal             |
              +----------+----------+
                         v
              DISPOSITION COMPILER
                         |
              TARGET / SHAM / OFF
                         |
                         v
                VERIFIED OUTCOME
```

The primary physical-model conditions are:

1. RAW model.
2. INFORMATION only.
3. ASSISTANCE/compiler only.
4. INFORMATION + ASSISTANCE.

Where possible, OFF/TARGET/SHAM compiler comparisons are replayed against the same physical model response and therefore do not consume additional model calls.

## 4. Information candidates

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

No candidate survives by design intuition alone. Each must earn value through causal comparison.

## 5. Delivery representations

For information that shows value, D3 compares semantically equivalent delivery forms:

- raw prose;
- compact typed fields;
- decision table;
- priority-ordered block;
- explicit alternatives;
- decomposition into subproblems;
- minimal ledger plus current state;
- compressed summary;
- admissible-action matrix;
- just-in-time delivery through evidence acquisition.

Matched controls include:

- token-matched irrelevant context;
- similarly sized stale information;
- shuffled ordering;
- redundant context;
- arbitrary decomposition;
- irrelevant structured fields.

The experiment must distinguish information gain from representation gain, ordering gain, timing gain, and extra-token/checkpoint effects.

## 6. Disposition compiler

The disposition compiler remains a first-class D3 intervention.

It may derive control decisions only from system-owned semantics such as:

- missing required evidence -> ACQUIRE_EVIDENCE;
- unknown irreversible effect -> reconcile / escalate, never blind retry;
- global invariant violation -> SAFE_STOP;
- valid retryable no-effect failure -> authorized retry path;
- insufficient causal discrimination -> ACQUIRE_EVIDENCE or ESCALATE;
- valid committed external effect with missing local update -> reconcile local state without replay.

It must never use:

- case IDs;
- hidden oracle labels;
- expected answer tokens as lookup keys;
- sealed holdout annotations;
- future outcome information.

The compiler must be independently testable and its inputs must be recorded.

## 7. Automation requirement

D3 must operate as one resumable campaign rather than a sequence of manually launched experiments.

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
artifact commit + scoring
        |
        v
zero-call OFF/TARGET/SHAM replay
        |
        v
causal analysis
        |
        v
continue / stop / promote / reject / escalate experiment
        |
        v
sealed confirmation
        |
        v
final evidence package
```

Normal model failures become evidence and must not stop the campaign.

## 8. Automated controller responsibilities

### 8.1 Preflight

Before the first admissible call, automatically verify and record:

- repository commit and branch;
- case-bank hashes;
- system-prompt hashes;
- Ollama endpoint availability;
- exact model IDs and digests where available;
- runtime version;
- generation options;
- context configuration;
- measurement version;
- call budget and prior journal state;
- unique physical call identity registry;
- no obvious oracle leakage;
- required output directories and write permissions.

Preflight failure spends zero model calls.

### 8.2 Experiment matrix generation

The controller generates only preregistered experiment families and arms, including:

- RAW;
- INFORMATION;
- ASSISTANCE;
- INFORMATION + ASSISTANCE;
- OFF/TARGET/SHAM replay;
- relevant model-size controls;
- information representation, ordering, timing, and ablation variants.

### 8.3 Adaptive scheduling

The scheduler must allocate calls toward the highest-value unresolved causal questions rather than executing a fixed full factorial sweep.

Normative priority:

1. hard safety/invariant uncertainty;
2. semantic correctness uncertainty;
3. silent-wrong-action reduction;
4. model-size substitution;
5. information marginal value;
6. assistance marginal value;
7. information x assistance interaction;
8. minimum sufficient support;
9. efficiency and cost.

A mechanism with strong evidence of futility or harm must stop receiving calls unless a prespecified contradiction test remains.

### 8.4 Zero-call counterfactual replay

Each eligible physical response is automatically replayed through deterministic OFF/TARGET/SHAM logic where causally valid.

The replay must preserve:

- identical model response;
- identical pre-decision state;
- identical oracle;
- identical instrumentation;
- only the intervention variable changed.

### 8.5 Sequential decision states

After each preregistered evidence block, the controller classifies the comparison as one of:

- SUPERIOR;
- NONINFERIOR;
- HARMFUL;
- FUTILE;
- UNRESOLVED.

Stopping must use sequentially valid logic. Repeated naive fixed-horizon confidence checks are not admissible.

### 8.6 Failure mining

The controller automatically classifies observed failures at minimum into:

- format-only;
- schema-only;
- answer wrong / disposition correct;
- answer correct / disposition wrong;
- both wrong;
- evidence failure;
- state failure;
- authority failure;
- topology/dependency failure;
- transaction failure;
- recovery failure;
- invariant/global-interaction failure;
- novelty/uncertainty failure;
- context/representation failure;
- suspected instrumentation/oracle issue.

These classifications drive subsequent experiments but never change hidden ground truth.

### 8.7 Minimum-information search

Once a high-performing information packet exists, the controller performs adaptive removal:

```text
best packet
  -> remove one field
       -> preserved? keep it removed
       -> degraded? restore it
```

Interactions are tested only among fields/mechanisms that already demonstrated value or where the observed failure pattern makes the interaction causally plausible.

The output is the Minimum Sufficient Information Packet (MSIP).

## 9. Call budget

D3 has an adaptive hard ceiling of 600 admissible physical model calls.

Recommended budget envelope:

| Phase | Purpose | Maximum calls |
|---|---|---:|
| D3.0 | D2 closure + existing zero-call compiler screen | 0 |
| D3.1 | fresh baseline / failure bank | 48 |
| D3.2 | WHAT information matters | 96 |
| D3.3 | HOW information is delivered | 72 |
| D3.4 | minimum sufficient information / ablation | 64 |
| D3.5 | four-condition combined substitution test | 128 |
| D3.6 | timing / JIT / ACQUIRE_EVIDENCE | 32 |
| D3.7 | negative-transfer and misleading-information attacks | 48 |
| D3.8 | sealed confirmation | 96 |
| Reserve | unresolved high-value causal ambiguity only | 16 |
| **Absolute maximum** | | **600** |

These are ceilings, not quotas. Calls may be reallocated within D3 when the adaptive scheduler documents why the expected information gain is higher elsewhere.

The campaign may terminate materially below 600 calls.

## 10. Four-condition causal test

The central combined test uses fresh cases and compares:

```text
RAW
INFORMATION only
ASSISTANCE only
INFORMATION + ASSISTANCE
```

The intended discovery/generalization target is at least 32 independent fresh observations per physical-model arm when the comparison remains informative.

A sealed confirmation bank supplies approximately 24 additional independent cases per condition where the final claim remains unresolved and valuable.

Sequential stopping may terminate a condition earlier for decisive superiority, harm, or futility, or extend selected unresolved conditions within the overall 600-call ceiling.

## 11. Primary model roles

### SMALL_A

`qwen2.5:1.5b-instruct-q8_0`

Primary model for discovering whether information and deterministic support can substitute for model capacity.

### QWEN

`qwen3.5:9b-q8_0`

Primary strong local comparison anchor.

### Transition controls

3B/3.8B/8B models are used only where they materially localize a transition discovered by SMALL_A/QWEN comparisons.

### Stronger residual ceiling

14B/24B models are used only when necessary to distinguish remaining model-capacity limits from architecture, information, verifier, or task-specification limitations.

They are not production dependencies.

## 12. Timing / JIT information experiment

For information shown to be valuable, D3 compares:

- all-upfront delivery;
- just-before-decision delivery;
- ACQUIRE_EVIDENCE / just-in-time retrieval;
- matched sham acquisition.

Each actual model invocation is counted individually.

The objective is not to maximize context. It is to minimize information burden while preserving verified outcomes.

## 13. Negative-transfer attacks

The best information/assistance configuration must be attacked using:

- token-matched irrelevant information;
- stale-but-plausible state;
- internally conflicting evidence;
- redundant history;
- full-history/context overload;
- unnecessary decomposition;
- misleading but non-authoritative metadata.

Measure:

- distraction susceptibility;
- stale-state susceptibility;
- prompt/context poisoning sensitivity;
- structural erosion;
- unnecessary escalation;
- silent wrong actions;
- negative transfer.

A mechanism that works only in clean development conditions is not promotable.

## 14. Crash / resume semantics

Every physical model call must be journaled atomically enough to prevent accidental double counting or replay.

At minimum persist:

- case ID;
- arm ID;
- experiment phase;
- model ID;
- model/runtime provenance;
- prompt hash;
- system-prompt hash;
- physical model call ID;
- raw response;
- scores;
- tokens;
- latency;
- experiment state;
- total and phase budget state;
- next scheduled action;
- artifact checksums.

After interruption:

1. reload the journal;
2. verify completed artifacts and call identities;
3. verify runtime/model provenance still matches;
4. resume at the first uncommitted action;
5. never silently rerun a committed physical call.

A provenance change requires explicit segmentation of evidence or campaign halt according to the preregistered rule.

## 15. Hard-stop conditions requiring operator review

The automated campaign must halt on:

- unauthorized irreversible action or simulated equivalent indicating a hard invariant violation;
- duplicate irreversible effect;
- resurrected authority;
- oracle leakage;
- ambiguous or duplicated physical model call identity;
- holdout tuning or sealed-case contamination;
- corrupted journal or evidence artifact;
- model/runtime/configuration provenance mismatch that invalidates comparability;
- promoted rule bypassing authority;
- all preregistered experiment options exhausted while a high-value causal question remains unresolved.

Ordinary model failures, low scores, malformed outputs, and mechanism failures do not trigger manual review; they are evidence.

## 16. Automation may not change experimental truth

The controller may select among preregistered experiment moves, but may not autonomously:

- rewrite hidden oracles after observing results;
- alter success criteria;
- change sealed confirmation cases;
- synthesize favorable replacements for failed holdout cases;
- expand model or system authority;
- retry failed model calls until success;
- promote mechanisms from development evidence alone;
- convert a model explanation into ground truth;
- add a new mechanism family solely because the current mechanism lost.

Any genuinely new mechanism implied by results must be recorded as a new hypothesis and handled under the existing Harvest D causal-promotion rules.

## 17. CPU sentinel relationship

The previously approved CPU Sentinel remains part of Harvest D and is not replaced by D3.

D3 informs its eventual input contract by determining which fields actually matter and in which representation.

The sentinel remains subject to its separate requirements:

- SMALL_A actor evidence and CPU_SENTINEL evidence are separate;
- CPU-residency claims require observed zero GPU offload;
- sentinel may detect but may not directly authorize, execute, commit, certify, or override Qwen;
- validated sentinel intervention uses matched S0/S1/S2 and sham comparisons.

The D3 MSIP may become the candidate sentinel-visible packet, but only after sentinel-specific causal validation.

## 18. Promotion gates

A D3 mechanism or information packet is promotable only if:

1. TARGET materially exceeds RAW where superiority is required;
2. TARGET materially exceeds SHAM;
3. hard invariants remain clean;
4. no unacceptable semantic regression occurs;
5. the effect survives neighboring generalization;
6. the effect survives fresh-family generalization where applicable;
7. negative-transfer controls are acceptable;
8. the minimum-support ablation identifies required vs redundant support;
9. the result survives sealed confirmation;
10. provenance and call identity remain admissible.

Mechanism states remain:

- REQUIRED;
- CONDITIONAL;
- REDUNDANT;
- HARMFUL;
- UNRESOLVED.

## 19. Required D3 outputs

The automated final package must include at minimum:

- `information_value_map.json` — marginal value of information classes;
- `delivery_map.json` — best representation/order/timing;
- `information_location_map.json` — model-visible vs system-only vs both;
- `minimum_sufficient_information_packet.json`;
- `disposition_compiler_evidence.json`;
- `information_assistance_interaction.json`;
- `model_substitution_frontier.json`;
- `negative_transfer_map.json`;
- `sequential_decisions.jsonl`;
- `failure_migration_map.json`;
- `d3_campaign_journal.jsonl`;
- `d3_call_ledger.jsonl`;
- `d3_resume_state.json`;
- `d3_final_report.md`;
- `d4_handoff.json`.

The final report must answer:

- WHAT information matters;
- HOW it should be represented;
- WHEN it should arrive;
- WHERE it should live;
- HOW MUCH is minimally sufficient;
- WHICH model sizes benefit;
- WHAT deterministic assistance contributes independently;
- WHAT information + assistance contributes jointly;
- WHAT information or assistance harms performance;
- WHAT remains unresolved.

## 20. Primary success criterion

The highest-value D3 outcome is not simply improved benchmark accuracy.

D3 succeeds if it causally identifies whether and how:

> better information improves model cognition, deterministic assistance converts cognition into correct system behavior, and the combination allows a smaller local model to match or exceed a larger raw model while preserving hard invariants and reducing model dependence.

This is the primary architecture-substitution claim D3 is designed to test.
