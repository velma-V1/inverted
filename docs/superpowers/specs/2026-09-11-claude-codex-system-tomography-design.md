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
