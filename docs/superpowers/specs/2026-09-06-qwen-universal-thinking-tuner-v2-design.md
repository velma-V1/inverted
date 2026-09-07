# Universal Adaptive Model Operating-Surface Tuner V2

## Status

Approved architecture for redesigning the existing Qwen thinking tuner into a reusable experimental template. This is a protocol revision of the current test lineage, not a new experiment family.

## Objective

Discover the smallest, most robust inference configuration that materially improves each task family while distinguishing model cognition from interface, contract, completion, and execution failures.

The tuner must answer five questions for every task family:

1. Does additional reasoning materially improve semantic performance over direct inference?
2. What is the minimum useful reasoning budget?
3. What temperature region gives robust semantic performance at that budget?
4. Do budget and temperature interact strongly enough to change the selected profile?
5. Which remaining failures are semantic, contract, completion, or infrastructure failures?

The system must spend calls only where additional evidence can change one of these decisions.
## Non-Negotiable Experimental Rules

- Preserve all V1 raw requests, responses, scores, provenance, and summaries unchanged.
- V1 may be rescored into a derived audit, but rescored data must remain labeled as derived evidence.
- Never mix V1 derived evidence with V2 fresh validation as though the protocols were identical.
- Deterministic scorers take precedence over LLM judges whenever a deterministic oracle is possible.
- Semantic correctness and output-contract correctness are separate axes.
- No profile can be certified from three examples or one micro-batch.
- A temperature value is never promoted because of tiny latency differences inside an accuracy tie.
- Thousandths-place temperature refinement occurs only while finer resolution still yields useful semantic information.
- A broad successful temperature region is reported as a plateau, not collapsed into false precision.
- Every scheduled model call must carry a machine-readable reason stating what unresolved decision it can change.
- If a result cannot change a decision, the call is not scheduled.
- No retries are used to erase model failures; failures are recorded and classified.
- The physical-call ceiling remains a hard abort boundary, not an expected workload.

## Protocol Lineage

Protocol V1 is the completed 192-call Qwen3.5 9B run. Protocol V2 replaces the internal decision engine while keeping the same user-facing tuner command and experiment identity.
## Evidence Model

Each observation records at least:

- protocol version, run ID, model identity, model digest, runtime version, task family, case ID, difficulty stratum, inference seed, and stage;
- full inference profile, including think mode, reasoning cap, temperature, sampling parameters, context limit, and final-answer cap;
- exact request and response envelopes;
- semantic score and semantic subcomponent scores;
- contract score and contract failure reason;
- completion status and done reasons;
- latency, output tokens, thinking tokens, physical calls, and natural thinking termination;
- infrastructure status and any non-model failure classification;
- scheduler reason for why the observation was requested.

Atomic task outcomes are preserved even when several tasks share one model call. Aggregate scores are derived from atomic outcomes, never substituted for them.

## Scoring Axes

1. **Semantic correctness** — whether the substantive answer is correct independent of harmless representation differences.
2. **Contract correctness** — whether the answer obeys the required schema, formatting, field names, and response protocol.
3. **Completion reliability** — whether the model produces a usable final answer without truncation, empty content, or invalid completion state.
4. **Efficiency** — wall time, output tokens, thinking tokens, and physical-call cost, considered only after semantic and reliability gates.
## Semantic Canonicalization

Scorers must recognize semantically equivalent valid answers before declaring failure.

Examples:

- exact classification values remain correct even if returned under a different harmless container shape;
- numeric words and numerals may normalize where the task meaning is unchanged;
- ordered dependency solutions normalize delimiters while preserving required order;
- coding tasks use executable or behavioral oracles whenever feasible instead of one exact source string;
- synthesis tasks score required factual content separately from the requested output contract.

A response may therefore be `SEMANTIC_PASS / CONTRACT_FAIL`. Contract failures remain real failures for production routing but must not be misdiagnosed as missing cognition.

## Task Bank and Generators

The twelve current task families remain the initial canonical set. Each family becomes a deterministic generator capable of producing many fresh atomic tasks across difficulty strata.

A micro-batch contains five independently scored atomic tasks. Before inference, the campaign freezes the generated pool, seeds, expected answers, difficulty labels, and hashes. Generation cannot adapt task answers after model output is observed.

The generator interface must be generic enough for future task families, models, runtimes, and non-temperature parameter axes without rewriting the campaign engine.
## Paired Experimental Design

Competing profiles receive the same frozen micro-batches in the same comparison block. Matching inference seeds are used within each paired block; different blocks use different predetermined seeds.

This provides paired evidence for profile deltas rather than comparing unrelated sample averages. Task-order rotation is deterministic so a profile cannot systematically benefit from always running first or last.

A profile cannot be certified with fewer than eight fresh micro-batches, equal to forty atomic tasks. Evidence is reviewed only at predetermined checkpoints of 40, 60, 80, and 120 atomic tasks. These checkpoints prevent arbitrary repeated peeking from becoming a hidden stopping rule.

A comparison is `CLOSE` when its paired 95% confidence interval intersects either the +5 percentage-point superiority threshold or the -2 percentage-point non-inferiority threshold. CLOSE comparisons expand automatically through the 60, 80, and 120 atomic-task checkpoints. At 120, unresolved superiority becomes `TIE_OR_PLATEAU`; unresolved non-inferiority prevents promotion. Clearly dominated candidates may be eliminated before certification, but early evidence may eliminate a loser only; it may not certify a winner.

## Statistical Decision Rules

The default minimum useful semantic effect is five percentage points. The default acceptable semantic floor for a deployable family profile is 90%. Both values are preregistered ExperimentSpec parameters and may be overridden before generation for a domain that requires a different standard.

Profile comparisons use paired semantic deltas with 95% confidence intervals computed by deterministic clustered bootstrap over paired micro-batches. Bootstrap seeds and resample counts are frozen in the campaign manifest.

A candidate earns semantic superiority only when the confidence interval supports a gain at or above the minimum useful effect. If the interval cannot distinguish a practically meaningful gain, the semantic result is `TIE_OR_PLATEAU` rather than a winner.

Efficiency may break a tie only after semantic correctness, completion reliability, and non-inferiority are established. Small latency fluctuations never create a cognitive winner.
## Stage 0 — V1 Derived Audit

Before any V2 inference, the campaign rescoring tool reads the immutable V1 raw evidence and emits a separate derived audit containing semantic, contract, completion, and efficiency classifications.

The audit is diagnostic only. It may set search priors such as likely budget brackets or known contract hazards, but it cannot certify a V2 operating profile.

## Stage 1 — Direct Versus Thinking Gate

For each family, compare direct inference against one strong thinking anchor on fresh paired tasks. The anchor is model-adapter metadata, not a universal constant; for current Qwen3.5 general reasoning the initial reference is temperature 1.0, while coding/debugging may use the model-recommended precise-coding anchor.

At a preregistered checkpoint, thinking advances when the paired 95% confidence interval supports at least a +5 percentage-point semantic gain. If the comparison is CLOSE, evidence expands to the next checkpoint. If neither profile reaches the preregistered acceptable semantic floor after the final checkpoint, one high-budget diagnostic profile is admitted to determine whether the family is budget-limited; that diagnostic cannot certify a final profile by itself.

If direct and thinking are semantically equivalent, direct mode wins unless thinking materially improves completion reliability or contract behavior. If both remain weak, the family is labeled capability-unresolved and receives a targeted diagnostic instead of a temperature sweep.

## Stage 2 — Minimum Useful Reasoning Budget

The scheduler brackets the transition between insufficient and sufficient reasoning using adaptive budget candidates. It searches around observed failure/success boundaries rather than replaying the fixed V1 ladder.

The chosen budget is the smallest tested cap that is statistically non-inferior to the best semantic result within a preregistered two-percentage-point non-inferiority margin and has acceptable completion reliability.
Natural thinking termination is recorded separately from the configured cap. If several caps produce equivalent semantics and the model consistently stops below all of them, the reported operating surface includes the observed natural-thinking distribution rather than pretending the largest cap was required.

## Stage 3 — Thinking Temperature Surface

Temperature tuning begins only after thinking has earned advancement and a budget bracket exists.

The first pass uses a coarse set centered on model-specific recommended anchors and expands outward only when an edge candidate shows meaningful semantic improvement. Candidates are always tested on paired fresh tasks.

Temperature refinement uses the fixed resolution sequence 0.10, 0.05, 0.02, 0.01, 0.001. The next finer resolution is admitted only when the current paired evidence either supports a >=5 percentage-point semantic improvement toward one side or leaves a plateau boundary CLOSE under the defined superiority/non-inferiority thresholds. Otherwise refinement stops at the current resolution.

The primary output is a validated temperature region. A single recommended point is reported only when evidence supports a narrower optimum. Otherwise the result is a plateau with explicit lower and upper tested bounds.

Within a plateau, the recommended operating point is the most interior tested value whose completion reliability is non-inferior within two percentage points to the best plateau member; latency is ignored for choosing that point.

## Stage 4 — Budget × Temperature Interaction

The final calibration stage evaluates direct mode plus the top two surviving budget regions crossed with the top two surviving temperature regions on fresh paired tasks.

This bounded interaction check exists only to catch cases where the best budget changes under the best temperature. It must not expand into an exhaustive factorial grid unless the interaction evidence itself remains unresolved and can still change the selected policy.
## Stage 5 — Fresh Holdout Certification

The final selected direct profile, thinking profile, and nearest serious alternative are evaluated on a fresh frozen holdout that was never used for search decisions.

Certification requires at least forty atomic holdout tasks per family and expands through 60, 80, and 120 when the selected and alternate profiles are CLOSE under the same preregistered paired thresholds. The holdout reports semantic accuracy, contract accuracy, completion reliability, confidence intervals, and paired deltas.

A family may finish as `VALIDATED`, `PLATEAU`, `DIRECT_SUFFICIENT`, `CONTRACT_LIMITED`, `CAPABILITY_UNRESOLVED`, or `INFRASTRUCTURE_INVALID`. `UNRESOLVED` alone is not sufficiently diagnostic.

## Frontier Sampling

Each task generator exposes difficulty strata. Initial evidence samples across the strata. Later adaptive batches concentrate on strata where competing profiles disagree or where semantic accuracy is neither saturated nor uniformly failed.

Easy tasks where all profiles are consistently correct and impossible tasks where all profiles are consistently wrong receive reduced allocation after the scheduler has enough evidence to classify them.

Frontier selection affects only which already-frozen task IDs are sampled next. It may not rewrite task content, expected answers, or scoring after observing model output.

## Scheduler and Call Economy

Every pending batch has a `decision_reason`, `decision_target`, expected information value, and maximum calls. Valid reasons include baseline establishment, semantic-gain resolution, budget-boundary localization, temperature-boundary localization, interaction resolution, and holdout certification.

The scheduler removes work when the corresponding decision becomes settled. The live progress display reports calls completed, currently projected calls remaining, elapsed wall time, and ETA, with projected work shrinking as candidates are eliminated.
## Call Budget Geometry

The old fixed 500-call ceiling is not silently reused when it would make valid certification impossible. V2 computes minimum, expected, and worst-case physical-call geometry from the selected families, checkpoint schedule, paired profiles, and adapter call cost before launch.

The campaign manifest contains a preregistered hard ceiling. Launch fails before any model call if the ceiling cannot support the minimum required evidence for the requested scope.

The hard ceiling remains an abort guard; adaptive pruning is expected to finish materially below the worst case. A stage that cannot change a policy decision is removed rather than run merely because budget remains.

## Universal Engine Boundaries

The existing Qwen command becomes a thin configuration over reusable components:

- `ExperimentSpec` — protocol version, families, parameter axes, statistical gates, evidence checkpoints, and call ceiling.
- `ModelAdapter` — model identity, runtime provenance, supported inference parameters, default anchors, and physical-call semantics.
- `TaskFamily` — deterministic generator, difficulty strata, canonicalizer, and scorer.
- `ParameterAxis` — candidate generation and refinement rules for budget, temperature, or future parameters.
- `EvidenceStore` — immutable raw envelopes plus append-only normalized observations and derived analyses.
- `DecisionEngine` — paired statistics, superiority/non-inferiority decisions, plateau detection, and family status.
- `AdaptiveScheduler` — schedules only evidence capable of changing an unresolved decision.
- `ProgressReporter` — responsive terminal progress, projected calls, elapsed wall time, and ETA.

Changing models or adding a future parameter must not require rewriting task generation, scoring, statistics, or evidence storage.
## Evidence Integrity and Resume

Each generated task pool, manifest, scorer definition, parameter grid seed, bootstrap seed, model adapter configuration, and runtime provenance record is hashed before inference. Resume validates those hashes before adding evidence.

Completed trials are never repeated automatically. A resumed campaign reconstructs scheduler state from committed observations and continues only unresolved decisions.

Raw evidence is append-only. Derived rescoring and statistical summaries are written as separate artifacts with explicit source hashes so an evaluator change cannot rewrite history.

The V2 implementation remains outside the frozen Test-1 source-binding directories. Existing Test-1 cryptographic guardrails must not be weakened to accommodate the universal tuner.

## Failure Classification

Model failures are classified at the smallest causal layer supported by evidence:

- `SEMANTIC_FAIL`
- `CONTRACT_FAIL`
- `COMPLETION_FAIL`
- `CAPABILITY_LIMIT`
- `PARAMETER_SENSITIVITY`
- `INFRASTRUCTURE_FAIL`
- `PROVENANCE_FAIL`
- `SCORER_INVALID`

A scorer defect invalidates the affected derived decision but does not invalidate preserved raw model evidence. Infrastructure or provenance failures stop affected inference rather than being counted as model errors.
## Final Policy Output

Each family policy reports:

- selected mode: direct, thinking, or unresolved;
- semantic accuracy and confidence interval;
- contract accuracy and completion reliability;
- direct-versus-thinking paired semantic delta;
- minimum useful reasoning budget and observed natural-thinking distribution;
- tested temperature range, validated plateau bounds, recommended operating point when justified, and achieved resolution;
- reason temperature refinement stopped;
- interaction-test result;
- holdout sample size and checkpoint reached;
- dominant failure classes;
- decision status and evidence hashes.

The policy must distinguish `temperature_optimum` from `temperature_plateau`. A value such as `0.798` is forbidden as an optimum unless paired semantic evidence actually resolves the surface to that precision.

## Human-Readable Report

The run also emits a concise report showing, per family, what thinking bought, what it cost, where the capability boundary moved, which contract failures remain, and why additional calls stopped. It includes no unsupported ranking based on timing noise.

The report highlights reusable system lessons, such as cases where a deterministic formatter or verifier would eliminate contract failures without spending more model reasoning.
## Test Strategy

Implementation proceeds by TDD. Required test classes include:

- deterministic task generation and immutable pool hashing;
- semantic canonicalization versus contract scoring for each family;
- executable coding oracles and negative cases;
- paired comparison statistics and deterministic bootstrap reproducibility;
- superiority, non-inferiority, plateau, and unresolved decision boundaries;
- checkpoint expansion from 40 to 60, 80, and 120 atomic tasks;
- early loser elimination without early winner certification;
- budget bracketing and minimum-useful-budget selection;
- temperature plateau discovery, edge expansion, and stop-on-no-information behavior;
- bounded budget × temperature interaction logic;
- call-budget geometry and pre-launch insufficiency rejection;
- resume without duplicate calls;
- raw-evidence immutability and derived-rescore provenance;
- responsive terminal progress at wide and narrow window sizes;
- synthetic adversarial surfaces where the true answer is a plateau, narrow optimum, monotonic boundary, noisy tie, and contract-only failure.

The synthetic harness must prove the engine can refuse false precision, not merely recover a planted point optimum.
## Migration From V1

The current `scripts/run-qwen-thinking-tuning.ps1` remains the primary launcher. Existing V1 artifacts remain readable. V2 writes a new protocol manifest and new artifact names or versioned schemas so old evidence cannot be mistaken for V2 evidence.

The current `qwen_thinking_tuning.py` behavior may be decomposed into focused modules during implementation, but the public launcher and model-specific entry point remain stable.

The first V2 campaign targets the same twelve Qwen3.5 9B task families. The universal abstraction is implemented only where required by those families and the known future need to swap models/parameter axes; no unrelated framework features are added.

## Acceptance Criteria

The redesign is complete only when all of the following are true:

1. The existing 192-call run can be rescored without mutating any original evidence.
2. Semantic and contract outcomes are independently visible for every atomic task.
3. No profile can be certified from fewer than forty fresh atomic tasks.
4. Close profile comparisons expand automatically through preregistered checkpoints.
5. Temperature search returns a plateau when evidence does not justify a point optimum.
6. A synthetic broad plateau cannot produce a fake thousandths-place winner from latency noise.
7. The minimum useful reasoning budget is selected by semantic non-inferiority, not by largest configured cap.
8. Budget × temperature interaction receives fresh bounded validation before final certification.
9. Every model call has a decision reason and disappears when that decision is settled.
10. The same engine can run another model adapter or task-family specification without rewriting campaign logic.
11. Resume, evidence hashing, provenance binding, hard-call ceilings, and responsive progress remain intact.
12. Full repository regression is green before any real V2 campaign is authorized.

## Explicit Non-Goals

V2 does not fine-tune model weights, add Inverted Brain or Historical Seed treatments, compare multiple model sizes, or launch a new Harvest campaign. It establishes a trustworthy universal operating-surface measurement instrument first.