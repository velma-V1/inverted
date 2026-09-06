# Inverted Brain Test 2 — Frontier Mechanism Harvest

## Status
Preregistered design for the dedicated `inverted-brain` branch. This experiment is separate from the original Inverted executor-vs-auditor benchmark on `main`. Existing Inverted and historical Brain evidence is immutable.

## Primary Question
Can observable successful behaviors from Claude Code and Codex be reduced to a minimal, causally supported mechanism that repairs a Qwen3.5-9B + Inverted-Brain frontier failure and transfers to fresh unseen tasks without unacceptable negative transfer?

The experiment is not successful merely because Claude/Codex outperform Qwen or because a larger prompt improves Qwen. A retained mechanism must be localized, causally supported, minimal, transferable, and independently verified.

## Research Basis
The design incorporates current agent-diagnosis and learning evidence:

- AgentRx (Microsoft Research, 2026) shows that step-by-step constraint evaluation and localization of the first unrecoverable/critical failure step materially improves failure localization and root-cause attribution over prompting-only baselines.
- Causal Agent Replay and CausalFlow (2026) motivate intervention-based attribution: modify or remove a candidate step/behavior and replay forward rather than inferring causality from trajectory appearance alone.
- Long-Horizon Agent Trajectory Attribution (2026) uses standardized trajectory components plus leave-one-out/incremental perturbation baselines, supporting component-level ablation rather than whole-trace imitation.
- From Patches to Trajectories (2026) finds that training on shorter, grounded, information-bearing teacher trajectory segments can improve success while reducing inference cost; full teacher traces can contain redundant or flawed behavior.
- Verified Critical Step Optimization (ACL 2026) reports strong gains by supervising only a small fraction of verified critical steps, supporting selective mechanism extraction rather than broad prompt growth.
- Universal Verifier work (Microsoft Research, 2026) supports separate process and outcome scoring and non-overlapping verifier rubrics.
- Failure-learning work (ACL 2024–2026) shows that negative trajectories can be useful when converted into controlled contrastive or calibrated examples rather than learned wholesale.
- Curriculum Replay via Progressive Suffixes (ACL 2026) supports keeping tests near the current competence boundary so outcomes remain informative instead of collapsing to all-pass or all-fail.

## Models and Fixed Roles
- `QWEN_BRAIN_BASE`: `qwen3.5:9b-q8_0`, current frozen Brain, Qwen-recommended non-thinking sampling preset, fixed seed policy.
- `CLAUDE_RAW`: Claude Code with only neutral arena/tool plumbing.
- `CODEX_RAW`: Codex with only neutral arena/tool plumbing.
- `QWEN_BRAIN_CANDIDATE`: same Qwen weights/runtime as baseline plus exactly one candidate mechanism under test.

Claude/Codex are teachers/reference agents only. Their full prompts, policies, or trajectories may not be copied into Qwen.

## Experimental Phases

### Phase 0 — Infrastructure and Contamination Gate
Before any scientific call:
1. freeze task-generator code, verifier code, model/runtime configuration, Brain baseline hash, and branch commit;
2. verify no overlap with D3/Test2 task texts, private answers, or prior Brain holdouts;
3. confirm every arm starts from an identical workspace snapshot;
4. confirm hidden verifier artifacts are outside writable model workspaces;
5. confirm raw prompts and complete observable trajectories are logged;
6. abort as infrastructure-invalid if evidence identity, model fingerprint, or task hash changes.

### Phase 1 — Adaptive Frontier Discovery
Generate a sealed pool of 60 new tasks from multiple task grammars. Difficulty is controlled along independent dimensions rather than a single scalar:
- explicit-constraint count;
- cross-file dependency depth;
- state mutation depth;
- stale-evidence risk;
- distractor/decoy count;
- repair branching factor;
- negative/invariant constraints;
- evidence ambiguity;
- tool-budget pressure;
- temporal/order dependency;
- hidden downstream interaction;
- ontology/interface novelty.

The sampler adapts toward Qwen's mixed-outcome region. Trivial all-pass and impossible all-fail strata are retained as calibration evidence but receive no additional teacher budget. Preferred harvest region is where baseline Qwen success is neither near 0% nor near 100% across repetitions.

### Phase 2 — Teacher Harvest
Select approximately 20 Qwen failures or near-failures from the informative frontier. Run Claude RAW and Codex RAW on the identical frozen task/workspace.

Highest-value harvest cases are:
- Qwen fails and both teachers pass;
- Qwen fails and one teacher passes via a reproducible mechanism;
- Qwen passes only intermittently while teacher trajectories converge on a common behavior.

All-agent failure is evidence of a likely true frontier and is not used to invent a mechanism.

### Phase 3 — Normalized Trajectory Representation
Normalize observable events into a common schema:
- state observations / files inspected;
- observation order;
- tool calls and results;
- explicit tests/assertions executed;
- first mutation;
- state rereads after mutation;
- dependency exploration;
- candidate/repair changes;
- rollback/reconstruction;
- final verification actions;
- failures/tool errors and recovery;
- wall time, calls, token/cost telemetry when available.

No private chain-of-thought is required or inferred.

### Phase 4 — Critical Divergence Localization
For each Qwen-fail/teacher-pass case, locate the earliest point after which the Qwen trajectory can no longer reach a verified pass without changing the policy/action choice. Maintain an evidence-backed constraint log at each step.

Candidate failure classes include, but are not limited to:
- intent/constraint representation;
- wrong evidence acquisition;
- stale-state use;
- tool-output misinterpretation;
- wrong dependency selection;
- premature commitment/mutation;
- failure to preserve an invariant;
- failure migration during repair;
- insufficient reconstruction;
- wrong verification criterion/timing;
- unsupported inference;
- compute/tool-budget allocation.

The taxonomy is descriptive, not a closed answer key; novel classes may be added when supported by evidence.

### Phase 5 — Causal Replay / Ablation
A behavior is not considered causal merely because successful teachers exhibit it.

For each candidate mechanism, construct intervention variants that remove, replace, delay, or force the behavior while holding the rest of the task/environment constant as far as practical. Replay from the nearest branchable state when possible.

Preferred evidence hierarchy:
1. both Claude and Codex pass normally, and targeted removal of mechanism X causes a verified degradation in both;
2. one teacher shows the effect repeatedly across independent tasks and removal causes degradation;
3. component-level leave-one-out or counterfactual replay changes outcome probability materially;
4. purely correlational trajectory difference — insufficient for retention by itself.

Interactions are allowed: if X alone is insufficient but X+Y is necessary, record an interaction candidate rather than falsely assigning all credit to one step.

### Phase 6 — Minimal Contrastive Mechanism Extraction
For a causally supported divergence, derive the smallest implementation-neutral rule/state transition needed to distinguish the failed and successful behavior.

Store a contrastive record:
- triggering state/guard;
- baseline failed behavior;
- minimally changed behavior;
- evidence supporting necessity;
- known scope/boundaries;
- expected compute/tool cost;
- counterevidence and failed ablations.

Do not store the teacher's full trajectory as a Brain law.

### Phase 7 — Qwen Candidate Test
Add exactly one candidate mechanism (or one preregistered interaction bundle when indivisible) to the Brain candidate arm.

Run paired baseline-vs-candidate on development cases that were not used to derive the exact wording. Candidate must repair the predicted failure class without broad prompt-specific leakage.

### Phase 8 — Fresh Transfer Holdout
Freeze the candidate before generating/opening the final holdout.

Run 24 fresh tasks across at least four task grammars:
- baseline Qwen Brain;
- Qwen Brain + candidate mechanism.

Use repeated fixed seeds where stochasticity matters. Both arms receive identical information, tools, context ceiling, and verifier.

## Retention Gates
A candidate Brain mechanism is retained only if all required gates pass:
1. **Causal support:** intervention/ablation evidence shows the candidate materially affects outcome or process validity.
2. **Fresh lift:** candidate improves verified fresh-holdout success by a preregistered meaningful margin (default >= 12.5 percentage points, i.e. at least 3/24 additional passes) unless a harder frontier metric is explicitly preregistered before holdout reveal.
3. **No material regression:** no more than one baseline-pass case becomes a candidate failure, and no new catastrophic/invariant-breaking failure appears.
4. **Cross-grammar:** improvement occurs in at least two distinct task grammars or is explicitly bounded to one verified domain rather than generalized.
5. **Mechanism match:** repaired cases exhibit the predicted process change, not an unrelated lucky outcome.
6. **Complexity rent:** added prompt/tool/call cost is recorded; a large cost increase requires proportionally larger capability lift.
7. **No benchmark encoding:** mechanism contains no task IDs, answers, private ontology labels, or generator-specific literals unnecessary to the causal rule.

Failure of a retention gate preserves the candidate and evidence as rejected/limited; it is never silently deleted.

## Process and Outcome Scoring
Score separately:
- terminal outcome correctness;
- explicit requirement satisfaction;
- invariant preservation;
- process validity / prohibited-action violations;
- verification completeness;
- controllable vs infrastructure/uncontrollable failure;
- tool/call/token/time cost.

A passing output with an invalid prohibited process is not merged into clean success statistics.

## Evidence Contract
For every trial preserve:
- exact task package and task hash;
- model/runtime/Brain hashes and inference options;
- exact visible prompts/messages;
- raw responses;
- normalized trajectory and raw tool events;
- stdout/stderr;
- workspace pre/post hashes and diff;
- verifier rubrics and result;
- failure/critical-step annotations;
- intervention definition and replay result;
- candidate-mechanism record;
- timestamps, wall time, token/cost fields where exposed;
- SHA-256 manifest.

Aborted/infrastructure-invalid trials remain evidence but are excluded from scientific denominators.

## Budget
Initial ceiling: approximately 200 agent runs, allocated adaptively rather than spent uniformly.
- Frontier discovery: up to ~60 Qwen runs plus limited repeats.
- Teacher harvest: up to ~40 teacher runs focused on informative Qwen frontier cases.
- Causal interventions/ablations: up to ~48 runs.
- Qwen candidate vs baseline fresh transfer: ~48 runs.

Unused calls are not spent merely to hit the ceiling.

## Primary Success Claim
The strongest allowed positive claim is:

> A previously unencoded behavioral mechanism was localized from Qwen frontier failures, supported by counterfactual/ablation evidence from successful frontier-agent trajectories, reduced to a minimal implementation-neutral Brain intervention, and moved the same fixed Qwen3.5-9B model on fresh sealed tasks without unacceptable regression.

This test cannot by itself prove universal intelligence improvement or full reasoning-architecture replacement.

## Primary Failure/Null Outcomes
Valuable null results include:
- teachers do not reliably outperform Qwen in the selected frontier region;
- teachers pass but do not share/reproduce a localizable mechanism;
- apparent mechanisms fail causal replay;
- a causal teacher mechanism is not reachable/effective for Qwen;
- candidate improves development cases but not fresh holdout;
- candidate causes negative transfer exceeding the retention gate.

Each null result narrows what kinds of knowledge the Inverted Brain can safely compile.
