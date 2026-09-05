# INVERTED — Permanent Model Operating Rules

## Governance authority

Before applying this convenience operating summary, read and obey [`REPO_LAWS_AND_REGULATIONS.md`](REPO_LAWS_AND_REGULATIONS.md), the sole canonical repository lawbook, then the owner-approved six-law amendment in [`INVERTED_CONSTITUTION.md`](INVERTED_CONSTITUTION.md).

This file provides a compact operating layer beneath those authorities. It may not weaken, replace, or outrank them.

## Status

**MANDATORY PROJECT-WIDE OPERATING SUMMARY FOR ALL FUTURE MODELS, AGENTS, CONTRIBUTORS, EXPERIMENT DESIGNERS, AND IMPLEMENTATION WORK.**

These rules apply across INVERTED unless an explicit later repository decision supersedes them. They are not limited to Harvest D, D3, Test 5, Harvest E, or Test 6.

## 1. User requirements are the floor, not the ceiling

> **Your requirements define the minimum. I am responsible for identifying higher-value options, missing experiments, better architecture, better telemetry, and failure modes you did not explicitly name.**

Future models must not stop at literal compliance when a materially better design, test, safeguard, evidence source, simplification, automation path, or failure detector is available.

Before finalizing any meaningful design or implementation, independently ask:

- What important option was not requested?
- What assumption could make the current plan wrong?
- What failure mode has not been tested?
- What evidence would change the architecture ranking?
- What data would become expensive or impossible to reconstruct later?
- What can be automated safely rather than delegated to the operator?
- What component can be removed, simplified, or made deterministic?
- What interaction between components could invalidate isolated test results?
- What fresh/neighbor/adversarial case would most strongly challenge the current conclusion?

Do not add complexity merely because more options exist. **Something has to prove it belongs.** Higher-value alternatives must be surfaced, tested where appropriate, and ranked by evidence.

## 2. Capture future-useful evidence while it is cheap

> **Do not merely satisfy the requested experiment. Ask what we will wish we had recorded six months later, and capture it now when it is cheap.**

Model inference, local testing time, sealed cases, and exact runtime states can be expensive or impossible to reproduce. Storage and deterministic post-hoc analysis are comparatively cheap.

Therefore, whenever safe and practical, preserve enough observable evidence to support future questions without rerunning the expensive experiment.

At minimum apply these principles:

- Preserve **raw immutable evidence** before normalization or summarization.
- Preserve **normalized/queryable data** separately from raw evidence.
- Preserve **derived/recomputable analysis** separately from both.
- Hashes are for integrity and linkage; they must not replace useful safe payloads.
- Record model-visible information separately from system-known information.
- Preserve exact model requests, full raw runtime responses, model/runtime provenance, case lineage, state/evidence/authority snapshots, interventions, routing, recovery, scoring, timing, and relevant environment metadata.
- Record edge cases and invalid/inadmissible trials rather than deleting them.
- Record non-events when causally useful: interventions that were eligible but did not fire, alternatives that were available but rejected, information that existed but was omitted, and recovery paths that were available but not selected.
- Preserve deterministic counterfactuals/shadow replays whenever they are scientifically useful and cost no new model call.
- Record operator/manual interventions that affect comparability.
- Preserve enough scheduler/adaptive-selection state to reconstruct why calls were allocated or stopped.
- Store structured, observable decision traces where useful: candidate actions, rejected alternatives, reason codes, referenced evidence/state/authority, uncertainty, recovery options, and expected postconditions. Do not depend on hidden/private chain-of-thought.
- If essential capture fails, retain every available byte, mark the call incomplete, and stop spending expensive calls if the capture subsystem is unreliable.

## 3. Retesting avoidance is an explicit design objective

Before an expensive run begins, ask:

> If a high-value hypothesis appears after this run, can the stored evidence answer it without another model call?

If the answer is "no" because an observable, safe, cheap-to-store field is missing, improve the capture design before spending the calls.

This does **not** mean indiscriminate collection. Do not capture credentials, secrets, arbitrary environment variables, unrelated filesystem/process data, private chain-of-thought, or information that would contaminate a sealed experiment. Maximize **usable, safe, causally interpretable** evidence.

## 4. Failure is data only when causality is preserved

A failure must produce more than a failure count. Preserve, where observable:

`OBSERVATION -> FIRST MEANINGFUL DIVERGENCE -> DETECTION -> DIAGNOSIS -> INTERVENTION/RECOVERY -> STATE TRANSITION -> VERIFIED OUTCOME -> ARCHITECTURE INSTRUCTION`

Do not use blind retries. Do not silently rewrite oracles, success criteria, prior evidence, or holdouts after seeing results. Negative evidence should narrow the architecture or create a targeted causal hypothesis.

## 5. Evidence outranks cleverness

No mechanism survives because it is elegant, novel, or theoretically appealing. Components should be classified from evidence as appropriate:

- REQUIRED
- CONDITIONAL
- REDUNDANT
- HARMFUL
- UNRESOLVED

Promote only after the applicable causal, generalization, regression, safety, and evidence-depth gates are satisfied.

## 6. Model-specific operating-surface rule

The project is not searching for one universal prompt or one fixed support bundle.

For model-uplift work, treat support as a conditional function of model, task/failure region, difficulty/structure, observable state, context pressure, and resource target. Candidate dimensions include information identity/source, dose, sequence, timing, placement, representation, assistance, interactions, and persistence.

Measure each model against its **own raw baseline**. Cross-model comparisons are useful for diagnosis and routing, but one model remaining stronger than another is never itself a failure condition.

During discovery, preserve the Pareto frontier across verified correctness, silent/catastrophic failure, stability/generalization, latency, tokens, compute, model calls, recoverability, and architecture burden. A near-peak point may be preferred when it buys a material efficiency gain.

Do not optimize for minimum support or smallest model until the relevant high-performance frontier is known. Compression is a later phase that must demonstrate preservation of the selected capability point.

Read `docs/OPERATING_SURFACE_EVIDENCE_FRONTIER.md` and its JSON companion before proposing new model-uplift inference so already-mapped regions are not broadly retested.

## 7. Scope

These rules apply to:

- architecture and system design;
- experimental design and testing;
- model selection and routing;
- telemetry and data schemas;
- recovery and failure handling;
- repository implementation;
- handoffs between models/agents;
- future optimization and compression work.

When another repository document gives more specific instructions, follow both unless they conflict. If a conflict exists, use the precedence defined by `REPO_LAWS_AND_REGULATIONS.md`, preserve frozen experiment/safety constraints, and incorporate the owner-approved constitutional amendment wherever applicable.
