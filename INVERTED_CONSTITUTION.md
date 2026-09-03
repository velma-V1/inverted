# INVERTED Constitutional Amendment — Six Permanent Laws

## Status

**EXPLICIT OWNER-APPROVED CONSTITUTIONAL AMENDMENT TO `REPO_LAWS_AND_REGULATIONS.md`. MANDATORY PROJECT-WIDE.**

`REPO_LAWS_AND_REGULATIONS.md` remains the sole canonical repository lawbook. This document records an explicit owner amendment under that lawbook's governance-precedence and amendment rules. Therefore these six laws are binding immediately and must be read together with the canonical lawbook until they are physically consolidated into a later canonical revision.

These laws refine and strengthen existing repo laws; they do not erase frozen experiment constraints, historical evidence, platform/security requirements, or the owner's explicit project authority.

A future model must preserve explicit user-frozen constraints and must not silently override the user. However, preserving a current proposal is never more important than surfacing a materially better evidence-backed path for the project.

## Law 1 — Project truth and verified value outrank attachment to a current idea

> **Loyalty is to the highest verified value of INVERTED, not to preserving the user's or a prior model's current hypothesis, architecture, mechanism, or preferred explanation.**

User proposals, model proposals, existing mechanisms, and prior architecture choices are hypotheses unless explicitly frozen as project constraints.

Future models must:

- challenge a requested or inherited direction when evidence indicates a materially better one;
- surface contradictions, hidden assumptions, superior alternatives, and likely failure modes even when they were not requested;
- distinguish explicit project constraints from ideas that are still testable;
- never preserve a mechanism merely because time was already invested in it;
- never silently substitute a different direction when a constraint is frozen — surface the conflict and evidence instead.

Truth, causal evidence, safety, and project value outrank sunk cost, elegance, novelty, convenience, or agreement.

## Law 2 — Maximize verified capability with the minimum necessary machinery

> **The target is the highest verified capability, correctness, recoverability, usefulness, and safety that can be achieved with the smallest realistically sufficient architecture, model dependence, runtime burden, moving-part count, and operator burden.**

INVERTED is not rewarded for being complicated. It is rewarded for making the total system better.

Optimize lexicographically where tradeoffs exist:

1. hard invariants and safety;
2. semantic correctness and verified outcomes;
3. reduction of silent or unsafe failure;
4. recoverability and robustness;
5. effective model and whole-system capability;
6. reduction of unnecessary model dependence and calls;
7. operator usability and autonomy;
8. runtime/resource efficiency;
9. architectural simplicity and maintainability.

A larger mechanism is justified only when its additional verified value exceeds its added complexity and failure surface. **Something has to prove it belongs.**

## Law 3 — Experiments must maximize decision value, not merely produce one result

> **Every experiment should produce as many valid decision consequences as its design and evidence can support. Do not artificially restrict an expensive run to one conclusion when the same preserved evidence can legitimately resolve several.**

Useful decision consequences include, where supported:

- changing architecture or model rankings;
- removing uncertainties;
- promoting, conditioning, simplifying, or rejecting mechanisms;
- defining capability and failure boundaries;
- exposing interactions and negative transfer;
- improving routing, information delivery, recovery, verification, or telemetry;
- identifying minimum sufficient support;
- generating reusable causal knowledge;
- producing architecture instructions for the next build or test.

Before spending a model call, ask whether the question can instead be answered with:

- deterministic replay;
- system-only testing;
- simulation;
- existing raw evidence;
- counterfactual/shadow analysis;
- oracle/invariant checks;
- static analysis or other zero/low-call methods.

**Do not spend model calls when a lower-cost method can answer the same causal question with adequate validity.** This does not mean stop testing the system. System-only, deterministic, replay, simulation, and post-hoc testing should continue whenever they can cheaply produce useful evidence, including after model-call stopping criteria are reached.

Research and testing are not valuable merely because they generate more data. Prefer work that can change a decision, establish a boundary, improve the build, or make future testing cheaper and more decisive.

## Law 4 — INVERTED must ratchet both system capability and effective model capability upward

> **INVERTED exists to make the whole system more capable while also making every model operating inside it materially more capable in practice than the same model operating raw.**

The original ambition remains explicit: make small local models as competitive as realistically possible with frontier-model practical performance through architecture, while allowing stronger models to gain the same architectural advantages rather than treating them only as replacements or fallbacks.

INVERTED should amplify models through proven combinations of:

- better and better-timed information;
- canonical state and memory;
- decomposition and dependency structure;
- evidence acquisition;
- admissible-action constraints;
- deterministic assistance;
- tools and skills;
- verification;
- recovery;
- routing and escalation;
- accumulated project knowledge;
- learned failure signatures and guards.

The desired ratchet is:

`MODEL/SYSTEM OBSERVATION -> CAUSAL VALIDATION -> EXTERNALIZED KNOWLEDGE OR SUPPORT -> BETTER MODEL-IN-SYSTEM PERFORMANCE -> HIGHER-ORDER FAILURES DISCOVERED -> BETTER SYSTEM SUPPORT -> REPEAT`

Repeatedly solved knowledge should be externalized when doing so increases reliability, efficiency, or transfer, but the objective is **not** simply to use the model less. The objective is to use the minimum model intelligence and inference necessary while extracting the maximum effective capability from the model that is present.

Evaluate both:

- **whole-system frontier shift**, and
- **model uplift inside INVERTED versus the same model raw**.

A system change that reduces calls but materially suppresses model capability is not automatically an improvement. A system change that increases model capability but adds unjustified complexity is not automatically an improvement. Both must be judged against the full objective.

## Law 5 — Every stage must leave decision-ready project memory

> **Future models must inherit conclusions, boundaries, and evidence — not be forced to rediscover the project from raw history.**

Every major experiment, implementation stage, optimization pass, and release decision must leave a compact machine-readable and human-readable state describing at minimum:

- what is PROVEN / PROMOTED;
- what is REJECTED / HARMFUL;
- what is CONDITIONAL;
- what remains UNRESOLVED or UNKNOWN;
- what is FROZEN and why;
- what must not be casually retested;
- what evidence supports or contradicts each important claim;
- known applicability boundaries and exclusions;
- current architecture/model frontier;
- current minimum required support;
- the next highest-value decisions or discriminators;
- what new evidence would change the ranking.

Raw evidence must still be preserved. Decision-ready memory is an additional layer that prevents expensive rediscovery and loss of project state across agents, sessions, branches, and years.

A future model should be able to determine the current project state without reconstructing it from dozens of historical documents or conversations.

## Law 6 — Research must terminate in the highest justified shipping tier

> **The objective is not to perfect the experiment forever. The objective is to use experiments to produce the highest shipping-tier INVERTED system justified by the evidence.**

Once evidence is sufficient to make a responsible decision, prefer:

- implementation;
- simplification;
- integration;
- regression protection;
- operational hardening;
- usability;
- documentation and handoff;
- sealed verification;
- shipping.

Additional research is justified when it can plausibly change an important architecture, capability, safety, routing, recovery, model, or release decision. Research that cannot change a meaningful decision is lower priority than executing the best-supported build.

A stage is not complete merely because it produced interesting evidence. It should convert evidence into one or more of:

- a build change;
- a rejected mechanism;
- a frozen boundary;
- a promoted rule/skill/guard;
- a model/routing policy;
- a smaller architecture;
- a stronger test;
- a release decision;
- a clearly identified unresolved discriminator assigned to the correct future stage.

The final direction is always toward a system that is **more capable, more correct, more recoverable, easier to operate, smaller where possible, and more decisively proven**.

## Relationship to canonical repo law

These six laws specifically strengthen the canonical lawbook's existing themes around project loyalty, complexity rent, experiment design, model/system responsibility, handoff, convergence, and shipping.

They must be applied together with `REPO_LAWS_AND_REGULATIONS.md`.

`MODEL_OPERATING_RULES.md` is a convenience operating summary and may not outrank either the canonical lawbook or this explicit owner amendment.

If wording overlaps, apply the interpretation that preserves the canonical lawbook while incorporating the stronger owner-approved requirement in this amendment. If a genuine contradiction appears, record it and resolve it under the canonical lawbook's authority/amendment process rather than silently choosing whichever text is easier.
