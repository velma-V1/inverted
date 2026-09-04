# Harvest D D3-Closure v2 — Search-Space Adequacy and Cost-Scaled Information Tomography Addendum

## Status

**OWNER-APPROVED NORMATIVE CORRECTIVE ADDENDUM. PHYSICAL D3-CLOSURE EXECUTION IS NOT AUTHORIZED UNTIL THIS ADDENDUM IS IMPLEMENTED AND ITS MODEL-FREE ADEQUACY GATE PASSES.**

This addendum corrects a scientific-design defect discovered before any D3-Closure v2 physical model call was spent. It supplements and, where conflicting, supersedes Sections 5, 8, 11, 13, 15, 16, and 17 of `2026-09-03-harvest-d-d3-closure-v2-design.md`.

It is governed by:

- `REPO_LAWS_AND_REGULATIONS.md`;
- `INVERTED_CONSTITUTION.md`;
- `CLAIM_SPACE_ADEQUACY_AMENDMENT.md`;
- frozen D3-v1 evidence/provenance;
- the post-D3 adaptive evidence-deepening addendum.

D3-v1 remains immutable historical evidence. No D3-Closure physical evidence exists yet, so correcting Closure now does not contaminate an empirical campaign.

---

## 1. The defect being corrected

The previous Closure design allocated only a small information block while intending to support broad claims including:

- minimum sufficient information;
- best information delivery;
- model-specific support;
- information burden/negative transfer;
- information × assistance interaction;
- model-size substitution.

That allocation could identify the best of the sampled treatments. It could not defensibly identify the best practical strategy over the much larger design space.

The failure was **claim-space / experiment-space mismatch**, not merely an insufficient raw call count.

The correction is not brute force. It is structured search:

```text
EXPLICIT CLAIM SPACE
→ ZERO-CALL ENUMERATION / REDUCTION
→ COST + REPRODUCIBILITY CALIBRATION
→ BROAD CHEAP SCREEN
→ INTERACTION COVERAGE
→ ADAPTIVE CHALLENGER SEARCH
→ LOCAL OPTIMIZATION
→ MINIMALITY ABLATION
→ ROBUSTNESS / NEGATIVE TRANSFER
→ MODEL-SPECIFIC BOUNDARIES
→ FRESH / SEALED CONFIRMATION
```

---

## 2. Revised primary objective

The information objective is:

> **Find the smallest defensible conditional information-and-support policy that maps observable model/task/failure features to the minimum sufficient model-visible information, representation, ordering, amount, placement, timing, and assistance required for the highest verified correctness without hard-invariant regression.**

A universal packet is promoted only if specialization does not materially improve verified performance.

The target output is a policy:

```text
(model,
 task/failure family,
 state/evidence features,
 authority/reversibility features,
 novelty/dependency/action-space features)
        ↓
CONTENT SUBSET
REPRESENTATION
ORDERING
AMOUNT / COMPRESSION / BURDEN
PLACEMENT / TIMING
A1-A4 MODEL-VISIBLE ASSISTANCE
        ↓
semantic model decision
        ↓
system-owned disposition / authority / verification / recovery
```

---

## 3. Full primary search space

Before any model call, the system must construct `closure_claim_space_manifest.json` and `closure_search_space_manifest.json`.

### 3.1 Content factors

I1–I10 are independent candidate inclusion decisions unless a case makes a field inapplicable:

1. I1 objective/subgoal
2. I2 canonical state/version
3. I3 scope/authority
4. I4 evidence/missing evidence
5. I5 consequence/reversibility
6. I6 invariants/postcondition
7. I7 admissible actions
8. I8 dependencies/order
9. I9 previous verified/recovery
10. I10 uncertainty/novelty/alternatives

Ten binary fields produce 1,023 non-empty subsets before other factors are considered.

### 3.2 Representation factors

Primary representation classes already present in Harvest D remain candidates unless zero-call equivalence removes them:

- RAW_PROSE
- TYPED_FIELDS
- STRICT_JSON
- DECISION_TABLE
- PRIORITY_BLOCK
- EXPLICIT_ALTERNATIVES
- DECOMPOSITION
- MINIMAL_LEDGER
- COMPRESSED_SUMMARY
- ADMISSIBLE_ACTION_MATRIX

### 3.3 Ordering factors

- DEFAULT
- TASK_OBJECTIVE_FIRST
- STATE_FIRST
- EVIDENCE_FIRST
- SAFETY_STATE_EVIDENCE_FIRST
- SHUFFLED_CONTROL

A treatment is not counted when that ordering produces the same actual field order for the packet.

### 3.4 Amount/burden factors

- MINIMUM
- COMPRESSED
- MODERATE
- FULL
- OVERLOADED

These labels must correspond to real physical payload differences.

Pure token/context burden is tested separately with semantically neutral padding so semantic content is not confounded with length.

### 3.5 Timing and placement

Physically meaningful candidates include:

- UPFRONT
- PRE_DECISION
- JUST_IN_TIME
- PROGRESSIVE only when it is a genuine delivery treatment rather than a cosmetic label
- TASK/USER context placement
- SYSTEM context placement
- MIXED placement only when it creates genuinely distinct model-visible channel behavior

If two timing/placement treatments yield identical outbound messages, they are one equivalence class.

### 3.6 Model-visible assistance

A1–A4 remain cognition-level candidate factors:

- A1 canonical-state/version anchor
- A2 admissible-action frontier
- A3 evidence/missing-evidence support
- A4 dependency/decomposition support

For broad optimization, TARGET presence/absence is the primary factor. Matched SHAM comparisons are reserved for causal confirmation of surviving mechanisms rather than multiplying every candidate by all sham combinations.

A5–A11 remain system-owned/deterministic and should be evaluated primarily through zero-call replay/system testing where causal validity permits.

### 3.7 Effect-modifier strata

The system must preserve at minimum:

- model identity/policy;
- case/failure family;
- evidence missingness;
- authority risk;
- reversibility/irreversibility;
- invariant sensitivity;
- dependency depth;
- action-space size;
- novelty/uncertainty;
- prior failure/recovery state.

The experiment may discover that several strata can share one policy. It may not assume that before testing.

### 3.8 Robustness factors are a second-stage search

Stale, contradictory, noisy, irrelevant, misleading, untrusted, and redundant information are not multiplied into the initial correct/system-owned optimum search.

They form a robustness/negative-transfer stage after promising policies exist.

This keeps the primary search tractable without discarding robustness evidence.

---

## 4. Search-space arithmetic and equivalence reduction

The system must calculate the raw and reduced space rather than hard-code a claim such as “thousands of combinations.”

Before model stratification, the theoretical space can already reach tens of millions when content subsets, representation, ordering, amount, timing, placement, and A1–A4 combinations are multiplied.

The exact count depends on which combinations are legal and genuinely distinct.

Required zero-call outputs:

- `closure_search_space_manifest.json`
- `closure_candidate_equivalence_classes.jsonl`
- `closure_candidate_pruning_ledger.jsonl`
- `closure_uncovered_space.json`

For every generated treatment, record:

- factor vector;
- semantic-field hash;
- rendered payload hash;
- final outbound system-message hash;
- final outbound user/task-message hash;
- field order;
- placement/timing class;
- assistance payload hash;
- approximate token burden;
- legality;
- applicability by model/family;
- equivalence-class ID;
- prune/admit reason.

### 4.1 Safe zero-call pruning

Prune:

- physically impossible combinations;
- hidden-oracle leakage;
- byte-identical treatments;
- model-visible semantically identical treatments with identical delivery behavior;
- no-op ordering/timing/placement labels;
- treatments invalid for a model/case;
- deterministic consequences answerable without a model.

Do not prune merely because a candidate is longer or currently unfavored. Length may itself change model behavior.

---

## 5. Experimental-design strategy

The search must use different designs for different inferential jobs.

### 5.1 Broad screening is not optimization

Use a balanced/fractional or mixed-level covering design to identify high-value factors and factor levels economically.

The broad screen should maximize:

- main-effect identifiability;
- pairwise interaction coverage;
- case/family diversity;
- model/family effect-modifier visibility;
- separation from context-length burden.

One-factor-at-a-time evidence from D3-v1 may be used as a prior/ranking signal but cannot by itself support interaction or optimality claims.

### 5.2 Mixed-level covering design

Implement a deterministic mixed-level covering-array generator, or another equally defensible standard-library-compatible design method, for the live candidate space.

Minimum initial target:

- 100% 2-way coverage of admitted primary factors/levels within the screened domain where physically possible;
- explicit report of constrained/uncoverable pairs;
- targeted 3-way coverage for high-risk factor groups identified by D3-v1, architecture semantics, or early evidence.

High-priority 3-way groups include combinations among:

- content × representation × model;
- content × amount × model;
- content × A2/action-frontier × model;
- evidence/missing-evidence × A3 × model;
- state/version × A1 × family;
- invariants/authority × ordering/placement × family;
- amount × timing × model;
- information × assistance × failure family.

The coverage requirement may expand if observed interactions show that 2-way assumptions are inadequate.

### 5.3 Protected discovery stream

At least a small frozen fraction of development inference budget remains reserved for randomly selected admissible candidates from underexplored equivalence classes.

Purpose:

- detect scheduler blind spots;
- detect unmodeled interactions;
- prevent an early winner from monopolizing the search.

This stream may not open sealed confirmation evidence.

---

## 6. Reproducibility and cost calibration

Before candidate elimination based on small differences, run a fresh calibration block.

### 6.1 Reproducibility block

Default candidate design:

- 4 structurally distinct cases;
- both primary models;
- 3 exact physical repetitions;
- up to 24 physical calls.

Adaptive reduction is allowed only if exact-condition stability is established early under a preregistered rule.

Record:

- byte identity;
- semantic identity;
- verified-outcome identity;
- completion class;
- input/output/thinking tokens where exposed;
- latency;
- context use;
- warm/load metadata;
- previous-call linkage.

The result establishes the empirical noise floor.

Effects smaller than the observed instability floor cannot drive elimination/promotion without additional evidence.

### 6.2 Cost calibration

The same block establishes actual model/policy cost on the user's runtime.

The primary local cost metric is **model inference wall time / GPU occupancy proxy** because all local candidates compete for the same physical resource.

Tokens/context remain explanatory and safety metrics.

The budget system freezes:

- median latency;
- p75/p90 latency;
- median token burden;
- context-exhaustion risk;
- expected cost class

for each model/policy/treatment family used by the scheduler.

---

## 7. Cost-scaled budget model

Raw call count is no longer the main experimental budget.

The controller tracks a budget vector:

```text
physical_model_calls
inference_wall_time_seconds
input_tokens
output/thinking_tokens where exposed
system_only_operations
protected_confirmation_budget
```

### 7.1 Cost classes

#### SYSTEM_ONLY

Weight: zero physical model calls.

Includes enumeration, rendering, static analysis, deterministic replay, compiler/guard testing, existing-evidence analysis, scoring, simulation, coverage generation, and other model-free work.

System-only work has no model-call ceiling. It stops only when it no longer changes a relevant decision or would consume unreasonable ordinary CPU/runtime for no added value.

#### FAST

Short non-thinking/low-latency model calls.

These receive the highest permissible sample count because they are cheap.

#### MEDIUM

Moderate-latency calls receive a moderate sample count.

#### LONG / THINKING

Long-deliberation or near-context-exhaustion calls receive a much smaller sample count.

### 7.2 Dynamic rule

For equivalent scientific value:

```text
FAST CALL  -> MORE SAMPLES
SLOW CALL  -> FEWER SAMPLES
SYSTEM     -> DOES NOT CONSUME MODEL-CALL BUDGET
```

The scheduler uses expected calibrated inference time to reserve budget before a call and reconciles against actual observed time after the call.

### 7.3 Hard safety ceilings remain

Physical call caps remain as runaway-loop protection, but they are intentionally loose for fast calls.

No expensive model/policy may consume the entire physical-call cap because the inference-time budget will stop it first.

### 7.4 No silent under-powering

If a broad claim requires more expensive evidence than the frozen cost envelope can support, the controller must:

1. seek zero-call reduction;
2. use more efficient experimental design;
3. narrow the claim;
4. mark it UNRESOLVED;
5. or require explicit owner authorization for more cost.

It may not retain the broad claim while quietly lowering sample adequacy.

---

## 8. Cost-aware model roles in the information search

The broadest live search should occur where observations are cheapest **without assuming transfer across models**.

### 8.1 SMALL_A

If calibration confirms the prior pattern that SMALL_A calls are extremely fast, SMALL_A may receive hundreds or more development calls because the same inference-time budget can cover a much larger search region.

Use this to learn:

- broad factor effects;
- interactions;
- negative-transfer regions;
- candidate policy neighborhoods;
- failure-family structure.

### 8.2 QWEN

Qwen receives a smaller broad screen when calls are expensive, plus targeted evaluation of:

- candidate policies surviving cheap screening;
- model-specific challengers;
- cases where SMALL_A evidence cannot transfer safely;
- high-value interaction hypotheses;
- fresh/sealed confirmation.

If D4 makes Qwen dramatically faster while preserving semantics, the scheduler automatically increases Qwen sample allowance under the same inference-time budget.

### 8.3 Transfer is a hypothesis

SMALL_A screening may prioritize what Qwen should test; it may not prove Qwen's optimum.

The search must preserve Qwen-specific discovery/challenger calls sufficient to detect non-transfer.

---

## 9. Adaptive search after screening

After each evidence block, update:

- factor main effects;
- supported interaction effects;
- model/family conditional effects;
- candidate expected verified correctness;
- hard-invariant violations;
- completion/context-exhaustion risk;
- uncertainty interval;
- coverage novelty;
- expected information gain per unit calibrated cost.

Candidate scheduling priority is approximately:

```text
hard-invariant uncertainty
> architecture-changing semantic uncertainty
> candidate capable of changing current winner
> uncovered high-value interaction
> model/family conditional uncertainty
> minimum-support uncertainty
> negative-transfer boundary
> efficiency / information-gain-per-cost
```

A cheap candidate with high information value should outrank an expensive candidate with the same expected discrimination.

---

## 10. Local optimization around survivors

The broad screen narrows the candidate region; it does not declare a winner.

For each surviving policy, generate its local neighborhood:

- remove one visible field;
- add one omitted field;
- toggle one A1–A4 mechanism;
- change one representation;
- change one ordering;
- move one amount/compression level;
- change one timing/placement treatment;
- test a context-length-matched control where relevant.

Use sequential elimination to remove dominated neighbors and continue until:

- no tested neighbor produces a meaningful improvement beyond the noise/decision threshold;
- the strongest untested local challenger is below the remaining decision-value threshold;
- or cost ceiling forces an explicit UNRESOLVED result.

---

## 11. Minimum-sufficient-information proof

A packet/policy is not `MINIMUM SUFFICIENT` because it was named minimum.

Promotion requires backward/leave-one-out ablation of every retained model-visible component:

```text
WINNING POLICY
↓
REMOVE COMPONENT
↓
MATCHED FRESH TEST
↓
NO MATERIAL DEGRADATION?
    YES -> DELETE IT
    NO  -> RETAIN IT
↓
REPEAT
```

Components include:

- each retained I-field;
- retained A1–A4 assistance;
- representation complexity where simpler representation is available;
- ordering/timing/placement complexity;
- excess context burden.

After deletion convergence, perform at least one joint-removal/challenger test capable of detecting a pairwise redundancy interaction among retained components.

Output is model/family conditional unless fresh evidence supports a universal MSIP.

---

## 12. Negative transfer and robustness

After candidate policies are found, test boundaries around them:

- too little information;
- too much information;
- irrelevant token-matched burden;
- stale plausible state;
- conflicting untrusted evidence;
- redundant history;
- misleading route/recovery hints;
- poor representation;
- unnecessary decomposition.

Score separately:

- semantic correctness;
- completion rate;
- context exhaustion;
- hard-invariant outcome;
- latency/cost;
- model/family-specific harm.

A support mechanism that helps one model/family and harms another becomes CONDITIONAL, not averaged into a universal policy.

---

## 13. Real recovery testing

Recovery remains an independent causal question.

A recovery trial must include a genuine second decision/state transition when the mechanism claims to recover cognition or action, rather than synthesizing a recovery label from a single answer.

Minimum trajectory:

```text
initial decision/state
→ actual failure/divergence
→ detection
→ diagnosis/classification
→ recovery information/action frontier
→ recovery decision/action
→ resulting state
→ independent verification
```

Prevention and recovery are scored separately.

Recovery model calls obey the same cost-scaling rule: fast recovery decisions may be sampled broadly; long-thinking recovery calls receive a smaller ceiling.

---

## 14. Model substitution frontier

After information/support policies stabilize sufficiently:

Compare:

```text
SMALL_A RAW
SMALL_A OPTIMIZED/SUPPORTED
QWEN RAW under frozen D4 policy
QWEN OPTIMIZED/SUPPORTED
```

Transition models are invoked only when required to localize a residual boundary.

The test must distinguish:

- architecture uplift shared by all models;
- parameter-count substitution;
- model-specific support;
- tasks where architecture cannot close the capacity gap.

If SMALL_A optimized remains materially below Qwen, do not force substitution. Record the boundary.

---

## 15. Fresh and sealed confirmation

Optimization/development data may choose the candidate.

Fresh and sealed data may confirm it.

The final confirmation set includes:

- promoted candidate policy;
- RAW baseline;
- strongest surviving challenger;
- required negative-transfer control where it could overturn promotion.

Confirmation depth is scaled to cost but must meet the minimum evidence requirement of the claim.

If a long-call model cannot obtain adequate confirmation under the cost envelope, narrow the claim or mark UNRESOLVED rather than calling a shallow result promoted.

---

## 16. Revised phase architecture

The old fixed `C1..C7 = 200 calls` framing is no longer sufficient as the normative budget.

Use these logical phases:

### T0 — ZERO-CALL CLAIM-SPACE / BLOCKER AUDIT

No model calls.

Outputs search-space, equivalence, coverage target, cost-plan, and blocker artifacts.

### T1 — REPRODUCIBILITY + COST CALIBRATION

Small preregistered physical block; establishes noise and cost classes.

### T2 — D4 QWEN POLICY CALIBRATION

Cost-scaled matched policy test. Expensive default-thinking calls get a smaller ceiling; if non-thinking is fast, that arm can receive more evidence while maintaining matched validity through appropriate paired allocation.

### T3 — BROAD INFORMATION FACTOR / INTERACTION SCREEN

Primarily cheap calls plus a smaller Qwen-specific covering/challenger sample.

### T4 — ADAPTIVE INTERACTION / CONDITIONAL-POLICY SEARCH

Spend only on unresolved high-value factors/regions.

### T5 — LOCAL OPTIMIZATION + MSIP/MRS ABLATION

Attack survivors and remove unnecessary support.

### T6 — NEGATIVE TRANSFER + REAL RECOVERY

Bound harm and recovery behavior.

### T7 — MODEL-SUBSTITUTION LOCALIZATION

Conditional transition models only if necessary.

### T8 — FRESH/SEALED CONFIRMATION

Protected from development spending.

---

## 17. Revised budget semantics

The protocol no longer promises that 206 or 248 calls are sufficient.

Before T1, only zero-call work is authorized.

After T1 cost calibration, the system freezes an owner-visible experiment budget containing:

- maximum inference wall time;
- physical-call runaway ceiling;
- per-model/policy expected cost;
- protected confirmation inference-time reserve;
- minimum search-coverage requirements;
- minimum evidence depth for each intended claim.

The scheduler then derives allowable sample counts dynamically.

This means:

- fast calls may legitimately number in the hundreds or thousands;
- slow calls may number only in the tens;
- system-only operations may number in the thousands/millions without consuming model-call budget if they remain useful;
- the total scientific search can be massive without being computationally massive.

No phase spends calls merely because a quota exists.

---

## 18. Required new outputs

In addition to existing Closure artifacts, emit:

- `closure_claim_space_manifest.json`
- `closure_search_space_manifest.json`
- `closure_candidate_equivalence_classes.jsonl`
- `closure_candidate_pruning_ledger.jsonl`
- `closure_combinatorial_coverage.json`
- `closure_interaction_coverage.json`
- `closure_reproducibility_calibration.json`
- `closure_cost_calibration.json`
- `closure_cost_budget_state.jsonl`
- `closure_candidate_frontier.jsonl`
- `closure_local_search_ledger.jsonl`
- `closure_minimality_ablations.jsonl`
- `closure_uncovered_space.json`
- `closure_claim_adequacy_report.json`

Existing outputs remain required where applicable.

---

## 19. Hard pre-run adequacy gate

No physical D3-Closure call may start unless automated/model-free validation proves:

1. the full claim-space schema exists;
2. the candidate universe can be generated deterministically;
3. impossible/equivalent/no-op treatments are identified;
4. raw and reduced search-space counts are reported;
5. the covering/screen design meets its declared interaction coverage target;
6. uncovered combinations are explicitly reported;
7. cost calibration can freeze dynamic sample economics;
8. the scheduler ranks evidence value per calibrated cost;
9. fast and slow policies receive different permissible sample counts under the same inference-time envelope;
10. system-only operations consume zero physical model calls;
11. candidate elimination cannot erase the protected random/challenger stream;
12. local minimality search exists;
13. real recovery requires actual multi-step evidence;
14. fresh/sealed confirmation remains protected;
15. final claim strength is mechanically bounded by achieved coverage/evidence state;
16. Law 28 blocker audit passes;
17. the launch path fails closed when this adequacy gate is absent or stale.

---

## 20. Exit conditions

The information-search portion may stop when all are true:

- the strongest candidate policy is stable against its strongest surviving challenger;
- plausible decision-changing main effects/interactions are resolved or explicitly excluded from the claim;
- local neighborhood search has converged to the defined threshold;
- minimum-support ablation has removed redundant components;
- negative-transfer boundaries are sufficiently characterized for supported use;
- model-specific differences are either resolved or the claim is conditional;
- fresh/sealed confirmation succeeds at the required depth;
- remaining uncovered space has expected decision value below the cost of further testing **or** is explicitly carried as UNRESOLVED;
- the claim-adequacy report states exactly what is and is not proven.

The whole Closure stage exits only when its architecture-changing questions are decision-ready for Test 5.

---

## 21. Governing interpretation

The new testing philosophy is:

> **Massive coverage does not require massive expensive inference. Use free system analysis to collapse the universe, use cheap fast calls broadly, use expensive long-thinking calls selectively, and spend sealed confirmation only after the search has earned a candidate worth confirming.**

And:

> **Never call a sampled screen an optimization result. Never call a handcrafted packet minimum without ablation. Never call an experiment sufficient until the search-space/claim-space adequacy gate can explain why the untested space cannot reasonably overturn the claim.**
