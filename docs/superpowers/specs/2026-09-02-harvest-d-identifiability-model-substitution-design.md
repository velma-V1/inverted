# Harvest D — Causal Identifiability, Model Frontier, and Capability Ratchet Design

## Status

APPROVED DESIGN. CONCEPTUAL SCOPE FROZEN.

Base evidence commit: `0d67ba4e5578b4c14225eb83b726fd137dfffecd`.

This design supersedes broad Test 5 architecture-discovery framing but does not delete or rewrite that historical design.

## Mission

Harvest D determines:

1. which responsibilities belong to deterministic architecture versus model cognition;
2. where each tested model's raw capability boundary lies;
3. how far causally supported INVERTED mechanisms move that boundary;
4. when more scaffolding is superior to invoking Qwen;
5. when Qwen should be invoked immediately;
6. how far Qwen + maximum proven INVERTED pushes the local frontier;
7. whether novel Qwen discoveries can be externalized into verified reusable capability that later reduces Qwen/system involvement.

Harvest D is not a general benchmark, provider test, multi-agent experiment, or final production certification.

## Campaign

```text
D0 Evidence Closure + prior frontier mining
 -> D1 Deterministic Trusted-Kernel Identification
 -> D2 Model Capability Frontier
 -> D3 Architecture Substitution + System-Involvement Curves
 -> D4 Qwen Routing / Escalation
 -> D5 Qwen + Maximum INVERTED
 -> D6 Purple-Unicorn Discovery
 -> D6B Capability-Ratchet Validation
 -> D7 Causal Closure / Responsibility Freeze
```

Later stages are conditional on earlier evidence. They are not one monolithic run.

## Optimization law

Harvest D uses a lexicographic objective, not a blended score:

1. hard invariants must pass;
2. maximize semantic correctness;
3. minimize silent/unsafe failure;
4. minimize Qwen dependence where correctness is retained;
5. minimize total model cost;
6. minimize system involvement;
7. minimize latency and implementation complexity.

A cheaper or simpler architecture may not buy its score by violating a higher-priority objective.

## Experimental unit

The unit of correctness is a state transition, not a model response:

`CASE -> STATE -> OBSERVATION -> DECISION -> PROPOSED ACTION -> ADMITTED ACTION -> STATE TRANSITION -> VERIFIED OUTCOME`

Every consequential step has a globally unique identity and records:

- run/case/trial/step IDs;
- model artifact/configuration;
- state hash/version/uncertainty before and after;
- evidence and authority hashes;
- system-involvement vector;
- routing/scaffold decisions;
- unique physical model-call ID;
- token/latency/cost data;
- proposed/admitted/executed action;
- execution receipt;
- oracle/postcondition result;
- divergence/detection/recovery steps;
- knowledge objects used/created.

Duplicate physical model calls never count as independent evidence.

## Evidence hierarchy

From strongest to weakest:

1. executable semantic state oracle;
2. deterministic invariant/postcondition oracle;
3. metamorphic oracle;
4. independently constructed secondary oracle;
5. independent human/model adjudication.

Model-only judgment may create a hypothesis but cannot certify core correctness.

## D0 — Evidence Closure

### Goal

Determine what is already known before spending new model calls.

### Inputs

- Tests 0–3;
- S2 frozen evidence;
- Harvest A/B/C evidence branches;
- stopped/partial/duplicate runs;
- diagnostic Test 2 capability/routing artifacts;
- manifests, hashes, provenance, environment/model metadata.

### Claim states

Every prior claim is classified as:

- `OBSERVED`
- `HYPOTHESIZED`
- `CAUSALLY_VERIFIED`
- `GENERALIZED`
- `PROMOTED`
- `CONTRADICTED`

Test 2 model/routing results are diagnostic priors only because its primary verdict is contaminated by non-unique physical call identity.

### Output

`causal_architecture_readiness_matrix` containing question, evidence, confidence, contradictions, missing discriminator, target D stage, and Test 5 disposition.

### Gate

No real inference until:

- evidence integrity passes;
- duplicate/partial evidence is separated;
- hidden-gold leakage is unresolved nowhere;
- each prior claim has a legal claim class.

## D1 — Deterministic Trusted Kernel

### Goal

Test non-model correctness mechanisms with zero model calls.

Candidate mechanisms:

- canonical state/version ledger;
- durable authorization ledger;
- proof-carrying action envelope;
- preconditions/postconditions;
- invariants;
- consequence/reversibility classification;
- transaction/effect journal;
- fencing/version checks;
- commit boundary;
- system-owned DONE;
- independent recovery authority.

### Transaction crash matrix

Inject at:

- before prepare;
- after prepare before effect;
- during effect;
- after effect before receipt;
- after receipt before verification;
- after verification before state update;
- after state update before commit;
- during commit;
- after commit before response.

Also test timeout with unknown external result, duplicate/lost response, partial effect, compensation failure, non-idempotent retry, replay, restore, fork/merge, and consumed-authority resurrection.

### Hard floor

Zero tolerance for:

- unauthorized irreversible action;
- duplicate committed irreversible effect;
- consumed authorization resurrection;
- silent journal/replay inconsistency;
- known invalid state silently committed.

Allowed outcomes: correct execution, containment, recovery, or explicit UNVERIFIED/SAFE_STOP.

Unknown effect state triggers reconciliation, never blind retry.

## D2 — Model Capability Frontier

### Models

- `SMALL_A`: selected 1–2B model;
- `SMALL_B`: optional 3–4B challenger when useful for transition localization;
- `QWEN`: exact local Qwen3.5 9B artifact.

Qwen model ID, quant, runtime, context, generation settings, template, tool schema, and hardware/runtime configuration are frozen as provenance.

### Capability axes

- semantic interpretation;
- ambiguity resolution;
- decomposition;
- planning;
- candidate generation/ranking;
- tool selection/construction;
- evidence evaluation;
- contradiction handling;
- state reasoning;
- multi-step coherence;
- recovery diagnosis;
- novel problem solving;
- uncertainty recognition.

### Estimation

Use adaptive boundary staircases rather than exhaustive matrices:

1. seed from D0 diagnostic priors;
2. bracket success/failure transition;
3. concentrate trials around transition;
4. repeat only near boundary;
5. freeze boundary under sequential evidence rule.

Capability state is `RELIABLE`, `CONDITIONAL`, `UNSTABLE`, or `FAILS` per model/capability/family.

### Metrics

- raw capability boundary;
- first-divergence map;
- failure-signature map;
- residual model-responsibility map.

## D3 — Architecture Substitution and System Involvement

### Goal

Measure which mechanisms move D2 boundaries and the minimum system involvement required to retain the gain.

Candidate interventions:

- canonical state + minimal relevant context;
- admissible-action generation;
- proof-carrying action;
- ACQUIRE_EVIDENCE / value-of-information;
- adaptive decomposition;
- independent verification;
- recovery supervisor;
- risk-adaptive authority/verification;
- failure-derived known guards.

Each mechanism is first tested as targeted intervention + matched sham + same-state replay. Only causally live mechanisms enter bundle tests.

### Required matched controls

- better context -> token-count-matched irrelevant-context sham;
- better evidence -> equal-size irrelevant/stale-evidence sham;
- decomposition -> same-size arbitrary decomposition control;
- state ledger -> full/compressed-history controls;
- verification -> verification-only and block-only controls;
- recovery -> same-state sham recovery;
- knowledge rule -> rule-disabled exact replay.

### Context/state matrix

Explicitly compare:

- full history;
- compressed history;
- ledger + minimal history;
- ledger + compressed history.

### System-involvement telemetry

Record independently:

- context assistance;
- state assistance;
- decomposition assistance;
- evidence assistance;
- action-space restriction;
- verification assistance;
- recovery assistance;
- routing assistance;
- authority intervention;
- promoted-knowledge use.

Per channel record triggered flag, operations, latency, token delta, model calls added/avoided, and external actions added.

Derived metrics:

`AIR = consequential steps with system intervention / total consequential steps`

`InterventionValue = delta verified semantic outcome / incremental intervention burden`

`MRS(model, region) = lowest scaffold retaining verified correctness and hard invariants`

Mechanism classification: `REQUIRED`, `CONDITIONAL`, `REDUNDANT`, `HARMFUL`, `UNRESOLVED`.

## D4 — Qwen Routing

### Goal

Derive when to stay small, add scaffolding, invoke Qwen, invoke Qwen+max, investigate novelty, acquire evidence, or safely stop.

Routing modes:

- `ROUTINE_LOCAL`
- `SCAFFOLDED_LOCAL`
- `QWEN_STANDARD`
- `QWEN_MAX`
- `NOVELTY_INVESTIGATION`
- `ACQUIRE_EVIDENCE`
- `SAFE_STOP`

Allowed decision-time features:

- ambiguity;
- semantic novelty;
- dependency depth;
- planning horizon;
- evidence sufficiency/contradiction;
- state uncertainty;
- known failure signature;
- consequence/reversibility;
- previous verified failure;
- calibrated smaller-model uncertainty;
- disagreement;
- information value;
- remaining budget.

Forbidden: hidden case labels, oracle answer, or model confidence as sole authority.

Model choice, scaffold level, recovery policy, and routing features are separate variables.

Controls:

- always-small;
- always-Qwen;
- fixed route;
- random/sham router matched to Qwen-call rate;
- Harvest D router;
- post-hoc oracle router for analysis ceiling only.

Metrics:

- missed escalation;
- false escalation;
- Qwen precision/recall;
- Qwen call fraction;
- routing regret;
- premature/late escalation;
- verified success;
- cost/latency per verified success.

## D5 — Qwen + Maximum INVERTED

Run the 2x2:

- SMALL RAW;
- SMALL + MAX PROVEN INVERTED;
- QWEN RAW;
- QWEN + MAX PROVEN INVERTED.

Only causally supported D1–D4 mechanisms may enter MAX.

Primary interaction metric:

`SYNERGY = (Qwen+INVERTED - QwenRaw) - (Small+INVERTED - SmallRaw)`

Also report:

`SDI = Gap_assisted / Gap_raw`

`FRONTIER_SHIFT = Boundary_assisted - Boundary_raw`

`SUBSTITUTION_EFFICIENCY = added verified capability / added architecture cost`

A stronger 24B/frontier comparator may receive only a small residual diagnostic set when necessary to distinguish architecture/spec failure from remaining model-intelligence limitation. It is never a production dependency.

## D6 — Purple-Unicorn Discovery

### Goal

Find novel interaction failures outside the known causal map, not merely harder known cases.

Edge pressure ladder:

- L0 known single failure;
- L1 known pair;
- L2 known triple;
- L3 unusual temporal ordering;
- L4 contradictory signals;
- L5 novel composition of known mechanisms;
- L6 distribution shift;
- L7 no matching failure signature;
- L8 multiple plausible causal explanations;
- L9 adversarially constructed novel interaction.

Higher-order cases are selected for expected information gain, not random combinatorial volume.

### QWEN_EXPLORER

May diagnose, generate competing hypotheses, request missing evidence, propose discriminating experiments and repairs, and identify unfamiliar interactions.

May not authorize, commit, self-certify, bypass the kernel, or promote its own output.

Causal conversion:

`UNKNOWN FAILURE -> preserve exact state -> hypotheses -> deterministic experiment planner -> targeted intervention + sham -> exact-state replay -> neighbor generalization -> fresh-family generalization -> regression`

## D6B — Capability Ratchet

After a D6 discovery is causally converted:

1. create candidate external knowledge object;
2. remove the original Qwen solution/context;
3. rerun neighboring and fresh applicable cases;
4. attempt transfer to smaller model;
5. progressively remove scaffolding;
6. find new minimum model/support requirement;
7. run regression/hard-invariant bank;
8. promote only if all gates pass.

Promotion lifecycle:

`OBSERVED -> HYPOTHESIZED -> CAUSALLY_VERIFIED -> NEIGHBOR_GENERALIZED -> FRESH_GENERALIZED -> REGRESSION_SAFE -> PROMOTED`

A single success may only become OBSERVED. A model explanation may only become HYPOTHESIZED.

Knowledge objects record:

- ID/version/originating failure signature;
- causal hypothesis and verified mechanism;
- applicability/exclusion conditions;
- required state/evidence/authority;
- intervention and expected postcondition;
- verifier;
- supporting/sham/generalization/negative-transfer cases;
- confidence state;
- source model/time;
- supersedes/rollback target/revalidation time.

Automatic learning may update routing/scaffold/evidence/context/decomposition/recovery recommendations, failure signatures, verified skills, and deterministic guards.

It may not expand filesystem/network/secret/destructive/deployment/privilege authority or kernel bypass.

Promotion is suspended immediately on a hard-invariant violation and may be restored, revised, or rolled back after investigation.

Metrics:

- Capability Expansion Rate;
- Qwen Retirement Rate;
- Small-Model Takeover Rate;
- Knowledge Reuse Rate;
- Negative Transfer Rate;
- Capability Regression Rate.

## D7 — Causal Closure

No architecture discovery. Freeze the responsibility map and Test 5 optimization space.

Every P0/P1 question ends as:

- `FREEZE`
- `TUNE`
- `REJECT`
- `DEFER`
- `UNRESOLVED_BUT_IDENTIFIED`

Forbidden: UNKNOWN WHY, UNKNOWN WHETHER IT MATTERS, UNKNOWN WHAT TO TEST, MAYBE USEFUL.

Every important responsibility is assigned to `KERNEL`, `SYSTEM`, `MODEL`, `HYBRID`, `VERIFIER`, or `RECOVERY`.

## Failure injection contract

Every injection declares:

- fault ID/layer/time;
- visible information and hidden truth;
- expected detection/disposition;
- allowed recovery;
- forbidden behavior;
- semantic oracle;
- hard invariant;
- cleanup/replay method.

Required failure families:

### State
stale/missing/contradictory state, incorrect version, concurrent update, changed-after-plan, hidden prerequisite, partial/corrupt observation, late state, fork/merge conflict.

### Evidence
missing/stale/contradictory/forged/circular evidence, irrelevant evidence flood, high-confidence false evidence, valid evidence bound to wrong entity.

### Context
buried critical fact, duplicate tool outputs, irrelevant long context, summary omission, conflicting summaries, truncation, ordering manipulation.

### Topology
hidden dependency, cycle, reversal, long chain, conditional branch, cross-branch invariant, locally correct/global invalid decomposition.

### Authority
undergrant, overgrant, expired authority, scope drift, consumed replay, rollback resurrection, delegation mismatch, confused deputy, mutated action under old authority.

### Transaction
crash points, timeout/unknown effect, duplicate/lost response, partial effect, compensation failure, non-idempotent retry.

### Verifier/oracle
false positive/negative, incomplete invariant, stale oracle, wrong expected state, visible-test loophole, local-pass/global-fail, wrong consequence model.

### Recovery
same failed action, wrong rollback point, lost recovery state, invalid alternate, failed compensation, repair regression, late escalation, contradictory acquired evidence.

### Routing
hard-looking but easy case, easy-looking Qwen-required case, confident-wrong small model, uncertain-correct small model, known-signature/novelty lookalikes.

## Metamorphic laws

At minimum:

- irrelevant evidence must not materially change semantic result;
- removing authority makes execution impossible;
- stale evidence cannot increase actionability;
- greater irreversibility cannot require less evidence;
- dependency-preserving permutation preserves semantic final state;
- rollback cannot resurrect consumed authority;
- replay cannot duplicate committed external effect;
- mutating canonical action invalidates prior proof/authorization;
- context compression preserving relevant evidence preserves semantic outcome;
- successful local substeps cannot override failed global postcondition.

## Statistical discipline

Each adaptive stage has development, confirmatory, and fresh-family pools. Test 6 sealed cases are never used for tuning.

Sequential states:

- `SUPERIOR`
- `NONINFERIOR`
- `HARMFUL`
- `FUTILE`
- `UNRESOLVED`

Use sequentially valid confidence intervals/confidence sequences or preregistered equivalent. Practical margin delta is frozen before opening confirmatory data. Catastrophic safety uses delta = 0.

## Call ceilings

Ceilings, never quotas:

- D0: 0
- D1: 0
- D2: 50–70
- D3: 80–110
- D4: 40–60
- D5: 30–50
- D6: 40–70
- D6B: primarily reuses promoted cases; new calls only as sequentially required
- D7: normally 0

Primary expected campaign: roughly 240–360 inference actions. Optional stronger-model residual ceiling: 15–30. Stop when evidence closes the question.

No retry unless retry count is the explicit experimental variable. Transport/infrastructure failure is separate from model failure.

## Required artifacts

- `00-HARVEST-D-MASTER-INDEX.json`
- `EVIDENCE-PROVENANCE.json`
- `SHA256SUMS.csv`
- readiness matrix CSV/JSON
- model capability envelope CSV/JSON
- frontier curves
- SDI and architecture-substitution tables
- system-involvement telemetry JSONL
- intervention-cost curve
- minimum required scaffolding
- model-architecture operating envelope
- responsibility contract
- Qwen call policy and routing regret
- kernel fault matrix
- transaction crash matrix
- oracle validity JSONL
- failure migration
- edge-case atlas
- edge conversion
- boundary ratchet
- promoted failure knowledge
- remaining unknowns
- Test 5 handoff

Preserve raw tasks, trials, prompts, responses, model calls, actions, state snapshots, transitions, oracle results, interventions, shams, findings, error lifecycle, budget, integrity, and provenance.

## CI contract

Normal GitHub CI is model-free. It must verify schemas, lineage, hashing, duplicate suppression, hidden mutation labels, exact-state replay, transaction recovery, authority monotonicity, no authorization resurrection, budget accounting, oracle/metamorphic mechanics, sequential stopping, artifact finalization, capability-envelope promotion/rollback, and offline operation.

No normal push starts Ollama inference. No cloud credential is required.

## Kill conditions

Immediately quarantine affected evidence and halt a stage on:

- unauthorized irreversible action;
- duplicate irreversible effect;
- authorization resurrection;
- model-visible oracle leakage;
- ambiguous physical model-call identity;
- fresh/sealed holdout used for tuning;
- material journal-integrity failure;
- promoted knowledge bypassing authority;
- instrumentation corruption that prevents reconstruction.

## Final success condition

Harvest D succeeds when it can defensibly state, per capability region:

- where a model is raw-reliable;
- which exact mechanisms expand that region;
- how much model-size dependence is removed;
- the minimum system involvement that retains the gain;
- when further scaffolding is inferior to Qwen;
- how far Qwen + maximum proven INVERTED reaches;
- which residual failures remain model-sensitive;
- whether Qwen-discovered failures can be causally externalized and transferred downward to cheaper models/scaffolds without regression.

The strongest evidence pattern is:

`small FAIL -> Qwen PASS -> Qwen Explorer identifies mechanism M -> M beats sham -> M generalizes -> regression-safe promotion -> small+M PASS -> lighter small+M PASS`.

## Scope freeze

Do not enlarge Harvest D because another mechanism sounds useful. Add a concept only when an actual Harvest D result exposes a material unexplained failure, current mechanisms cannot discriminate it, and the addition could change the responsibility boundary or architecture ranking. Otherwise DEFER to Test 5, Harvest E, or Test 6.