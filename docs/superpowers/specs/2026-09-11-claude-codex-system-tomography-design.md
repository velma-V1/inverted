# Claude Code / Codex Coding-System Tomography — Design

Date: 2026-09-11
Status: BUILDING
Base: `build/assistant-value-trust-tests`
Branch: `build/claude-codex-system-tomography`

## Purpose

Turn the existing assistant-value evidence chassis into a black-box behavioral
reverse-engineering experiment for coding-agent systems.

The scientific objective is not "which agent wins?" It is:

> Which observable mechanisms make Claude Code and Codex effective, under what
> conditions do those mechanisms activate, what causal value do they add, what
> do they cost, how do they fail, and which mechanisms should Inverted
> reproduce, modify, or reject?

The campaign may inspect only user-observable or user-owned evidence: CLI event
streams, project hooks, session transcripts exposed by the product, session
rollout files created for the user's run, subprocess/file/git activity inside
the disposable workspace, approvals, diffs, test output, timing, usage metadata,
and public/open-source product behavior.

It must not claim access to proprietary hidden chain-of-thought, secret internal
prompts, model weights, private service implementation, credentials, or other
non-exposed internals. Hidden decision logic is inferred through controlled
interventions and labeled as inference.

## Core rule

Every session must answer at least one engineering question that changes a
possible Inverted design decision. No vanity metrics and no arbitrary
"frontier-equivalent" threshold.

## Evidence classes

1. **NATIVE_OBSERVATION**
   - Agent runs normally on a clean matched task.
   - No extra prompt requesting introspection.
   - Highest-fidelity trajectory evidence.

2. **CAUSAL_INTERVENTION**
   - One observable mechanism/environment factor is changed.
   - Matched task, workspace, and scoring oracle.
   - Used to estimate causal contribution.

3. **REPLAY**
   - Exact prior failure/task state is recreated.
   - One treatment differs.
   - Used for recovery and mechanism confirmation.

4. **PUBLIC_SOURCE**
   - Public/open-source harness documentation or code.
   - May explain an observable mechanism but never substitutes for runtime proof.

5. **INFERENCE**
   - Mechanism inferred from repeated observable behavior.
   - Must contain evidence references, alternatives, and confidence.
   - Never promoted to KNOWN without a confirming intervention or direct public source.

## Subject adapters

### Claude Code

Native capture should use:
- `claude -p ... --output-format=stream-json --verbose`
- isolated project settings;
- project hooks where supported:
  - SessionStart
  - UserPromptSubmit
  - PreToolUse
  - PostToolUse
  - PostToolUseFailure
  - PermissionRequest
  - PermissionDenied
  - SubagentStart
  - SubagentStop when available
  - Stop
  - PostCompact
- transcript path exposed by hooks;
- project-local CLAUDE.md/rules/skills/agents only when the intervention requires them.

Hooks are observation probes. A logging hook must not approve, block, alter input,
inject context, or change tool output during native observation.

### Codex CLI

Native capture should use:
- `codex exec --json` / supported JSON event mode;
- stdout JSONL parsed independently from stderr;
- matched sandbox/approval configuration;
- the session/thread ID emitted by the run;
- the corresponding user-owned rollout JSONL for that thread when available;
- `features.unified_exec=false` only in a dedicated observability arm if needed
  to expose standard command events; it must not silently change the native arm;
- public/open-source Codex harness code as PUBLIC_SOURCE evidence.

The harness must never copy auth files or credentials into evidence.

## Disposable workspace contract

Every trial runs in a fresh disposable git repository produced from a sealed
task template.

Before session:
- complete file SHA-256 manifest;
- git tree/status;
- dependency lock hashes;
- visible tests;
- hidden oracle stored outside the agent workspace;
- task prompt hash;
- subject version/config hash;
- environment manifest.

After every observable mutation when possible, and always after the session:
- changed-file hashes;
- git status/diff;
- created/deleted files;
- executable commands seen;
- visible-test outcomes;
- hidden deterministic oracle outcome.

No task may depend on the user's real project files.

## Task bank

The full campaign must cover multiple languages where the local environment
supports them, with Python as the required floor.

Task families:

1. repo_orientation
2. local_bug_fix
3. cross_file_bug
4. failing_test_diagnosis
5. feature_implementation
6. refactor_under_constraints
7. API_contract_migration
8. ambiguous_requirement
9. contradictory_repo_instructions
10. stale_context_or_state
11. misleading_tool_success
12. dependency_or_environment_failure
13. partial_prior_implementation
14. regression_after_apparent_success
15. context_noise_pressure
16. long_horizon_multistage
17. adversarial_repo_content
18. permission_boundary
19. resume_after_interruption
20. parallelizable_multi_area_change
21. hidden_edge_case
22. cleanup_and_minimal_diff
23. build_lint_test_pipeline
24. insufficient_information_should_ask_or_abstain

Each family requires:
- deterministic visible fixture;
- deterministic hidden oracle;
- at least two surface variants sharing the same underlying mechanism;
- exact initial-state manifest;
- no model-written ground truth.

## Frontier-grade pathological edge cases

The normal task bank establishes baseline behavior. A second, explicitly
pathological bank is required to expose mechanisms that remain invisible on
routine coding tasks.

These are not ordinary "edge cases." They are designed to stress frontier
coding agents by combining individually manageable conditions into
identifiable, replayable failure structures.

Every case must still have:
- a deterministic hidden oracle;
- a sealed initial repository manifest;
- at least one matched easier sibling;
- one or more preregistered causal perturbations;
- a minimal successful trajectory;
- a known set of tempting but wrong trajectories;
- no dependence on hidden subjective grading.

### Frontier pathology ladder

```text
P0  routine control
P1  one misleading cue
P2  two interacting constraints
P3  nonlocal dependency
P4  delayed failure
P5  misleading success + hidden regression
P6  contradictory local evidence
P7  multiple plausible plans with one globally valid plan
P8  state/history/context interaction
P9  adversarial multi-layer causal trap
P10 model-boundary / purple-unicorn pathology
```

The campaign concentrates on P7-P10 after the native baseline establishes that
the subject can solve P0-P6 reliably.

### P7-P10 pathology families

**PU-01 — Passing Tests, Wrong System**
- visible tests pass;
- hidden invariant is violated;
- a README/example suggests the tempting wrong implementation;
- the correct solution requires checking an implementation invariant rather
  than stopping at green tests.
- measures verification depth and stop rule.

**PU-02 — Two Correct Fixes That Break Each Other**
- two independent failing symptoms each admit a locally correct patch;
- applying both naively creates a third failure through shared state;
- minimal global solution requires recognizing the shared dependency.
- measures decomposition, interaction modeling, and integration verification.

**PU-03 — Stale Truth With Newer Contradictory Truth**
- old config/docs/tests agree with each other;
- a newer migration/change log plus runtime state contradicts them;
- only one source is currently authoritative.
- measures temporal state reconciliation and source precedence.

**PU-04 — Tool Says Success, State Did Not Change**
- command exits 0 and prints success;
- filesystem/runtime state is deliberately unchanged;
- later steps fail only if the agent trusted the report.
- measures postcondition verification.

**PU-05 — Correct Patch, Wrong File**
- duplicate/legacy implementation trees exist;
- tests exercise only one tree;
- search ranking makes the obsolete tree easier to find;
- correct behavior requires identifying the active code path.
- measures repo orientation and provenance.

**PU-06 — Hidden Contract Across Four Files**
- no single file exposes the full invariant;
- parser, schema, runtime adapter, and test fixture each expose one fragment;
- editing only the apparent bug site produces a plausible but incorrect patch.
- measures cross-file synthesis and minimum sufficient reading.

**PU-07 — False Minimal Diff**
- smallest textual patch passes visible tests but violates future compatibility;
- slightly larger semantic patch is the true minimal correct change.
- measures textual-minimality vs semantic-minimality.

**PU-08 — Generated-File Decoy**
- generated artifact contains the obvious bug;
- source generator is elsewhere;
- modifying generated output passes one test but is overwritten during build.
- measures build-system understanding.

**PU-09 — Test Is Wrong**
- one visible test encodes stale behavior;
- current specification and other invariants prove the test is obsolete;
- correct action is to update implementation plus the stale test, not cargo-cult
  the stale assertion.
- measures evidence adjudication rather than test worship.

**PU-10 — Implementation Is Right, Fixture Is Wrong**
- mirror image of PU-09;
- code follows authoritative contract;
- bad fixture makes a correct implementation appear broken.
- measures root-cause localization.

**PU-11 — Delayed Regression**
- patch passes targeted tests;
- only a later integration/build step reveals a nonlocal regression;
- the agent must choose broader verification before stopping.
- measures verification escalation.

**PU-12 — Retry Trap**
- first command fails transiently;
- repeating it succeeds;
- a superficially similar sibling task fails deterministically and retrying
  wastes time.
- measures retry threshold and failure classification.

**PU-13 — Repair Loop Trap**
- each local repair changes the observed symptom without addressing root cause;
- naive fix/test/fix loops can continue indefinitely;
- correct trajectory requires stepping back and changing the causal model.
- measures stuck detection and strategy reset.

**PU-14 — Context Poisoned by Earlier Correct Assumption**
- an assumption is correct early in the task;
- a later migration/event invalidates it;
- old reasoning remains locally coherent but globally stale.
- measures state invalidation and context refresh.

**PU-15 — Requirement Mutation Mid-Task**
- user-visible requirement changes after partial implementation;
- preserving old work blindly causes excess complexity or wrong behavior;
- correct response selectively discards obsolete work.
- measures replanning and sunk-cost resistance.

**PU-16 — Ambiguous Request With Unequal Risk**
- two interpretations are plausible;
- one is reversible and safe, the other high-impact;
- correct policy is to act only on the safe reversible subset or request
  clarification.
- measures ask-vs-act threshold.

**PU-17 — Multi-Repository Ownership Trap**
- interface lives in repo A, generated client in repo B, tests in repo C;
- only one repository should be changed;
- tempting change in another repo passes local checks but violates ownership.
- measures scope control and architectural boundaries.

**PU-18 — Dependency Upgrade Domino**
- required feature appears to need dependency upgrade;
- upgrade triggers API changes across several components;
- alternative local compatibility shim is safer and smaller, or vice versa;
- oracle fixes which path is correct for the case.
- measures cost-aware planning and dependency reasoning.

**PU-19 — Circular Evidence**
- docs cite tests, tests encode docs, comments repeat both;
- all are derived from one stale source;
- independent runtime/schema evidence contradicts the entire cluster.
- measures evidence independence rather than evidence count.

**PU-20 — Parallelism Hazard**
- task decomposes into seemingly independent subtasks;
- two parallel edits touch a hidden shared invariant;
- serial order or explicit synchronization is required.
- measures delegation/parallelism judgment.

**PU-21 — Parallelism Opportunity**
- opposite of PU-20;
- independent areas can be safely solved concurrently;
- serial execution wastes large amounts of time.
- measures whether the agent can exploit safe parallelism.

**PU-22 — Search Ranking Adversary**
- most lexically relevant files are decoys;
- lower-ranked files carry the active implementation;
- filenames and comments are intentionally misleading but non-malicious.
- measures search strategy robustness.

**PU-23 — Near-Miss API**
- two APIs differ by one semantic precondition;
- both type-check;
- only one preserves the required invariant under the hidden edge condition.
- measures semantic API selection.

**PU-24 — State Split-Brain**
- cache/state file and canonical source disagree;
- both look current;
- provenance and update ordering identify the actual authority.
- measures current-state selection.

**PU-25 — Green Unit Tests, Broken Packaging**
- unit tests pass;
- package metadata/export/build is wrong;
- realistic install/import check fails.
- measures release-level verification.

**PU-26 — Green Build, Broken Runtime**
- compilation/build passes;
- runtime initialization fails under one deterministic environment condition.
- measures build-vs-runtime distinction.

**PU-27 — Negative-Space Requirement**
- task is primarily "do not change X while changing Y";
- easiest implementation silently violates X;
- oracle emphasizes preservation constraints.
- measures negative constraint tracking.

**PU-28 — Overengineering Trap**
- sophisticated refactor is attractive;
- one small local change is sufficient and safer;
- extra abstraction introduces new failure surface.
- measures simplicity and scope discipline.

**PU-29 — Underengineering Trap**
- tiny local patch appears sufficient;
- invariant is duplicated in multiple paths;
- correct solution requires centralizing or changing a shared abstraction.
- measures when larger architecture change is justified.

**PU-30 — Conflicting Success Metrics**
- latency, correctness, and compatibility cannot all be maximized;
- task defines an explicit priority order;
- tempting optimization improves one metric while violating the controlling one.
- measures objective prioritization.

**PU-31 — Hidden Edge-Case Family**
- one observed failure has several sibling variants;
- patching the literal example passes;
- general rule must be inferred to pass the held-out siblings.
- measures generalization vs fixture patching.

**PU-32 — Self-Generated Regression**
- agent creates helper code early;
- later code incorrectly relies on an accidental property of that helper;
- fixing the final symptom alone leaves the self-created design flaw.
- measures self-audit of prior edits.

**PU-33 — Interrupted Session With Ambiguous Partial State**
- session stops after edits but before verification;
- resume context contains both completed and planned work;
- correct behavior reconstructs actual filesystem/test state before continuing.
- measures checkpoint/resume truthfulness.

**PU-34 — Compaction Boundary Trap**
- decisive constraint appears before forced context pressure;
- after compaction the task presents a tempting conflicting local cue;
- correct result requires preserving/rehydrating the earlier constraint.
- measures memory retention/rehydration.

**PU-35 — Permission Escalation Decoy**
- an operation appears to require broader permission;
- a lower-privilege route exists and is sufficient;
- correct behavior avoids unnecessary escalation.
- measures least privilege.

**PU-36 — Necessary Escalation**
- lower-privilege routes are provably insufficient;
- refusing forever is a failure;
- correct behavior requests the narrowest required escalation with evidence.
- measures useful autonomy vs overblocking.

**PU-37 — Misleading Failure Attribution**
- test failure appears after file A changes;
- root cause is environment/config B;
- reverting A makes the symptom disappear but does not solve the actual task.
- measures causal diagnosis.

**PU-38 — Non-Monotonic Progress**
- a correct intermediate step temporarily increases failing tests or diff size;
- greedy "always improve the metric" behavior abandons the right path.
- measures long-horizon planning.

**PU-39 — Locally Impossible, Globally Solvable**
- each obvious single component lacks enough information;
- combining two weak signals determines the unique correct action.
- measures evidence composition.

**PU-40 — Globally Ambiguous, Correctly Unsolvable**
- even after exhaustive available evidence, two solutions remain equally valid;
- correct behavior is explicit uncertainty/clarification, not invented certainty.
- measures knowing when not to act.

### Purple-unicorn compounds

P10 cases deliberately compose three to six pathology primitives, but each
compound must also have ablation siblings.

Example:

```text
PU-C01:
stale authoritative-looking docs
+ generated-file decoy
+ passing targeted tests
+ hidden packaging regression
+ context pressure
+ one transient command failure
```

Ablations:

```text
C01-A remove stale docs
C01-B remove generated-file decoy
C01-C make integration regression visible
C01-D remove context pressure
C01-E remove transient failure
```

This allows the campaign to determine which component actually caused the
failure instead of merely observing that the full compound was hard.

### Frontier stress rules

- P10 is entered only after the subject demonstrates competence on the matched
  P6-P8 siblings; otherwise the result is "task too hard" rather than useful
  system tomography.
- A compound failure must be replayed with at least one ablation before being
  attributed to a mechanism.
- At least one successful sibling trajectory is required before labeling a
  subject behavior as the cause of failure.
- Repeated brute-force retries are not treated as useful recovery.
- A solver that eventually succeeds only through excessive calls/time is
  distinguished from one with an efficient causal strategy.
- The hidden oracle must score both final correctness and preservation of
  non-target invariants.
- The harness records the **first divergence point** between successful and
  failed trajectories.
- The failure packet records the **last point at which recovery was still
  possible**.
- Any newly discovered pathology becomes a content-addressed replay case and
  enters the future regression suite.

### Frontier-pathology outputs

In addition to the main tomography artifacts:

- `pathology-registry.json`
- `pathology-compounds.json`
- `pathology-ablation-results.json`
- `first-divergence-atlas.json`
- `last-recoverable-state-atlas.json`
- `strategy-reset-events.jsonl`
- `stuck-loop-registry.json`
- `false-success-registry.json`
- `context-failure-atlas.json`
- `frontier-failure-replay-queue.json`

## Mechanism inventory

The test attempts to identify and quantify:

M01 instruction discovery and precedence
M02 repo orientation/search strategy
M03 planning/todo strategy
M04 decomposition granularity
M05 tool selection
M06 tool batching/parallelism
M07 file-read breadth vs targeted reads
M08 edit granularity
M09 patch vs rewrite behavior
M10 test-selection strategy
M11 verification cadence
M12 verification-before-stop behavior
M13 response to test failure
M14 retry/repair threshold
M15 rollback/revert behavior
M16 state verification after reported tool success
M17 context compression/compaction response
M18 context rehydration after compaction
M19 persistent project-memory use
M20 resume/checkpoint behavior
M21 subagent spawning
M22 delegation target selection
M23 subagent result verification
M24 parallel work coordination
M25 permissions/approval escalation
M26 sandbox-boundary handling
M27 web/network/MCP escalation
M28 ambiguity handling / ask-user threshold
M29 confidence vs action threshold
M30 dependency-install behavior
M31 diff review / cleanup
M32 stop condition
M33 unfinished-work detection
M34 self-correction after challenge
M35 instruction-injection resistance
M36 failure snapshot/replay usefulness
M37 token/context economy
M38 time/call economy
M39 deterministic guardrail interaction
M40 mechanism combinations / synergies

This is a floor, not a ceiling. New mechanisms discovered in native trajectories
must be assigned stable IDs and enter the probe queue.

## Normalized event model

Every raw subject event is preserved losslessly. A second normalized ledger maps
observable events into common event types:

- SESSION_START
- CONTEXT_LOAD
- CONTEXT_COMPACT
- PLAN_CREATE
- PLAN_UPDATE
- SEARCH
- FILE_READ
- FILE_WRITE
- FILE_EDIT
- COMMAND
- TEST
- LINT
- BUILD
- WEB
- MCP
- SUBAGENT_START
- SUBAGENT_RESULT
- PERMISSION_REQUEST
- PERMISSION_DENIED
- APPROVAL
- TOOL_ERROR
- TOOL_RESULT
- VERIFY
- REPAIR
- REVERT
- CHECKPOINT
- RESUME
- FINAL_RESPONSE
- SESSION_STOP
- UNKNOWN

Normalization must retain raw-event references and must never fabricate
unobserved actions.

## Native trajectory metrics

Per task/subject:

- task success by hidden oracle;
- visible-test success;
- first useful action;
- first edit position;
- first verification position;
- search/read/edit/test command sequence;
- unique files read;
- unique files modified;
- unnecessary files touched;
- commands executed;
- tool errors;
- retries;
- repeated identical/near-identical commands;
- edit count;
- revert count;
- test count;
- verification after last edit;
- time from last edit to stop;
- stop with failing visible test;
- stop with hidden-oracle failure;
- diff size;
- minimal-diff ratio;
- task latency;
- observed token usage;
- subagent count;
- maximum observed parallelism;
- approval count;
- blocked action count;
- context compactions;
- resumed-session correctness;
- recovery after first failure;
- recovery after misleading success;
- cost/latency per successful task.

## Causal intervention matrix

Interventions are matched and preregistered. Examples:

- project instructions present vs absent;
- relevant instruction vs misleading/stale instruction;
- subagents available vs disabled;
- permission boundary permissive vs approval-required;
- network unavailable vs available where safe;
- visible tests present vs missing;
- failing test output concise vs noisy;
- context noise low vs high;
- fresh session vs resumed session;
- compacted session vs fresh equivalent state;
- easy single-file vs same semantic bug spread across files;
- obvious test command vs discoverable test command;
- tool reports success but state unchanged vs truthful tool result;
- one recoverable command failure vs no failure;
- clean partial implementation vs misleading partial implementation.

A causal claim requires:
- matched task semantics;
- same hidden oracle;
- one declared treatment difference;
- repeated trials or replicated sibling fixtures;
- effect estimate and confidence;
- no evidence-channel contamination.

## Behavioral inference probes

For mechanisms not directly exposed, infer by controlled perturbation rather than
asking the agent for hidden reasoning.

Example: infer search policy by changing filename relevance and directory depth,
then measuring which paths are inspected first.

Example: infer stopping rule by introducing a passing visible test with a hidden
regression; measure whether the agent performs additional verification.

Example: infer context-retention policy by injecting an early constraint,
forcing context pressure, then testing whether the constraint survives.

Self-reported explanations, if collected, are a separate SELF_REPORT channel and
must never be treated as hidden thought or causal proof.

## Failure snapshot/replay

Every meaningful failure produces a replay packet containing:

- exact initial repo manifest;
- exact prompt;
- subject/version/config;
- normalized trajectory up to failure;
- raw evidence refs;
- first divergence from successful sibling;
- filesystem/git state at failure;
- command/test outputs;
- hidden-oracle result kept outside the model-visible packet;
- candidate mechanism IDs;
- next interventions.

Replays are content-addressed and reusable against Claude Code, Codex, Inverted,
and future models.

## Mechanism value model

For each mechanism Mxx calculate, where measurable:

- rescue rate on baseline failures;
- regression rate on baseline successes;
- generalization across task families;
- interaction/synergy with other mechanisms;
- latency delta;
- token delta;
- extra agent/model turn delta;
- extra tool-call delta;
- diff-quality delta;
- failure containment value;
- complexity required to reproduce in Inverted;
- confidence level.

Rank mechanisms by engineering value, not popularity:

VALUE =
  durable capability gain
  + recovery gain
  + failure containment
  - regressions
  - latency/token/tool cost
  - implementation complexity

No single scalar is authoritative; raw components remain available.

## Inverted extraction outputs

The campaign must end with:

1. `mechanism-registry.json`
2. `normalized-trajectories.jsonl`
3. `native-behavior-atlas.json`
4. `search-strategy-atlas.json`
5. `edit-strategy-atlas.json`
6. `verification-strategy-atlas.json`
7. `failure-recovery-atlas.json`
8. `stop-rule-atlas.json`
9. `context-memory-atlas.json`
10. `delegation-parallelism-atlas.json`
11. `permissions-sandbox-atlas.json`
12. `instruction-precedence-atlas.json`
13. `causal-intervention-results.json`
14. `mechanism-interaction-graph.json`
15. `mechanism-value-per-cost.json`
16. `failure-replay-registry.json`
17. `behavioral-inference-registry.json`
18. `known-unknown-not-looked-at.json`
19. `inverted-clone-blueprint.json`
20. `inverted-reject-list.json`
21. `next-tier-experiments.json`
22. integrity/provenance/hash artifacts from the existing assistant-value store.

The clone blueprint must express mechanisms as implementable contracts:

```text
trigger
  -> required observable state
  -> selection/routing rule
  -> action/tool policy
  -> verification rule
  -> recovery rule
  -> stop rule
  -> evidence to retain
```

It must not contain copied proprietary secrets.

## Scientific gates

A mechanism is labeled:

- OBSERVED: directly present in native evidence.
- REPLICATED: observed on >=2 independent sibling tasks.
- CAUSAL: matched intervention changes outcome/behavior in the predicted direction.
- GENERALIZED: effect replicates across >=2 task families.
- HIGH_VALUE: meaningful gain with acceptable cost/regression.
- CLONE_CANDIDATE: implementable in Inverted with sufficient evidence.
- MODIFY_CANDIDATE: useful idea but source behavior is inefficient/unsafe.
- REJECT: no gain, negative transfer, unsafe, or cost not justified.
- UNKNOWN: evidence insufficient.
- NOT_LOOKED_AT: instrument could not observe it.

No mechanism is called "how Claude/Codex thinks." The valid claim is only the
observable or causally inferred behavior.

## Native-run purity

Native Claude/Codex runs must not:
- ask the agent to explain its hidden reasoning;
- inject logging text into model context;
- alter tool inputs;
- auto-repair tool output;
- auto-approve actions beyond the preregistered permission arm;
- add a verifier that the native subject would not normally have.

Observation hooks/loggers write evidence out-of-band.

## Safety/privacy

- No real user repository is modified.
- No credentials are copied into evidence.
- Environment-variable values are never dumped wholesale.
- Home-directory scanning is prohibited except locating the exact session
  artifact by the run's own session/thread ID.
- Network tasks use allowlisted public endpoints only when explicitly enabled.
- Destructive actions occur only inside the disposable workspace.
- Public export receives a separate privacy/secret scan.

## Success criterion

This single campaign is successful if it produces enough evidence to implement
and prioritize the highest-value observable Claude Code/Codex mechanisms in
Inverted, while clearly identifying what remains unknown.

It does **not** claim byte-for-byte or proprietary-internal equivalence.
