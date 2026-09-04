# INVERTED — Complete Research, Testing, and Brain Dossier

Date: 2026-09-04

Status: **PROJECT RESEARCH DOSSIER / TEST-END KNOWLEDGE CONTRACT / BRAIN RESEARCH MAP**

This file consolidates the research conclusions, empirical evidence, architectural implications, testing requirements, unresolved questions, and INVERTED-brain concepts developed for the repository through the current Harvest D / D3-Closure work.

It is intentionally broader than a single experiment specification. Its purposes are:

1. preserve the research already collected so future models do not repeat it;
2. state what the project must know by the end of testing before Test 5 can optimize/compress the architecture;
3. define the full information/control search space so a narrow test cannot accidentally support a broad claim;
4. preserve the current INVERTED-brain concepts, including what may eventually move inside a neural model and what must remain external/system-owned;
5. record the local-model resource envelope, including the owner requirement that **9.6 GB through 13 GB local model footprints are tolerable candidates**;
6. convert the D3-v1 failure and the later D3-Closure undercoverage discovery into permanent design constraints.

Raw immutable run evidence, frozen preregistrations, manifests, exact commits, and deterministic oracles outrank this synthesis.

---

# 1. PROJECT OBJECTIVE

INVERTED is not trying to make a small model imitate a large model through prompt tricks.

The governing question is:

> **How much verified capability can be produced by the smallest practical reasoning model when state, information, authority, action-space construction, verification, recovery, routing, and reusable knowledge are organized around it correctly?**

The target architecture should minimize dependence on fragile model cognition while preserving or improving verified capability.

The project should discover empirically which responsibilities belong to:

- deterministic kernel;
- system-owned state/evidence layer;
- model-visible information compiler;
- semantic reasoning model;
- action-space constructor;
- verifier;
- recovery controller;
- router;
- durable knowledge layer;
- or a future learned/internal INVERTED brain.

The final system is not required to use the smallest model possible at any cost. It is required to use the **smallest realistically sufficient architecture/model combination that preserves the strongest verified behavior**.

---

# 2. LOCAL HARDWARE / MODEL RESOURCE ENVELOPE

Current known local target:

- RTX 4070 Super — 12 GB VRAM;
- 32 GB system RAM;
- Ryzen 7800-series CPU;
- Ollama local runtime;
- Qwen3.5 9B Q8 anchor around the current ~9–9.6 GB practical weight footprint.

Owner requirement:

> **Models in the 9.6 GB through 13 GB practical local footprint range are tolerable.**

This changes model-selection policy.

The project must not reject a stronger local candidate merely because it exceeds the current ~9.6 GB Qwen anchor.

For every model candidate, distinguish:

- parameter count;
- architecture family;
- quantization;
- artifact size;
- actual loaded VRAM where observable;
- CPU/RAM offload;
- context/KV-cache footprint;
- latency;
- tokens/second;
- cold-start/load cost;
- sustained throughput;
- semantic capability;
- failure family;
- support requirement;
- reliability under INVERTED;
- and total lifecycle/system cost.

Models below 9.6 GB are preferred only when they preserve equivalent verified capability.

Models from 9.6–13 GB are normal admissible candidates.

Models above 13 GB are not automatically forbidden, but additional verified capability must pay for additional resource/latency/operational cost.

Because 13 GB may exceed physical VRAM after runtime/KV overhead, the test must measure **real residency/offload behavior** rather than treating file size as equivalent to VRAM use.

---

# 3. INTERNAL REPOSITORY EVIDENCE ALREADY ESTABLISHED

## 3.1 Original architecture benchmark lesson

The original INVERTED benchmark was explicitly designed to compare direct AI execution with system-owned candidate execution/auditing and deterministic checks.

Important retained principles:

- hidden deterministic truth outranks model judgment;
- model output is evidence, not authority;
- same model/config must be compared across architectural roles;
- random-auditor and oracle-auditor controls are needed to distinguish semantic benefit from retry mechanics;
- equal-token/equal-call analysis is required so extra compute does not masquerade as architecture;
- catastrophic false acceptance matters separately from average task success.

Internal source:

`docs/superpowers/specs/2026-08-30-inverted-architecture-benchmark-design.md`

## 3.2 Test-3 / adaptive evidence-discovery lesson

Earlier Test-3 planning already identified six competing theories:

- H0 model ceiling;
- H1 fixed-stack theory;
- H2 routing theory;
- H3 evidence-acquisition theory;
- H4 verification theory;
- H5 external-learning theory.

Important retained lesson:

> The system should choose the highest-value next operation from verified evidence state, not assume one universal stack ordering.

The planned controller concept was:

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

Internal source:

`docs/superpowers/specs/2026-09-01-adaptive-evidence-discovery-campaign-design.md`

## 3.3 Harvest A/B/C retained lessons

The repository research synthesis records:

- bundled INVERTED mechanisms can be dramatically harmful;
- checked/system disposition can be very strong;
- richer behavior/context can create unnecessary evidence burden or unjustified actions;
- architecture can produce lift while leaving escalation, authority interpretation, and action correctness unresolved;
- every retained mechanism must pay complexity rent or enforce an invariant.

Internal source:

`docs/research/2026-09-02-harvest-d-research-synthesis.md`

## 3.4 D2 model frontier

Corrected D2 evidence:

- SMALL_A `qwen2.5:1.5b-instruct-q8_0`: 2/18 semantic successes;
- Qwen3.5 9B: 10/18;
- on the 8 QWEN_GAIN cases, 3B recovered 5/8;
- of the 3 remaining, Phi 3.8B recovered 2/3;
- Qwen3 8B recovered the last residual;
- on 8 cases missed by both 1.5B and 9B, Qwen3 14B recovered only 1/8;
- five persistent 14B failures were answer-right / disposition-wrong.

D2 conclusion:

> Parameter count alone does not explain the residual failure surface.

Internal sources:

- `docs/harvest-d-d2-closure.md`
- `docs/harvest-d-d2-measurement-correction.md`

## 3.5 D3-v1 632-call forensic result

The completed D3-v1 run is frozen historical evidence.

Important facts from the post-run forensic analysis:

- 632 physical calls captured completely;
- original campaign reported `COMPLETE` and `audit_passed`;
- multiple intended derived evidence families remained empty;
- disposition scoring was invalid because prompts exposed answer vocabulary but not the separate hidden disposition vocabulary;
- all 632 disposition scores therefore collapsed to failure;
- Qwen had severe context/deliberation exhaustion;
- SMALL_A was operationally stable but much weaker semantically;
- assistance mechanisms were replayed after the model call and therefore did not causally affect cognition;
- amount conditions were no-ops;
- several ordering conditions were no-ops;
- progressive timing was not truly progressive;
- scheduler decisions were not updated from observed outcomes;
- unused later-phase budget was caused by candidate-pool exhaustion, not evidence saturation.

### Qwen D3-v1 behavior

Qwen 9B:

- 383 calls;
- 302 `done_reason=length` (~78.9%);
- 81 normal stops;
- completed stops: 74/81 answer-correct (~91.4%);
- every length call consumed the full 4096 input+output token envelope;
- massive hidden/returned thinking could consume the context before a usable final answer appeared.

Interpretation:

> A dominant Qwen failure was call-policy/deliberation control, not necessarily semantic incapability.

### SMALL_A D3-v1 behavior

SMALL_A:

- 249 calls;
- all normally stopped;
- 90/249 answer-correct (~36.1%);
- schema parse behavior was much better than strict format scoring suggested;
- frequent fenced JSON created format tax without proving semantic failure.

### Sealed information effect

Qwen matched raw vs supported sealed cases:

- RAW: 2/22;
- SUPPORTED: 9/22;
- 8 fail→success transitions;
- 1 success→failure transition;
- exact McNemar p approximately .039.

SMALL_A:

- RAW: 12/22;
- SUPPORTED: 10/22;
- support did not help and may have harmed.

Retained interpretation:

> Support is probably model-specific and failure-specific. Universal context injection is not justified.

## 3.6 Disposition compiler evidence

Offline replay on generated closure-source semantics showed:

- A6 disposition compiler: 138/148 expected dispositions;
- remaining failures concentrated in authority cases because A6 lacked scope;
- A6 + A7 authority guard: 148/148 on those generated replay-source cases.

This is not independent generalization, but it strongly supports the responsibility hypothesis:

> Disposition/authority should be system-owned unless later evidence disproves that boundary.

---

# 4. CURRENT STRONGEST EXTERNAL-INVERTED ARCHITECTURE HYPOTHESIS

Current best defensible external architecture:

```text
USER GOAL / TASK CONTRACT
        |
        v
SYSTEM-OWNED CANONICAL STATE + UNCERTAINTY
        |
        v
INFORMATION COMPILER
  choose only useful model-visible state/evidence
        |
        v
ADMISSIBLE ACTION FRONTIER
        |
        v
BOUNDED SEMANTIC REASONING MODEL
        |
        v
TYPED SEMANTIC PROPOSAL
        |
        v
DETERMINISTIC DISPOSITION COMPILER
        |
        v
AUTHORITY + INVARIANT + CONSEQUENCE GUARDS
        |
        v
TYPED EXECUTION / TRANSACTION BOUNDARY
        |
        v
INDEPENDENT VERIFIER
        |
        +------------------+
        | success          | failure
        v                  v
 VERIFIED COMMIT      FAILURE LOCALIZATION
                           |
                           v
                    TARGETED RECOVERY
                           |
                           v
                       REVERIFY
```

Likely responsibilities to keep outside model cognition:

- canonical state;
- state version;
- authority;
- hard invariants;
- disposition where deterministic semantics suffice;
- transaction truth;
- irreversible-effect fencing;
- commit/rollback/compensation semantics;
- provenance;
- final success verification;
- duplicate-effect prevention;
- recovery admission;
- deterministic routing where observable features suffice;
- command/syntax compilation where typed semantic actions can be compiled safely.

Likely model responsibilities:

- semantic interpretation;
- ambiguous goal understanding;
- novel reasoning;
- hypothesis generation;
- evidence-request selection where deterministic rules are insufficient;
- decomposition where beneficial;
- semantic action choice inside a bounded admissible frontier;
- diagnosis of unfamiliar failure;
- proposing recovery candidates;
- exploring novel capability boundaries.

This boundary remains empirical. A system mechanism that adds cost without causal value should be removed.

---

# 5. EXTERNAL RESEARCH — INFORMATION, CONTEXT, AND SCAFFOLDING

## 5.1 SMART / Small Reasons, Large Hints

**Guiding Reasoning in Small Language Models with LLM Assistance** (Kim et al., 2025)

Source: https://arxiv.org/abs/2504.09923

Framework: Small Reasons, Large Hints (SMART).

Core finding:

- identify uncertain reasoning steps;
- inject targeted larger-model guidance only when needed;
- avoid exhaustive large-model intervention;
- targeted scaffolding can materially improve SLM reasoning.

INVERTED implication:

- support should be conditional;
- uncertainty/evidence state can decide when support is worth spending;
- do not flood every call with maximum scaffolding.

## 5.2 Three Roles, One Model

**Three Roles, One Model: Role Orchestration at Inference Time to Close the Performance Gap Between Small and Large Agents** (McClendon et al., 2026)

Source: https://arxiv.org/abs/2604.11465

Qwen3-8B on AppWorld was used as:

1. history summarizer;
2. main agent;
3. isolated correction model.

Reported baseline task completion roughly doubled under the scaffold, and full-precision scaffolded Qwen3-8B exceeded the cited DeepSeek-Coder 33B AppWorld baseline.

INVERTED implications:

- failure can be mechanical/contextual rather than raw reasoning-only;
- context compression can improve small-model agent behavior;
- isolation of correction context can break repeated failure loops;
- inference-time structure can partially substitute for model size;
- the correct comparison is optimized-small vs optimized-large, not supported-small vs raw-large.

## 5.3 ACON

**ACON: Optimizing Context Compression for Long-horizon LLM Agents** (Kang et al., 2025/2026)

Sources:

- https://arxiv.org/abs/2510.00615
- https://github.com/microsoft/acon

Reported results include substantial peak-token/memory reduction while largely preserving performance, successful distillation of the compressor into smaller models, and improvement of smaller long-horizon agents.

Important mechanism:

- compare trajectories where full context succeeds and compressed context fails;
- infer what information was lost;
- update compression guidelines from the failure delta.

INVERTED implication:

> Information compression should learn from **paired success/failure causal differences**, not from generic summarization quality.

## 5.4 Context Length Alone Hurts

**Context Length Alone Hurts LLM Performance Despite Perfect Retrieval** (Du et al., 2025)

Source: https://aclanthology.org/2025.findings-emnlp.1264/

Reported result:

- performance degraded substantially as context length increased even when relevant evidence was perfectly retrievable;
- irrelevant content alone was not the complete explanation;
- input length itself can create reasoning burden.

INVERTED implication:

- amount must be tested independently from information quality;
- token-matched irrelevant burden controls are necessary;
- “more true context” is not automatically safer or more capable.

## 5.5 Lost in the Middle

**Lost in the Middle: How Language Models Use Long Contexts** (Liu et al., TACL 2024)

Source: https://aclanthology.org/2024.tacl-1.9/

Core finding:

- relevant information position changes performance;
- beginning/end often outperform middle placement;
- longer-context capability does not imply robust use of all positions.

INVERTED implication:

- field ordering/placement must be a real causal variable;
- key state/evidence/invariant fields should not be assumed equally usable anywhere in context;
- shuffled controls matter.

## 5.6 Premise Order Matters

**Premise Order Matters in Reasoning with Large Language Models** (Chen et al., ICML 2024)

Source: https://proceedings.mlr.press/v235/chen24i.html

Reported result:

- logically equivalent premise permutations can cause large accuracy changes;
- order aligned with reasoning requirements can outperform random order substantially.

INVERTED implication:

- order is not cosmetic;
- context compilers should test state-first, evidence-first, safety-first, objective-first, and actual randomized controls.

## 5.7 Code-Guided Reasoning

**Code-Guided Reasoning for Small Language Models: Evaluating Executable MCQA Scaffolds** (2026)

Source: https://huggingface.co/papers/2605.18827

Retained lesson:

- executable scaffolds can help smaller models;
- assistance can also add cost or regress some conditions;
- scaffolding must be evaluated as a causal mechanism rather than assumed beneficial.

## 5.8 Reasoning can hurt

**Mind Your Step (by Step): Chain-of-Thought can Reduce Performance on Tasks where Thinking Makes Humans Worse** (Liu et al., ICML 2025)

Source: https://proceedings.mlr.press/v267/liu25t.html

**Reasoning Can Hurt the Inductive Abilities of Large Language Models** (Jin et al., 2025)

Source: https://arxiv.org/abs/2505.24225

**Towards Structural Understanding of LLM Overthinking** (2026)

Source: https://deepmind.google/research/publications/203490/

Retained implications:

- more reasoning is not monotonically better;
- decomposition can create new failure points;
- over-exploration and over-verification can waste context/compute;
- Qwen should receive a bounded, evidence-driven reasoning policy rather than unlimited thinking;
- routing should distinguish routine tasks from tasks that actually benefit from deeper deliberation.

---

# 6. EXTERNAL RESEARCH — ROUTING AND ACTION-SPACE REDUCTION

## 6.1 Confident or Seek Stronger

**Confident or Seek Stronger: Exploring Uncertainty-Based On-device LLM Routing From Benchmarking to Generalization** (Chuang et al., 2025)

Source: https://arxiv.org/abs/2502.04428

Core retained finding:

- uncertainty routing only works well when uncertainty aligns with correctness;
- alignment varies by model and uncertainty method;
- confidence must be calibrated rather than trusted directly.

INVERTED implication:

- model self-confidence is only a candidate feature;
- compare it against simpler system observables such as novelty, missing evidence, dependency depth, state ambiguity, irreversible consequence, and prior failure.

## 6.2 Causal Minimal Tool Filtering

**ToolChoiceConfusion: Causal Minimal Tool Filtering for Reliable LLM Agents** (Babu & Iyer, 2026)

Sources:

- https://arxiv.org/abs/2606.06284
- https://github.com/R-Suresh/ToolChoiceConfusion

Reported benchmark result:

- exposing only the causally necessary next-step tool frontier can preserve strong success while sharply reducing visible tools/token burden;
- larger tool menus create wrong-tool and premature-action errors.

INVERTED implication:

> A2/admissible-action support may improve behavior by **removing bad choices**, even if the model’s internal reasoning is unchanged.

Therefore tests must distinguish:

- cognitive improvement;
- action-space shaping;
- reduced token burden;
- reduced opportunity for premature action.

## 6.3 Goal-State Inference + CMTF

**GIST-CMTF: Goal-State Inference for Causal Minimal Tool Filtering in LLM Agents** (Babu & Shukla, 2026)

Source: https://arxiv.org/abs/2606.16813

Retained lesson:

- a perfect tool frontier around the wrong inferred goal still fails;
- goal ambiguity must be resolved before causal action filtering.

INVERTED implication:

- objective/subgoal inference is a distinct upstream responsibility;
- unclear goal state should produce clarification/evidence acquisition rather than confident execution.

---

# 7. EXTERNAL RESEARCH — FAILURE, PROCESS, AND RECOVERY

## 7.1 PALADIN

**PALADIN: Self-Correcting Language Model Agents to Cure Tool-Failure Cases** (Vuddanti et al., 2025/2026)

Sources:

- https://arxiv.org/abs/2509.25238
- https://github.com/33k0/PALADIN-Framework

Core mechanism:

- systematically inject tool failures;
- preserve recovery-annotated trajectories;
- retrieve similar failure exemplars;
- execute learned recovery behavior.

INVERTED implications:

- failure data is training data;
- recovery must be exposed as an explicit trajectory, not a final pass/fail flag;
- injected failures and recovery exemplars can teach otherwise missing operational behavior;
- recovery rate and task success should be measured separately.

## 7.2 AgentProcessBench

**AgentProcessBench: Diagnosing Step-Level Process Quality in Tool-Using Agents** (Fan et al., 2026)

Source: https://arxiv.org/abs/2603.14465

Key findings retained:

- step-level process quality reveals information hidden by final outcome;
- weaker agents can look deceptively good at the step level because they terminate early;
- neutral vs erroneous action classification is difficult;
- process signals complement outcome supervision.

INVERTED implication:

- first meaningful divergence matters;
- early termination can distort metrics;
- process and final-state correctness must both be retained.

## 7.3 AgentDebug

AgentDebug framework / AgentErrorBench.

Source: https://github.com/ulab-uiuc/AgentDebug

Retained architecture:

- explicit error taxonomy;
- root-cause isolation;
- corrective feedback after causal localization.

INVERTED implication:

- do not repair the final symptom blindly;
- localize the earliest causally meaningful divergence and target repair there.

## 7.4 AgentProp / evaluator auditing

**Auditing Automated Evaluation, Error Propagation, and Runtime Mitigation in Tool-Using Language Agents** (Gurram, 2026)

Source: https://arxiv.org/abs/2604.16706

Retained findings:

- simple heuristic end-to-end judging can be extremely unreliable;
- input-corruption rejection and recovery can be statistically independent capabilities;
- agents can fabricate tool execution/success in ways hidden by naive final scores.

INVERTED implications:

- prevention and recovery are separate axes;
- execution claims must be grounded in system evidence;
- model statements cannot certify tool effects.

## 7.5 Success provenance / causal credit

Recent research also reinforces that a correct final answer does not reveal why the agent succeeded and that step-level correctness signals need not equal causal contribution.

Research anchors:

- **Success Is Not Self-Explanatory: Auditing Success Provenance in Agent Evaluation** — https://arxiv.org/abs/2607.24054
- **Credit Without Ground Truth: Auditing Step-Level Credit Assignment in LLM Agents Against Executed Replay** — https://arxiv.org/abs/2608.19760

INVERTED implication:

- causal replay/intervention outranks descriptive credit;
- hidden exposure or accidental answer acquisition must not be mistaken for reasoning capability;
- confidence/LLM-judge signals must not be treated as causal ground truth.

---

# 8. EXPERIMENT-DESIGN RESEARCH — THE COMBINATORIAL MISS

A major design correction emerged immediately before physical D3-Closure execution.

The problem:

The test intended to make claims such as:

- minimum sufficient information;
- best representation;
- best order;
- best placement/timing;
- model-specific support;
- negative-transfer boundary;

while the implemented C2 core physically compared mainly handcrafted `MINIMUM` vs `FULL` information packets.

That is a **screen**, not an optimization/search of the claim space.

## 8.1 Why the space explodes

The original D3 information content contains I1–I10.

Even just nonempty subsets:

`2^10 - 1 = 1,023` possible field subsets.

Current explicit amount levels:

- MINIMUM;
- COMPRESSED;
- MODERATE;
- FULL;
- OVERLOADED.

Current explicit ordering levels:

- DEFAULT;
- TASK_OBJECTIVE_FIRST;
- STATE_FIRST;
- EVIDENCE_FIRST;
- SAFETY_STATE_EVIDENCE_FIRST;
- SHUFFLED_CONTROL.

Ignoring representation, placement, timing, quality, model, failure family, and assistance:

`1,023 × 5 × 6 = 30,690` nominal combinations.

Add plausible representation choices, placement/timing, model, family, and assistance and the theoretical space becomes hundreds of thousands to millions of conditions.

A 10–14 call refinement block cannot identify the global optimum of that space.

## 8.2 Correct methodology: design of experiments + adaptive search

NIST design-of-experiments guidance distinguishes:

- low-resolution/fractional designs for **screening important factors**;
- higher-resolution designs for **interactions**;
- response-surface/local optimization designs after the important region is known.

Sources:

- NIST Fractional Factorial Designs: https://www.itl.nist.gov/div898/handbook/pri/section3/pri3345.htm
- NIST Design Selection: https://www.itl.nist.gov/div898/handbook/pri/section3/pri33.htm

NIST combinatorial-testing guidance uses covering arrays / t-way coverage to efficiently cover interactions without full Cartesian enumeration.

Sources:

- https://www.nist.gov/publications/combinatorial-testing
- https://csrc.nist.gov/pubs/ir/7878/final
- https://www.nist.gov/itl/math/nist-covering-array-tables

Best-arm / successive-elimination research supports progressively eliminating poor candidates and concentrating samples on competitive survivors.

Research anchors:

- Audibert & Bubeck, **Best Arm Identification in Multi-Armed Bandits** — https://www.microsoft.com/en-us/research/publication/best-arm-identification-multi-armed-bandits/
- Shahrampour et al., **On Sequential Elimination Algorithms for Best-Arm Identification in Multi-Armed Bandits** — https://arxiv.org/abs/1609.02606

INVERTED testing implication:

> **Do not brute-force the combinatorial space and do not pretend a tiny handpicked sample optimized it. Use model-free enumeration/pruning, factor screening, interaction coverage, adaptive elimination, local search, minimality ablation, and fresh confirmation.**

---

# 9. REQUIRED REDESIGN OF INFORMATION TOMOGRAPHY

The information compiler must be treated as a conditional policy search, not a prompt contest.

## 9.1 Full candidate factor map

### Content

- I1 objective/current subgoal;
- I2 canonical state/version;
- I3 scope/authority;
- I4 evidence/missing evidence;
- I5 consequence/reversibility;
- I6 invariants/postcondition;
- I7 admissible actions;
- I8 dependencies/order;
- I9 previous verified/recovery state;
- I10 uncertainty/novelty/alternatives.

### Quality

- correct complete;
- correct incomplete;
- missing;
- stale;
- contradictory;
- noisy;
- irrelevant;
- redundant;
- misleading non-authoritative;
- internally consistent but insufficient.

### Trust/source

- canonical system;
- deterministic tool evidence;
- model-derived claim;
- untrusted external metadata;
- mixed-trust packet.

### Amount

- minimum;
- compressed;
- moderate;
- full;
- overloaded;
- pure token-burden control.

### Representation

Candidate families include:

- raw prose;
- compact typed fields;
- strict JSON/schema;
- decision table;
- priority block;
- explicit alternatives;
- subproblem/decomposition form;
- minimal ledger/current state;
- compressed summary;
- admissible-action matrix;
- graph/dependency form where appropriate.

### Ordering

- objective-first;
- state-first;
- evidence-first;
- safety/state/evidence-first;
- dependency-first where appropriate;
- actual seeded shuffle control.

### Placement

- system message;
- user/task message;
- dedicated state packet;
- tool/evidence result;
- mixed placement.

### Timing

- all upfront;
- immediately before decision;
- genuinely progressive reveal across steps;
- just-in-time after evidence request;
- only on detected uncertainty/failure.

### Assistance interaction

Model-visible:

- A1 state anchor;
- A2 action frontier;
- A3 evidence gate;
- A4 dependency/decomposition support.

System-owned:

- A5 verifier;
- A6 disposition compiler;
- A7 authority guard;
- A8 consequence guard;
- A9 recovery supervisor;
- A10 failure guard;
- A11 routing/escalation.

### Model interaction

At minimum distinguish:

- 1–2B routine model;
- 3–4B transition class;
- 8–9B anchor class;
- any better local candidate inside the tolerated 9.6–13 GB footprint;
- larger diagnostic ceiling only when necessary.

### Task/failure interaction

- state;
- evidence;
- context;
- topology/dependency;
- authority;
- transaction;
- verifier/oracle;
- recovery;
- routing;
- global interaction/invariant;
- novelty/uncertainty.

## 9.2 Zero-call enumeration and pruning

Before inference:

1. enumerate admissible packet policies;
2. render every candidate model-free;
3. hash rendered payload;
4. hash semantic field set;
5. record token estimate;
6. remove exact duplicates;
7. remove semantic no-ops;
8. remove impossible combinations;
9. remove oracle-leaking combinations;
10. identify dominated policies that add burden with no new information;
11. measure pairwise/t-way factor coverage;
12. construct a screening design that covers important levels/interactions efficiently.

This step can eliminate thousands of theoretical combinations at zero model-call cost.

## 9.3 Stage 1 — reproducibility calibration

Before small differences are interpreted as treatment effects, measure stochastic/runtime variance under exact repeated conditions.

Questions:

- is temperature-0 output byte-identical?;
- semantic-identical?;
- disposition-identical?;
- how much latency/token variance exists?;
- does previous-call warm state/carryover matter?;
- does runtime restart change behavior?;
- how much repeat depth is needed before a 1–2 case delta is meaningful?

Without this, optimization can chase noise.

## 9.4 Stage 2 — broad factor screen

Use a balanced/fractional/covering design to identify strong main effects and obvious negative-transfer effects.

The objective is not to declare a winner.

The objective is to answer:

- which content fields matter?;
- does amount matter?;
- does representation matter?;
- does order matter?;
- does placement matter?;
- does timing matter?;
- which effects differ by model/family?;
- which factors are approximately inert and can be dropped from deeper search?

## 9.5 Stage 3 — interaction search

Promote only factors showing plausible interaction.

Mandatory candidate interactions include:

- content × representation;
- content × amount;
- content × ordering;
- amount × model;
- representation × model;
- information × A1–A4;
- A2 × action-space size;
- information × failure family;
- information × recovery;
- model × failure family;
- model × support burden.

Use t-way coverage and targeted causal pairs rather than arbitrary full Cartesian combinations.

## 9.6 Stage 4 — local optimization around surviving regions

When a region wins broad screening, search neighbors:

- add/remove one information field;
- compress/expand;
- change one ordering;
- change one representation;
- change placement;
- change assistance mechanism;
- change only the relevant timing decision.

This is where “best practical packet/policy” begins to become a meaningful claim.

## 9.7 Stage 5 — minimum sufficient support

Once a high-performing policy is identified:

```text
WINNING POLICY
 -> remove one field/mechanism
 -> matched replay/fresh comparison
 -> preserve if removal hurts
 -> remove if noninferior
 -> repeat
```

The result should be conditional:

`MSIP(model, family, state_features)`

not a universal one-size-fits-all packet unless evidence actually supports universality.

## 9.8 Stage 6 — negative-transfer boundary

Search for the switch point where support moves from useful to harmful.

Examples:

- token burden;
- irrelevant context;
- stale state;
- excessive decomposition;
- unnecessary reasoning;
- too narrow action frontier;
- wrong goal-state inference;
- misleading recovery precedent.

The goal is a routing rule, not merely “support can hurt.”

## 9.9 Stage 7 — fresh confirmation

Only after search/tuning ends:

- freeze candidate policy/policies;
- open untouched fresh/sealed families;
- confirm uplift;
- confirm minimality where required;
- confirm no hard-invariant regression;
- compare optimized-small against optimized-larger model under the same information/control advantages.

---

# 10. CALL-BUDGET POLICY AFTER THE COMBINATORIAL CORRECTION

The old expectation of ~206 calls and the 248 absolute combined ceiling is **not sufficient to support broad information-optimization claims**.

The correct principle is:

> A call budget must be derived from the claim-space, design resolution, variance, interaction coverage, promotion thresholds, and sequential stopping rule—not guessed from a convenient round number.

A reasonable provisional architecture for the next campaign is:

- D4 call-policy gate: bounded separately;
- reproducibility block;
- broad factor screen;
- interaction/conditional search;
- local optimization/minimality;
- recovery causal block;
- model-substitution localization;
- protected fresh confirmation.

The final ceiling must be frozen only after zero-call enumeration computes:

- number of nonduplicate admissible policies;
- factor levels;
- chosen t-way interaction coverage;
- number of model/family strata that materially matter;
- minimum matched depth for the target effect size;
- runtime stochasticity;
- protected confirmation requirement.

The campaign should then use adaptive elimination so it can stop materially below the ceiling.

Do **not** return automatically to a 1,000-call quota.

Do **not** cap the campaign so low that the claimed optimum is unidentified.

---

# 11. EVERYTHING THE PROJECT MUST KNOW BY THE END OF TESTING

This section is the end-of-testing knowledge contract.

Test 5 should not be authorized to optimize/compress until every high-impact item below is either:

- known with appropriate evidence;
- explicitly bounded;
- assigned to a later test because it cannot change Test 5 architecture;
- or rejected as not worth further testing.

## 11.1 Model operating policy

Know:

- whether Qwen should think by default;
- when thinking should be disabled;
- whether bounded/conditional reasoning is superior;
- the smallest reasoning/token budget preserving correctness;
- context-exhaustion rate;
- empty-final rate;
- semantic error rate after normal completion;
- latency/token cost of deeper reasoning;
- features that predict when deeper reasoning pays.

## 11.2 Raw model capability envelope

For each candidate model/family:

- raw success by failure family;
- complexity boundary;
- silent-wrong-action rate;
- hard-invariant violations;
- context-exhaustion behavior;
- schema/format tax separately from semantics;
- latency/tokens/resource cost.

## 11.3 Supported model capability envelope

For each model:

- B0 raw;
- B1 normal proven INVERTED support;
- B2 maximum proven INVERTED support;
- frontier shift;
- remaining residual failure classes;
- negative transfer.

## 11.4 Smallest useful model

Know the smallest model that can safely/reliably own each capability region.

Do not ask only “which one model wins overall?”

Produce capability-region ownership such as:

- routine local;
- scaffolded local;
- stronger local;
- novelty investigation;
- acquire evidence;
- safe stop/escalate.

## 11.5 Model substitution boundary

Know:

- how much of the 1.5B→9B raw gap architecture removes;
- whether a 3–4B model becomes the practical optimum;
- whether an 8–9B anchor remains necessary;
- whether a 9.6–13 GB candidate materially changes the frontier;
- which residual failures are genuinely capacity-bound vs architecture/spec/oracle-bound.

## 11.6 Information content value

For I1–I10, know:

- marginal value;
- conditional value;
- harmful conditions;
- redundancy;
- interactions;
- failure families needing the field;
- models needing the field;
- whether system-only is enough;
- whether model-visible exposure is needed.

## 11.7 Information amount curve

Know the model/family curve across:

- too little;
- sufficient;
- compressed;
- moderate;
- full;
- overloaded;
- token-matched irrelevant burden.

Identify where additional context stops helping or starts hurting.

## 11.8 Representation policy

Know whether semantically equivalent information works differently as:

- prose;
- typed fields;
- JSON;
- table;
- ledger;
- alternatives;
- dependency graph;
- admissible-action matrix;
- compressed summary.

Retain only representation differences large enough to justify system complexity.

## 11.9 Ordering policy

Know when:

- objective-first;
- state-first;
- evidence-first;
- safety-first;
- dependency-first;
- randomized order

changes outcomes.

## 11.10 Placement and timing

Know whether information belongs in:

- system context;
- task context;
- structured state packet;
- tool/evidence response;
- JIT injection;
- progressive delivery.

Know whether timing benefit is real or merely token-position/context-length confounding.

## 11.11 Minimum Sufficient Information Policy

Do not output merely a single static packet unless data proves it.

Desired artifact:

`MSIP(model, task/failure family, observable state features)`

with explicit fallback when confidence is insufficient.

## 11.12 Assistance mechanisms A1–A11

For every assistance mechanism classify:

- REQUIRED;
- CONDITIONAL;
- REDUNDANT;
- HARMFUL;
- UNRESOLVED.

Know exact applicable regions and causal effect.

## 11.13 Cognition vs action-space shaping

For A2 and related controls, know whether improvement came from:

- better semantic reasoning;
- fewer visible choices;
- lower token burden;
- blocking premature actions;
- or deterministic system correction after the model.

## 11.14 Deterministic responsibility contract

For every material responsibility assign:

- KERNEL;
- SYSTEM;
- MODEL;
- HYBRID;
- VERIFIER;
- RECOVERY.

At minimum resolve:

- state;
- authority;
- invariants;
- disposition;
- action syntax;
- action semantics;
- transaction truth;
- verification;
- routing;
- recovery;
- durable learning/promotion.

## 11.15 Prevention vs recovery

Measure separately:

- failure prevented?;
- failure detected?;
- first causal error localized?;
- diagnosis correct?;
- recovery frontier correct?;
- recovery selected?;
- recovery admitted safely?;
- recovery executed?;
- postcondition restored?;
- new failure introduced?;
- failure migrated?;
- safe escalation/stop used appropriately?

## 11.16 Real recovery policy

A recovery claim requires an actual state transition, not a synthesized trajectory record.

Need real causal sequences:

```text
failure
 -> detection
 -> diagnosis
 -> intervention
 -> new action/state
 -> verification
```

## 11.17 Negative transfer

Know:

- which support harms which model/family;
- whether harm is due to content, burden, placement, action restriction, wrong goal inference, overthinking, stale information, or recovery precedent;
- observable boundary that allows routing around the harm.

## 11.18 Routing policy

Test pre-inference features such as:

- novelty;
- missing evidence;
- state ambiguity;
- dependency depth;
- action-space size;
- irreversible consequence;
- authority ambiguity;
- previous failure;
- model historical boundary;
- estimated information burden;
- task family/complexity.

Output should map observable state to:

- routine small model;
- scaffolded small model;
- stronger local model;
- maximum local policy;
- acquire evidence;
- novelty investigation;
- safe stop/escalation.

## 11.19 Confidence calibration

Know whether model confidence predicts correctness enough to improve routing beyond system-owned features.

If not, kill confidence-based routing.

## 11.20 Reproducibility/stochasticity

Know:

- exact-repeat semantic stability;
- exact-repeat byte stability;
- runtime/order carryover;
- warm/cold effects;
- restart effects;
- seed sensitivity;
- minimum independent observations needed for stable conclusions.

## 11.21 Failure attribution

Every important residual failure must be attributable as far as realistic to:

- model;
- information;
- architecture;
- oracle;
- specification;
- instrumentation;
- infrastructure;
- recovery;
- routing;
- or interaction.

`UNKNOWN WHY` is not an acceptable P0/P1 handoff state.

## 11.22 Generalization

Winning mechanisms must survive:

- neighbor cases;
- fresh families;
- new seeds;
- relevant model sizes;
- difficulty shifts;
- adverse information quality;
- hard-invariant cases.

## 11.23 Efficiency

For each promoted mechanism know:

- physical calls saved/added;
- input/output tokens;
- latency;
- resource load;
- implementation complexity;
- maintenance burden;
- failures prevented;
- capability gained.

## 11.24 Search-space coverage

For every broad claim, report:

- total theoretical factor space;
- model-free-pruned space;
- tested factor coverage;
- t-way interaction coverage;
- unresolved regions;
- reason those unresolved regions cannot overturn the final architecture decision.

This is required to prevent another undercoverage error.

## 11.25 Architecture compression readiness

Before Test 5:

- know which mechanisms are causally live;
- know which are harmful;
- know which interactions still matter;
- know thresholds/boundaries;
- know model envelopes;
- know routing policy;
- know remaining explicit unknowns.

Internal handoff source:

`docs/harvest-d-test5-handoff-schema.md`

---

# 12. INVERTED BRAIN — COMPLETE CONCEPT

The “INVERTED brain” is the longer-term hypothesis that some of the external information/control mechanisms discovered by Harvest D can eventually be learned into a compact neural reasoning core.

It is **not** permission to remove deterministic authority or verification boundaries.

The idea is to train a model whose internal computation naturally mirrors the high-value causal mechanisms found externally.

## 12.1 External-to-internal mapping

External INVERTED currently resembles:

```text
input/task
 -> canonical state construction
 -> relevant-information selection
 -> admissible-action reduction
 -> reasoning
 -> first-error/self-check
 -> recovery choice
 -> semantic action
 -> deterministic authority/execution
 -> verification
```

A future learned brain could internalize some portions:

```text
INPUT INTERFACE
      |
      v
STATE ESTIMATION / BELIEF REPRESENTATION
      |
      v
RELEVANCE / MINIMUM-INFORMATION GATING
      |
      v
ACTION-FRONTIER / OPTION REPRESENTATION
      |
      v
ADAPTIVE RECURRENT REASONING CORE
      |
      v
UNCERTAINTY / NOVELTY / FIRST-ERROR SIGNAL
      |
      v
RECOVERY / REPLAN LATENT STATE
      |
      v
TYPED SEMANTIC ACTION
```

External deterministic boundary remains:

```text
AUTHORITY
CANONICAL REAL-WORLD STATE
IRREVERSIBLE EXECUTION
TRANSACTION / COMMIT
HARD INVARIANTS
INDEPENDENT VERIFICATION
DURABLE PROVENANCE
FINAL SUCCESS DETERMINATION
```

## 12.2 Why build the external architecture first

External INVERTED provides causal labels for what an internal model would need to learn.

Without that evidence, training an “INVERTED brain” risks merely inventing new neural modules without knowing whether they correspond to real failure mechanisms.

External testing should determine:

- what information is actually needed;
- which ordering/representation/timing helps;
- when reasoning depth helps;
- when reasoning hurts;
- what action-space reduction contributes;
- what first-error signals predict;
- what recovery transitions work;
- what must remain deterministic;
- which mechanisms vary by model/family.

Then internal training can target proven functions.

---

# 13. INVERTED BRAIN — LATENT / RECURRENT REASONING RESEARCH

## 13.1 Coconut / continuous thought

**Training Large Language Models to Reason in a Continuous Latent Space** (Hao et al., 2024)

Source: https://arxiv.org/abs/2412.06769

Coconut feeds a hidden state back as the next reasoning-state embedding rather than decoding every reasoning step into text.

Reported behavior includes:

- latent multi-step reasoning;
- ability to represent multiple possible next reasoning directions;
- advantages on some planning/backtracking tasks;
- fewer language-space thinking tokens in some settings.

INVERTED-brain implication:

- future internal reasoning need not be forced through natural-language tokens;
- a compact state-transition loop may be more appropriate than verbose chain-of-thought;
- latent recurrence could represent state, uncertainty, and alternative actions without paying full language-token cost.

Caution:

- internal latent reasoning is harder to inspect;
- external authority/verification becomes even more important;
- causal testing must determine whether hidden recurrence actually reduces errors rather than only tokens.

## 13.2 Depth-recurrent transformers

**Thinking Deeper, Not Longer: Depth-Recurrent Transformers for Compositional Generalization** (Chen, 2026)

Source: https://arxiv.org/abs/2603.21676

Core idea:

- reuse shared weights recursively through latent depth;
- trade recurrence steps for computation depth without linearly increasing parameter count.

INVERTED-brain implication:

- a compact model could allocate more internal compute only when task complexity demands it;
- reasoning depth can become a routed resource;
- this aligns with D4’s need for bounded/conditional deliberation.

Required project question:

> Can a small recurrent core learn an empirically grounded stop/continue/escalate policy better than a fixed-depth model?

## 13.3 Brain hypothesis

A promising future model architecture is therefore not necessarily “one 70B dense model squeezed smaller.”

It may be:

```text
small shared reasoning core
+ recurrent/adaptive depth
+ compact internal state
+ task-conditioned information gating
+ sparse specialist capacity
+ external deterministic execution/verification
```

This remains a research hypothesis until Harvest D establishes which functions deserve internalization.

---

# 14. INVERTED BRAIN — SPARSE EXPERT / SPECIALIST RESEARCH

## 14.1 MoE-LPR

**MoE-LPR: Multilingual Extension of Large Language Models Through Mixture-of-Experts with Language Priors Routing** (Zhou et al., AAAI 2025)

Source: https://ojs.aaai.org/index.php/AAAI/article/view/34805

Retained mechanism:

- freeze original parameters;
- add experts for new capability;
- route selectively;
- use small replay to preserve old capability.

INVERTED-brain implication:

- new expert capacity may be added without rewriting the whole base brain;
- a capability ratchet could potentially add specialists while protecting verified base behavior;
- routing and catastrophic-forgetting control are central.

## 14.2 Expert pruning/skipping

**Not All Experts are Equal: Efficient Expert Pruning and Skipping for Mixture-of-Experts Large Language Models** (Lu et al., ACL 2024)

Source: https://aclanthology.org/2024.acl-long.334/

**Cluster-Driven Expert Pruning for Mixture-of-Experts Large Language Models** (Guo et al., 2025)

Source: https://arxiv.org/abs/2504.07807

**Dropping Experts, Recombining Neurons: Retraining-Free Pruning for Sparse Mixture-of-Experts LLMs** (Zhou et al., 2025)

Source: https://aclanthology.org/2025.findings-emnlp.820/

**STUN: Structured-Then-Unstructured Pruning for Scalable MoE Pruning** (Lee et al., ACL 2025)

Source: https://aclanthology.org/2025.acl-long.671/

Retained implication:

- expert redundancy exists;
- task-specific and task-agnostic pruning can remove capacity;
- total model parameter count need not equal active inference capacity;
- expert-level structure may be a practical way to keep broad stored capability while activating only a small working set.

INVERTED-brain concept:

```text
GENERAL REASONING CORE
   |
   +-- state/evidence specialist
   +-- code/tool specialist
   +-- diagnosis specialist
   +-- recovery specialist
   +-- domain specialist(s)

ROUTER activates only what the current evidence state justifies.
```

Critical warning:

Token-by-token expert swapping from SSD is likely impractical due to bandwidth/latency.

Prefer:

- task/session-level expert selection;
- warm RAM cache;
- prefetch specialists before the reasoning segment;
- persistent expert set during a local episode.

---

# 15. INVERTED BRAIN — MEMORY / STORAGE HIERARCHY

Given current hardware, the likely useful hierarchy is:

## VRAM — hot cognition

Keep:

- active reasoning core;
- active specialists/experts;
- current compact state;
- current KV/cache;
- immediate typed action frontier.

## RAM — warm support

Keep:

- likely-next experts;
- recent state/history summaries;
- indexes;
- retrieved verified procedures;
- active manuals/knowledge chunks;
- failure exemplars relevant to current task.

## NVMe — cold durable knowledge

Keep:

- inactive specialists;
- manuals;
- repo history;
- verified failure archive;
- promoted skills;
- domain databases;
- training/replay trajectories;
- long-tail knowledge.

Operating principle:

> **Prefetch by task/episode; do not page experts per token.**

The system should measure whether the load/prefetch cost pays for capability before adopting a complex streaming design.

---

# 16. INVERTED BRAIN — KNOWLEDGE INSERTION / TEXT-TO-STATE

A major long-term idea is to reduce the amount of prose a reasoning model must process.

Instead of:

```text
raw manual / logs / documentation / history
 -> enormous natural-language prompt
 -> model tries to rediscover structure
```

use:

```text
RAW TEXT / LOG / DOC
       |
       v
DETERMINISTIC / VERIFIED PARSER-COMPILER
       |
       v
CANONICAL STRUCTURED REPRESENTATION
  facts
  entities
  state
  dependencies
  evidence
  authority
  actions
  uncertainty
  provenance
       |
       v
COMPACT MODEL INTERFACE
```

Potential representations:

- typed records;
- graphs;
- tensors/embeddings with explicit provenance;
- state-transition objects;
- dependency DAGs;
- action schemas;
- evidence sets.

The future model could consume a machine-oriented representation directly rather than repeatedly tokenizing natural language.

This is not yet proven to reduce training cost or improve capability. It is a major brain hypothesis to be tested after external information tomography identifies what the model actually needs.

---

# 17. INVERTED BRAIN — TYPED SEMANTIC ACTIONS

The model should not spend unnecessary capacity learning every shell/program syntax variant when a deterministic compiler can own syntax.

Preferred training/inference target:

```text
state + goal + evidence
 -> typed semantic action
```

Example:

```text
SwitchBranch(repo="X", branch="main")
```

System compiler:

```text
PowerShell / Bash / Git exact command
```

Benefits to test:

- reduced syntax failure;
- smaller action vocabulary;
- easier authority checks;
- easier deterministic verification;
- less training devoted to surface forms;
- safer cross-platform execution.

The model should learn **what transition is needed**, while deterministic code can often own **how the exact command is spelled**.

---

# 18. INVERTED BRAIN — TRAINING TRAJECTORY

The desired training object is not merely prompt→answer.

The project should preserve trajectories like:

```text
TASK
 -> STATE ESTIMATE
 -> INFORMATION SELECTED
 -> INFORMATION OMITTED + REASON
 -> ACTION FRONTIER
 -> DECISION
 -> ACTION
 -> STATE TRANSITION
 -> VERIFICATION
 -> FIRST ERROR IF ANY
 -> DIAGNOSIS
 -> RECOVERY CHOICE
 -> RECOVERY RESULT
 -> FINAL VERIFIED STATE
```

Training signals can be separated:

- state-estimation loss;
- relevance/information-selection loss;
- action-frontier loss;
- semantic-action loss;
- uncertainty/routing loss;
- first-error localization loss;
- recovery-selection loss;
- final-outcome loss;
- efficiency/compute penalty;
- negative-transfer penalty;
- hard-invariant violation penalty.

This separation is important because D3 has repeatedly shown that bundling all failures into one final score hides the actual mechanism.

---

# 19. INVERTED BRAIN — WHAT MUST REMAIN EXTERNAL UNTIL PROVEN OTHERWISE

Even if internal brain research succeeds, the following should remain outside the neural model by default:

- real canonical state;
- authorization credentials/consumption;
- least-privilege policy;
- hard safety/business invariants;
- irreversible execution authority;
- transaction commit truth;
- effect reconciliation;
- duplicate-effect fencing;
- cryptographic provenance;
- independent verification;
- final success/failure state;
- rollback/compensation authority;
- sealed/oracle truth.

Reason:

These are enforceable guarantees, not merely reasoning tasks.

A neural model may advise these systems. It should not become their sole authority without extraordinarily strong evidence.

---

# 20. INVERTED BRAIN — WHAT MAY EVENTUALLY MOVE INTERNAL

Candidates for internalization after causal proof:

- compact state abstraction;
- relevance selection;
- information prioritization;
- missing-information prediction;
- action-frontier ranking;
- dependency/decomposition representation;
- uncertainty/novelty detection;
- adaptive reasoning depth;
- semantic routing;
- first-error localization;
- recovery proposal;
- specialist/expert routing;
- reusable procedural pattern recognition.

Promotion criterion:

Internalizing a mechanism must preserve or improve:

- semantic correctness;
- hard-invariant performance;
- routing precision;
- recovery;
- generalization;
- latency/resource efficiency;

while reducing external machinery enough to pay complexity rent.

---

# 21. INVERTED BRAIN — CORE HYPOTHESES TO PROVE OR KILL

B1. A compact reasoning core with explicit structured state can match a larger text-heavy model on routine/known tasks.

B2. Model-specific information selection produces more capability than universal full-context prompting.

B3. Adaptive/recurrent reasoning depth can preserve hard-task capability while avoiding Qwen-style overthinking/context exhaustion on routine tasks.

B4. An externally trained relevance/action-frontier policy can later be distilled/internalized without losing causal benefit.

B5. Typed semantic actions reduce model burden without shrinking capability.

B6. Sparse specialists can expand stored capability while keeping active working-set size inside the local resource envelope.

B7. Task-level expert prefetch is fast enough; token-level SSD expert streaming is probably not.

B8. Failure/recovery trajectories create reusable competence that ordinary success-only training misses.

B9. Stronger-model discoveries can be converted into durable small-model/system capability through a verified knowledge ratchet.

B10. The best final brain may use fewer parameters for general reasoning but more **structured external knowledge/capability** than a conventional dense model.

B11. A learned internal brain must still be wrapped by external authority/state/verification boundaries.

B12. External INVERTED mechanisms that do not survive ablation should **not** be trained into the brain.

---

# 22. CAPABILITY RATCHET / MODEL-MENTORING RESEARCH DIRECTION

The project has repeatedly considered a stronger model mentoring a weaker model.

The useful version is not unrestricted teacher advice.

Preferred lifecycle:

```text
SMALL MODEL FAILS
       |
       v
STRONG MODEL INVESTIGATES
       |
       v
CAUSAL HYPOTHESIS / RECOVERY / PROCEDURE
       |
       v
TARGETED + SHAM REPLAY
       |
       v
FRESH GENERALIZATION
       |
       v
REGRESSION
       |
       v
PROMOTED EXTERNAL SKILL / RULE / DATA
       |
       v
SMALL MODEL OR SYSTEM REUSES IT
       |
       v
STRONG MODEL CALL RETIRED IF POSSIBLE
```

Metrics:

- Qwen retirement rate;
- small-model takeover rate;
- knowledge reuse rate;
- capability expansion rate;
- negative-transfer rate;
- regression rate.

The strongest model is both:

- executor for tasks outside the small-model envelope;
- explorer for novel failures.

It is not final authority over its own proposed knowledge.

---

# 23. PROPOSED PERMANENT GOVERNANCE CORRECTION — CLAIM-SPACE ADEQUACY LAW

The D3-Closure undercoverage discovery exposed a governance gap separate from the Pre-Test Blocker Law.

The repository must permanently enforce the following principle:

> **No experiment may claim to optimize, minimize, identify a best configuration, establish a boundary, or generalize across a variable space unless the experiment first maps that claim space and demonstrates that its design has enough coverage/resolution to support the claim.**

Required pre-inference claim-space audit for consequential experiments:

1. state the exact claim;
2. enumerate material independent factors;
3. enumerate factor levels;
4. identify plausible interactions;
5. calculate full theoretical combination count where meaningful;
6. model-free eliminate duplicates/no-ops/impossible/dominated conditions;
7. choose the design objective: comparison, screening, interaction localization, optimization, minimality, boundary finding, or confirmation;
8. choose an experimental design appropriate to that objective;
9. report expected factor/t-way coverage;
10. derive physical-call depth from variance/effect-size/decision threshold rather than intuition;
11. preserve budget for interactions/local search if screening finds important factors;
12. reserve fresh confirmation separate from tuning;
13. state what untested regions remain and why they cannot overturn the authorized conclusion.

Forbidden inference patterns:

- testing 2–3 handpicked variants and calling the winner globally best;
- calling a handcrafted packet “minimum” without ablation;
- calling an amount curve optimized after only endpoint comparison;
- claiming no interaction because it was never sampled;
- treating call ceiling as evidence coverage;
- confusing many calls with broad factor coverage;
- confusing broad factor coverage with adequate per-factor statistical depth.

If claim-space adequacy is not demonstrated, the result must be labeled **SCREENING ONLY**, **LOCAL RESULT**, or **UNRESOLVED**, never global/optimal/minimum.

This law should become canonical in `REPO_LAWS_AND_REGULATIONS.md` before physical execution of the redesigned campaign.

---

# 24. TEST AUTHORIZATION STATUS AFTER THIS DOSSIER

The currently implemented D4→D3-Closure chain is valuable harness work, but broad physical execution should remain **HOLD** until the claim-space adequacy correction is implemented.

The following must occur first:

1. freeze D3-v1 historical evidence;
2. retain the repaired D4 call-policy gate;
3. retain the repaired semantic/disposition/authority/recovery/provenance machinery;
4. replace the narrow information block with zero-call search-space enumeration;
5. add reproducibility calibration;
6. add factor-screen design;
7. add interaction/t-way coverage accounting;
8. add adaptive elimination/local optimization;
9. implement real recovery transitions rather than synthetic-only recovery records;
10. derive the new physical-call ceiling from the final design;
11. protect fresh confirmation;
12. run the Pre-Test Blocker and Run-Failure Audit;
13. run the Claim-Space Adequacy Audit;
14. only then authorize physical inference.

---

# 25. REQUIRED FINAL ARTIFACTS

By the end of Harvest D / corrected closure testing, the repository should be able to generate at least:

## Evidence / provenance

- immutable raw call ledger;
- exact model IDs and digests;
- generation/runtime settings;
- environment/hardware identity;
- model residency/resource telemetry where available;
- case/partition hashes;
- scheduler decisions;
- crash/resume journal;
- checksums/manifests;
- missingness/protocol-violation logs.

## Model capability

- raw model capability map;
- supported model capability map;
- model substitution frontier;
- 9.6–13 GB candidate comparison where needed;
- Qwen operating-policy evidence;
- routing regret/precision/recall.

## Information

- complete factor-space manifest;
- pruned candidate-space manifest;
- coverage matrix;
- information field value map;
- amount curve;
- representation map;
- ordering map;
- placement/timing map;
- model-specific MSIP policy;
- negative-transfer map.

## Assistance / system control

- A1–A11 mechanism map;
- minimum required scaffolding;
- disposition compiler evidence;
- authority guard evidence;
- verifier evidence;
- action-space-shaping analysis.

## Failure / recovery

- first-divergence atlas;
- prevention map;
- recovery map;
- recovery failure/migration map;
- retry safety boundary;
- unresolved failure registry.

## Architecture

- responsibility contract;
- mechanism classification;
- model/system boundary;
- routing policy;
- architecture substitution metrics;
- complexity-rent accounting;
- Test 5 handoff.

## Brain

- externally proven functions eligible for internalization;
- functions rejected for internalization;
- brain training-schema requirements;
- structured-state/action vocabulary;
- recurrent-depth hypothesis status;
- expert/specialist hypothesis status;
- memory hierarchy requirements;
- capability-ratchet training set;
- external deterministic boundary that must remain.

---

# 26. SOURCE CATALOG

## Internal repository sources

- `REPO_LAWS_AND_REGULATIONS.md`
- `INVERTED_CONSTITUTION.md`
- `TESTING.md`
- `docs/research/2026-09-02-harvest-d-research-synthesis.md`
- `docs/harvest-d-d2-closure.md`
- `docs/harvest-d-d2-measurement-correction.md`
- `docs/harvest-d-test5-handoff-schema.md`
- `docs/superpowers/specs/2026-08-30-inverted-architecture-benchmark-design.md`
- `docs/superpowers/specs/2026-09-01-adaptive-evidence-discovery-campaign-design.md`
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-automated-information-control-tomography.md`
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-post-run-adaptive-evidence-deepening-addendum.md`
- `docs/superpowers/specs/2026-09-03-harvest-d-d3-closure-v2-design.md`
- `docs/superpowers/plans/2026-09-03-harvest-d-d3-automated-tomography.md`
- `docs/superpowers/plans/2026-09-03-harvest-d-d3-closure-v2.md`

## External research — verified source anchors

### Experimental design / combinatorial search

- NIST, Fractional Factorial Designs: https://www.itl.nist.gov/div898/handbook/pri/section3/pri3345.htm
- NIST, Selecting an Experimental Design: https://www.itl.nist.gov/div898/handbook/pri/section3/pri33.htm
- NIST, Combinatorial Testing: https://www.nist.gov/publications/combinatorial-testing
- NISTIR 7878, Combinatorial Coverage Measurement: https://csrc.nist.gov/pubs/ir/7878/final
- NIST Covering Array Tables / ACTS: https://www.nist.gov/itl/math/nist-covering-array-tables
- Audibert & Bubeck, Best Arm Identification in Multi-Armed Bandits: https://www.microsoft.com/en-us/research/publication/best-arm-identification-multi-armed-bandits/
- Shahrampour et al., Sequential Elimination Algorithms for Best-Arm Identification: https://arxiv.org/abs/1609.02606

### Information/context/scaffolding

- Kim et al., Guiding Reasoning in Small Language Models with LLM Assistance / SMART: https://arxiv.org/abs/2504.09923
- McClendon et al., Three Roles, One Model: https://arxiv.org/abs/2604.11465
- Kang et al., ACON: https://arxiv.org/abs/2510.00615
- ACON code: https://github.com/microsoft/acon
- Du et al., Context Length Alone Hurts LLM Performance Despite Perfect Retrieval: https://aclanthology.org/2025.findings-emnlp.1264/
- Liu et al., Lost in the Middle: https://aclanthology.org/2024.tacl-1.9/
- Chen et al., Premise Order Matters: https://proceedings.mlr.press/v235/chen24i.html
- Code-Guided Reasoning for Small Language Models: https://huggingface.co/papers/2605.18827

### Routing/action-space

- Chuang et al., Confident or Seek Stronger: https://arxiv.org/abs/2502.04428
- Babu & Iyer, ToolChoiceConfusion / CMTF: https://arxiv.org/abs/2606.06284
- CMTF code: https://github.com/R-Suresh/ToolChoiceConfusion
- Babu & Shukla, GIST-CMTF: https://arxiv.org/abs/2606.16813

### Failure/recovery/evaluation

- Vuddanti et al., PALADIN: https://arxiv.org/abs/2509.25238
- PALADIN code: https://github.com/33k0/PALADIN-Framework
- Fan et al., AgentProcessBench: https://arxiv.org/abs/2603.14465
- AgentDebug: https://github.com/ulab-uiuc/AgentDebug
- Gurram, Auditing Automated Evaluation, Error Propagation, and Runtime Mitigation: https://arxiv.org/abs/2604.16706
- Success Is Not Self-Explanatory: https://arxiv.org/abs/2607.24054
- Credit Without Ground Truth: https://arxiv.org/abs/2608.19760

### Reasoning depth / overthinking

- Liu et al., Mind Your Step (by Step): https://proceedings.mlr.press/v267/liu25t.html
- Jin et al., Reasoning Can Hurt the Inductive Abilities of LLMs: https://arxiv.org/abs/2505.24225
- DeepMind, Towards Structural Understanding of LLM Overthinking: https://deepmind.google/research/publications/203490/

### INVERTED brain / latent/recurrent/sparse experts

- Hao et al., Training Large Language Models to Reason in a Continuous Latent Space / Coconut: https://arxiv.org/abs/2412.06769
- Chen, Thinking Deeper, Not Longer: Depth-Recurrent Transformers: https://arxiv.org/abs/2603.21676
- Zhou et al., MoE-LPR: https://ojs.aaai.org/index.php/AAAI/article/view/34805
- Lu et al., Not All Experts are Equal: https://aclanthology.org/2024.acl-long.334/
- Guo et al., Cluster-Driven Expert Pruning: https://arxiv.org/abs/2504.07807
- Zhou et al., Dropping Experts, Recombining Neurons: https://aclanthology.org/2025.findings-emnlp.820/
- Lee et al., STUN: https://aclanthology.org/2025.acl-long.671/

---

# 27. FINAL RESEARCH POSITION

The strongest current interpretation is:

1. INVERTED’s value is not a single inverted executor/auditor trick. It is a **responsibility and information architecture** around imperfect cognition.
2. The residual model failures are not explained by parameter count alone.
3. System-owned disposition/authority/verification appears extremely promising and should be kept outside model cognition unless falsified.
4. Qwen’s D3-v1 result strongly indicates that uncontrolled deliberation can destroy an otherwise capable model’s usable output.
5. Information quality, amount, order, position, and representation can independently change model performance.
6. Support can help one model and harm another.
7. Action-space reduction can create large reliability gains without increasing raw reasoning intelligence.
8. Failure detection and recovery are separate capabilities and must be trained/tested separately.
9. The information-policy space is combinatorial; it requires real DOE/combinatorial/adaptive-search methodology.
10. The correct target is likely a **conditional information/support policy**, not one universal prompt.
11. The final local model is allowed to live in the **9.6–13 GB footprint range** when that additional footprint buys verified capability.
12. The eventual INVERTED brain should be trained from externally proven causal mechanisms, not designed from analogy alone.
13. A promising long-term brain is a compact recurrent reasoning core with structured state, adaptive depth, typed semantic actions, sparse specialists, and a hierarchical memory system.
14. Real authority, state truth, irreversible execution, invariants, provenance, and independent verification should remain external by default.
15. The next physical testing campaign should not begin until claim-space adequacy is explicitly proven and the information search is redesigned accordingly.

The end state sought by this research is:

> **A system where the smallest practical local cognition receives exactly the information and action space it needs, reasons only as deeply as the task requires, hands typed semantic intent to a deterministic trusted boundary, learns from verified failures without corrupting prior capability, and escalates to stronger cognition only when the evidence state proves it is necessary.**
