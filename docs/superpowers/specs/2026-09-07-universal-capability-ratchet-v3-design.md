# Universal Capability Ratchet V3 — Failure-to-Mechanism Intervention Tomography

## Status

Owner-approved experiment architecture. Design only. This document does **not** authorize implementation or real inference.

V3 is the direct continuation of the Universal Adaptive Model Operating-Surface Tuner V2. It preserves V2's validated experimental chassis and changes the scientific target from local inference-profile optimization to **causal capability expansion**.

The project objective is not another leaderboard, another broad architecture comparison, or another fixed prompt search. V3 must turn expensive model failures into reusable experimental assets, identify what actually repairs them, determine who should own each repair, and ratchet successful repairs into durable system capability.

---

## 1. Primary objective

For every important Qwen capability boundary:

> **What is the smallest causal intervention that converts the same observable failure state into verified success, why does it work, where does it stop working, and can the resulting mechanism be compiled into a deterministic rule, prompt/context policy, reasoning profile, tool policy, skill, verifier, recovery rule, fine-tuning candidate, escalation rule, or safe-stop boundary?**

Every physical model call must answer a named decision that can alter architecture, model operating policy, prompt/context policy, tool use, skill use, verification/recovery, fine-tuning strategy, routing, or the verified capability frontier.

The unit of progress is not average score. The unit of progress is **new verified territory plus a reusable explanation for how it became solvable**.

---

## 2. Why V3 exists

V2 proved that the reusable experiment engine works and produced 3,960 atomic observations from 1,260 physical calls, but it also exposed the next frontier.

Key V2 findings that constrain V3:

- reasoning can materially improve some families and materially harm others;
- arithmetic moved from 61.7% direct to 89.2% under the 2048-token diagnostic, a +27.5 percentage-point frontier movement;
- strict transformation, planning, and ambiguity showed meaningful reasoning/support signals;
- logic, governance, and synthesis showed negative transfer from additional reasoning;
- coding remained weak even after more reasoning, indicating that a different mechanism may be required;
- semantic correctness and contract correctness must remain separate;
- fresh holdouts can reverse apparently obvious gate conclusions;
- most thinking calls hit configured reasoning limits, so task-specific reasoning depth is real;
- V2 incorrectly required a candidate to reach the 90% deployment floor before allowing deeper tuning, preventing promising sub-90% frontier movement from receiving parameter characterization;
- adaptive scheduling eliminated large amounts of unnecessary work and therefore earned permanent inclusion.

Broader project evidence additionally establishes that model response surfaces are task/state dependent, support can reverse sign, more context is not monotonically better, richer observable state can help routing, deterministic verification/recovery can outperform repeated model retries, and large bundled architectures do not earn promotion merely by existing.

V3 therefore moves from **"which setting scores better?"** to **"what causal mechanism repairs this exact failure and should own the responsibility permanently?"**

---

## 3. Non-negotiable laws

1. **Existing evidence first.** No fresh call may answer a question already resolved by valid historical evidence.
2. **Failure is preserved, never overwritten.** A successful retry cannot replace the original failed trajectory.
3. **Same-state causal comparison.** Where possible, competing repairs branch from the same immutable parent failure snapshot.
4. **No blind retries.** Every replay must be either a preregistered reproducibility probe, a causal intervention, a sequence step, or an explicit recovery treatment.
5. **Movement earns investigation; certification earns deployment.** A material frontier shift may advance even below the final deployment floor.
6. **Model cognition and system responsibility remain separate.** State, authority, execution permission, transaction truth, hard invariants, and final verification remain system-owned where deterministically possible.
7. **Semantic and contract outcomes remain separate.** Formatting failure must not be misdiagnosed as missing cognition.
8. **Every mechanism pays complexity rent.** A mechanism survives only if removing it loses verified capability, reliability, safety, or material efficiency.
9. **Fresh and sealed evidence are protected.** Development cannot consume or mutate final confirmation cases.
10. **Observable evidence only.** Capture exposed reasoning/thinking fields and state transitions, but never depend on inaccessible private chain-of-thought.
11. **Negative evidence must change something.** A failed branch must narrow a mechanism, routing rule, ownership boundary, recovery policy, training eligibility, or capability boundary.
12. **No false precision.** Plateaus remain plateaus. Timing noise cannot select a cognitive optimum.
13. **No global winner is required.** Different task/failure/state regions may require different interventions.
14. **Data collection is cheap; retesting is not.** Capture every safe observable datum that can support future causal analysis.
15. **The campaign does not stop because Qwen fails.** Model failure becomes evidence and the scheduler continues. Only evidence-integrity, provenance, infrastructure, or hard-ceiling violations may invalidate/stop affected execution.
16. **Every failure enters the canonical replay registry.** From V3 onward, every model/system failure and every snapshot/replay descendant must be represented in the append-only `TEST_REPLAY.jsonl` registry so the exact failure state can be immediately replayed against the model that failed or any compatible alternate model without reconstructing the original campaign.

---

## 4. Preserve the V2 chassis

V3 reuses the V2 universal experimental infrastructure rather than replacing it:

- deterministic task generators and frozen task pools;
- immutable manifests, hashes, seeds, model/runtime provenance;
- exact raw request/response envelopes;
- append-only normalized observations;
- deterministic/oracle-first scoring;
- semantic, contract, completion, and efficiency axes;
- paired comparisons on matched tasks/states;
- clustered deterministic bootstrap and preregistered confidence thresholds;
- evidence checkpoints such as 40/60/80/120 atomic outcomes where that geometry is appropriate;
- adaptive loser elimination without premature winner certification;
- fresh holdout certification;
- hard physical-call ceiling computed before launch;
- resumable execution without duplicate completed trials;
- one persistent progress/ETA view;
- scheduler reason attached to every physical call;
- raw evidence retained even if a later scorer is found defective.

V3 extends the generic engine with failure snapshots, parent/child replay lineage, intervention graphs, causal hypotheses, mechanism promotion states, replay fixtures, mutation families, and architecture/training dispositions.

---

## 5. Named decisions

Every scheduled call must point to at least one unresolved `decision_id`.

### D1 — Failure cause
What is the earliest observable divergence and best supported causal explanation for this failure?

### D2 — Responsibility owner
Should the repair belong to `MODEL`, `SYSTEM`, `TOOL`, `SKILL`, `VERIFIER`, `RECOVERY`, `ROUTER`, `FINE_TUNE`, `ESCALATION`, or `SAFE_STOP`?

### D3 — Reasoning requirement
Does additional reasoning help this state, what budget region is useful, what temperature region is robust, and where does extra reasoning become harmful?

### D4 — Prompt/context requirement
Can wording, state, evidence, dependency, invariant, authority, uncertainty, or other information operators repair the failure?

### D5 — Representation/delivery requirement
Does the same semantic information behave differently as prose, fields, ledger, matrix, graph, list, compact summary, or progressive delivery; and does timing/placement/order/repetition matter?

### D6 — Tool requirement
Can external computation/search/execution move the boundary, and is the remaining problem tool selection, argument generation, result interpretation, or recovery?

### D7 — Skill/policy requirement
Can a reusable procedure solve the recurring region without modifying model weights?

### D8 — Verification/recovery requirement
Can deterministic detection plus targeted repair convert the failure more reliably/cheaply than additional cognition?

### D9 — Interaction/sequence requirement
Do interventions enable, suppress, replace, recur, re-anchor, or become useful only after another state transition?

### D10 — Routing requirement
Which observable pre-decision features predict the cheapest successful intervention without hidden family/oracle labels?

### D11 — Fine-tuning qualification
Does a recurring residual represent a genuine model-internal deficit after prompt/context/tool/skill/verifier alternatives are tested, and would weight adaptation reduce recurring external complexity?

### D12 — Capability compilation
Can the discovered repair be generalized and converted into durable cheaper capability without regression?

A call is forbidden if no possible result can change at least one active decision.

---

## 6. Failure Snapshot Protocol

### 6.1 Trigger

A `failure_snapshot` is created whenever an atomic model/system attempt produces any material failure, including:

- semantic incorrectness;
- contract/schema failure;
- completion/truncation/empty answer;
- reasoning-cap exhaustion;
- verifier rejection;
- tool-selection or tool-result interpretation error;
- invalid candidate action;
- preservation/state/dependency violation;
- authority/scope error;
- evidence misuse or unsupported claim;
- repeated/no-progress behavior;
- recovery failure;
- negative-transfer event;
- novel or unclassified failure.

### 6.2 Immutable parent

The original failed attempt is immutable and receives a stable `failure_snapshot_id`. No successful replay may alter, replace, normalize away, or relabel the original raw evidence.

### 6.3 Mandatory snapshot payload

Capture every safely observable field relevant to reconstructing the failure:

- campaign/run/trial/case IDs;
- model ID, digest, provider/runtime/version;
- exact inference profile and seed;
- task and structural descriptors;
- exact system/user/tool messages and rendered bytes/hashes;
- semantic ingredient IDs, representation, dose, order, placement, timing, recurrence, and trigger;
- cumulative context bytes/tokens and critical-information positions;
- canonical observable system state before the call;
- model-visible state separately from system-known state;
- parent transcript/state hashes;
- exposed thinking/reasoning fields or streams when available;
- thinking cap, natural-stop status, completion reason, and token position;
- intermediate/final model outputs;
- available tools/actions, selected tool/action, rejected alternatives when observable;
- exact tool requests/results/parser products;
- candidate answer/action;
- semantic and subcomponent scores;
- contract score/failure;
- verifier result and postcondition result;
- first observable divergence classification;
- failure taxonomy and confidence;
- latency, prompt/eval/output/thinking tokens, load state, and relevant runtime telemetry;
- scheduler reason and unresolved decision target;
- eligible-but-not-fired interventions where causally useful;
- operator/manual intervention affecting comparability.

Do not persist credentials, secrets, unrelated private machine data, or inaccessible hidden chain-of-thought.

### 6.4 Failure tree

Every replay branch has:

- `parent_failure_snapshot_id`;
- `parent_state_hash`;
- `counterfactual_group_id`;
- `intervention_id`;
- `hypothesis_id`;
- one or more changed dimensions;
- explicit expected causal implication;
- child outcome;
- child snapshot if the replay also fails.

A failure can therefore become the root of a durable causal tree rather than a discarded bad answer.

### 6.5 Immediate replay registration

Snapshot creation is not complete until the failure has an append-only `FAILURE_FIXTURE` record in `TEST_REPLAY.jsonl`. The registry write must occur before optional derived analysis. If the registry cannot safely persist the fixture, the failure evidence remains incomplete and additional expensive model calls stop until replay capture is restored.

---

## 7. Failure Autopsy and hypothesis generation

After a snapshot is frozen, Inverted analyzes the observable trajectory and identifies the earliest meaningful divergence that can be supported by evidence.

Candidate causal classes include:

- insufficient reasoning depth;
- reasoning drift/overthinking;
- missing or poorly represented state;
- missing prerequisite/dependency;
- evidence insufficiency, staleness, contradiction, or provenance confusion;
- authority/scope misunderstanding;
- objective/constraint ambiguity;
- action-space confusion;
- critical information lost by context position/pressure;
- contract/interface failure independent of cognition;
- missing deterministic computation;
- missing tool capability;
- wrong tool selection;
- incorrect tool arguments;
- correct tool use but bad result interpretation;
- missing verifier feedback;
- recovery-policy failure;
- reusable procedural/skill deficit;
- model capability limit;
- unknown/novel failure.

For each hypothesis, the autopsy produces one or more interventions designed to distinguish that hypothesis from plausible alternatives. Generic "try again" branches are forbidden.

---

## 8. Intervention registry

Interventions are independent, composable experimental objects.

### 8.1 Prompt interventions

Examples: objective clarification, constraint emphasis, decomposition request, counterexample, ask-before-answer, uncertainty declaration, verification-oriented request, alternatives request, failure warning, minimal restatement.

### 8.2 Information/context ingredients

Examples: canonical state, state delta, prerequisites, dependency graph, evidence sufficiency/provenance/freshness, authority/scope, invariants, admissible/forbidden actions, reversibility/consequence, prior verified state, prior failure, recovery frontier, alternatives, success/failure criteria.

### 8.3 Representation interventions

Semantically equivalent information may be rendered as prose, typed fields, ordered list, ledger, decision table, dependency matrix, graph-like structure, compact summary, explicit alternatives, or another registered representation.

Representation-only contrasts must preserve the semantic contract. If payload meaning changes, the comparison is no longer representation-only.

### 8.4 Delivery interventions

- upfront;
- pre-decision;
- just-in-time;
- progressive after an observable state transition;
- verifier-triggered;
- failure-triggered;
- exact repeat;
- refreshed repeat from current state;
- compressed re-anchor;
- order reversal;
- recurrence such as `A -> B -> A`.

### 8.5 Cognition interventions

Direct versus bounded thinking, reasoning-budget boundaries, temperature regions, and other model-supported inference parameters. V3 continues the unfinished V2 budget/temperature work only inside regions where reasoning has demonstrated frontier movement or remains a live causal explanation.

### 8.6 Deterministic interventions

Formatters, calculators, parsers, state transforms, action pruning, invariant checks, deterministic evidence selection, and other mechanisms that can remove a model-owned responsibility.

### 8.7 Tool interventions

Tool-result supplied, correct tool forced, tool menu with autonomous selection, tool execution, result interpretation, verifier around tool use, malformed tool result, tool failure, tool unavailable, and recovery from tool failure.

### 8.8 Skill/policy interventions

Reusable skill objects containing trigger, observable state, procedure, evidence requirements, allowed tools, decision rules, verification, stop condition, known negative-transfer boundary, and version/provenance.

### 8.9 Verification/recovery interventions

Deterministic detection, critique limited to observable verifier feedback, targeted correction, alternate action, rollback/compensation proposal, safe stop, and escalation. Detection, diagnosis, authorization, execution, and final verification remain separable.

### 8.10 Escalation interventions

A stronger model may be used as an experimental reference/mentor only when the decision is whether Qwen has reached a model-internal boundary or whether a stronger solution can be distilled into cheaper reusable structure. Stronger-model success is not itself a Qwen failure criterion.

---

## 9. Two replay modes

### 9.1 Exact replay

Purpose: measure reproducibility/stochasticity or run the exact failure fixture against another model.

Preserve the model-visible task/state, prompt/messages, tool schema/results, inference profile, and seed where supported. For same-model replay, exact compatible parameters are required. For cross-model replay, the fixture remains exact while unsupported model-specific parameters are translated by an explicit adapter record; this is labeled `CROSS_MODEL_REPLAY`, not same-model exact reproducibility.

Exact replay may not be interpreted as an intervention gain.

### 9.2 Counterfactual replay

Purpose: identify a causal repair.

Start from the same frozen parent state and intentionally modify one registered dimension, or a preregistered combination when the hypothesis requires interaction testing.

Exact and counterfactual replay evidence must remain analytically distinct.

---

## 10. Failure Replay Laboratory

A high-value failure becomes a local matched experiment rather than a single retry.

Example geometry:

```text
ORIGINAL FAILURE S0
├── S0 + prompt clarification
├── S0 + dependency representation
├── S0 + thinking budget
├── S0 + deterministic computation
├── S0 + tool
├── S0 + skill
├── S0 + verifier feedback
└── S0 + targeted compound intervention
```

The scheduler does not exhaustively test all branches. It selects treatments capable of distinguishing the current causal hypotheses, preserves protected exploration for surprising alternatives, and eliminates branches when additional evidence cannot change a decision.

When progressive state is part of the hypothesis, the system may freeze a parent transcript and fork matched child continuations from the same recorded state.

Every replay request and every replay result is appended to the same canonical `TEST_REPLAY.jsonl` group under the originating `failure_snapshot_id`, allowing the full micro-experiment to be selected and rerun as one fixture family.

---

## 11. Corrected advancement gates

V3 separates discovery from deployment.

### MOVEMENT
A branch earns deeper investigation when evidence supports one or more of:

- meaningful semantic uplift;
- conversion of a previously unsolved structural difficulty level;
- elimination of a high-consequence failure;
- meaningful completion/contract improvement when the failure belongs to that layer;
- material reduction in model calls/tokens/latency/architecture burden while preserving capability;
- credible interaction/enabling/recovery signal that changes ownership or next test.

A candidate does **not** need to cross the final deployment floor to earn MOVEMENT.

### TIER_CANDIDATE
A mechanism demonstrates repeatable causal value beyond a single instance/local artifact and merits neighboring/generalization testing.

### CERTIFIED
A mechanism satisfies the applicable fresh/sealed, regression, reliability, hard-invariant, and complexity-rent requirements for production promotion.

The default 90% semantic deployment floor remains a certification criterion where appropriate, not a discovery advancement gate.

---

## 12. V3 campaign stages

### Stage 0 — Historical Evidence Compiler — zero fresh inference

Consume valid historical evidence from Test 1, valid/diagnostic Test 2 portions, Test 3, Harvest A/B/C/D, HD-NEXT evidence, V1 tuner audit, and the completed V2 dump.

Build a queryable `Failure & Capability Atlas` containing known successes, failures, negative-transfer regions, saturated regions, known reasoning effects, historical intervention outcomes, unresolved decisions, and candidate ownership boundaries.

Every possible V3 question is classified as `ANSWERED`, `PARTIALLY_ANSWERED`, `OBSERVATIONAL_ONLY`, `CONTRADICTED`, `REQUIRES_FRESH_INTERVENTION`, `UNANSWERABLE_FROM_EXISTING_DATA`, `NOT_DECISION_RELEVANT`, or `DEFER` before new calls are authorized.

### Stage 1 — Frontier Case Selection and Snapshot Seeding

Seed the replay corpus from historical raw evidence where reconstruction is sufficiently complete. Every historical failure admitted for V3 replay must be normalized into the canonical `TEST_REPLAY.jsonl` fixture schema before it can be scheduled.

Select high-information non-saturated cases, especially:

- arithmetic;
- strict transformation;
- planning/dependencies;
- ambiguity/uncertainty;
- coding;
- `GLOBAL_INTERACTION`;
- `TRANSACTION`;
- `VERIFIER_ORACLE`;
- policy ordering;
- state preservation;
- structural dependency/recovery;
- evidence trust;
- authority/scope.

Classification, debugging, tool-agent decisions, extraction, logic, governance, and synthesis remain valuable as controls, regressions, and negative-transfer regions rather than receiving equal search budget by default.

### Stage 2 — Reproducibility and First-Divergence Calibration

Use limited exact replay only where necessary to distinguish stochasticity from stable failure. Estimate the local noise floor before interpreting small deltas.

No broad replication campaign is allowed when historical reproducibility evidence is already sufficient for the decision.

### Stage 3 — Failure-to-Success Intervention Tournament

For each selected failure snapshot, construct the smallest set of competing interventions capable of distinguishing live causal hypotheses. Compare against the same parent failure state.

The primary output is not a winner label. It is an updated causal/ownership map.

### Stage 4 — Mechanism Localization and Ablation

Successful compound repairs are attacked with matched removals and shams. Examples:

- A;
- B;
- C;
- A+B;
- A+C;
- B+C;
- A+B+C;
- sham-A+B+C;
- order reversals;
- recurrence where justified.

Classify each component as `REQUIRED`, `CONDITIONAL`, `ENABLER`, `SYNERGIST`, `SUPPRESSOR`, `REPLACEMENT`, `RECURRENT`, `REANCHOR`, `RECOVERY_ONLY`, `REDUNDANT`, `HARMFUL`, or `UNRESOLVED`.

### Stage 5 — Operating-Surface Deepening

Only mechanisms that earned movement or remain decision-critical receive deeper characterization of:

- true dose;
- reasoning budget;
- temperature region;
- representation;
- order;
- recurrence;
- timing;
- placement;
- context position/useful-token ratio;
- static versus progressive delivery;
- failure-/verifier-triggered delivery.

This stage explicitly completes the useful V2 budget/temperature work without allowing parameter tuning to consume the entire campaign.

### Stage 6 — Failure Mutation and Neighborhood Generalization

For a repaired snapshot, generate deterministic nearby variants that preserve the causal structure while varying surface details or difficulty:

- numbers/names/entities;
- dependency depth;
- requirement count;
- action-space size;
- critical-information position;
- distractors;
- missing/contradictory evidence;
- authority state;
- reversibility/consequence;
- tool availability;
- context pressure;
- order;
- recovery opportunity.

Classify successful repairs as:

- `INSTANCE_PATCH`;
- `LOCAL_MECHANISM`;
- `REGION_MECHANISM`;
- `CROSS_REGION_MECHANISM`;
- `PROMOTION_CANDIDATE`.

Generated mutation fixtures are also appended to `TEST_REPLAY.jsonl` with lineage to the original failure and a flag distinguishing synthetic neighborhood mutation from naturally observed failure.

### Stage 7 — Tool / Skill / Verification / Recovery Tomography

Where residual failures justify it, distinguish:

- missing capability from missing tool;
- tool selection from tool use;
- tool argument generation from result interpretation;
- generation failure from missing verifier feedback;
- verifier-detectable errors from model-internal capability limits;
- reusable procedural deficit from one-off prompt sensitivity;
- recovery value from repeated generic retries.

A third blind checked retry is not admitted merely because a second attempt failed; historical evidence already shows sharply diminishing return from repeated retries.

### Stage 8 — Capability Compilation

Every generalized repair is evaluated for the cheapest durable owner in this order unless evidence requires otherwise:

1. deterministic system rule/transform;
2. state/evidence representation;
3. formatter/parser/validator;
4. tool policy;
5. reusable skill/policy;
6. task-conditioned reasoning policy;
7. verifier/recovery policy;
8. fine-tuning candidate;
9. stronger-model escalation;
10. safe-stop/hard boundary.

Compilation must preserve source evidence, trigger conditions, negative-transfer boundary, and rollback/version information.

### Stage 9 — Fine-Tuning Qualification and Optional Controlled Lane

Fine-tuning is considered only for recurring residuals that remain model-internal after cheaper external interventions are tested.

The evidence store must be able to emit training candidates containing:

- pre-failure observable state;
- failed response;
- failure taxonomy;
- causal correction;
- successful trajectory;
- failed intervention negatives;
- mechanism label;
- structural descriptors;
- tool/context state;
- training eligibility and contamination lineage.

If a compatible local fine-tuning adapter/harness is explicitly enabled in the implementation, the evaluation arms are:

- base Qwen;
- base Qwen + best external mechanism;
- tuned Qwen;
- tuned Qwen + best external mechanism.

Training, development, fresh evaluation, and sealed evaluation partitions must be structurally separated. A tuned model earns promotion only through fresh capability expansion or verified complexity removal without regression.

If no approved training adapter is available, Stage 9 ends with a qualified immutable training corpus and decision record rather than blocking V3 completion.

### Stage 10 — Conditional Controller Extraction

After enough operating-surface evidence exists, derive a small deterministic controller from observable state only.

Allowed routing outputs include:

- `DIRECT`;
- `THINK`;
- `ADD_CONTEXT`;
- `USE_SKILL`;
- `USE_TOOL`;
- `VERIFY`;
- `RECOVER`;
- `ESCALATE`;
- `SAFE_STOP`.

Candidate observable routing features include dependency depth, evidence sufficiency, contradiction, authority uncertainty, constraint count, action-space size, tool eligibility, verifier failure, preservation risk, ambiguity, context pressure, prior failure state, and reasoning exhaustion.

Hidden family labels and oracle answers are forbidden as production router inputs.

Measure routing regret against the best experimentally established intervention available for each case/state.

### Stage 11 — Fresh Transfer, Regression, and Sealed Confirmation

Freeze mechanisms, controller rules, thresholds, representations, prompts, and model profiles before fresh evaluation.

Fresh evaluation tests neighboring and structurally different untouched cases. Sealed confirmation begins only after fresh results justify it and cannot be used for further tuning.

Regression must include regions already solved by direct Qwen and regions where extra reasoning/support has shown negative transfer.

No mechanism can be promoted if it expands one region by silently damaging protected existing territory beyond its preregistered regression tolerance.

Fresh/sealed failures are still captured into `TEST_REPLAY.jsonl`, but their partition labels remain immutable and those entries cannot be fed back into development until the corresponding confirmation phase is formally closed.

---

## 13. Permanent Failure Snapshot Corpus

V3 creates a versioned `Failure Snapshot Corpus` as a first-class project asset.

Logical structure:

```text
failure_snapshot/
├── immutable_parent_state
├── original_attempt
├── failure_taxonomy
├── first_divergence
├── causal_hypotheses
├── replay_branches
├── successful_repairs
├── failed_repairs
├── negative_transfer
├── mutation_family
├── mechanism_extracted
├── generalization_results
├── training_eligibility
└── promotion_status
```

Snapshots are reusable experimental fixtures for later mechanisms. A future mechanism can be evaluated against selected historical real failures without rebuilding the original campaign, provided the stored state is sufficient to reproduce the model-visible condition and the analysis clearly distinguishes historical replay from fresh independent confirmation.

A snapshot fixture never becomes "fresh" merely because a new intervention is tested on it.

### 13.1 Canonical `TEST_REPLAY.jsonl`

All failure and replay fixtures are kept together in one append-only canonical replay registry: `TEST_REPLAY.jsonl`.

This file exists for **fast exact retesting**. A future harness must be able to select one fixture, one failure family, one model's failures, one mechanism class, or the entire registry without reopening the original campaign evidence layout.

Each logical failure group contains records such as:

- `FAILURE_FIXTURE` — the immutable original failure;
- `REPLAY_REQUEST` — a registered exact/counterfactual/cross-model replay definition;
- `REPLAY_RESULT` — the observed replay outcome;
- `MUTATION_FIXTURE` — a causally linked neighborhood variant;
- `MECHANISM_LABEL` — current causal/ownership classification;
- `PROMOTION_EVENT` — movement/generalization/promotion disposition changes.

Every `FAILURE_FIXTURE` must include enough **model-visible replay material** to reproduce the request without reconstructing the parent campaign: exact messages/context, tool schemas and model-visible tool results, relevant observable state, inference parameters, seed where supported, scoring/oracle reference, expected contract, model/runtime provenance, hashes, and partition/contamination labels.

Large non-model-visible forensic payloads may remain content-addressed in the raw evidence store and be referenced by immutable hash/path. Any payload that was actually visible to the model and is required for exact replay must either be embedded in the fixture or referenced through a content-addressed replay asset whose hash is verified before launch.

The registry must support:

- **same-model exact replay** — reproduce the failure as closely as the runtime permits;
- **same-model intervention replay** — alter only registered dimensions;
- **cross-model replay** — give another compatible model the same model-visible failure fixture, with adapter changes explicitly recorded;
- **batch replay** — select all failures by source model, family, failure class, mechanism, difficulty, date/campaign, or promotion state;
- **replay diffing** — compare outputs, tool behavior, reasoning usage, latency/tokens, and verifier outcomes across models/interventions;
- **zero-rerun research** — inspect prior replay trees and outcomes without inference when the stored evidence already answers the question.

`TEST_REPLAY.jsonl` is the canonical replay registry. Separate snapshot/branch files may be generated as indexes or analysis views, but they may not become independent competing sources of truth.

No registry row is deleted or rewritten after commitment. Corrections are appended as versioned superseding records with lineage to the original record.

---

## 14. Evidence schema additions

Every material observation/replay should carry, where applicable:

- `decision_id`;
- `hypothesis_id`;
- `mechanism_id`;
- `intervention_id`;
- `failure_snapshot_id`;
- `parent_failure_snapshot_id`;
- `counterfactual_group_id`;
- `parent_state_hash`;
- `first_divergence_class`;
- `architecture_owner_candidate`;
- `routing_feature_vector`;
- `negative_transfer_signature`;
- `skill_candidate_id`;
- `fine_tune_candidate_id`;
- `promotion_state`;
- `scheduler_selection_reason`;
- `expected_information_value`;
- `protected_exploration`;
- `admissible_unexplored_neighbors`;
- `replay_record_type`;
- `source_model_id`;
- `target_model_id`;
- `replay_mode`;
- `replay_compatibility_adapter`;
- `fixture_hash`;
- `replay_asset_hashes`;
- full raw lineage to request/response/tool/state evidence.

Derived conclusions may never replace raw events.

---

## 15. Required output metrics

V3 preserves accuracy/reliability/latency/tokens, but the primary project metrics become:

### Frontier Shift
Movement in structural/difficulty territory that becomes verified solvable.

### Failure Conversion Rate
Fraction of selected prior failures converted into verified success under an identified intervention.

### Causal Mechanism Yield
Fraction of investigated failure clusters that produce a falsifiable, supported repair mechanism rather than an unexplained winner.

### Compilation Yield
Fraction of generalized repairs converted into durable rules, tools, skills, reasoning policies, verifiers, recovery policies, training candidates, or explicit boundaries.

### Knowledge Reuse Rate
How often a compiled mechanism solves new eligible cases without rediscovery.

### Negative Transfer Rate
How often a mechanism damages cases/regions that did not need it.

### Routing Regret
Observed controller result versus the best known experimentally valid intervention for the same state.

### Fine-Tune Added Value
Fresh capability or complexity reduction attributable to weight adaptation beyond the best external mechanism.

### Substitution Efficiency
Verified capability gained per added architecture/compute burden.

### Capability Regression Rate
Previously verified territory lost after mechanism/controller/tuning changes.

### Failure Corpus Reuse Value
How many later decisions can be answered from preserved snapshots without rerunning the original expensive failure acquisition.

### Replay Portability
How many registered failures can be replayed faithfully across compatible models/runtimes, with incompatibilities explicitly classified rather than silently altered.

---

## 16. Adaptive scheduler policy

The V3 scheduler prioritizes **expected decision value**, not equal coverage or raw uncertainty alone.

Priority rises when a branch can:

- move a known frontier substantially;
- distinguish architecture ownership;
- resolve a high-consequence failure;
- identify a reusable mechanism;
- eliminate a large class of future calls;
- determine whether a tool/skill/fine-tune path is necessary;
- resolve contradictory evidence;
- test a surprising interaction or negative-transfer boundary.

Priority falls when:

- all plausible outcomes lead to the same architecture decision;
- a region is already saturated;
- all candidates are uniformly incapable and no intervention can change ownership;
- evidence has already established the required boundary;
- a proposed branch merely increases sample count without increasing resolution.

Protected exploration remains mandatory for weak/reversed/unusual compound hypotheses, rare structural states, and purple-unicorn failures so exploitation cannot blind the project to new mechanisms.

---

## 17. Statistics and promotion

V3 retains paired evidence and preregistered clustered confidence analysis from V2 where binary/continuous atomic outcomes support it.

The default minimum useful semantic effect remains +5 percentage points for ordinary profile/intervention comparisons unless a domain-specific effect threshold is preregistered.

However, promotion is multi-objective and causal. A candidate may be high value with a smaller mean semantic delta when it:

- removes a catastrophic/high-consequence failure;
- replaces expensive model calls with deterministic behavior;
- converts a structural difficulty tier;
- eliminates a recurring recovery loop;
- materially reduces architecture burden while preserving capability.

Tiny effects inside the calibrated noise floor cannot create a winner.

A successful mechanism must beat an appropriate matched sham/control whenever a sham can falsify the proposed causal explanation.

---

## 18. Architecture disposition contract

Every completed investigated branch must end in one or more explicit dispositions:

- `KEEP`;
- `REMOVE`;
- `ROUTE`;
- `SYSTEM_OWN`;
- `TOOL_OWN`;
- `SKILL_OWN`;
- `THINKING_POLICY`;
- `VERIFY_RECOVER`;
- `FINE_TUNE`;
- `ESCALATE`;
- `SAFE_STOP`;
- `HARD_BOUNDARY`;
- `CONDITIONAL`;
- `DEFER` only when the decision cannot currently be made for a recorded external reason.

`UNRESOLVED` without a reason, boundary, and next decision requirement is not a valid terminal scientific result.

---

## 19. Call geometry and campaign economics

V3 must compute call geometry from the actual number of selected failure fixtures, live hypotheses, intervention costs, progressive-call depth, statistical checkpoints, protected exploration reserve, fresh/holdout requirements, and optional fine-tune evaluation arms.

There is no arbitrary fixed 500/1000-call experiment ceiling inherited from unrelated campaigns.

Before launch the manifest must report:

- minimum valid physical calls;
- expected adaptive physical calls;
- worst-case physical calls;
- per-stage expected/worst-case allocation;
- protected exploration allocation;
- fresh/sealed reserve;
- model-specific call cost, including multi-call thinking/progressive interventions;
- hard abort ceiling.

The ceiling is an integrity guard, not a target. Adaptive pruning should reduce work aggressively when decisions settle.

Wall-clock inconvenience may change scheduling order/residency strategy, but it may not delete high-value scientific coverage.

---

## 20. Completion and failure behavior

A model-level failure never aborts the V3 campaign. It is snapshotted, registered in `TEST_REPLAY.jsonl`, classified, and execution advances.

A replay failure also becomes a child snapshot and a new replay-registry record; it does not trigger unlimited retry.

Affected inference may stop only for validity-threatening conditions such as:

- runtime/provider unavailable beyond the frozen infrastructure policy;
- model identity/digest/provenance mismatch;
- task/manifest/hash corruption;
- evidence-store or `TEST_REPLAY.jsonl` write failure that threatens raw/replay capture;
- scorer/oracle integrity failure for the affected decision;
- hard call ceiling violation.

Resume must preserve campaign, case, snapshot, replay-record, branch, attempt, and intervention identity.

V3 is complete only when:

1. every selected high-value historical/fresh failure has a terminal evidence state;
2. every failure and replay branch is represented in the canonical `TEST_REPLAY.jsonl` registry;
3. every scheduled physical call has raw evidence and a decision reason;
4. every material successful repair has either causal localization/generalization or is explicitly classified `INSTANCE_PATCH`;
5. every negative result changes an ownership/boundary/routing/training decision or is recorded as a falsified hypothesis;
6. every promoted mechanism has fresh evidence and regression results appropriate to its consequence;
7. sealed evidence, if entered, was not used for tuning;
8. all evidence and replay manifests/hashes verify;
9. the failure corpus and replay lineage verify;
10. no architecture claim depends on a hidden oracle label or inaccessible private chain-of-thought;
11. the final capability map states what Qwen can solve direct, with reasoning, with context, with tools, with skills, with verification/recovery, after tuning, only by escalation, or not safely/reliably at all.

---

## 21. Required artifacts

At minimum V3 must emit:

- `protocol-v3-manifest.json`;
- `historical-evidence-atlas.json`;
- **`TEST_REPLAY.jsonl` — canonical append-only source for all failure fixtures, replay definitions/results, mutation fixtures, and replay lineage**;
- `raw-calls.jsonl`;
- `atomic-observations.jsonl`;
- `causal-hypotheses.jsonl`;
- `intervention-registry.json`;
- `mechanism-graph.json`;
- `negative-transfer-map.json`;
- `capability-frontier.json`;
- `routing-dataset.jsonl`;
- `skill-candidates.jsonl`;
- `fine-tune-candidates.jsonl`;
- `compiled-capabilities.json`;
- `fresh-transfer-report.json`;
- `sealed-verdict.json` when sealed confirmation is entered;
- SHA-256 manifests for immutable evidence and replay assets;
- concise human-readable report describing discoveries, causal mechanisms, rejected mechanisms, capability movement, ownership decisions, and next architecture state.

`failure-snapshots.jsonl`, `replay-branches.jsonl`, or other specialized replay tables may be generated as derived/query-optimized views, but `TEST_REPLAY.jsonl` is the replay source of truth and derived views must carry its source hashes/record IDs.

The exact surrounding physical storage layout may be adapted during implementation, but all logical data and lineage above are mandatory.

---

## 22. Synthetic/preflight validation requirements

No real V3 inference may launch until tests prove at least:

1. a failed model response creates an immutable snapshot, appends a valid `FAILURE_FIXTURE` to `TEST_REPLAY.jsonl`, and the campaign continues;
2. successful replay cannot overwrite the original failure;
3. exact replay and counterfactual replay are analytically distinct;
4. child replays retain exact parent/state lineage;
5. multiple intervention forks from one snapshot remain independently reconstructable;
6. only registered changed dimensions differ in one-factor counterfactual tests;
7. compound interventions produce correct ablation/sham geometry;
8. MOVEMENT can advance a strong sub-90% candidate while CERTIFIED still rejects it;
9. negative reasoning effects prevent global always-think routing;
10. tool selection, tool execution, tool interpretation, verifier, and recovery failures are separable;
11. skill candidates preserve trigger/procedure/verifier/negative-transfer metadata;
12. failure mutation preserves causal structure while changing registered surface dimensions;
13. historical snapshots cannot be mislabeled fresh;
14. fresh and sealed partitions cannot leak into development/training;
15. fine-tune candidates retain data lineage and contamination partition labels;
16. hidden oracle/family labels are unavailable to production controller features;
17. adaptive pruning cannot delete mandatory protected exploration/fresh/sealed reserves;
18. raw evidence survives scorer revision unchanged;
19. resume cannot duplicate completed physical calls or replay branches;
20. manifest/model/hash mismatch stops affected inference before contamination;
21. a scorer defect invalidates the derived decision but preserves raw evidence;
22. every call must have a decision reason that is capable of changing an unresolved decision;
23. a synthetic causal mechanism can be recovered from a planted failure state while a sham is rejected;
24. a planted instance-only patch fails neighborhood generalization and is not promoted;
25. a planted negative-transfer mechanism is routed conditionally rather than globally promoted;
26. a deterministic substitute beats unnecessary model reasoning and is assigned system/tool ownership;
27. a genuine model-internal residual is correctly qualified for fine-tuning/escalation rather than falsely assigned to prompt/context;
28. one `TEST_REPLAY.jsonl` fixture can reproduce the same-model request without reading the original campaign directory;
29. the same fixture can be run against another compatible model with all adapter substitutions explicitly recorded;
30. batch selection by source model, failure class, task family, mechanism, and promotion state is deterministic;
31. every replay result links back to exactly one replay request and one originating failure family;
32. replay-registry append/correction semantics never mutate prior committed rows;
33. a replay asset hash mismatch blocks the affected replay before inference.

Template/preflight validation must launch **zero real model calls**.

---

## 23. Explicit non-goals

V3 must not:

- rerun broad RAW-vs-INVERTED architecture contests;
- treat all twelve V2 families equally when evidence says their information value differs;
- tune temperatures before establishing that reasoning is causally relevant;
- promote a mechanism because it is sophisticated or intuitive;
- use generic retries to inflate success;
- collapse failure, repair, and successful outcome into one record;
- maintain competing independent replay stores that can drift from `TEST_REPLAY.jsonl`;
- call a representation change a semantic ingredient change or vice versa;
- infer private chain-of-thought that is not exposed by the runtime;
- assume a stronger model's solution is automatically the correct architecture;
- fine-tune errors caused by missing state, bad prompts, wrong tools, missing verification, or system-owned responsibilities;
- train/evaluate on contaminated snapshot descendants without lineage tracking;
- use historical replay as fresh confirmation;
- build a controller before the intervention surface is sufficiently mapped;
- optimize for minimum architecture before the maximum useful capability frontier is understood;
- spend calls simply because budget remains.

---

## 24. End-state

V3 should leave INVERTED with something materially more valuable than another benchmark report:

```text
REAL FAILURE
  -> IMMUTABLE SNAPSHOT
  -> APPEND TO TEST_REPLAY
  -> FIRST DIVERGENCE
  -> CAUSAL HYPOTHESES
  -> MATCHED REPLAY FORKS
  -> BEST REPAIR + FALSIFICATION
  -> FAILURE MUTATION
  -> NEIGHBOR GENERALIZATION
  -> FRESH GENERALIZATION
  -> REGRESSION
  -> CHEAPEST DURABLE OWNER
  -> COMPILED CAPABILITY
  -> ROUTING / TRAINING / ESCALATION POLICY
  -> PERMANENT CROSS-MODEL REPLAY FIXTURE
  -> MOVED CAPABILITY FRONTIER
```

The defining V3 principle is:

> **A failure is not the end of a test. It is the beginning of a miniature causal research program whose successful result must become reusable capability or a sharper boundary. Every failure is also permanently retained as a fast replay test for the model that failed and for compatible future models.**

V3 succeeds when the project can point to newly solved territory and say not only **that** Qwen/Inverted improved, but **why**, **under what observable conditions**, **which mechanism owns the improvement**, **what it costs**, **where it fails**, **how it can be replayed exactly**, and **how the project can reuse the discovery without paying to rediscover it.**
