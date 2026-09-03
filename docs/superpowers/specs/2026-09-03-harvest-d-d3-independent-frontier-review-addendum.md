# Harvest D D3 — Independent Frontier Review Addendum

## Status

APPROVED NORMATIVE DESIGN ADDENDUM FOR D3.

This addendum exists because user suggestions are a floor, not the design ceiling. D3 must proactively preserve and test high-value dimensions even when they were not explicitly requested, provided they remain inside the frozen Harvest D purpose and do not alter experimental truth, authority, or sealed evidence.

It supplements:

- `2026-09-03-harvest-d-d3-automated-information-control-tomography.md`
- `2026-09-03-harvest-d-d3-data-capture-addendum.md`

The governing principle is:

> If an observable variable is cheap to record now and could plausibly explain later behavior, preserve it now. If a low-cost calibration experiment is necessary to know whether the rest of the evidence is interpretable, run it before spending heavily elsewhere.

## 1. Record opportunities and non-events, not only events

A system that logs only what fired creates severe selection bias. At every decision boundary D3 must record the complete **opportunity set** where practical:

- assistance mechanisms eligible to inspect or intervene;
- mechanisms ineligible and the reason;
- mechanisms eligible but not triggered;
- mechanisms triggered but rejected by validation;
- candidate routes available;
- candidate actions/recoveries available;
- actions/recoveries ruled out and why;
- evidence sources available but not requested;
- information fields available but omitted from the model packet;
- guards/verifiers applicable but not invoked;
- authority that existed but was intentionally not exercised.

This permits later measurement of false negatives, missed opportunities, unnecessary interventions, conditional mechanism value, and policy threshold quality.

Required normalized records include `d3_intervention_opportunities.jsonl` and `d3_decision_opportunity_sets.jsonl`.

## 2. Reproducibility and residual-nondeterminism calibration

D3 must not assume that temperature=0 plus a fixed seed guarantees identical outputs under the actual local runtime.

Before heavy adaptive conclusions depend on exact response stability, run a small preregistered reproducibility block using exact duplicate requests under unchanged configuration.

Default initial calibration:

- 4 structurally different cases;
- SMALL_A and QWEN;
- 3 physical repetitions per exact request/model;
- 24 calls total, counted inside the 1000-call D3 ceiling;
- repeats interleaved rather than executed consecutively where practical;
- record cold/warm model status, prior-call identity, load duration, runtime allocation, and elapsed time since prior call.

Measure at minimum:

- byte-identical response rate;
- semantic-identical response rate;
- disposition stability;
- answer stability;
- structured-decision-trace stability;
- latency/token variance;
- whether divergence correlates with cache/load/order/runtime state.

If meaningful divergence is observed, D3 may allocate additional calibration calls adaptively and must use the observed stochasticity when interpreting exact replays, matched comparisons, and sequential evidence.

If outputs are stable, stop calibration early according to the preregistered rule; do not spend calls merely to prove determinism repeatedly.

Required output: `d3_reproducibility_calibration.json` plus per-call linkage in the normal call/event datasets.

## 3. Case structural descriptors beyond family/difficulty

`family` and a hand-assigned difficulty number are insufficient to discover the true capability frontier. For every case derive and retain objective structural descriptors where meaningful, including:

- prompt/message byte and token length;
- number of state fields;
- number of evidence items and evidence sources;
- evidence completeness ratio where definable;
- number of contradictory evidence items;
- number of authority constraints/scopes;
- number of candidate actions;
- number of admissible actions;
- dependency graph node/edge count;
- dependency depth and width;
- transaction count;
- number of external/simulated effects;
- reversibility class;
- consequence/risk class;
- number of invariants/postconditions;
- number of interacting failure layers;
- ambiguity/hypothesis count when explicitly encoded;
- recovery-choice count;
- novelty/known-signature status;
- required reasoning horizon/step count where deterministically known;
- information-packet field count and token density;
- action-space reduction produced by assistance.

These features must be computed deterministically where possible and versioned. They are explanatory metadata, not replacements for semantic oracles.

Required output: `d3_case_structural_features.jsonl`.

## 4. Normalized model-behavior features

In addition to raw output, derive queryable behavior features without changing the response:

- response bytes/tokens;
- parse success/failure class;
- required-field completeness;
- extra/unexpected fields;
- disposition emitted;
- answer emitted;
- candidate-action count;
- rejected-alternative count;
- evidence references count;
- state references count;
- authority references count;
- missing-information requests count;
- uncertainty/confidence category;
- recovery options considered count;
- selected-recovery class;
- expected-postcondition present/absent;
- hallucinated/nonexistent field references;
- references to stale/wrong-version state;
- proposed action outside admissible set;
- unnecessary escalation/evidence request indicators;
- novelty flag;
- concise reason-code classes.

All derived behavior features must link back to the immutable raw response and parser/scorer version.

Required output: `d3_model_behavior_features.jsonl`.

## 5. Decision-boundary sensitivity and threshold telemetry

For routers, guards, risk checks, confidence gates, evidence sufficiency rules, and other thresholded mechanisms, record more than the final pass/fail decision.

Where available, preserve:

- input feature vector;
- threshold/rule version;
- raw score/value before thresholding;
- threshold value;
- signed distance/margin from threshold;
- tie-breaking rule;
- competing rule scores;
- whether a tiny feature change could flip the decision;
- reason code for the selected route/action.

This allows later threshold tuning and sensitivity analysis from stored evidence without rerunning model inference.

Required output: `d3_decision_boundary_telemetry.jsonl`.

## 6. Carryover, ordering, cache, and time-varying context

Every physical call must record enough neighboring-call context to detect hidden carryover effects:

- immediately previous physical call ID on that runtime/model;
- previous case/arm/model;
- presentation-order index;
- time since previous call;
- model resident/not-resident status where observable;
- load/reload event since previous call;
- runtime process restart epoch;
- warm/cold indicator;
- block/batch identity;
- concurrent local activity relevant to the experiment when safely observable;
- whether hardware allocation changed.

Randomized/interleaved blocks should be used where appropriate to reduce systematic order confounding. Do not add expensive dedicated order experiments unless telemetry or calibration reveals a material effect.

## 7. Missingness, censoring, and unavailable-data provenance

Missing data must itself be data. Every optional or required field that is absent should be classifiable as:

- NOT_APPLICABLE;
- NOT_EXPOSED_BY_RUNTIME;
- COLLECTION_FAILED;
- COLLECTION_SKIPPED_TO_AVOID_PERTURBATION;
- REDACTED_FOR_SAFETY/SECRET_PROTECTION;
- UNKNOWN;
- CAPTURE_INCOMPLETE.

Do not encode these as the same null value without a reason code.

For censored/terminated trials, preserve the exact censoring point and why later events are absent.

Required output: integrated missingness fields plus `d3_missingness_summary.json`.

## 8. Causal-claim graph and evidence traceability

Every architecture claim should be represented as a machine-readable graph rather than only prose.

For each claim preserve:

- claim ID/version;
- exact statement;
- claim state;
- mechanism/information/recovery object involved;
- supporting raw call IDs;
- supporting deterministic replay IDs;
- contradictory call/replay IDs;
- sham/negative-control evidence;
- neighboring/fresh/sealed evidence;
- applicable families/conditions;
- exclusions and known failure region;
- effect estimate/statistical state;
- promotion/suspension/revalidation history;
- superseded claim IDs;
- responsible component/version.

Required outputs:

- `d3_causal_claim_graph.jsonl`
- `d3_claim_evidence_edges.jsonl`

The final system build must be derivable from promoted nodes in this graph rather than from an informal narrative preference.

## 9. Coverage and evidence-saturation telemetry

The adaptive campaign must continuously measure what it has and has not covered.

Maintain matrices for:

- information classes x quality/source/representation/timing;
- assistance mechanisms x failure families;
- recovery choices x failure families;
- model sizes x capability/failure regions;
- TARGET/OFF/SHAM coverage;
- development/neighbor/fresh/sealed coverage;
- structural-feature ranges;
- edge-case classes;
- hard-invariant attack coverage.

For every uncovered cell record whether it is:

- intentionally excluded as scientifically low value;
- structurally inapplicable;
- killed by prior evidence;
- deferred due to budget;
- still unresolved and important.

The scheduler should use coverage gaps as one input to experiment priority, but raw coverage count must never override expected causal information value.

Required outputs:

- `d3_coverage_matrix.json`
- `d3_uncovered_space.jsonl`
- `d3_evidence_saturation.jsonl`

## 10. Protocol-violation and assumption ledger

Record explicit violations and assumptions that could invalidate interpretation:

- protocol deviation ID;
- affected calls/cases/blocks;
- intended protocol;
- observed deviation;
- cause if known;
- whether evidence remains admissible, diagnostic only, segmented, or rejected;
- downstream claims affected.

Also preserve a versioned assumption ledger for assumptions such as model determinism, oracle validity, state-model correctness, independence/matching structure, runtime stability, and absence of leakage.

When evidence contradicts an assumption, update the assumption state; do not silently continue using it.

Required outputs:

- `d3_protocol_violations.jsonl`
- `d3_assumption_ledger.jsonl`

## 11. Unknown/novel field preservation

Runtime/API payloads may gain fields that the harness does not yet understand. The raw payload is always authoritative evidence.

Normalization must preserve unrecognized safe fields in a versioned `extras`/extension map rather than dropping them. Schema evolution may later promote useful unknown fields to first-class normalized columns without rewriting raw evidence.

## 12. Lossless retention policy

Raw evidence may be compressed only losslessly. Do not replace raw requests, responses, state snapshots, or event payloads with summaries to save disk space.

Derived duplicate indexes may be regenerated and can be compressed/rebuilt, but the immutable raw layer and manifests remain authoritative.

## 13. Data salvage after partial/corrupt execution

If a call, block, or run becomes inadmissible, preserve all surviving raw evidence and linkage. Mark the admissibility state; do not delete the material.

A failed experiment can remain extremely useful for:

- harness debugging;
- runtime anomaly analysis;
- edge-case discovery;
- new scorer development;
- failure taxonomy expansion;
- causal hypothesis generation.

Promotion logic must distinguish diagnostic evidence from admissible causal evidence.

## 14. Autonomous schema-extension rule

During D3, the controller may discover a new observable metadata field or edge-case class not anticipated by the design. It may begin recording that field immediately **only if**:

- collection is passive/observational or deterministic;
- it does not alter model prompts, task semantics, authority, oracle access, or execution behavior;
- it is safe/non-secret;
- the schema change is versioned and logged;
- earlier absence is explicitly represented as NOT_PREVIOUSLY_COLLECTED rather than backfilled by guesswork.

Any new field requiring a changed model prompt, new model call, new intervention, new authority, or changed experimental condition is a new experimental hypothesis and must follow normal preregistration/causal rules.

This allows data capture to improve during a long campaign without silently changing the experiment.

## 15. Final independent completeness test

Before D3 is allowed to conclude, run a model-free evidence audit that attempts to answer at least these classes of retrospective question:

1. Why was this exact model call scheduled?
2. What other experiments could have been scheduled instead?
3. What exact information was available to the system, and what subset reached the model?
4. What transformation produced the rendered information packet?
5. What actions, routes, assistance mechanisms, and recoveries were available but not chosen?
6. What exact deterministic rule/threshold caused every system decision?
7. Can the same raw response be rescored, rerouted, reverified, and replayed through all deterministic counterfactuals without inference?
8. Could runtime nondeterminism or order/cache state explain the observed delta?
9. What variables are missing, and why are they missing?
10. What structural case features predict success/failure better than the coarse family/difficulty label?
11. Which promoted architecture claims are contradicted anywhere in the evidence?
12. Which important regions of the experimental space remain uncovered?
13. Can every final-build component be traced to sufficient raw evidence and promotion gates?
14. Can every excluded component be traced to harm, futility, redundancy, or unresolved evidence?
15. If a future analyst proposes a new deterministic scorer/router/verifier, can it be evaluated against original D3 observations without another physical model call?

If a question cannot be answered because a cheap observable field was discarded, the data-capture design or implementation is incomplete.
