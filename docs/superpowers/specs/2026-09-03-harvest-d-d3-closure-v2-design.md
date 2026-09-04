# Harvest D D3-Closure v2 — Corrected Measurement and Model-Substitution Design

## Status

APPROVED IMPLEMENTATION DESIGN derived from the completed D3-v1 evidence package and governed by `REPO_LAWS_AND_REGULATIONS.md`, `INVERTED_CONSTITUTION.md`, `TESTING.md`, the frozen D3 specification, and the post-D3 adaptive evidence-deepening addendum.

This design does **not** modify, relabel, overwrite, or resume the completed D3-v1 campaign. D3-v1 remains frozen historical evidence. All corrected measurement and new inference work receives new protocol/run identities.

## 1. Objective

Build the smallest corrected measurement system capable of answering the architecture-changing questions D3-v1 failed to isolate:

> What is the smallest model, smallest sufficient information packet, and smallest required deterministic support set that produces the highest verified correctness while preserving hard invariants and minimizing model dependence?

The design must also separate model incapability from context exhaustion, specification failure, oracle/scoring failure, instrumentation failure, architecture failure, and recovery failure.

## 2. Frozen D3-v1 boundary

The D3-v1 campaign produced 632 physical calls under commit `171d492f6371292aebabaeb1b9487c28d4193995`. Those artifacts remain immutable.

No corrected scorer may be presented as original D3-v1 scoring. Any offline reinterpretation is labeled `D3-V1-POSTHOC-SALVAGE` with separate provenance.

The corrected test must use new run IDs, protocol version `D3-CLOSURE-v2`, new case partitions, and fresh sealed confirmation evidence.

## 3. Required pre-inference outputs

Before any new physical model call, the post-D3 zero-call analyzer must be able to generate:

- `post_d3_gap_registry.json`
- `post_d3_zero_call_findings.json`
- `post_d3_decision_impact_map.json`
- `post_d3_hypothesis_lineage.json`
- `post_d3_followup_routing.json`
- `post_d3_followup_test_spec.md`
- `post_d3_followup_budget_justification.json`

The analyzer must preserve raw evidence hierarchy and mark unsupported conclusions as unresolved rather than manufacturing causal claims.

## 4. Corrected responsibility boundary

The model is responsible for semantic interpretation and selecting a semantic answer/action from an explicitly valid answer/action vocabulary.

The system is responsible for:

- canonical state;
- authority;
- invariant enforcement;
- deterministic disposition compilation;
- irreversible-action admission;
- verification;
- recovery admission;
- final outcome classification.

The model is not required to invent hidden system dispositions.

### 4.1 Corrected score dimensions

Every physical model result records independently:

- `parseable_json`
- `schema_valid`
- `semantic_action_correct`
- `compiled_disposition_correct`
- `authority_correct`
- `hard_invariant_correct`
- `verified_outcome_correct`
- `format_valid`
- `context_exhausted`

Format validity may never zero out semantic correctness.

## 5. Information delivery repair

### 5.1 Amount must be real

`MINIMUM`, `COMPRESSED`, `MODERATE`, `FULL`, and `OVERLOADED` must render measurably different model-visible payloads.

Automated tests must prove:

- different amount variants produce distinct rendered hashes where intended;
- token/character burden is monotonic enough to distinguish the levels;
- truth conditions remain equivalent except where the protocol intentionally omits fields;
- overloaded context adds non-authoritative burden rather than changing the oracle.

### 5.2 Ordering must be real

Implement real semantic-preserving orderings:

- `TASK_OBJECTIVE_FIRST`
- `STATE_FIRST`
- `EVIDENCE_FIRST`
- `SAFETY_STATE_EVIDENCE_FIRST`
- `SHUFFLED_CONTROL`

`SHUFFLED_CONTROL` must use a frozen seed and actually change field order when more than one field is visible.

### 5.3 Representation remains orthogonal

Representation changes must preserve the same visible semantic field set unless the test explicitly changes information content.

## 6. Assistance repair

Assistance is split by responsibility.

### 6.1 Model-visible pre-decision assistance

These mechanisms may alter cognition and therefore require real pre-inference TARGET/OFF/SHAM comparisons:

- A1 canonical-state/version anchor
- A2 admissible-action frontier
- A3 evidence/missing-evidence support
- A4 dependency/decomposition support

The intervention must be present before the model answers. A post-response dictionary mutation is not causal assistance evidence.

### 6.2 System-owned deterministic assistance

These mechanisms operate after semantic proposal or directly on system state and should use deterministic replay where causally valid:

- A5 verifier/postcondition gate
- A6 disposition compiler
- A7 authority/least-privilege guard
- A8 consequence/reversibility guard
- A9 recovery controller
- A10 failure signature/guard
- A11 routing/escalation controller

A deterministic replay is scored by whether it changes an actual system decision/outcome class, not merely whether a dictionary differs.

## 7. Recovery trajectories

Every recovery-eligible case must preserve:

`initial state -> first meaningful divergence -> first detection -> failure class -> available recovery frontier -> selected recovery -> system admission/rejection -> resulting canonical state -> verifier/postcondition -> RECOVERED/MIGRATED/WORSENED/ESCALATED/SAFE_STOPPED`

Unknown external effect prohibits blind retry.

Recovery and prevention are separate measurements.

## 8. Adaptive scheduler repair

The scheduler must consume observed block results and classify each mechanism/comparison as:

- SUPERIOR
- NONINFERIOR
- HARMFUL
- FUTILE
- UNRESOLVED

Behavior:

- SUPERIOR: stop redundant screening; deepen/generalize/ablate the winning mechanism.
- HARMFUL: permit only the preregistered contradiction/boundary check, then bound or kill.
- FUTILE: stop ordinary spending.
- UNRESOLVED: select the smallest maximally discriminating next block.
- RESOLVED comparison: reallocate unused unsealed budget to the highest-value unresolved decision.

The scheduler may not alter oracles, sealed cases, authority, success criteria, or absolute budget ceilings.

## 9. D4 Qwen call-policy gate

Bounded Qwen deliberation is a D4 responsibility and must be frozen before Qwen participates in D3-Closure confirmatory inference.

The D4 gate distinguishes:

- semantic wrong answer;
- context/deliberation exhaustion;
- empty final answer after thinking;
- normal completed answer.

Maximum D4 physical calls: 48.

Candidate policies are preregistered and must include the current/default policy plus one or more policies that prevent unbounded context exhaustion. The exact supported runtime control is verified model-free against the installed runtime/configuration before spending calls.

D3-Closure consumes the winning D4 Qwen profile as frozen input and does not tune it internally.

## 10. D3-Closure v2 model set

Primary models:

- SMALL_A: `qwen2.5:1.5b-instruct-q8_0`
- QWEN: `qwen3.5:9b-q8_0` under the frozen D4 policy

Transition models are conditional only:

- 3B if needed to localize a residual model-size boundary;
- 3.8B only if the 3B boundary remains unresolved;
- 8B only for a residual near the Qwen boundary;
- 14B only to discriminate a model-capacity ceiling from a specification/oracle/architecture ceiling.

### 10.1 Local-model resource envelope

For the current local deployment target, **models in the 9.6 GB through 13 GB size/footprint range are explicitly tolerable and must not be rejected solely because they exceed the current ~9.6 GB Qwen anchor.**

Model selection and substitution analysis must therefore distinguish:

- parameter count;
- quantization;
- model artifact size;
- actual runtime-loaded memory footprint where observable;
- VRAM residency/spill behavior;
- RAM use;
- latency/throughput;
- and verified semantic capability.

A larger-parameter model with a quantization that places its practical local footprint inside the **9.6–13 GB tolerable envelope** remains an admissible transition or final candidate. Parameter count alone may not exclude it.

Models below 9.6 GB are preferred only when they preserve equivalent verified capability, reliability, and operational behavior. The project must not sacrifice meaningful verified capability merely to stay below 9.6 GB.

Models above 13 GB are not automatically forbidden, but they require explicit evidence that the additional verified capability or failure-class removal justifies the additional local resource, latency, and operational cost.

The pre-test runtime audit must record the actual artifact identity/size and, where exposed by the runtime, loaded memory behavior so that the 9.6–13 GB tolerance is applied to observed deployment cost rather than guessed from parameter count.

## 11. D3-Closure v2 physical-call budget

Hard maximum: 200 physical model calls.

- C0 zero-call salvage/preflight: 0
- C1 fresh matched raw baseline: up to 24
- C2 information/MSIP/order/representation: up to 36
- C3 real pre-decision assistance: up to 36
- C4 recovery/first-error behavior: up to 24
- C5 transition localization: up to 24, conditional
- C6 contradiction/measurement-risk reserve: up to 8
- C7 protected fresh confirmation: up to 48

The 48 confirmation calls are protected. Unused unsealed calls may move only with a recorded decision-impact justification. The budget is a ceiling, not a quota.

## 12. Fresh evidence partitions

Create deterministic partitions:

- `closure-development`
- `closure-fresh`
- `closure-sealed`

No D3-v1 sealed case becomes fresh confirmation for a post-hoc hypothesis.

The sealed bank must cover the major causal families and emphasize authority, transaction, recovery, global invariant, and novelty because of consequence.

## 13. Core hypotheses

The corrected test must be able to decide or explicitly bound:

1. **Model uplift:** SMALL_A supported materially outperforms the same model raw.
2. **Model substitution:** SMALL_A + minimum support approaches or matches Qwen raw/frozen-policy on relevant families without hard-invariant regression.
3. **Minimum sufficient information:** a removable subset exists; fields are retained only when removal causes reproducible semantic or invariant degradation.
4. **Information burden:** too much or poorly delivered information can harm at least some models/families.
5. **Model-specific support:** MSIP/MRS may differ by model and failure family.
6. **Pre-decision assistance:** model-visible support can improve cognition beyond sham/control.
7. **Action-space shaping vs cognition:** benefits from A2 are separated from genuine reasoning improvement.
8. **Prevention vs recovery:** mechanisms may be useful for one and not the other.
9. **Routing predictability:** observable pre-inference features can identify when SMALL_A should be used, when Qwen is required, and when evidence/recovery/escalation is required.
10. **Confidence calibration:** model confidence is admitted as a routing signal only if it predicts correctness sufficiently better than simpler system-owned observables.

## 14. Promotion and claim states

Mechanism state:

- REQUIRED
- CONDITIONAL
- REDUNDANT
- HARMFUL
- UNRESOLVED

Evidence state:

- OBSERVED
- HYPOTHESIZED
- CAUSALLY_VERIFIED
- GENERALIZED
- PROMOTED

No silent promotion is allowed.

## 15. Hard preflight gate

Before the first physical call, automated tests must prove at minimum:

- D3-v1 paths are read-only inputs to salvage tooling;
- semantic scoring is independent from format validity;
- disposition is compiled by the system rather than guessed from hidden labels;
- amount variants genuinely differ;
- ordering variants genuinely differ;
- shuffled control really shuffles deterministically;
- model-visible assistance is injected pre-decision;
- deterministic assistance uses outcome semantics, not dictionary-difference semantics;
- scheduler observes results and changes eligibility/allocation accordingly;
- harmful/futile mechanisms stop ordinary call allocation;
- unused unsealed budget can be reallocated without touching protected confirmation budget;
- recovery trajectories contain all required stages;
- context exhaustion has a dedicated failure class;
- no automatic retry loop exists;
- exact provenance is captured;
- crash/resume cannot duplicate a committed call;
- same-terminal compact progress is tested at normal and narrow widths.

A failed preflight spends zero physical model calls.

## 16. Outputs

D3-Closure must emit raw/normalized/derived layers and at minimum:

- `closure_information_value_map.json`
- `closure_minimum_sufficient_information_packet.json`
- `closure_assistance_value_map.json`
- `closure_minimum_required_scaffolding.json`
- `closure_disposition_compiler_evidence.json`
- `closure_recovery_policy_map.json`
- `closure_model_substitution_frontier.json`
- `closure_negative_transfer_map.json`
- `closure_routing_policy_evidence.json`
- `closure_sequential_decisions.jsonl`
- `closure_system_events.jsonl`
- `closure_call_ledger.jsonl`
- `closure_provenance.json`
- `closure_final_report.json`
- `test5_handoff.json`

## 17. Exit condition

D3-Closure ends when the project can defensibly state or explicitly bound:

- smallest useful model within the accepted local resource envelope;
- SMALL_A raw capability;
- SMALL_A uplift under INVERTED;
- Qwen anchor capability under frozen D4 policy;
- model-substitution boundary;
- minimum information support by applicable model/family;
- minimum model-visible assistance;
- deterministic system-owned support;
- harmful/negative-transfer support;
- recovery policy and remaining failure boundary;
- routing inputs;
- all unresolved gaps and their later owner.

When these architecture decisions are closed to the required evidence depth, stop D3 research and hand the result to Test 5 for compression/optimization rather than adding more test machinery.