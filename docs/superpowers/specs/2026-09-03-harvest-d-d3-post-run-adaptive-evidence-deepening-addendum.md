# Harvest D D3 — Post-Run Adaptive Evidence Deepening Addendum

## Status

APPROVED POST-RUN DESIGN REQUIREMENT.

This addendum defines what must happen **after the current D3 campaign has completed, finalized its evidence package, and frozen its provenance**. It does not modify the live D3 scheduler, call budget, case bank, scoring, success criteria, or sealed confirmation set.

Its purpose is to ensure that D3 does not end at the questions we knew how to ask before the run. The completed evidence dump must be used to discover the exact high-value question, interaction, boundary, failure mode, or mechanism that the original design missed, and then to design the smallest scientifically valid follow-up test capable of resolving it.

The governing principle is:

> A decisive result ends redundant measurement of an answered comparison; it does not end investigation of a promising mechanism. Data already collected must be mined before new calls are authorized, and any new calls must target a concrete unresolved decision that could not be answered from the existing dump.

This is the formal mechanism for asking, after D3:

> **What will we wish we had tested once we can finally see the whole causal surface?**

---

## 1. Hard freeze barrier

Before any post-D3 analysis may influence a new experiment:

1. D3 must reach a terminal state under its original protocol.
2. The D3 final evidence package must be generated.
3. The call ledger, journal, provenance, case hashes, sealed-case hashes, final report, and evidence checksums must be frozen.
4. The original D3 empirical claims must be reported without incorporating any later follow-up evidence.
5. No D3 result may be relabeled, deleted, repaired, or re-scored merely because the post-run analysis reveals a better hypothesis.

The post-run stage is therefore **prospective from the moment D3 closes**, even though its hypotheses are derived retrospectively from D3 evidence.

Any follow-up result must remain distinguishable from original D3 evidence by run ID, protocol version, case partition, provenance, and claim lineage.

---

## 2. Zero-call analysis comes first

The first post-D3 action is not another model call.

The complete D3 dump must be mined using deterministic/offline analysis wherever possible, including at minimum:

- raw model requests and responses;
- normalized calls and scores;
- information packets and field lineage;
- assistance TARGET/OFF/SHAM replays;
- state, evidence, and authority snapshots;
- recovery trajectories;
- model behavior features;
- structural case features;
- sequential decisions;
- decision-boundary telemetry;
- intervention opportunities and non-events;
- negative-transfer evidence;
- missingness and inadmissibility records;
- coverage matrix and uncovered-space records;
- evidence-saturation records;
- causal claim graph and evidence edges;
- runtime/order/carryover telemetry;
- edge cases and anomalies;
- the D3 final report and D4 handoff.

New inference calls are prohibited until this retrospective pass has established that the existing dataset cannot answer a decision-relevant question with sufficient confidence.

---

## 3. Required post-D3 gap registry

The retrospective pass must produce a **Post-D3 Gap Registry**. Every candidate gap must include:

- stable gap ID;
- originating D3 evidence IDs / claim nodes;
- affected model(s);
- affected failure family/families;
- affected information field, representation, assistance mechanism, recovery path, or interaction;
- observed signal;
- why the original D3 design did not fully resolve it;
- whether the gap is caused by missing coverage, insufficient power, confounding, measurement weakness, unexpected interaction, or genuinely new behavior;
- whether it can be answered with zero additional calls;
- candidate causal hypothesis;
- strongest plausible competing explanation;
- exact project decision that would change if the gap were resolved;
- consequence of leaving it unresolved;
- proposed evidence needed to discriminate the alternatives;
- correct destination: immediate post-D3 follow-up, D4, Test 5, Harvest E, Test 6, or no further testing.

A gap with no plausible decision impact does not justify new model calls.

---

## 4. Gap classes

At minimum classify each candidate into one of these states:

### PROMISING_DEEPEN
A mechanism or information treatment shows a superior or strongly favorable signal, but the evidence surface is not deep enough to establish where it works, why it works, or how little support is actually required.

### HARMFUL_BOUND_OR_KILL
A mechanism causes harm or negative transfer. The goal is not to keep testing it indefinitely; the goal is to confirm causality, identify the boundary of harm if that boundary matters, and then kill or strictly condition the mechanism.

### UNRESOLVED_DISCRIMINATE
The current data cannot distinguish competing causal explanations. The next test must maximize discrimination rather than simply add more samples of the same comparison.

### COVERAGE_HOLE
A relevant model, failure family, structural regime, interaction, timing regime, or recovery state is underrepresented or absent.

### INTERACTION_MISSING
Marginal effects are known, but an interaction suggested by D3 evidence was not directly tested.

### GENERALIZATION_MISSING
A promising result has not yet survived enough fresh families, structural neighborhoods, model sizes, or difficulty regimes.

### MINIMUM_SUPPORT_UNKNOWN
A mechanism works, but D3 did not identify the minimum sufficient information packet, minimum required scaffolding, or removable redundant support with enough confidence.

### NEGATIVE_TRANSFER_BOUNDARY_UNKNOWN
A treatment helps in one regime and harms another, but the switch point or observable routing condition is unknown.

### CAPABILITY_BOUNDARY_UNKNOWN
The data shows a transition between models or architectures, but the point at which the smaller model stops being substitutable is not localized tightly enough.

### MEASUREMENT_OR_ORACLE_RISK
A surprising result may be explained by scoring, parsing, instrumentation, oracle/verifier mismatch, missingness, carryover, ordering, or provenance rather than the mechanism under study.

### SURPRISE_NEW_HYPOTHESIS
The dump exposes a behavior or causal relation not represented in the preregistered D3 mechanism families. It is explicitly exploratory until confirmed on fresh evidence.

### RESOLVED_NO_NEW_CALLS
The question is already answerable from D3 or cannot change a project decision. It receives no further inference budget.

---

## 5. Superior results escalate evidence depth

A SUPERIOR result must not be interpreted as “stop learning because this is good.”

Instead:

```text
SUPERIOR SIGNAL
    -> stop redundant screening of the already-answered comparison
    -> identify remaining uncertainty around the winning mechanism
    -> test harder/fresher/generalization boundaries
    -> test matched sham and negative-transfer controls
    -> test relevant interactions
    -> ablate toward MSIP/MRS
    -> localize the failure boundary
    -> determine whether the mechanism is REQUIRED / CONDITIONAL / REDUNDANT
    -> promote only after the applicable fresh evidence gate is satisfied
```

The scheduler or analyst may stop spending calls on a **resolved comparison**, but must not equate that with a resolved **mechanism**.

The same distinction applies to NONINFERIOR results when noninferiority would permit model-size substitution or machinery removal.

---

## 6. Follow-up design must be generated from the observed dump

The exact follow-up test is intentionally **not frozen now** because doing so would defeat the purpose of this stage.

After D3 closes, the follow-up design must be derived from:

1. the highest-value unresolved gaps;
2. the causal claim graph;
3. observed effect sizes and uncertainty;
4. where evidence saturated and where it did not;
5. failure clusters and first-divergence points;
6. model-size transition boundaries;
7. assistance/information/recovery interaction signals;
8. negative-transfer regimes;
9. missing intervention opportunities;
10. anomalies and edge cases that could alter architecture decisions.

The test must therefore answer **the question D3 revealed**, not merely repeat D3 with more calls.

---

## 7. Smallest-valid-test rule

Retesting is expensive. The post-D3 follow-up must be the smallest set of experiments capable of changing a real architecture decision with defensible confidence.

For every proposed physical-call block, record:

- the unresolved hypothesis it targets;
- the competing hypothesis it discriminates against;
- why existing D3 evidence is insufficient;
- why deterministic replay / offline reanalysis is insufficient;
- why the selected cases are maximally informative;
- why the selected model(s) are necessary;
- the minimum fresh evidence depth required;
- the early-stop rule;
- the maximum call ceiling;
- the project decision unlocked by resolution.

Calls that cannot be tied to such a decision are removed before execution.

The user’s requested budget or suggested test is a floor for design thinking, not a requirement to spend unnecessary calls.

---

## 8. Follow-up routing rules

Not every discovered gap belongs in a new immediate test.

Route it to the earliest stage that can resolve it without duplicating future work:

- **Immediate post-D3 follow-up**: a narrow causal uncertainty blocks interpretation of D3 or the design of D4/Test 5.
- **D4**: the issue is specifically Qwen call policy, escalation threshold, or bounded deliberation.
- **Test 5**: the issue concerns architecture optimization, compression, removal, or minimum machinery after the mechanisms are understood.
- **Harvest E**: the issue concerns dev-agent/provider/tool-routing behavior rather than the local model/system causal surface.
- **Test 6**: the issue is best tested only against the final frozen architecture under fresh adversarial, long-horizon, restart, poisoning, corruption, rollback, or local-only conditions.
- **No new test**: the existing evidence is sufficient or the answer cannot affect a decision.

This prevents D3 follow-up work from stealing questions that later stages are already designed to answer.

---

## 9. Post-hoc discovery cannot become confirmation by relabeling

Because the follow-up hypotheses are discovered from D3 results:

- D3 development/sealed cases used to discover the hypothesis may not serve as independent confirmation of that hypothesis;
- a genuinely new mechanism requires fresh cases or a fresh partition before a confirmatory claim;
- exploratory effect sizes must remain labeled exploratory;
- thresholds and success criteria for the follow-up must be frozen before new confirmatory calls begin;
- the follow-up may use D3 evidence to choose **where to look**, but not to manufacture a favorable truth condition;
- D3’s sealed set remains sealed historical evidence and is never converted into a tuning bank.

This preserves causal credibility while still exploiting the information value of the completed dump.

---

## 10. Required follow-up outputs

Before any new physical calls, produce at minimum:

- `post_d3_gap_registry.json`;
- `post_d3_zero_call_findings.json`;
- `post_d3_decision_impact_map.json`;
- `post_d3_hypothesis_lineage.json`;
- `post_d3_followup_routing.json`;
- `post_d3_followup_test_spec.md`;
- `post_d3_followup_budget_justification.json`.

If the conclusion is that no additional immediate test is justified, `post_d3_followup_test_spec.md` must state that explicitly and identify which future stage owns each remaining gap.

If new calls are authorized, the resulting run must preserve its own raw/normalized/derived evidence and link every claim back to both the new evidence and the D3 evidence that generated the hypothesis.

---

## 11. Priority function for the missed-question test

When several gaps compete for a limited follow-up budget, rank them by:

1. hard-invariant or silent-wrong-action risk;
2. ability to change whether a mechanism enters the core architecture;
3. ability to change the minimum required model size;
4. ability to remove machinery while preserving capability;
5. ability to resolve a contradictory or surprising D3 result;
6. ability to localize a negative-transfer or recovery boundary;
7. ability to reduce future model dependence;
8. expected information gain per physical model call;
9. uniqueness relative to D4/Test 5/Harvest E/Test 6;
10. value for future retrospective analysis.

A narrow, high-impact discriminator outranks a broad “more data” campaign.

---

## 12. End state

The post-D3 stage ends only when every material D3-discovered gap is in one of four states:

- **ANSWERED_FROM_EXISTING_DATA**;
- **FOLLOWUP_CONFIRMED_OR_REJECTED**;
- **ROUTED_TO_LATER_STAGE**;
- **EXPLICITLY_NOT_WORTH_TESTING**.

The desired outcome is not another large test by default.

The desired outcome is:

> **Use the D3 evidence dump to discover the test we could not have designed correctly before seeing the results, then run only the minimum fresh experiment necessary to close that exact gap.**

This stage exists to convert unexpected results, superior mechanisms, negative transfer, unresolved comparisons, and uncovered edge cases into higher project value without contaminating the original D3 experiment or wasting calls on questions the existing data already answers.
