# Harvest D D3 — Research-Delta Addendum

## Status

**OWNER-APPROVED. NORMATIVE FOR D3 IMPLEMENTATION.**

This addendum amends and strengthens:

- `2026-09-03-harvest-d-d3-automated-information-control-tomography.md`; and
- `2026-09-03-harvest-d-d3-data-capture-addendum.md`.

It adds three research-motivated requirements discovered immediately before implementation:

1. a pure context-length causal control;
2. a protected randomized exploration stream alongside adaptive scheduling; and
3. explicit decomposition of failure detection, diagnosis, recovery selection, execution, and post-recovery verification.

These changes do **not** increase the D3 physical-model-call ceiling above 1,000. They consume the existing unsealed discovery reservoir and should use deterministic/system-only replay wherever a new model call is not causally required.

---

# 1. PURE CONTEXT-LENGTH CAUSAL CONTROL

D3 already tests information amount, overload, representation, ordering, placement, and timing. That is not sufficient to distinguish semantic distraction from a **pure context-length tax**.

D3 must therefore include matched cases in which the useful information is held constant while context length changes.

## 1.1 Required matched conditions

For eligible cases, compare at minimum:

### C0 — MINIMAL USEFUL CONTEXT
Only the useful information required by the condition under test.

### C1 — LENGTH-ONLY / LOW-SEMANTIC PADDING
The exact same useful information as C0 plus token-matched padding designed to add context length while adding as little task-relevant semantic content as practical.

### C2 — IRRELEVANT PLAUSIBLE CONTEXT
The exact same useful information as C0 plus plausible but task-irrelevant material of approximately matched added token length.

### C3 — REDUNDANT / REPEATED CONTEXT
The exact same useful information as C0 plus repeated or redundant information of approximately matched added token length.

Where useful, an overloaded/full-history condition may remain as an additional stress condition but may not substitute for C1–C3.

## 1.2 Causal questions

The experiment must distinguish:

- useful-information effect;
- pure context-length effect;
- semantic-distraction effect;
- redundancy/repetition effect;
- relevant-information position effect;
- truncation effect;
- model-size × context-length interaction;
- representation × context-length interaction.

Do not infer a pure length effect from a long prompt that also changes semantic content.

## 1.3 Matching requirements

Within a matched context-length comparison, preserve where applicable:

- identical case and semantic oracle;
- identical useful information fields and values;
- identical useful-information ordering unless ordering is the tested variable;
- identical system/tool schemas;
- identical generation parameters;
- identical model artifact/runtime provenance;
- approximately matched added-token volume between long-context controls;
- no hidden oracle leakage in padding.

If exact token matching is not possible before runtime tokenization, record the realized token counts and analyze the actual difference.

## 1.4 Data capture additions

Record per call/condition:

- context-control ID (`C0`, `C1`, `C2`, `C3`, or stress variant);
- exact useful-information field set and hash;
- useful-information token contribution where measurable;
- added/padding token contribution;
- total prompt tokens;
- useful-token ratio;
- positions/spans of useful information in the rendered prompt;
- distance from each critical information span to the model decision boundary/end of prompt where measurable;
- padding generation method/version;
- padding semantic class;
- truncation occurrence and exact removed spans/fields;
- whether the model referenced information originating from padding;
- model-size/context-control interaction label.

## 1.5 Allocation rule

Start with a small matched screen. Deepen only if context length, distraction, redundancy, or model-size interaction produces a meaningful unresolved effect.

This is part of the existing D3.2/D3.3/D3.7 discovery reservoirs. It does not receive an additional call budget outside the 1,000-call ceiling.

---

# 2. PROTECTED RANDOMIZED EXPLORATION STREAM

D3's adaptive scheduler is valuable but can create tunnel vision, selection bias, or premature concentration on experiment regions that looked promising early.

D3 must therefore maintain a small protected randomized/stratified exploration stream in parallel with adaptive high-information scheduling.

## 2.1 Purpose

The exploration stream exists to:

- detect scheduler blind spots;
- estimate whether adaptive selection systematically changes observed effect sizes;
- expose mechanisms/families the scheduler prematurely deprioritized;
- provide a less selection-biased reference distribution;
- preserve coverage of eligible experiment space;
- challenge early scheduler assumptions.

It is a scientific control on the scheduler, not a replacement for adaptive allocation.

## 2.2 Allocation

Of **actual unsealed physical model calls**, target approximately **10–15%** for the protected exploration stream.

Rules:

- the protected 100-call sealed confirmation reserve is untouched;
- the exploration share is drawn from the existing unsealed discovery reservoir;
- if D3 stops early, the exploration fraction applies to the calls actually spent rather than forcing a fixed quota;
- safety-ineligible or scientifically invalid conditions remain ineligible for random assignment;
- ordinary adaptive stopping cannot silently consume the protected exploration share;
- a hard safety/integrity stop may terminate all streams.

The controller should schedule exploration in blocks throughout the campaign rather than spending it all at the beginning or end.

## 2.3 Sampling method

Prefer **stratified random exploration over the eligible unresolved space**, not naive uniform sampling over impossible or irrelevant combinations.

Stratify where practical across the dimensions that materially affect D3 conclusions, including:

- model/capacity tier;
- case/failure family;
- information condition;
- assistance class;
- recovery class;
- difficulty/risk tier;
- development versus fresh/neighbor status where allowed.

The exploration scheduler may exclude combinations that are preregistered as inapplicable, unsafe, contaminated, or causally meaningless.

## 2.4 Mandatory scheduler evidence

For every adaptive or exploration assignment, record:

- scheduler mode: `ADAPTIVE` or `PROTECTED_EXPLORATION`;
- full eligible candidate set or a durable reference to it;
- deterministic adaptive score/rank for each eligible candidate where computed;
- randomization/stratification block ID;
- selection probability/propensity when calculable;
- random seed/state sufficient to reproduce assignment;
- exclusion/ineligibility reasons;
- calls remaining in adaptive, exploration, and sealed pools;
- current hypothesis/evidence state before assignment.

## 2.5 Bias diagnostic

D3's final analysis must compare adaptive-stream and exploration-stream evidence for signs of:

- effect-size inflation/deflation;
- family/model undercoverage;
- premature mechanism elimination;
- selection-induced apparent superiority;
- unobserved high-value regions discovered by exploration;
- disagreement in mechanism rankings.

A material adaptive-versus-exploration contradiction is **high-value evidence** and must be reconciled before promotion of the affected mechanism.

---

# 3. DETECTION → DIAGNOSIS → RECOVERY → VERIFICATION DECOMPOSITION

D3 may not treat `recovery` as one bundled mechanism. A successful or failed recovery trajectory can fail at several distinct responsibility boundaries.

For every applicable failure/recovery case, decompose the trajectory into the following observable stages:

```text
FAILURE OCCURS / PRE-FAILURE STATE
        ↓
DETECTION
        ↓
DIAGNOSIS / FAILURE CLASSIFICATION
        ↓
RECOVERY OPTIONS GENERATED / AVAILABLE
        ↓
ADMISSIBILITY / SAFETY FILTER
        ↓
RECOVERY SELECTION
        ↓
RECOVERY EXECUTION OR SYSTEM REJECTION
        ↓
RESULTING CANONICAL STATE / EFFECT STATUS
        ↓
POST-RECOVERY VERIFICATION
        ↓
RECOVERED / MIGRATED / WORSENED / UNKNOWN / ESCALATED / SAFE-STOPPED
```

## 3.1 Detection layer

Record and score separately:

- whether a consequential failure/divergence existed;
- first component capable of observing it;
- whether detection fired;
- detector source/mechanism;
- true/false positive and false-negative state where an oracle exists;
- first-detection lag;
- whether earlier detection was possible from already available system evidence;
- whether detection merely noticed the symptom or identified the causal boundary.

## 3.2 Diagnosis layer

Record and score separately:

- predicted failure family/layer;
- competing diagnoses if explicitly emitted;
- confidence/uncertainty category;
- evidence/state fields used;
- correctness of diagnosis where deterministically adjudicable;
- whether diagnosis localized the first meaningful divergence;
- whether an incorrect diagnosis still led to a safe disposition;
- whether a correct diagnosis led to an incorrect recovery choice.

This separates **knowing something is wrong** from **knowing what is wrong**.

## 3.3 Recovery-option layer

Record:

- complete observable recovery option set;
- source of each option: model, deterministic system, predefined policy, tool, or mixed;
- whether the correct/safest recovery was present in the candidate set;
- unsafe or inapplicable options proposed;
- required evidence/authority/state prerequisites for each option;
- eligibility/admissibility result and reason for every option;
- options rejected before model/system selection.

Measure **candidate-set coverage** independently from final selection quality.

## 3.4 Recovery-selection layer

Record and score:

- selected recovery;
- selector component;
- selection inputs;
- selected-versus-best-admissible disposition where an oracle exists;
- unnecessary escalation;
- unsafe retry selection;
- failure to choose ACQUIRE_EVIDENCE when required;
- failure to reconcile unknown effects before retry;
- least-destructive/reversible choice quality;
- whether another available admissible recovery would have produced a better verified outcome.

## 3.5 Recovery-execution layer

Record:

- admitted/rejected execution;
- authority/scope state at execution;
- exact state/effect before execution;
- execution/simulation result;
- partial success/failure;
- unknown external effect;
- duplicate-effect risk;
- compensation/rollback status;
- canonical-state transition;
- new failures introduced.

## 3.6 Post-recovery verification layer

Record and score independently:

- verifier mechanism/version;
- expected postcondition;
- actual postcondition;
- local success versus global invariant success;
- stale canonical state after recovery;
- failure migration;
- verifier false positive/negative where adjudicable;
- whether the verifier checked the correct world/state model;
- whether authority or effect state was incorrectly resurrected;
- whether further action is admissible.

A recovery is not successful merely because the original symptom disappeared.

## 3.7 Causal intervention ladder

Where causally valid, test the following decomposition using the **same raw model response and zero-call deterministic replay** whenever possible:

- `R0`: RAW / no recovery assistance;
- `R1`: detection only;
- `R2`: detection + diagnosis;
- `R3`: detection + diagnosis + admissibility-constrained recovery options;
- `R4`: detection + diagnosis + constrained recovery selection;
- `R5`: full recovery pipeline + post-recovery verification;
- matched SHAM variants where meaningful.

Do not spend a new model call merely to toggle a deterministic downstream stage when the exact same physical response can be replayed.

If a stage changes what the model sees before it decides, a new matched physical call may be required and must be labeled accordingly.

## 3.8 Responsibility attribution

Every failed recovery trajectory must identify the earliest supported causal responsibility boundary, such as:

- `DETECTION_MISS`;
- `DIAGNOSIS_WRONG`;
- `RECOVERY_CANDIDATE_MISSING`;
- `ADMISSIBILITY_FILTER_WRONG`;
- `RECOVERY_SELECTION_WRONG`;
- `EXECUTION_FAILURE`;
- `STATE_RECONCILIATION_FAILURE`;
- `POSTCONDITION_VERIFIER_FAILURE`;
- `FAILURE_MIGRATION`;
- `ORACLE_OR_INSTRUMENTATION_UNRESOLVED`.

Later downstream failures should also be retained; the first causal boundary is not permission to discard the rest of the trajectory.

## 3.9 Required recovery metrics

At minimum, make it possible to compute:

- detection precision/recall where labels permit;
- detection lag;
- diagnosis accuracy and uncertainty;
- recovery candidate coverage;
- unsafe-option proposal rate;
- admissibility-filter false allow/false block;
- recovery-selection correctness;
- unnecessary escalation rate;
- blind/unsafe retry rate;
- verified recovery rate;
- preventable damage;
- bad-correction rate;
- post-recovery invariant preservation;
- failure-migration rate;
- recovered-but-stale-state rate;
- causal lift versus OFF/RAW;
- causal lift versus SHAM;
- model-size × recovery-stage interaction;
- information × recovery-stage interaction;
- assistance × recovery-stage interaction.

---

# 4. CALL-BUDGET AND AUTOMATION CONSEQUENCES

The 1,000-call ceiling remains unchanged.

These additions modify **allocation and observability**, not the total budget.

The automated D3 controller must:

1. include the new context-length comparisons in eligible information experiments;
2. reserve a rolling 10–15% target share of actual unsealed calls for protected exploration;
3. preserve the 100-call sealed confirmation reserve;
4. decompose recovery evidence into the stages above;
5. prefer deterministic replay/system-only testing for downstream recovery stages when valid;
6. reallocate calls from context/recovery variants classified HARMFUL/FUTILE only after the protected exploration rules and contradiction checks are satisfied;
7. retain all new metadata in raw, normalized, and derived evidence layers.

No new physical call is justified solely because a deterministic analysis, replay, verifier run, static/system test, or existing raw response can answer the same causal question adequately.

---

# 5. NEW REQUIRED DATA PRODUCTS / FIELDS

The D3 final package must additionally make the following directly queryable, either as new artifacts or schema-versioned extensions of existing D3 artifacts:

- context-length control assignments and realized token geometry;
- useful-information versus padding token accounting;
- protected-exploration assignments and selection propensities;
- adaptive-versus-exploration coverage/effect comparison;
- detection events and detection lag;
- diagnosis records;
- recovery candidate sets and admissibility decisions;
- recovery-selection records;
- execution/effect transitions;
- post-recovery verification records;
- earliest causal recovery-responsibility classification;
- stage-by-stage recovery outcome deltas;
- deterministic recovery replay lineage.

Recommended explicit artifact names:

- `d3_context_length_controls.jsonl`;
- `d3_exploration_assignments.jsonl`;
- `d3_scheduler_bias_diagnostics.json`;
- `d3_failure_detection_events.jsonl`;
- `d3_failure_diagnoses.jsonl`;
- `d3_recovery_candidates.jsonl`;
- `d3_recovery_stage_events.jsonl`;
- `d3_recovery_responsibility_map.json`.

The data dictionary must define all added fields/enums.

---

# 6. PROMOTION IMPACT

No information-delivery, scheduler, recovery, or model-substitution mechanism may be promoted if the relevant new control reveals a material unresolved contradiction.

In particular:

- a context strategy is not promotable if its apparent benefit is actually explained by uncontrolled context length or padding/distraction effects;
- an adaptively discovered winner is not promotable if protected exploration materially contradicts the ranking and the contradiction is unresolved;
- a recovery mechanism is not promotable as a bundled success if stage decomposition shows that a different component caused the gain or that the recovery introduced material migration/global-invariant loss.

These controls exist to make the final D3 architecture **more causally identifiable, more reusable, and less likely to require expensive retesting**.
