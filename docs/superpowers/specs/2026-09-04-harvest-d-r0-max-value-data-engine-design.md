# Harvest D R0 — Maximum-Value Zero-Call Data Engine Design

Date: 2026-09-04
Status: OWNER-APPROVED R0 DESIGN / PRE-PHYSICAL-CLOSURE GATE

## 1. Purpose

R0 exists to make every later physical model call maximally reusable and causally interpretable before D3-Closure spends another inference call.

R0 is **model-free**. It must not authorize or execute physical inference. Its job is to convert the current Closure harness into a claim-space-aware evidence engine that can answer:

> What exactly will a proposed call teach us, what prior evidence can already reduce or prioritize that call, what causal treatment was actually exposed, what state changed, what coverage obligation was satisfied, and what claims remain illegal afterward?

R0 is not a prompt optimizer and is not Test 5. It is the measurement/discovery substrate required for R1-R10 and the Harvest D -> Test 5 handoff.

## 2. Governing constraints

R0 obeys:

- `REPO_LAWS_AND_REGULATIONS.md`;
- `INVERTED_CONSTITUTION.md`;
- `CLAIM_SPACE_ADEQUACY_AMENDMENT.md`;
- `AGENTS.md`;
- `TESTING.md`;
- `docs/research/2026-09-04-inverted-complete-research-testing-brain-dossier.md`;
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-closure-search-space-adequacy-addendum.md`;
- `docs/superpowers/plans/2026-09-03-d3-closure-claim-space-cost-scaled-implementation.md`;
- frozen D3-v1 evidence and prior immutable test artifacts.

Permanent rules applied here:

1. Data collection is cheap; retesting is not.
2. Small datasets are not discarded merely because they are underpowered for broad claims.
3. Historical evidence may increase decision value, reduce duplicate testing, identify strata, seed priors, detect instrumentation defects, and prioritize challengers.
4. Historical evidence must never be relabeled as fresh causal confirmation or sealed generalization evidence.
5. Actual model-visible exposure outranks nominal treatment labels.
6. Raw evidence is immutable; derived interpretations are versioned and reproducible.
7. Call count is not claim-space coverage.
8. System-only work consumes zero physical model-call budget.
9. Physical Closure remains fail-closed until R0 and all later mandatory adequacy prerequisites are green.

## 3. R0 architecture

R0 adds a model-free evidence graph around the existing Closure primitives.

```text
CLAIM CONTRACT
     |
     v
SEARCH-SPACE ENUMERATION
     |
     +--> legality / oracle-leak rejection
     +--> actual-render equivalence
     +--> no-op collapse
     +--> deterministic/system-only reduction
     |
     v
REDUCED CANDIDATE UNIVERSE
     |
     +--> prior-evidence valuation
     +--> pairwise coverage obligations
     +--> targeted 3-way obligations
     +--> uncovered-space registry
     |
     v
R0 TREATMENT / EVIDENCE CONTRACT
     |
     +--> treatment identity
     +--> actual exposure identity
     +--> pre-state identity
     +--> action-frontier identity
     +--> scheduler rationale identity
     |
     v
MODEL-FREE ADEQUACY REPORT
     |
     +--> what is ready
     +--> what is blocked
     +--> legal claim ceiling
     +--> explicit physical_execution_authorized=false
```

R0 does not replace existing `d3_closure_search_space.py`, `d3_closure_covering.py`, `d3_closure_cost.py`, `d3_closure_treatment.py`, or `d3_closure_adequacy.py`. It composes and hardens them.

## 4. Evidence tiers — preserve small datasets without overstating them

Every existing or future evidence source is assigned an explicit evidence tier.

### E0 — deterministic/system evidence

Zero-call evidence such as rendering equivalence, compiler/guard replay, static legality checks, exact hashes, coverage enumeration, oracle consistency checks, and historical artifact integrity.

Can support deterministic claims directly when the mechanism is purely deterministic.

### E1 — historical empirical prior

Prior physical runs including small-N datasets, D2 slices, D3-v1, Harvest A/B/C, D4, and other frozen empirical evidence.

Allowed uses:

- estimate likely effect direction;
- identify failure-family strata;
- prioritize factor levels;
- identify likely no-op or harmful regions for mandatory challenge rather than silent pruning;
- seed scheduler priors;
- estimate runtime/cost priors;
- select sentinel cases;
- discover instrumentation fields that must exist;
- detect contradictions requiring fresh evidence;
- reduce redundant retesting when exact causal equivalence is provable model-free.

Forbidden uses:

- fresh confirmation;
- sealed confirmation;
- proof of global optimum/minimum;
- proof of current runtime reproducibility;
- proof of current model-digest behavior when digest/runtime changed;
- automatic elimination of a candidate solely because a small prior dataset looked weak.

### E2 — fresh development evidence

New R1-R7 physical evidence used for calibration, screening, interaction search, local optimization, real recovery, routing, and robustness.

### E3 — fresh sealed confirmation

Untouched R8 confirmation evidence opened only after candidate policies are frozen.

### E4 — novelty/unknown-edge evidence

R9 D6 edge-case discovery evidence. It may reopen earlier rounds but may not be retroactively treated as sealed confirmation for a tuned policy.

Every artifact referencing evidence must record its tier.

## 5. Historical evidence valuation

R0 must create a model-free ledger for useful prior datasets rather than ignoring them.

Each evidence source receives:

- `evidence_source_id`;
- source path/run;
- immutable source hash where available;
- evidence tier;
- model ID/digest if known;
- case/failure families covered;
- treatment dimensions actually varied;
- sample size;
- outcome fields available;
- instrumentation completeness;
- causal strength classification;
- freshness/runtime compatibility;
- reusable-for fields;
- forbidden-for fields;
- contradictions with later evidence;
- scheduler-prior weight;
- reason for the weight.

Prior weight is never equivalent to observation count. A tiny clean matched dataset can be more valuable for prioritization than a large confounded dataset, while still being insufficient for promotion.

### 5.1 Prior-value classes

- `STRONG_CAUSAL_PRIOR`: matched/sham/intervention evidence with valid instrumentation.
- `USEFUL_DIRECTIONAL_PRIOR`: empirical signal useful for ranking but insufficient for promotion.
- `FAILURE_ATLAS_PRIOR`: valuable for strata, failure families, sentinels, or instrumentation design.
- `COST_RUNTIME_PRIOR`: useful only for initial cost expectations before R1 calibration.
- `INSTRUMENTATION_WARNING`: evidence primarily demonstrating a measurement defect or missing field.
- `NONTRANSFERABLE`: preserved but cannot influence the live scheduler beyond explicit challenge selection.

R0 must preserve contradictory priors rather than average them away.

## 6. Canonical per-call evidence graph

Every future physical call must be linkable through stable IDs.

```text
scheduler_decision_id
       |
       v
treatment_id
       |
       v
exposure_id ----> pre_state_id ----> action_frontier_id
       |                 |
       v                 v
physical_model_call_id
       |
       v
proposal_id
       |
       v
system_decision_id
       |
       v
execution_id
       |
       v
post_state_id
       |
       v
verification_id
       |
       +--> failure_event_id
       +--> recovery_id
       +--> counterfactual_group_id
```

R0 defines and validates the zero-call portions of this graph. Later rounds populate physical-call nodes.

## 7. Treatment identity contract

A nominal factor vector is not enough.

Each admitted treatment must record:

- full factor vector;
- selected I1-I10 fields;
- representation;
- ordering;
- amount;
- timing;
- placement;
- A1-A4 model-visible assistance;
- model/family applicability;
- semantic field hash;
- rendered payload hash;
- outbound system-message hash;
- outbound task/user-message hash;
- actual field order;
- assistance payload hash;
- approximate token burden;
- legality;
- prune/admit reason;
- equivalence class ID;
- deterministic treatment ID.

Two nominal variants are one treatment when the actual model-visible semantic/rendering/delivery behavior is equivalent.

No-op labels must collapse before physical scheduling.

## 8. Exposure contract

R0 adds an explicit exposure manifest because later analyses need to know not merely that `I4=ON`, but how and where I4 appeared.

For each rendered field or assistance block, capture where derivable model-free:

- field/mechanism ID;
- source/trust class;
- rendered segment hash;
- byte start/end offset;
- approximate token start/end offset;
- normalized position fraction;
- channel (`SYSTEM`, `TASK`, `ASSISTANCE`);
- order index;
- timing class;
- representation;
- semantic value hash;
- authoritative vs non-authoritative status.

Exact tokenizer offsets may be added in R1 when a runtime tokenizer is available. R0 must at least provide deterministic approximate offsets from the outbound messages.

## 9. Pre-state and action-frontier contract

For every case/treatment candidate, R0 must derive stable model-free state descriptors where the case schema supports them:

### Pre-state

- objective/subgoal;
- canonical state/version;
- evidence available/missing;
- authority/scope;
- consequence/reversibility;
- invariants/postcondition requirements;
- dependencies/depth;
- prior verified/recovery state;
- novelty/uncertainty;
- failure family;
- hard-invariant sensitivity.

### Action frontier

- candidate actions;
- admissible actions;
- action count;
- removed/rejected actions when deterministically known;
- reason codes;
- irreversible action count;
- authority-sensitive action count;
- evidence-gated action count.

This lets later analysis separate cognition improvement from action-space shaping.

## 10. Claim-space manifest

R0 must emit a claim contract before any physical call.

At minimum the manifest defines the claims Harvest D intends the corrected Closure campaign to resolve:

- information-field value;
- amount/burden curve;
- representation effects;
- ordering effects;
- placement/timing effects;
- A1-A4 causal value;
- model/family conditional effects;
- model substitution boundary;
- negative-transfer boundary;
- real recovery capability;
- routing features and thresholds;
- minimum-sufficient-information eligibility;
- system/model responsibility boundaries.

Each claim records:

- inferential objective: `SCREEN | INTERACTION | OPTIMIZE | MINIMALITY | BOUNDARY | CONFIRM`;
- material factors;
- effect modifiers;
- required coverage obligations;
- required evidence tiers;
- required negative/sham/control evidence;
- required fresh/sealed confirmation;
- current legal claim ceiling.

## 11. Search-space reduction

The raw theoretical space is derived from factor cardinalities and never hard-coded.

Safe model-free reductions include:

- impossible combinations;
- hidden-oracle leakage;
- inapplicable fields;
- exact byte duplicates;
- model-visible semantic equivalents with identical delivery behavior;
- no-op ordering/timing/placement variants;
- deterministic consequences that do not require cognition.

The following are **not** safe prune reasons by themselves:

- longer prompt;
- weak historical prior;
- small prior sample;
- current architectural preference;
- negative D3-v1 result produced under invalid instrumentation;
- model-size assumptions.

Those candidates may receive lower scheduler priority later but remain represented in the uncovered/pruning rationale unless eliminated by a valid equivalence or legality rule.

## 12. Coverage obligations

R0 computes model-free coverage obligations over the admitted search domain.

Required:

- 100% coverable pairwise factor-level coverage for the selected broad screen;
- explicit constrained/uncoverable pair ledger;
- deterministic design generation;
- required targeted 3-way obligations;
- protected random/challenger rows from underexplored equivalence classes;
- model/family effect-modifier visibility;
- context-length burden controls separated from semantic-content changes.

High-priority 3-way obligations include:

- content x representation x model;
- content x amount x model;
- content x A2 x model;
- I4/missing evidence x A3 x model;
- I2/state x A1 x family;
- authority/invariant x ordering/placement x family;
- amount x timing x model;
- information x assistance x failure family.

R0 reports obligations; it does not spend calls to satisfy them.

## 13. Scheduler-ready candidate metadata

R0 does not implement the final adaptive inference policy, but every candidate must expose the metadata later required by the frontier scheduler:

- coverage novelty;
- prior evidence value;
- prior contradiction flag;
- expected architecture-decision relevance;
- hard-invariant relevance;
- model/family applicability;
- estimated token burden;
- initial cost prior;
- discovery/challenger eligibility;
- sealed eligibility;
- required control/sham linkage;
- unresolved claim IDs the candidate can inform.

Historical evidence changes priority, not truth.

## 14. Required R0 artifacts

Model-free Closure must emit at least:

- `closure_claim_space_manifest.json`
- `closure_search_space_manifest.json`
- `closure_candidate_equivalence_classes.jsonl`
- `closure_candidate_pruning_ledger.jsonl`
- `closure_prior_evidence_ledger.jsonl`
- `closure_treatment_catalog.jsonl`
- `closure_treatment_exposure.jsonl`
- `closure_pre_state_catalog.jsonl`
- `closure_action_frontier_catalog.jsonl`
- `closure_combinatorial_coverage.json`
- `closure_interaction_coverage.json`
- `closure_uncovered_space.json`
- `closure_r0_readiness_report.json`
- `closure_claim_adequacy_report.json`

All artifacts must be included in checksums/manifests.

## 15. R0 readiness semantics

R0 can finish `R0_MODEL_FREE_COMPLETE` only when:

- raw claim/search counts are derived;
- legal/equivalent/no-op reduction is explicit;
- treatment identities are deterministic;
- required prior datasets are inventoried or explicitly marked unavailable;
- smaller historical datasets are preserved with bounded evidence roles;
- coverage obligations are generated;
- targeted 3-way obligations are represented;
- treatment exposure is reconstructable;
- pre-state/action-frontier catalogs are generated where applicable;
- uncovered/pruned regions are explicit;
- all required R0 artifacts are present and non-empty where semantically required;
- no physical model calls occurred;
- physical Closure remains unauthorized.

`R0_MODEL_FREE_COMPLETE` does **not** mean physical Closure is authorized. R1 reproducibility/cost calibration, adaptive frontier, local minimality, real recovery, protected confirmation, blocker audit, and other mandatory gates must still become green.

## 16. Failure behavior

R0 fails closed on:

- missing mandatory source data without an explicit bounded-unavailable record;
- ambiguous treatment identity;
- duplicate treatment IDs mapping to different exposures;
- hidden oracle material in model-visible content;
- impossible coverage claims;
- uncovered mandatory 3-way obligations hidden from the report;
- historical evidence silently counted as fresh evidence;
- stale/mutated frozen D3-v1 evidence;
- empty required artifacts falsely reported complete;
- physical model-call count greater than zero.

No blind retry is permitted.

## 17. Acceptance tests

The R0 implementation must prove at minimum:

1. raw candidate count is derived from factor cardinalities;
2. different nominal labels with identical actual exposure collapse;
3. no-op timing/order/placement collapses are recorded, not silently dropped;
4. oracle-leaking candidates are rejected;
5. historical small datasets are inventoried with bounded evidence roles;
6. a weak/small prior cannot directly eliminate an otherwise legal candidate;
7. prior evidence can change candidate priority metadata without becoming fresh evidence;
8. treatment exposure includes channel/order/position information;
9. pre-state/action-frontier catalogs are stable for the same case/config;
10. pairwise coverage obligations are complete for the admitted screen domain;
11. required 3-way obligations are either covered/planned or explicitly missing;
12. uncovered search regions are explicit;
13. R0 readiness fails when any mandatory artifact is missing/empty;
14. model-free Closure emits the full R0 package;
15. R0 emits zero physical calls;
16. execution authorization remains false after R0 completion;
17. checksums cover every R0 artifact;
18. Windows model-free launcher path continues to pass.

## 18. Non-goals

R0 does not:

- choose the final information policy;
- choose the final model/router;
- classify A1-A11 finally;
- prove minimum sufficient information;
- execute recovery inference;
- open fresh/sealed confirmation evidence;
- design Test 5;
- authorize physical Closure.

## 19. Completion boundary

R0 ends when the repository can produce a complete zero-call package that tells R1-R10 what is known, what priors exist, what must be tested, what coverage remains, what each future call must record, and what claims are still illegal.

Only after R0 is green does the project proceed to R1 reproducibility and local cost calibration.
