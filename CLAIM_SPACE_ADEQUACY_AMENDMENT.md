# INVERTED Constitutional Amendment — Claim-Space Adequacy and Cost-Scaled Testing Law

## Status

**EXPLICIT OWNER-APPROVED CONSTITUTIONAL AMENDMENT TO `REPO_LAWS_AND_REGULATIONS.md`. MANDATORY PROJECT-WIDE.**

`REPO_LAWS_AND_REGULATIONS.md` remains the sole canonical repository lawbook. This document records an explicit owner amendment under the lawbook's governance-precedence and amendment rules. It is binding immediately and must be read together with the canonical lawbook and `INVERTED_CONSTITUTION.md` until physically consolidated into a later canonical revision.

This amendment was created after a pre-run review exposed a major scientific-design miss: an experiment intended to support broad claims about minimum/best/model-specific information support had a sample allocation capable only of screening a small hand-selected subset. The purpose of this law is to prevent any future experiment from silently claiming more than its design can resolve.

Historical evidence remains historical evidence. This law does not retroactively invalidate valid observations; it limits the claims that may be promoted from inadequately covered search spaces.

---

# LAW — CLAIM-SPACE ADEQUACY, SEARCH-COVERAGE, AND COST-SCALED TESTING

> **Before an experiment is authorized, the project must prove that the experiment design is adequate for the scope of the claim it intends to make. Call count alone is never evidence of adequacy.**

A test that compares three candidates may identify the best of those three. It may not claim to have found the best practical solution across a large unsearched design space.

A test that removes one factor at a time may estimate certain marginal effects. It may not automatically claim to have resolved interactions, global optimality, conditional optima, or minimum sufficient combinations.

A test that samples a tiny fraction of a combinatorial space may still support strong conclusions **only when the sampling design, structural assumptions, interaction coverage, sequential evidence, and bounded claim are sufficient to justify them**.

## 1. Mandatory claim-to-search-space map

Before costly execution, every consequential experiment must state:

```text
EXACT CLAIM
↓
DECISION VARIABLES THAT COULD CHANGE THE CLAIM
↓
LEGAL LEVELS / VALUES OF EACH VARIABLE
↓
IMPORTANT EFFECT MODIFIERS / STRATA
↓
PLAUSIBLE INTERACTIONS
↓
RAW THEORETICAL SEARCH SPACE
↓
ZERO-CALL CONSTRAINT / EQUIVALENCE / DOMINANCE REDUCTION
↓
REMAINING DISTINCT TREATMENT SPACE
↓
COVERAGE / SEARCH METHOD
↓
EVIDENCE DEPTH REQUIRED FOR THE CLAIM
↓
STOP / PROMOTION / UNRESOLVED RULE
```

This artifact is the **claim-space adequacy audit**.

For large spaces, exact exhaustive enumeration of all physical trials is not required. Exact enumeration or characterization of the **candidate space as data** should be performed when cheap and practical so the project knows what it is not testing.

## 2. Claim vocabulary has binding evidence requirements

The following words are not interchangeable:

### `SCREEN`
Means the experiment identifies promising/unpromising factors or candidates among a defined screen. It does not prove optimum or minimum.

### `BEST OF TESTED`
Means exactly that. It may not be shortened to `BEST` when serious untested candidates remain.

### `OPTIMAL / BEST PRACTICAL`
Requires either exhaustive admissible coverage or a defensible optimization/search method with convergence, challenger search, interaction handling, and fresh confirmation sufficient to bound the probability/value of an undiscovered materially superior region.

### `MINIMUM SUFFICIENT`
Requires removal/minimality testing around the promoted solution. A hand-authored packet named `MINIMUM` is not evidence of minimality.

### `GENERALIZED`
Requires fresh evidence across the relevant model/task/failure strata. Average success on a skewed subset is not generalization.

### `MODEL-SPECIFIC` / `CONDITIONAL`
Requires evidence that the effect differs by model or observable stratum strongly enough to justify separate policies.

If the design cannot satisfy the evidence requirement, narrow the claim before running or improve the design.

## 3. Combinatorial search-space law

When a mechanism has many possible combinations — information fields, ordering, representation, timing, placement, assistance, tools, routing, recovery, model size, or similar factors — do **not** choose an arbitrary small number of combinations and treat that sample as optimization.

Use a staged search:

```text
ZERO-CALL SPACE CONSTRUCTION
↓
INVALID / IMPOSSIBLE / DUPLICATE / NO-OP REDUCTION
↓
BROAD FACTOR SCREEN
↓
INTERACTION COVERAGE / CHALLENGER SEARCH
↓
ADAPTIVE DEEPENING AROUND PROMISING REGIONS
↓
LOCAL OPTIMIZATION
↓
MINIMALITY / ABLATION
↓
NEGATIVE-TRANSFER / ROBUSTNESS BOUNDARY
↓
FRESH + SEALED CONFIRMATION
```

For factors with many levels or combinations, use appropriate experimental-design methods rather than arbitrary sampling. Depending on the question, valid methods can include:

- fractional factorial screening;
- orthogonal/balanced screening designs;
- pairwise or higher-strength covering arrays;
- sequential elimination / best-arm identification;
- adaptive information-gain allocation;
- local neighborhood search;
- coordinate/factor ablation;
- response-surface or surrogate optimization where assumptions are defensible;
- protected randomized exploration to detect scheduler blind spots.

No method is automatically authoritative. The method must match the claim.

## 4. Interaction-adequacy law

Before declaring a factor unimportant or a configuration optimal, explicitly ask whether interactions can reverse the result.

At minimum classify every important factor pair/group as:

- interaction physically impossible;
- interaction scientifically implausible with documented reason;
- interaction covered by the design;
- interaction screened but unresolved;
- interaction intentionally deferred and therefore excluded from the final claim.

Main-effect screening may be used to prune the space, but an architecture candidate cannot be promoted as globally or conditionally optimal if a plausible high-value interaction capable of reversing the decision remains untested.

## 5. Zero-call reduction law

**Search-space size is not permission to spend blindly.**

Before model calls, use free/system-only work to remove:

- byte-identical treatments;
- semantically identical model-visible treatments;
- no-op orderings/placements/timings;
- impossible combinations;
- hidden-oracle leakage;
- dominated labels that render to the same treatment;
- treatments invalid for a model/case;
- deterministic consequences answerable without inference.

Preserve a pruning ledger explaining every removed region.

Do not prune a candidate merely because it is longer, stranger, or currently unfavored when that property could itself change model behavior.

## 6. Search-coverage accounting law

Every combinatorial experiment must emit a machine-readable coverage report including, where applicable:

- raw theoretical candidate count;
- legal candidate count;
- equivalence-reduced candidate count;
- number actually sampled;
- main-effect coverage;
- 2-way interaction coverage;
- higher-order interaction coverage where required;
- model/family/stratum coverage;
- unexplored regions;
- regions pruned and why;
- candidates eliminated by evidence;
- candidates still capable of changing the winner;
- fresh/sealed confirmation depth;
- claim strength currently justified.

A test may stop with uncovered space only when the remaining space cannot plausibly change the project decision at the required evidence level or the final claim is explicitly bounded to exclude it.

## 7. Adaptive search must preserve discovery

Adaptive testing is encouraged because retesting is expensive, but exploitation may not erase exploration.

The scheduler must preserve a preregistered randomized/challenger stream so an early apparent winner cannot permanently hide a different region of the space.

When evidence says a factor is:

- **HARMFUL** → stop ordinary spending; retain contradiction/boundary checks.
- **FUTILE** → stop ordinary spending.
- **PROMISING** → deepen, interact, generalize, then ablate.
- **UNRESOLVED** → choose the next maximally discriminating treatment.
- **STABLE WINNER** → attack it with its strongest surviving challenger and local neighborhood before promotion.

## 8. Cost-scaled testing law

> **The scientific size of a test and the cost of a test are different quantities. Testing depth must scale inversely with the cost of each observation.**

The project must not use one raw call ceiling as the sole budget for experiments whose call costs differ by orders of magnitude.

### 8.1 Required cost classes

At minimum distinguish:

#### SYSTEM / DETERMINISTIC — effectively free model cost

Examples:

- static enumeration;
- packet rendering;
- deterministic replay;
- compiler/guard verification;
- scoring;
- simulation that does not invoke a model;
- checksum/integrity checks;
- existing-evidence analysis.

These consume **zero physical model calls**. Use them aggressively while they remain decision-relevant. They are bounded by compute/runtime usefulness, not an inference-call quota.

#### NEAR-FREE / TINY MODEL

Very small local models with negligible runtime cost relative to the rest of the experiment may receive the broadest live-inference sample ceilings when calibration confirms that they are cheap.

#### FAST MODEL CALL — cheap

A short non-thinking or low-latency inference call may receive a **larger sample ceiling** because its marginal cost is low.

#### MEDIUM MODEL CALL

Receives a moderate sample ceiling.

#### VERY EXPENSIVE / LONG / THINKING / OFFLOADED CALL

Receives a **smaller sample ceiling**. A call that occupies the model/GPU for tens of seconds or minutes, approaches the context limit, or crosses a hardware-residency/offload cliff cannot be budgeted as if it costs the same as a tiny or cleanly resident model.

### 8.2 Hardware-residency and model-footprint law

**Model-call cost is not a smooth function of parameter count or artifact size. Hardware residency can create cliffs.**

The scheduler must therefore consider both:

1. installed model artifact / expected resident footprint; and
2. measured runtime cost.

A model that barely fits cleanly in accelerator memory may be dramatically cheaper than a model only slightly larger that forces partial offload, RAM/PCIe movement, reduced KV headroom, or another residency penalty.

Therefore:

- do not budget by parameter count alone;
- do not assume two neighboring model sizes have neighboring costs;
- capture installed model size/digest and relevant residency/offload telemetry where exposed;
- define environment-specific residency thresholds before testing when the hardware has a known cliff;
- treat crossing a known residency cliff as a strong **pre-call expensive-class prior**;
- verify that prior with measured latency/throughput before finalizing sample economics;
- immediately raise a model/policy cost class if runtime evidence shows spill/offload or severe slowdown.

Hardware-specific thresholds belong in a versioned experiment cost profile rather than this permanent law. The current Harvest D local profile is `configs/harvest-d-local-model-cost-profile.json`.

### 8.3 Calibrate cost from the actual runtime

Do not permanently guess which bucket a model/policy belongs to.

Before the main experiment, collect a small reproducibility/cost calibration block and record at minimum:

- installed model artifact size and digest;
- wall-clock/model latency;
- prompt/input tokens;
- generated/output tokens;
- thinking/reasoning tokens where exposed;
- context exhaustion;
- residency/offload evidence where exposed;
- model/runtime identity;
- hardware/runtime load metadata where exposed.

Freeze expected cost classes from this calibration for scheduling. If observed cost drifts materially, trigger a budget recalibration/stage audit rather than silently changing sample economics.

### 8.4 Budget vector, not one number

Every expensive experiment should track at least:

```text
PHYSICAL MODEL CALLS
MODEL INFERENCE WALL-TIME / GPU-OCCUPANCY PROXY
MODEL ARTIFACT / RESIDENCY CLASS
TOKEN / CONTEXT BURDEN
SYSTEM-ONLY WORK
PROTECTED CONFIRMATION RESERVE
```

Use **inference time on the actual test hardware as the primary local cost proxy** when all calls run on the same local system, with artifact/residency class and tokens/context retained as predictive/explanatory/guard metrics.

The physical-call ceiling remains a hard runaway-safety limit, not the principal definition of experiment size.

### 8.5 Dynamic sample principle

For a fixed evidence objective:

```text
SYSTEM WORK        -> FREE model-call cost
TINY / NEAR-FREE   -> HIGHEST permissible N
FAST CALLS         -> HIGH permissible N
MEDIUM CALLS       -> MODERATE permissible N
VERY EXPENSIVE     -> LOW permissible N
```

A `massive` test may therefore contain thousands of cheap/system-only evaluations and hundreds or thousands of tiny/fast model calls while using only a small number of long-thinking/offloaded calls.

A `small` expensive-model test may contain few calls yet consume more inference time than a much larger fast-call experiment.

### 8.6 Cost cannot weaken scientific adequacy silently

If the required evidence cannot be obtained within the affordable cost budget, the legal outcomes are:

1. reduce cost using zero-call pruning, better experimental design, cheaper models, or more efficient calls;
2. narrow the claim;
3. mark the question UNRESOLVED and route it correctly;
4. explicitly authorize additional cost.

It is forbidden to keep the broad claim and quietly under-sample it because the correct experiment is expensive.

## 9. Reproducibility/noise floor law

Before eliminating candidates based on small differences, estimate runtime/model variability under exact repeated conditions.

The search algorithm must not treat an effect smaller than the observed noise/instability floor as a reliable architecture signal.

Where deterministic or near-deterministic behavior is empirically established for a model/policy, later replication can be reduced. Where instability is high, evidence depth must increase or the claim must narrow.

## 10. Final adequacy gate

Immediately before authorizing physical execution, the responsible model/reviewer must answer:

> **If the experiment succeeds exactly as designed, what claims will it actually be able to prove, what important combinations/interactions will still be capable of changing those claims, and why is the planned search depth sufficient relative to the cost of the observations?**

If the answer reveals a material mismatch between the intended claim and attainable evidence, the experiment is a **SCIENTIFIC RISK / HARD BLOCKER** under Law 28 and may not start.

## 11. Required outputs

For every nontrivial combinatorial/optimization experiment, preserve at minimum:

- `claim_space_manifest.json`
- `search_space_manifest.json`
- `candidate_pruning_ledger.jsonl`
- `coverage_report.json`
- `cost_calibration.json`
- `cost_budget_state.jsonl`
- `interaction_coverage.json`
- `uncovered_space.json`
- `claim_adequacy_report.json`

Equivalent names are acceptable when the schema is preserved and discoverable.

## 12. Final rule

> **Never confuse “we tested enough cases to get a result” with “we tested enough of the right space to justify the claim.”**

And:

> **Spend trials in proportion to information value per unit cost: system-only evidence first, tiny/fast inference broadly, expensive inference selectively, and fresh confirmation only after the candidate space has been reduced enough that confirmation can actually mean something.**
