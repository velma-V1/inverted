# HD-NEXT-2 — Layered Ingredient Discovery and Operating-Surface Program

## Status

Owner-approved architectural design for the next INVERTED testing program.

HD-NEXT-2 is an umbrella program, not one monolithic run. Its first stage, HD-NEXT-2A, is intentionally split into multiple independently preregistered campaigns so discovery depth is not sacrificed merely to fit one wall-clock window or one 1000-action ceiling.

## Core question

> For each model and observable operating state, what information operators, formulations, doses, sequences, recurrences, trigger conditions, and delivery geometries improve capability above that model's own raw baseline — and where do those same interventions become useless or harmful?

The existing I1-I10 and A-series mechanisms are **seed priors only**. They do not define the complete ingredient vocabulary and must not constrain discovery to the four or few combinations that have looked acceptable so far.

## Governing principles

1. **Discovery depth outranks speed.** Runtime evidence is used to schedule intelligently, not to delete scientifically valuable coverage.
2. **Data collection is cheap; retesting is expensive.** Every physical call must preserve enough raw evidence for later questions that were not known when the call was made.
3. **Ingredients are reusable operators.** A semantic ingredient may appear more than once in a sequence; `A -> B -> A` is a valid experimental object.
4. **Weak alone does not mean useless.** An ingredient cannot be retired solely because its standalone effect is weak or negative.
5. **Model-specific surfaces are allowed.** Small-A, Qwen, and diagnostic models may require different operators, doses, forms, and sequences.
6. **Delivery is stateful when needed.** Some compound effects may only exist when one layer changes the model/task state before the next layer arrives.
7. **No universal winner is required.** The output may be a branching model-specific interaction graph and later a conditional controller.
8. **Fresh/sealed evidence is protected.** HD-NEXT-2A is discovery; independent confirmation is deferred until the discovery surface is frozen.
9. **No blind retries.** Repeated model calls are permitted only as preregistered replications, sequence steps, or explicit recovery interventions.
10. **Pareto evidence is preserved.** Correctness, latency, tokens, calls, stability, safety, and architecture complexity remain separate outputs.

## Models

### Primary models

- Small-A: `qwen2.5:1.5b-instruct-q8_0`
- Qwen: `qwen3.5:9b-q8_0`

Both are optimized only against their own raw baselines.

### Diagnostic model

- Devstral Small 2: `devstral-small-2:24b`

Devstral 24B may be used in selected HD-NEXT-2A campaigns as a **diagnostic/reference probe** to determine whether an interaction is model-specific, architecture-specific, or broader. It must not define the recipe for either primary model.

The local runtime record shows 904 historical 24B calls and a warm median below 9 seconds, so targeted diagnostic use is practical when calls are batched to preserve model residency.
## Semantic ingredient registry

HD-NEXT-2A begins by defining ingredients by **meaning**, not by historical label or prompt wording. Each ingredient requires a semantic contract stating what information it contributes and what it must not leak.

Initial families include, at minimum:

- objective and subgoal;
- canonical current state and state delta;
- authority, scope, and approval state;
- evidence sufficiency, provenance, freshness, and contradiction;
- uncertainty and missing-information declaration;
- risk, consequence, reversibility, and preservation constraints;
- invariants, prerequisites, dependencies, and causal structure;
- admissible actions, forbidden actions, and action consequences;
- prior verified state, prior failures, and recovery options;
- alternatives, counterexamples, positive/negative examples;
- decomposition, plan, success criteria, and failure criteria;
- verifier expectations and tool constraints;
- likely failure mode, edge cases, history, and compressed memory.

This list is a floor, not a ceiling. New semantic families may be added during 2A when they are genuinely distinct and the addition is logged before their first experimental use.

Historical I1-I10/A-series elements map into this registry as prior formulations; they are not privileged categories.
## Delivery model

HD-NEXT-2A must distinguish two fundamentally different forms of layering.

### Static packet layering

All layers are rendered in one model call but remain independently identifiable and ordered, for example:

`A -> B -> A`

This measures order, repetition, context position, and compound information effects without an intermediate model state transition.

### Progressive stateful layering

The model acts between layers:

`A -> response/state R1 -> B -> response/state R2 -> A -> final response`

This measures genuine state-transition effects, including priming, drift, re-anchoring, recovery, and delayed usefulness.

For progressive tests, the harness must preserve parent/child transcript lineage and, where causally useful, support **forked transcript branches**: produce one frozen parent transcript, then continue matched child treatments from that exact recorded state. This isolates the incremental effect of the next layer from root-call variance.

Every progressive physical model call counts independently against the campaign action budget.
## Interaction roles to classify

Each ingredient can occupy more than one role:

- `STANDALONE_POSITIVE`
- `STANDALONE_NEGATIVE`
- `ENABLER` — weak alone but unlocks a later operator;
- `SYNERGIST` — compound path materially exceeds either component alone;
- `SUPPRESSOR` — reduces the value of another operator;
- `REPLACEMENT` — makes an earlier operator unnecessary;
- `RECURRENT` — becomes useful again after an intervening layer;
- `REANCHOR` — restores a useful frame after drift or state change;
- `RECOVERY` — becomes useful specifically after failure/verification rejection;
- `STATE_TRIGGERED` — useful only when an observable condition is present;
- `SATURATING` — helps until a depth/dose boundary, then stops helping;
- `OVERLOAD_HARM` — additional support causes degradation;
- `DORMANT` — no value established yet, but insufficient evidence for retirement;
- `HARMFUL` — replicated negative transfer with no discovered compensating role.

A standalone failure is therefore only one observation about one role.
## HD-NEXT-2A test family

HD-NEXT-2A is a sequence of independently frozen experiments. A later campaign may use earlier 2A results as development priors, but it must not rewrite the earlier campaign after results are known.

### 2A-0 — Noise, baseline, and runtime calibration

Purpose: establish current RAW performance, repeated-cell stochasticity, output-length behavior, and warm/cold runtime distributions before fine effect claims.

Required coverage:

- both primary models;
- eight structurally distinct RAW anchor cells per primary model, with four identical replications per cell;
- eight structurally distinct historical-seed treatment anchor cells per primary model, with four identical replications per cell;
- all major operating regions represented across the anchor set;
- selected 24B diagnostic repeats for residency/runtime calibration;
- explicit cold-load and warm-load telemetry.

Outputs: model-specific noise floor, runtime planning distribution, saturation map, and the set of non-saturated regions eligible for discovery.

### 2A-1 — Broad semantic ingredient discovery

Purpose: expand beyond I1-I10 and identify which information families deserve deeper study.

Use a balanced sparse design over approximately 35-50 semantic ingredient families, both primary models, and structurally diverse non-saturated cases. Each ingredient begins with one conservative canonical formulation and dose so content identity is screened before expensive geometry optimization.

Before an initial ingredient family can be marked standalone-mapped, it must receive at least **four structurally distinct treatment cells per primary model across at least two operating regions**, unless the ingredient is semantically inapplicable to a region and that exclusion is recorded. A new ingredient family discovered later in 2A inherits the same minimum before the 2A freeze or remains explicitly unresolved.

2A-1 does **not** retire ingredients for weak standalone performance. It only assigns initial evidence states and identifies promising, contradictory, or under-observed families.

### 2A-2 — Formulation and representation discovery

Purpose: separate ingredient value from rendering quality.

For active, contradictory, and strategically important dormant families, compare multiple semantically equivalent formulations such as prose, typed fields, ledgers, matrices, graphs, ordered lists, compact summaries, and explicit alternatives.

A formulation must preserve the semantic contract of its ingredient. If the semantic payload changes, it is a new ingredient/dose condition rather than a representation-only comparison.

### 2A-3 — Pairwise enabling, suppression, and order

Purpose: identify directional edges in the interaction graph.

Where feasible, matched cells compare:

- RAW;
- A;
- B;
- `A -> B`;
- `B -> A`.

This campaign targets enabling, synergy, suppression, replacement, and simple order dependence. Candidate pairs are chosen from strong, contradictory, uncertain, and protected-random regions rather than only the current winners.

### 2A-4 — Recurrent layering

Purpose: test whether an operator becomes useful again after another layer changes context or model state.

Required sequence families include, when supported by prior edges:

- `A -> B -> A`;
- `A -> A -> B`;
- `A -> B -> B`;
- `B -> A -> B`;
- `A -> B -> C -> A`.

For repeated operators, distinguish at least:

- `REPEAT_EXACT` — same semantic payload repeated;
- `REPEAT_REFRESHED` — same semantic operator regenerated from the current observable state;
- `REANCHOR_COMPRESSED` — a smaller restatement of the earlier operator.

Where practical, compare static-packet recurrence against progressive-stateful recurrence so recency/context effects are not confused with true state-transition effects.

### 2A-5 — Higher-order compound-path discovery

Purpose: deepen only where lower-order evidence justifies it while preserving deliberate exploration.

Search depth begins at three layers and may extend to five or more when marginal evidence remains high. Repeated symbols remain legal; the sequence space is a reusable alphabet, not a permutation of unique ingredients.

At least 20% of admissible development search capacity in this stage is protected for exploration outside the current best branch: weak ingredients after strong ones, reversed paths, repeated operators, unusual spacing, and rare structural states.

### 2A-6 — State-triggered and delayed delivery

Purpose: determine whether the value of an ingredient depends on *when an observable state appears* rather than only where the ingredient sits in a fixed prompt.

Candidate triggers include:

- unresolved dependency;
- evidence insufficiency or contradiction;
- authority/scope uncertainty;
- high consequence or irreversibility;
- preservation risk;
- model uncertainty or malformed candidate;
- pre-action verification boundary;
- context drift or lost constraint;
- recovery availability.

Compare unconditional delivery against delivery only after the preregistered observable trigger. Hidden family labels and oracle answers are forbidden as router inputs.

### 2A-7 — Failure/recovery-triggered delivery

Purpose: map which operators become useful only after a failed attempt, verifier rejection, parse failure, preservation violation, or other observable failure state.

Detection, diagnosis, support injection, candidate generation, system authorization, execution, and verification remain separate responsibilities. A system-owned disposition must never be scored as model semantic error.

### 2A-8 — Edge-case and negative-transfer harvest

Purpose: deliberately search the low-probability regions that an exploitative optimizer would ignore.

This stage emphasizes:

- unusual ingredient pairs and recurrence patterns;
- compounds predicted to fail;
- rare task-state combinations;
- cross-region compound cases;
- overload, distraction, stale-context, and misleading-support controls;
- model disagreement cases;
- rare failures found in previous 2A stages.

The objective is not a high average score. It is to discover missing boundaries and "purple-unicorn" interactions before the ingredient graph is frozen.

### 2A-9 — Coverage-driven gap closure

Purpose: attack the remaining high-value holes in the evidence graph rather than simply run more of the current winners.

The scheduler consumes the coverage ledger and prioritizes untested, noisy, contradictory, recurrent-only, recovery-only, model-disagreement, and high-consequence regions. Selection logic and tie-breaking are frozen before the campaign begins.

### 2A-10 — Saturation audit and discovery freeze

This is zero-inference by default. It audits whether 2A has enough evidence to move from ingredient discovery into precise characterization. If high-priority holes remain, it identifies the exact additional preregistered gap-closure campaign required; it does not silently spend more calls.

## Action-budget policy

Every empirical 2A subtest is an independent campaign under the repository's **1000 combined external/AI action ceiling** unless a stricter frozen limit is declared.

The 1000-action ceiling is **per campaign, not a total cap for HD-NEXT-2A**. Multiple 2A campaigns are permitted because each answers a different causal question.

Before execution, each campaign must reserve non-model external actions. The default planning envelope is:

`maximum model calls = 1000 - frozen non-model-action reserve`

Use a default reserve of at least 40 actions unless preflight proves a different reserve is sufficient. Progressive layers count each physical model call separately.

Wall-clock duration is not an automatic early-stop criterion. If a frozen campaign must span sessions, it may checkpoint and resume from the immutable schedule/ledger without changing cases, treatments, thresholds, or selection logic.

## Runtime-aware scheduling

Use `docs/LOCAL_RUNTIME_EVIDENCE.md` when planning each campaign.

- Small-A may carry broad high-volume discovery because its measured HD-NEXT-1 latency is ~0.09s/call.
- Qwen should receive enough calls to map its own surface; do not downsample it merely because it is slower. Current planning anchor is ~34s/call, with a ~77s/call long-output stress case.
- Devstral 24B diagnostic calls should normally be executed in same-model blocks to preserve residency; warm median historical latency is under 9s.
- Treatment/case ordering inside each model block must remain randomized or balanced.
- Load duration and warm/cold state must be preserved so scheduler behavior cannot masquerade as treatment latency.

## Operating regions

Development coverage must span, at minimum:

1. `GLOBAL_INTERACTION`;
2. `TRANSACTION`;
3. `VERIFIER_ORACLE`;
4. `AUTHORITY_SCOPE`;
5. `EVIDENCE_TRUST`;
6. `STATE_PRESERVATION`;
7. `POLICY_ORDERING`;
8. `STRUCTURAL_DEPENDENCY_RECOVERY`.

Cross-region compound cases are required because some interactions may only appear when two failure structures coexist.

Cases should vary objective descriptors including dependency depth, requirement count, action-space size, evidence completeness, ambiguity, authority state, reversibility, consequence severity, preservation burden, recovery availability, and context pressure.

Hidden family/oracle labels may be used for experimental stratification during development, but later dynamic policies must route only on observable pre-decision state.

## True dose integrity

HD-NEXT-2 must not repeat D3's dose failure. Distinct dose labels must produce distinct semantic payloads and distinct rendered bytes.

For every dose layer, preserve semantic fields, exact bytes, SHA-256, token count, and transform lineage. Preflight rejects a supposed dose contrast when adjacent levels render identically.

## Required evidence capture

Every experimental unit must preserve enough raw state to support later re-analysis without rerunning inference. At minimum capture:

- model ID/digest and runtime identity;
- physical call ID and immutable execution position;
- case ID, structural descriptors, partition, and parent/branch lineage;
- semantic ingredient IDs and formulation IDs;
- layer order, recurrence type, spacing, timing, placement, and trigger;
- exact rendered layer bytes and hashes;
- cumulative context bytes/tokens and critical-information positions;
- parent transcript hash and observable state before each progressive layer;
- intermediate model output after each progressive layer;
- final raw response and parsed candidate answer;
- input/output tokens, latency, load duration, prompt-eval duration, eval duration, and completion reason;
- verifier/oracle result and failure taxonomy;
- scheduler selection reason/probability and protected-exploration flag;
- admissible unexplored neighboring treatments when the unit is scheduled.

Model cognition and system authority must be scored separately. The model proposes a candidate answer/action; the system independently owns authorization, execution permission, safety disposition, and final verification.

## Coverage ledger

The program maintains a model-specific graph rather than a single leaderboard. Nodes represent semantic operators/formulations/states; directed edges represent observed transitions or compound paths.

Every candidate region is labeled `UNTESTED`, `PARTIAL`, `NOISY`, `POSITIVE`, `NEGATIVE`, `CONDITIONAL`, `ENABLER`, `RECURRENT`, `RECOVERY_ONLY`, `DORMANT`, or `HARMFUL` as evidence develops.

## Conservative retirement rule

An ingredient cannot be classified `HARMFUL` or removed from future consideration merely because it fails standalone or in one representation/order.

`HARMFUL` retirement requires negative transfer exceeding the calibrated meaningful-effect threshold on at least **three structurally distinct matched cases across at least two operating regions**, plus at least **two distinct interaction-role probes** drawn from enabling, recurrent, recovery, or state-triggered tests with no meaningful positive signal. If those conditions are not met, the ingredient remains `DORMANT`, `CONDITIONAL`, or another non-retired state.

High-consequence negative transfer is never averaged away by gains elsewhere; it remains an explicit boundary in the graph.

## Effect interpretation

Each subtest preregisters its exact statistical method after 2A-0 supplies the current noise floor. At minimum, analysis must preserve paired wins/losses and confidence/uncertainty by model and operating region.

Useful classifications include:

- direct uplift above RAW;
- incremental uplift over the parent path;
- order reversal (`A -> B` versus `B -> A`);
- recurrence gain (`A -> B -> A` versus `A -> B` and relevant controls);
- state-trigger gain versus unconditional delivery;
- recovery gain after the same observable failure state;
- latency/token/call deltas for every correctness comparison.

Do not promote a tiny delta that lies inside the measured repeated-cell noise floor.

## Protected exploration

Adaptive exploitation must never consume the entire discovery budget. Later 2A stages reserve at least 20% of admissible development search capacity for protected exploration unless a frozen subtest justifies a larger share.

Protected exploration includes weak/dormant operators, reversed sequences, repeated operators, unusual spacing, negative controls, model-disagreement regions, and rare structural compounds.

## HD-NEXT-2A completion criteria

2A does **not** stop because a winner appears or because a target wall-clock duration is reached.

The zero-call 2A-10 audit may freeze discovery only when all of the following are true:

1. every initial semantic ingredient family has met the 2A-1 standalone-mapping floor in both primary models, or is explicitly marked semantically inapplicable/unresolved;
2. strategically important weak/dormant ingredients have received interaction-role testing rather than standalone-only judgment;
3. major positive, negative, and contradictory pairwise edges have been challenged with order controls;
4. recurrence has been tested wherever order, drift, persistence, recovery, or re-anchoring signals justify it;
5. state-triggered and recovery-triggered value has been investigated in the major observable failure regions;
6. protected exploration has covered non-obvious sequences and rare structural states;
7. high-priority contradictory/noisy cells have either been resolved or explicitly carried forward;
8. no known high-value evidence hole is being ignored merely to save runtime;
9. all unresolved regions are represented in the coverage ledger with an explicit reason and next experiment;
10. additional broad discovery is yielding mostly redundant evidence relative to targeted characterization.

If these conditions are not met, 2A-10 produces the specification for another gap-closure campaign rather than falsely declaring saturation.

## Transition after 2A

After the 2A graph is frozen, HD-NEXT-2 continues as a characterization and control program rather than another broad ingredient search.

### 2B — Dose and layer-depth characterization

Map true per-ingredient dose curves, total cumulative information dose, and layer-count dose. Preserve points that trade a tiny amount of correctness for material latency/token savings.

### 2C — Interaction and sequence confirmation

Confirm the strongest pairwise, recurrent, and higher-order paths with matched controls, calibrated noise, and denser local sequence neighborhoods. Determine precedence, recurrence, saturation, and replacement boundaries.

### 2D — Timing, placement, and context geometry

Vary when information arrives, which message/context layer contains it, representation, spacing, critical-information position, useful-token ratio, and context pressure without changing semantic content unintentionally.

### 2E — Conditional progressive controller

Freeze a small deterministic policy that observes allowed public state and chooses whether to deliver no support, a static recipe, a progressive next layer, a recurrent re-anchor, or a recovery intervention.

The controller must use observable state only and must preserve a RAW/no-support route for regions where assistance causes negative transfer.

### 2F — Pareto frontier and compression

Only after the high-performance surface is mapped, search for minimum-equivalent support, cheaper representations, shorter sequences, fewer calls, and simpler controller rules.

### 2G — Fresh transfer

Freeze all recipes, thresholds, and controller rules before evaluating untouched fresh cases.

### 2H — Sealed confirmation

Run final independent confirmation on sealed cases. No treatment, threshold, router, or representation changes are permitted after sealed execution begins.
## Required final artifacts

HD-NEXT-2 must ultimately produce:

- model-specific semantic ingredient registry;
- formulation map;
- directional interaction graph;
- recurrent-layer map;
- state-trigger and recovery-trigger map;
- true dose-response curves;
- sequence and layer-depth curves;
- negative-transfer boundaries;
- local runtime/residency telemetry summaries;
- model-specific Pareto frontiers;
- frozen conditional controller;
- fresh-transfer report;
- sealed-confirmation verdict;
- immutable physical-call ledger and raw request/response evidence.

## Explicit non-goals

HD-NEXT-2 must not:

- assume I1-I10 are the complete ingredient set;
- force Small-A to match Qwen as a success criterion;
- select a universal recipe across models or regions;
- compress support before the performance frontier is known;
- eliminate recurrence because an ingredient was already delivered once;
- treat a static `A -> B -> A` packet as equivalent to progressive `A -> response -> B -> response -> A` delivery;
- spend fresh/sealed cases during discovery tuning;
- use runtime inconvenience as evidence that a scientific region is unimportant.
