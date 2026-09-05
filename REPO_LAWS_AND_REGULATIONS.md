# INVERTED — REPO LAWS AND REGULATIONS

**Status:** CANONICAL. PROJECT-WIDE. MANDATORY.  
**Purpose:** Govern all model-assisted research, testing, design, implementation, analysis, and project decisions for INVERTED.

---

# 0. PROJECT PHASE

INVERTED is no longer an open-ended idea-discovery project.

The project has a specific direction.

The job is now to determine the **best defensible path toward the established objective**, remove what does not contribute, resolve blockers, and converge on the smallest system that preserves the required capability.

Models shall not treat difficulty, uncertainty, or the existence of alternatives as permission to restart project discovery.

---

# 1. SUPREME DIRECTIVE

Build the strongest defensible INVERTED system using the **smallest sufficient architecture**, while preserving the capabilities, reliability, safety, recoverability, and operating constraints required by the project.

Every action must serve one or more of:

- proving feasibility;
- improving the chosen path;
- locating a real boundary;
- removing a blocker;
- identifying a failure mechanism;
- reducing unnecessary complexity;
- improving verified capability;
- establishing the next correct decision;
- qualifying the final system.

Anything that does none of these is outside the active project path.

---

# 2. USER INTENT IS THE TARGET

Treat the user's wording as **intent**, not as the limit of the technical formulation.

The user is not required to know:

- expert terminology;
- experimental vocabulary;
- architecture language;
- formal research methods;
- the exact technical question that must be asked.

The model must infer the strongest technical interpretation necessary to accomplish the stated goal.

Do not force the user to discover the vocabulary needed to ask for expert help.

---

# 3. DIRECTIONAL COMMITMENT

Once feasibility is sufficiently established, INVERTED continues toward the objective.

Difficulty is not evidence that the direction is wrong.

When blocked:

1. identify the blocker;
2. determine its cause;
3. remove it, replace it, route around it, reduce it, or build what is missing;
4. continue toward the objective.

A directional change is justified only if evidence establishes that:

- the objective is infeasible;
- the current path is materially inferior to another path to the same objective;
- a hard blocker cannot reasonably be removed;
- new evidence invalidates a foundational assumption;
- the path violates a hard project constraint.

Do not pivot merely because another approach is interesting.

---

# 4. EXPLORE PATHS, NOT DESTINATIONS

INVERTED may test multiple ways to move forward.

The structure is:

```text
ONE OBJECTIVE
    ↓
MULTIPLE POSSIBLE PATHS
    ↓
COMPARE / TEST / FALSIFY
    ↓
SELECT STRONGEST PATH
    ↓
CONTINUE FORWARD
```

Exploration exists to improve direction.

Exploration shall not become a substitute for direction.

---

# 5. INFORMATION SUFFICIENCY LAW

INVERTED is not a data-mining project.

The goal is not maximum information.

The goal is:

> **enough of the right information to make the next correct decision with high confidence.**

A useful information set must help determine at least one of:

- feasibility;
- mechanism;
- boundary;
- failure mode;
- model requirement;
- architecture responsibility;
- routing policy;
- recovery policy;
- safety/authority boundary;
- complexity requirement;
- immediate next action.

If additional information is unlikely to change any of those, stop collecting it.

---

# 6. EXISTING EVIDENCE FIRST

Before new research, testing, or inference:

1. inspect existing evidence;
2. determine what is already known;
3. identify what is already disproven;
4. identify what is bounded;
5. identify contradictions;
6. identify the exact remaining uncertainty.

Never spend new calls to answer a question existing evidence can validly answer.

Historical evidence must be reused before retesting.

---

# 7. RETESTING LAW

Data collection is cheap.

Retesting is not.

Before authorizing a new test, classify the question:

- `ANSWERED`
- `PARTIALLY_ANSWERED`
- `OBSERVATIONAL_ONLY`
- `CONTRADICTED`
- `REQUIRES_FRESH_INTERVENTION`
- `UNANSWERABLE_FROM_EXISTING_DATA`
- `NOT_DECISION_RELEVANT`
- `DEFER`

Only the classifications that genuinely require fresh intervention may justify new physical testing.

---

# 8. TEST AUTHORIZATION LAW

No new test may run unless it can change a named decision.

Every proposed test must define:

- `decision_id`
- current best answer;
- existing evidence;
- remaining uncertainty;
- why existing evidence is insufficient;
- what result A changes;
- what result B changes;
- what a null or failed result means;
- minimum valid evidence;
- stopping condition;
- architecture consequence.

If different possible outcomes would not change the decision, do not run the test.

---

# 9. QUESTIONS MUST EARN TESTING

A question is test-worthy only if its answer could materially change:

- architecture;
- model choice;
- information policy;
- action frontier;
- routing;
- verification;
- recovery;
- authority;
- safety;
- complexity;
- capability boundary;
- shipping decision;
- immediate next action.

Interesting questions are not automatically valuable questions.

---

# 10. EVIDENCE MUST BECOME KNOWLEDGE

A test is not complete because data exists.

Required transformation:

```text
OBSERVATION
    ↓
PATTERN
    ↓
BEST CAUSAL EXPLANATION
    ↓
COUNTEREVIDENCE / FALSIFICATION
    ↓
BOUNDARY
    ↓
DECISION
    ↓
ARCHITECTURE CONSEQUENCE
```

Every material result must end in one or more of:

- `KEEP`
- `REMOVE`
- `REPLACE`
- `CONDITIONAL`
- `ROUTE`
- `BOUND`
- `ESCALATE`
- `SAFE_STOP`
- `DEFER`
- `REJECT`

Raw evidence without a decision consequence is unfinished work.

---

# 11. NEGATIVE RESULTS MUST PRODUCE VALUE

A failed experiment is not complete when the project merely records what failed.

The failure must be converted into one of:

- a removed mechanism;
- a bounded mechanism;
- a new routing rule;
- a new recovery rule;
- a new system-owned responsibility;
- a falsified assumption;
- a smaller architecture;
- a sharper test;
- a known safe-stop condition.

Failure that produces no reusable consequence is wasted evidence.

---

# 12. MODELS ARE UNTRUSTED COGNITION

Models are useful for:

- semantic interpretation;
- hypothesis generation;
- novel reasoning;
- ambiguity resolution;
- evidence requests;
- diagnosis;
- decomposition where useful;
- recovery proposals;
- research synthesis.

Models should not own responsibilities that can be implemented more reliably with deterministic logic.

Prefer system ownership for:

- canonical state;
- authority;
- invariants;
- transaction truth;
- duplicate-effect prevention;
- deterministic validation;
- irreversible-effect fencing;
- provenance;
- verification where deterministically possible;
- hard safety boundaries.

---

# 13. RESPONSIBILITY MUST BE EXPLICIT

Every important behavior must have an owner:

- `KERNEL`
- `SYSTEM`
- `MODEL`
- `HYBRID`
- `VERIFIER`
- `RECOVERY`
- `HUMAN`

If responsibility is unclear, the architecture is unfinished.

Do not allow the same responsibility to be duplicated across multiple components without evidence that redundancy is required.

---

# 14. MODEL-SPECIFIC CAPABILITY FIRST; COMPRESSION SECOND

Do not assume larger models are better system components, and do not assume smaller models should imitate larger ones.

During discovery, maximize the defensible operating frontier of **each model against its own raw baseline** before optimizing model size or minimum support.

The target is not:

> one universal recipe, one universal model ranking, or the smallest model at any cost.

The discovery target is:

> **the exact model-specific conditions that maximize verified practical capability, including the information, amount, order, timing, placement, representation, assistance, task/state conditions, and resource tradeoffs that create the gain.**

Only after that frontier is understood may INVERTED compress toward smaller models, minimum-equivalent support, lower latency, fewer tokens, or simpler machinery while preserving the desired capability.

A stronger model is not a failure condition for a smaller model. Cross-model comparison is diagnostic; model-specific uplift is the primary discovery measure.

---

# 15. STRONG MODEL ESCALATION

Strong-model calls must earn their cost.

A strong model should be used when observable conditions indicate that cheaper/system-owned paths are insufficient.

Potential escalation reasons include:

- genuine novelty;
- unresolved ambiguity;
- missing evidence;
- known smaller-model capability boundary;
- high dependency complexity;
- irreversible consequence;
- failed deterministic resolution;
- unresolved recovery;
- novel failure investigation.

Do not use strong models as default workers when cheaper paths are sufficient.

---

# 16. CAPABILITY RATCHET

When a stronger model solves a recurring problem:

1. identify why it succeeded;
2. extract the causal mechanism;
3. determine whether that mechanism can become:
   - a deterministic rule;
   - better state;
   - better evidence;
   - a guard;
   - an action frontier;
   - a reusable knowledge object;
   - a smaller-model scaffold;
4. verify the extracted mechanism;
5. retest the cheaper path;
6. retire the strong model from that region if possible.

Expensive cognition should become durable cheaper capability whenever defensible.

---

# 17. CONTEXT IS NOT FREE — MAP BEFORE MINIMIZING

More information is not automatically better.

Every information field, representation, order, placement, timing policy, amount, source, and interaction may change model behavior and must be treated as part of a model-specific operating surface.

Do not assume:

- more context improves reasoning;
- more reasoning improves accuracy;
- more explanation improves execution;
- more history improves decisions;
- the same information policy is optimal for different models, tasks, difficulty levels, failure states, or context pressures.

During discovery, map the performance and negative-transfer surface deeply enough to identify the defensible frontier. **Do not minimize support before knowing what maximum useful capability looks like.**

After the frontier is established, find minimum-equivalent policies that preserve the chosen Pareto-optimal operating point.

---

# 18. ACTION-SPACE DISCIPLINE

Models should not be exposed to unnecessary choices.

Where possible, provide only admissible actions.

But action restriction must not silently remove valid behavior.

Any action-frontier mechanism must be evaluated for:

- false removal of correct actions;
- retention of dangerous actions;
- novel valid actions;
- stale frontiers;
- interaction effects across action sequences.

---

# 19. VERIFY THE WORLD, NOT THE MODEL'S CLAIM

A model saying an action succeeded is not evidence that the world changed correctly.

Verification should test:

- actual state;
- actual effects;
- invariants;
- postconditions;
- duplicate effects;
- partial effects;
- unknown effects;
- delayed visibility;
- rollback or compensation status.

Treat claims as untrusted until verified.

---

# 20. RECOVERY IS A FIRST-CLASS CAPABILITY

Failure prevention and failure recovery are separate responsibilities.

When failure occurs, preserve:

```text
FAILURE
  ↓
DETECTION
  ↓
FIRST DIVERGENCE
  ↓
DIAGNOSIS
  ↓
RECOVERY FRONTIER
  ↓
RECOVERY ACTION
  ↓
NEW STATE
  ↓
VERIFICATION
```

Do not call a recovery successful merely because the final task completed.

Verify that the failure was actually removed and not migrated.

---

# 21. GLOBAL CORRECTNESS OVER LOCAL SUCCESS

A component can behave correctly while the system behaves incorrectly.

Test interactions.

Ask whether:

- correct local actions create unsafe sequences;
- locally valid postconditions violate global invariants;
- correct routing produces globally inferior trajectories;
- recovery invalidates another action;
- timing makes otherwise valid decisions stale;
- individually useful mechanisms become harmful together.

The system is the unit of success.

---

# 22. COMPLEXITY RENT

Every component, rule, model, service, document, branch, and mechanism must earn its existence.

For each addition, ask:

- What does it fix?
- What measurable capability does it provide?
- What breaks if it is removed?
- Can an existing component absorb it?
- Can deterministic logic replace it?
- Can a smaller model replace it?
- Is its benefit universal or conditional?

If it cannot justify its complexity, remove it.

---

# 23. DOCUMENTATION DISCIPLINE

Documentation exists to preserve authoritative information, not to create the appearance of rigor.

Do not create a new document when:

- an existing canonical file owns the information;
- the content can be represented in structured project state;
- the document would duplicate another source;
- the document does not materially improve future decisions.

Prefer a small number of canonical files over many overlapping documents.

---

# 24. CANONICAL STATE OVER MEMORY

The repository is the durable source of project truth.

Models must not rely on reconstructed conversational memory when canonical project state exists.

Maintain clear separation between:

- stable laws;
- current project state;
- current open questions;
- evidence;
- temporary task instructions.

Old conclusions that no longer represent current evidence must be marked superseded or retired.

---

# 25. BIG REQUEST RULE

For every large, exhaustive, deep, or high-stakes request:

1. read [`INVERTED_BIG_REQUEST_REFERENCE.md`](INVERTED_BIG_REQUEST_REFERENCE.md);
2. identify the actual decision;
3. inspect existing evidence;
4. translate user intent into technical form;
5. reason as deeply as necessary;
6. avoid unnecessary scope expansion;
7. return the smallest complete result.

Depth is not measured by output length.

---

# 26. STOP RULE

Stop research/testing when:

- feasibility is sufficiently established;
- the active mechanism is understood well enough to act;
- relevant boundaries are known or safely bounded;
- major failure modes are accounted for;
- one path is materially preferred;
- remaining uncertainty is unlikely to change architecture or next action.

The existence of more measurable variables is not a reason to continue.

The existence of more literature is not a reason to continue.

The fact that more could be learned is not a reason to continue.

---

# 27. SHIPPING AND COMPRESSION

Discovery does not continue forever.

Once evidence is sufficient:

1. freeze the live mechanisms;
2. remove harmful mechanisms;
3. remove redundant mechanisms;
4. route conditional mechanisms;
5. collapse duplicated responsibilities;
6. select minimum sufficient models;
7. qualify the resulting architecture;
8. ship the smallest defensible system.

Later testing should compress and qualify—not reopen settled discovery without cause. Compression begins only after the relevant capability frontier is mapped well enough that simplification can be measured against a known high-performance reference.

---

# 28. ANSWER FORMAT

Use as much internal reasoning as necessary.

External output should normally be:

1. **Conclusion**
2. **Evidence**
3. **Risk / remaining uncertainty**
4. **Decision consequence**
5. **Next action**

If the answer is `NO`, say `NO` first.

If the answer is simple, keep it simple.

If the task is enormous, do the enormous reasoning and then compress the result.

Do not substitute verbosity for depth.

---

# 29. FINAL MODEL CHECK

Before finishing any significant task, ask:

1. Did I reduce uncertainty?
2. Did I close or sharpen a decision?
3. Did I identify a real blocker?
4. Did I materially improve the chosen path?
5. Did I reuse existing evidence before requesting more?
6. Did I add unnecessary complexity?
7. Am I expanding because it matters, or because I can?

If the work does not improve the path forward, it is not complete.

---

# 30. FINAL LAW

> **INVERTED does not seek maximum information, maximum testing, maximum model size, maximum architecture, or maximum documentation.**

It seeks:

> **the maximum defensible capability from each model and the whole system, discovered across the model-specific operating surface, then compressed to the minimum information, architecture, compute, and complexity that preserves the chosen capability frontier.**

Discovery and compression are different phases. The project is not rewarded for minimizing before it knows what capability is being sacrificed, and it is not rewarded for exploring forever.

The project is rewarded for understanding enough to make the next correct move—and then making it.
