# Test-3 Adaptive Evidence Discovery Campaign — Design

Date: 2026-09-01
Status: DESIGN ONLY — NO TIER-A INFERENCE AUTHORIZED
Base SHA: `e646d2e7e77ce28e92e0c8060ff758b950de995f`
Design branch: `design/test3-adaptive-evidence-discovery`

## 1. Purpose

Test-3 is a sequence of small, preregistered experiments designed to force a structural discovery about what actually improves frozen-model agent performance.

The campaign does **not** assume that the answer is a better model, a fixed stack order, adaptive routing, verification, memory, evidence acquisition, or mentoring. Those are competing causal explanations.

The governing question is:

> Given the verified state of a task right now, what is the highest-value next operation, and can the system improve that decision policy from verified failures without changing model weights?

The campaign must be designed so that negative results are as informative as positive results.

## 2. Governing scientific rules

1. **Everything is data.** Every pass, failure, retry, cache hit, unused call, verifier decision, model disagreement, latency, token count, edge case, mentor result, recovery, regression, and instrumentation anomaly is retained.
2. **One causal question per section.** Each section has its own preregistration, run ID, evidence directory, verdict, failure atlas, and forensic bundle.
3. **No giant multi-day run.** Sections are intentionally bounded and analyzed before the next section is frozen.
4. **No outcome-dependent early stopping.** A section may stop only for preregistered infrastructure/safety/integrity reasons, not because results look favorable or unfavorable.
5. **No hidden-gold leakage.** Hidden truth cannot enter prompts, controller inputs, mentor prompts, retrieval queries, or verifier inputs unless that arm explicitly represents an oracle analysis ceiling and is labeled non-production evidence.
6. **Model output is evidence, not authority.** Authority comes from the experiment contract and designated verification/governance mechanisms.
7. **Verifier is implementation-agnostic.** A verifier may be deterministic code, schema/rule validation, property testing, solver output, policy logic, tool evidence, a model, multiple models, or a composition of these.
8. **Every mutation is revalidated.** Retry, repair, regeneration, mentor-induced changes, and retrieved-skill application must all cross the appropriate verification boundary.
9. **Replayability is explicit.** Every counterfactual is labeled `CAUSAL_REPLAY` or `REQUIRES_NEW_INFERENCE`. The experiment must never fabricate unobserved model behavior.
10. **Tier separation remains strict.** GitHub/model-free replay may generate hypotheses and eliminate impossible/low-value designs; architecture claims require Tier-A real model inference.
11. **Holdout hygiene is mandatory.** Each section receives a separate holdout; the final integrated holdout remains sealed until Section 6.
12. **The measurement system is itself testable.** Integrity alarms, telemetry defects, cache-accounting defects, and provenance failures are retained as evidence and cannot silently rewrite experiment conclusions.

## 3. Prior evidence motivating Test-3

The campaign starts from several results already observed:

- Correct intermediate representation produced dramatically higher solvability than direct model action in the earlier basis experiment, indicating that representation/formalization can dominate raw model capability.
- Pure inversion was not a universal win; hybrid deterministic + model + feedback architectures were stronger candidates.
- Retries recover failures but can introduce new failures, so every mutation needs revalidation.
- Structured failure evidence can be more valuable than raw feedback, while overly constrained targeted repair can underperform full regeneration.
- Different models have complementary success regions; there is measurable oracle headroom beyond the best single model and best static role assignment.
- Static specialization did not resolve all hard policy holdouts, implying that the missing mechanism may be state-conditioned recovery rather than merely component order.
- Deterministic validation and semantic validation catch different classes of failure.
- The Test-2 integrity layer itself produced a possible false contamination classification around intentional stability repeats, proving that measurement logic must also be adversarially tested.

These observations motivate competing theories rather than one assumed architecture.

## 4. Competing theories

Test-3 compares six major explanations.

### H0 — Model ceiling
System architecture adds little. The frozen models themselves dominate the remaining error.

### H1 — Fixed-stack theory
A broadly superior static ordering of components exists.

### H2 — Routing theory
No universal fixed stack is sufficient; the best next model/component depends on current task/failure state.

### H3 — Evidence-acquisition theory
The largest gain comes from choosing what information to obtain before acting again.

### H4 — Verification theory
Reliability is dominated by choosing the correct verifier type, placement, and depth for the current risk/failure state.

### H5 — External-learning theory
Verified failures can be converted into reusable edge cases or procedural skills that improve future frozen-model performance.

No hypothesis is privileged in the analysis.

## 5. Campaign structure

```text
Existing evidence
      |
      v
S0 GitHub causal discovery      0 model calls
      |
      v
S1 Fixed stack / order          ~80 max target
      |
      v
S2 Adaptive routing             ~100–120 max target
      |
      v
S3 Verification strategy        ~80–100 max target
      |
      v
S4 Verified experience/memory   ~80 max target
      |
      v
S5 Mentor / skill transfer      ~100–120 max target
      |
      v
S6 Integrated controller        ~120–160 max target
      |
      v
Sealed final holdout
```

The numbers above are **design ceilings, not final preregistered budgets**. Exact section budgets must be frozen after Section 0 power/variance analysis and before any Tier-A call in the relevant section.

An absolute campaign-level safety ceiling of 960 new physical model calls may be used, but the design goal is to remain materially below it by using model-free/GitHub elimination first.

## 6. Section 0 — GitHub causal discovery atlas

### Question
What can be learned from existing evidence without spending new inference?

### Inputs
- Test-1 evidence
- Test-2 evidence
- Model-free Test-2 evidence
- Existing failure taxonomies
- Existing model complementarity/router data
- Existing component-order causal replay data

### Required normalized transition schema

Each historical transition should be normalized into a structure equivalent to:

```text
state_before
  task family
  complexity
  representation
  requirements
  current candidate status
  prior model/role
  prior attempts
  failure signature
  verifier results
  semantic/deterministic disagreement
  retrieved experience if any
  calls/tokens/time spent

action
  component
  model
  verifier
  retry/repair/regenerate/switch/etc.

state_after
  deterministic result
  semantic result
  hidden-gold result
  catastrophic status
  blocked/allowed
  calls/tokens/time delta
```

### Search dimensions
- fixed component permutations
- component ablations
- model-per-role assignments
- failure-conditioned switching
- retry vs regenerate vs repair
- verifier placement
- verifier type where replayable
- cost/success Pareto frontier
- replay-safe conditional policies

### Required labels
Every candidate comparison must be labeled:
- `CAUSAL_REPLAY`
- `REQUIRES_NEW_INFERENCE`
- `INVALID_COUNTERFACTUAL`

### Outputs
- best fixed-policy candidates
- best replayable adaptive-policy candidates
- unresolved causal questions
- `REQUIRES_NEW_INFERENCE` queue
- power/variance estimates for later sections
- candidate Section-1 preregistration

Section 0 may not make Tier-A architecture claims.

## 7. Section 1 — Fixed stack/order

### Question
Does fixed component order have enough causal value to justify further fixed-stack optimization?

### Primary arms
1. best single-model baseline
2. current best fixed hybrid
3. top 2–3 fixed orders discovered by Section 0
4. deliberately poor/random-order negative control

### Required equalization
Where feasible, compare equal physical-call and equal-token slices so additional compute does not masquerade as architectural value.

### Interpretation
- Large, stable fixed-order effect: retain fixed topology as a major variable.
- Small/negligible effect: sharply reduce future budget spent on universal stack-order search.

### Holdout
Dedicated Holdout A only.

## 8. Section 2 — Adaptive routing

### Question
Does choosing the next operation from current evidence state outperform the best fixed topology?

### Primary arms
1. best fixed stack from Section 1
2. task/family router
3. failure-conditioned router
4. richer evidence-state router
5. random router control
6. oracle next-action ceiling for analysis only

### Allowed routing features
Only features available at decision time:
- task family
- complexity
- representation
- previous model/role
- deterministic result
- semantic disagreement signal
- failure signature
- retry count
- budget spent/remaining

Hidden gold is forbidden as a production-router feature.

### Core output
Regret to oracle, regret to best fixed policy, and error reduction attributable to conditional routing.

### Holdout
Dedicated Holdout B only.

## 9. Section 3 — Verification strategy

### Question
What verification mechanism and placement gives the best reliability/cost tradeoff?

### Candidate conditions
- no verification control
- deterministic verification only
- semantic verification only
- deterministic then semantic
- semantic then deterministic
- risk-triggered semantic verification
- second verifier on disagreement

### Verifier classes
May include:
- schema checks
- deterministic requirement checks
- invariant/property tests
- policy engines
- execution/tool evidence
- solver checks
- model semantic verifier
- multi-verifier consensus

### Metrics
- invalid outputs caught
- valid outputs falsely blocked
- catastrophic escapes
- recoveries enabled
- unnecessary verifier calls
- tokens/calls/latency per prevented failure
- verifier disagreement
- stable wrong-verdict rate

### Holdout
Dedicated Holdout C only.

## 10. Section 4 — Verified experience / memory

### Question
Does targeted verified experience improve future frozen-model behavior beyond generic extra context?

### Primary conditions
1. no memory
2. random irrelevant memory
3. similar but wrong/stale memory
4. failure metadata only
5. verified edge-case record
6. verified successful recovery trajectory/summary

### Required measurement
- success delta
- repeated-failure reduction
- physical-call reduction
- token/latency effect
- induced new failures
- overgeneralization
- retrieval precision
- marginal value of retrieved item

### Critical rule
Memory is not trusted because it exists. Retrieved memory is evidence with provenance and confidence, not authority.

### Holdout
Dedicated Holdout D only.

## 11. Section 5 — Mentor / skill transfer

### Question
Can a frozen weaker model acquire reusable procedural capability from a stronger/peer model’s successful trajectory without weight updates?

### Candidate student/teacher cases
Prefer naturally observed complementary pairs where Student A failed and Model B succeeded on matched tasks.

### Primary conditions
- M0: no help
- M1: ordinary retry
- M2: student failure diagnosis
- M3: teacher final answer only
- M4: teacher successful trajectory
- M5: contrastive student-failure vs teacher-success missing-skill patch
- M6: previously verified stored skill from another related task

### Required transfer criterion
Fixing the original failure is insufficient. A skill counts as learned only if it improves fresh related tasks without unacceptable regression or catastrophic increase.

### Skill lifecycle
```text
candidate skill
   -> replay original failure
   -> fresh transfer cases
   -> regression/catastrophic checks
   -> add / modify / merge / reject
```

Every skill version must preserve provenance, originating failure(s), teacher trajectory reference, student trajectory reference, validation history, and retirement/rejection reason.

### Holdout
Dedicated Holdout E only.

## 12. Section 6 — Integrated adaptive controller

### Question
After Sections 1–5 identify individually useful mechanisms, does an integrated evidence-state controller outperform simpler architectures on a sealed final holdout?

### Only proven components may enter
Section 6 may combine only mechanisms that earned causal support in earlier sections or are included as explicit negative/ablation controls.

### Candidate actions
- execute
- deterministic verify
- semantic verify
- acquire evidence
- retrieve edge case
- retrieve proven skill
- retry
- regenerate
- targeted repair
- switch model
- ask mentor
- rollback
- accept/block/stop

### Primary comparison ladder
1. best single model
2. best fixed stack
3. best static role-specialized stack
4. adaptive controller
5. adaptive + proven memory mechanism
6. adaptive + proven mentor/skill mechanism
7. oracle ceiling for analysis only

### Final holdout
Holdout F is sealed from all prior section tuning and may only be opened by the frozen Section-6 preregistration.

## 13. Task design

Test-3 tasks should contain causal twins and adversarial contrasts, not only random benchmark samples.

Required challenge classes should include:
1. representation failure
2. missing requirement
3. ordering failure
4. wrong value
5. unintended side effect
6. deterministic pass / semantic fail
7. semantic plausibility / deterministic fail
8. verifier false reject
9. verifier false accept
10. correlated model failure
11. complementary model success
12. stale/misleading memory
13. relevant edge-case memory
14. irrelevant edge-case memory
15. useful mentor
16. misleading mentor
17. teacher solution outside student capability
18. budget-pressure decisions
19. cases where retry/do-nothing is optimal
20. cases where acquiring information is better than acting

Causal twins should differ by the smallest possible feature needed to force a different optimal route.

## 14. Negative controls

The campaign must test whether apparent intelligence is merely extra compute/context.

Required controls include, where applicable:
- random model switch
- random verifier
- random edge-case retrieval
- irrelevant edge case
- irrelevant skill
- random extra model call
- random retry
- teacher answer without skill extraction
- equal-token control
- equal-physical-call control

If intelligent routing/memory/mentoring cannot beat these controls, the claimed mechanism is not supported.

## 15. Evidence-state controller model

The controller is conceptually:

```text
Evidence State E_t
       |
       v
Policy pi(E_t)
       |
       v
Action A_t
       |
       v
Observation
       |
       v
Verification
       |
       v
Evidence State E_(t+1)
```

The controller may be deterministic, learned from replay data, rule-based, model-assisted, or hybrid depending on the section. The experiment must distinguish controller implementation from the causal hypothesis being tested.

## 16. Information-acquisition accounting

When the controller chooses to gather evidence before acting, the experiment records:
- evidence requested
- acquisition cost
- evidence returned
- whether the evidence changed the selected action
- whether the changed action improved outcome
- expected vs realized value of information where estimable

This allows the experiment to test whether the governing bottleneck is reasoning or knowing when more information is required.

## 17. Canonical per-transition telemetry

Every transition should preserve, when available:

```text
state_before
action_selected
alternative_actions_considered
selection_scores
selection_reason

model
role
prompt
response
model_digest
context/settings

verifier_type
verifier_input
verifier_output
verifier_decision
verifier_confidence/evidence

retrieved_edge_cases
retrieval_scores
retrieval_provenance
realized_retrieval_value

mentor
student
student_failure_trajectory
teacher_success_trajectory
candidate_skill
skill_version
skill_validation_history

state_after
deterministic_result
semantic_result
hidden_gold_result
catastrophic_result
blocked/allowed

physical_calls
logical_calls
cache_hits
tokens
latency
elapsed_time
budget_remaining

counterfactual_status
provenance
integrity_hashes
```

Missing fields must be explicit, not silently omitted when their absence matters.

## 18. Standard evidence packet per section

Each section must produce at least:

```text
preregistration.json
config.json
provenance.json
model_calls.jsonl
events.jsonl
trials.csv
validator_results.csv
failures.csv
wins.csv
losses.csv
transitions.csv
counterfactuals.csv
costs.csv
latency.csv
tokens.csv
cache.csv
failure_atlas.json
effect_sizes.json
verdict.json
report.txt
SHA256SUMS.csv
COMPLETE-EVIDENCE.txt
```

Section-specific files are additive. Existing Test-1/Test-2 evidence contracts should be reused where compatible rather than replaced.

## 19. Section-to-section progression

Each section follows:

```text
preregister
   -> run bounded section
   -> collect complete evidence
   -> forensic analysis
   -> adversarial review
   -> identify unexplained residual
   -> GitHub/model-free counterfactual search
   -> draft next section preregistration
```

Later sections are allowed to change based on earlier evidence, but only **before** the later section is preregistered and before its first Tier-A call.

This is the mechanism that keeps the campaign adaptive without making any individual experiment outcome-dependent.

## 20. Discovery interpretation matrix

The campaign should explicitly map outcomes to structural conclusions:

- Adaptive >> fixed: universal topology is not the governing principle.
- Verified memory >> adaptive alone: persistent verified experience is a major capability layer.
- Mentor skill transfer >> memory: frozen models can acquire reusable procedural capability externally.
- Evidence acquisition >> extra attempts: knowing what to learn next is a major bottleneck.
- Verification strategy >> routing: epistemic control dominates model routing.
- Random extra compute ~= intelligent policy: apparent architecture gain is mostly test-time scaling.
- Teacher helps original case but not fresh transfer: mentoring is memorization, not learning.
- Stale/wrong memory creates significant failures: memory authority/trust becomes a primary research problem.
- All system arms ~= one another while oracle remains high: controller state representation is inadequate.
- All tested arms ~= oracle: remaining performance is near the measured capability ceiling for this task distribution.

## 21. Implementation boundaries

This design does **not** authorize implementation or inference yet.

Implementation must:
- preserve Test-1/Test-2 evidence unchanged
- branch from the verified Test-2 base
- use tests first for new experiment contracts
- keep model-free discovery separate from Tier-A evidence
- introduce section-specific preregistration gates
- make accidental cross-section holdout reuse impossible or immediately detectable
- prevent hidden-gold/controller leakage
- prevent physical-call budget overruns
- retain complete failure/evidence telemetry

## 22. Success criterion for Test-3 as a research campaign

Test-3 succeeds scientifically even if no proposed architecture wins.

The campaign is successful if it materially narrows the set of plausible governing principles and produces reusable causal evidence about:
- what state matters
- what action should follow a failure
- which verifier is useful when
- whether information acquisition is worth its cost
- whether verified experience transfers
- whether mentoring produces generalizable external learning
- how close the system is to an oracle routing ceiling

The desired end state is not merely a higher benchmark score.

It is a defensible answer to:

> What actually controls reliable performance in a frozen-model agent system, and what evidence should determine the next operation?
