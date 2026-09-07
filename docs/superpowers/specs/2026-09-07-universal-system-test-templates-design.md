# Universal System Test Templates — Design Specification

## Status

Continuation of the owner-approved INVERTED universal-testing direction.

## Purpose

Build one reusable, falsifiable template contract for testing whole systems and the mechanisms inside them without creating a new bespoke benchmark for every system.

The first four profiles are the causal 2×2 core already implied by the project:

- `RAW` — model without Brain or INVERTED system support.
- `BRAIN` — model plus Brain only.
- `INVERTED_SYSTEM` — model plus INVERTED system only.
- `BRAIN_INVERTED` — model plus both.

The template layer does not assert that any profile is better. It defines what must be measured before a mechanism is allowed to survive.
## Decision the templates must close

For every system under test, determine:

1. whether the complete system materially improves verified capability over the same model raw;
2. which mechanisms cause that improvement or regression;
3. whether mechanisms are independent, enabling, synergistic, suppressive, redundant, or conditional;
4. where the effect disappears or reverses across model, task, difficulty, operating state, and resource conditions;
5. what the smallest architecture is that preserves the selected capability frontier.

Every surviving mechanism ends classified as exactly one of:

- `REQUIRED`
- `CONDITIONAL`
- `REDUNDANT`
- `HARMFUL`
- `UNRESOLVED`

No mechanism may be promoted from aggregate score alone.
## Causal geometry

The whole-system core is a matched 2×2 factorial:

| Brain | INVERTED | Profile |
|---|---|---|
| off | off | `RAW` |
| on | off | `BRAIN` |
| off | on | `INVERTED_SYSTEM` |
| on | on | `BRAIN_INVERTED` |

This resolves Brain main effect, INVERTED main effect, and Brain×INVERTED interaction without inventing redundant arms.

Inside a non-raw system, the template declares mechanisms explicitly. The planner generates only comparisons that can change a named decision:

- full-system versus raw;
- mechanism-isolated versus raw when isolation is semantically valid;
- leave-one-mechanism-out ablation for every mechanism that claims necessity;
- declared pair or higher-order interaction probes;
- negative/control conditions required to distinguish semantic effect from retry, formatting, additional-token, or additional-call effects.

The planner must not enumerate the full power set of mechanisms.
## Template contract

Every system template must freeze:

- `template_id`, `system_id`, schema version, and decision ID;
- the raw baseline and full-system mechanism set;
- mechanism IDs, descriptions, responsibility owners, expected causal role, and forbidden responsibilities;
- whether isolation and leave-one-out ablation are valid/required;
- explicitly justified interaction probes;
- task families and operating regions to which the test applies;
- primary metrics, hard safety/reliability gates, and efficiency metrics;
- evidence fields required for later zero-call reanalysis;
- allowed final dispositions and minimum evidence rules.

Responsibility ownership uses the project vocabulary:

`KERNEL`, `SYSTEM`, `MODEL`, `HYBRID`, `VERIFIER`, `RECOVERY`, `HUMAN`.

Model cognition and system authority remain distinct. A template may never move canonical authority, irreversible commit truth, or deterministic invariant ownership to the model merely to make an experimental arm easier to build.
## Evidence and scoring

Every comparison preserves raw immutable evidence plus a normalized comparison row. The template requires, at minimum:

- model/runtime identity and inference parameters;
- task/case/seed and execution position;
- exact active mechanism set and version/hash;
- model-visible inputs separated from system-known hidden/oracle state;
- candidate/action/state transitions and verifier results;
- failure taxonomy and first meaningful divergence;
- latency, tokens, calls, retries, and recovery actions;
- trigger eligibility and non-events when causally relevant;
- final oracle/verified outcome;
- comparison reason and decision it can change.

Primary interpretation is paired and slice-aware. A global mean may summarize results but cannot erase a high-consequence negative-transfer boundary or a model/region-specific reversal.

Infrastructure, provenance, capture, and scorer failures are not silently scored as semantic system failures. They remain explicit invalid/incomplete evidence classes.
## Initial template definitions

`RAW` contains no support mechanisms and exists only as the matched model baseline.

`BRAIN` initially represents the externalized cognition-support layer: canonical working context, evidence/state memory, uncertainty/failure state, decomposition/dependency support, and re-anchoring/recovery context. These are testable mechanism IDs, not assumed permanent components.

`INVERTED_SYSTEM` initially represents system-owned candidate generation/admissible-action control, deterministic state/invariant handling, semantic model auditing, independent verification, and recovery/commit fencing. Authority remains outside the model.

`BRAIN_INVERTED` composes the two sets without collapsing their identities. Its mandatory first interaction probe is the matched 2×2 whole-system comparison so overlap versus true compounding is directly measurable.

Future harvested systems use the same contract. They receive new mechanism manifests; they do not receive a new scoring philosophy or a bespoke benchmark unless their semantics make an existing comparison invalid.

## Non-goals

This layer does not run the expensive model campaign, fine-tune weights, replace HD-NEXT-2, rewrite the preserved six-arm benchmark, or claim Brain/INVERTED effectiveness before evidence exists.

It is a reusable preregistration and comparison-planning layer that makes future system tests comparable and prevents mechanisms from escaping causal scrutiny.
## Acceptance criteria

The template layer is complete for this stage when:

1. all four initial profiles load through one schema/validator;
2. `RAW` cannot accidentally contain mechanisms;
3. every non-raw mechanism has explicit ownership and a causal test requirement;
4. the Brain×INVERTED 2×2 comparison is generated deterministically;
5. required leave-one-out ablations are generated without full-power-set explosion;
6. declared interaction probes are generated only when their prerequisites exist;
7. duplicate IDs, unknown owners, invalid mechanism references, and authority-boundary violations fail preflight;
8. every generated comparison carries a named `decision_id` and reason;
9. the planner reports exact comparison count before any model call;
10. unit tests prove deterministic generation and invalid-template rejection;
11. existing repository tests remain green;
12. no real inference is launched by template validation or planning.