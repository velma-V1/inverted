# Test-3 S1-R2 Expanded Category Fixed-Order Screen — Design

Date: 2026-09-01
Status: APPROVED DESIGN — NO S1-R2 TIER-A INFERENCE AUTHORIZED YET
Branch: `build/test3-s1-fixed-stack-order`
Predecessor protocol: `S1-R1`
Campaign design: `docs/superpowers/specs/2026-09-01-adaptive-evidence-discovery-campaign-design.md`

## 1. Purpose

S1-R2 is the next corrective fixed-stack/order experiment for Test-3 Section 1. It expands the causal screen from the narrow S1-R1 task surface to six task families while preserving the intervention structure needed to answer the same causal question:

> Does fixed component order have enough causal value to justify further fixed-stack optimization?

S1-R2 does not change the model pair, four-arm comparison, component vocabulary, two-call intervention exposure rule, verifier authority, or hidden-gold policy. It increases only the breadth and number of matched task cases.

The invalid original 24-call S1 run remains preserved as forensic evidence and is not eligible for primary causal claims. S1-R1 remains immutable as the corrective predecessor protocol. S1-R2 is a new revision and must not rewrite S1-R1 evidence, code-level provenance, or interpretation.

## 2. Exact experiment budget

S1-R2 freezes the following exact physical-call schedule:

```text
25 matched tasks
× 4 frozen arms
× 2 physical model calls per arm-task
= 200 exact physical model calls
```

Budget requirements:

- exact total physical calls: `200`
- arm count: `4`
- exact physical calls per arm: `50`
- matched tasks per arm: `25`
- exact physical calls per arm-task: `2`
- no model cache hits
- no model-adapter internal retries
- no transport retries that silently add model inference
- no outcome-dependent early stopping
- any deviation from the exact schedule invalidates the primary S1-R2 causal verdict

Unused calls are not permitted in a valid completed S1-R2 run. A runtime or infrastructure interruption may preserve a partial forensic packet, but that packet must be labeled `INVALID_FOR_PRIMARY_S1_R2_CAUSAL_CLAIM`.

## 3. Frozen arms

S1-R2 retains the four Section-1 causal arms and their semantics:

1. `S1-A0` — best single-model baseline
2. `S1-A1` — current best fixed hybrid/order from the S0 production-only ranking
3. `S1-A2` — alternate fixed order from the S0 production-only ranking
4. `S1-A3` — deterministic random-order negative control over production components

The fixed/order production component vocabulary remains:

- `requirement_validator`
- `retry`
- `targeted_repair`
- `final_validator`

`oracle_auditor` remains analysis-only and is forbidden from every production S1-R2 arm.

The same frozen model roles remain:

- best-single/executor model: resolved from committed Test-2 Tier-A evidence
- repair model: resolved from committed Test-2 role-champion evidence

At the current evidence freeze these resolve to:

- `qwen3.5:9b-q8_0`
- `cogito:3b-v1-preview-llama-q8_0`

The CLI must still resolve and report these from evidence rather than trusting hard-coded names as provenance.

## 4. Holdout A-R2

S1-R2 uses a fresh deterministic holdout named `A-R2`.

A-R2 requirements:

- exactly 25 cases
- deterministic construction from preregistered seeds
- seed range disjoint from original Holdout A, S1-R1 Holdout A-R1, Test-2 holdouts, and later Test-3 holdouts
- no model outcome may influence task selection, complexity, seed, or family allocation
- same ordered 25-case sequence presented to every arm
- hidden target state and hidden benchmark metadata never enter model prompts
- all task definitions and seed metadata retained in the forensic evidence packet

S1-R2 is the intended next local Tier-A Section-1 run. A real S1-R1 run is not required first; R1 remains the frozen narrower predecessor protocol.

## 5. Six task families

A-R2 contains six task families. Each family contributes exactly four preregistered cases, one at each complexity level 1–4. The 25th case is an additional Level-4 repair-containment stress case.

### 5.1 Existing: state

Purpose: test direct state transformation under multiple machine-checkable requirements.

Core failure modes:

- omitted requirement
- wrong value
- unintended state mutation
- critical final requirement failure at higher complexity

### 5.2 Existing: policy

Purpose: test procedural constraints and action ordering, including forbidden operations.

Core failure modes:

- ordering violation
- forbidden procedure
- missing required state transition
- locally plausible output that violates process constraints

### 5.3 Existing: reconciliation

Purpose: test selection of the correct value from conflicting sources using explicit source-priority rules.

Core failure modes:

- stale-source selection
- unresolved field
- wrong canonical value
- partial reconciliation

### 5.4 New: preservation

Purpose: test whether the system can make required changes while preserving already-correct or protected state.

Construction principles:

- at least one required mutable target
- at least one public `preserve` invariant
- protected state begins correct
- valid solution changes only required mutable paths
- higher complexity increases the number of mutable and preserved fields
- critical preservation failures are allowed at high complexity for catastrophe measurement

Primary failure signal:

> Did the intervention satisfy requested changes without damaging state that was explicitly required to remain unchanged?

### 5.5 New: dependency/order

Purpose: test multi-step prerequisite structure where individually valid actions fail if sequenced incorrectly.

Construction principles:

- use existing public requirement types such as `action_present` and `action_before`
- include at least one prerequisite action and one dependent action
- higher complexity adds independent state requirements and/or additional ordering pressure without introducing hidden rules
- the valid sequence must be derivable entirely from the public task payload

Primary failure signal:

> Can the fixed component order recover a task whose correctness depends on operation dependencies rather than only final state values?

### 5.6 New: repair containment

Purpose: test whether targeted recovery fixes a localized verified defect without regressing already-correct requirements or introducing new side effects.

Construction principles:

- initial deterministic seed candidate contains a preregistered localized defect
- several other public requirements begin satisfied
- at least one explicit preservation or no-side-effect invariant protects correct state
- successful repair must fix the seeded defect and preserve all previously correct requirements
- the model is never told hidden fault metadata; it receives only public requirements, previous actions, and public-safe observed validator feedback

Primary failure signal:

> Does recovery remain contained to the failed region, or does it destroy previously correct work while appearing to repair the immediate defect?

The extra 25th A-R2 case is a Level-4 repair-containment stress case because mutation-induced regression is especially relevant to the `targeted_repair` versus `retry` order question.

## 6. A-R2 family/complexity allocation

The frozen allocation is:

| Family | L1 | L2 | L3 | L4 | Extra | Total |
|---|---:|---:|---:|---:|---:|---:|
| state | 1 | 1 | 1 | 1 | 0 | 4 |
| policy | 1 | 1 | 1 | 1 | 0 | 4 |
| reconciliation | 1 | 1 | 1 | 1 | 0 | 4 |
| preservation | 1 | 1 | 1 | 1 | 0 | 4 |
| dependency/order | 1 | 1 | 1 | 1 | 0 | 4 |
| repair containment | 1 | 1 | 1 | 1 | 1×L4 | 5 |
| **Total** | **6** | **6** | **6** | **6** | **1** | **25** |

The exact case order and seeds must be frozen in code tests before the first Tier-A S1-R2 call.

## 7. Seed-failure protocol

Every arm-task begins from the same zero-call deterministic failed candidate for that case.

Requirements:

- seed failure is generated before any model inference
- deterministic verifier confirms the seed candidate fails
- identical seed candidate/actions are supplied to all four arms for a matched case
- injected-fault metadata is retained for forensic analysis but never rendered into model prompts
- no hidden target state, `critical` flag, hidden-gold label, injected-fault label, or non-public benchmark metadata may enter executor or repair prompts

For ordinary families, deterministic fault injection may be used if it guarantees a genuine failed state.

For repair-containment cases, the seed defect must be deterministic and localized so the experiment can measure regression of requirements that were already correct at intervention start. The evidence packet must record the set of requirements satisfied before intervention and whether each remains satisfied afterward.

## 8. Two-call intervention exposure contract

Each arm-task consumes exactly two physical model calls.

The two calls are an equal-compute exposure budget, not permission for hidden retries.

Rules:

- at least one of the two calls must be an active intervention
- if a second planned model operation is no longer causally active because an earlier operation has already produced/locked the selected candidate, it executes as a shadow call
- shadow outputs are recorded but mathematically forbidden from changing the selected candidate or verdict
- active and shadow token/latency accounting remain separate
- cache is disabled for every active and shadow call
- any arm-task with fewer or more than two physical calls invalidates the completed R2 protocol

For fixed/order arms, the runtime must reject any component order that can reach terminal `final_validator` before any model-call component receives active intervention exposure.

## 9. Public-information boundary

Executor prompts may contain only:

- public task ID/family/complexity
- public goal
- public initial state
- public allowed operations
- public machine-checkable requirements

Repair prompts may additionally contain:

- previous candidate actions
- public-safe observed validator feedback for failed public requirements

Repair feedback must not contain:

- `critical`
- hidden target state
- hidden-gold result
- injected fault class
- oracle-only metadata
- benchmark-only labels not present in the public task

Hidden-gold and semantic evaluators may score outputs after inference for experiment measurement, but their hidden data cannot influence production-arm model prompts or action selection.

## 10. Primary outcomes

The primary causal unit is the matched task across all four arms.

Primary measurements:

- verified success per arm
- matched wins/losses/ties versus `S1-A0`
- matched wins/losses/ties versus `S1-A3`
- net wins
- catastrophic failures added/removed
- intervention exposure validity
- exact physical-call compliance

Primary Section-1 interpretation remains based on whether fixed order produces a large, stable causal effect relative to both baseline and random-order control.

A null or small effect remains non-dispositive for very small effects because S1-R2 is still a bounded screen, not the 260-cluster full-power experiment estimated by S0.

## 11. New category-level outcomes

R2 adds family-level analysis so aggregate performance cannot hide category-specific architecture effects.

Required per-family outputs:

- task count
- successes/failures per arm
- matched net wins versus baseline
- matched net wins versus random control
- catastrophe count
- mean physical calls (must equal 2 per arm-task)
- token and latency summaries
- active/shadow call counts

Additional family-specific metrics:

### Preservation

- preservation violations
- requested-change success with preservation intact
- collateral state corruption count

### Dependency/order

- action-order violations
- missing prerequisite/dependent actions
- final-state pass with procedural failure count where applicable

### Repair containment

- initially satisfied public requirements
- initially failed public requirements
- failed requirements repaired
- previously satisfied requirements regressed
- new failures introduced
- containment success rate
- repair regression rate

## 12. Protocol validity gate

A primary S1-R2 verdict is authorized only if all are true:

- `protocol_revision == S1-R2`
- `holdout == A-R2`
- `matched_tasks == 25`
- `arm_count == 4`
- `physical_model_calls == 200`
- each arm uses exactly 50 physical calls
- each of 100 arm-task trials uses exactly 2 physical calls
- every seed failure is deterministically verified
- every arm-task has at least one active intervention call
- no cache hit occurs
- no model adapter has internal retries enabled
- no analysis-only component enters a production arm
- prompt leakage scans find no hidden/non-public benchmark fields
- all 25 tasks are matched across all four arms
- all six required families and frozen complexity allocation are present

If any condition fails, the result must be labeled:

`INVALID_FOR_PRIMARY_S1_R2_CAUSAL_CLAIM`

The packet remains retained for forensic analysis.

## 13. Verdict classes

S1-R2 may emit one of:

- `S1_R2_FIXED_ORDER_LARGE_SIGNAL`
- `S1_R2_FIXED_ORDER_CATEGORY_CONDITIONAL_SIGNAL`
- `S1_R2_SCREEN_NON_DECISIVE`
- `S1_R2_FIXED_ORDER_NEGATIVE_OR_HARMFUL`
- `INVALID_FOR_PRIMARY_S1_R2_CAUSAL_CLAIM`

`CATEGORY_CONDITIONAL_SIGNAL` is used when aggregate effect is weak/non-decisive but one or more preregistered families show a coherent fixed-order advantage that is not accompanied by unacceptable catastrophe/regression growth. It is hypothesis-generating for later adaptive routing and does not justify claiming a universal fixed stack.

## 14. Evidence requirements

S1-R2 reuses the standard Test-3 evidence packet and adds R2-specific files where necessary.

At minimum preserve:

- `preregistration.json`
- `config.json`
- `provenance.json`
- `model_calls.jsonl`
- `events.jsonl`
- `trials.csv`
- `validator_results.csv`
- `transitions.csv`
- `failures.csv`
- `wins.csv`
- `losses.csv`
- `costs.csv`
- `latency.csv`
- `tokens.csv`
- `cache.csv`
- `effect_sizes.json`
- `failure_atlas.json`
- `verdict.json`
- `report.txt`
- `SHA256SUMS.csv`
- `COMPLETE-EVIDENCE.txt`

R2 additionally requires:

- `category-effects.csv`
- `containment-effects.csv`
- `protocol-validity.json`
- seed-failure provenance sufficient to prove matched starting states across arms

The packet must distinguish active-call outputs from shadow-call outputs and must never treat shadow output as causal outcome evidence.

## 15. R1 immutability and provenance

Implementation must preserve S1-R1 behavior and evidence semantics.

Required regression guarantees:

- existing S1-R1 tests remain green
- `S1-R1` remains exact 80 calls / 10 matched tasks / 20 calls per arm
- `A-R1` case seeds and schedule remain unchanged
- original invalid 24-call run remains explicitly classified as invalid primary evidence
- R2 uses separate protocol/holdout identifiers and evidence directories
- no R2 result is written into an R1 evidence path

Code may factor common execution mechanics into shared helpers only if regression tests prove the frozen R1 observable contract remains unchanged.

## 16. CI/TDD acceptance criteria

Implementation follows strict red-green TDD.

Before implementation, regression tests must fail for missing R2 behavior and explicitly cover:

1. exact 25-case A-R2 schedule and six-family allocation
2. seed disjointness from A and A-R1
3. new preservation task semantics
4. new dependency/order task semantics
5. localized repair-containment seed semantics
6. exact `25 × 4 × 2 = 200` runtime budget
7. exact 50 calls per arm
8. exact two calls per arm-task
9. active/shadow non-interference
10. R2 protocol-validity rejection on 199 or 201 calls
11. public-only prompt/repair-feedback boundary
12. no cache/internal retry
13. category-level analysis outputs
14. containment regression metrics
15. R1 exact-80 contract unchanged
16. short in-place terminal progress rendering without line wrapping

Final green light requires, on one final commit:

- full pytest suite
- S1-R2 200-call mock execution and protocol validation
- S1-R1 regression validation
- Test-2 validation
- reproducible S0 clean-clone scientific replay
- Linux supported Python matrix
- Windows Python/PowerShell integration matrix

No real Tier-A S1-R2 inference is authorized until all gates above are green and the local dry-plan reports the frozen R2 protocol exactly.

## 17. Local preflight contract

Before the first real R2 call, the local dry-plan must print at least:

```text
SECTION=S1_FIXED_STACK_ORDER
PROTOCOL_REVISION=S1-R2
HOLDOUT=A-R2
EXACT_BUDGET=200
ARM_COUNT=4
PER_ARM_CALL_CAP=50
CALLS_PER_ARM_TASK=2
MATCHED_TASKS=25
CATEGORY_COUNT=6
BEST_SINGLE_MODEL=<resolved from evidence>
REPAIR_MODEL=<resolved from evidence>
TIER_A_INFERENCE_AUTHORIZED=false
```

The real run requires an explicit Tier-A authorization flag and refuses to launch if the dry-plan/runtime contract does not resolve to the exact values above.

## 18. Interpretation boundary

S1-R2 is deliberately broader and stronger than S1-R1, but it is still a Section-1 screen.

It may support:

- a large universal fixed-order signal
- evidence that fixed order matters only for specific task/failure families
- evidence that fixed order is weak, neutral, or harmful
- identification of categories that should become routing features in Section 2

It may not by itself establish:

- a universally optimal architecture across arbitrary tasks
- a small-effect null below its statistical resolution
- adaptive routing superiority
- memory/mentor/verification claims reserved for later Test-3 sections

The purpose of the additional 120 calls is to buy **causal breadth and category resolution**, not to disguise more compute as architectural intelligence.
