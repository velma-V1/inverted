# Harvest D Research Synthesis — 2026-09-02

## Status

This document freezes the research conclusions that are allowed to shape Harvest D. It does not authorize architecture claims by itself. Raw immutable evidence outranks summaries, design documents, and model opinions.

Canonical evidence base for this branch: `0d67ba4e5578b4c14225eb83b726fd137dfffecd`.

## Project objective

INVERTED exists to minimize how much correctness depends on model intelligence by externalizing state, authority, evidence, verification, execution control, recovery, and reusable failure knowledge only where those mechanisms causally improve verified system behavior.

The target local anchor is Qwen3.5 9B. A future always-on 1–2B model is expected to handle routine work. The system must remain local-first, provider-agnostic, and fully functional with networking disabled and all cloud adapters removed.

## Evidence-grounded corrections

### S2

The frozen S2 run is complete and protocol-valid but explicitly non-decisive for architecture claims. It contains 72 matched cases, 360 trials, 720 physical model calls, 418 active inference calls, 302 shadow calls, 4 instrumentation anomalies, 4 stochastic divergences, 0 protocol failures, and verdict `S2_SCREEN_NON_DECISIVE`. `architecture_claims_authorized` is false.

S2 also exposed a key identifiability problem: model choice, recovery action, scaffold level, and router features were not cleanly separable. Harvest D must treat them as independent variables.

### Test 2

Test 2 already contains valuable diagnostic priors: model-task capability matrices, model-complexity curves, model-fault matrices, routing holdouts/regret, ablations, interactions, saturation, failure recovery matrices, and retry/repair threshold artifacts.

However, its primary verdict is `INCONCLUSIVE` because of `non_unique_physical_model_call_identity`. Therefore these artifacts may seed D0/D2/D4 case selection, but they are never promoted to certified capability boundaries.

### Harvest A/B/C

Harvest A demonstrated that a bundled INVERTED arm can be dramatically harmful, so Harvest D must test exact mechanisms rather than treating “INVERTED” as a single architecture.

Harvest B showed that checked disposition can be extremely strong and that richer behavior can add unnecessary evidence load or unjustified actions.

Harvest C showed positive architecture lift while leaving escalation, authority interpretation, and action correctness unresolved.

Combined lesson: every retained mechanism must pay measurable rent or enforce a hard invariant.

## Architecture ranking

Broad architecture search is closed unless a Harvest D result exposes a new design-changing unknown.

The leading family is a runtime-assured AI control plane / minimal deterministic trusted execution kernel:

1. user objective / task contract
2. system-owned canonical state + uncertainty
3. plan/decomposition
4. admissible-action / evidence-acquisition layer
5. untrusted model for semantic cognition
6. proof-carrying action
7. trusted kernel for state/version, provenance, preconditions, authority, temporal policy, invariants, consequence/reversibility, transaction/effect staging, fencing, and commit
8. independent postcondition verification
9. durable/event-sourced commit
10. recovery supervisor
11. verified experience / promoted knowledge

The model must not own canonical state, authorization, commit authority, irreversible execution authority, transaction truth, or final self-certification.

## Core laws

1. Truth lives outside the unreliable component.
2. Every consequential effect crosses a non-bypassable boundary.
3. The trusted boundary is much smaller than the governed capability.
4. Authority is explicit, scoped, revocable, and durably consumed.
5. State transitions are the correctness unit.
6. Safety is expressed as invariants over states/transitions.
7. Record enough before mutation to reconstruct/recover.
8. Recovery authority is independent from the failed component.
9. Irreversible actions require stronger evidence.
10. Uncertainty is explicit.
11. Context is a cache/view, never canonical state.
12. DONE is system state, not a model statement.
13. Tool descriptions/results/provider outputs are untrusted claims.
14. Rollback is a new transition, not time travel; prior effects and consumed authority remain real.
15. The verifier/world model is itself an attack surface.

## Model frontier objective

Harvest D must measure three boundaries per model/capability:

- `B0`: raw model boundary
- `B1`: model + proven INVERTED support
- `B2`: model + maximum proven INVERTED support

For Qwen:

- `Q0`: raw Qwen frontier
- `Q1`: Qwen + normal INVERTED
- `Q2`: Qwen + maximum proven INVERTED

Primary metrics:

- `SDI = Gap_assisted / Gap_raw`
- `FRONTIER_SHIFT = Boundary_assisted - Boundary_raw`
- `SUBSTITUTION_EFFICIENCY = added verified capability / added architecture cost`

The question is not merely whether Qwen is stronger. It is when extra structure beats invoking Qwen, when Qwen is genuinely necessary, and how far Qwen + INVERTED together can push the local frontier.

## System involvement objective

Harvest D must record system involvement by independent channels rather than one blended score:

- context assistance
- state assistance
- decomposition assistance
- evidence assistance
- action-space restriction
- verification assistance
- recovery assistance
- routing assistance
- authority intervention
- promoted-knowledge use

Derived metrics include Architecture Intervention Ratio, Intervention Value, and Minimum Required Scaffolding.

Optimization law is lexicographic:

1. hard invariants
2. semantic correctness
3. silent/unsafe failure
4. Qwen dependence
5. total model cost
6. system involvement
7. latency / implementation complexity

The target is the least involved architecture that preserves the strongest verified capability.

## Capability expansion over time

INVERTED must not merely route around current model limits. It must be able to use stronger-model discoveries to expand future system capability through a controlled external knowledge ratchet.

Qwen has two distinct roles:

- `QWEN_EXECUTOR`: solve work beyond the smaller model envelope
- `QWEN_EXPLORER`: investigate novel failures outside the known causal map

Qwen may diagnose, propose hypotheses, request evidence, and propose repairs. It may not authorize, commit, self-certify, or promote its own discoveries.

Promotion lifecycle:

`OBSERVED -> HYPOTHESIZED -> CAUSALLY_VERIFIED -> NEIGHBOR_GENERALIZED -> FRESH_GENERALIZED -> REGRESSION_SAFE -> PROMOTED`

Contradicted knowledge is suspended and rolled back through a versioned capability envelope.

Boundary-ratchet metrics:

- Capability Expansion Rate
- Qwen Retirement Rate
- Small-Model Takeover Rate
- Knowledge Reuse Rate
- Negative Transfer Rate
- Capability Regression Rate

A capability gain only counts if it expands verified territory without losing existing territory.

## First-class dispositions

Production/test dispositions are:

- `EXECUTE`
- `ACQUIRE_EVIDENCE`
- `ESCALATE`
- `SAFE_STOP`

Routing modes may include:

- `ROUTINE_LOCAL`
- `SCAFFOLDED_LOCAL`
- `QWEN_STANDARD`
- `QWEN_MAX`
- `NOVELTY_INVESTIGATION`

## Causal standard

Every promoted architecture claim follows:

`OBSERVATION -> FIRST MEANINGFUL DIVERGENCE -> CAUSAL HYPOTHESIS -> TARGETED INTERVENTION -> SHAM -> SAME PRE-FAILURE STATE REPLAY -> OUTCOME DELTA -> NEIGHBORING GENERALIZATION -> FRESH-FAMILY GENERALIZATION -> REGRESSION -> ARCHITECTURE INSTRUCTION`

A mechanism that sounds reasonable but does not beat its matched sham is rejected as a causal explanation.

## Hard invariants

Zero tolerance for certification:

- unauthorized catastrophic/irreversible action
- duplicate committed irreversible effect
- consumed authorization resurrection
- known invalid state silently committed
- material journal/replay inconsistency
- reward hacking / hidden-oracle tampering
- instrumentation/evidence corruption
- required cloud dependency for local/core mode
- kernel-policy bypass
- model self-certification

## Conceptual scope freeze

Harvest D is frozen to:

`D0 Evidence Closure -> D1 Deterministic Kernel -> D2 Model Capability Frontier -> D3 Architecture Substitution -> D4 Qwen Routing -> D5 Qwen + Maximum INVERTED -> D6 Purple-Unicorn Discovery -> D6B Capability Ratchet -> D7 Causal Closure`

Do not add categories because a mechanism sounds interesting. A new concept may enter only after an actual Harvest D result reveals a material unexplained failure that existing mechanisms cannot discriminate and that could change the responsibility boundary or architecture ranking.

## Relationship to later work

Harvest D shapes the architecture and closes responsibility/model-boundary uncertainty.

Test 5 becomes architecture optimization/compression: tune, compare, interact, delete, compress, minimize, freeze, certify.

Harvest E handles dev-agent/provider tomography such as Claude Code/Codex integration.

Test 6 is the sealed kill/prove/improve campaign with fresh untouched adversarial cases.